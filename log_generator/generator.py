import json
import os
import random
import uuid
from datetime import UTC, datetime

_LEVEL_WEIGHTS = [
    ("INFO", 55),
    ("WARNING", 25),
    ("ERROR", 16),
    ("CRITICAL", 4),
]
_LEVELS = [lw[0] for lw in _LEVEL_WEIGHTS]
_WEIGHTS = [lw[1] for lw in _LEVEL_WEIGHTS]

_MESSAGES = {
    "INFO": [
        "Request processed successfully",
        "User session started",
        "Scheduled job completed",
        "Cache refreshed",
        "Health check passed",
        "Config reloaded",
        "Connection pool initialized",
    ],
    "WARNING": [
        "High memory usage detected",
        "Slow response time on endpoint",
        "Retry attempt on downstream service",
        "Queue backlog growing",
        "Cache miss rate above threshold",
    ],
    "ERROR": [
        "Unhandled exception in request handler",
        "Database connection timeout",
        "Failed to parse request payload",
        "Downstream service returned 503",
        "Null pointer in data pipeline",
    ],
    "CRITICAL": [
        "Service is unresponsive",
        "Database cluster unreachable",
        "Out of memory — process killed",
        "Disk quota exceeded",
        "Security violation detected",
    ],
}

_ERROR_CODES = {
    "INFO": [200, 201, 204],
    "WARNING": [429, 408, 409],
    "ERROR": [500, 502, 503, 504],
    "CRITICAL": [500, 503],
}


def build_log_entry(service_names: list[str]) -> dict:
    level = random.choices(_LEVELS, weights=_WEIGHTS, k=1)[0]
    service = random.choice(service_names)
    message = random.choice(_MESSAGES[level])
    error_code = random.choice(_ERROR_CODES[level])
    return {
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "level": level,
        "service": service,
        "message": message,
        "metadata": {
            "request_id": uuid.uuid4().hex[:12],
            "error_code": error_code,
        },
    }


def get_log_file_path(log_dir: str) -> str:
    os.makedirs(log_dir, exist_ok=True)
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    return os.path.join(log_dir, f"{date_str}.log")


def write_log_entry(file_path: str, entry: dict) -> None:
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
