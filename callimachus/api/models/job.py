"""Job-state response models."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class JobEventOut(BaseModel):
    ts: float
    level: Literal["info", "warn", "error"]
    message: str
    data: dict[str, Any] | None = None


class JobStateOut(BaseModel):
    id: str
    kind: str
    status: Literal["queued", "running", "done", "error"]
    progress: list[JobEventOut]
    result: Any | None = None
    error: str | None = None
    created_at: float
