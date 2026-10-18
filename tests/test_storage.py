"""Unit tests for SQLite storage and data retention in backend/storage.py."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest

from backend.storage import StorageDB


class TestStorageRetention(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_history.db"
        self.db = StorageDB(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cleanup_old_snapshots_removes_expired_records(self):
        now = datetime.now(timezone.utc)
        # 1. Alter Snapshot (vor 70 Tagen) direkt per SQL einfügen
        old_ts = now - timedelta(days=70)
        new_ts = now - timedelta(days=10)
        with self.db._get_connection() as conn:
            conn.execute(
                "INSERT INTO usage_snapshots (timestamp, five_hour_utilization, seven_day_all_utilization) VALUES (?, ?, ?)",
                (old_ts.isoformat(), 0.1, 0.05),
            )
            conn.execute(
                "INSERT INTO usage_snapshots (timestamp, five_hour_utilization, seven_day_all_utilization) VALUES (?, ?, ?)",
                (new_ts.isoformat(), 0.5, 0.20),
            )
            conn.commit()

        # Vor Bereinigung: 2 Einträge
        snapshots_all = self.db.get_snapshots_since(now - timedelta(days=90))
        self.assertEqual(len(snapshots_all), 2)

        # Expliziter Cleanup auf 60 Tage
        deleted = self.db.cleanup_old_snapshots(retention_days=60)
        self.assertEqual(deleted, 1)

        # Nach Bereinigung: Nur der 10 Tage alte Snapshot existiert noch
        remaining = self.db.get_snapshots_since(now - timedelta(days=90))
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].seven_day_all_utilization, 0.20)

    def test_insert_snapshot_automatically_triggers_cleanup(self):
        now = datetime.now(timezone.utc)
        # Alter Snapshot (vor 65 Tagen)
        old_ts = now - timedelta(days=65)
        with self.db._get_connection() as conn:
            conn.execute(
                "INSERT INTO usage_snapshots (timestamp, five_hour_utilization) VALUES (?, ?)",
                (old_ts.isoformat(), 0.1),
            )
            conn.commit()

        # Jetzt neuer Snapshot via insert_snapshot
        self.db.insert_snapshot(
            five_hour_util=0.8,
            five_hour_resets=None,
            seven_day_util=0.3,
            seven_day_resets=None,
            timestamp=now,
        )

        # Der 65 Tage alte Snapshot wurde beim Insert automatisch aufgeräumt
        recs = self.db.get_snapshots_since(now - timedelta(days=90))
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].five_hour_utilization, 0.8)


    def test_insert_and_retrieve_opus_snapshot(self):
        now = datetime.now(timezone.utc)
        resets_at = now + timedelta(days=6)
        self.db.insert_snapshot(
            five_hour_util=0.2,
            five_hour_resets=None,
            seven_day_util=0.4,
            seven_day_resets=None,
            sonnet_util=0.35,
            sonnet_resets=resets_at,
            opus_util=0.15,
            opus_resets=resets_at,
            timestamp=now,
        )

        recs = self.db.get_snapshots_since(now - timedelta(hours=1))
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].seven_day_opus_utilization, 0.15)
        self.assertIsNotNone(recs[0].seven_day_opus_resets_at)

        latest = self.db.get_latest_snapshot()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.seven_day_opus_utilization, 0.15)


    def test_legacy_db_migration(self):
        from unittest.mock import patch
        legacy_dir = Path(self.temp_dir.name) / ".local" / "share" / "kde-claude-stat"
        legacy_dir.mkdir(parents=True)
        legacy_db = legacy_dir / "history.db"

        # Create dummy legacy db with 1 snapshot
        legacy_storage = StorageDB(db_path=legacy_db)
        legacy_storage.insert_snapshot(five_hour_util=0.77, five_hour_resets=None, seven_day_util=0.33, seven_day_resets=None)

        with patch("pathlib.Path.home", return_value=Path(self.temp_dir.name)):
            from backend.storage import get_default_db_path
            migrated_path = get_default_db_path()
            self.assertTrue(migrated_path.exists())
            self.assertEqual(migrated_path.parent.name, "token-monitor")
            # Verify data exists in migrated db
            new_storage = StorageDB(db_path=migrated_path)
            latest = new_storage.get_latest_snapshot()
            self.assertIsNotNone(latest)
            self.assertEqual(latest.five_hour_utilization, 0.77)


if __name__ == "__main__":
    unittest.main()

