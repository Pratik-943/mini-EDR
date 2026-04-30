"""Process monitor: detect new process creation using psutil."""
import time
import threading
from typing import Optional

import psutil

from agent.utils.logger import get_logger


class ProcessMonitor:
    def __init__(self, stop_event: threading.Event, poll_interval: float = 1.0, logger=None):
        self.stop_event = stop_event
        self.poll_interval = poll_interval
        self.logger = logger or get_logger()

    def start(self) -> None:
        """Start monitoring processes. This method is intended to run in a thread."""
        self.logger.info("ProcessMonitor starting")

        try:
            known_pids = set(psutil.pids())
        except Exception:
            self.logger.exception("Failed to list initial processes")
            known_pids = set()

        while not self.stop_event.is_set():
            try:
                current_pids = set(psutil.pids())
                new_pids = current_pids - known_pids

                for pid in new_pids:
                    try:
                        proc = psutil.Process(pid)
                        name = proc.name()
                        # Log in required format
                        self.logger.info(f"PROCESS_START | PID={pid} | NAME={name}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        # Process disappeared or access denied; skip
                        continue
                    except Exception:
                        self.logger.exception("Error retrieving process info for PID %s", pid)

                known_pids = current_pids
            except Exception:
                self.logger.exception("ProcessMonitor encountered an error")

            time.sleep(self.poll_interval)
