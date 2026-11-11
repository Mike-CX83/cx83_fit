"""ASGI HTTP and signed JWT checks, with synthetic service fixtures.

The default uses Starlette's in-process transport, with the real SDK, lifespan,
HTTP middleware and token verifier. Set DASHBOARD_TEST_LOOPBACK=1 to repeat the
same cases through an actual Uvicorn socket. Neither proves external OAuth,
ChatGPT connectivity, persistence or visual browser rendering.
"""
import json
import os
import socket
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

try:
    import jwt
    import uvicorn
    from cryptography.hazmat.primitives.asymmetric import rsa
    from starlette.testclient import TestClient
    from dashboard.mcp_server import MCPConfig, OwnerTokenVerifier, create_mcp_app
    DEPENDENCY_ERROR = None
except ImportError as exc:
    DEPENDENCY_ERROR = str(exc)


class FixtureJwksClient:
    """Trusted fixture keys, no external network or real credentials."""
    def __init__(self, public_key):
        self.jwk = jwt.PyJWK.from_dict({
            **json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key)),
            "kid": "synthetic-key", "alg": "RS256", "use": "sig",
        })

    def get_signing_key_from_jwt(self, token):
        if jwt.get_unverified_header(token).get("kid") != "synthetic-key":
            raise jwt.PyJWKClientError("Unknown fixture key")
        return self.jwk


# Names read from the current dashboard/mcp_server.py registrations. These are
# the expected catalog, not a copy of whatever tools/list returns.
UNCONDITIONAL_CATALOG = frozenset({
    "read_measurements", "read_tracking", "read_overview", "read_fitness_plan",
    "read_oura", "read_photo", "read_journal", "preview_journal", "save_journal_entry",
    "delete_journal_entry", "read_journal_context", "read_sobriety_pattern",
    "save_journal_memory", "record_journal_question", "read_governing_document",
    "save_meal", "read_watch_signals", "read_headroom", "read_clinical_items",
    "save_clinical_item", "stop_clinical_item",
})
WRITE_CATALOG = frozenset({"save_review", "write_measurement"})
SITE_CATALOG = frozenset({
    "read_repository_file", "search_repository", "apply_repository_edit", "commit_and_publish",
})
# These seven were absent from the recorded ChatGPT session catalog. They are
# unconditional in the current source and must stay present with both flags off.
SESSION_ABSENT_CATALOG = frozenset({
    "read_sobriety_pattern", "save_meal", "read_watch_signals", "read_headroom",
    "read_clinical_items", "save_clinical_item", "stop_clinical_item",
})


@unittest.skipIf(DEPENDENCY_ERROR is not None, f"MCP HTTP dependencies unavailable: {DEPENDENCY_ERROR}")
class MCPHTTPTests(unittest.TestCase):
    loopback = False

    def setUp(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        if self.loopback:
            self.sock = socket.socket()
            self.addCleanup(self.sock.close)
            self.sock.bind(("127.0.0.1", 0))
            self.base = f"http://127.0.0.1:{self.sock.getsockname()[1]}"
        else:
            self.base = "http://127.0.0.1:18171"
        self.config = MCPConfig(
            "https://issuer.example.test", "https://issuer.example.test/keys",
            self.base + "/mcp", "synthetic-owner", writes_enabled=True,
        )
        self.verifier = OwnerTokenVerifier(self.config,
                                          jwks_client=FixtureJwksClient(self.key.public_key()))
        self.app = create_mcp_app(self.config, verifier=self.verifier)
        if self.loopback:
            self.server = uvicorn.Server(uvicorn.Config(self.app, log_level="critical", access_log=False))
            self.thread = threading.Thread(target=self.server.run, kwargs={"sockets": [self.sock]}, daemon=True)
            self.thread.start()
            self.addCleanup(self.stop_server)
            deadline = time.monotonic() + 5
            while not self.server.started and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(self.server.started, "Loopback server did not start")
        else:
            self.client = TestClient(self.app, base_url=self.base)
            self.client.__enter__()
            self.addCleanup(self.client.__exit__, None, None, None)

    def stop_server(self):
        self.server.should_exit = True
        self.thread.join(timeout=5)

    def token(self, **overrides):
        claims = {"iss": self.config.issuer, "sub": self.config.subject,
                  "aud": self.config.resource, "iat": int(time.time()),
                  "exp": int(time.time()) + 120, "client_id": "synthetic-client",
                  "scope": "health:read"}
        claims.update(overrides)
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "synthetic-key"})

    def rpc(self, method, params=None, token=None, extra_headers=None):
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream",
                   "MCP-Protocol-Version": "2025-11-25"}
        if token:
            headers["Authorization"] = "Bearer " + token
        headers.update(extra_headers or {})
        payload = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            payload["params"] = params
        if not self.loopback:
            response = self.client.post("/mcp", json=payload, headers=headers)
            try:
                return response.status_code, response.json()
            except ValueError:
                return response.status_code, {"http_error": response.status_code}
        request = Request(self.base + "/mcp", data=json.dumps(payload).encode(), headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            body = exc.read()
            try:
                parsed = json.loads(body)
            except ValueError:
                parsed = {"http_error": exc.code}
            return exc.code, parsed

    def test_missing_token_cannot_list_tools(self):
        self.assertEqual(self.rpc("tools/list")[0], 401)

    def test_rejects_wrong_issuer_audience_subject_and_expiry(self):
        for change in ({"iss": "https://untrusted.example.test"},
                       {"aud": "https://another.example.test/mcp"},
                       {"sub": "another-owner"}, {"exp": int(time.time()) - 30}):
            with self.subTest(change=change):
                self.assertEqual(self.rpc("tools/list", token=self.token(**change))[0], 401)

    def test_read_scope_required_even_for_write_token(self):
        self.assertEqual(self.rpc("tools/list", token=self.token(scope="health:write"))[0], 403)

    def test_authenticated_read_calls_bounded_shared_service(self):
        with patch("dashboard.mcp_server._read_records", return_value={"items": [], "count": 0}) as service:
            status, body = self.rpc("tools/call", {"name": "read_measurements", "arguments": {
                "start": "2026-11-01", "end": "2026-11-05"}}, token=self.token())
            self.assertEqual(status, 200)
            self.assertFalse(body.get("result", {}).get("isError", False), body)
            service.assert_called_once_with("2026-11-01", "2026-11-05", False, 100, 0)

    @staticmethod
    def write_arguments():
        return {"measurement": {"metric": "weight", "value": "100", "unit": "kg",
                                "local_date": "2026-11-05", "synthetic": True},
                "request_id": "99fffd01-bf48-4513-8768-e56755f848cc",
                "explicitly_authorized": True}

    def test_read_token_cannot_write(self):
        with patch("dashboard.mcp_server._put_record") as service:
            status, body = self.rpc("tools/call", {"name": "write_measurement",
                "arguments": self.write_arguments()}, token=self.token())
            self.assertEqual(status, 200)
            self.assertTrue(body["result"]["isError"])
            service.assert_not_called()

    def test_extended_reads_require_auth_and_forward_validated_arguments(self):
        for name, service_name, arguments in [
            ('read_tracking', '_read_tracking', {'kind': 'nutrition', 'start': '2026-11-01', 'end': '2026-11-05'}),
            ('read_overview', '_read_overview', {'start': '2026-11-01', 'end': '2026-11-05'}),
            ('read_oura', '_read_oura', {'collection': 'daily_sleep'}),
        ]:
            with patch('dashboard.mcp_server.'+service_name, return_value={'synthetic': True}) as service:
                self.assertEqual(self.rpc('tools/call', {'name': name, 'arguments': arguments})[0], 401)
                service.assert_not_called()
                status, body = self.rpc('tools/call', {'name': name, 'arguments': arguments}, token=self.token())
                self.assertEqual(status, 200)
                self.assertFalse(body['result'].get('isError', False), body)
                service.assert_called_once()

    def test_photo_image_requires_explicit_request_and_returns_image_content(self):
        arguments = {'photo_id': '99fffd01-bf48-4513-8768-e56755f848cc', 'explicitly_requested': False}
        with patch('dashboard.mcp_server._read_photo', return_value=({'synthetic': True}, b'synthetic-image')) as service:
            _, body = self.rpc('tools/call', {'name': 'read_photo', 'arguments': arguments}, token=self.token())
            self.assertTrue(body['result']['isError'])
            service.assert_not_called()
            arguments['explicitly_requested'] = True
            _, body = self.rpc('tools/call', {'name': 'read_photo', 'arguments': arguments}, token=self.token())
            self.assertFalse(body['result'].get('isError', False), body)
            self.assertEqual(body['result']['content'][1]['type'], 'image')
            self.assertEqual(body['result']['content'][1]['mimeType'], 'image/jpeg')

    def test_review_save_requires_write_scope_and_explicit_intent(self):
        arguments = {'text': 'Synthetic review only', 'local_date': '2026-11-05',
            'request_id': '99fffd01-bf48-4513-8768-e56755f848cc', 'synthetic': True, 'explicitly_authorized': True}
        with patch('dashboard.mcp_server._save_review', return_value={'id':'synthetic','synthetic':True}) as service:
            _, body = self.rpc('tools/call', {'name':'save_review','arguments':arguments}, token=self.token())
            self.assertTrue(body['result']['isError']); service.assert_not_called()
            arguments['explicitly_authorized'] = False
            _, body = self.rpc('tools/call', {'name':'save_review','arguments':arguments}, token=self.token(scope='health:read health:write'))
            self.assertTrue(body['result']['isError']); service.assert_not_called()
            arguments['explicitly_authorized'] = True
            _, body = self.rpc('tools/call', {'name':'save_review','arguments':arguments}, token=self.token(scope='health:read health:write'))
            self.assertFalse(body['result'].get('isError',False),body)
            service.assert_called_once()

    def test_scoped_write_requires_explicit_intent(self):
        args = self.write_arguments()
        args["explicitly_authorized"] = False
        with patch("dashboard.mcp_server._put_record") as service:
            status, body = self.rpc("tools/call", {"name": "write_measurement", "arguments": args},
                                    token=self.token(scope="health:read health:write"))
            self.assertEqual(status, 200)
            self.assertTrue(body["result"]["isError"])
            service.assert_not_called()

    def test_scoped_authorized_synthetic_write(self):
        with patch("dashboard.mcp_server._put_record", return_value={"id": "synthetic", "version": 1}) as service:
            status, body = self.rpc("tools/call", {"name": "write_measurement",
                "arguments": self.write_arguments()}, token=self.token(scope="health:read health:write"))
            self.assertEqual(status, 200)
            self.assertFalse(body.get("result", {}).get("isError", False), body)
            self.assertTrue(service.call_args.args[0]["synthetic"])

    def test_unknown_payload_fields_rejected(self):
        args = self.write_arguments()
        args["measurement"]["source_system"] = "clinical"
        with patch("dashboard.mcp_server._put_record") as service:
            status, body = self.rpc("tools/call", {"name": "write_measurement", "arguments": args},
                                    token=self.token(scope="health:read health:write"))
            self.assertEqual(status, 200)
            self.assertTrue(body["result"]["isError"])
            service.assert_not_called()

    def test_bad_origin_rejected(self):
        self.assertEqual(self.rpc("tools/list", token=self.token(),
                                 extra_headers={"Origin": "https://malicious.example.test"})[0], 403)

    def test_journal_tools_follow_the_read_connection(self):
        status, body = self.rpc("tools/list", token=self.token())
        self.assertEqual(status, 200, body)
        names = [tool["name"] for tool in body["result"]["tools"]]
        for name in ("read_journal", "preview_journal", "save_journal_entry", "delete_journal_entry"):
            self.assertIn(name, names)
        arguments = {"body": "Synthetic journal from the client.", "local_date": "2026-11-08",
                     "request_id": "99fffd01-bf48-4513-8768-e56755f848cc", "explicitly_authorized": False,
                     "synthetic": True}
        with patch("dashboard.mcp_server._save_journal_entry", return_value={"id": "synthetic"}) as service:
            _, denied = self.rpc("tools/call", {"name": "save_journal_entry", "arguments": arguments}, token=self.token())
            self.assertTrue(denied["result"]["isError"])
            service.assert_not_called()
            arguments["explicitly_authorized"] = True
            _, allowed = self.rpc("tools/call", {"name": "save_journal_entry", "arguments": arguments}, token=self.token())
            self.assertFalse(allowed["result"].get("isError", False), allowed)
            service.assert_called_once()
        with patch("dashboard.mcp_server._preview_journal", return_value={"persisted": False, "accepted": []}) as preview:
            _, checked = self.rpc("tools/call", {"name": "preview_journal", "arguments": {
                "body": "I did not meditate.", "proposals": [{
                    "domain_id": 18, "metric_key": "explicit_choice", "value_state": "observed",
                    "boolean": False, "support_span": "I did not meditate", "temporal_scope": "completed"}]}},
                token=self.token())
            self.assertFalse(checked["result"].get("isError", False), checked)
            preview.assert_called_once()

    def catalog_names(self, *, writes_enabled, site_edits_enabled):
        config = MCPConfig(
            self.config.issuer, self.config.jwks_url, self.config.resource, self.config.subject,
            writes_enabled=writes_enabled, site_edits_enabled=site_edits_enabled,
        )
        verifier = OwnerTokenVerifier(config, jwks_client=FixtureJwksClient(self.key.public_key()))
        app = create_mcp_app(config, verifier=verifier)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-11-25",
            "Authorization": "Bearer " + self.token(),
        }
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        with TestClient(app, base_url=self.base) as client:
            response = client.post("/mcp", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        tools = body["result"]["tools"]
        return [tool["name"] for tool in tools]

    def test_authenticated_catalog_follows_feature_flags(self):
        self.assertEqual(len(UNCONDITIONAL_CATALOG), 21)
        self.assertEqual(len(WRITE_CATALOG), 2)
        self.assertEqual(len(SITE_CATALOG), 4)
        self.assertTrue(SESSION_ABSENT_CATALOG <= UNCONDITIONAL_CATALOG)
        self.assertTrue(UNCONDITIONAL_CATALOG.isdisjoint(WRITE_CATALOG | SITE_CATALOG))
        cases = (
            (False, False, 21),
            (True, False, 23),
            (False, True, 25),
            (True, True, 27),
        )
        for writes_enabled, site_edits_enabled, total in cases:
            with self.subTest(writes_enabled=writes_enabled, site_edits_enabled=site_edits_enabled):
                names = self.catalog_names(
                    writes_enabled=writes_enabled, site_edits_enabled=site_edits_enabled)
                expected = set(UNCONDITIONAL_CATALOG)
                if writes_enabled:
                    expected.update(WRITE_CATALOG)
                if site_edits_enabled:
                    expected.update(SITE_CATALOG)
                self.assertEqual(len(names), len(set(names)))
                self.assertEqual(set(names), expected)
                self.assertEqual(len(names), total)
                if not writes_enabled and not site_edits_enabled:
                    self.assertTrue(SESSION_ABSENT_CATALOG <= set(names))

    def test_metadata_advertises_optional_write_scope(self):
        if self.loopback:
            with urlopen(self.base + "/.well-known/oauth-protected-resource/mcp", timeout=5) as response:
                metadata = json.load(response)
        else:
            response = self.client.get("/.well-known/oauth-protected-resource/mcp")
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response.headers["cache-control"])
            metadata = response.json()
        self.assertEqual(set(metadata["scopes_supported"]), {"health:read", "health:write"})

    def test_default_configuration_disables_mcp_and_partial_config_fails(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(MCPConfig.from_environment())
        with patch.dict("os.environ", {"MCP_SUBJECT": "owner"}, clear=True):
            with self.assertRaises(ValueError):
                MCPConfig.from_environment()


@unittest.skipUnless(os.environ.get("DASHBOARD_TEST_LOOPBACK") == "1",
                     "Real socket verification is opt-in: DASHBOARD_TEST_LOOPBACK=1")
class MCPLoopbackTests(MCPHTTPTests):
    loopback = True


if __name__ == "__main__":
    unittest.main()
