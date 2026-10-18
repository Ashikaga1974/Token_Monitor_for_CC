"""Tests for native KDE notifications and debouncing in backend/notifier.py."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.notifier import (
    NotificationConfig,
    NotificationManager,
    send_desktop_notification,
)


class TestNotifier(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "test_config.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_config_save_load(self):
        cfg = NotificationConfig(
            enabled=True,
            notify_burn_rate=False,
            notify_threshold_1=True,
            threshold_1_percent=80,
            notify_threshold_2=True,
            threshold_2_percent=92,
        )
        cfg.save(self.config_path)

        loaded = NotificationConfig.load(self.config_path)
        self.assertTrue(loaded.enabled)
        self.assertFalse(loaded.notify_burn_rate)
        self.assertTrue(loaded.notify_threshold_1)
        self.assertEqual(loaded.threshold_1_percent, 80)
        self.assertTrue(loaded.notify_threshold_2)
        self.assertEqual(loaded.threshold_2_percent, 92)

    @patch("backend.notifier.send_desktop_notification")
    def test_threshold_1_triggers_once_per_window(self, mock_notify):
        mock_notify.return_value = True
        mgr = NotificationManager(NotificationConfig(threshold_1_percent=85, threshold_2_percent=95))

        stats = {
            "session": {
                "utilization": 87.0,
                "resets_at_iso": "2026-10-13T12:00:00+00:00",
                "resets_in_minutes": 90,
                "hits_100_before_reset": False,
            }
        }

        # First evaluation -> should trigger
        events = mgr.check_and_notify(stats)
        self.assertIn("session_threshold_1", events)
        self.assertEqual(mock_notify.call_count, 1)

        # Immediate second evaluation in same window -> should be debounced (no second alert)
        mock_notify.reset_mock()
        events2 = mgr.check_and_notify(stats)
        self.assertEqual(events2, [])
        self.assertEqual(mock_notify.call_count, 0)

        # New window resets_at -> should trigger again
        stats_new_window = {
            "session": {
                "utilization": 86.0,
                "resets_at_iso": "2026-10-13T17:00:00+00:00",
                "resets_in_minutes": 180,
                "hits_100_before_reset": False,
            }
        }
        events3 = mgr.check_and_notify(stats_new_window)
        self.assertIn("session_threshold_1", events3)
        self.assertEqual(mock_notify.call_count, 1)

    @patch("backend.notifier.send_desktop_notification")
    def test_threshold_2_triggers(self, mock_notify):
        mock_notify.return_value = True
        mgr = NotificationManager(NotificationConfig(threshold_1_percent=85, threshold_2_percent=95))

        stats = {
            "session": {
                "utilization": 96.0,
                "resets_at_iso": "2026-10-13T12:00:00+00:00",
                "resets_in_minutes": 45,
                "hits_100_before_reset": False,
            }
        }

        events = mgr.check_and_notify(stats)
        self.assertIn("session_threshold_2", events)
        self.assertNotIn("session_threshold_1", events)  # T1 suppressed when T2 fires
        self.assertEqual(mock_notify.call_count, 1)

    @patch("backend.notifier.send_desktop_notification")
    def test_burn_rate_exhaustion_alert(self, mock_notify):
        mock_notify.return_value = True
        mgr = NotificationManager(NotificationConfig())

        stats = {
            "session": {
                "utilization": 70.0,
                "resets_at_iso": "2026-10-13T12:00:00+00:00",
                "resets_in_minutes": 60,
                "hits_100_before_reset": True,
                "burn_rate_pct_per_hour": 35.0,
            }
        }

        events = mgr.check_and_notify(stats)
        self.assertIn("session_burn_rate", events)
        self.assertEqual(mock_notify.call_count, 1)

        # Within 45min debounce -> no repeat
        mock_notify.reset_mock()
        events2 = mgr.check_and_notify(stats)
        self.assertEqual(events2, [])
        self.assertEqual(mock_notify.call_count, 0)

    @patch("backend.notifier.send_desktop_notification")
    def test_disabled_config_suppresses_alerts(self, mock_notify):
        mgr = NotificationManager(NotificationConfig(enabled=False))
        stats = {
            "session": {
                "utilization": 99.0,
                "resets_at_iso": "2026-10-13T12:00:00+00:00",
                "hits_100_before_reset": True,
            }
        }
        events = mgr.check_and_notify(stats)
        self.assertEqual(events, [])
        self.assertEqual(mock_notify.call_count, 0)
