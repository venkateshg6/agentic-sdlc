import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch
from orchestrator.provider import Provider, ProviderError


class ProviderTests(unittest.TestCase):
    def setUp(self):
        env = {"LLM_BASE_URL": "https://provider.example/v1", "LLM_MODEL": "test-model", "LLM_API_KEY": "fake"}
        self.patcher = patch.dict(os.environ, env, clear=True)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_valid_json(self):
        response = json.dumps({"choices": [{"message": {"content": '{"files":{}}'}}]}).encode()
        p = Provider(lambda *a, **k: io.BytesIO(response), lambda _: None)
        self.assertEqual(p.complete("developer", {}), {"files": {}})
        self.assertEqual(len(p.calls), 1)

    def test_retries_and_fallback(self):
        count = [0]
        def transport(*args, **kwargs):
            count[0] += 1
            if count[0] <= 3:
                raise urllib.error.HTTPError("https://provider.example", 429, "busy", {}, None)
            return io.BytesIO(b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}')
        os.environ.update(LLM_FALLBACK_BASE_URL="https://fallback.example/v1", LLM_FALLBACK_MODEL="fallback")
        p = Provider(transport, lambda _: None)
        self.assertEqual(p.complete("test", {}), {"ok": True})
        self.assertEqual(len(p.calls), 4)
        self.assertEqual(p.calls[-1]["provider"], "LLM_FALLBACK")

    def test_invalid_json_exhaustion(self):
        p = Provider(lambda *a, **k: io.BytesIO(b"bad"), lambda _: None)
        with self.assertRaises(ProviderError):
            p.complete("test", {})
        self.assertEqual(len(p.calls), 3)

    def test_insecure_remote_refused(self):
        os.environ["LLM_BASE_URL"] = "http://provider.example/v1"
        with self.assertRaises(ProviderError):
            Provider().complete("test", {})
