# Intelligent Observability & Event Watchdog — MVP Specification

**Version:** 1.0 (MVP)
**Date:** 2026-05-18
**Scope:** Detect anomalies/spikes in application logs using statistical thresholds, trigger simulated webhook alerts, and visualize health trends.

---

## 1. Goals

- Parse JSON-structured application logs for WARNING / ERROR / CRITICAL entries
- Detect error spikes using rolling-window statistical thresholds
- Fire HTTP-based webhook alerts when thresholds are breached
- Persist log entries and alerts in SQLite
- Visualize error-rate trends and alert history via a lightweight dashboard

**Out of scope (v1):** LLM/ML anomaly interpretation, DEBUG/INFO log levels, authentication, Docker orchestration, realistic traffic simulation.

---

## 2. Technology Stack

| Layer           | Technology                        |
|-----------------|-----------------------------------|
| Language        | Python 3.11+                      |
| API Framework   | FastAPI                           |
| Database        | SQLite (via SQLAlchemy)           |
| Dashboard UI    | FastAPI + Jinja2 HTML templates   |
| Config          | python-dotenv (.env file)         |
| HTTP Client     | httpx (async)                     |
| Scheduling      | asyncio + custom polling loop     |

---

## 3. System Architecture

```
┌─────────────────┐       writes JSON       ┌──────────────────┐
│  Log Generator  │ ───────────────────────▶│  logs/YYYY-MM-DD │
│  (Terminal 1)   │       to date file       │  .log (file)     │
└─────────────────┘                          └────────┬─────────┘
                                                      │ reads (poll)
                                                      ▼
                                             ┌─────────────────┐
                                             │ Watchdog Service │
                                             │  (Terminal 2)   │
                                             │                 │
                                             │ rolling-window  │
                                             │ threshold check │
                                             └────────┬────────┘
                                                      │ HTTP POST on breach
                                                      ▼
                                             ┌─────────────────┐
                                             │ Webhook Receiver │
                                             │  (Terminal 3)   │◀── alerts saved
                                             │  FastAPI :8001  │    to SQLite
                                             └─────────────────┘
                                                      │ SQLite shared
                                                      ▼
                                             ┌─────────────────┐
                                             │   Dashboard     │
                                             │  (Terminal 4)   │
                                             │  FastAPI :8002  │
                                             └─────────────────┘
```

**Shared resource:** Single SQLite file at `data/watchdog.db`.
- Watchdog writes parsed log entries → `log_entries` table
- Webhook Receiver writes triggered alerts → `alerts` table
- Dashboard reads both tables

---

## 4. Database Schema

### Table: `log_entries`
Populated by **Watchdog** as it processes the log file.

| Column       | Type     | Notes                              |
|--------------|----------|------------------------------------|
| id           | INTEGER  | Primary key, auto-increment        |
| timestamp    | DATETIME | Parsed from log entry              |
| level        | TEXT     | WARNING / ERROR / CRITICAL         |
| service      | TEXT     | Source service name from log       |
| message      | TEXT     | Log message text                   |
| metadata     | TEXT     | Raw JSON string of extra fields    |
| created_at   | DATETIME | UTC insert time                    |

### Table: `alerts`
Populated by **Webhook Receiver** on each received alert.

| Column           | Type     | Notes                              |
|------------------|----------|------------------------------------|
| id               | INTEGER  | Primary key, auto-increment        |
| timestamp        | DATETIME | Time the spike was detected        |
| severity         | TEXT     | HIGH / CRITICAL                    |
| message          | TEXT     | Human-readable alert description   |
| error_count      | INTEGER  | Errors counted in the window       |
| threshold        | INTEGER  | Configured threshold value         |
| window_seconds   | INTEGER  | Rolling window size used           |
| source_service   | TEXT     | Service name where spike occurred  |
| created_at       | DATETIME | UTC insert time                    |

---

## 5. Configuration (.env)

All services read from a shared `.env` at `ai_development_challenge/.env`.

```env
# ── Shared ──────────────────────────────
DB_PATH=./data/watchdog.db
LOG_DIR=./logs

# ── Log Generator ───────────────────────
MAX_TIME_BETWEEN_LOGS=2         # Upper bound (s) of uniform(0, MAX) sleep between entries
LOG_SERVICE_NAMES=api,worker,scheduler,db  # Comma-separated simulated services

# ── Watchdog ────────────────────────────
WATCHDOG_POLL_INTERVAL_SECONDS=10   # How often watchdog checks log file
ROLLING_WINDOW_SECONDS=60           # Rolling window for spike detection
ERROR_THRESHOLD=5                   # Errors in window to trigger HIGH alert
CRITICAL_THRESHOLD=10               # Errors in window to trigger CRITICAL alert
WEBHOOK_URL=http://localhost:8001/webhook/alert

# ── Webhook Receiver ────────────────────
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8001

# ── Dashboard ───────────────────────────
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8002
ALERT_LOOKBACK_HOURS=24        # "X" in "alerts in last X hours" KPI
```

---

## 6. Component Specifications

### 6.1 Log Generator (`log_generator/`)

**Purpose:** Produce a continuous stream of random JSON log entries into a date-stamped file.

**Behavior:**
- Runs indefinitely, emitting one log entry every `random.uniform(0, MAX_TIME_BETWEEN_LOGS)` seconds
- Log file path: `{LOG_DIR}/{YYYY-MM-DD}.log` — one file per calendar day, new file on midnight rollover
- Each log entry is one JSON object per line (NDJSON / JSON Lines format)
- Log level distribution (random, weighted): INFO 55%, WARNING 25%, ERROR 16%, CRITICAL 4%
- Service name picked randomly from `LOG_SERVICE_NAMES`

**Log Entry JSON Schema:**
```json
{
  "timestamp": "2026-05-18T14:32:01.123456Z",
  "level": "ERROR",
  "service": "api",
  "message": "Unhandled exception in request handler",
  "metadata": {
    "request_id": "abc-123",
    "error_code": 500
  }
}
```

**Key behaviors:**
- Graceful shutdown on SIGINT/SIGTERM
- Creates `LOG_DIR` if it does not exist
- No DB interaction — file only

---

### 6.2 Watchdog Service (`watchdog/`)

**Purpose:** Continuously monitor the log file for error spikes and fire HTTP alerts.

**Startup validation (exits with error if any fail):**
- `WATCHDOG_POLL_INTERVAL_SECONDS` > 0
- `ROLLING_WINDOW_SECONDS` > `WATCHDOG_POLL_INTERVAL_SECONDS` — window must exceed poll interval to guarantee full log coverage (no gaps between polls)
- `ERROR_THRESHOLD` > 0
- `CRITICAL_THRESHOLD` > `ERROR_THRESHOLD`

**Behavior:**
- On startup: determine today's log file path; open at last known offset (or start of file)
- Every `WATCHDOG_POLL_INTERVAL_SECONDS`: read new lines, parse JSON entries, persist to `log_entries` table
- Maintain rolling window: count ERROR + CRITICAL entries whose `timestamp` falls within last `ROLLING_WINDOW_SECONDS` — because the window is always wider than the poll interval, consecutive polls always overlap, eliminating coverage gaps
- After each poll, evaluate threshold:
  - `error_count >= CRITICAL_THRESHOLD` → severity = CRITICAL
  - `error_count >= ERROR_THRESHOLD` → severity = HIGH
  - Below threshold → no alert
- On threshold breach: POST alert payload to `WEBHOOK_URL`
- Alert cooldown: do not re-alert for the same breach window (track last alert timestamp to prevent spam — cooldown = `ROLLING_WINDOW_SECONDS`)
- Handles midnight log file rollover (switches to new date file)
- Graceful shutdown on SIGINT/SIGTERM

**Alert Payload (HTTP POST body):**
```json
{
  "timestamp": "2026-05-18T14:32:01Z",
  "severity": "HIGH",
  "message": "Error spike detected: 7 errors in 60s window",
  "error_count": 7,
  "threshold": 5,
  "window_seconds": 60,
  "source_service": "api"
}
```

**Source service in alert:** service name with highest error count in the window.

---

### 6.3 Webhook Receiver (`webhook_receiver/`)

**Purpose:** Accept inbound alert POSTs, persist to DB, expose read endpoints.

**FastAPI Endpoints:**

| Method | Path              | Description                        |
|--------|-------------------|------------------------------------|
| POST   | `/webhook/alert`  | Receive and store an alert         |
| GET    | `/alerts`         | List alerts (supports `?limit=N`)  |
| GET    | `/health`         | Returns `{"status": "ok"}`         |

**POST `/webhook/alert` request body:** Alert Payload schema (see 6.2).
**POST `/webhook/alert` response:** `201 Created` + stored alert as JSON.

**Validation:**
- `severity` must be HIGH or CRITICAL — reject with 422 otherwise
- `timestamp` must be valid ISO datetime
- `error_count` and `threshold` must be positive integers

---

### 6.4 Dashboard (`dashboard/`)

**Purpose:** Display health KPIs and alert history from SQLite.

**FastAPI Endpoints:**

| Method | Path              | Description                          |
|--------|-------------------|--------------------------------------|
| GET    | `/`               | Serve main dashboard HTML            |
| GET    | `/api/stats`      | KPI summary (JSON)                   |
| GET    | `/api/error-rate` | Error rate over time series (JSON)   |
| GET    | `/api/alerts`     | Recent alert history (JSON)          |

**`/api/stats` response shape:**
```json
{
  "total_logs_processed": 1420,
  "total_alerts": 12,
  "alerts_last_x_hours": 3,
  "current_error_rate_pct": 18.5,
  "lookback_hours": 24
}
```

**`/api/error-rate` response shape:**
Array of `{bucket_time, error_count, warning_count, critical_count}` bucketed by minute (last 60 min).

**`/api/alerts` response shape:**
Array of alert rows ordered by `timestamp DESC`, limit 50.

**Dashboard HTML (`templates/index.html`):**
- Single-page, no JS framework — plain HTML + vanilla JS `fetch()`
- Auto-refreshes every 30 seconds via `setInterval`
- Sections:
  1. **KPI cards** — total logs, total alerts, alerts in last X hours, current error %
  2. **Error rate chart** — inline SVG or `<canvas>` bar/line chart (vanilla JS)
  3. **Alert history table** — severity, timestamp, message, error count, service

---

## 7. Directory Structure

```
ai_development_challenge/
├── log_generator/
│   ├── __init__.py
│   ├── main.py          # Entry point, env loading, loop
│   └── generator.py     # Log entry creation + file writer
├── watchdog/
│   ├── __init__.py
│   ├── main.py          # Entry point, env loading, poll loop
│   ├── reader.py        # File tail / offset tracking
│   ├── detector.py      # Rolling window + threshold logic
│   └── notifier.py      # HTTP POST to webhook
├── webhook_receiver/
│   ├── __init__.py
│   ├── main.py          # FastAPI app entry point
│   ├── models.py        # Pydantic request/response models
│   ├── database.py      # SQLAlchemy setup + alert CRUD
│   └── routes.py        # FastAPI route handlers
├── dashboard/
│   ├── __init__.py
│   ├── main.py          # FastAPI app entry point
│   ├── queries.py       # SQLite read queries
│   └── templates/
│       └── index.html   # Single-page dashboard
├── shared/
│   ├── __init__.py
│   ├── database.py      # SQLAlchemy engine + session factory
│   └── models.py        # SQLAlchemy ORM models (log_entries, alerts)
├── data/                # SQLite DB lives here (git-ignored)
├── logs/                # Generated log files (git-ignored)
├── .env                 # Local config (git-ignored)
├── .env.example         # Template with all keys, no values
├── requirements.txt
├── SPEC.md
└── prompts.md
```

---

## 8. Inter-Service Communication

| From       | To               | Protocol    | Trigger                      |
|------------|------------------|-------------|------------------------------|
| Watchdog   | Webhook Receiver | HTTP POST   | Threshold breach detected    |
| Dashboard  | SQLite           | Direct read | Every API request            |
| Watchdog   | SQLite           | Direct write| Every poll cycle             |
| Webhook Rx | SQLite           | Direct write| Every received alert         |

No message queue in MVP. All HTTP calls are fire-and-forget with basic retry (1 retry on connection error).

---

## 9. Error Handling Principles

- Each service logs its own operational errors to stdout (not to the log file it monitors)
- Failed webhook POST: log error, continue watchdog loop — do not crash
- Malformed log line in file: skip line, log warning to stdout, continue
- DB write failure: log error, continue — do not crash service
- Dashboard DB read failure: return empty data with HTTP 200 (UI shows "no data")

---

## 10. MVP Acceptance Criteria

1. Log Generator produces valid JSON entries to dated file continuously
2. Watchdog detects a spike (inject burst of errors) and sends HTTP alert within 2x poll interval
3. Webhook Receiver stores alert and returns 201
4. Dashboard displays correct alert count and non-empty error-rate chart
5. All four services run simultaneously without crashing
6. Stopping one service does not crash others
