# Intelligent Observability & Event Watchdog

SRE tool that monitors application logs for error spikes, fires webhook alerts, enriches alerts with Claude AI analysis, and visualizes trends in a live dashboard.

---

## Architecture

```
┌─────────────────┐  writes NDJSON   ┌──────────────────────┐
│  Log Generator  │ ────────────────▶│  logs/YYYY-MM-DD.log │
│  (Terminal 1)   │                  └──────────┬───────────┘
└─────────────────┘                             │ polls every N seconds
                                                ▼
                                     ┌─────────────────────┐
                                     │  Watchdog Service   │
                                     │  (Terminal 2)       │
                                     │                     │
                                     │  rolling-window     │
                                     │  spike detection    │
                                     │  + Claude AI        │
                                     └──────────┬──────────┘
                                                │ HTTP POST on breach
                                                ▼
                                     ┌─────────────────────┐
                                     │  Webhook Receiver   │
                                     │  (Terminal 3)       │◀── stores alerts
                                     │  FastAPI :8001      │    to SQLite
                                     └──────────┬──────────┘
                                                │ shared SQLite
                                                ▼
                                     ┌─────────────────────┐
                                     │    Dashboard        │
                                     │  (Terminal 4)       │
                                     │  FastAPI :8002      │
                                     └─────────────────────┘
```

All services share a single SQLite database (`data/watchdog.db`).

---

## Components

### 1. Log Generator (`log_generator/`)

Continuously writes random JSON log entries to a date-stamped file (`logs/YYYY-MM-DD.log`). One entry per line (NDJSON format). Sleep between entries is `random.uniform(0, MAX_TIME_BETWEEN_LOGS)`.

Level distribution: INFO 55% / WARNING 25% / ERROR 16% / CRITICAL 4%.

Rolls over to a new file at midnight. No database interaction.

### 2. Watchdog Service (`watchdog/`)

Polls the log file every `WATCHDOG_POLL_INTERVAL_SECONDS`, reads new lines, and persists parsed entries to the `log_entries` table.

After each poll it evaluates a rolling window of `ROLLING_WINDOW_SECONDS`: if ERROR + CRITICAL count in that window reaches `ERROR_THRESHOLD` it fires a HIGH alert; if it reaches `CRITICAL_THRESHOLD` it fires CRITICAL. A cooldown equal to `ROLLING_WINDOW_SECONDS` prevents duplicate alerts for the same spike.

On a breach, the watchdog optionally calls Claude (`claude-haiku-4-5`) to classify the spike, identify a likely root cause, and suggest a remediation step. These AI fields are included in the alert payload and stored alongside the alert. If `ANTHROPIC_API_KEY` is not set, the service runs normally without AI enrichment.

**Startup validation** — exits with a clear error if:
- `ROLLING_WINDOW_SECONDS` ≤ `WATCHDOG_POLL_INTERVAL_SECONDS`
- `CRITICAL_THRESHOLD` ≤ `ERROR_THRESHOLD`
- Any required numeric value ≤ 0

### 3. Webhook Receiver (`webhook_receiver/`)

FastAPI service on port 8001. Receives alert POSTs from the watchdog, validates them, and stores them in the `alerts` table.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhook/alert` | Receive and store alert (returns 201) |
| GET | `/alerts?limit=N` | List stored alerts |
| GET | `/health` | `{"status": "ok"}` |

Rejects alerts with invalid severity (not HIGH or CRITICAL) with 422.

### 4. Dashboard (`dashboard/`)

FastAPI service on port 8002. Reads from SQLite and serves a single-page HTML dashboard that auto-refreshes every 30 seconds.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Main dashboard HTML |
| GET | `/api/stats` | KPI summary (total logs, alerts, error rate) |
| GET | `/api/error-rate` | Per-minute error counts for last 60 min |
| GET | `/api/alerts` | Recent alert history (limit 50) |

Dashboard sections:
- **KPI cards** — total logs processed, total alerts, alerts in last X hours, current error rate %
- **Error rate chart** — 60-bucket canvas bar chart (green = clean, yellow = errors below threshold, red = spike at or above threshold, blue = warnings)
- **Alert table** — severity, timestamp, service, error count, message, AI classification, AI recommendation

---

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager

### Install dependencies

```bash
cd code
uv sync
```

### Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your values. At minimum, set `ANTHROPIC_API_KEY` if you want AI-enriched alerts (optional).

---

## Environment Variables

### Shared

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `./data/watchdog.db` | Path to the SQLite database file |
| `LOG_DIR` | `./logs` | Directory where log files are written |

### Log Generator

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_TIME_BETWEEN_LOGS` | `2` | Upper bound (seconds) of uniform sleep between log entries. Lower = faster generation |
| `LOG_SERVICE_NAMES` | `api,worker,scheduler,db` | Comma-separated list of simulated service names |

### Watchdog

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(empty)* | Anthropic API key for Claude AI spike analysis. Leave empty to disable AI enrichment |
| `AI_ANALYSIS_MAX_SAMPLES` | `20` | Max number of log entries sent to Claude per spike analysis. Higher = more context, higher token cost |
| `WATCHDOG_POLL_INTERVAL_SECONDS` | `5` | How often the watchdog reads new log lines. Must be less than `ROLLING_WINDOW_SECONDS` |
| `ROLLING_WINDOW_SECONDS` | `30` | Size of the rolling window used to count errors. Must be greater than `WATCHDOG_POLL_INTERVAL_SECONDS` |
| `ERROR_THRESHOLD` | `5` | Minimum error count in the window to trigger a HIGH alert |
| `CRITICAL_THRESHOLD` | `10` | Minimum error count in the window to trigger a CRITICAL alert. Must be greater than `ERROR_THRESHOLD` |
| `WEBHOOK_URL` | `http://localhost:8001/webhook/alert` | Endpoint the watchdog POSTs alerts to |

### Webhook Receiver

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBHOOK_HOST` | `0.0.0.0` | Host the webhook receiver binds to |
| `WEBHOOK_PORT` | `8001` | Port the webhook receiver listens on |

### Dashboard

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_HOST` | `0.0.0.0` | Host the dashboard binds to |
| `DASHBOARD_PORT` | `8002` | Port the dashboard listens on |
| `ALERT_LOOKBACK_HOURS` | `24` | Hours used for the "Alerts last X hours" KPI card |

---

## Running the System

Open four terminals, all from the `code/` directory.

**Terminal 1 — Log Generator**
```bash
uv run python -m log_generator.main
```

**Terminal 2 — Watchdog**
```bash
uv run python -m watchdog.main
```

**Terminal 3 — Webhook Receiver**
```bash
uv run python -m webhook_receiver.main
```

**Terminal 4 — Dashboard**
```bash
uv run python -m dashboard.main
```

Open **http://localhost:8002** in a browser.

### Triggering an alert manually

Lower the threshold in `.env` to force a spike quickly:

```env
ERROR_THRESHOLD=3
CRITICAL_THRESHOLD=6
MAX_TIME_BETWEEN_LOGS=0.5
```

Restart the log generator and watchdog. An alert should fire within one rolling window.

### Stopping

Each service shuts down cleanly on `Ctrl+C`. Stopping any one service does not crash the others.

---

## Project Structure

```
code/
├── log_generator/
│   ├── generator.py     # Log entry builder + file writer
│   └── main.py          # Entry point + poll loop
├── watchdog/
│   ├── reader.py        # File tail with offset tracking
│   ├── detector.py      # Rolling window + threshold logic
│   ├── notifier.py      # HTTP POST to webhook (1 retry)
│   ├── analyzer.py      # Claude AI spike analysis
│   └── main.py          # Entry point + poll loop
├── webhook_receiver/
│   ├── models.py        # Pydantic request/response models
│   ├── database.py      # Alert CRUD
│   ├── routes.py        # FastAPI route handlers
│   └── main.py          # FastAPI app entry point
├── dashboard/
│   ├── queries.py       # SQLite read queries
│   ├── main.py          # FastAPI app entry point
│   └── templates/
│       └── index.html   # Single-page dashboard
├── shared/
│   ├── database.py      # SQLAlchemy engine + session factory
│   └── models.py        # ORM models (log_entries, alerts)
├── data/                # SQLite DB — created at runtime, git-ignored
├── logs/                # Log files — created at runtime, git-ignored
├── .env.example         # Template with all variables
├── pyproject.toml
└── SPEC.md              # Full MVP specification
```
