"""Tests for CLI collection and hook installation."""

import io
import json
import sys
import unittest
from unittest.mock import patch

from backend.cli import collect_from_stdin, format_model_display_name, get_current_model
from backend.storage import StorageDB, SnapshotRecord
from datetime import datetime, timezone
from pathlib import Path
import tempfile


class TestCliHook(unittest.TestCase):
    def setUp(self):
        self.storage_patcher = patch("backend.cli.StorageDB")
        self.mock_storage = self.storage_patcher.start()

    def tearDown(self):
        self.storage_patcher.stop()

    def test_collect_from_stdin_passthrough(self):
        sample_json = json.dumps({
            "workspace": {"current_dir": "/tmp"},
            "rate_limits": {
                "five_hour": {"used_percentage": 25.0, "resets_at": 1792159200}
            }
        })
        
        # Test that stdin is passed through to stdout when passthrough=True
        with patch("sys.stdin", io.StringIO(sample_json)), patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            res = collect_from_stdin(passthrough=True)
            self.assertEqual(res, {"status": "collected"})
            self.assertEqual(mock_stdout.getvalue(), sample_json)

    def test_collect_from_stdin_standalone_silent(self):
        sample_json = json.dumps({
            "workspace": {"current_dir": "/tmp"},
            "rate_limits": {
                "five_hour": {"used_percentage": 25.0, "resets_at": 1792159200}
            }
        })
        
        # Without passthrough (standalone mode), stdout stays completely silent (no raw JSON in terminal)
        with patch("sys.stdin", io.StringIO(sample_json)), patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            res = collect_from_stdin(passthrough=False)
            self.assertEqual(res, {"status": "collected"})
            self.assertEqual(mock_stdout.getvalue(), "")

    def test_collect_from_stdin_empty(self):
        with patch("sys.stdin", io.StringIO("")), patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            res = collect_from_stdin(passthrough=True)
            self.assertEqual(res, {})
            self.assertEqual(mock_stdout.getvalue(), "")

    def test_format_model_display_name(self):
        self.assertEqual(format_model_display_name("claude-sonnet-5-5"), "Sonnet 5.5")
        self.assertEqual(format_model_display_name("claude-opus-4-8"), "Opus 4.8")
        self.assertEqual(format_model_display_name("claude-3-7-sonnet-20250219"), "Sonnet 3.7")
        self.assertEqual(format_model_display_name("claude-opus-4-7"), "Opus 4.7")
        self.assertEqual(format_model_display_name("claude-custom-model"), "Custom Model")
        self.assertEqual(format_model_display_name(""), "")

    def test_get_current_model_from_records(self):
        now = datetime.now(timezone.utc)
        records = [
            SnapshotRecord(
                timestamp=now,
                five_hour_utilization=0.1,
                five_hour_resets_at=None,
                seven_day_all_utilization=0.2,
                seven_day_all_resets_at=None,
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
                raw_response=json.dumps({
                    "model": {"id": "claude-sonnet-5-5", "display_name": "Sonnet 5.5"}
                }),
            )
        ]
        # In Abwesenheit von settings.json (oder wenn Snapshot ganz frisch ist)
        model = get_current_model(records, settings_path=Path("/nonexistent/settings.json"), now=now)
        self.assertIsNotNone(model)
        self.assertEqual(model["id"], "claude-sonnet-5-5")
        self.assertEqual(model["display_name"], "Sonnet 5.5")

    def test_get_current_model_stale_record_falls_back_to_settings(self):
        now = datetime.now(timezone.utc)
        stale_time = datetime.fromtimestamp(now.timestamp() - 7200, tz=timezone.utc)  # 2 Stunden alt
        records = [
            SnapshotRecord(
                timestamp=stale_time,
                five_hour_utilization=0.1,
                five_hour_resets_at=None,
                seven_day_all_utilization=0.2,
                seven_day_all_resets_at=None,
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
                raw_response=json.dumps({
                    "model": {"id": "claude-sonnet-5-5", "display_name": "Sonnet 5.5"}
                }),
            )
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_file.write_text(json.dumps({"model": "claude-opus-4-8"}), encoding="utf-8")
            model = get_current_model(records, settings_path=settings_file, now=now)
            self.assertIsNotNone(model)
            self.assertEqual(model["id"], "claude-opus-4-8")
            self.assertEqual(model["display_name"], "Opus 4.8")

    def test_collect_from_stdin_low_utilization(self):
        # 1.0 % Nutzung muss als 0.01 (1 %) in die DB geschrieben werden, nicht als 1.0 (100 %)
        sample_json = json.dumps({
            "rate_limits": {
                "five_hour": {"utilization": 1.0, "resets_at": "2026-10-13T19:49:59+00:00"}
            }
        })
        with patch("sys.stdin", io.StringIO(sample_json)):
            res = collect_from_stdin(passthrough=False)
            self.assertEqual(res, {"status": "collected"})
            self.mock_storage().insert_snapshot.assert_called_once()
            call_kwargs = self.mock_storage().insert_snapshot.call_args.kwargs
            self.assertAlmostEqual(call_kwargs["five_hour_util"], 0.01)

    def test_repair_unnormalized_snapshots(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db = StorageDB(Path(tmpdir) / "test.db")
            # Manuell fehlerhaften 1.0-Snapshot einfügen
            raw = json.dumps({
                "five_hour": {"utilization": 1.0, "resets_at": "2026-10-13T19:49:59+00:00"},
                "limits": [{"kind": "session", "percent": 1}]
            })
            conn = test_db._get_connection()
            try:
                conn.execute(
                    "INSERT INTO usage_snapshots (timestamp, five_hour_utilization, raw_response) VALUES (?, ?, ?)",
                    (datetime.now(timezone.utc).isoformat(), 1.0, raw),
                )
                conn.commit()
            finally:
                conn.close()
            # Re-init oder explizite Reparatur aufrufen
            fixed_count = test_db.repair_unnormalized_snapshots()
            self.assertEqual(fixed_count, 1)

            latest = test_db.get_latest_snapshot()
            self.assertIsNotNone(latest)
            self.assertAlmostEqual(latest.five_hour_utilization, 0.01)


