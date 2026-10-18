"""Tests for budget pace, linear regression, and snapshot storage."""

from datetime import datetime, timezone, timedelta
import unittest
from backend.storage import StorageDB
from backend.calculator import (
    calculate_budget_pace,
    calculate_burn_rate_linear_regression,
    calculate_burn_metrics,
)


class TestCalculator(unittest.TestCase):
    def test_budget_pace_halfway(self):
        now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        # Reset in 2.5 hours within a 5-hour window -> 50% pace
        resets_at = now + timedelta(hours=2.5)
        pace = calculate_budget_pace(resets_at, window_hours=5.0, now=now)
        self.assertAlmostEqual(pace, 0.5, places=2)

    def test_burn_rate_linear_regression(self):
        # 3 data points: at 0h: 10%, at 1h: 20%, at 2h: 30% -> 10%/h
        points = [(0.0, 10.0), (1.0, 20.0), (2.0, 30.0)]
        slope = calculate_burn_rate_linear_regression(
            points, window_hours=5.0, min_points=3, min_span_pct=0.1
        )
        self.assertAlmostEqual(slope, 10.0, places=2)

    def test_burn_rate_linear_regression_lookback(self):
        # Flache Phase zu Beginn (0.0h bis 1.0h bei 1%), danach steiler Sprint (1.0h bis 1.5h von 1% auf 21% -> 40%/h)
        points = [
            (0.0, 1.0),
            (0.3, 1.0),
            (0.6, 1.0),
            (1.0, 1.0),
            (1.2, 9.0),
            (1.4, 17.0),
            (1.5, 21.0),
        ]
        # Ohne Lookback (über gesamte 1.5h): Durchschnitt wird durch flache Phase gedrückt
        overall_slope = calculate_burn_rate_linear_regression(
            points, window_hours=5.0, min_points=3, min_span_pct=0.1
        )
        self.assertLess(overall_slope, 20.0)

        # Mit Lookback (letzte 30 Min = 0.5h, also ab 1.0h): erfasst den aktuellen Sprint dynamisch
        recent_slope = calculate_burn_rate_linear_regression(
            points, window_hours=5.0, min_points=3, min_span_pct=0.1, max_lookback_hours=0.5
        )
        self.assertGreater(recent_slope, 35.0)

    def test_burn_metrics_exhaustion(self):
        now = datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc)
        resets_at = now + timedelta(hours=3)  # Reset in 180 min
        # Use StorageDB record structure
        from backend.storage import SnapshotRecord

        records = [
            SnapshotRecord(
                timestamp=now - timedelta(hours=2),
                five_hour_utilization=0.2,
                five_hour_resets_at=resets_at,
                seven_day_all_utilization=0.1,
                seven_day_all_resets_at=now + timedelta(days=5),
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
            SnapshotRecord(
                timestamp=now - timedelta(hours=1),
                five_hour_utilization=0.4,
                five_hour_resets_at=resets_at,
                seven_day_all_utilization=0.1,
                seven_day_all_resets_at=now + timedelta(days=5),
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
            SnapshotRecord(
                timestamp=now,
                five_hour_utilization=0.6,  # 60%
                five_hour_resets_at=resets_at,
                seven_day_all_utilization=0.1,
                seven_day_all_resets_at=now + timedelta(days=5),
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
        ]
        # Slope = 20%/h. Remaining = 40%. Time to 100% = 2h = 120 min.
        # Reset is in 180 min -> hits_100_before_reset must be True!
        metrics = calculate_burn_metrics(
            records=records,
            limit_type="session",
            resets_at=resets_at,
            window_hours=5.0,
            current_utilization=0.6,
            now=now,
        )
        self.assertEqual(metrics["utilization"], 60.0)
        self.assertAlmostEqual(metrics["burn_rate_pct_per_hour"], 20.0, places=1)
        self.assertEqual(metrics["estimated_minutes_to_100"], 120)
        self.assertTrue(metrics["hits_100_before_reset"])

    def test_burn_metrics_inactive(self):
        now = datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc)
        resets_at = now + timedelta(hours=3)
        from backend.storage import SnapshotRecord

        records = [
            SnapshotRecord(
                timestamp=now - timedelta(hours=1),
                five_hour_utilization=0.4,
                five_hour_resets_at=resets_at,
                seven_day_all_utilization=0.1,
                seven_day_all_resets_at=now + timedelta(days=5),
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
            SnapshotRecord(
                timestamp=now,
                five_hour_utilization=0.6,
                five_hour_resets_at=resets_at,
                seven_day_all_utilization=0.1,
                seven_day_all_resets_at=now + timedelta(days=5),
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
        ]
        # Inactive session: burn rate must be 0.0, trend 'idle', no premature exhaustion hit
        metrics = calculate_burn_metrics(
            records=records,
            limit_type="session",
            resets_at=resets_at,
            window_hours=5.0,
            current_utilization=0.6,
            now=now,
            is_active=False,
        )
        self.assertEqual(metrics["burn_rate_pct_per_hour"], 0.0)
        self.assertEqual(metrics["trend"], "idle")
        self.assertIsNone(metrics["estimated_minutes_to_100"])
        self.assertFalse(metrics["hits_100_before_reset"])
        self.assertFalse(metrics["is_active"])

    def test_burn_metrics_reset_drop(self):
        # Stellt sicher, dass alte Snapshots vor einem Session-Reset (z.B. 100% Drop auf 2%)
        # den neuen Trend nicht negativ verzerren.
        now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
        resets_at = now + timedelta(hours=1)
        from backend.storage import SnapshotRecord

        records = [
            SnapshotRecord(
                timestamp=now - timedelta(hours=4),
                five_hour_utilization=1.0,  # 100% vor dem Reset
                five_hour_resets_at=resets_at,
                seven_day_all_utilization=0.2,
                seven_day_all_resets_at=now + timedelta(days=5),
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
            SnapshotRecord(
                timestamp=now - timedelta(hours=3, minutes=55),
                five_hour_utilization=0.02,  # 2% direkt nach dem Reset
                five_hour_resets_at=resets_at,
                seven_day_all_utilization=0.2,
                seven_day_all_resets_at=now + timedelta(days=5),
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
            SnapshotRecord(
                timestamp=now - timedelta(hours=1),
                five_hour_utilization=0.10,  # 10%
                five_hour_resets_at=resets_at,
                seven_day_all_utilization=0.2,
                seven_day_all_resets_at=now + timedelta(days=5),
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
            SnapshotRecord(
                timestamp=now,
                five_hour_utilization=0.20,  # 20%
                five_hour_resets_at=resets_at,
                seven_day_all_utilization=0.2,
                seven_day_all_resets_at=now + timedelta(days=5),
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
        ]
        metrics = calculate_burn_metrics(
            records=records,
            limit_type="session",
            resets_at=resets_at,
            window_hours=5.0,
            current_utilization=0.20,
            now=now,
            is_active=True,
        )
        # Trotz des anfänglichen 100%-Werts muss die Burn-Rate positiv sein
        self.assertGreater(metrics["burn_rate_pct_per_hour"], 0.0)
        self.assertNotEqual(metrics["trend"], "idle")
        # Der Startpunkt im Chart darf nicht mehr 100% anzeigen
        self.assertLess(metrics["chart"]["usage"][0]["y"], 50.0)

    def test_weekly_jitter_keeps_full_usage_line(self):
        # Regression: Kleine API-Schwankungen (±wenige %) im Weekly-Chart dürfen
        # NICHT als Reset gewertet werden und die Verbrauchslinie auf wenige
        # Punkte zusammenschrumpfen lassen.
        now = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
        resets_at = now + timedelta(days=3)  # 7-Tage-Fenster, Reset in 3 Tagen
        from backend.storage import SnapshotRecord

        # Verlauf über ~3 Tage: steigt 13% -> 38% mit ±2% Jitter, inkl. 38->34 Drop
        pct_sequence = [13, 15, 17, 20, 22, 23, 22, 24, 25, 24, 26, 28, 30, 32, 34, 36, 38, 34, 36, 38]
        records = []
        total = len(pct_sequence)
        for i, pct in enumerate(pct_sequence):
            # Punkte gleichmäßig über die letzten ~70 Stunden verteilen
            ts = now - timedelta(hours=(total - 1 - i) * 3.5)
            records.append(
                SnapshotRecord(
                    timestamp=ts,
                    five_hour_utilization=None,
                    five_hour_resets_at=None,
                    seven_day_all_utilization=pct / 100.0,
                    seven_day_all_resets_at=resets_at,
                    seven_day_sonnet_utilization=None,
                    seven_day_sonnet_resets_at=None,
                )
            )

        metrics = calculate_burn_metrics(
            records=records,
            limit_type="weekly",
            resets_at=resets_at,
            window_hours=168.0,
            current_utilization=0.38,
            now=now,
        )
        usage = metrics["chart"]["usage"]
        # Linie muss viele Punkte behalten (nicht auf den letzten Blip getrimmt)
        self.assertGreaterEqual(len(usage), 15)
        # Und sich über einen breiten x-Bereich erstrecken (nicht bei x~now geclustert)
        self.assertLess(usage[0]["x"], 0.5)

    def test_process_detection(self):
        from backend.process import is_claude_process_running
        # Function call should return boolean without exception
        running = is_claude_process_running()
        self.assertIsInstance(running, bool)

    def test_rate_limit_backoff(self):
        import time
        from backend.client import is_rate_limited, get_rate_limit_remaining_seconds, reset_rate_limit
        import backend.client as client_mod

        # Default state: not rate-limited
        reset_rate_limit()
        self.assertFalse(is_rate_limited())
        self.assertEqual(get_rate_limit_remaining_seconds(), 0.0)

        # Simulate active backoff
        client_mod._rate_limited_until = time.time() + 60.0
        self.assertTrue(is_rate_limited())
        self.assertGreater(get_rate_limit_remaining_seconds(), 0.0)

        # Reset
        client_mod._rate_limited_until = 0.0

    def test_hook_install_and_remove(self):
        import tempfile
        import json
        from pathlib import Path
        from unittest.mock import patch
        from backend.hook import install_statusline_hook, remove_statusline_hook, is_hook_installed

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps({"statusLine": {"type": "command", "command": "~/.claude/statusline.sh"}})
            )
            with patch("backend.hook.get_claude_settings_path", return_value=settings_path):
                self.assertFalse(is_hook_installed())
                ok, _ = install_statusline_hook()
                self.assertTrue(ok)
                self.assertTrue(is_hook_installed())

                # Verify command was prepended
                data = json.loads(settings_path.read_text())
                self.assertEqual(
                    data["statusLine"]["command"],
                    "$HOME/.local/bin/token-monitor-collect --passthrough | ~/.claude/statusline.sh",
                )

                # Verify idempotency
                ok, _ = install_statusline_hook()
                self.assertTrue(ok)
                data = json.loads(settings_path.read_text())
                self.assertEqual(
                    data["statusLine"]["command"],
                    "$HOME/.local/bin/token-monitor-collect --passthrough | ~/.claude/statusline.sh",
                )

                # Verify removal
                ok, _ = remove_statusline_hook()
                self.assertTrue(ok)
                self.assertFalse(is_hook_installed())
                data = json.loads(settings_path.read_text())
                self.assertEqual(data["statusLine"]["command"], "~/.claude/statusline.sh")


    def test_lookback_charts(self):
        from backend.calculator import calculate_lookback_chart
        from backend.storage import SnapshotRecord

        now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        resets_at = now + timedelta(days=5)
        records = [
            SnapshotRecord(
                timestamp=now - timedelta(hours=8),
                five_hour_utilization=None,
                five_hour_resets_at=None,
                seven_day_all_utilization=0.15,
                seven_day_all_resets_at=resets_at,
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
            SnapshotRecord(
                timestamp=now - timedelta(hours=3),
                five_hour_utilization=None,
                five_hour_resets_at=None,
                seven_day_all_utilization=0.20,
                seven_day_all_resets_at=resets_at,
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
        ]
        chart_7h = calculate_lookback_chart(records, "weekly", now, 7.0, 25.0)
        self.assertEqual(chart_7h["label_start"], "-7h")
        self.assertEqual(chart_7h["label_end"], "Now")
        self.assertEqual(chart_7h["elapsed_ratio"], 1.0)
        self.assertTrue(len(chart_7h["usage"]) >= 2)
        # End of chart should anchor at current utilization 25.0
        self.assertEqual(chart_7h["usage"][-1]["y"], 25.0)

        # Full calculate_burn_metrics should expose "charts" with "7h", "24h", "7d"
        metrics = calculate_burn_metrics(
            records=records,
            limit_type="weekly",
            resets_at=resets_at,
            window_hours=168.0,
            current_utilization=0.25,
            now=now,
        )
        self.assertIn("charts", metrics)
        self.assertIn("7h", metrics["charts"])
        self.assertIn("24h", metrics["charts"])
        self.assertIn("7d", metrics["charts"])

    def test_lookback_chart_30d_daily_buckets(self):
        # 30-Tage-Lookback: Tagesraster-Buckets und Tages-Label "30d", Sägezahn über Resets sichtbar
        from backend.calculator import calculate_lookback_chart
        from backend.storage import SnapshotRecord

        now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        records = []
        # Zwei Weekly-Zyklen: hochlaufen bis ~60%, Reset auf 5%, erneut hochlaufen
        for day, util in [(25, 0.20), (22, 0.45), (19, 0.60), (16, 0.05), (10, 0.30), (4, 0.55)]:
            records.append(
                SnapshotRecord(
                    timestamp=now - timedelta(days=day),
                    five_hour_utilization=None,
                    five_hour_resets_at=None,
                    seven_day_all_utilization=util,
                    seven_day_all_resets_at=now + timedelta(days=2),
                    seven_day_sonnet_utilization=None,
                    seven_day_sonnet_resets_at=None,
                )
            )

        chart_30d = calculate_lookback_chart(records, "weekly", now, 720.0, 55.0)
        self.assertEqual(chart_30d["label_start"], "-30d")
        self.assertEqual(chart_30d["label_end"], "Now")
        # Tagesraster: jeder Datenpunkt liegt in einem eigenen Tages-Bucket (6 Werte + Endanker)
        self.assertTrue(len(chart_30d["usage"]) >= 6)
        # Endanker hält die aktuelle Auslastung
        self.assertEqual(chart_30d["usage"][-1]["y"], 55.0)

    def test_lookback_chart_reset_step_down_to_zero(self):
        # 24h-Lookback über einen Reset: Sägezahn-Abfall auf 0% am Reset-Zeitpunkt
        # und flache 0%-Linie während inaktiver Nacht statt Diagonale
        from backend.calculator import calculate_lookback_chart
        from backend.storage import SnapshotRecord

        now = datetime(2026, 10, 17, 14, 0, tzinfo=timezone.utc)
        reset_time = now - timedelta(hours=22)
        next_week_reset = reset_time + timedelta(days=7)

        records = [
            # Gestern vor dem Reset: hohe Auslastung (89%)
            SnapshotRecord(
                timestamp=now - timedelta(hours=23),
                five_hour_utilization=None,
                five_hour_resets_at=None,
                seven_day_all_utilization=0.88,
                seven_day_all_resets_at=reset_time,
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
            SnapshotRecord(
                timestamp=now - timedelta(hours=22, minutes=10),
                five_hour_utilization=None,
                five_hour_resets_at=None,
                seven_day_all_utilization=0.89,
                seven_day_all_resets_at=reset_time,
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
            # Nachts war der Rechner aus (keine Snapshots)
            # Heute früh nach dem Aufwachen: 0% bzw. leichter Anstieg
            SnapshotRecord(
                timestamp=now - timedelta(hours=6),
                five_hour_utilization=None,
                five_hour_resets_at=None,
                seven_day_all_utilization=0.0,
                seven_day_all_resets_at=next_week_reset,
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
            SnapshotRecord(
                timestamp=now - timedelta(hours=4),
                five_hour_utilization=None,
                five_hour_resets_at=None,
                seven_day_all_utilization=0.05,
                seven_day_all_resets_at=next_week_reset,
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
        ]

        chart_24h = calculate_lookback_chart(records, "weekly", now, 24.0, 14.0)
        usage = chart_24h["usage"]

        # Prüfen, dass ein Stützpunkt mit 0.0% am Reset-Zeitpunkt existiert
        zero_points = [p for p in usage if p["y"] == 0.0]
        self.assertTrue(len(zero_points) >= 2, "Erwartet mindestens 2 Nullpunkte: am Reset und vor Aufwachen")

        # Prüfen, dass vor dem Reset der hohe Wert gehalten wird
        high_points = [p for p in usage if p["y"] >= 88.0]
        self.assertTrue(len(high_points) >= 1)

        # Prüfen, dass der Reset-Stützpunkt vor dem Aufwach-Stützpunkt liegt
        reset_norm_x = (reset_time.timestamp() - (now.timestamp() - 24 * 3600.0)) / (24 * 3600.0)
        match_reset = [p for p in usage if abs(p["x"] - reset_norm_x) < 0.01 and p["y"] == 0.0]
        self.assertTrue(len(match_reset) >= 1, "Exakter 0.0%-Punkt am Reset-Zeitpunkt erforderlich")

        # 7h-Lookback (startet nach dem Reset): Darf nicht mit 89% starten, sondern mit 0%
        chart_7h = calculate_lookback_chart(records, "weekly", now, 7.0, 14.0)
        self.assertEqual(chart_7h["usage"][0]["y"], 0.0, "7h-Chart nach Reset muss bei 0.0% starten")

    def test_weekly_burn_rate_anchors_cycle_start_and_smooths_lookback(self):
        """Verifiziert, dass bei Weekly der Zyklusstart verankert wird und die Burn-Rate nicht durch 24h-Peaks verfälscht wird."""
        now = datetime(2026, 10, 17, 16, 0, tzinfo=timezone.utc)
        # 7-Tage-Fenster, Reset in 6 Tagen -> Zyklusstart war vor 24h
        resets_at = now + timedelta(days=6)
        from backend.storage import SnapshotRecord

        # Nach Reset vor 24h gab es erst ab vor 8h Snapshots (0% bis 24%)
        records = [
            SnapshotRecord(
                timestamp=now - timedelta(hours=8),
                five_hour_utilization=0.1,
                five_hour_resets_at=None,
                seven_day_all_utilization=0.0,
                seven_day_all_resets_at=resets_at,
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
            SnapshotRecord(
                timestamp=now - timedelta(hours=4),
                five_hour_utilization=0.4,
                five_hour_resets_at=None,
                seven_day_all_utilization=0.12,
                seven_day_all_resets_at=resets_at,
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
            SnapshotRecord(
                timestamp=now,
                five_hour_utilization=0.8,
                five_hour_resets_at=None,
                seven_day_all_utilization=0.24,
                seven_day_all_resets_at=resets_at,
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
            ),
        ]

        metrics = calculate_burn_metrics(
            records=records,
            limit_type="weekly",
            resets_at=resets_at,
            window_hours=168.0,
            current_utilization=0.24,
            now=now,
            is_active=True,
        )

        # 1. Chart muss am Zyklusstart bei (0.0, 0.0) verankert sein
        usage = metrics["chart"]["usage"]
        self.assertEqual(usage[0]["x"], 0.0)
        self.assertEqual(usage[0]["y"], 0.0)

        # 2. Burn-Rate darf nicht auf den 8h-Sprint (~3%/h) hochschnellen,
        # sondern muss die gesamte verstrichene Zykluszeit (~24h) berücksichtigen (< 1.5%/h)
        self.assertLess(metrics["burn_rate_pct_per_hour"], 1.5)
        # 3. ETA muss deutlich über 2 Tagen liegen (nicht < 30 Stunden)
        self.assertGreater(metrics["estimated_minutes_to_100"], 2880)  # > 48 Stunden

    def test_weekly_opus_burn_metrics(self):
        now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        resets_at = now + timedelta(days=5)
        from backend.storage import SnapshotRecord

        records = [
            SnapshotRecord(
                timestamp=now - timedelta(hours=24),
                five_hour_utilization=None,
                five_hour_resets_at=None,
                seven_day_all_utilization=0.10,
                seven_day_all_resets_at=resets_at,
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
                seven_day_opus_utilization=0.05,
                seven_day_opus_resets_at=resets_at,
            ),
            SnapshotRecord(
                timestamp=now,
                five_hour_utilization=None,
                five_hour_resets_at=None,
                seven_day_all_utilization=0.20,
                seven_day_all_resets_at=resets_at,
                seven_day_sonnet_utilization=None,
                seven_day_sonnet_resets_at=None,
                seven_day_opus_utilization=0.15,
                seven_day_opus_resets_at=resets_at,
            ),
        ]

        metrics = calculate_burn_metrics(
            records=records,
            limit_type="weekly_opus",
            resets_at=resets_at,
            window_hours=168.0,
            current_utilization=0.15,
            now=now,
            is_active=True,
        )

        self.assertIsNotNone(metrics)
        self.assertEqual(metrics["utilization"], 15.0)
        self.assertIn("charts", metrics)
        self.assertIn("24h", metrics["charts"])


if __name__ == "__main__":
    unittest.main()



