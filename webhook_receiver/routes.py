import os

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from shared.database import get_db, get_engine, get_session_factory, init_db
from webhook_receiver.database import list_alerts, save_alert
from webhook_receiver.models import AlertIn, AlertOut

load_dotenv()

_engine = get_engine(os.getenv("DB_PATH", "./data/watchdog.db"))
init_db(_engine)
_session_factory = get_session_factory(_engine)

router = APIRouter()


@router.post("/webhook/alert", status_code=201)
def receive_alert(alert_in: AlertIn):
    try:
        with get_db(_session_factory) as session:
            stored = save_alert(session, alert_in.model_dump())
            return AlertOut.model_validate(stored)
    except Exception as exc:
        print(f"[webhook_receiver] DB error on save: {exc}")
        raise HTTPException(status_code=500, detail="Failed to store alert")


@router.get("/alerts", response_model=list[AlertOut])
def get_alerts(limit: int = 50):
    try:
        with get_db(_session_factory) as session:
            return [AlertOut.model_validate(a) for a in list_alerts(session, limit)]
    except Exception as exc:
        print(f"[webhook_receiver] DB error on list: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")


@router.get("/health")
def health():
    return {"status": "ok", "service": "webhook-receiver"}
