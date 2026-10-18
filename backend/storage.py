"""SQLite storage for usage snapshots."""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import json
import logging
import os
from pathlib import Path
import sqlite3
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    five_hour_utilization REAL,
    five_hour_resets_at TEXT,
    seven_day_all_utilization REAL,
    seven_day_all_resets_at TEXT,
    seven_day_sonnet_utilization REAL,
    seven_day_sonnet_resets_at TEXT,
    seven_day_opus_utilization REAL,
    seven_day_opus_resets_at TEXT,
    monthly_limit_cents INTEGER,
    monthly_used_credits_cents REAL,
    monthly_utilization REAL,
    monthly_resets_at TEXT,
    raw_response TEXT
);
CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON usage_snapshots(timestamp);
"""


@dataclass
class SnapshotRecord:
    timestamp: datetime
    five_hour_utilization: Optional[float]
    five_hour_resets_at: Optional[datetime]
    seven_day_all_utilization: Optional[float]
    seven_day_all_resets_at: Optional[datetime]
    seven_day_sonnet_utilization: Optional[float]
    seven_day_sonnet_resets_at: Optional[datetime]
    seven_day_opus_utilization: Optional[float] = None
    seven_day_opus_resets_at: Optional[datetime] = None
    raw_response: Optional[str] = None


def secure_directory(path: Path) -> None:
    """Ensures a directory exists with strict user-only permissions (0700)."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        if (path.stat().st_mode & 0o777) != 0o700:
            os.chmod(path, 0o700)
    except OSError as e:
        logger.debug(f"Could not enforce 0700 permissions on {path}: {e}")


def secure_file(path: Path) -> None:
    """Ensures file permissions are strict user-only (0600)."""
    try:
        if path.is_file() and (path.stat().st_mode & 0o777) != 0o600:
            os.chmod(path, 0o600)
    except OSError as e:
        logger.debug(f"Could not enforce 0600 permissions on {path}: {e}")


def get_default_db_path() -> Path:
    """Default path for the SQLite database in ~/.local/share/token-monitor/ with auto-migration from legacy path."""
    base_dir = Path.home() / ".local" / "share" / "token-monitor"
    secure_directory(base_dir)
    target_db = base_dir / "history.db"

    # Auto-Migration von bisherigem Pfad (~/.local/share/kde-claude-stat/history.db)
    if not target_db.exists():
        legacy_db = Path.home() / ".local" / "share" / "kde-claude-stat" / "history.db"
        if legacy_db.is_file():
            try:
                import shutil
                shutil.copy2(legacy_db, target_db)
                secure_file(target_db)
                logger.info(f"Successfully migrated legacy database from {legacy_db} to {target_db}")
            except Exception as e:
                logger.warning(f"Could not migrate legacy database: {e}")

    return target_db



class StorageDB:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_default_db_path()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(SCHEMA)
        secure_file(self.db_path)
        try:
            self.repair_unnormalized_snapshots()
        except Exception as e:
            logger.debug(f"Snapshot repair skipped: {e}")

    def repair_unnormalized_snapshots(self) -> int:
        """
        Korrigiert fälschlicherweise nicht durch 100 geteilte Snapshots,
        bei denen 1.0 % (1 %) fälschlicherweise als 1.0 (100 %) statt 0.01 gespeichert wurde.
        """
        repaired = 0
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, five_hour_utilization, seven_day_all_utilization, raw_response FROM usage_snapshots WHERE five_hour_utilization = 1.0 OR seven_day_all_utilization = 1.0"
                )
                rows = cursor.fetchall()
                for row in rows:
                    row_id = row["id"]
                    raw = row["raw_response"]
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw)
                        fh = data.get("five_hour") or {}
                        sd = data.get("seven_day") or {}
                        limits = data.get("limits") or []

                        fix_fh = False
                        if row["five_hour_utilization"] == 1.0:
                            if fh.get("utilization") == 1.0 or fh.get("used_percentage") == 1.0:
                                fix_fh = True
                            for lim in limits:
                                if isinstance(lim, dict) and lim.get("kind") == "session" and lim.get("percent") == 1:
                                    fix_fh = True

                        fix_sd = False
                        if row["seven_day_all_utilization"] == 1.0:
                            if sd.get("utilization") == 1.0 or sd.get("used_percentage") == 1.0:
                                fix_sd = True
                            for lim in limits:
                                if isinstance(lim, dict) and lim.get("kind") == "weekly_all" and lim.get("percent") == 1:
                                    fix_sd = True

                        if fix_fh and fix_sd:
                            cursor.execute(
                                "UPDATE usage_snapshots SET five_hour_utilization = 0.01, seven_day_all_utilization = 0.01 WHERE id = ?",
                                (row_id,),
                            )
                            repaired += 1
                        elif fix_fh:
                            cursor.execute(
                                "UPDATE usage_snapshots SET five_hour_utilization = 0.01 WHERE id = ?",
                                (row_id,),
                            )
                            repaired += 1
                        elif fix_sd:
                            cursor.execute(
                                "UPDATE usage_snapshots SET seven_day_all_utilization = 0.01 WHERE id = ?",
                                (row_id,),
                            )
                            repaired += 1
                    except Exception:
                        pass
        finally:
            conn.close()
        return repaired

    def insert_snapshot(
        self,
        five_hour_util: Optional[float],
        five_hour_resets: Optional[datetime],
        seven_day_util: Optional[float],
        seven_day_resets: Optional[datetime],
        sonnet_util: Optional[float] = None,
        sonnet_resets: Optional[datetime] = None,
        opus_util: Optional[float] = None,
        opus_resets: Optional[datetime] = None,
        raw_response: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Saves a new snapshot to the database."""
        ts = timestamp or datetime.now(timezone.utc)
        ts_iso = ts.isoformat()

        recent_cutoff = ts.timestamp() - 60
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT five_hour_utilization, seven_day_all_utilization, timestamp FROM usage_snapshots ORDER BY timestamp DESC LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                last_fh = row["five_hour_utilization"]
                last_sd = row["seven_day_all_utilization"]
                last_dt = datetime.fromisoformat(row["timestamp"])

                # If statusline did not provide five_hour, carry forward last valid five_hour
                if five_hour_util is None and last_fh is not None:
                    five_hour_util = last_fh

                # Filter corrupted drop to 0% if recent usage was established
                if last_sd and last_sd > 0.05 and seven_day_util == 0.0 and (ts.timestamp() - last_dt.timestamp() < 3600):
                    return

                # Deduplicate: Skip if within 60s and change is negligible (< 1.5% jitter)
                if last_dt.timestamp() > recent_cutoff:
                    sd_diff = abs((last_sd or 0.0) - (seven_day_util or 0.0))
                    fh_diff = abs((last_fh or 0.0) - (five_hour_util or 0.0))
                    if sd_diff < 0.015 and fh_diff < 0.015:
                        return


            conn.execute(
                """
                INSERT INTO usage_snapshots (
                    timestamp,
                    five_hour_utilization, five_hour_resets_at,
                    seven_day_all_utilization, seven_day_all_resets_at,
                    seven_day_sonnet_utilization, seven_day_sonnet_resets_at,
                    seven_day_opus_utilization, seven_day_opus_resets_at,
                    raw_response
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts_iso,
                    five_hour_util,
                    five_hour_resets.isoformat() if five_hour_resets else None,
                    seven_day_util,
                    seven_day_resets.isoformat() if seven_day_resets else None,
                    sonnet_util,
                    sonnet_resets.isoformat() if sonnet_resets else None,
                    opus_util,
                    opus_resets.isoformat() if opus_resets else None,
                    raw_response,
                ),
            )
            conn.commit()

        # Automatische Datenbereinigung älterer Snapshots
        try:
            self.cleanup_old_snapshots()
        except Exception as e:
            logger.debug(f"Snapshot cleanup skipped: {e}")

    def cleanup_old_snapshots(self, retention_days: int = 60) -> int:
        """Löscht Snapshots, die älter als retention_days sind, um unbegrenztes Datenbankwachstum zu verhindern."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM usage_snapshots WHERE timestamp < ?",
                (cutoff.isoformat(),),
            )
            conn.commit()
            return cursor.rowcount

    def get_snapshots_since(self, since: datetime) -> List[SnapshotRecord]:
        """Retrieves all snapshots since a given timestamp."""
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM usage_snapshots WHERE timestamp >= ? ORDER BY timestamp ASC",
                (since.isoformat(),),
            )
            rows = cur.fetchall()

        results: List[SnapshotRecord] = []
        for r in rows:
            try:
                dt = datetime.fromisoformat(r["timestamp"])
                fh_resets = (
                    datetime.fromisoformat(r["five_hour_resets_at"])
                    if r["five_hour_resets_at"]
                    else None
                )
                sd_resets = (
                    datetime.fromisoformat(r["seven_day_all_resets_at"])
                    if r["seven_day_all_resets_at"]
                    else None
                )
                sonnet_resets = (
                    datetime.fromisoformat(r["seven_day_sonnet_resets_at"])
                    if r["seven_day_sonnet_resets_at"]
                    else None
                )
                opus_resets = (
                    datetime.fromisoformat(r["seven_day_opus_resets_at"])
                    if ("seven_day_opus_resets_at" in r.keys() and r["seven_day_opus_resets_at"])
                    else None
                )
                opus_util = r["seven_day_opus_utilization"] if "seven_day_opus_utilization" in r.keys() else None
                results.append(
                    SnapshotRecord(
                        timestamp=dt,
                        five_hour_utilization=r["five_hour_utilization"],
                        five_hour_resets_at=fh_resets,
                        seven_day_all_utilization=r["seven_day_all_utilization"],
                        seven_day_all_resets_at=sd_resets,
                        seven_day_sonnet_utilization=r["seven_day_sonnet_utilization"],
                        seven_day_sonnet_resets_at=sonnet_resets,
                        seven_day_opus_utilization=opus_util,
                        seven_day_opus_resets_at=opus_resets,
                        raw_response=r["raw_response"],
                    )
                )
            except Exception as e:
                logger.warning(f"Error parsing snapshot: {e}")
                continue
        return results

    def get_latest_snapshot(self) -> Optional[SnapshotRecord]:
        """Ruft den neuesten gespeicherten Snapshot-Datensatz ab."""
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM usage_snapshots ORDER BY timestamp DESC LIMIT 1"
            )
            row = cur.fetchone()
        if not row:
            return None
        try:
            dt = datetime.fromisoformat(row["timestamp"])
            fh_resets = (
                datetime.fromisoformat(row["five_hour_resets_at"])
                if row["five_hour_resets_at"]
                else None
            )
            sd_resets = (
                datetime.fromisoformat(row["seven_day_all_resets_at"])
                if row["seven_day_all_resets_at"]
                else None
            )
            sonnet_resets = (
                datetime.fromisoformat(row["seven_day_sonnet_resets_at"])
                if row["seven_day_sonnet_resets_at"]
                else None
            )
            opus_resets = (
                datetime.fromisoformat(row["seven_day_opus_resets_at"])
                if ("seven_day_opus_resets_at" in row.keys() and row["seven_day_opus_resets_at"])
                else None
            )
            opus_util = row["seven_day_opus_utilization"] if "seven_day_opus_utilization" in row.keys() else None
            return SnapshotRecord(
                timestamp=dt,
                five_hour_utilization=row["five_hour_utilization"],
                five_hour_resets_at=fh_resets,
                seven_day_all_utilization=row["seven_day_all_utilization"],
                seven_day_all_resets_at=sd_resets,
                seven_day_sonnet_utilization=row["seven_day_sonnet_utilization"],
                seven_day_sonnet_resets_at=sonnet_resets,
                seven_day_opus_utilization=opus_util,
                seven_day_opus_resets_at=opus_resets,
                raw_response=row["raw_response"],
            )
        except Exception as e:
            logger.warning(f"Error parsing latest snapshot: {e}")
            return None
