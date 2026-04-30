import win32serviceutil
import win32service
import win32event
import servicemanager
import sys
import os
from pathlib import Path

# Ensure the agent package is in the path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from agent.main import main
from agent.utils.logger import get_logger

class MiniEDRService(win32serviceutil.ServiceFramework):
    _svc_name_ = "MiniEDR"
    _svc_display_name_ = "Mini Endpoint Detection and Response Agent"
    _svc_description_ = "Lightweight agent for monitoring system activity (Processes, Files, Network, Registry)."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.logger = get_logger()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.logger.info("Service stop signal received")
        # main() handles its own loop, we just need a way to stop it
        # The main script uses KeyboardInterrupt or its own stop_event. 
        # In this simplistic service, killing the process or letting it exit is managed by the OS.
        sys.exit(0)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, "")
        )
        self.logger.info("Service started")
        
        try:
            main()
        except Exception as e:
            self.logger.exception(f"Service crashed: {e}")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(MiniEDRService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(MiniEDRService)
