from datetime import UTC, datetime, timedelta

from sqlalchemy import func

from shared.models import Alert, LogEntry

_ERROR_LEVELS = {"ERROR", "CRITICAL"}
_CHART_LEVELS = {"WARNING", "ERROR", "CRITICAL"}


def get_stats(session, lookback_hours: int) -> dict:
    total_logs = session.query(func.count(LogEntry.id)).scalar() or 0
    total_alerts = session.query(func.count(Alert.id)).scalar() or 0

    cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)
    alerts_recent = (
        session.query(func.count(Alert.id))
        .filter(Alert.created_at >= cutoff)
        .scalar()
        or 0
    )

    one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    recent_total = (
        session.query(func.count(LogEntry.id))
        .filter(LogEntry.timestamp >= one_hour_ago)
        .scalar()
        or 0
    )
    recent_errors = (
        session.query(func.count(LogEntry.id))
        .filter(
            LogEntry.timestamp >= one_hour_ago,
            LogEntry.level.in_(_ERROR_LEVELS),
        )
        .scalar()
        or 0
    )
    error_rate = round(recent_errors / recent_total * 100, 1) if recent_total > 0 else 0.0

    return {
        "total_logs_processed": total_logs,
        "total_alerts": total_alerts,
        "alerts_last_x_hours": alerts_recent,
        "current_error_rate_pct": error_rate,
        "lookback_hours": lookback_hours,
    }


def get_error_rate_series(session) -> list:
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=1)

    rows = (
        session.query(LogEntry)
        .filter(
            LogEntry.timestamp >= cutoff,
            LogEntry.level.in_(_CHART_LEVELS),
        )
        .all()
    )

    buckets: dict[str, dict] = {}
    for i in range(60):
        t = (cutoff + timedelta(minutes=i)).replace(second=0, microsecond=0)
        key = t.strftime("%Y-%m-%dT%H:%M:00")
        buckets[key] = {"bucket_time": key, "warning_count": 0, "error_count": 0, "critical_count": 0}

    for row in rows:
        key = row.timestamp.strftime("%Y-%m-%dT%H:%M:00")
        if key not in buckets:
            continue
        if row.level == "WARNING":
            buckets[key]["warning_count"] += 1
        elif row.level == "ERROR":
            buckets[key]["error_count"] += 1
        elif row.level == "CRITICAL":
            buckets[key]["critical_count"] += 1

    return list(buckets.values())


def get_recent_alerts(session, limit: int = 50) -> list:
    rows = (
        session.query(Alert)
        .order_by(Alert.timestamp.desc())
        .limit(limit)
        .all()
    )
    result = []
    for row in rows:
        ts = row.timestamp.isoformat() if row.timestamp else None
        if ts and not ts.endswith("Z") and "+" not in ts:
            ts += "Z"
        result.append(
            {
                "id": row.id,
                "timestamp": ts,
                "severity": row.severity,
                "message": row.message,
                "error_count": row.error_count,
                "threshold": row.threshold,
                "window_seconds": row.window_seconds,
                "source_service": row.source_service,
                "ai_classification": row.ai_classification,
                "ai_root_cause": row.ai_root_cause,
                "ai_recommendation": row.ai_recommendation,
            }
        )
    return result
