# Plan: Watchdog Service

**Ref:** SPEC.md §6.2, §4, §5, §8 (inter-service communication), §9 (error handling)
**Output:** Polling service that reads log file, detects spikes, fires HTTP alerts
**Dependency:** `shared/` complete; Webhook Receiver running (for integration test)

---

## Step 1 — Skeleton

**`watchdog/__init__.py`** — empty

**`watchdog/reader.py`**
- Define class `LogFileReader`:
  - `__init__(self, log_dir: str)` → `pass`
  - `get_current_file_path(self) -> str` → `return ""`
  - `read_new_lines(self) -> list[dict]` → `return []`

**`watchdog/detector.py`**
- Define class `SpikeDetector`:
  - `__init__(self, window_seconds: int, error_threshold: int, critical_threshold: int)` → `pass`
  - `evaluate(self, session, now: datetime) -> dict | None` → `return None`

**`watchdog/notifier.py`**
- Define function `send_alert(webhook_url: str, payload: dict) -> bool` → `return False`

**`watchdog/main.py`**
- Load env vars with python-dotenv
- Define `run()` → `pass`
- Add `if __name__ == "__main__": run()` block

Verify: `python -m watchdog.main` exits cleanly.

---

## Step 2 — Implement `LogFileReader` (`reader.py`)

Purpose: Track position in today's log file; return only new lines since last read.

Instructions:
- `__init__`: store `log_dir`. Initialize `_current_file_path: str = ""` and `_offset: int = 0`
- `get_current_file_path()`: compute `{log_dir}/{YYYY-MM-DD}.log` using UTC date. If date changed since last call (new day), reset `_offset = 0` and update `_current_file_path`. Return path.
- `read_new_lines()`:
  1. Get current file path via `get_current_file_path()`
  2. If file does not exist: return `[]`
  3. Open file, seek to `self._offset`
  4. Read remaining lines; update `self._offset = file.tell()` after reading
  5. For each line: strip whitespace, skip empty; attempt `json.loads(line)` — on `JSONDecodeError` print warning to stdout and skip
  6. Return list of successfully parsed dicts

Key consideration: file is appended to by another process. Never assume a line is complete — if the last line has no `\n`, skip it (partial write). Track offset before any partial line.

---

## Step 3 — Implement `SpikeDetector` (`detector.py`)

Purpose: Query recent `log_entries` from DB and decide if a threshold is breached.

Instructions:
- `__init__`: store `window_seconds`, `error_threshold`, `critical_threshold`. Initialize `_last_alert_time: datetime | None = None`.
- `evaluate(session, now)`:
  1. Compute window start: `now - timedelta(seconds=self.window_seconds)`
  2. Query `log_entries` where `timestamp >= window_start` AND `level IN ('ERROR', 'CRITICAL')`
  3. If result count == 0: return `None`
  4. Check cooldown: if `_last_alert_time` is set and `(now - _last_alert_time).total_seconds() < window_seconds`: return `None` (still in cooldown)
  5. Determine severity:
     - count >= `critical_threshold` → `"CRITICAL"`
     - count >= `error_threshold` → `"HIGH"`
     - else → return `None`
  6. Find dominant service: group results by `service`, pick service with most errors
  7. Build and return alert payload dict matching SPEC §6.2 schema
  8. Update `self._last_alert_time = now`

Return `None` when no alert, return payload dict when alert should fire.

---

## Step 4 — Implement `send_alert` (`notifier.py`)

Instructions:
- Use `httpx` (sync client for simplicity in MVP)
- POST `payload` as JSON to `webhook_url`
- Set timeout of 5 seconds
- On success (2xx): print "Alert sent: {severity}" to stdout, return `True`
- On `httpx.ConnectError` or `httpx.TimeoutException`: print error to stdout, retry once after 1 second, return `False` if retry also fails
- On non-2xx response: print status code + response body to stdout, return `False`
- Do not raise exceptions — always return bool

---

## Step 5 — Implement `main.py` poll loop

Instructions:
- Load all env vars: `DB_PATH`, `LOG_DIR`, `WATCHDOG_POLL_INTERVAL_SECONDS`, `ROLLING_WINDOW_SECONDS`, `ERROR_THRESHOLD`, `CRITICAL_THRESHOLD`, `WEBHOOK_URL`
- On startup: call `init_db(engine)` to ensure tables exist
- Instantiate `LogFileReader(LOG_DIR)` and `SpikeDetector(...)` once
- Loop forever:
  1. `now = datetime.utcnow()`
  2. `new_lines = reader.read_new_lines()`
  3. If `new_lines`: open DB session, bulk-insert as `LogEntry` rows, commit
     - Parse `timestamp` field from each line's string → `datetime` object before inserting
     - On parse error for a line: skip that line, log warning
  4. `alert_payload = detector.evaluate(session, now)`
  5. If `alert_payload`: call `send_alert(WEBHOOK_URL, alert_payload)`
  6. `time.sleep(WATCHDOG_POLL_INTERVAL_SECONDS)`
- Wrap in `try/except KeyboardInterrupt` → "Watchdog stopped." + exit cleanly
- DB errors in loop: print to stderr, continue loop

---

## Step 6 — Integration Test

Requires: Log Generator running, Webhook Receiver running.

1. Start Webhook Receiver (`python -m webhook_receiver.main`)
2. Start Log Generator (`python -m log_generator.main`) with short interval (0.2s)
3. Start Watchdog with low thresholds for testing:
   ```
   ERROR_THRESHOLD=3
   CRITICAL_THRESHOLD=6
   ROLLING_WINDOW_SECONDS=30
   WATCHDOG_POLL_INTERVAL_SECONDS=5
   ```
4. Within ~30 seconds: verify Watchdog stdout shows "Alert sent"
5. Verify `GET http://localhost:8001/alerts` returns at least 1 alert
6. Verify `data/watchdog.db` contains rows in both `log_entries` and `alerts` tables

---

## Checklist

- [ ] Step 1: All stubs import cleanly
- [ ] Step 2: Reader skips partial lines; returns only new lines on each call; resets on new day
- [ ] Step 3: Detector respects cooldown; never double-alerts in same window; identifies dominant service
- [ ] Step 4: send_alert retries once on connection error; never raises
- [ ] Step 5: log entries persisted to DB each poll; alert fires when threshold breached
- [ ] Step 6: Full stack integration produces alert in DB within ~60s
