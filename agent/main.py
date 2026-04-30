"""Agent entrypoint: start monitors and collect system info."""
import threading
import time
import sys

from agent.utils.logger import get_logger
from agent.config.settings import MONITORED_PATHS, PROCESS_POLL_INTERVAL
from agent.core.process_monitor import ProcessMonitor
from agent.core.file_monitor import FileMonitor
from agent.core.network_monitor import NetworkMonitor
from agent.core.registry_monitor import RegistryMonitor
from agent.core.system_info import collect_system_info


def main():
    logger = get_logger()
    stop_event = threading.Event()

    # Collect system info once at startup
    collect_system_info(logger)
    logger.info("AGENT STARTED")

    # Instantiate monitors
    proc_monitor = ProcessMonitor(stop_event=stop_event, poll_interval=PROCESS_POLL_INTERVAL, logger=logger)
    file_monitor = FileMonitor(paths=MONITORED_PATHS, stop_event=stop_event, logger=logger)
    net_monitor = NetworkMonitor(stop_event=stop_event, poll_interval=1.0, logger=logger)
    reg_monitor = RegistryMonitor(stop_event=stop_event, poll_interval=5.0, logger=logger)

    # Run monitors in separate threads
    t_proc = threading.Thread(target=proc_monitor.start, name="ProcessMonitor")
    t_file = threading.Thread(target=file_monitor.start, name="FileMonitor")
    t_net = threading.Thread(target=net_monitor.start, name="NetworkMonitor")
    t_reg = threading.Thread(target=reg_monitor.start, name="RegistryMonitor")

    t_proc.start()
    t_file.start()
    t_net.start()
    t_reg.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown requested, stopping monitors")
        stop_event.set()
        t_proc.join(timeout=5)
        t_file.join(timeout=5)
        t_net.join(timeout=5)
        t_reg.join(timeout=5)
    except Exception:
        logger.exception("Agent encountered an unexpected error")
        stop_event.set()
    finally:
        logger.info("AGENT STOPPED")


if __name__ == "__main__":
    main()
