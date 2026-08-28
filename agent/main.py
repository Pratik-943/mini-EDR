from __future__ import annotations

import argparse
import platform
import socket
from datetime import datetime, timezone

import httpx


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def enroll(client: httpx.Client, server: str, enrollment_token: str) -> dict:
    response = client.post(f"{server}/api/v1/agents/enroll", json={
        "enrollment_token": enrollment_token,
        "hostname": socket.gethostname(),
        "platform": "windows" if platform.system() == "Windows" else "linux",
        "agent_version": "0.1.0",
    })
    response.raise_for_status()
    return response.json()


def send_demo_event(client: httpx.Client, server: str, agent_token: str) -> dict:
    event = {
        "timestamp": now(), "platform": "windows" if platform.system() == "Windows" else "linux",
        "category": "powershell", "action": "script_block", "process_name": "powershell.exe",
        "command_line": "powershell.exe -enc <safe-demo-value>",
        "source": "mini-edr-demo", "raw_event_id": "demo-001", "details": {"demo": True},
    }
    response = client.post(f"{server}/api/v1/events", headers={"Authorization": f"Bearer {agent_token}"}, json={"events": [event]})
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="mini-EDR agent foundation")
    parser.add_argument("--server", required=True, help="Server base URL, for example http://127.0.0.1:8000")
    parser.add_argument("--enrollment-token", required=True, help="One-time enrollment token")
    parser.add_argument("--demo", action="store_true", help="Send one safe simulated detection event")
    args = parser.parse_args()
    with httpx.Client(timeout=10.0) as client:
        credentials = enroll(client, args.server.rstrip("/"), args.enrollment_token)
        print(f"Enrolled agent {credentials['agent_id']}")
        if args.demo:
            result = send_demo_event(client, args.server.rstrip("/"), credentials["agent_token"])
            print(f"Sent safe demo event; alerts: {result['alert_ids']}")


if __name__ == "__main__":
    main()

