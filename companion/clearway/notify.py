"""Phone notifications through ntfy (https://ntfy.sh) - free, no account needed."""
from __future__ import annotations

import json
import logging
import threading
import urllib.parse
import urllib.request

log = logging.getLogger("clearway.notify")


def publish(server: str, topic: str, title: str, message: str, *, priority: int = 4,
            tags: list[str] | None = None, click: str | None = None,
            actions: list[dict] | None = None) -> None:
    """Send a notification in a background thread so polling is never delayed."""
    payload = {
        "topic": topic,
        "title": title,
        "message": message,
        "priority": priority,
        "tags": tags or [],
    }
    if click:
        payload["click"] = click
    if actions:
        payload["actions"] = actions[:3]

    def _send():
        try:
            req = urllib.request.Request(
                server.rstrip("/") + "/",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "Clearway-CPDLC/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
        except Exception as exc:  # notification failures must never break the session
            log.warning("ntfy publish failed: %s", exc)

    threading.Thread(target=_send, daemon=True).start()


def quick_action(label: str, base_url: str, key: str, msg_id: int, reply: str) -> dict:
    query = urllib.parse.urlencode({"k": key, "id": msg_id, "r": reply})
    return {
        "action": "http",
        "label": label,
        "url": f"{base_url}/api/quick?{query}",
        "method": "POST",
        "clear": True,
    }
