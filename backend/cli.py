"""CLI and data collection service for Token Monitor for Claude Code."""

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import sys
from typing import Dict, Any, Optional, Tuple, List

from .client import fetch_usage_api, is_rate_limited, reset_rate_limit, get_rate_limit_remaining_seconds
from .process import is_claude_process_running
from .storage import StorageDB, SnapshotRecord, get_default_db_path
from .calculator import calculate_burn_metrics, calculate_lookback_chart

logger = logging.getLogger(__name__)

API_MIN_INTERVAL_SECONDS = 180  # 3 Minuten Mindestabstand zum Schutz vor Rate-Limits


def parse_iso_datetime(dt_val: Any) -> Optional[datetime]:
    if dt_val is None or dt_val == "":
        return None
    if isinstance(dt_val, (int, float)):
        try:
            return datetime.fromtimestamp(dt_val, tz=timezone.utc)
        except Exception:
            return None
    try:
        dt = datetime.fromisoformat(str(dt_val).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def collect_from_stdin(passthrough: bool = False) -> Dict[str, Any]:
    """Reads statusline JSON from stdin, records snapshots, and optionally passes through to stdout."""
    raw_input = sys.stdin.read()
    if passthrough:
        # Immediate passthrough for downstream statuslines in the pipeline
        sys.stdout.write(raw_input)
        sys.stdout.flush()

    if not raw_input.strip():
        return {}

    try:
        data = json.loads(raw_input)
    except Exception as e:
        logger.error(f"Failed to parse stdin JSON: {e}")
        return {}

    rate_limits = data.get("rate_limits") or data
    if not isinstance(rate_limits, dict):
        return {}

    def extract_limit(block: Any) -> Tuple[Optional[float], Optional[datetime]]:
        if not block or not isinstance(block, dict):
            return None, None
        val = block.get("used_percentage")
        if val is None:
            val = block.get("utilization")
        try:
            val_f = float(val) / 100.0 if val is not None else None
        except (ValueError, TypeError):
            val_f = None
        resets = parse_iso_datetime(block.get("resets_at"))
        return val_f, resets

    fh_util, fh_resets = extract_limit(rate_limits.get("five_hour"))
    sd_util, sd_resets = extract_limit(rate_limits.get("seven_day"))
    sonnet_util, sonnet_resets = extract_limit(rate_limits.get("seven_day_sonnet"))

    if fh_util is not None or sd_util is not None or sonnet_util is not None:
        try:
            db = StorageDB()
            db.insert_snapshot(
                five_hour_util=fh_util,
                five_hour_resets=fh_resets,
                seven_day_util=sd_util,
                seven_day_resets=sd_resets,
                sonnet_util=sonnet_util,
                sonnet_resets=sonnet_resets,
                raw_response=raw_input,
            )
        except Exception as e:
            logger.error(f"Snapshot insertion failed: {e}")

    return {"status": "collected"}


def format_model_display_name(model_id: str) -> str:
    """Formatiert Modell-IDs (z. B. claude-sonnet-5-5) in lesbare Anzeigenamen."""
    if not model_id:
        return ""
    mapping = {
        "claude-sonnet-5-5": "Sonnet 5.5",
        "claude-opus-4-8": "Opus 4.8",
        "claude-3-7-sonnet": "Sonnet 3.7",
        "claude-3-5-sonnet": "Sonnet 3.5",
        "claude-3-5-haiku": "Haiku 3.5",
        "claude-3-opus": "Opus 3",
        "claude-3-haiku": "Haiku 3",
    }
    for key, name in mapping.items():
        if key in model_id.lower():
            return name

    clean = model_id.lower()
    if clean.startswith("claude-"):
        clean = clean[7:]
    clean = re.sub(r"-\d{8}$", "", clean)
    m = re.match(r"^([a-z]+)-(\d+)-(\d+)$", clean)
    if m:
        family, major, minor = m.groups()
        return f"{family.capitalize()} {major}.{minor}"

    parts = clean.split("-")
    return " ".join(p.capitalize() for p in parts)


def get_current_model(
    records: List[SnapshotRecord],
    settings_path: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, str]]:
    """
    Ermittelt das aktuell genutzte Modell.
    Priorität:
    1. Fake-Modus: Modell aus den gefälschten Snapshots
    2. Frische Snapshots (< 30 Min alt und neuer als settings.json mtime)
    3. Aktuelle Konfiguration in ~/.claude/settings.json
    4. Ältere Snapshots aus records als Fallback
    """
    current_time = now or datetime.now(timezone.utc)
    target_settings = settings_path or (Path.home() / ".claude" / "settings.json")

    # 1. Fake-Modus prüfen
    fake_flag = get_default_db_path().parent / "fake_active"
    is_fake = fake_flag.is_file()

    latest_snap_model: Optional[Dict[str, str]] = None
    latest_snap_dt: Optional[datetime] = None

    for rec in reversed(records):
        if rec.raw_response:
            try:
                data = json.loads(rec.raw_response)
                m = data.get("model")
                if isinstance(m, dict) and (m.get("display_name") or m.get("id")):
                    m_id = str(m.get("id", ""))
                    d_name = str(m.get("display_name") or format_model_display_name(m_id))
                    latest_snap_model = {"id": m_id, "display_name": d_name}
                    latest_snap_dt = rec.timestamp
                    break
                elif isinstance(m, str) and m.strip():
                    clean_id = m.strip()
                    latest_snap_model = {"id": clean_id, "display_name": format_model_display_name(clean_id)}
                    latest_snap_dt = rec.timestamp
                    break
            except Exception:
                pass

    if is_fake and latest_snap_model:
        return latest_snap_model

    # 2. settings.json auslesen
    settings_model: Optional[Dict[str, str]] = None
    settings_mtime = 0.0
    try:
        if target_settings.is_file():
            settings_mtime = target_settings.stat().st_mtime
            data = json.loads(target_settings.read_text(encoding="utf-8"))
            m = data.get("model")
            if isinstance(m, str) and m.strip():
                clean_id = m.strip()
                settings_model = {"id": clean_id, "display_name": format_model_display_name(clean_id)}
    except Exception:
        pass

    # 3. Frischer Snapshot (< 30 Min alt und neuer als settings.json mtime)
    if latest_snap_model and latest_snap_dt:
        snap_ts = latest_snap_dt.timestamp()
        age_seconds = current_time.timestamp() - snap_ts
        if age_seconds < 1800 and snap_ts >= settings_mtime:
            return latest_snap_model

    # 4. Modell aus settings.json
    if settings_model:
        return settings_model

    # 5. Fallback auf jüngstes Snapshot-Modell
    if latest_snap_model:
        return latest_snap_model

    return None


def refresh_and_compute_stats(force: bool = False) -> Dict[str, Any]:
    """Queries live data via API, saves snapshot, and computes current metrics."""
    db = StorageDB()
    now = datetime.now(timezone.utc)
    is_active = is_claude_process_running()

    raw_data: Optional[Dict[str, Any]] = None

    latest_snapshot = db.get_latest_snapshot()
    # Verhindert Überlastung der API bei häufigen Widget-Pings (mind. 180s / 3 Min Abstand, außer bei explizitem force)
    min_interval_passed = (
        latest_snapshot is None
        or (now.timestamp() - latest_snapshot.timestamp.timestamp()) >= API_MIN_INTERVAL_SECONDS
    )

    fake_flag = get_default_db_path().parent / "fake_active"
    # 1. Query API only when Claude Code is active or an explicit refresh was requested (and not in fake mode)
    if not fake_flag.is_file() and ((is_active and min_interval_passed) or force):
        if force:
            reset_rate_limit()
        if not is_rate_limited():
            try:
                raw_data = fetch_usage_api()
            except Exception as e:
                logger.error(f"API request failed: {e}")
                raw_data = None
        else:
            logger.info("API request paused: Rate limit backoff is active.")

    # 2. Fetch historical snapshots from the past 7 days
    seven_days_ago = datetime.fromtimestamp(now.timestamp() - 7 * 86400, tz=timezone.utc)
    records = db.get_snapshots_since(seven_days_ago)

    if raw_data:
        fh = raw_data.get("five_hour") or {}
        sd = raw_data.get("seven_day") or {}
        sonnet = raw_data.get("seven_day_sonnet") or {}
        opus = raw_data.get("seven_day_opus") or {}

        fh_util = fh.get("utilization")
        fh_resets = parse_iso_datetime(fh.get("resets_at"))
        sd_util = sd.get("utilization")
        sd_resets = parse_iso_datetime(sd.get("resets_at"))
        sonnet_util = sonnet.get("utilization")
        sonnet_resets = parse_iso_datetime(sonnet.get("resets_at"))
        opus_util = opus.get("utilization")
        opus_resets = parse_iso_datetime(opus.get("resets_at"))

        # Fallback auf limits-Array, falls utilization nicht im Einzelobjekt lag
        if fh_util is None or sd_util is None or sonnet_util is None or opus_util is None:
            for lim in raw_data.get("limits") or []:
                if not isinstance(lim, dict):
                    continue
                kind = lim.get("kind")
                pct = lim.get("percent")
                res = parse_iso_datetime(lim.get("resets_at"))
                if kind == "session" and fh_util is None:
                    fh_util = pct
                    if fh_resets is None:
                        fh_resets = res
                elif kind == "weekly_all" and sd_util is None:
                    sd_util = pct
                    if sd_resets is None:
                        sd_resets = res
                elif kind == "weekly_sonnet" and sonnet_util is None:
                    sonnet_util = pct
                    if sonnet_resets is None:
                        sonnet_resets = res
                elif kind == "weekly_opus" and opus_util is None:
                    opus_util = pct
                    if opus_resets is None:
                        opus_resets = res

        def _to_ratio(v: Any) -> Optional[float]:
            if v is None:
                return None
            try:
                return float(v) / 100.0
            except (ValueError, TypeError):
                return None

        fh_util = _to_ratio(fh_util)
        sd_util = _to_ratio(sd_util)
        sonnet_util = _to_ratio(sonnet_util)
        opus_util = _to_ratio(opus_util)

        db.insert_snapshot(
            five_hour_util=fh_util,
            five_hour_resets=fh_resets,
            seven_day_util=sd_util,
            seven_day_resets=sd_resets,
            sonnet_util=sonnet_util,
            sonnet_resets=sonnet_resets,
            opus_util=opus_util,
            opus_resets=opus_resets,
            raw_response=json.dumps(raw_data),
            timestamp=now,
        )
        records.append(
            SnapshotRecord(
                timestamp=now,
                five_hour_utilization=fh_util,
                five_hour_resets_at=fh_resets,
                seven_day_all_utilization=sd_util,
                seven_day_all_resets_at=sd_resets,
                seven_day_sonnet_utilization=sonnet_util,
                seven_day_sonnet_resets_at=sonnet_resets,
                seven_day_opus_utilization=opus_util,
                seven_day_opus_resets_at=opus_resets,
                raw_response=json.dumps(raw_data),
            )
        )
    else:
        # Fallback to last stored snapshot
        if not records:
            return {"error": "No data available"}
        last = records[-1]
        fh_util = last.five_hour_utilization
        fh_resets = last.five_hour_resets_at
        sd_util = last.seven_day_all_utilization
        sd_resets = last.seven_day_all_resets_at
        sonnet_util = last.seven_day_sonnet_utilization
        sonnet_resets = last.seven_day_sonnet_resets_at
        opus_util = last.seven_day_opus_utilization
        opus_resets = last.seven_day_opus_resets_at

        # When Claude Code is inactive and the reset timestamp is in the past,
        # the reset has already occurred -> reset utilization to 0
        if not is_active:
            def _is_expired(dt: Optional[datetime]) -> bool:
                if not dt:
                    return False
                target = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                return target < now

            if _is_expired(fh_resets):
                fh_util = 0.0
                fh_resets = None
            if _is_expired(sd_resets):
                sd_util = 0.0
                sd_resets = None
            if _is_expired(sonnet_resets):
                sonnet_util = 0.0
                sonnet_resets = None
            if _is_expired(opus_resets):
                opus_util = 0.0
                opus_resets = None

    if fh_resets:
        session_metrics = calculate_burn_metrics(
            records=records,
            limit_type="session",
            resets_at=fh_resets,
            window_hours=5.0,
            current_utilization=fh_util or 0.0,
            now=now,
            is_active=is_active,
        )
    else:
        # No active 5h window (usage 0%, reset not yet triggered)
        session_metrics = {
            "utilization": round((fh_util or 0.0) * 100.0 if (fh_util or 0.0) <= 1.0 else (fh_util or 0.0), 1),
            "budget_pace": 0.0,
            "pace_status": "on_pace",
            "burn_rate_pct_per_hour": 0.0,
            "trend": "idle",
            "is_active": is_active,
            "estimated_minutes_to_100": None,
            "resets_in_minutes": 0,
            "resets_at_iso": None,
            "hits_100_before_reset": False,
            "chart": {
                "elapsed_ratio": 0.0,
                "usage": [{"x": 0.0, "y": 0.0}],
                "projection": [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}],
            },
        }

    weekly_metrics = (
        calculate_burn_metrics(
            records=records,
            limit_type="weekly",
            resets_at=sd_resets,
            window_hours=168.0,
            current_utilization=sd_util or 0.0,
            now=now,
            is_active=is_active,
        )
        if sd_resets
        else None
    )

    weekly_sonnet_metrics = (
        calculate_burn_metrics(
            records=records,
            limit_type="weekly_sonnet",
            resets_at=sonnet_resets,
            window_hours=168.0,
            current_utilization=sonnet_util or 0.0,
            now=now,
            is_active=is_active,
        )
        if sonnet_resets
        else None
    )

    weekly_opus_metrics = (
        calculate_burn_metrics(
            records=records,
            limit_type="weekly_opus",
            resets_at=opus_resets,
            window_hours=168.0,
            current_utilization=opus_util or 0.0,
            now=now,
            is_active=is_active,
        )
        if opus_resets
        else None
    )

    # 30-Tage-Verlauf (mehrere Weekly-Reset-Zyklen) als zusätzliche Lookback-Ansicht.
    # Separate Abfrage, damit die 7-Tage-Berechnungen oben unberührt bleiben.
    thirty_days_ago = datetime.fromtimestamp(now.timestamp() - 30 * 86400, tz=timezone.utc)
    records_30d = db.get_snapshots_since(thirty_days_ago)
    if weekly_metrics is not None:
        weekly_metrics["charts"]["30d"] = calculate_lookback_chart(
            records_30d, "weekly", now, 720.0, (sd_util or 0.0) * 100.0
        )
    if weekly_sonnet_metrics is not None:
        weekly_sonnet_metrics["charts"]["30d"] = calculate_lookback_chart(
            records_30d, "weekly_sonnet", now, 720.0, (sonnet_util or 0.0) * 100.0
        )
    if weekly_opus_metrics is not None:
        weekly_opus_metrics["charts"]["30d"] = calculate_lookback_chart(
            records_30d, "weekly_opus", now, 720.0, (opus_util or 0.0) * 100.0
        )

    # Modell-Aufschlüsselung (Model Breakdown)
    model_limits: List[Dict[str, Any]] = []
    source_raw: Optional[Dict[str, Any]] = raw_data
    if not source_raw and records:
        for r in reversed(records):
            if r.raw_response:
                try:
                    source_raw = json.loads(r.raw_response)
                    break
                except Exception:
                    pass

    if source_raw and isinstance(source_raw, dict):
        raw_limits = source_raw.get("limits")
        if isinstance(raw_limits, list) and len(raw_limits) > 0:
            for lim in raw_limits:
                if not isinstance(lim, dict):
                    continue
                k = lim.get("kind")
                if k in ("session", "weekly_all"):
                    continue
                scope = lim.get("scope") or {}
                lbl = ""
                if isinstance(scope.get("model"), dict):
                    lbl = scope["model"].get("display_name") or scope["model"].get("id") or ""
                if not lbl:
                    lbl = scope.get("surface") or k or ""
                lbl = format_model_display_name(lbl) if lbl else "Model"
                pct = lim.get("percent") or 0.0
                model_limits.append({
                    "label": lbl,
                    "percent": round(float(pct), 1),
                    "kind": k,
                })
        else:
            # Check seven_day_* objects (sonnet, opus etc.)
            non_model_keys = {"all", "oauth_apps", "cowork", "omelette"}
            for key, val in source_raw.items():
                if key.startswith("seven_day_") and isinstance(val, dict):
                    sub = key[len("seven_day_"):]
                    if sub in non_model_keys:
                        continue
                    util = val.get("utilization")
                    if util is not None:
                        label = "Sonnet" if sub == "sonnet" else ("Opus" if sub == "opus" else sub.capitalize())
                        model_limits.append({
                            "label": label,
                            "percent": round(float(util), 1),
                            "kind": f"weekly_{sub}",
                            "resets_at": val.get("resets_at"),
                        })

    if not model_limits:
        if sonnet_util is not None:
            pct = round(sonnet_util * 100.0, 1) if sonnet_util <= 1.0 else round(sonnet_util, 1)
            model_limits.append({
                "label": "Sonnet",
                "percent": pct,
                "kind": "weekly_sonnet",
            })
        if opus_util is not None:
            pct = round(opus_util * 100.0, 1) if opus_util <= 1.0 else round(opus_util, 1)
            model_limits.append({
                "label": "Opus",
                "percent": pct,
                "kind": "weekly_opus",
            })

    current_model = get_current_model(records, now=now)
    if current_model and session_metrics:
        session_metrics["model"] = current_model

    return {
        "timestamp": now.isoformat(),
        "is_active": is_active,
        "is_rate_limited": is_rate_limited(),
        "rate_limit_remaining_seconds": int(get_rate_limit_remaining_seconds()),
        "model": current_model,
        "model_limits": model_limits,
        "session": session_metrics,
        "weekly": weekly_metrics,
        "weekly_sonnet": weekly_sonnet_metrics,
        "weekly_opus": weekly_opus_metrics,
    }


def main():
    parser = argparse.ArgumentParser(description="Token Monitor for Claude Code CLI Backend")
    parser.add_argument(
        "command",
        choices=["status", "collect", "serve", "install-hook", "remove-hook", "test-notify"],
        help="Command to execute",
    )
    parser.add_argument("--port", type=int, default=48291, help="Port for local HTTP server")
    parser.add_argument(
        "--passthrough",
        action="store_true",
        help="Pass stdin unmodified to stdout (for pipelines)",
    )
    args = parser.parse_args()

    if args.command == "collect":
        collect_from_stdin(passthrough=args.passthrough)
    elif args.command == "install-hook":
        from .hook import install_statusline_hook
        ok, msg = install_statusline_hook()
        print(msg)
        sys.exit(0 if ok else 1)
    elif args.command == "remove-hook":
        from .hook import remove_statusline_hook
        ok, msg = remove_statusline_hook()
        print(msg)
        sys.exit(0 if ok else 1)
    elif args.command == "status":
        stats = refresh_and_compute_stats()
        print(json.dumps(stats, indent=2))
    elif args.command == "serve":
        from .server import run_server
        run_server(args.port)
    elif args.command == "test-notify":
        from .notifier import send_desktop_notification
        ok = send_desktop_notification(
            summary="Token Monitor for Claude Code",
            body="Test-Benachrichtigung via CLI erfolgreich gesendet!",
            urgency=1,
        )
        print("[✓] Benachrichtigung gesendet." if ok else "[!] Fehler beim Senden.")


if __name__ == "__main__":
    main()
