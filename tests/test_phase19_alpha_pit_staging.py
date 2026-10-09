from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from scripts.phase19_alpha_pit_staging import PITStageBlocked, month_ends, stage

CSV = ("symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
       "AAA,Alpha Corp,NASDAQ,Stock,2020-01-01,null,Active\n"
       "BBB,Beta Corp,NYSE,Stock,2020-01-01,null,Active\n"
       "CCC,Gamma ETF,NASDAQ,ETF,2020-01-01,null,Active\n").encode()


class PITStagingTests(unittest.TestCase):
    def test_21_month_ends(self):
        dates = month_ends(date(2024, 1, 1), date(2025, 9, 30))
        self.assertEqual(len(dates), 21)
        self.assertEqual(str(dates[0]), "2024-01-31")
        self.assertEqual(str(dates[-1]), "2025-09-30")

    def test_preview_is_offline_and_does_not_write_files(self):
        with TemporaryDirectory() as d:
            folder = Path(d) / "out"
            result = stage(start=date(2024, 1, 1), end=date(2024, 3, 31),
                           root=folder, execute=False,
                           fetch=lambda *a: self.fail("preview contacted provider"))
            self.assertEqual(result["status"], "OFFLINE_PREVIEW_ONLY")
            self.assertFalse(folder.exists())
            self.assertEqual(len(result["remaining"]), 3)
            self.assertEqual(result["saved"], 0)

    def test_single_request_shard_and_resume(self):
        with TemporaryDirectory() as d:
            folder = Path(d)
            counter = []
            def fetch(*a):
                counter.append(1)
                return CSV
            # Mock the provider's configured property (no actual key fetched).
            from unittest.mock import patch
            with patch("scripts.phase19_alpha_pit_staging.AlphaVantagePitUniverseProvider.configured",
                       new_callable=lambda: property(lambda self: True)):
                first = stage(start=date(2024, 1, 1), end=date(2024, 3, 31),
                              root=folder, execute=True, max_requests=1, fetch=fetch)
                self.assertEqual(first["saved"], 1)
                self.assertEqual(first["api_requests"], 1)
                self.assertEqual(first["status"], "PARTIAL_RESUMABLE_RESEARCH_ONLY")
                self.assertEqual(first["snapshots"][0]["qualified_stocks"], 2)
                self.assertEqual(len(counter), 1)
                second = stage(start=date(2024, 1, 1), end=date(2024, 3, 31),
                               root=folder, execute=True, max_requests=1, fetch=fetch)
                self.assertEqual(second["reused"], 1)
                self.assertEqual(second["saved"], 1)
                self.assertEqual(len(counter), 2)
                third = stage(start=date(2024, 1, 1), end=date(2024, 3, 31),
                              root=folder, execute=True, max_requests=1, fetch=fetch)
                self.assertEqual(third["status"], "SOURCE_MONTHS_SAVED_NOT_PIT_CERTIFIED")
                self.assertEqual(third["reused"], 2)
                self.assertEqual(third["saved"], 1)
                self.assertEqual(len(counter), 3)
                self.assertFalse(third["production_database_modified"])
                self.assertFalse(third["historical_pit_identity_certified"])

    def test_tampered_cache_blocks_without_refetch(self):
        with TemporaryDirectory() as d:
            folder = Path(d)
            from unittest.mock import patch
            with patch("scripts.phase19_alpha_pit_staging.AlphaVantagePitUniverseProvider.configured",
                       new_callable=lambda: property(lambda self: True)):
                stage(start=date(2024, 1, 1), end=date(2024, 1, 31),
                      root=folder, execute=True, fetch=lambda *_: CSV)
                (folder / "2024-01-31.csv").write_text("bad")
                with self.assertRaises(PITStageBlocked):
                    stage(start=date(2024, 1, 1), end=date(2024, 1, 31),
                          root=folder, execute=True,
                          fetch=lambda *_: self.fail("refetched tampered source"))

    def test_invalid_api_payload_keeps_pit_empty(self):
        with TemporaryDirectory() as d:
            folder = Path(d)
            from unittest.mock import patch
            with patch("scripts.phase19_alpha_pit_staging.AlphaVantagePitUniverseProvider.configured",
                       new_callable=lambda: property(lambda self: True)):
                result = stage(start=date(2024, 1, 1), end=date(2024, 1, 31),
                               root=folder, execute=True,
                               fetch=lambda *_: b'{"Information":"API limit"}')
            self.assertEqual(result["status"], "PROVIDER_BLOCKED_RESUMABLE_NONCANONICAL")
            self.assertEqual(result["saved"], 0)
            self.assertFalse(folder.joinpath("2024-01-31.csv").exists())


    def test_redirect_follows_only_approved_alpha_vantage_host(self):
        import httpx
        from unittest.mock import patch
        from scripts.phase19_alpha_pit_staging import _raw_response
        from data.providers.alpha_vantage_pit_universe import AlphaVantagePitUniverseProvider

        seen_hosts = []
        def handler(request):
            seen_hosts.append(request.url.host)
            if request.url.host == "www.alphavantage.co":
                return httpx.Response(302, headers={
                    "Location": str(request.url).replace(
                        "www.alphavantage.co", "alphavantage.co", 1
                    )
                })
            return httpx.Response(200, content=CSV)
        original_client = httpx.Client
        transport = httpx.MockTransport(handler)
        with patch("httpx.Client", side_effect=lambda **kw: original_client(
            transport=transport, **kw
        )):
            response = _raw_response(
                AlphaVantagePitUniverseProvider(api_key="unit-test-key"),
                date(2024, 1, 31),
            )
        self.assertEqual(response, CSV)
        self.assertEqual(seen_hosts, ["www.alphavantage.co", "alphavantage.co"])

    def test_redirect_to_untrusted_domain_refuses_to_send_api_key(self):
        import httpx
        from unittest.mock import patch
        from scripts.phase19_alpha_pit_staging import _raw_response
        from data.providers.alpha_vantage_pit_universe import AlphaVantagePitUniverseProvider

        seen_hosts = []
        def handler(request):
            seen_hosts.append(request.url.host)
            return httpx.Response(302, headers={
                "Location": "https://example.invalid/query?apikey=stolen"
            })
        original_client = httpx.Client
        transport = httpx.MockTransport(handler)
        with patch("httpx.Client", side_effect=lambda **kw: original_client(
            transport=transport, **kw
        )):
            with self.assertRaisesRegex(PITStageBlocked, "PROVIDER_REDIRECT_HOST_NOT_ALLOWED"):
                _raw_response(
                    AlphaVantagePitUniverseProvider(api_key="unit-test-key"),
                    date(2024, 1, 31),
                )
        self.assertEqual(seen_hosts, ["www.alphavantage.co"])

    def test_failure_reports_safe_http_status_and_counts_attempt(self):
        with TemporaryDirectory() as d:
            from unittest.mock import patch
            def denied(*args):
                raise PITStageBlocked("PROVIDER_HTTP_STATUS_429")
            with patch("scripts.phase19_alpha_pit_staging.AlphaVantagePitUniverseProvider.configured",
                       new_callable=lambda: property(lambda self: True)):
                report = stage(start=date(2024, 1, 1), end=date(2024, 1, 31),
                               root=Path(d), execute=True, fetch=denied)
            self.assertEqual(report["error"], "PITStageBlocked")
            self.assertEqual(report["error_code"], "PROVIDER_HTTP_STATUS_429")
            self.assertEqual(report["api_requests"], 1)
            self.assertEqual(report["saved"], 0)
            self.assertFalse(report["production_database_modified"])


    def test_request_accept_header_matches_working_adapter(self):
        import httpx
        from unittest.mock import patch
        from scripts.phase19_alpha_pit_staging import _raw_response
        from data.providers.alpha_vantage_pit_universe import AlphaVantagePitUniverseProvider

        seen = {}
        def handler(request):
            seen["accept"] = request.headers.get("Accept")
            seen["user_agent"] = request.headers.get("User-Agent")
            return httpx.Response(200, content=CSV)
        original_client = httpx.Client
        transport = httpx.MockTransport(handler)
        with patch("httpx.Client", side_effect=lambda **kw: original_client(
            transport=transport, **kw
        )):
            result = _raw_response(
                AlphaVantagePitUniverseProvider(api_key="offline-unit-key"),
                date(2024, 1, 31),
            )
        self.assertEqual(result, CSV)
        self.assertEqual(seen["user_agent"], "S15.3 Research Terminal")
        self.assertEqual(seen["accept"], "*/*")
        self.assertNotEqual(seen["accept"], "text/csv")

    def test_provider_406_is_fail_closed_and_api_key_not_in_status(self):
        import httpx
        from unittest.mock import patch
        from scripts.phase19_alpha_pit_staging import _raw_response
        from data.providers.alpha_vantage_pit_universe import AlphaVantagePitUniverseProvider

        original_client = httpx.Client
        transport = httpx.MockTransport(lambda _req:
                                        httpx.Response(406, content=b"Not acceptable"))
        with patch("httpx.Client", side_effect=lambda **kw: original_client(
            transport=transport, **kw
        )):
            with self.assertRaisesRegex(PITStageBlocked,
                                        "PROVIDER_HTTP_STATUS_406") as context:
                _raw_response(
                    AlphaVantagePitUniverseProvider(api_key="offline-unit-key"),
                    date(2024, 1, 31),
                )
        self.assertNotIn("offline-unit-key", str(context.exception))


if __name__ == "__main__":
    unittest.main()
