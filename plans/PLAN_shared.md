# Plan: Shared Module

**Ref:** SPEC.md §4 (Database Schema), §5 (Configuration)
**Output:** `shared/` package used by all other components
**Dependency:** None — build this first

---

## Step 1 — Skeleton

Create the following files with empty/stub implementations. No logic yet.

**`shared/__init__.py`** — empty

**`shared/models.py`**
- Import SQLAlchemy declarative base
- Define class `LogEntry` — columns matching SPEC §4 `log_entries` table (names, types only, no defaults yet)
- Define class `Alert` — columns matching SPEC §4 `alerts` table (names, types only)
- Leave `__repr__` methods as `pass` for now

**`shared/database.py`**
- Define function `get_engine(db_path: str)` → returns nothing yet, just `pass`
- Define function `get_session_factory(engine)` → returns nothing yet, just `pass`
- Define function `init_db(engine)` → `pass`
- Define context manager `get_db()` → `pass`

Goal: all imports resolve, no runtime errors when modules are imported.

---

## Step 2 — Implement `shared/models.py`

Reference: SPEC §4 for exact column names and types.

Instructions:
- Use SQLAlchemy `DeclarativeBase` (SQLAlchemy 2.x style) or `declarative_base()` (1.x) — pick one and stay consistent across the project
- `LogEntry.timestamp` and `Alert.timestamp` store UTC datetimes — use `DateTime` column type
- `LogEntry.metadata` stores a raw JSON string — use `Text` column type (not JSON type, keeps it simple)
- Both tables need `id` as INTEGER primary key with `autoincrement=True`
- Both tables need `created_at` with a server-side default of UTC now — look up SQLAlchemy `server_default` or `default` with `datetime.utcnow`
- Verify: `python -c "from shared.models import LogEntry, Alert; print('OK')"` should print OK

---

## Step 3 — Implement `shared/database.py`

Instructions:
- `get_engine(db_path)`: Use `sqlalchemy.create_engine` with a SQLite URL. Ensure the directory in `db_path` exists before creating (create it if missing).
- `get_session_factory(engine)`: Return a `sessionmaker` bound to the engine with `autocommit=False`, `autoflush=False`
- `init_db(engine)`: Call `Base.metadata.create_all(engine)` — this creates tables if they don't exist; it is idempotent
- `get_db(session_factory)`: Context manager that yields a session, commits on success, rolls back on exception, always closes

Key consideration: SQLite has limited concurrency. Multiple services will write to the same file. Add `connect_args={"check_same_thread": False}` and `pool_pre_ping=True` to `create_engine`.

---

## Step 4 — Sanity Test

No formal test framework yet — just a manual verification script.

Create `shared/test_shared.py` (temporary, not production code):
- Load `DB_PATH` from environment (use python-dotenv)
- Call `get_engine`, `init_db`
- Open session, insert one `LogEntry` and one `Alert` with dummy data
- Query both back, print them
- Assert row counts == 1

Run it: `python -m shared.test_shared`
Expected: two printed rows, no exceptions.

Delete `test_shared.py` after verification passes.

---

## Checklist

- [ ] Step 1: Skeleton imports without error
- [ ] Step 2: Both ORM models have all SPEC columns
- [ ] Step 3: `init_db` creates `log_entries` and `alerts` tables in SQLite file
- [ ] Step 4: Insert + query round-trip works
- [ ] No hardcoded paths — `DB_PATH` always comes from env/argument
