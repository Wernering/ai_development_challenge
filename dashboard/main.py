import os
import sys

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

load_dotenv()

from dashboard.queries import get_error_rate_series, get_recent_alerts, get_stats
from shared.database import get_db, get_engine, get_session_factory, init_db

_DB_PATH = os.getenv("DB_PATH", "./data/watchdog.db")
_LOOKBACK_HOURS = int(os.getenv("ALERT_LOOKBACK_HOURS", "24"))
_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
_PORT = int(os.getenv("DASHBOARD_PORT", "8002"))
_ERROR_THRESHOLD = int(os.getenv("ERROR_THRESHOLD", "5"))

_engine = get_engine(_DB_PATH)
init_db(_engine)
_session_factory = get_session_factory(_engine)

_templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)

app = FastAPI(title="Watchdog Dashboard")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return _templates.TemplateResponse(
        request,
        "index.html",
        {
            "lookback_hours": _LOOKBACK_HOURS,
            "error_threshold": _ERROR_THRESHOLD,
        },
    )


@app.get("/api/stats")
def api_stats():
    try:
        with get_db(_session_factory) as session:
            return JSONResponse(get_stats(session, _LOOKBACK_HOURS))
    except Exception as exc:
        print(f"[dashboard] stats error: {exc}", file=sys.stderr)
        return JSONResponse({"error": "data unavailable"})


@app.get("/api/error-rate")
def api_error_rate():
    try:
        with get_db(_session_factory) as session:
            return JSONResponse(get_error_rate_series(session))
    except Exception as exc:
        print(f"[dashboard] error-rate error: {exc}", file=sys.stderr)
        return JSONResponse({"error": "data unavailable"})


@app.get("/api/alerts")
def api_alerts():
    try:
        with get_db(_session_factory) as session:
            return JSONResponse(get_recent_alerts(session))
    except Exception as exc:
        print(f"[dashboard] alerts error: {exc}", file=sys.stderr)
        return JSONResponse({"error": "data unavailable"})


if __name__ == "__main__":
    uvicorn.run("dashboard.main:app", host=_HOST, port=_PORT, reload=False)
