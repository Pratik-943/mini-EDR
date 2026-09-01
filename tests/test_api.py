import re
from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app
from server.config import Settings


ADMIN_TOKEN = "a" * 32


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(admin_token=ADMIN_TOKEN, database_path=tmp_path / "test.db", server_name="test")
    return TestClient(create_app(settings))


def create_deployment(client: TestClient, name: str = "win-test") -> tuple[dict, str]:
    response = client.post("/api/v1/deployments", headers={"X-Admin-Token": ADMIN_TOKEN}, json={
        "agent_name": name, "platform": "windows", "expires_in_minutes": 60,
    })
    assert response.status_code == 201
    created = response.json()
    match = re.search(r"/windows/([^']+)", created["install_command"])
    assert match
    return created, match.group(1)


def test_one_time_deployment_enrolls_and_alerts(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        created, deployment_token = create_deployment(client)
        assert "token" not in created
        enrolled = client.post("/api/v1/agents/enroll", json={
            "deployment_token": deployment_token, "hostname": "win-test-host", "platform": "windows", "agent_version": "0.2.0",
        })
        assert enrolled.status_code == 201
        token = enrolled.json()["agent_token"]
        repeat = client.post("/api/v1/agents/enroll", json={
            "deployment_token": deployment_token, "hostname": "another-host", "platform": "windows", "agent_version": "0.2.0",
        })
        assert repeat.status_code == 401
        ingested = client.post("/api/v1/events", headers={"Authorization": f"Bearer {token}"}, json={"events": [{
            "timestamp": "2026-09-01T12:00:00Z", "platform": "windows", "category": "powershell",
            "action": "script_block", "process_name": "powershell.exe", "command_line": "powershell -enc ZABlAG0AbwA=",
            "source": "fixture", "raw_event_id": "4104", "details": {},
        }]})
        assert ingested.status_code == 200
        assert len(ingested.json()["alert_ids"]) == 1
        agents = client.get("/api/v1/agents", headers={"X-Admin-Token": ADMIN_TOKEN})
        assert agents.json()[0]["agent_name"] == "win-test"


def test_deployments_require_admin_access(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        assert client.get("/api/v1/deployments").status_code == 401
        assert client.post("/api/v1/deployments", json={"agent_name": "linux-01", "platform": "linux"}).status_code == 401

