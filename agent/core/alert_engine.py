import os
import yara
from pathlib import Path
from agent.utils.logger import get_logger

class AlertEngine:
    def __init__(self, logger=None):
        self.logger = logger or get_logger()
        self.rules = None
        
        base_dir = Path(__file__).resolve().parents[1]
        self.rules_path = base_dir / "rules" / "suspicious.yar"
        
        try:
            if self.rules_path.exists():
                self.rules = yara.compile(filepath=str(self.rules_path))
                self.logger.info("YARA rules loaded successfully")
        except Exception:
            self.logger.exception("Failed to compile YARA rules")

    def scan_file(self, filepath: str):
        """Scans a file against loaded YARA rules and logs an ALERT if there's a match."""
        if not self.rules:
            return
            
        # VERY IMPORTANT: Do not scan our own log file or we create an infinite loop!
        if filepath.endswith(".log"):
            return
            
        try:
            # Check if file exists and is accessible
            if not os.path.exists(filepath):
                return
                
            # Quick check to avoid scanning large files or locked files
            if os.path.getsize(filepath) > 50 * 1024 * 1024: # Skip > 50MB
                return

            matches = self.rules.match(filepath)
            if matches:
                rule_names = [m.rule for m in matches]
                self.logger.warning(f"ALERT | YARA_MATCH | FILE={filepath} | RULES={','.join(rule_names)}")
                
                # Active Response: Quarantine / Remove the file!
                try:
                    os.remove(filepath)
                    self.logger.warning(f"ACTION | FILE_QUARANTINED | FILE={filepath}")
                except Exception as e:
                    self.logger.error(f"ACTION_FAILED | COULD NOT REMOVE FILE | FILE={filepath} | ERROR={e}")
                    
        except Exception:
            # Can happen if file is locked or deleted right after creation
            pass
