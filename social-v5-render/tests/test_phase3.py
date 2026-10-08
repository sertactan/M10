"""Offline safety and PIT first-observation invariants; no live network."""
import asyncio
import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import pit_capture
import social_v5_free as core
from mcp_auth import BearerGuard


def fake_row(source_id="a", age_minutes=2):
    at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=age_minutes)
    return {
        "platform": "bluesky", "source_id": source_id,
        "created_at": core.iso(at), "observed_at": core.iso(at + dt.timedelta(seconds=20)),
        "ticker": "INOD", "text": "Research $INOD " + source_id,
        "source_url": "https://bsky.app/profile/demo/post/" + source_id,
        "author_hash": core.sha("demo")[:24], "sentiment": "",
        "capture_proof": "public_network_capture", "engagement": 1,
    }


class FirstObservedTests(unittest.TestCase):
    def test_preserve_first_seen_and_deduplicate(self):
        with tempfile.TemporaryDirectory() as td:
            row = fake_row()
            now = core.iso(dt.datetime.now(dt.timezone.utc))
            result = pit_capture.record_capture(td, "INOD", [row, row], "run1", now)
            self.assertEqual(result["new_first_seen"], 1)
            first = pathlib.Path(result["target"]).read_text()
            second = pit_capture.record_capture(td, "INOD", [row], "run2", now)
            self.assertEqual(second["new_first_seen"], 0)
            self.assertEqual(pathlib.Path(result["target"]).read_text(), first)
            record = json.loads(first.strip())
            self.assertNotIn("text", record)
            self.assertNotIn("source_url", record)
            self.assertNotIn("source_id", record)
            self.assertEqual(record["run_id"], "run1")
            self.assertEqual(record["first_observed_at"], row["observed_at"])

    def test_reject_unverified_or_no_cashtag(self):
        row = fake_row()
        row["capture_proof"] = "user_supplied_unverified"
        self.assertRaises(ValueError, pit_capture.anonymized_post, row, "INOD", "test")
        row["capture_proof"] = "public_network_capture"
        row["text"] = "INOD not a cashtag"
        self.assertRaises(ValueError, pit_capture.anonymized_post, row, "INOD", "test")

    def test_reject_future_observation(self):
        with tempfile.TemporaryDirectory() as td:
            row = fake_row()
            old_time = core.iso(dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3))
            self.assertRaises(ValueError, pit_capture.record_capture, td, "INOD", [row], "test", old_time)

    def test_capture_handles_failed_source_without_fabricating_posts(self):
        old = pit_capture.core.collect_bluesky
        oldm = pit_capture.core.collect_mastodon
        try:
            pit_capture.core.collect_bluesky = lambda *a, **k: (_ for _ in ()).throw(PermissionError("403"))
            pit_capture.core.collect_mastodon = lambda *a, **k: []
            with tempfile.TemporaryDirectory() as td:
                result = pit_capture.capture("INOD", td, "test")
                self.assertEqual(result["sources"]["bluesky"]["status"], "PUBLIC_SOURCE_UNAVAILABLE")
                self.assertEqual(result["sources"]["mastodon"]["status"], "OK")
                self.assertEqual(result["new_first_seen"], 0)
        finally:
            pit_capture.core.collect_bluesky = old
            pit_capture.core.collect_mastodon = oldm


class SecurityTests(unittest.TestCase):
    async def request(self, guard, path="/mcp", headers=None):
        messages = []
        async def app_receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        async def send(event):
            messages.append(event)
        await guard({"type": "http", "path": path, "headers": headers or []}, app_receive, send)
        return messages[0]["status"]

    @staticmethod
    async def underlying(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    def test_fail_closed(self):
        token = "this-is-a-long-random-looking-test-token-123456789"
        guard = BearerGuard(self.underlying, token=token)
        self.assertEqual(asyncio.run(self.request(guard)), 401)
        self.assertEqual(asyncio.run(self.request(guard, headers=[(b"authorization", b"Bearer wrong")])), 401)
        self.assertEqual(asyncio.run(self.request(guard, headers=[(b"authorization", ("Bearer " + token).encode())])), 200)
        self.assertEqual(asyncio.run(self.request(guard, headers=[(b"authorization", ("Bearer " + token).encode())] * 2)), 401)
        self.assertEqual(asyncio.run(self.request(guard, path="/health")), 200)

    def test_backwards_compatible_when_disabled(self):
        guard = BearerGuard(self.underlying, token="")
        self.assertEqual(asyncio.run(self.request(guard)), 200)

    def test_too_short_secret_rejected(self):
        self.assertRaises(ValueError, BearerGuard, self.underlying, "short")


if __name__ == "__main__":
    unittest.main()
