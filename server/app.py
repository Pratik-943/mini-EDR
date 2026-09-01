from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from server.config import ROOT, Settings, get_settings
from server.database import add_event, connection, initialize, list_agents, list_alerts, utc_now
from server.detection import evaluate, load_rules
from server.schemas import AlertStatusUpdate, DeploymentRequest, EnrollmentRequest, EventBatch


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def as_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    rules_directory = ROOT / "rules"
    payload_directory = ROOT / "server" / "payloads"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize(app_settings.database_path)
        app.state.rules = load_rules(rules_directory)
        yield

    app = FastAPI(title="mini-EDR", version="0.2.0", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=ROOT / "server" / "static"), name="static")

    def authenticate_admin(x_admin_token: str | None = Header(default=None)) -> None:
        if not app_settings.admin_token:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin access is not configured")
        if not x_admin_token or not secrets.compare_digest(x_admin_token, app_settings.admin_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")

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

    def pending_deployment(token: str, platform: str | None = None) -> dict:
        with connection(app_settings.database_path) as conn:
            row = conn.execute("SELECT * FROM deployments WHERE token_hash = ?", (token_digest(token),)).fetchone()
            if row is None or row["status"] != "pending":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid, used, or revoked deployment token")
            if as_utc(row["expires_at"]) <= datetime.now(timezone.utc):
                conn.execute("UPDATE deployments SET status = 'expired' WHERE id = ?", (row["id"],))
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Deployment token has expired")
            if platform and row["platform"] != platform:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deployment token is for a different platform")
            return dict(row)

    def public_url(request: Request) -> str:
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("host", request.url.netloc)
        return f"{scheme}://{host}"

    def package_path(platform: str):
        filename = "mini-edr-agent-windows.msi" if platform == "windows" else "mini-edr-agent-linux-amd64.deb"
        return payload_directory / filename

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "service": app_settings.server_name, "rule_count": len(app.state.rules)}

    @app.post("/api/v1/deployments", status_code=status.HTTP_201_CREATED, dependencies=[Depends(authenticate_admin)])
    def create_deployment(request: Request, deployment: DeploymentRequest) -> dict:
        token = secrets.token_urlsafe(32)
        deployment_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=deployment.expires_in_minutes)
        with connection(app_settings.database_path) as conn:
            existing = conn.execute("SELECT id FROM deployments WHERE agent_name = ?", (deployment.agent_name,)).fetchone()
            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent name already exists")
            conn.execute(
                """INSERT INTO deployments(id, agent_name, platform, token_hash, status, created_at, expires_at)
                   VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
                (deployment_id, deployment.agent_name, deployment.platform, token_digest(token), now.isoformat(), expires_at.isoformat()),
            )
        base_url = public_url(request)
        script_url = f"{base_url}/api/v1/install/{deployment.platform}/{token}"
        if deployment.platform == "windows":
            command = f"$p=Join-Path $env:TEMP 'mini-edr-install.ps1'; Invoke-WebRequest -Uri '{script_url}' -OutFile $p; & $p"
        else:
            command = f"curl --fail --silent --show-error --output /tmp/mini-edr-install.sh '{script_url}' && sudo bash /tmp/mini-edr-install.sh"
        return {
            "id": deployment_id,
            "agent_name": deployment.agent_name,
            "platform": deployment.platform,
            "status": "pending",
            "expires_at": expires_at.isoformat(),
            "install_command": command,
            "package_ready": package_path(deployment.platform).is_file(),
        }

    @app.get("/api/v1/deployments", dependencies=[Depends(authenticate_admin)])
    def deployments() -> list[dict]:
        with connection(app_settings.database_path) as conn:
            rows = conn.execute(
                "SELECT id, agent_name, platform, status, created_at, expires_at, downloaded_at, enrolled_at, agent_id FROM deployments ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    @app.post("/api/v1/deployments/{deployment_id}/revoke", dependencies=[Depends(authenticate_admin)])
    def revoke_deployment(deployment_id: str) -> dict:
        with connection(app_settings.database_path) as conn:
            result = conn.execute("UPDATE deployments SET status = 'revoked' WHERE id = ? AND status = 'pending'", (deployment_id,))
            if result.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending deployment not found")
        return {"id": deployment_id, "status": "revoked"}

    @app.get("/api/v1/install/{platform}/{token}", response_class=PlainTextResponse)
    def installer_bootstrap(platform: str, token: str, request: Request) -> str:
        if platform not in {"windows", "linux"}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported platform")
        deployment = pending_deployment(token, platform)
        with connection(app_settings.database_path) as conn:
            conn.execute("UPDATE deployments SET downloaded_at = COALESCE(downloaded_at, ?) WHERE id = ?", (utc_now(), deployment["id"]))
        base_url = public_url(request)
        download_url = f"{base_url}/api/v1/packages/{platform}/{token}"
        if platform == "windows":
            return f'''$ErrorActionPreference = 'Stop'
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{ throw 'Run PowerShell as Administrator.' }}
$package = Join-Path $env:TEMP 'mini-edr-agent.msi'
Invoke-WebRequest -Uri '{download_url}' -OutFile $package
Start-Process msiexec.exe -Wait -ArgumentList '/i', $package, '/qn', 'SERVER_URL={base_url}', 'DEPLOYMENT_TOKEN={token}', 'AGENT_NAME={deployment["agent_name"]}'
Write-Host 'mini-EDR agent installed. The service starts automatically.'
'''
        return f'''#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" -eq 0 || {{ echo 'Run this installer with sudo.'; exit 1; }}
package=/tmp/mini-edr-agent.deb
curl --fail --silent --show-error --location '{download_url}' --output "$package"
DEBIAN_FRONTEND=noninteractive dpkg -i "$package"
mini-edr-agent configure --server-url '{base_url}' --deployment-token '{token}' --agent-name '{deployment["agent_name"]}'
systemctl enable --now mini-edr-agent
echo 'mini-EDR agent installed. The service starts automatically.'
'''

    @app.get("/api/v1/packages/{platform}/{token}")
    def download_package(platform: str, token: str) -> FileResponse:
        if platform not in {"windows", "linux"}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported platform")
        pending_deployment(token, platform)
        path = package_path(platform)
        if not path.is_file():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Agent package is not published on this server")
        return FileResponse(path, filename=path.name, media_type="application/octet-stream")

    @app.post("/api/v1/agents/enroll", status_code=status.HTTP_201_CREATED)
    def enroll(request: EnrollmentRequest) -> dict:
        deployment = pending_deployment(request.deployment_token, request.platform)
        agent_id = str(uuid.uuid4())
        agent_token = secrets.token_urlsafe(32)
        now = utc_now()
        with connection(app_settings.database_path) as conn:
            conn.execute(
                """INSERT INTO agents(id, agent_name, hostname, platform, agent_version, token_hash, enrolled_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (agent_id, deployment["agent_name"], request.hostname, request.platform, request.agent_version,
                 token_digest(agent_token), now, now),
            )
            result = conn.execute(
                """UPDATE deployments SET status = 'active', enrolled_at = ?, agent_id = ?
                   WHERE id = ? AND status = 'pending'""",
                (now, agent_id, deployment["id"]),
            )
            if result.rowcount != 1:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Deployment token was already used")
        return {"agent_id": agent_id, "agent_name": deployment["agent_name"], "agent_token": agent_token}

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

    @app.post("/api/v1/agents/heartbeat")
    def agent_heartbeat(agent: dict = Depends(authenticate_agent)) -> dict:
        return {"status": "ok", "agent_id": agent["id"]}

    @app.get("/api/v1/agents", dependencies=[Depends(authenticate_admin)])
    def agents() -> list[dict]:
        return list_agents(app_settings.database_path)

    @app.get("/api/v1/alerts", dependencies=[Depends(authenticate_admin)])
    def alerts(limit: int = 100) -> list[dict]:
        return list_alerts(app_settings.database_path, max(1, min(limit, 250)))

    @app.patch("/api/v1/alerts/{alert_id}", dependencies=[Depends(authenticate_admin)])
    def update_alert(alert_id: str, update: AlertStatusUpdate) -> dict:
        with connection(app_settings.database_path) as conn:
            cursor = conn.execute("UPDATE alerts SET status = ? WHERE id = ?", (update.status, alert_id))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
        return {"id": alert_id, "status": update.status}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(_: Request) -> HTMLResponse:
        return HTMLResponse((ROOT / "server" / "templates" / "index.html").read_text(encoding="utf-8"))

    return app


app = create_app()
