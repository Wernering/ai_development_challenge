# Plan: Dashboard

**Ref:** SPEC.md §6.4, §4, §5 (ALERT_LOOKBACK_HOURS, DASHBOARD_PORT)
**Output:** FastAPI service on port 8002 serving HTML dashboard + JSON API
**Dependency:** `shared/` complete; SQLite has data (run full stack first)

---

## Step 1 — Skeleton

**`dashboard/__init__.py`** — empty

**`dashboard/queries.py`**
- Define function `get_stats(session, lookback_hours: int) -> dict` → `return {}`
- Define function `get_error_rate_series(session) -> list` → `return []`
- Define function `get_recent_alerts(session, limit: int = 50) -> list` → `return []`

**`dashboard/main.py`**
- Create FastAPI app instance
- Mount Jinja2 `templates/` directory
- Define route `GET /` → return `TemplateResponse("index.html", {...})`
- Define route `GET /api/stats` → `return {}`
- Define route `GET /api/error-rate` → `return []`
- Define route `GET /api/alerts` → `return []`
- Add uvicorn `if __name__ == "__main__"` block using `DASHBOARD_HOST` / `DASHBOARD_PORT`

**`dashboard/templates/index.html`**
- Valid HTML5 boilerplate only — `<h1>Watchdog Dashboard</h1>`, no data yet

Verify: `python -m dashboard.main` starts. `GET /` returns HTML page. `GET /api/stats` returns `{}`.

---

## Step 2 — Implement `queries.py`

Instructions for each function — do not write the SQL yet, just understand what each needs:

**`get_stats(session, lookback_hours)`:**
- Count total rows in `log_entries`
- Count total rows in `alerts`
- Count `alerts` where `created_at >= (now - lookback_hours)`
- Compute current error rate: count `log_entries` with `level IN ('ERROR','CRITICAL')` in last 60 minutes ÷ total `log_entries` in last 60 minutes × 100. Handle divide-by-zero → return 0.0
- Return dict matching SPEC §6.4 `/api/stats` response shape

**`get_error_rate_series(session)`:**
- Look back 60 minutes from now, bucketed by minute (60 buckets)
- For each bucket: count WARNING, ERROR, CRITICAL separately from `log_entries`
- Return list of dicts: `{bucket_time: str, warning_count: int, error_count: int, critical_count: int}`
- Hint: use SQLite `strftime('%Y-%m-%dT%H:%M:00', timestamp)` for bucketing in raw SQL, or group in Python after fetching

**`get_recent_alerts(session, limit)`:**
- Query `alerts` ordered by `timestamp DESC`, apply limit
- Return list of dicts (serialize each ORM object to dict)

---

## Step 3 — Implement API Routes (`main.py`)

Instructions:
- Load env vars once at startup: `DB_PATH`, `ALERT_LOOKBACK_HOURS`
- Create engine + session factory at startup
- Each API route: open DB session via `get_db()`, call appropriate query function, close session
- `GET /api/stats` → call `get_stats`, return JSON (use `JSONResponse`)
- `GET /api/error-rate` → call `get_error_rate_series`, return JSON
- `GET /api/alerts` → call `get_recent_alerts`, return JSON
- `GET /` → pass `lookback_hours` and `service_name` to template context (for display in HTML)
- On DB error in any route: log to stdout, return `{"error": "data unavailable"}` with HTTP 200 (UI graceful degradation — see SPEC §9)

---

## Step 4 — Implement HTML Structure (`index.html`)

Build the static shell — no real data yet, use hardcoded placeholder values.

Instructions:
- `<head>`: include `<meta charset="UTF-8">`, viewport meta, minimal inline `<style>` (no external CSS deps)
- Layout: single column, max-width 1200px, centered
- **Section 1 — KPI cards**: 4 cards in a flex row
  - "Total Logs Processed" / "Total Alerts" / "Alerts Last {X}h" / "Current Error Rate %"
  - Each card: `<div class="kpi-card">` with `<span class="kpi-value" id="kpi-total-logs">—</span>` and label
- **Section 2 — Error Rate Chart**: `<canvas id="error-chart" width="900" height="200"></canvas>`
- **Section 3 — Alert History**: `<table id="alert-table">` with columns: Severity / Time / Service / Error Count / Message
- Add `<script>` block at bottom (empty for now — filled in Step 5)

---

## Step 5 — Implement Vanilla JS Data Fetching + Chart

Instructions for the `<script>` block in `index.html`:

**Data fetching:**
- Write async function `loadDashboard()`:
  1. `fetch('/api/stats')` → update each KPI card's value by `id`
  2. `fetch('/api/alerts')` → clear and repopulate `#alert-table tbody` rows
  3. `fetch('/api/error-rate')` → call `drawChart(data)`
- Handle fetch errors: if any fetch fails, leave existing values unchanged (do not blank the UI)

**Chart (`drawChart(data)`):**
- Use `<canvas>` 2D context — no chart library
- Draw a simple bar chart: one bar per minute bucket, height proportional to `error_count + critical_count`
- Color bars: green if count == 0, yellow if > 0, red if > threshold (pass threshold as a JS variable from the template)
- Draw x-axis labels every 10 minutes
- Keep it simple — this is MVP, not production charting

**Auto-refresh:**
- Call `loadDashboard()` on `DOMContentLoaded`
- `setInterval(loadDashboard, 30000)` for 30-second refresh
- Show last-updated timestamp in a `<small>` element after each refresh

---

## Step 6 — Full Stack Integration Test

1. Ensure `.env` has all values; run full stack: Log Generator, Watchdog, Webhook Receiver
2. Wait ~2 minutes for data to accumulate
3. Start Dashboard: `python -m dashboard.main`
4. Open browser at `http://localhost:8002`
5. Verify:
   - KPI cards show non-zero numbers (not `—`)
   - Chart renders bars (not blank canvas)
   - Alert table shows at least 1 row (trigger a spike if needed by lowering `ERROR_THRESHOLD`)
   - After 30 seconds, numbers update automatically
6. Kill Log Generator — verify Dashboard does not crash (shows last known data)

---

## Checklist

- [ ] Step 1: Service starts, `/` returns HTML, API routes return empty structures
- [ ] Step 2: All 3 query functions return correct shaped data against real DB
- [ ] Step 3: Routes return non-empty JSON when DB has data; DB errors return graceful response
- [ ] Step 4: HTML renders all 3 sections with placeholder values
- [ ] Step 5: `loadDashboard()` populates KPIs + table; chart draws bars; auto-refresh works
- [ ] Step 6: Full stack shows live data; stopping generator doesn't crash dashboard
