from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any
import uvicorn
from loguru import logger
import json
import os
import asyncio
import requests

OLLAMA_MODEL = "llama3.2:1b"
sequence_buffer = {}
agent_registry = {}  # { ip: { hostname, os, registered_at, last_seen } }

REGISTRY_FILE = "server_logs/agent_registry.json"

def load_registry():
    global agent_registry
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r") as f:
                agent_registry = json.load(f)
        except Exception:
            agent_registry = {}

def save_registry():
    try:
        with open(REGISTRY_FILE, "w") as f:
            json.dump(agent_registry, f, indent=2)
    except Exception:
        pass

app = FastAPI(title="Mini-EDR Central Backend")

# We will save logs to a backend log file
SERVER_LOGS_DIR = "server_logs"
os.makedirs(SERVER_LOGS_DIR, exist_ok=True)
logger.add(os.path.join(SERVER_LOGS_DIR, "edr_alerts.log"), rotation="10 MB")

# Load persisted agent registry on startup
load_registry()

class LogEntry(BaseModel):
    message: str
    record: Dict[str, Any]

class AgentInfo(BaseModel):
    hostname: str
    os: str
    os_version: str
    cpu_count: int
    total_memory: int

@app.post("/api/register")
async def register_agent(request: Request, info: AgentInfo):
    """Called once by the agent on startup to register itself."""
    from datetime import datetime
    client_host = request.client.host if request.client else "Unknown"
    agent_registry[client_host] = {
        "hostname": info.hostname,
        "os": info.os,
        "os_version": info.os_version,
        "cpu_count": info.cpu_count,
        "total_memory_gb": round(info.total_memory / (1024**3), 1),
        "registered_at": datetime.utcnow().isoformat(),
        "last_seen": datetime.utcnow().isoformat(),
        "ip": client_host,
    }
    save_registry()  # Persist to disk so it survives server restarts
    logger.info(f"[ENDPOINT: {client_host}] AGENT_REGISTERED | HOST={info.hostname} | OS={info.os}")
    return {"status": "registered"}

def classify_threat(message: str) -> str:
    """Classify a log message into a threat level."""
    msg = message.upper()
    if any(k in msg for k in ["YARA_MATCH", "FILE_QUARANTINED", "MIMIKATZ", "RANSOMWARE", "SHELLCODE"]):
        return "critical"
    if any(k in msg for k in ["AI_DETECTED", "REGISTRY_MODIFIED", "PERSISTENCE", "PRIVILEGE"]):
        return "high"
    if any(k in msg for k in ["ALERT", "SUSPICIOUS", "MALWARE", "INTRUSION"]):
        return "medium"
    if any(k in msg for k in ["WARN"]):
        return "low"
    return "normal"

THREAT_ORDER = ["normal", "low", "medium", "high", "critical"]

async def analyze_sequence(client_host: str, logs: list):
    global OLLAMA_MODEL
    prompt = f"You are a Cybersecurity AI analyzing endpoint telemetry. Does this sequence of events indicate ransomware or malicious behavior? Reply ONLY with the word 'MALICIOUS' or 'BENIGN'. Sequence:\n{json.dumps(logs)}"
    try:
        def query_ollama():
            return requests.post("http://localhost:11434/api/generate", json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            }, timeout=10).json()
            
        res = await asyncio.to_thread(query_ollama)
        response_text = res.get("response", "").strip().upper()
        
        if "MALICIOUS" in response_text:
            logger.warning(f"[ENDPOINT: {client_host}] RECEIVED ALERT: AI_DETECTED_MALICIOUS_SEQUENCE | MODEL={OLLAMA_MODEL} | EVENTS={len(logs)}")
            # Escalate threat level to HIGH for AI detections
            if client_host in agent_registry:
                current = agent_registry[client_host].get("threat_level", "normal")
                if THREAT_ORDER.index("high") > THREAT_ORDER.index(current):
                    agent_registry[client_host]["threat_level"] = "high"
                    save_registry()
    except Exception:
        pass

@app.post("/api/logs")
async def receive_log(request: Request, entry: LogEntry):
    from datetime import datetime
    client_host = request.client.host if request.client else "Unknown"

    # Update last_seen and threat level for this endpoint
    if client_host in agent_registry:
        agent_registry[client_host]["last_seen"] = datetime.utcnow().isoformat()
        new_level = classify_threat(entry.message)
        current_level = agent_registry[client_host].get("threat_level", "normal")
        # Only escalate, never downgrade automatically
        if THREAT_ORDER.index(new_level) > THREAT_ORDER.index(current_level):
            agent_registry[client_host]["threat_level"] = new_level
            save_registry()

    # Add to sequence buffer
    if client_host not in sequence_buffer:
        sequence_buffer[client_host] = []
    sequence_buffer[client_host].append(entry.message)

    # If we have 5 events, run AI analysis
    if len(sequence_buffer[client_host]) >= 5:
        logs_to_analyze = sequence_buffer[client_host].copy()
        sequence_buffer[client_host] = []
        asyncio.create_task(analyze_sequence(client_host, logs_to_analyze))

    # Log the received message
    if "ALERT" in entry.message:
        logger.warning(f"[ENDPOINT: {client_host}] RECEIVED ALERT: {entry.message}")
    else:
        logger.info(f"[ENDPOINT: {client_host}] RECEIVED LOG: {entry.message}")
    return {"status": "success"}

class SettingsModel(BaseModel):
    model_name: str

@app.post("/api/settings/model")
async def set_model(settings: SettingsModel):
    global OLLAMA_MODEL
    OLLAMA_MODEL = settings.model_name
    return {"status": "success", "model": OLLAMA_MODEL}
    
@app.get("/api/settings/model")
async def get_model():
    return {"model": OLLAMA_MODEL}

@app.get("/api/alerts")
async def get_alerts():
    """Returns the most recent alerts and active endpoint count."""
    log_file = os.path.join(SERVER_LOGS_DIR, "edr_alerts.log")
    alerts = []
    endpoints = set()
    if os.path.exists(log_file):
        try:
            with open(log_file, "r") as f:
                lines = f.readlines()
                for line in reversed(lines[-500:]):
                    # Track unique endpoints seen recently
                    if "[ENDPOINT:" in line:
                        try:
                            ip = line.split("[ENDPOINT: ")[1].split("]")[0]
                            endpoints.add(ip)
                        except: pass

                    if "[ENDPOINT:" in line:
                        alerts.append(line.strip())
                        
                    # Keep only last 50 alerts
                    if len(alerts) > 50:
                        alerts = alerts[:50]
        except Exception as e:
            logger.error(f"Error reading logs: {e}")
    
    return {
        "alerts": alerts,
        "endpoints_count": len(agent_registry),
        "endpoints_list": list(agent_registry.values())
    }

class ActionRequest(BaseModel):
    action: str
    target: str

@app.post("/api/action")
async def perform_action(req: ActionRequest):
    """Handles remediation actions triggered from the dashboard."""
    logger.warning(f"DASHBOARD ACTION INITIATED | ACTION={req.action} | TARGET={req.target}")
    return {"status": "success", "message": f"Action {req.action} dispatched for {req.target}"}

@app.get("/api/endpoint/{client_ip}/logs")
async def get_endpoint_logs(client_ip: str):
    """Returns all logs for a specific endpoint IP."""
    log_file = os.path.join(SERVER_LOGS_DIR, "edr_alerts.log")
    logs = []
    search_ip = client_ip.replace("_", ".")  # allow URL-safe IP
    if os.path.exists(log_file):
        try:
            with open(log_file, "r") as f:
                for line in f.readlines():
                    if f"[ENDPOINT: {search_ip}]" in line:
                        logs.append(line.strip())
        except Exception as e:
            logger.error(f"Error reading logs for {search_ip}: {e}")
    return {"ip": search_ip, "logs": list(reversed(logs[-200:]))}

@app.post("/api/endpoint/{client_ip}/reset")
async def reset_endpoint_threat(client_ip: str):
    """Resets the threat level of an endpoint back to normal."""
    search_ip = client_ip.replace("_", ".")
    if search_ip in agent_registry:
        agent_registry[search_ip]["threat_level"] = "normal"
        save_registry()
        return {"status": "reset", "ip": search_ip}
    return {"status": "not_found"}

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Dashboard Not Found</h1><p>{e}</p>", status_code=404)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Return a minimal SVG shield icon to suppress browser 404 errors."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#00FF9C">'
        '<path d="M12 2L4 5v6c0 5.25 3.5 10.15 8 11.35C16.5 21.15 20 16.25 20 11V5l-8-3z"/>'
        "</svg>"
    )
    from fastapi.responses import Response
    return Response(content=svg, media_type="image/svg+xml")

from fastapi.responses import FileResponse

@app.get("/download/agent")
async def download_agent():
    """Serves the compiled universal agent.exe payload to endpoints."""
    base_dir = os.path.dirname(__file__)
    possible_paths = [
        os.path.abspath(os.path.join(base_dir, "payloads", "agent.exe")),
        os.path.abspath(os.path.join(base_dir, "..", "dist", "agent.exe")),
        os.path.abspath(os.path.join(base_dir, "..", "agent", "agent.exe")),
        os.path.abspath(os.path.join(base_dir, "..", "agent.exe"))
    ]
    for agent_path in possible_paths:
        if os.path.exists(agent_path):
            return FileResponse(path=agent_path, filename="agent.exe", media_type="application/x-msdownload")
    return HTMLResponse(content="Agent payload not found. Run GitHub Actions build first.", status_code=404)

@app.get("/deploy/dropper", response_class=HTMLResponse)
async def get_dropper(request: Request):
    """Returns a self-configuring PowerShell one-liner auto-filled with this server's URL."""
    host = request.headers.get("host", request.client.host)
    scheme = "https" if request.headers.get("x-forwarded-proto") == "https" else "http"
    server_url = f"{scheme}://{host}"

    dropper = (
        f'$s="{server_url}"; '
        f'Invoke-WebRequest -Uri "$s/download/agent" -OutFile "$env:TEMP\\agent.exe"; '
        f'Start-Process "$env:TEMP\\agent.exe" -ArgumentList "$s/api/logs" -WindowStyle Hidden'
    )

    html = f"""<!DOCTYPE html>
<html style="background:#0a0a0a;color:#fff;font-family:monospace;padding:40px">
<head><title>Mini-EDR | Deploy Agent</title></head>
<body>
<h2 style="color:#00FF9C">&#x1F6E1; Mini-EDR | Endpoint Deployment</h2>
<p style="color:#aaa">Run this command in <strong>PowerShell as Administrator</strong> on the target Windows machine:</p>
<div style="background:#1a1a1a;border:1px solid #333;border-radius:8px;padding:20px;word-break:break-all;cursor:pointer" onclick="navigator.clipboard.writeText(this.dataset.cmd)" data-cmd="{dropper}">
  <code style="color:#00C8FF;font-size:13px">{dropper}</code>
  <p style="color:#555;font-size:11px;margin-top:8px">Click to copy</p>
</div>
<p style="color:#555;font-size:12px;margin-top:20px">The agent silently installs, registers itself, and begins streaming live telemetry to your dashboard.</p>
<a href="/" style="color:#00FF9C">&#x2190; Back to Dashboard</a>
</body></html>"""
    return HTMLResponse(content=html)

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
