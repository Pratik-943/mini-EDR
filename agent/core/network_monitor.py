"""Network monitor: detect new network connections using psutil."""
import time
import threading
from typing import Optional

import psutil

from agent.utils.logger import get_logger


class NetworkMonitor:
    def __init__(self, stop_event: threading.Event, poll_interval: float = 1.0, logger=None):
        self.stop_event = stop_event
        self.poll_interval = poll_interval
        self.logger = logger or get_logger()

    def _hash_conn(self, conn):
        laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
        raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""
        return f"{conn.pid}-{laddr}-{raddr}-{conn.status}"

    def start(self) -> None:
        """Start monitoring network connections. This method is intended to run in a thread."""
        self.logger.info("NetworkMonitor starting")

        try:
            known_conns = set()
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'ESTABLISHED':
                    known_conns.add(self._hash_conn(conn))
        except Exception:
            self.logger.exception("Failed to list initial network connections")
            known_conns = set()

        while not self.stop_event.is_set():
            try:
                current_conns = set()
                new_conns = []

                for conn in psutil.net_connections(kind='inet'):
                    if conn.status == 'ESTABLISHED':
                        conn_hash = self._hash_conn(conn)
                        current_conns.add(conn_hash)
                        if conn_hash not in known_conns:
                            new_conns.append(conn)

                for conn in new_conns:
                    try:
                        pid = conn.pid
                        laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
                        raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""

                        proc_name = "Unknown"
                        if pid:
                            try:
                                proc = psutil.Process(pid)
                                proc_name = proc.name()
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass

                        self.logger.info(
                            f"NETWORK_CONNECT | PID={pid} | NAME={proc_name} | "
                            f"LADDR={laddr} | RADDR={raddr} | STATUS={conn.status}"
                        )
                    except Exception:
                        pass

                known_conns = current_conns

            except psutil.AccessDenied:
                # Normal for connections belonging to processes owned by other users
                pass
            except Exception:
                self.logger.exception("NetworkMonitor encountered an error")

            time.sleep(self.poll_interval)
