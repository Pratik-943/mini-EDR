import requests
import json
import threading
from agent.config.settings import BACKEND_URL

def http_sink(message):
    """Custom loguru sink to forward logs to the backend."""
    record = message.record
    
    # Avoid infinite loops if requests library logs something
    if record["name"].startswith("urllib3") or record["name"].startswith("requests"):
        return

    payload = {
        "message": record["message"],
        "record": {
            "level": record["level"].name,
            "time": record["time"].isoformat(),
            "name": record["name"],
        }
    }

    # We use a simple thread to send the post request to avoid blocking the agent
    def send():
        try:
            requests.post(BACKEND_URL, json=payload, timeout=2.0)
        except Exception:
            pass # Ignore connection errors if server is down

    threading.Thread(target=send, daemon=True).start()
