"""Collect basic system information and log it once on startup."""
import json
import platform
import socket
import requests

import psutil

from agent.utils.logger import get_logger
from agent.config.settings import BACKEND_URL


def collect_system_info(logger=None):
    logger = logger or get_logger()
    try:
        info = {
            "hostname": socket.gethostname(),
            "os": platform.system(),
            "os_version": platform.version(),
            "platform": platform.platform(),
            "cpu_count": psutil.cpu_count(logical=True),
            "total_memory": psutil.virtual_memory().total,
        }
        logger.info("SYSTEM_INFO | " + json.dumps(info))

        # Register agent with central server
        register_url = BACKEND_URL.replace("/api/logs", "/api/register")
        try:
            requests.post(register_url, json={
                "hostname": info["hostname"],
                "os": info["os"],
                "os_version": info["os_version"],
                "cpu_count": info["cpu_count"],
                "total_memory": info["total_memory"],
            }, timeout=5)
        except Exception:
            pass  # Server may not be reachable yet

        return info
    except Exception:
        logger.exception("Failed to collect system information")
        return {}
