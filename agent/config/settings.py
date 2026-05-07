"""Agent configuration settings"""
import sys
import os
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
# Priority: 1) Command-line argument, 2) Environment variable, 3) Default server IP
if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
    BACKEND_URL = sys.argv[1]
elif os.environ.get("EDR_BACKEND_URL"):
    BACKEND_URL = os.environ["EDR_BACKEND_URL"]
else:
    BACKEND_URL = "http://54.206.252.28:8000/api/logs"
