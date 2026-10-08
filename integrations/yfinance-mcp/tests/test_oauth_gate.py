"""Regression tests for private OAuth consent. No upstream network or real secrets."""
import base64
import hashlib
import os
import re
import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

os.environ.setdefault("MERIDYEN_OAUTH_PASSWORD", "test-only-owner-password-1234567890")
os.environ.setdefault("MERIDYEN_OAUTH_SIGNING_KEY", "test-only-hmac-signing-key-0123456789abcdef-0123456789")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import oauth_gate as gate
from starlette.applications import Starlette
from starlette.testclient import TestClient

class OAuthTests(unittest.TestCase):
    def setUp(self):
        gate.pending.clear()
        gate.codes.clear()
        gate.attempts.clear()
        self.client = TestClient(Starlette(routes=gate.OAUTH_ROUTES))
        self.verifier = "A" * 64
        self.challenge = base64.urlsafe_b64encode(
            hashlib.sha256(self.verifier.encode()).digest()
        ).rstrip(b"=").decode()
        self.redirect = "https://chatgpt.com/connector/oauth/meridyen-test"

    def issue_ticket(self):
        res = self.client.get("/authorize", params={
            "client_id": gate.CLIENT, "redirect_uri": self.redirect,
            "response_type": "code", "scope": gate.SCOPE,
            "resource": gate.RESOURCE, "state": "test",
            "code_challenge": self.challenge, "code_challenge_method": "S256",
        })
        self.assertEqual(res.status_code, 200)
        match = re.search(r'name="ticket" value="([^"]+)"', res.text)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_ten_successful_authorizations_do_not_lockout_owner(self):
        for _ in range(10):
            res = self.client.post("/authorize/login", data={
                "ticket": self.issue_ticket(),
                "password": os.environ["MERIDYEN_OAUTH_PASSWORD"],
            }, follow_redirects=False)
            self.assertEqual(res.status_code, 303)
        self.assertEqual(len(gate.attempts["testclient"]), 0)

    def test_failed_passwords_are_rate_limited(self):
        for _ in range(8):
            res = self.client.post("/authorize/login", data={
                "ticket": self.issue_ticket(), "password": "incorrect",
            }, follow_redirects=False)
            self.assertEqual(res.status_code, 403)
        res = self.client.post("/authorize/login", data={
            "ticket": self.issue_ticket(),
            "password": os.environ["MERIDYEN_OAUTH_PASSWORD"],
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 429)

    def test_pkce_single_use_code(self):
        res = self.client.post("/authorize/login", data={
            "ticket": self.issue_ticket(),
            "password": os.environ["MERIDYEN_OAUTH_PASSWORD"],
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 303)
        code = parse_qs(urlsplit(res.headers["location"]).query)["code"][0]
        fields = {"grant_type": "authorization_code", "code": code,
                  "client_id": gate.CLIENT, "redirect_uri": self.redirect,
                  "code_verifier": self.verifier, "resource": gate.RESOURCE}
        issued = self.client.post("/token", data=fields)
        self.assertEqual(issued.status_code, 200)
        self.assertTrue(gate.verify_token(issued.json()["access_token"]))
        replay = self.client.post("/token", data=fields)
        self.assertEqual(replay.status_code, 400)

if __name__ == "__main__":
    unittest.main()
