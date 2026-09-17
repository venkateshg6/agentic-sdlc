import tempfile
import unittest
from pathlib import Path
from shortener.service import Store, Problem
from shortener.policy import is_expired


class BoundaryTests(unittest.TestCase):
    def test_exact_boundary(self):
        self.assertTrue(is_expired(100, 100))
        self.assertFalse(is_expired(101, 100))
        self.assertFalse(is_expired(None, 100))

    def test_expired_click_not_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [100]
            store = Store(Path(directory) / "test.db", clock=lambda: now[0])
            code = store.create({"url": "https://example.com", "ttl_seconds": 1})["code"]
            now[0] = 101
            with self.assertRaises(Problem) as error:
                store.redirect(code)
            self.assertEqual(error.exception.status, 410)
            self.assertEqual(store.analytics(code)["clicks"], 0)
