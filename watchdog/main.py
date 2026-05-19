import json
import os
import sys
import time
from datetime import UTC, datetime

from dotenv import load_dotenv

load_dotenv()

from shared.database import get_db, get_engine, get_session_factory, init_db
from shared.models import LogEntry
from watchdog.analyzer import analyze_spike
from watchdog.detector import SpikeDetector
from watchdog.notifier import send_alert
from watchdog.reader import LogFileReader


def _load_and_validate_config() -> dict:
    errors = []

    def _pos_int(name: str, default: str) -> int:
        raw = os.getenv(name, default)
        try:
            v = int(raw)
            if v <= 0:
                errors.append(f"{name} must be > 0 (got {raw!r})")
            return v
        except ValueError:
            errors.append(f"{name} must be an integer (got {raw!r})")
            return 0

    cfg = {
        "db_path": os.getenv("DB_PATH", "./data/watchdog.db"),
        "log_dir": os.getenv("LOG_DIR", "./logs"),
        "poll_interval": _pos_int("WATCHDOG_POLL_INTERVAL_SECONDS", "5"),
        "window_seconds": _pos_int("ROLLING_WINDOW_SECONDS", "30"),
        "error_threshold": _pos_int("ERROR_THRESHOLD", "5"),
        "critical_threshold": _pos_int("CRITICAL_THRESHOLD", "10"),
        "webhook_url": os.getenv("WEBHOOK_URL", "http://localhost:8001/webhook/alert"),
    }

    if cfg["window_seconds"] <= cfg["poll_interval"]:
        errors.append(
            f"ROLLING_WINDOW_SECONDS ({cfg['window_seconds']}) must be > "
            f"WATCHDOG_POLL_INTERVAL_SECONDS ({cfg['poll_interval']}) "
            "to guarantee full log coverage between polls"
        )

    if cfg["critical_threshold"] <= cfg["error_threshold"]:
        errors.append(
            f"CRITICAL_THRESHOLD ({cfg['critical_threshold']}) must be > "
            f"ERROR_THRESHOLD ({cfg['error_threshold']})"
        )

    if errors:
        print("[watchdog] Configuration errors — cannot start:", file=sys.stderr)
        for e in errors:
            print(f"  • {e}", file=sys.stderr)
        sys.exit(1)

    return cfg


def _parse_timestamp(ts_str: str) -> datetime | None:
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(ts_str, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def run() -> None:
    cfg = _load_and_validate_config()

    print(
        f"[watchdog] Starting — poll={cfg['poll_interval']}s "
        f"window={cfg['window_seconds']}s "
        f"thresholds=HIGH≥{cfg['error_threshold']} CRITICAL≥{cfg['critical_threshold']}"
    )

    engine = get_engine(cfg["db_path"])
    init_db(engine)
    session_factory = get_session_factory(engine)

    reader = LogFileReader(cfg["log_dir"])
    detector = SpikeDetector(
        window_seconds=cfg["window_seconds"],
        error_threshold=cfg["error_threshold"],
        critical_threshold=cfg["critical_threshold"],
    )

    try:
        while True:
            now = datetime.now(UTC)
            new_lines = reader.read_new_lines()

            if new_lines:
                try:
                    with get_db(session_factory) as session:
                        for line in new_lines:
                            ts = _parse_timestamp(line.get("timestamp", ""))
                            if ts is None:
                                print(
                                    f"[watchdog] Skipping line with bad timestamp: {line.get('timestamp')!r}",
                                    file=sys.stderr,
                                )
                                continue
                            session.add(LogEntry(
                                timestamp=ts,
                                level=line.get("level", ""),
                                service=line.get("service", ""),
                                message=line.get("message", ""),
                                log_metadata=json.dumps(line.get("metadata", {})),
                            ))
                        print(f"[watchdog] Persisted {len(new_lines)} entries")
                except Exception as exc:
                    print(f"[watchdog] DB write error: {exc}", file=sys.stderr)

            try:
                with get_db(session_factory) as session:
                    result = detector.evaluate(session, now)
                if result:
                    alert_payload, spike_entries = result
                    ai = analyze_spike(alert_payload, spike_entries)
                    if ai:
                        alert_payload["ai_classification"] = ai.get("classification")
                        alert_payload["ai_root_cause"] = ai.get("root_cause")
                        alert_payload["ai_recommendation"] = ai.get("recommendation")
                        print(
                            f"[watchdog] AI: {ai.get('classification')} — {ai.get('root_cause')}"
                        )
                    send_alert(cfg["webhook_url"], alert_payload)
            except Exception as exc:
                print(f"[watchdog] Detector error: {exc}", file=sys.stderr)

            time.sleep(cfg["poll_interval"])

    except KeyboardInterrupt:
        print("\n[watchdog] Stopped.")


if __name__ == "__main__":
    run()
