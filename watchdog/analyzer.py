import json
import os
import sys

_SYSTEM_PROMPT = (
    "You are an SRE anomaly analyst. Given a set of application log entries that triggered an error spike, "
    "respond with a JSON object containing exactly three keys:\n"
    "  - classification: short label for the anomaly type (e.g. 'Database Overload', 'Memory Pressure', "
    "'Network Degradation', 'Application Bug')\n"
    "  - root_cause: one sentence explaining the likely cause\n"
    "  - recommendation: one actionable remediation step\n"
    "Respond ONLY with the JSON object, no markdown, no extra text."
)


def _build_user_content(alert_payload: dict, log_entries: list) -> str:
    summary = (
        f"Alert: {alert_payload['severity']} spike — "
        f"{alert_payload['error_count']} errors in {alert_payload['window_seconds']}s "
        f"on service '{alert_payload['source_service']}'."
    )
    samples = []
    for entry in log_entries[:20]:
        samples.append({
            "timestamp": entry.timestamp.isoformat(),
            "level": entry.level,
            "service": entry.service,
            "message": entry.message,
        })
    return f"{summary}\n\nLog samples:\n{json.dumps(samples, indent=2)}"


def analyze_spike(alert_payload: dict, log_entries: list) -> dict | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": _build_user_content(alert_payload, log_entries),
                }
            ],
        )
        raw = response.content[0].text.strip()
        return json.loads(raw)
    except Exception as exc:
        print(f"[watchdog] AI analysis failed: {exc}", file=sys.stderr)
        return None
