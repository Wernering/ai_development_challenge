# Plan: Webhook Receiver

**Ref:** SPEC.md §6.3, §4 (`alerts` table), §5 (env vars)
**Output:** FastAPI service on port 8001, persists alerts to SQLite
**Dependency:** `shared/` module complete (Step 1 of PLAN_shared.md done)

---

## Step 1 — Skeleton

Create files with stubs. All imports must resolve; routes return dummy data.

**`webhook_receiver/__init__.py`** — empty

**`webhook_receiver/models.py`**
- Define Pydantic class `AlertIn` — fields matching SPEC §6.2 alert payload (7 fields), no validators yet
- Define Pydantic class `AlertOut` — same fields plus `id: int` and `created_at: datetime`

**`webhook_receiver/database.py`**
- Define function `save_alert(session, alert_data: dict) -> Alert` → `pass`
- Define function `list_alerts(session, limit: int = 50) -> list` → `return []`

**`webhook_receiver/routes.py`**
- Import FastAPI `APIRouter`
- Define router with prefix `/`
- Stub `POST /webhook/alert` → returns `{"status": "stub"}`
- Stub `GET /alerts` → returns `[]`
- Stub `GET /health` → returns `{"status": "ok"}`

**`webhook_receiver/main.py`**
- Create FastAPI app instance
- Include router from `routes.py`
- Add uvicorn `if __name__ == "__main__"` block using `WEBHOOK_HOST` and `WEBHOOK_PORT` from env

Verify: `python -m webhook_receiver.main` starts without error. Hit `GET /health` → `{"status": "ok"}`.

---

## Step 2 — Implement Pydantic Models (`models.py`)

Instructions:
- `AlertIn` fields: `timestamp` (datetime), `severity` (str), `message` (str), `error_count` (int), `threshold` (int), `window_seconds` (int), `source_service` (str)
- Add validator on `severity`: must be one of `["HIGH", "CRITICAL"]` — use `@field_validator` or `Literal` type
- Add validator: `error_count` and `threshold` must be > 0
- `AlertOut` inherits or duplicates `AlertIn` fields + adds `id: int`, `created_at: datetime`
- Enable `model_config = ConfigDict(from_attributes=True)` so SQLAlchemy ORM objects can be serialized directly

---

## Step 3 — Implement Database Functions (`database.py`)

Instructions:
- `save_alert(session, alert_data: dict)`:
  - Construct `Alert` ORM object from `alert_data`
  - Add to session, commit, refresh to get generated `id` and `created_at`
  - Return the `Alert` object
- `list_alerts(session, limit: int)`:
  - Query `alerts` table ordered by `timestamp DESC`
  - Apply limit
  - Return list of `Alert` ORM objects

Import `Alert` from `shared.models`. Import session factory setup from `shared.database`.

---

## Step 4 — Implement Route Handlers (`routes.py`)

Instructions:
- Load env vars at module level using python-dotenv: `DB_PATH`
- Create engine + session factory once at startup (not per request)
- `POST /webhook/alert`:
  - Accept `AlertIn` body
  - Open DB session via `get_db()`
  - Call `save_alert(session, alert_in.model_dump())`
  - Return `AlertOut` with HTTP 201
  - On DB error: log to stdout, return HTTP 500
- `GET /alerts`:
  - Accept optional query param `limit: int = 50`
  - Return list of `AlertOut`
- `GET /health`:
  - Return `{"status": "ok", "service": "webhook-receiver"}`

---

## Step 5 — Integration Test

No test framework — manual curl verification:

1. Start service: `python -m webhook_receiver.main`
2. POST valid alert:
   ```
   curl -X POST http://localhost:8001/webhook/alert \
     -H "Content-Type: application/json" \
     -d '{"timestamp":"2026-05-18T10:00:00Z","severity":"HIGH","message":"spike","error_count":7,"threshold":5,"window_seconds":60,"source_service":"api"}'
   ```
   Expect: 201 response with `id` field present
3. GET alerts: `curl http://localhost:8001/alerts` — expect array with 1 item
4. POST invalid severity `"severity":"LOW"` — expect 422

---

## Checklist

- [ ] Step 1: Service starts, `/health` responds
- [ ] Step 2: `AlertIn` rejects invalid severity and non-positive counts
- [ ] Step 3: `save_alert` persists to SQLite, `list_alerts` returns ordered results
- [ ] Step 4: POST returns 201 + stored object; GET returns list
- [ ] Step 5: All curl tests pass
- [ ] No env vars hardcoded — always read from `.env`
