from shared.models import Alert


def save_alert(session, alert_data: dict) -> Alert:
    alert = Alert(**alert_data)
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return alert


def list_alerts(session, limit: int = 50) -> list[Alert]:
    return (
        session.query(Alert)
        .order_by(Alert.timestamp.desc())
        .limit(limit)
        .all()
    )
