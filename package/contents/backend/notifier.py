"""Native desktop notifications for Token Monitor for Claude Code via D-Bus."""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
import json
import logging
from pathlib import Path
import subprocess
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


import html
import os

def sanitize_notification_text(text: str, max_length: int = 500) -> str:
    """Escapes Pango/HTML markup characters and enforces a maximum text length."""
    if not text:
        return ""
    clean = text.strip()[:max_length]
    return html.escape(clean, quote=False)


def get_notification_config_path() -> Path:
    base_dir = Path.home() / ".local" / "share" / "token-monitor"
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        if (base_dir.stat().st_mode & 0o777) != 0o700:
            os.chmod(base_dir, 0o700)
    except OSError:
        pass

    target_cfg = base_dir / "notification_config.json"
    if not target_cfg.exists():
        legacy_cfg = Path.home() / ".local" / "share" / "kde-claude-stat" / "notification_config.json"
        if legacy_cfg.is_file():
            try:
                import shutil
                shutil.copy2(legacy_cfg, target_cfg)
            except Exception:
                pass

    return target_cfg



@dataclass
class NotificationConfig:
    enabled: bool = True
    notify_burn_rate: bool = True
    notify_threshold_1: bool = True
    threshold_1_percent: int = 85
    notify_threshold_2: bool = True
    threshold_2_percent: int = 95

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "NotificationConfig":
        cfg_path = path or get_notification_config_path()
        if cfg_path.is_file():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                return cls(
                    enabled=bool(data.get("enabled", True)),
                    notify_burn_rate=bool(data.get("notify_burn_rate", True)),
                    notify_threshold_1=bool(data.get("notify_threshold_1", True)),
                    threshold_1_percent=int(data.get("threshold_1_percent", 85)),
                    notify_threshold_2=bool(data.get("notify_threshold_2", True)),
                    threshold_2_percent=int(data.get("threshold_2_percent", 95)),
                )
            except Exception as e:
                logger.warning(f"Failed to load notification config from {cfg_path}: {e}")
        return cls()

    def save(self, path: Optional[Path] = None) -> None:
        cfg_path = path or get_notification_config_path()
        try:
            cfg_path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
            if cfg_path.is_file() and (cfg_path.stat().st_mode & 0o777) != 0o600:
                os.chmod(cfg_path, 0o600)
        except Exception as e:
            logger.error(f"Failed to save notification config to {cfg_path}: {e}")


def send_desktop_notification(
    summary: str,
    body: str,
    urgency: int = 1,
    timeout_ms: int = 5000,
    app_icon: str = "utilities-system-monitor",
) -> bool:
    """
    Sends a native desktop notification via D-Bus (org.freedesktop.Notifications).
    Falls back gracefully to notify-send if D-Bus module fails.
    """
    safe_summary = sanitize_notification_text(summary, max_length=120)
    safe_body = sanitize_notification_text(body, max_length=500)

    # 1. Direct D-Bus call
    try:
        import dbus

        bus = dbus.SessionBus()
        notify_obj = bus.get_object("org.freedesktop.Notifications", "/org/freedesktop/Notifications")
        notify_iface = dbus.Interface(notify_obj, "org.freedesktop.Notifications")
        hints = {"urgency": dbus.Byte(urgency)}
        notify_iface.Notify(
            "Token Monitor for Claude Code",
            0,
            app_icon,
            safe_summary,
            safe_body,
            [],
            hints,
            timeout_ms,
        )
        return True
    except Exception as e:
        logger.debug(f"Direct D-Bus notify failed ({e}), attempting notify-send fallback...")

    # 2. Fallback to notify-send CLI binary
    try:
        urgency_str = "critical" if urgency >= 2 else ("low" if urgency == 0 else "normal")
        cmd = [
            "notify-send",
            "-a", "Token Monitor for Claude Code",
            "-i", app_icon,
            "-u", urgency_str,
            "-t", str(timeout_ms),
            safe_summary,
            safe_body,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        return res.returncode == 0
    except Exception as e:
        logger.warning(f"notify-send fallback failed: {e}")
        return False


class NotificationManager:
    """Manages notifications with debouncing and reset-aware hysteresis."""

    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or NotificationConfig.load()
        # State tracking for debouncing
        self.last_session_burn_alert: Optional[datetime] = None
        self.last_weekly_burn_alert: Optional[datetime] = None
        self.alerted_session_t1_reset: Optional[str] = None
        self.alerted_session_t2_reset: Optional[str] = None
        self.alerted_weekly_t1_reset: Optional[str] = None
        self.alerted_weekly_t2_reset: Optional[str] = None

    def update_config(self, new_config: NotificationConfig) -> None:
        self.config = new_config
        self.config.save()

    def check_and_notify(self, stats: Dict[str, Any]) -> List[str]:
        """
        Evaluates current metrics and sends desktop notifications if thresholds are reached.
        Returns list of triggered notification identifiers.
        """
        if not self.config.enabled:
            return []

        now = datetime.now(timezone.utc)
        triggered: List[str] = []

        session = stats.get("session") or {}
        weekly = stats.get("weekly") or {}

        s_util = float(session.get("utilization") or 0.0)
        s_resets_iso = session.get("resets_at_iso")
        s_hits_100 = bool(session.get("hits_100_before_reset"))
        s_burn = float(session.get("burn_rate_pct_per_hour") or 0.0)
        s_resets_in = int(session.get("resets_in_minutes") or 0)

        w_util = float(weekly.get("utilization") or 0.0)
        w_resets_iso = weekly.get("resets_at_iso")
        w_hits_100 = bool(weekly.get("hits_100_before_reset"))
        w_resets_in = int(weekly.get("resets_in_minutes") or 0)

        def _fmt_min(minutes: int) -> str:
            if minutes <= 0:
                return "in Kürze"
            h = minutes // 60
            m = minutes % 60
            if h > 0:
                return f"{h}h {m}m"
            return f"{m}m"

        # 1. Critical Burn Rate warning (hits 100 before reset)
        if self.config.notify_burn_rate:
            if s_hits_100 and s_resets_iso:
                should_alert = False
                if self.last_session_burn_alert is None:
                    should_alert = True
                elif (now - self.last_session_burn_alert) > timedelta(minutes=45):
                    should_alert = True

                if should_alert:
                    self.last_session_burn_alert = now
                    send_desktop_notification(
                        summary="⚠️ Claude Code: Limit-Erschöpfung droht!",
                        body=f"Bei aktueller Burn-Rate ({s_burn:.1f} %/h) wird das 5h-Session-Limit vor dem Reset (in {_fmt_min(s_resets_in)}) erreicht!",
                        urgency=2,
                        timeout_ms=7000,
                    )
                    triggered.append("session_burn_rate")

            if w_hits_100 and w_resets_iso:
                should_alert_w = False
                if self.last_weekly_burn_alert is None:
                    should_alert_w = True
                elif (now - self.last_weekly_burn_alert) > timedelta(hours=3):
                    should_alert_w = True

                if should_alert_w:
                    self.last_weekly_burn_alert = now
                    send_desktop_notification(
                        summary="⚠️ Claude Code: Wochenlimit-Erschöpfung droht!",
                        body=f"Wochen-Limit wird bei aktuellem Tempo vor dem Reset (in {_fmt_min(w_resets_in)}) erreicht!",
                        urgency=2,
                        timeout_ms=7000,
                    )
                    triggered.append("weekly_burn_rate")

        # 2. Threshold 2 (Critical, e.g. 95%)
        if self.config.notify_threshold_2:
            t2 = float(self.config.threshold_2_percent)
            if s_util >= t2 and s_resets_iso:
                if self.alerted_session_t2_reset != s_resets_iso:
                    self.alerted_session_t2_reset = s_resets_iso
                    send_desktop_notification(
                        summary=f"🚨 Claude Code: Kritisches Limit ({s_util:.0f} %)",
                        body=f"5-Stunden-Session ist zu {s_util:.0f} % ausgelastet. Reset erfolgt in {_fmt_min(s_resets_in)}.",
                        urgency=2,
                        timeout_ms=8000,
                    )
                    triggered.append("session_threshold_2")

            if w_util >= t2 and w_resets_iso:
                if self.alerted_weekly_t2_reset != w_resets_iso:
                    self.alerted_weekly_t2_reset = w_resets_iso
                    send_desktop_notification(
                        summary=f"🚨 Claude Code: Kritisches Wochen-Limit ({w_util:.0f} %)",
                        body=f"Wochen-Limit ist zu {w_util:.0f} % ausgelastet. Reset erfolgt in {_fmt_min(w_resets_in)}.",
                        urgency=2,
                        timeout_ms=8000,
                    )
                    triggered.append("weekly_threshold_2")

        # 3. Threshold 1 (Warning, e.g. 85%)
        if self.config.notify_threshold_1:
            t1 = float(self.config.threshold_1_percent)
            t2 = float(self.config.threshold_2_percent)
            if s_util >= t1 and s_util < t2 and s_resets_iso:
                if self.alerted_session_t1_reset != s_resets_iso:
                    self.alerted_session_t1_reset = s_resets_iso
                    send_desktop_notification(
                        summary=f"⚠️ Claude Code: Warnstufe erreicht ({s_util:.0f} %)",
                        body=f"5-Stunden-Session ist zu {s_util:.0f} % ausgelastet. Reset erfolgt in {_fmt_min(s_resets_in)}.",
                        urgency=1,
                        timeout_ms=5000,
                    )
                    triggered.append("session_threshold_1")

            if w_util >= t1 and w_util < t2 and w_resets_iso:
                if self.alerted_weekly_t1_reset != w_resets_iso:
                    self.alerted_weekly_t1_reset = w_resets_iso
                    send_desktop_notification(
                        summary=f"⚠️ Claude Code: Wochen-Warnstufe ({w_util:.0f} %)",
                        body=f"Wochen-Limit ist zu {w_util:.0f} % ausgelastet. Reset erfolgt in {_fmt_min(w_resets_in)}.",
                        urgency=1,
                        timeout_ms=5000,
                    )
                    triggered.append("weekly_threshold_1")

        # Clear alert flags when reset window advances or resets
        if s_resets_iso and self.alerted_session_t1_reset and self.alerted_session_t1_reset != s_resets_iso:
            self.alerted_session_t1_reset = None
        if s_resets_iso and self.alerted_session_t2_reset and self.alerted_session_t2_reset != s_resets_iso:
            self.alerted_session_t2_reset = None
        if w_resets_iso and self.alerted_weekly_t1_reset and self.alerted_weekly_t1_reset != w_resets_iso:
            self.alerted_weekly_t1_reset = None
        if w_resets_iso and self.alerted_weekly_t2_reset and self.alerted_weekly_t2_reset != w_resets_iso:
            self.alerted_weekly_t2_reset = None

        return triggered
