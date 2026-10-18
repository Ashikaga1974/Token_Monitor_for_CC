"""Unit tests for security hardening (CORS, DoS, permissions, sanitization)."""

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from backend.server import StatHTTPRequestHandler, MAX_POST_PAYLOAD_BYTES
from backend.storage import secure_directory, secure_file, StorageDB
from backend.notifier import sanitize_notification_text, NotificationConfig


class TestSecurityHardening(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sanitize_notification_text_escapes_pango_and_bounds_length(self):
        # HTML / Pango markup characters should be escaped
        malicious = "<script>alert('xss')</script> & 'test' \"quotes\""
        clean = sanitize_notification_text(malicious, max_length=100)
        self.assertNotIn("<script>", clean)
        self.assertIn("&lt;script&gt;", clean)
        self.assertIn("&amp;", clean)

        # Truncation before escaping
        long_str = "A" * 300
        truncated = sanitize_notification_text(long_str, max_length=50)
        self.assertEqual(len(truncated), 50)

    def test_secure_directory_and_file_permissions(self):
        dir_path = Path(self.temp_dir.name) / "secure_sub"
        secure_directory(dir_path)
        self.assertTrue(dir_path.is_dir())
        self.assertEqual(dir_path.stat().st_mode & 0o777, 0o700)

        file_path = dir_path / "test.db"
        file_path.write_text("dummy")
        secure_file(file_path)
        self.assertEqual(file_path.stat().st_mode & 0o777, 0o600)

    def test_storage_db_initialization_secures_file(self):
        db_path = Path(self.temp_dir.name) / "history_test.db"
        db = StorageDB(db_path=db_path)
        self.assertTrue(db_path.is_file())
        self.assertEqual(db_path.stat().st_mode & 0o777, 0o600)

    def test_notification_config_save_secures_file(self):
        cfg_path = Path(self.temp_dir.name) / "config.json"
        cfg = NotificationConfig()
        cfg.save(cfg_path)
        self.assertTrue(cfg_path.is_file())
        self.assertEqual(cfg_path.stat().st_mode & 0o777, 0o600)

    def _create_mock_handler(self, command: str, path: str, headers: dict, body: bytes = b""):
        """Creates a mock StatHTTPRequestHandler for isolated testing."""
        request = MagicMock()
        client_address = ("127.0.0.1", 12345)
        server = MagicMock()

        handler = StatHTTPRequestHandler.__new__(StatHTTPRequestHandler)
        handler.command = command
        handler.path = path
        handler.requestline = f"{command} {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.close_connection = True
        handler.request = request
        handler.client_address = client_address
        handler.server = server

        header_lines = [f"{k}: {v}\r\n" for k, v in headers.items()]
        header_raw = "".join(header_lines) + "\r\n"
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()

        # Parse headers
        from http.client import HTTPMessage
        import email
        handler.headers = email.message_from_string(header_raw)
        return handler

    def test_server_rejects_origin_header(self):
        # Any browser request that sets an Origin header must be rejected with 403
        handler = self._create_mock_handler("GET", "/stats", {"Origin": "https://malicious.example.com"})
        handler.do_GET()

        response = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("403 Forbidden", response)
        self.assertIn("Forbidden: cross-origin browser requests not permitted", response)

    def test_server_rejects_options_preflight(self):
        handler = self._create_mock_handler("OPTIONS", "/stats", {"Origin": "https://malicious.example.com"})
        handler.do_OPTIONS()

        response = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("403 Forbidden", response)

    @patch("backend.server.get_cached_or_fresh_stats")
    def test_server_no_cors_headers_on_valid_get(self, mock_stats):
        mock_stats.return_value = {"mock": "data"}
        handler = self._create_mock_handler("GET", "/stats", {})
        handler.do_GET()

        response = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("200 OK", response)
        self.assertNotIn("Access-Control-Allow-Origin", response)

    def test_server_rejects_oversized_post_payload(self):
        oversized = b"A" * (MAX_POST_PAYLOAD_BYTES + 100)
        handler = self._create_mock_handler(
            "POST",
            "/notify-config",
            {"Content-Length": str(len(oversized))},
            body=oversized,
        )
        handler.do_POST()

        response = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("413", response)
        self.assertIn("Payload Too Large (max 64KB)", response)


if __name__ == "__main__":
    unittest.main()
