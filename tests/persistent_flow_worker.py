"""Synthetic two-process acceptance helper. Never a production server or issuer.

Invoked only by test_persistent_flow with a disposable private directory. The
Starlette client sends actual ASGI requests without opening a network socket.
Only the external JWKS fetch is replaced, with an ephemeral RSA public key.
Browser sessions, CSRF, MCP authorization, services and SQLite are real.
"""
import json
import os
from pathlib import Path
import sys
import time
from html.parser import HTMLParser
from unittest.mock import patch
from uuid import uuid4

import django

django.setup()

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.asgi import get_asgi_application
from django.core.management import call_command
from django.utils import timezone
from starlette.testclient import TestClient

from dashboard.mcp_server import build_application
from tests.test_mcp_http import FixtureJwksClient
from tracking.models import Correction, Measurement, WriteRequest


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "input" and data.get("name"):
            self.values[data["name"]] = data.get("value", "")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def login(browser):
    page = browser.get("/login/")
    require(page.status_code == 200, "Login page failed")
    require(page.headers.get("referrer-policy") == "same-origin",
            "MCP composition must preserve browser form origin policy")
    csrf = Inputs(page.text).values["csrfmiddlewaretoken"]
    response = browser.post("/login/", data={
        "username": settings.OWNER_USERNAME,
        "password": "synthetic-local-proof-password-123",
        "csrfmiddlewaretoken": csrf,
    })
    require(response.status_code == 302, "Real password login failed")
    require(browser.get("/").status_code == 200, "Owner page failed")


def main():
    stage = sys.argv[1]
    require(stage in {"create", "restart"}, "Unknown proof stage")
    root = settings.PRIVATE_ROOT
    state_path = root / "synthetic-proof-state.json"
    if stage == "create":
        require(not state_path.exists(), "Must use a fresh disposable directory")
        call_command("migrate", verbosity=0)
        call_command("collectstatic", verbosity=0, interactive=False)
        get_user_model().objects.create_user(
            settings.OWNER_USERNAME, password="synthetic-local-proof-password-123")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = FixtureJwksClient(key.public_key())
    with patch("dashboard.mcp_server.PyJWKClient", return_value=jwks):
        app = build_application(get_asgi_application())

    def token(scope="health:read"):
        return jwt.encode({
            "iss": os.environ["MCP_ISSUER_URL"], "aud": os.environ["MCP_RESOURCE_URL"],
            "sub": os.environ["MCP_SUBJECT"], "iat": int(time.time()),
            "exp": int(time.time()) + 120, "client_id": "synthetic-client", "scope": scope,
        }, key, algorithm="RS256", headers={"kid": "synthetic-key"})

    with TestClient(app, base_url="http://127.0.0.1:18171", follow_redirects=False) as browser:
        def rpc(method, params, scope="health:read"):
            response = browser.post("/mcp", json={
                "jsonrpc": "2.0", "id": 1, "method": method, "params": params,
            }, headers={"Authorization": "Bearer " + token(scope),
                        "Accept": "application/json, text/event-stream",
                        "MCP-Protocol-Version": "2025-11-25"})
            require(response.status_code == 200, "MCP transport rejected valid request")
            require("no-store" in response.headers["cache-control"], "Missing MCP privacy header")
            body = response.json()
            require("error" not in body, "MCP protocol returned an error")
            return body["result"]

        def read(include=True):
            result = rpc("tools/call", {"name": "read_measurements", "arguments": {
                "start": str(timezone.localdate()), "end": str(timezone.localdate()),
                "include_synthetic": include}})
            require(not result.get("isError"), "MCP read failed")
            # The SDK may encode an untyped dict as JSON text content.
            return result.get("structuredContent") or json.loads(result["content"][0]["text"])

        require(browser.get("/").status_code == 302, "Anonymous history accessible")
        require(browser.post("/mcp", json={}).status_code == 401, "Anonymous MCP accessible")
        rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                           "clientInfo": {"name": "local-acceptance", "version": "1"}})

        if stage == "create":
            login(browser)
            require(browser.post("/measurements/new/", data={}).status_code == 403,
                    "CSRF missing but browser write accepted")
            page = browser.get("/measurements/new/")
            fields = Inputs(page.text).values
            form = {"csrfmiddlewaretoken": fields["csrfmiddlewaretoken"],
                    "request_id": fields["request_id"], "metric": "weight",
                    "value": "100.125", "unit": "kg", "local_date": str(timezone.localdate()),
                    "synthetic": "on", "notes": "Synthetic process restart proof"}
            require(browser.post("/measurements/new/", data=form).status_code == 302,
                    "Browser save failed")
            require(browser.post("/measurements/new/", data=form).status_code == 302,
                    "Browser retry failed")
            require(read(False)["count"] == 0, "Synthetic entry leaked into personal MCP history")
            observed = read()
            require(observed["count"] == 1, "Browser retry duplicated measurement")
            original = observed["items"][0]
            require(original["value"] == "100.125", "Browser value missing through MCP")
            args = {"measurement": {"metric": "weight", "value": "101.250", "unit": "kg",
                    "local_date": str(timezone.localdate()), "synthetic": True,
                    "notes": "Synthetic process restart proof"},
                    "request_id": str(uuid4()), "record_id": original["id"],
                    "expected_version": 1, "explicitly_authorized": True}
            request = {"name": "write_measurement", "arguments": args}
            denied = rpc("tools/call", request)
            require(denied.get("isError"), "Read-only token changed a measurement")
            corrected = rpc("tools/call", request, "health:read health:write")
            require(not corrected.get("isError"), "Authorized correction failed")
            require(rpc("tools/call", request, "health:read health:write") == corrected,
                    "Identical retry changed its response")
            state = {"args": args, "result": corrected, "id": original["id"],
                     "cookies": dict(browser.cookies)}
            with state_path.open("x") as output:
                os.chmod(state_path, 0o600)
                json.dump(state, output)
        else:
            state = json.loads(state_path.read_text())
            browser.cookies.update(state["cookies"])
            require(browser.get("/").status_code == 200, "Session did not survive process restart")
            require(rpc("tools/call", {"name": "write_measurement", "arguments": state["args"]},
                        "health:read health:write") == state["result"],
                    "Retry after restart did not recover original committed result")

        records = read()
        require(records["count"] == 1, "Unexpected measurement count")
        require(records["items"][0]["value"] == "101.250", "Correction did not persist")
        require(records["items"][0]["version"] == 2, "Retry changed revision")
        page = browser.get("/?synthetic=1")
        require(page.status_code == 200 and "101.250" in page.text, "Browser cannot read MCP correction")
        require("101.250" not in browser.get("/").text, "Synthetic entry in personal browser history")
        css = browser.get("/static/tracking/app.css")
        require(css.status_code == 200 and "text/css" in css.headers["content-type"],
                "Static stylesheet unavailable with DEBUG=False")
        require(Measurement.objects.count() == 1, "Duplicate row")
        require(Correction.objects.count() == 2, "Duplicate or missing audit")
        require(WriteRequest.objects.count() == 2, "Unexpected committed write requests")
        require(Correction.objects.get(operation="update").before["value"] == "100.125",
                "Original value missing from correction history")
        # Issuer failure must deny MCP while the owner's stored history remains usable.
        with patch.object(jwks, "get_signing_key_from_jwt", side_effect=OSError("synthetic outage")):
            response = browser.post("/mcp", json={}, headers={"Authorization": "Bearer " + token()})
            require(response.status_code == 401, "Issuer outage did not fail closed")
            require("101.250" in browser.get("/?synthetic=1").text,
                    "Stored browser history unavailable during issuer outage")
    print(json.dumps({"stage": stage, "transport": "in-process ASGI", "passed": True,
                      "measurements": 1, "revisions": 2}))


if __name__ == "__main__":
    main()
