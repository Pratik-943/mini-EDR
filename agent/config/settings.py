"""Agent configuration settings"""
from pathlib import Path

# Directories and paths
BASE_DIR = Path(__file__).resolve().parents[1]
LOG_FILE = str(BASE_DIR / "logs" / "agent.log")

# What to monitor
MONITORED_PATHS = [r"C:\Users"]

# Polling intervals (seconds)
PROCESS_POLL_INTERVAL = 1.0
SLEEP_INTERVAL = 1.0

# Backend Configuration
BACKEND_URL = "http://<YOUR_SERVER_IP>:8000/api/logs"
