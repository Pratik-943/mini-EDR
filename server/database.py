from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection(database_path: Path) -> Iterator[sqlite3.Connection]:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize(database_path: Path) -> None:
    with connection(database_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL UNIQUE,
                hostname TEXT NOT NULL,
                platform TEXT NOT NULL,
                agent_version TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                enrolled_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL REFERENCES agents(id),
                received_at TEXT NOT NULL,
                event_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL REFERENCES agents(id),
                rule_id TEXT NOT NULL,
                title TEXT NOT NULL,
                severity TEXT NOT NULL,
                mitre TEXT,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL,
                evidence_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS deployments (
                id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL UNIQUE,
                platform TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                downloaded_at TEXT,
                enrolled_at TEXT,
                agent_id TEXT REFERENCES agents(id)
            );
            CREATE INDEX IF NOT EXISTS idx_events_agent_received ON events(agent_id, received_at DESC);
            CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status, expires_at);
            """
        )

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(agents)").fetchall()}
        if "agent_name" not in columns:
            conn.execute("ALTER TABLE agents ADD COLUMN agent_name TEXT")
            conn.execute("UPDATE agents SET agent_name = hostname WHERE agent_name IS NULL")


def add_event(conn: sqlite3.Connection, agent_id: str, event: dict) -> None:
    conn.execute(
        "INSERT INTO events(agent_id, received_at, event_json) VALUES (?, ?, ?)",
        (agent_id, utc_now(), json.dumps(event, separators=(",", ":"))),
    )


def list_agents(database_path: Path) -> list[dict]:
    with connection(database_path) as conn:
        rows = conn.execute(
            "SELECT id, agent_name, hostname, platform, agent_version, enrolled_at, last_seen_at FROM agents ORDER BY last_seen_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def list_alerts(database_path: Path, limit: int = 100) -> list[dict]:
    with connection(database_path) as conn:
        rows = conn.execute(
            """SELECT a.*, ag.hostname, ag.platform FROM alerts a
               JOIN agents ag ON ag.id = a.agent_id
               ORDER BY a.created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    result = []
    for row in rows:
        alert = dict(row)
        alert["evidence"] = json.loads(alert.pop("evidence_json"))
        result.append(alert)
    return result
