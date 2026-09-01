from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class EnrollmentRequest(BaseModel):
    deployment_token: str = Field(min_length=24, max_length=512)
    hostname: str = Field(min_length=1, max_length=255)
    platform: Literal["windows", "linux"]
    agent_version: str = Field(min_length=1, max_length=64)


class DeploymentRequest(BaseModel):
    agent_name: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    platform: Literal["windows", "linux"]
    expires_in_minutes: int = Field(default=60, ge=5, le=1440)


class EndpointEvent(BaseModel):
    timestamp: datetime
    platform: Literal["windows", "linux"]
    category: str = Field(min_length=1, max_length=64)
    action: str = Field(min_length=1, max_length=64)
    process_name: str | None = Field(default=None, max_length=512)
    command_line: str | None = Field(default=None, max_length=4096)
    source: str = Field(min_length=1, max_length=256)
    raw_event_id: str | None = Field(default=None, max_length=128)
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator("category", "action", "process_name", "source", "raw_event_id", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class EventBatch(BaseModel):
    events: list[EndpointEvent] = Field(min_length=1, max_length=250)


class AlertStatusUpdate(BaseModel):
    status: Literal["new", "acknowledged", "closed", "false_positive"]
