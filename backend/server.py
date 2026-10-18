"""Local HTTP Server to serve metrics to KDE Plasma Widget."""

import http.server
import json
import logging
import threading
import time
from typing import Optional, Dict, Any

from .cli import refresh_and_compute_stats
from .notifier import NotificationManager, NotificationConfig, send_desktop_notification

logger = logging.getLogger(__name__)

# Metrics cache (valid for at least 10s to prevent unnecessary API polling)
_cached_stats: Optional[Dict[str, Any]] = None
_last_fetch_time: float = 0
_lock = threading.Lock()
CACHE_TTL_SECONDS = 10

_notification_manager = NotificationManager()


def get_cached_or_fresh_stats(force: bool = False) -> Dict[str, Any]:
    global _cached_stats, _last_fetch_time
    with _lock:
        now = time.time()
        if not force and _cached_stats and (now - _last_fetch_time < CACHE_TTL_SECONDS):
            return _cached_stats

        try:
            _cached_stats = refresh_and_compute_stats(force=force)
            _last_fetch_time = now
            if _cached_stats and not _cached_stats.get("error"):
                _notification_manager.check_and_notify(_cached_stats)
        except Exception as e:
            logger.error(f"Error refreshing stats: {e}")
            if _cached_stats:
                return _cached_stats
            return {"error": str(e)}

        return _cached_stats


MAX_POST_PAYLOAD_BYTES = 65536  # 64 KB Max payload size


class StatHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def _is_untrusted_origin(self) -> bool:
        """
        Rejects requests carrying an Origin header (e.g. from web browsers via cross-origin fetch/xhr).
        Local Plasma applet and local scripts do not send an Origin header.
        """
        origin = self.headers.get("Origin")
        if origin:
            logger.warning(f"Rejected request from untrusted origin: {origin}")
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            body = json.dumps({"error": "Forbidden: cross-origin browser requests not permitted"}).encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return True
        return False

    def do_OPTIONS(self):
        # Preflight requests from web browsers are rejected
        self.send_response(403)
        self.end_headers()

    def do_GET(self):
        if self._is_untrusted_origin():
            return

        force_refresh = self.path == "/refresh"

        if self.path in ("/stats", "/refresh") or self.path.startswith("/stats?"):
            data = get_cached_or_fresh_stats(force=force_refresh)
            body = json.dumps(data).encode("utf-8")
            self._send_json_response(200, body)
        elif self.path == "/notify-test":
            success = send_desktop_notification(
                summary="Token Monitor for Claude Code",
                body="Test-Benachrichtigung erfolgreich empfangen! KDE Plasma Benachrichtigungen funktionieren.",
                urgency=1,
            )
            body = json.dumps({"status": "ok" if success else "failed"}).encode("utf-8")
            self._send_json_response(200, body)
        elif self.path == "/notify-config":
            body = json.dumps(_notification_manager.config.__dict__).encode("utf-8")
            self._send_json_response(200, body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self._is_untrusted_origin():
            return

        if self.path == "/notify-config":
            try:
                content_length_header = self.headers.get("Content-Length")
                length = int(content_length_header) if content_length_header else 0
                if length < 0 or length > MAX_POST_PAYLOAD_BYTES:
                    self.send_response(413)
                    self.send_header("Content-Type", "application/json")
                    err_body = json.dumps({"error": "Payload Too Large (max 64KB)"}).encode("utf-8")
                    self.send_header("Content-Length", str(len(err_body)))
                    self.end_headers()
                    self.wfile.write(err_body)
                    return

                payload = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
                new_cfg = NotificationConfig(
                    enabled=bool(payload.get("enabled", True)),
                    notify_burn_rate=bool(payload.get("notify_burn_rate", True)),
                    notify_threshold_1=bool(payload.get("notify_threshold_1", True)),
                    threshold_1_percent=int(payload.get("threshold_1_percent", 85)),
                    notify_threshold_2=bool(payload.get("notify_threshold_2", True)),
                    threshold_2_percent=int(payload.get("threshold_2_percent", 95)),
                )
                _notification_manager.update_config(new_cfg)
                body = json.dumps({"status": "updated"}).encode("utf-8")
                self._send_json_response(200, body)
            except Exception as e:
                logger.error(f"Failed to update notify config: {e}")
                body = json.dumps({"error": str(e)}).encode("utf-8")
                self._send_json_response(400, body)
        else:
            self.send_response(404)
            self.end_headers()

    def _send_json_response(self, code: int, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Suppress noisy standard HTTP request console spam
        pass


def ensure_applet_icon_installed():
    """Stellt sicher, dass das Applet-Icon im Benutzer-Icon-Theme registriert ist (für Plasma Widget Explorer & Über-Dialog)."""
    try:
        from pathlib import Path
        import shutil
        import subprocess

        user_icons = Path.home() / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps"
        target_icon = user_icons / "com.buellsunited.TokenMonitor.svg"
        if not target_icon.is_file():
            sources = [
                Path.home() / ".local" / "share" / "plasma" / "plasmoids" / "com.buellsunited.TokenMonitor" / "contents" / "icons" / "com.buellsunited.TokenMonitor.svg",
                Path(__file__).resolve().parent.parent / "icons" / "com.buellsunited.TokenMonitor.svg",
            ]
            for src in sources:
                if src.is_file():
                    user_icons.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, target_icon)
                    subprocess.run(["kbuildsycoca6", "--noincremental"], capture_output=True, check=False)
                    break
    except Exception as e:
        logger.debug(f"Could not auto-register icon: {e}")


def run_server(port: int = 48291):
    ensure_applet_icon_installed()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), StatHTTPRequestHandler)
    print(f"Token Monitor for Claude Code server running at http://127.0.0.1:{port}/stats")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

