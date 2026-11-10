"""An actual OS process exit/restart against one disposable disk SQLite database."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import unittest


class PersistentProcessFlow(unittest.TestCase):
    def test_browser_mcp_retry_and_process_restart(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="health-persistent-proof-") as root:
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith(("MCP_", "DASHBOARD_", "DJANGO_", "OWNER_"))}
            env.update({"DJANGO_SETTINGS_MODULE": "dashboard.settings", "DASHBOARD_LOCAL_ONLY": "1",
                        "DASHBOARD_ALLOWED_HOSTS": "127.0.0.1,localhost,testserver",
                        "DASHBOARD_PRIVATE_ROOT": root,
                        "DASHBOARD_STATIC_ROOT": str(Path(root) / "staticfiles"),
                        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
                        "OWNER_USERNAME": "synthetic-owner", "MCP_SUBJECT": "synthetic-owner",
                        "MCP_RESOURCE_URL": "http://127.0.0.1:18171/mcp",
                        "MCP_ISSUER_URL": "https://issuer.example.test",
                        "MCP_JWKS_URL": "https://issuer.example.test/keys", "MCP_WRITES_ENABLED": "1"})
            for stage in ("create", "restart"):
                result = subprocess.run([sys.executable, "-m", "tests.persistent_flow_worker", stage],
                                        cwd=repo, env=env, text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                evidence = json.loads(result.stdout.strip().splitlines()[-1])
                self.assertTrue(evidence["passed"])
                self.assertEqual(evidence["stage"], stage)
                self.assertTrue((Path(root) / "dashboard.sqlite3").is_file())


if __name__ == "__main__":
    unittest.main()
