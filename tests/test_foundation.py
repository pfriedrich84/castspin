"""HTTP contract tests; these do not demonstrate Cast or audio support."""

import json
import tempfile
import threading
import unittest
from contextlib import closing
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from castspin.app import server


class FoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.config = Path(cls.temp.name) / "mappings.json"
        cls.config_patch = patch.object(server, "CONFIG", cls.config)
        cls.config_patch.start()
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)
        cls.config_patch.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.config.unlink(missing_ok=True)

    def get(self, path):
        with closing(HTTPConnection(*self.httpd.server_address, timeout=5)) as connection:
            connection.request("GET", path)
            response = connection.getresponse()
            body = response.read()
            self.assertEqual(int(response.getheader("Content-Length")), len(body))
            return response.status, response.getheader("Content-Type"), body.decode()

    def test_health_is_liveness_not_readiness(self):
        for path in ("/health", "/healthz?probe=1"):
            with self.subTest(path=path):
                status, content_type, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertEqual(content_type, "application/json")
                self.assertEqual(json.loads(body), {
                    "status": "ok",
                    "cast_receiver": "not_implemented",
                    "sendspin": "not_implemented",
                })

    def test_page_does_not_claim_playback(self):
        for path in ("/", "/index.html"):
            status, content_type, body = self.get(path)
            self.assertEqual(status, 200)
            self.assertIn("text/html", content_type)
            self.assertIn("No audio playback is available", body)
            self.assertIn("No mappings configured", body)

    def test_mappings_are_informational_only(self):
        mappings = [{"name": "Sauna", "sendspin_id": "sauna-esp32"}]
        self.config.write_text(json.dumps(mappings), encoding="utf-8")
        status, _, body = self.get("/api/mappings")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"mappings": mappings, "operational": False})

    def test_mapping_html_is_escaped(self):
        self.config.write_text(json.dumps([
            {"name": '<script>alert("x")</script>', "sendspin_id": "<img src=x>"},
            None,
        ]), encoding="utf-8")
        status, _, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertNotIn("<script>", body)
        self.assertNotIn("<img", body)
        self.assertIn("&lt;script&gt;", body)

    def test_unreadable_or_invalid_preview_mappings_do_not_crash(self):
        for value in (None, "not json", "{}", "null", '"text"', "[1, null]"):
            with self.subTest(value=value):
                if value is not None:
                    self.config.write_text(value, encoding="utf-8")
                self.assertEqual(self.get("/")[0], 200)
                self.assertEqual(self.get("/api/mappings")[0], 200)

    def test_unknown_path_does_not_expose_files(self):
        for path in ("/missing", "/../run.sh", "/data/mappings.json"):
            self.assertEqual(self.get(path), (404, "text/plain", "Not found"))


if __name__ == "__main__":
    unittest.main()
