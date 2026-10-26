"""Mathematical calculations for budget pace, burn rate, and projections using Python standard library."""

from datetime import datetime, timezone
import math
from statistics import linear_regression, StatisticsError, median
from typing import List, Optional, Tuple, Dict, Any
from .storage import SnapshotRecord


def calculate_budget_pace(
    resets_at: datetime,
    window_hours: float,
    now: Optional[datetime] = None,
) -> float:
    """Calculates linear elapsed time progress of a billing window (0.0 to 1.0)."""
    current = now or datetime.now(timezone.utc)
    if resets_at.tzinfo is None:
        resets_at = resets_at.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    total_seconds = window_hours * 3600.0
    if total_seconds <= 0:
        return 0.0

    # Proportion of elapsed time in the total window
    remaining_seconds = (resets_at - current).total_seconds()
    elapsed_seconds = total_seconds - remaining_seconds
    pace = elapsed_seconds / total_seconds

    return max(0.0, min(1.0, pace))


def calculate_burn_rate_linear_regression(
    points: List[Tuple[float, float]],
    window_hours: float,
    min_points: int = 3,
    min_span_pct: float = 0.10,
    max_lookback_hours: Optional[float] = None,
) -> float:
    """Calculates burn rate (percentage points/hour) via linear regression."""
    if len(points) < 2:
        return 0.0

    # Bei gesetztem Lookback-Fenster auf die jüngsten Datenpunkte fokussieren
    if max_lookback_hours is not None and len(points) >= 2:
        cutoff_h = points[-1][0] - max_lookback_hours
        recent_points = [p for p in points if p[0] >= cutoff_h]
        if len(recent_points) >= min_points or len(recent_points) >= 2:
            active_points = recent_points
        else:
            # Fallback: Mindestens die letzten min_points Punkte beibehalten
            active_points = points[-min_points:] if len(points) >= min_points else points
    else:
        active_points = points

    hours_span = active_points[-1][0] - active_points[0][0]
    effective_window = max_lookback_hours if max_lookback_hours is not None else window_hours
    min_span_hours = min(effective_window * min_span_pct, 6.0)

    # Validate minimum data points and time span
    if len(active_points) < min_points or hours_span < min_span_hours:
        if len(active_points) >= 2 and hours_span >= 0.05:
            # Sekantensteigung bei kürzerem aktiven Zeitfenster (> 3 Minuten)
            delta_y = active_points[-1][1] - active_points[0][1]
            return max(0.0, delta_y / hours_span)
        return 0.0

    x_vals = [p[0] for p in active_points]
    y_vals = [p[1] for p in active_points]

    try:
        # Standard library linear regression
        slope, _ = linear_regression(x_vals, y_vals)
        return max(0.0, float(slope))
    except StatisticsError:
        return 0.0



AHEAD_OF_PACE_MIN_UTILIZATION_PCT = 15.0
AHEAD_OF_PACE_MIN_PACE = 0.10
RECENT_BURN_WINDOW_FRACTION = 0.25
BURN_RATE_MIN_POINTS = 3


def calculate_recent_burn_rate(
    points: List[Tuple[float, float, float]],
    now_unix_seconds: float,
    window_hours: float,
) -> float:
    """Calculates burn rate preferring a sliding recent window (25% of window length) with fallback to last N points."""
    cutoff = now_unix_seconds - (window_hours * 3600.0 * RECENT_BURN_WINDOW_FRACTION)
    recent = [(p[0], p[1]) for p in points if p[2] >= cutoff]
    if len(recent) >= 2:
        return calculate_burn_rate_linear_regression(recent, window_hours=window_hours)

    fallback = [(p[0], p[1]) for p in points[-BURN_RATE_MIN_POINTS:]]
    return calculate_burn_rate_linear_regression(fallback, window_hours=window_hours)


def calculate_lookback_chart(
    records: List[SnapshotRecord],
    limit_type: str,
    current_time: datetime,
    lookback_hours: float,
    current_util_pct: float,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """Calculates a lookback chart series covering the last X hours up to now (ported from Token_Monitor_For_Win)."""
    win_start = current_time.timestamp() - (lookback_hours * 3600.0)

    # Bucket-Breite staffeln: 10 min (≤7h), 30 min (≤24h), 6 h (Monat/30d)
    if lookback_hours <= 7.0:
        bucket_sec = 600.0
    elif lookback_hours <= 24.0:
        bucket_sec = 1800.0
    else:
        bucket_sec = 21600.0

    buckets: Dict[int, List[Tuple[float, float, Optional[datetime]]]] = {}
    prev_val: Optional[float] = None
    prev_resets_at: Optional[datetime] = None

    # Sort records chronologically
    sorted_records = sorted(records, key=lambda r: r.timestamp.timestamp())

    for record in sorted_records:
        val: Optional[float] = None
        record_resets_at: Optional[datetime] = None
        if limit_type == "session":
            val = record.five_hour_utilization
            record_resets_at = record.five_hour_resets_at
        elif limit_type == "weekly":
            val = record.seven_day_all_utilization
            record_resets_at = record.seven_day_all_resets_at
        elif limit_type == "weekly_sonnet":
            val = record.seven_day_sonnet_utilization
            record_resets_at = record.seven_day_sonnet_resets_at
        elif limit_type == "weekly_opus":
            val = record.seven_day_opus_utilization
            record_resets_at = record.seven_day_opus_resets_at

        if val is None:
            continue

        pct = val * 100.0 if val <= 1.0 else val
        # Korrumpierte 0%-Dropouts bei bereits etablierter Nutzung ignorieren
        if pct <= 0.0 and current_util_pct > 5.0:
            continue

        ts = record.timestamp.timestamp()
        if ts < win_start:
            # Falls vor dem Fensterstart bereits ein Reset stattfand, Vorwert auf 0.0 nullen
            if record_resets_at is not None and record_resets_at.timestamp() < win_start:
                prev_val = 0.0
            else:
                prev_val = pct
            prev_resets_at = record_resets_at
            continue

        b_idx = int((ts - win_start) // bucket_sec)
        buckets.setdefault(b_idx, []).append((ts, pct, record_resets_at))

    series: List[Dict[str, float]] = []
    running_y = 0.0
    last_resets_at: Optional[datetime] = prev_resets_at
    reset_drop_threshold = 10.0

    # Bekannten Vorwert bei x=0.0 als Anker setzen
    if prev_val is not None:
        running_y = round(prev_val, 1)
        series.append({"x": 0.0, "y": running_y})

    for b_idx in sorted(buckets.keys()):
        items = buckets[b_idx]
        median_y = round(float(median([it[1] for it in items])), 1)
        latest_ts = items[-1][0]
        latest_resets_at = items[-1][2]

        is_reset = False
        if last_resets_at is not None and latest_resets_at is not None:
            t1 = last_resets_at if last_resets_at.tzinfo else last_resets_at.replace(tzinfo=timezone.utc)
            t2 = latest_resets_at if latest_resets_at.tzinfo else latest_resets_at.replace(tzinfo=timezone.utc)
            if abs((t2 - t1).total_seconds()) > 3600.0:
                is_reset = True
        if not is_reset and (running_y - median_y >= reset_drop_threshold):
            is_reset = True

        if is_reset:
            running_y = median_y
        else:
            # Innerhalb desselben Zyklus fängt max() Rundungs- und API-Jitter nach unten ab
            median_y = max(running_y, median_y)
            running_y = median_y

        last_resets_at = latest_resets_at

        norm_x = (latest_ts - win_start) / (lookback_hours * 3600.0)
        clamped_x = max(0.0, min(1.0, round(norm_x, 4)))
        if series and series[-1]["x"] == clamped_x:
            series[-1]["y"] = median_y
        else:
            series.append({"x": clamped_x, "y": median_y})

    rounded_curr = round(current_util_pct, 1)
    if series and (running_y - rounded_curr < reset_drop_threshold):
        rounded_curr = max(running_y, rounded_curr)

    if not series:
        series.append({"x": 0.0, "y": rounded_curr})
        series.append({"x": 1.0, "y": rounded_curr})
    elif series[-1]["x"] < 1.0:
        series.append({"x": 1.0, "y": rounded_curr})
    else:
        series[-1]["y"] = rounded_curr

    if label:
        tag = label
    elif lookback_hours >= 48.0 and lookback_hours % 24.0 == 0:
        tag = f"{int(lookback_hours / 24)}d"
    else:
        tag = f"{int(lookback_hours)}h"

    return {
        "elapsed_ratio": 1.0,
        "usage": series,
        "projection": [],
        "label_start": f"-{tag}",
        "label_end": "Now",
    }


def calculate_burn_metrics(
    records: List[SnapshotRecord],
    limit_type: str,
    resets_at: datetime,
    window_hours: float,
    current_utilization: float,
    now: Optional[datetime] = None,
    is_active: bool = True,
    max_lookback_hours: Optional[float] = None,
) -> Dict[str, Any]:

    """Calculates utilization, projection, and visualization data for a limit."""
    current_time = now or datetime.now(timezone.utc)
    if resets_at.tzinfo is None:
        resets_at = resets_at.replace(tzinfo=timezone.utc)

    window_start = resets_at.timestamp() - (window_hours * 3600.0)
    util_pct = current_utilization * 100.0 if current_utilization <= 1.0 else current_utilization

    # Bucket size: 5 min (300s) for 5-hour session, 30 min (1800s) for weekly
    bucket_sec = 300.0 if window_hours <= 5.0 else 1800.0

    raw_points: List[Tuple[float, float]] = []
    for record in records:
        if record.timestamp.timestamp() < window_start:
            continue

        val: Optional[float] = None
        if limit_type == "session":
            val = record.five_hour_utilization
        elif limit_type == "weekly":
            val = record.seven_day_all_utilization
        elif limit_type == "weekly_sonnet":
            val = record.seven_day_sonnet_utilization
        elif limit_type == "weekly_opus":
            val = record.seven_day_opus_utilization

        if val is None:
            continue

        pct = val * 100.0 if val <= 1.0 else val
        raw_points.append((record.timestamp.timestamp(), pct))

    # Chronologisch sortieren
    raw_points.sort(key=lambda item: item[0])

    # Isolierte 0%-Dropouts herausfiltern (z.B. API-Aussetzer mitten in etablierter Nutzung),
    # aber echte 0%-Messungen am Periodenstart oder nach Resets beibehalten.
    filtered_points: List[Tuple[float, float]] = []
    for i, (ts, pct) in enumerate(raw_points):
        if pct <= 0.0 and 0 < i < len(raw_points) - 1:
            prev_pct = raw_points[i - 1][1]
            next_pct = raw_points[i + 1][1]
            if prev_pct > 5.0 and next_pct > 5.0:
                continue
        filtered_points.append((ts, pct))

    # Reset-Erkennung: Falls innerhalb des Zeitfensters ein Session-Reset stattfand
    # (z.B. starker Drop oder Datenpunkte, die über der aktuellen Auslastung liegen),
    # gehören vorangehende Datenpunkte zur alten Session vor dem Reset.
    # Ein echter Reset nullt den Zähler (zweistelliger Prozent-Drop); kleinere
    # Schwankungen sind API-Rauschen (±wenige %) und dürfen keinen Reset auslösen.
    reset_drop_threshold = 10.0
    reset_idx = 0
    for i in range(len(filtered_points) - 1):
        prev_pct = filtered_points[i][1]
        next_pct = filtered_points[i + 1][1]
        if (prev_pct - next_pct >= reset_drop_threshold) or (prev_pct > util_pct + 2.0):
            reset_idx = i + 1

    while reset_idx < len(filtered_points) and filtered_points[reset_idx][1] > util_pct + 2.0:
        reset_idx += 1

    valid_points = filtered_points[reset_idx:]

    buckets: Dict[int, List[Tuple[float, float]]] = {}
    for ts, pct in valid_points:
        b_idx = int((ts - window_start) // bucket_sec)
        buckets.setdefault(b_idx, []).append((ts, pct))

    # Build smoothed usage points and linear regression input
    points: List[Tuple[float, float, float]] = []
    usage_series: List[Dict[str, float]] = []
    first_dt: Optional[datetime] = None
    is_weekly = window_hours > 5.0

    # Für wöchentliche Fenster (> 5h) den Zyklusstart bei x=0.0 mit 0.0% verankern
    if is_weekly:
        first_b_idx = min(buckets.keys()) if buckets else 0
        if first_b_idx > 0 or not buckets:
            points.append((0.0, 0.0, window_start))
            usage_series.append({"x": 0.0, "y": 0.0})

    running_usage_y = 0.0
    for b_idx in sorted(buckets.keys()):
        items = buckets[b_idx]
        median_y = round(float(median([it[1] for it in items])), 1)
        latest_ts = items[-1][0]

        # Monotonie: innerhalb des Zyklus nach Reset fängt max() Rundungs- und API-Jitter ab
        median_y = max(running_usage_y, median_y)
        running_usage_y = median_y

        if is_weekly:
            elapsed_h = (latest_ts - window_start) / 3600.0
        else:
            if first_dt is None:
                first_dt = datetime.fromtimestamp(latest_ts, tz=timezone.utc)
            elapsed_h = (latest_ts - first_dt.timestamp()) / 3600.0

        points.append((elapsed_h, median_y, latest_ts))

        norm_x = (latest_ts - window_start) / (window_hours * 3600.0)
        norm_x_clamped = max(0.0, min(1.0, round(norm_x, 4)))
        if usage_series and usage_series[-1]["x"] == norm_x_clamped:
            usage_series[-1]["y"] = median_y
        else:
            usage_series.append({
                "x": norm_x_clamped,
                "y": median_y,
            })

    # Normalized coordinates (0.0 to 1.0) for QML Canvas rendering
    elapsed_hours = (current_time.timestamp() - window_start) / 3600.0
    now_norm_x = max(0.0, min(1.0, round(elapsed_hours / window_hours, 4)))

    curr_usage_y = max(running_usage_y, round(util_pct, 1)) if usage_series else round(util_pct, 1)
    if not usage_series:
        usage_series.append({"x": now_norm_x, "y": curr_usage_y})
    elif usage_series[-1]["x"] < now_norm_x:
        usage_series.append({"x": now_norm_x, "y": curr_usage_y})
    else:
        usage_series[-1]["y"] = curr_usage_y

    # Calculate slope (burn rate in %/h) via sliding recent window
    if is_active:
        if max_lookback_hours is not None:
            burn_pct_per_hour = calculate_burn_rate_linear_regression(
                [(p[0], p[1]) for p in points],
                window_hours=window_hours,
                max_lookback_hours=max_lookback_hours,
            )
        else:
            burn_pct_per_hour = calculate_recent_burn_rate(
                points, current_time.timestamp(), window_hours
            )
    else:
        burn_pct_per_hour = 0.0

    # Budget pace (target progress)
    pace = calculate_budget_pace(resets_at, window_hours, current_time)

    # Dynamic consumption trend classification
    if not is_active:
        trend = "idle"
    elif burn_pct_per_hour < 5.0:
        trend = "low"
    elif burn_pct_per_hour < 15.0:
        trend = "moderate"
    elif burn_pct_per_hour < 30.0:
        trend = "high"
    else:
        trend = "critical"

    remaining_pct = max(0.0, 100.0 - util_pct)

    # Projected time remaining until 100% exhaustion
    eta_minutes: Optional[int] = None
    if is_active and burn_pct_per_hour > 0:
        eta_minutes = int((remaining_pct / burn_pct_per_hour) * 60.0)

    resets_in_minutes = max(0, int((resets_at - current_time).total_seconds() / 60.0))

    # Verbrauch gegen Soll-Tempo vergleichen (mit 5% Puffer). "Über Budget" aber erst ab einem
    # absoluten Mindestverbrauch und Mindest-Zeitfortschritt, um Fehlalarme kurz nach dem Reset
    # zu vermeiden (dann ist pace ~0 und jede kleine Nutzung läge sonst über dem Soll).
    current_ratio = util_pct / 100.0
    ahead_of_pace = (
        current_ratio > pace + 0.05
        and util_pct >= AHEAD_OF_PACE_MIN_UTILIZATION_PCT
        and pace >= AHEAD_OF_PACE_MIN_PACE
    )
    if ahead_of_pace:
        pace_status = "ahead_of_pace"
    elif current_ratio < pace - 0.05:
        pace_status = "behind_pace"
    else:
        pace_status = "on_pace"

    # Check whether 100% is reached before reset
    hits_100 = False
    if eta_minutes is not None and resets_in_minutes > 0:
        hits_100 = eta_minutes < resets_in_minutes


    # Projection line from current timestamp to exhaustion or window end
    now_norm_x = max(0.0, min(1.0, elapsed_hours / window_hours))
    projection_series: List[Dict[str, float]] = [{"x": round(now_norm_x, 4), "y": round(util_pct, 1)}]

    if burn_pct_per_hour > 0 and util_pct < 100.0:
        remaining_hours = (resets_at - current_time).total_seconds() / 3600.0
        hours_to_100 = (100.0 - util_pct) / burn_pct_per_hour
        if hours_to_100 < remaining_hours:
            hit_norm_x = (elapsed_hours + hours_to_100) / window_hours
            projection_series.append({"x": max(0.0, min(1.0, round(hit_norm_x, 4))), "y": 100.0})
        else:
            projected_y = util_pct + (burn_pct_per_hour * remaining_hours)
            projection_series.append({"x": 1.0, "y": round(min(100.0, projected_y), 1)})
    else:
        projection_series.append({"x": 1.0, "y": round(util_pct, 1)})

    charts_dict: Dict[str, Any] = {
        "7d": {
            "elapsed_ratio": round(now_norm_x, 4),
            "usage": usage_series,
            "projection": projection_series,
            "label_start": "Start",
            "label_end": "Reset",
        },
        "24h": calculate_lookback_chart(records, limit_type, current_time, 24.0, util_pct),
        "7h": calculate_lookback_chart(records, limit_type, current_time, 7.0, util_pct),
    }

    return {
        "utilization": round(util_pct, 1),
        "budget_pace": round(pace * 100.0, 1),
        "pace_status": pace_status,
        "burn_rate_pct_per_hour": round(burn_pct_per_hour, 2),
        "trend": trend,
        "is_active": is_active,
        "estimated_minutes_to_100": eta_minutes,
        "resets_in_minutes": resets_in_minutes,
        "resets_at_iso": resets_at.isoformat(),
        "hits_100_before_reset": hits_100,
        "chart": {
            "elapsed_ratio": round(now_norm_x, 4),
            "usage": usage_series,
            "projection": projection_series,
        },
        "charts": charts_dict,
    }
