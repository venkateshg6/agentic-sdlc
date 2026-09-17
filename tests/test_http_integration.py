"""Real loopback HTTP integration, without following the external redirect."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from wsgiref.simple_server import make_server
from shortener.api import create_app, PrivateRequestHandler


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class HTTPIntegrationTests(unittest.TestCase):
    def test_socket_roundtrip(self):
        with tempfile.TemporaryDirectory() as root:
            app = create_app(str(Path(root) / "http.db"), "integration-test-token")
            with make_server("127.0.0.1", 0, app, handler_class=PrivateRequestHandler) as server:
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    base = f"http://127.0.0.1:{server.server_port}"
                    req = urllib.request.Request(base + "/api/v1/urls",
                        data=b'{"url":"https://example.com","alias":"demo"}',
                        headers={"Authorization": "Bearer integration-test-token", "Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        self.assertEqual(response.status, 201)
                        self.assertEqual(json.load(response)["short_path"], "/r/demo")
                    opener = urllib.request.build_opener(NoRedirect())
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        opener.open(base + "/r/demo", timeout=5)
                    self.assertEqual(error.exception.code, 302)
                    self.assertEqual(error.exception.headers["Location"], "https://example.com")
                    error.exception.close()
                    req = urllib.request.Request(base + "/api/v1/urls/demo/analytics",
                        headers={"Authorization": "Bearer integration-test-token"})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        self.assertEqual(json.load(response)["clicks"], 1)
                finally:
                    server.shutdown()
                    worker.join(timeout=5)
