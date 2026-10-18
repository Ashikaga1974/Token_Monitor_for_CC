"""Tests for the configurable API base URL handling in backend/client.py."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend import client
from backend.client import (
    DEFAULT_API_BASE_URL,
    USAGE_API_PATH,
    _normalize_base_url,
    get_api_base_url,
    get_usage_api_url,
    load_api_base_url,
    set_api_base_url,
)


class TestApiBaseUrl(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "api_config.json"
        # Config-Pfad auf temporaeres Verzeichnis umbiegen, damit keine echte Nutzer-Config betroffen ist
        self._patcher = patch.object(client, "get_api_config_path", return_value=self.config_path)
        self._patcher.start()
        # Modul-State vor jedem Test auf Default zuruecksetzen
        client._api_base_url = DEFAULT_API_BASE_URL

    def tearDown(self):
        self._patcher.stop()
        self.temp_dir.cleanup()

    def test_normalize_valid_urls(self):
        self.assertEqual(_normalize_base_url("https://example.com"), "https://example.com")
        self.assertEqual(_normalize_base_url("http://localhost:8080"), "http://localhost:8080")

    def test_normalize_strips_trailing_slash(self):
        self.assertEqual(_normalize_base_url("https://example.com/"), "https://example.com")
        self.assertEqual(_normalize_base_url("https://example.com/path/"), "https://example.com/path")

    def test_normalize_rejects_invalid(self):
        self.assertIsNone(_normalize_base_url(""))
        self.assertIsNone(_normalize_base_url("   "))
        self.assertIsNone(_normalize_base_url(None))
        self.assertIsNone(_normalize_base_url("ftp://example.com"))
        self.assertIsNone(_normalize_base_url("api.anthropic.com"))  # fehlendes Schema

    def test_set_and_get_base_url(self):
        set_api_base_url("https://proxy.internal:9000")
        self.assertEqual(get_api_base_url(), "https://proxy.internal:9000")

    def test_set_invalid_falls_back_to_default(self):
        set_api_base_url("not-a-url")
        self.assertEqual(get_api_base_url(), DEFAULT_API_BASE_URL)

    def test_set_empty_falls_back_to_default(self):
        set_api_base_url("")
        self.assertEqual(get_api_base_url(), DEFAULT_API_BASE_URL)

    def test_usage_url_composition_no_double_slash(self):
        set_api_base_url("https://proxy.internal/")
        self.assertEqual(get_usage_api_url(), "https://proxy.internal" + USAGE_API_PATH)

    def test_persistence_roundtrip(self):
        set_api_base_url("https://proxy.internal:9000")
        # State zuruecksetzen und aus Datei neu laden (simuliert Backend-Neustart)
        client._api_base_url = DEFAULT_API_BASE_URL
        loaded = load_api_base_url()
        self.assertEqual(loaded, "https://proxy.internal:9000")
        self.assertEqual(get_api_base_url(), "https://proxy.internal:9000")

    def test_load_missing_file_returns_default(self):
        self.assertFalse(self.config_path.exists())
        self.assertEqual(load_api_base_url(), DEFAULT_API_BASE_URL)

    def test_load_corrupt_file_returns_default(self):
        self.config_path.write_text("{ not valid json", encoding="utf-8")
        self.assertEqual(load_api_base_url(), DEFAULT_API_BASE_URL)


if __name__ == "__main__":
    unittest.main()
