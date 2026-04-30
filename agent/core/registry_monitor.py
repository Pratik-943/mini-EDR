"""Registry monitor: detect changes to persistence-related registry keys."""
import time
import threading
import winreg
from typing import Dict, Any

from agent.utils.logger import get_logger


class RegistryMonitor:
    def __init__(self, stop_event: threading.Event, poll_interval: float = 5.0, logger=None):
        self.stop_event = stop_event
        self.poll_interval = poll_interval
        self.logger = logger or get_logger()

        # Monitor standard persistence keys
        self.keys_to_monitor = [
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce")
        ]

    def _read_key_values(self, hkey: int, subkey: str) -> Dict[str, Any]:
        """Reads all values from a given registry key."""
        values = {}
        try:
            with winreg.OpenKey(hkey, subkey, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        values[name] = value
                        i += 1
                    except OSError:
                        # No more values
                        break
        except FileNotFoundError:
            # Key might not exist, that's fine
            pass
        except Exception as e:
            self.logger.debug(f"Failed to read registry key {subkey}: {e}")
        return values

    def start(self) -> None:
        """Start monitoring registry keys. This method is intended to run in a thread."""
        self.logger.info("RegistryMonitor starting")

        known_state = {}
        for hkey, subkey in self.keys_to_monitor:
            known_state[(hkey, subkey)] = self._read_key_values(hkey, subkey)

        while not self.stop_event.is_set():
            try:
                for hkey, subkey in self.keys_to_monitor:
                    current_values = self._read_key_values(hkey, subkey)
                    old_values = known_state[(hkey, subkey)]
                    hkey_str = "HKLM" if hkey == winreg.HKEY_LOCAL_MACHINE else "HKCU"

                    # Check for new or modified values
                    for name, value in current_values.items():
                        if name not in old_values:
                            self.logger.info(
                                f"REGISTRY_ADDED | KEY={hkey_str}\\{subkey} | NAME={name} | VALUE={value}"
                            )
                        elif old_values[name] != value:
                            self.logger.info(
                                f"REGISTRY_MODIFIED | KEY={hkey_str}\\{subkey} | NAME={name} | NEW_VALUE={value}"
                            )

                    # Check for deleted values
                    for name in old_values:
                        if name not in current_values:
                            self.logger.info(
                                f"REGISTRY_DELETED | KEY={hkey_str}\\{subkey} | NAME={name}"
                            )

                    known_state[(hkey, subkey)] = current_values

            except Exception:
                self.logger.exception("RegistryMonitor encountered an error")

            time.sleep(self.poll_interval)
