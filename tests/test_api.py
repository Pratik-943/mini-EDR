from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app
from server.config import Settings


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(bootstrap_token="a" * 32, database_path=tmp_path / "test.db", server_name="test")
    return TestClient(create_app(settings))


def test_enroll_ingest_and_alert(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        enrolled = client.post("/api/v1/agents/enroll", json={
            "enrollment_token": "a" * 32, "hostname": "win-test", "platform": "windows", "agent_version": "0.1.0",
        })
        assert enrolled.status_code == 201
        token = enrolled.json()["agent_token"]
        ingested = client.post("/api/v1/events", headers={"Authorization": f"Bearer {token}"}, json={"events": [{
            "timestamp": "2026-08-29T12:00:00Z", "platform": "windows", "category": "powershell",
            "action": "script_block", "process_name": "powershell.exe", "command_line": "powershell -enc ZABlAG0AbwA=",
            "source": "fixture", "raw_event_id": "4104", "details": {},
        }]})
        assert ingested.status_code == 200
        assert len(ingested.json()["alert_ids"]) == 1
        alerts = client.get("/api/v1/alerts")
        assert alerts.status_code == 200
        assert alerts.json()[0]["rule_id"] == "EDR-PS-001"


def test_events_require_agent_authentication(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.post("/api/v1/events", json={"events": []})
        assert response.status_code == 422

