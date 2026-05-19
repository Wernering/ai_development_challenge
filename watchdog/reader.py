import json
import os
import sys
from datetime import UTC, datetime


class LogFileReader:
    def __init__(self, log_dir: str) -> None:
        self._log_dir = log_dir
        self._current_file_path = ""
        self._offset = 0

    def get_current_file_path(self) -> str:
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        expected = os.path.join(self._log_dir, f"{date_str}.log")
        if expected != self._current_file_path:
            self._current_file_path = expected
            self._offset = 0
        return self._current_file_path

    def read_new_lines(self) -> list[dict]:
        file_path = self.get_current_file_path()
        if not os.path.exists(file_path):
            return []

        entries = []
        with open(file_path, "r", encoding="utf-8") as f:
            f.seek(self._offset)
            while True:
                line = f.readline()
                if not line:
                    break
                # Only advance offset on lines that end with newline (complete writes)
                if not line.endswith("\n"):
                    break
                self._offset = f.tell()
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    print(f"[watchdog/reader] Skipping malformed line: {exc}", file=sys.stderr)
        return entries
