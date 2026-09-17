import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from shortener.api import create_app
from shortener.service import Problem, Store, validate_url


class ShortenerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 1000000.0
        self.store = Store(Path(self.temp.name) / "links.db", clock=lambda: self.now)

    def test_create_redirect_analytics(self):
        item = self.store.create({"url": "https://example.com/a"})
        self.assertEqual(self.store.redirect(item["code"]), "https://example.com/a")
        self.assertEqual(self.store.analytics(item["code"])["clicks"], 1)
        self.assertEqual(self.store.analytics(item["code"])["daily"][0]["clicks"], 1)

    def test_idempotency(self):
        body = {"url": "https://example.com"}
        self.assertEqual(self.store.create(body, "request1"), self.store.create(body, "request1"))
        with self.assertRaises(Problem) as error:
            self.store.create({"url": "https://example.org"}, "request1")
        self.assertEqual(error.exception.status, 409)

    def test_alias_conflict(self):
        body = {"url": "https://example.com", "alias": "demo"}
        self.store.create(body)
        with self.assertRaises(Problem) as error:
            self.store.create(body)
        self.assertEqual(error.exception.status, 409)

    def test_collision_retry(self):
        self.store.create({"url": "https://example.com", "alias": "same"})
        codes = iter(["same", "fresh"])
        self.store.code_factory = lambda: next(codes)
        self.assertEqual(self.store.create({"url": "https://example.org"})["code"], "fresh")

    def test_collision_exhaustion(self):
        self.store.create({"url": "https://example.com", "alias": "same"})
        self.store.code_factory = lambda: "same"
        with self.assertRaises(Problem) as error:
            self.store.create({"url": "https://example.com"})
        self.assertEqual(error.exception.status, 503)

    def test_expiration(self):
        code = self.store.create({"url": "https://example.com", "ttl_seconds": 5})["code"]
        self.now += 6
        with self.assertRaises(Problem) as error:
            self.store.redirect(code)
        self.assertEqual(error.exception.status, 410)
        self.assertEqual(self.store.get(code)["clicks"], 0)

    def test_disable(self):
        code = self.store.create({"url": "https://example.com"})["code"]
        self.store.disable(code)
        self.store.disable(code)
        with self.assertRaises(Problem) as error:
            self.store.redirect(code)
        self.assertEqual(error.exception.status, 410)

    def test_not_found(self):
        for fn in (self.store.get, self.store.redirect, self.store.disable, self.store.analytics):
            with self.assertRaises(Problem) as error:
                fn("missing")
            self.assertEqual(error.exception.status, 404)

    def test_bad_urls(self):
        for url in (None, "javascript:alert(1)", "file:///etc/passwd", "http://localhost/x",
                    "http://127.0.0.1", "http://[::1]", "https://x:y@example.com", "https://example.com\r\nX:1",
                    "http://10.0.0.1", "https://example.com:bad", "https://example.com/a b"):
            with self.subTest(url=url), self.assertRaises(Problem):
                validate_url(url)

    def test_invalid_fields(self):
        for body in ([], {"url": "https://example.com", "alias": "../x"},
                     {"url": "https://example.com", "ttl_seconds": True},
                     {"url": "https://example.com", "ttl_seconds": 0},
                     {"url": "https://example.com", "unexpected": 1}):
            with self.subTest(body=body), self.assertRaises(Problem):
                self.store.create(body)

    def test_concurrent_clicks(self):
        code = self.store.create({"url": "https://example.com"})["code"]
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: self.store.redirect(code), range(40)))
        self.assertEqual(self.store.get(code)["clicks"], 40)

    def test_rate_limit_and_reset(self):
        self.store.limit("client", maximum=1)
        with self.assertRaises(Problem) as error:
            self.store.limit("client", maximum=1)
        self.assertEqual(error.exception.status, 429)
        self.now += 61
        self.store.limit("client", maximum=1)

    def test_sql_parameterization(self):
        with self.assertRaises(Problem):
            self.store.get("' OR 1=1 --")
        self.assertTrue(self.store.create({"url": "https://example.com"})["code"])


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.key = "test-key-not-a-real-secret"
        self.app = create_app(str(Path(self.temp.name) / "api.db"), self.key)

    def request(self, method, path, body=None, auth=True, raw=None, content_type="application/json"):
        data = raw if raw is not None else json.dumps(body).encode() if body is not None else b""
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_TYPE": content_type,
               "CONTENT_LENGTH": str(len(data)), "wsgi.input": io.BytesIO(data), "REMOTE_ADDR": "127.0.0.1"}
        if auth:
            env["HTTP_AUTHORIZATION"] = "Bearer " + self.key
        result = {}
        def start(status, headers):
            result.update(status=int(status.split()[0]), headers=dict(headers))
        result["body"] = json.loads(b"".join(self.app(env, start)))
        return result

    def test_http_flow(self):
        created = self.request("POST", "/api/v1/urls", {"url": "https://example.com", "alias": "test"})
        self.assertEqual(created["status"], 201)
        response = self.request("GET", "/r/test", auth=False)
        self.assertEqual(response["status"], 302)
        self.assertEqual(response["headers"]["Location"], "https://example.com")
        self.assertEqual(self.request("GET", "/api/v1/urls/test/analytics")["body"]["clicks"], 1)
        self.assertEqual(self.request("DELETE", "/api/v1/urls/test")["status"], 200)
        self.assertEqual(self.request("GET", "/r/test")["status"], 410)

    def test_auth(self):
        self.assertEqual(self.request("POST", "/api/v1/urls", {}, auth=False)["status"], 401)
        self.assertEqual(self.request("GET", "/api/v1/urls/test/analytics", auth=False)["status"], 401)

    def test_json_and_body_limits(self):
        self.assertEqual(self.request("POST", "/api/v1/urls", raw=b"not json")["status"], 400)
        self.assertEqual(self.request("POST", "/api/v1/urls", raw=b"x" * 8193)["status"], 413)
        self.assertEqual(self.request("POST", "/api/v1/urls", {}, content_type="text/plain")["status"], 415)

    def test_health_and_headers(self):
        response = self.request("GET", "/health", auth=False)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["headers"]["X-Content-Type-Options"], "nosniff")
        self.assertIn("X-Request-ID", response["headers"])

    def test_rate_limit_http(self):
        with patch("shortener.service.Store.limit", side_effect=Problem(429, "Limit")):
            response = self.request("GET", "/r/test")
        self.assertEqual(response["status"], 429)
        self.assertEqual(response["headers"]["Retry-After"], "60")

    def test_weak_key_refused(self):
        with self.assertRaises(ValueError):
            create_app(str(Path(self.temp.name) / "weak.db"), "short")


if __name__ == "__main__":
    unittest.main()
