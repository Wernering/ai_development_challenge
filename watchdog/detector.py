from collections import Counter
from datetime import UTC, datetime, timedelta

from shared.models import LogEntry

_SPIKE_LEVELS = {"ERROR", "CRITICAL"}


class SpikeDetector:
    def __init__(self, window_seconds: int, error_threshold: int, critical_threshold: int) -> None:
        self._window_seconds = window_seconds
        self._error_threshold = error_threshold
        self._critical_threshold = critical_threshold
        self._last_alert_time: datetime | None = None

    def evaluate(self, session, now: datetime) -> tuple[dict, list] | None:
        window_start = now - timedelta(seconds=self._window_seconds)

        rows = (
            session.query(LogEntry)
            .filter(
                LogEntry.timestamp >= window_start,
                LogEntry.level.in_(_SPIKE_LEVELS),
            )
            .all()
        )

        count = len(rows)
        if count == 0:
            return None

        # Cooldown: skip if last alert is still within the window
        if self._last_alert_time is not None:
            elapsed = (now - self._last_alert_time).total_seconds()
            if elapsed < self._window_seconds:
                return None

        if count >= self._critical_threshold:
            severity = "CRITICAL"
        elif count >= self._error_threshold:
            severity = "HIGH"
        else:
            return None

        service_counts = Counter(r.service for r in rows)
        dominant_service = service_counts.most_common(1)[0][0]

        self._last_alert_time = now

        payload = {
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "severity": severity,
            "message": f"Error spike detected: {count} errors in {self._window_seconds}s window",
            "error_count": count,
            "threshold": self._error_threshold if severity == "HIGH" else self._critical_threshold,
            "window_seconds": self._window_seconds,
            "source_service": dominant_service,
        }
        return payload, rows
