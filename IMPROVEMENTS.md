# TODO / Production Improvements

Items to address before running this system in a production environment.
Grouped by priority and theme.

---

## Security

- [ ] **Authentication** — all 4 endpoints are open. Add API key or JWT auth to `/webhook/alert`, `/alerts`, and dashboard routes.
- [ ] **HTTPS** — run behind a reverse proxy (nginx / Caddy) with TLS termination.
- [ ] **Secrets management** — replace `.env` file with a proper secrets manager (AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager). Never commit credentials.
- [ ] **Rate limiting** — add rate limiting to `/webhook/alert` to prevent flooding from a misbehaving watchdog.
- [ ] **Input sanitization** — dashboard renders `source_service` and `message` fields from DB into HTML. Currently escaped via `escHtml()` but a security audit of all data paths is warranted.

---

## Infrastructure & Deployment

- [ ] **Docker / Docker Compose** — containerize each service so the system can be started with a single `docker compose up`. Include health checks per container.
- [ ] **Database** — SQLite is single-writer and not suitable under concurrent load. Migrate to PostgreSQL (SQLAlchemy already supports it — only `DB_PATH` → `DATABASE_URL` change needed).
- [ ] **Data retention** — no cleanup policy exists. `log_entries` grows unbounded. Add a scheduled job to purge entries older than N days.
- [ ] **Process supervision** — services are raw Python processes. Use systemd units, supervisord, or Kubernetes deployments to auto-restart on crash.
- [ ] **CI/CD pipeline** — add GitHub Actions workflow for lint, test, and build on push.

---

## Reliability & Observability

- [ ] **Structured logging** — services print to stdout with ad-hoc strings. Replace with `structlog` or Python `logging` with JSON formatter so logs are parseable by log aggregators (Loki, CloudWatch, Datadog).
- [ ] **Watchdog health check** — no way to know if the watchdog itself is alive. Expose a `/health` endpoint or emit a heartbeat metric so you can alert on watchdog silence.
- [ ] **Webhook retry queue** — failed alert POSTs are retried once then dropped. Use a persistent queue (Redis, SQS, or a local SQLite queue table) so alerts survive webhook receiver restarts.
- [ ] **Startup config validation on all services** — only watchdog validates config on start. Dashboard and webhook receiver should also exit with clear errors on bad config.
- [ ] **Graceful shutdown** — webhook receiver and dashboard don't handle SIGTERM cleanly. Add lifespan handlers to drain in-flight requests before stopping.

---

## Features & UX

- [ ] **Alert notification channels** — currently only HTTP webhook. Add Slack, PagerDuty, email, or Microsoft Teams delivery via configurable channels.
- [ ] **Dashboard filters** — no ability to filter by service, severity, or date range. Add query params to `/api/alerts` and UI controls for filtering.
- [ ] **Dashboard pagination** — alert table hard-caps at 50 rows. Add pagination or infinite scroll.
- [ ] **Dashboard date range selector** — error-rate chart is fixed to last 60 minutes. Allow user to adjust the lookback window.
- [ ] **Multi-day log ingestion** — watchdog only watches today's log file. On startup after downtime it misses previous days. Add backfill logic to process any unread files in `LOG_DIR`.
- [ ] **Real log ingestion** — replace the simulated log generator with a real log shipper integration (Fluentd, Vector, Filebeat) that tails actual application logs.

---

## AI / Claude Integration

- [ ] **Prompt tuning** — the SRE analyst prompt is generic. Tailor it with domain-specific service context, known failure modes, and runbook references.
- [ ] **Token cost monitoring** — no visibility into Claude API spend. Log `usage.input_tokens` and `usage.output_tokens` per call to a `ai_usage` table for cost tracking.
- [ ] **Async AI calls** — `analyze_spike()` is synchronous and blocks the watchdog poll loop during the API call. Move to async with `httpx` or `asyncio` so the loop is not delayed.
- [ ] **Trend-aware analysis** — Claude currently sees only a single spike snapshot. Feed it recent alert history and error-rate trends for richer root cause analysis.
- [ ] **Model selection** — currently pinned to `claude-haiku-4-5`. Expose `AI_MODEL` as an env var so operators can switch to Sonnet or Opus for higher-stakes environments without touching code.
- [ ] **Provider abstraction** — analysis logic is tightly coupled to the Anthropic SDK. Introduce a provider interface so the client can swap to OpenAI, Azure OpenAI, AWS Bedrock, or a local Ollama instance by changing one env var (`AI_PROVIDER`). Each provider implements the same `analyze_spike()` contract.
- [ ] **Prompt customization** — the SRE analyst prompt is hardcoded in `analyzer.py`. Externalize it to a file (e.g. `prompts/sre_analyst.txt`) so clients can tune tone, output format, domain language, and runbook references without touching Python code. Support a `SYSTEM_PROMPT_PATH` env var.
- [ ] **Per-environment prompt profiles** — different environments (staging vs. prod) may need different instructions. Support named prompt profiles that can be selected via env var.
- [ ] **Fallback & circuit breaker** — if Claude API is consistently failing, apply a circuit breaker so the watchdog doesn't waste time retrying on every spike.

---

## Testing

- [ ] **Unit tests** — `detector.py` rolling-window logic, `analyzer.py` prompt building, `queries.py` stat calculations, and `reader.py` offset tracking all lack tests.
- [ ] **Integration tests** — end-to-end test: inject log entries into DB, assert alert fires and is stored, assert dashboard stats update.
- [ ] **Load test** — validate system behavior under high log volume (thousands of entries per second) to find DB contention and memory limits.
- [ ] **Chaos test** — kill each service in turn and verify the others degrade gracefully without crashing.
