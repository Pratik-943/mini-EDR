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

app = FastAPI(title="Mini-EDR Central Backend")

# We will save logs to a backend log file
SERVER_LOGS_DIR = "server_logs"
os.makedirs(SERVER_LOGS_DIR, exist_ok=True)
logger.add(os.path.join(SERVER_LOGS_DIR, "edr_alerts.log"), rotation="10 MB")

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
    logger.info(f"[ENDPOINT: {client_host}] AGENT_REGISTERED | HOST={info.hostname} | OS={info.os}")
    return {"status": "registered"}

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
    except Exception as e:
        # Silently fail if Ollama is not running or model not found
        pass

@app.post("/api/logs")
async def receive_log(request: Request, entry: LogEntry):
    from datetime import datetime
    client_host = request.client.host if request.client else "Unknown"

    # Update last_seen for this endpoint
    if client_host in agent_registry:
        agent_registry[client_host]["last_seen"] = datetime.utcnow().isoformat()
    
    # Add to sequence buffer
    if client_host not in sequence_buffer:
        sequence_buffer[client_host] = []
    
    sequence_buffer[client_host].append(entry.message)
    
    # If we have 5 events, run AI analysis
    if len(sequence_buffer[client_host]) >= 5:
        logs_to_analyze = sequence_buffer[client_host].copy()
        sequence_buffer[client_host] = []
        asyncio.create_task(analyze_sequence(client_host, logs_to_analyze))
        
    # Simply log the received message using the server's logger
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

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Dashboard Not Found</h1><p>{e}</p>", status_code=404)

from fastapi.responses import FileResponse

@app.get("/download/agent")
async def download_agent():
    """Serves the compiled agent.exe payload to endpoints."""
    base_dir = os.path.dirname(__file__)
    # Check multiple possible locations since users may build/place it differently
    possible_paths = [
        os.path.abspath(os.path.join(base_dir, "..", "agent", "agent.exe")),
        os.path.abspath(os.path.join(base_dir, "..", "dist", "agent.exe")),
        os.path.abspath(os.path.join(base_dir, "payloads", "agent.exe")),
        os.path.abspath(os.path.join(base_dir, "..", "agent.exe"))
    ]
    
    for agent_path in possible_paths:
        if os.path.exists(agent_path):
            return FileResponse(path=agent_path, filename="agent.exe", media_type="application/x-msdownload")
            
    return HTMLResponse(content="Agent payload not found on server.", status_code=404)

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
