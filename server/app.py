from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any
import uvicorn
from loguru import logger
import json
import os

app = FastAPI(title="Mini-EDR Central Backend")

# We will save logs to a backend log file
SERVER_LOGS_DIR = "server_logs"
os.makedirs(SERVER_LOGS_DIR, exist_ok=True)
logger.add(os.path.join(SERVER_LOGS_DIR, "edr_alerts.log"), rotation="10 MB")

class LogEntry(BaseModel):
    message: str
    record: Dict[str, Any]

@app.post("/api/logs")
async def receive_log(request: Request, entry: LogEntry):
    client_host = request.client.host if request.client else "Unknown"
    # Simply log the received message using the server's logger
    if "ALERT" in entry.message:
        logger.warning(f"[ENDPOINT: {client_host}] RECEIVED ALERT: {entry.message}")
    else:
        logger.info(f"[ENDPOINT: {client_host}] RECEIVED LOG: {entry.message}")
    return {"status": "success"}

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
    
    # Mock at least 1 endpoint if empty for testing
    if len(endpoints) == 0: endpoints.add("192.168.1.100")
        
    return {"alerts": alerts, "endpoints_count": len(endpoints), "endpoints_list": list(endpoints)}

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
