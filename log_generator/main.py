import os
import random
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from log_generator.generator import build_log_entry, get_log_file_path, write_log_entry


def run() -> None:
    log_dir = os.getenv("LOG_DIR", "./logs")
    max_interval = float(os.getenv("MAX_TIME_BETWEEN_LOGS", "2"))
    raw_services = os.getenv("LOG_SERVICE_NAMES", "api,worker,scheduler,db")
    service_names = [s.strip() for s in raw_services.split(",") if s.strip()]

    print(f"[log_generator] Starting — max_interval={max_interval}s services={service_names}")

    try:
        while True:
            try:
                file_path = get_log_file_path(log_dir)
                entry = build_log_entry(service_names)
                write_log_entry(file_path, entry)
                print(f"[{entry['timestamp']}] {entry['level']:8s} {entry['service']:12s} {entry['message']}")
            except Exception as exc:
                print(f"[log_generator] ERROR: {exc}", file=sys.stderr)
                time.sleep(5)
                continue
            time.sleep(random.uniform(0, max_interval))
    except KeyboardInterrupt:
        print("\n[log_generator] Stopped.")


if __name__ == "__main__":
    run()
