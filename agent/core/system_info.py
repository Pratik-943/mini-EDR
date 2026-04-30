"""Collect basic system information and log it once on startup."""
import json
import platform
import socket

import psutil

from agent.utils.logger import get_logger


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
        return info
    except Exception:
        logger.exception("Failed to collect system information")
        return {}
