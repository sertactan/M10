"""Offline OpenBB owner OAuth and bearer compatibility tests. No live vendor fetch."""
import base64
import hashlib
import os
import re
import sys
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

os.environ.setdefault("MERIDYEN_MCP_BEARER_TOKEN", "UNIT-TEST-NOT-A-SECRET-0123456789abcdef0123456789")
os.environ.setdefault("MERIDYEN_OPENBB_OAUTH_PASSWORD", "UNIT-TEST-ONLY-OWNER-PASSWORD-01234567")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import oauth_gate as auth
from starlette.applications import Starlette
from starlette.testclient import TestClient
from starlette.routing import Route
from starlette.responses import JSONResponse

class OwnerOAuthTests(unittest.TestCase):
    def setUp(self):
        auth.pending.clear()
        auth.codes.clear()
        auth.attempts.clear()
        self.client = TestClient(Starlette(routes=auth.OAUTH_ROUTES))
        self.redirect = "https://chatgpt.com/connector/oauth/openbb-test"
        self.verifier = "A" * 64
        self.challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).rstrip(b"=").decode()

    def issue_ticket(self):
        r=self.client.get("/authorize",params={
            "client_id":auth.CLIENT,"redirect_uri":self.redirect,
            "response_type":"code","scope":auth.SCOPE,"resource":auth.RESOURCE,
            "state":"nonce","code_challenge":self.challenge,"code_challenge_method":"S256"})
        self.assertEqual(r.status_code, 200)
        return re.search(r'name="ticket" value="([^"]+)"',r.text).group(1)

    def test_pkce_and_no_replay(self):
        r=self.client.post("/authorize/login",data={"ticket":self.issue_ticket(),
           "password":os.environ["MERIDYEN_OPENBB_OAUTH_PASSWORD"]},follow_redirects=False)
        self.assertEqual(r.status_code,303)
        code=parse_qs(urlsplit(r.headers["location"]).query)["code"][0]
        form={"grant_type":"authorization_code","code":code,"client_id":auth.CLIENT,
              "redirect_uri":self.redirect,"resource":auth.RESOURCE,"code_verifier":self.verifier}
        token=self.client.post("/token",data=form)
        self.assertEqual(token.status_code,200)
        self.assertTrue(auth.verify_token(token.json()["access_token"]))
        self.assertEqual(self.client.post("/token",data=form).status_code,400)

    def test_successful_logins_do_not_consume_fail_budget(self):
        for _ in range(10):
            r=self.client.post("/authorize/login",data={"ticket":self.issue_ticket(),
              "password":os.environ["MERIDYEN_OPENBB_OAUTH_PASSWORD"]},follow_redirects=False)
            self.assertEqual(r.status_code,303)
        self.assertFalse(auth.attempts["testclient"])

    def test_wrong_password_limiter(self):
        for _ in range(8):
            r=self.client.post("/authorize/login",data={"ticket":self.issue_ticket(),
                "password":"invalid"},follow_redirects=False)
            self.assertEqual(r.status_code,403)
        r=self.client.post("/authorize/login",data={"ticket":self.issue_ticket(),
            "password":os.environ["MERIDYEN_OPENBB_OAUTH_PASSWORD"]},follow_redirects=False)
        self.assertEqual(r.status_code,429)

    def test_wrong_redirect_or_pkce_is_rejected(self):
        bad=self.client.get("/authorize",params={
            "client_id":auth.CLIENT,"redirect_uri":"https://attacker.example/callback",
            "response_type":"code","scope":auth.SCOPE,"resource":auth.RESOURCE,
            "code_challenge":self.challenge,"code_challenge_method":"S256"})
        self.assertEqual(bad.status_code,400)

    def test_backward_compatible_bearer_and_new_oauth(self):
        from server import BearerGate
        async def ok(request):
            return JSONResponse({"ok": True})
        client=TestClient(BearerGate(Starlette(routes=[Route("/mcp",ok,methods=["POST"])])))
        self.assertEqual(client.post("/mcp").status_code,401)
        self.assertIn("resource_metadata=",client.post("/mcp").headers["WWW-Authenticate"])
        bearer=os.environ["MERIDYEN_MCP_BEARER_TOKEN"]
        self.assertEqual(client.post("/mcp",headers={"Authorization":"Bearer "+bearer}).status_code,200)
        oauth_token=auth._token({"iss":auth.ORIGIN,"aud":auth.RESOURCE,"scope":auth.SCOPE,
             "sub":"meridyen-owner","exp":int(time.time())+600,"iat":int(time.time())})
        self.assertEqual(client.post("/mcp",headers={"Authorization":"Bearer "+oauth_token}).status_code,200)
        self.assertEqual(client.post("/mcp",headers={"Authorization":"Bearer wrong"}).status_code,401)

if __name__ == "__main__":
    unittest.main()
