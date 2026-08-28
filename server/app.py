from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from server.config import ROOT, Settings, get_settings
from server.database import add_event, connection, initialize, list_agents, list_alerts, utc_now
from server.detection import Rule, evaluate, load_rules
from server.schemas import AlertStatusUpdate, EnrollmentRequest, EventBatch


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    rules_directory = ROOT / "rules"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize(app_settings.database_path)
        app.state.rules = load_rules(rules_directory)
        yield

    app = FastAPI(title="mini-EDR", version="0.1.0", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=ROOT / "server" / "static"), name="static")

    def authenticate_agent(authorization: str | None = Header(default=None)) -> dict:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Agent bearer token required")
        digest = token_digest(authorization.removeprefix("Bearer "))
        with connection(app_settings.database_path) as conn:
            row = conn.execute("SELECT * FROM agents WHERE token_hash = ?", (digest,)).fetchone()
            if row is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent token")
            conn.execute("UPDATE agents SET last_seen_at = ? WHERE id = ?", (utc_now(), row["id"]))
        return dict(row)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "service": app_settings.server_name, "rule_count": len(app.state.rules)}

    @app.post("/api/v1/agents/enroll", status_code=status.HTTP_201_CREATED)
    def enroll(request: EnrollmentRequest) -> dict:
        if not app_settings.bootstrap_token or not secrets.compare_digest(request.enrollment_token, app_settings.bootstrap_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid enrollment token")
        agent_id = str(uuid.uuid4())
        agent_token = secrets.token_urlsafe(32)
        now = utc_now()
        with connection(app_settings.database_path) as conn:
            conn.execute(
                """INSERT INTO agents(id, hostname, platform, agent_version, token_hash, enrolled_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (agent_id, request.hostname, request.platform, request.agent_version, token_digest(agent_token), now, now),
            )
        return {"agent_id": agent_id, "agent_token": agent_token}

    @app.post("/api/v1/events")
    def ingest_events(batch: EventBatch, agent: dict = Depends(authenticate_agent)) -> dict:
        generated_alerts: list[str] = []
        with connection(app_settings.database_path) as conn:
            for item in batch.events:
                event = item.model_dump(mode="json")
                add_event(conn, agent["id"], event)
                for rule in evaluate(app.state.rules, event):
                    alert_id = str(uuid.uuid4())
                    conn.execute(
                        """INSERT INTO alerts(id, agent_id, rule_id, title, severity, mitre, description, status, created_at, evidence_json)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)""",
                        (alert_id, agent["id"], rule.id, rule.title, rule.severity, rule.mitre, rule.description,
                         utc_now(), json.dumps(event, separators=(",", ":"))),
                    )
                    generated_alerts.append(alert_id)
        return {"accepted": len(batch.events), "alert_ids": generated_alerts}

    @app.get("/api/v1/agents")
    def agents() -> list[dict]:
        return list_agents(app_settings.database_path)

    @app.get("/api/v1/alerts")
    def alerts(limit: int = 100) -> list[dict]:
        return list_alerts(app_settings.database_path, max(1, min(limit, 250)))

    @app.patch("/api/v1/alerts/{alert_id}")
    def update_alert(alert_id: str, update: AlertStatusUpdate) -> dict:
        with connection(app_settings.database_path) as conn:
            cursor = conn.execute("UPDATE alerts SET status = ? WHERE id = ?", (update.status, alert_id))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
        return {"id": alert_id, "status": update.status}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(_: Request) -> HTMLResponse:
        html = (ROOT / "server" / "templates" / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(html)

    return app


app = create_app()

