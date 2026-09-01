from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    admin_token: str
    database_path: Path
    server_name: str
    max_batch_events: int = 250


def get_settings() -> Settings:
    database_setting = os.getenv("EDR_DATABASE_PATH", "data/mini_edr.db")
    database_path = Path(database_setting)
    if not database_path.is_absolute():
        database_path = ROOT / database_path
    return Settings(
        admin_token=os.getenv("EDR_ADMIN_TOKEN", ""),
        database_path=database_path,
        server_name=os.getenv("EDR_SERVER_NAME", "mini-EDR"),
    )
