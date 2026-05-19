import sys
import time

import httpx


def send_alert(webhook_url: str, payload: dict) -> bool:
    for attempt in (1, 2):
        try:
            response = httpx.post(webhook_url, json=payload, timeout=5.0)
            if response.is_success:
                print(f"[watchdog/notifier] Alert sent: {payload['severity']} — {payload['message']}")
                return True
            print(
                f"[watchdog/notifier] Webhook returned {response.status_code}: {response.text[:200]}",
                file=sys.stderr,
            )
            return False
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            print(f"[watchdog/notifier] Attempt {attempt} failed: {exc}", file=sys.stderr)
            if attempt == 1:
                time.sleep(1)
    return False
