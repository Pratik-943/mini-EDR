from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def config_path() -> Path:
    if platform.system() == "Windows":
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "mini-edr-agent" / "agent.json"
    return Path("/etc/mini-edr-agent/agent.json")


def save_config(data: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if platform.system() != "Windows":
        path.chmod(0o600)


def load_config() -> dict:
    path = config_path()
    if not path.is_file():
        raise RuntimeError(f"Agent is not configured: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def enroll(client: httpx.Client, server: str, deployment_token: str) -> dict:
    response = client.post(f"{server}/api/v1/agents/enroll", json={
        "deployment_token": deployment_token,
        "hostname": socket.gethostname(),
        "platform": "windows" if platform.system() == "Windows" else "linux",
        "agent_version": "0.2.0",
    })
    response.raise_for_status()
    return response.json()


def ensure_enrolled(client: httpx.Client, config: dict) -> dict:
    if config.get("agent_token"):
        return config
    deployment_token = config.get("deployment_token")
    if not deployment_token:
        raise RuntimeError("Agent has neither an agent credential nor a deployment token")
    credentials = enroll(client, config["server_url"], deployment_token)
    config["agent_id"] = credentials["agent_id"]
    config["agent_name"] = credentials["agent_name"]
    config["agent_token"] = credentials["agent_token"]
    config.pop("deployment_token", None)
    save_config(config)
    return config


def heartbeat(client: httpx.Client, config: dict) -> None:
    response = client.post(
        f"{config['server_url']}/api/v1/agents/heartbeat",
        headers={"Authorization": f"Bearer {config['agent_token']}"},
    )
    response.raise_for_status()


def send_demo_event(client: httpx.Client, config: dict) -> dict:
    event = {
        "timestamp": now(), "platform": "windows" if platform.system() == "Windows" else "linux",
        "category": "powershell", "action": "script_block", "process_name": "powershell.exe",
        "command_line": "powershell.exe -enc <safe-demo-value>",
        "source": "mini-edr-demo", "raw_event_id": "demo-001", "details": {"demo": True},
    }
    response = client.post(f"{config['server_url']}/api/v1/events", headers={"Authorization": f"Bearer {config['agent_token']}"}, json={"events": [event]})
    response.raise_for_status()
    return response.json()


def command_configure(args: argparse.Namespace) -> None:
    save_config({
        "server_url": args.server_url.rstrip("/"),
        "deployment_token": args.deployment_token,
        "agent_name": args.agent_name,
    })
    print(f"Agent configuration saved to {config_path()}")


def command_run(_: argparse.Namespace) -> None:
    while True:
        try:
            with httpx.Client(timeout=15.0) as client:
                config = ensure_enrolled(client, load_config())
                heartbeat(client, config)
            time.sleep(30)
        except KeyboardInterrupt:
            return
        except Exception as error:
            print(f"mini-EDR agent connection failed: {error}", flush=True)
            time.sleep(30)


def command_demo(args: argparse.Namespace) -> None:
    config = {"server_url": args.server.rstrip("/"), "deployment_token": args.deployment_token, "agent_name": "demo-agent"}
    with httpx.Client(timeout=15.0) as client:
        credentials = enroll(client, config["server_url"], config["deployment_token"])
        config.update(credentials)
        result = send_demo_event(client, config)
    print(f"Enrolled agent {config['agent_name']} ({config['agent_id']})")
    print(f"Sent safe demo event; alerts: {result['alert_ids']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="mini-EDR endpoint agent")
    commands = parser.add_subparsers(dest="command", required=True)
    configure = commands.add_parser("configure", help="Save installer-provided endpoint configuration")
    configure.add_argument("--server-url", required=True)
    configure.add_argument("--deployment-token", required=True)
    configure.add_argument("--agent-name", required=True)
    configure.set_defaults(handler=command_configure)
    run = commands.add_parser("run", help="Run the persistent agent service")
    run.set_defaults(handler=command_run)
    demo = commands.add_parser("demo", help="Enroll once and send a safe simulated event")
    demo.add_argument("--server", required=True)
    demo.add_argument("--deployment-token", required=True)
    demo.set_defaults(handler=command_demo)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
