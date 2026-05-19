# Plan: Log Generator

**Ref:** SPEC.md §6.1, §5 (env vars: LOG_INTERVAL_SECONDS, LOG_DIR, LOG_SERVICE_NAMES)
**Output:** Continuous JSON log writer to `{LOG_DIR}/{YYYY-MM-DD}.log`
**Dependency:** None (no DB, no shared module needed)

---

## Step 1 — Skeleton

**`log_generator/__init__.py`** — empty

**`log_generator/generator.py`**
- Define function `build_log_entry(service_names: list[str]) -> dict` → `return {}`
- Define function `get_log_file_path(log_dir: str) -> str` → `return ""`
- Define function `write_log_entry(file_path: str, entry: dict) -> None` → `pass`

**`log_generator/main.py`**
- Load env vars with python-dotenv
- Define `run()` function → `pass`
- Add `if __name__ == "__main__": run()` block

Verify: `python -m log_generator.main` exits cleanly (no crash).

---

## Step 2 — Implement `build_log_entry`

Instructions:
- `service_names`: list parsed from `LOG_SERVICE_NAMES` env var (comma-split, strip whitespace)
- Pick `level` randomly using weighted choice — SPEC §6.1: WARNING 60%, ERROR 30%, CRITICAL 10%
  - Use `random.choices` with `weights` parameter
- Pick `service` randomly from `service_names` (uniform)
- Generate `message`: simple string combining level and service — e.g. `"ERROR in api: connection timeout"`. Use a small pool of ~5 message templates per level to vary output.
- Generate `metadata`: dict with at least `request_id` (random UUID4 short string) and `error_code` (integer, vary by level: CRITICAL→500, ERROR→4xx or 500, WARNING→4xx)
- `timestamp`: UTC now in ISO 8601 format with `Z` suffix — use `datetime.utcnow().isoformat() + "Z"`
- Return assembled dict matching SPEC §6.1 JSON schema exactly

---

## Step 3 — Implement `get_log_file_path` and `write_log_entry`

**`get_log_file_path(log_dir)`:**
- Return `{log_dir}/{YYYY-MM-DD}.log` using today's UTC date
- Create `log_dir` directory if it does not exist (`os.makedirs(..., exist_ok=True)`)

**`write_log_entry(file_path, entry)`:**
- Open file in append mode (`"a"`, encoding `"utf-8"`)
- Write `json.dumps(entry)` followed by `\n`
- Close file (use `with` block — do not keep file handle open between writes)
- Do not swallow exceptions — let them propagate to `main.py` for logging

---

## Step 4 — Implement `main.py` run loop

Instructions:
- Load: `LOG_INTERVAL_SECONDS` (float), `LOG_DIR` (str), `LOG_SERVICE_NAMES` (str → parse to list)
- Parse `LOG_SERVICE_NAMES`: split on comma, strip each item, filter empty strings
- Loop forever:
  1. Call `get_log_file_path(LOG_DIR)` — recalculate each iteration to handle midnight rollover
  2. Call `build_log_entry(service_names)`
  3. Call `write_log_entry(file_path, entry)`
  4. Print entry `level` + `service` + `timestamp` to stdout (one line — gives operator visibility)
  5. `time.sleep(LOG_INTERVAL_SECONDS)`
- Wrap loop in `try/except KeyboardInterrupt` → print "Generator stopped." and exit cleanly
- Operational errors inside loop (e.g. disk write failure): catch, print to stderr, `time.sleep(5)` and retry — do not exit

---

## Step 5 — Manual Verification

1. Create `.env` with `LOG_DIR=./logs`, `LOG_INTERVAL_SECONDS=0.5`, `LOG_SERVICE_NAMES=api,worker,db`
2. Run: `python -m log_generator.main`
3. Let run for 10 seconds, then Ctrl+C
4. Open `logs/{today}.log` — verify:
   - Each line is valid JSON (`python -c "import json; [json.loads(l) for l in open('logs/....log')]"`)
   - All 7 fields present
   - Level distribution roughly matches weights (mostly WARNING)
   - Multiple service names appear

---

## Checklist

- [ ] Step 1: Module imports cleanly
- [ ] Step 2: `build_log_entry` returns all 7 SPEC fields; weights produce ~60/30/10 split over many calls
- [ ] Step 3: File created in correct path; each call appends one valid JSON line
- [ ] Step 4: Loop runs, midnight rollover creates new file, Ctrl+C exits gracefully
- [ ] Step 5: Log file passes JSON parse check for all lines
