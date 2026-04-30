"""File monitor using watchdog to capture create/delete/modify events."""
import os
import time
import threading
from typing import List

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from agent.utils.logger import get_logger


from agent.core.alert_engine import AlertEngine

class FileEventHandler(FileSystemEventHandler):
    def __init__(self, logger=None):
        super().__init__()
        self.logger = logger or get_logger()
        self.alert_engine = AlertEngine(self.logger)

    def on_created(self, event):
        if event.is_directory:
            return
        self.logger.info(f"FILE_CREATED | {event.src_path}")
        self.alert_engine.scan_file(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        self.logger.info(f"FILE_DELETED | {event.src_path}")

    def on_modified(self, event):
        if event.is_directory:
            return
        self.logger.info(f"FILE_MODIFIED | {event.src_path}")
        self.alert_engine.scan_file(event.src_path)


class FileMonitor:
    def __init__(self, paths: List[str], stop_event: threading.Event, logger=None):
        self.paths = paths
        self.stop_event = stop_event
        self.logger = logger or get_logger()
        self.observer = Observer()
        self.handler = FileEventHandler(self.logger)

    def start(self) -> None:
        """Start the watchdog observer and watch configured paths."""
        self.logger.info("FileMonitor starting")

        for path in self.paths:
            try:
                if os.path.exists(path):
                    self.observer.schedule(self.handler, path, recursive=True)
                    self.logger.info(f"FileMonitor watching: {path}")
                else:
                    self.logger.warning(f"FileMonitor path does not exist: {path}")
            except Exception:
                self.logger.exception(f"Failed to schedule watcher for path: {path}")

        try:
            self.observer.start()
        except Exception:
            self.logger.exception("Failed to start file observer")
            return

        try:
            while not self.stop_event.is_set():
                time.sleep(1)
        except Exception:
            self.logger.exception("FileMonitor encountered an error")
        finally:
            try:
                self.observer.stop()
                self.observer.join()
            except Exception:
                self.logger.exception("Error stopping file observer")
