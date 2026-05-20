"""In-process job registry for long-running engine operations.

Designed for the single-user local-dev case. Jobs live in a dict on
``app.state.jobs``; restart drops everything. The append-only ``progress``
list plus ``threading.Condition`` lets the SSE endpoint stream events
without polling.

Not durable, not multi-process, no cancellation. If those become
requirements, swap this module for a Redis/Celery-backed registry — the
public surface (create / get / emit / set_status) is small on purpose.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

JobStatus = Literal["queued", "running", "done", "error"]
JobLevel = Literal["info", "warn", "error"]


@dataclass
class JobEvent:
    ts: float
    level: JobLevel
    message: str
    data: dict[str, Any] | None = None


@dataclass
class JobState:
    id: str
    kind: str
    status: JobStatus = "queued"
    progress: list[JobEvent] = field(default_factory=list)
    result: Any | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    # Condition guards progress/status mutations and notifies SSE waiters.
    cond: threading.Condition = field(
        default_factory=threading.Condition, repr=False, compare=False
    )

    def emit(self, level: JobLevel, message: str, data: dict | None = None) -> None:
        with self.cond:
            self.progress.append(JobEvent(time.time(), level, message, data))
            self.cond.notify_all()

    def set_status(
        self,
        status: JobStatus,
        *,
        result: Any | None = None,
        error: str | None = None,
    ) -> None:
        with self.cond:
            self.status = status
            if result is not None:
                self.result = result
            if error is not None:
                self.error = error
            self.cond.notify_all()

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-safe view, excluding the threading primitive."""
        with self.cond:
            return {
                "id": self.id,
                "kind": self.kind,
                "status": self.status,
                "progress": [asdict(e) for e in self.progress],
                "result": self.result,
                "error": self.error,
                "created_at": self.created_at,
            }


class JobRegistry:
    """Process-local job table.

    ``create()`` opportunistically prunes done/error jobs older than
    ``max_age_seconds`` so the dict can't grow forever in a long-running
    dev session.
    """

    def __init__(self, max_age_seconds: float = 3600.0) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = threading.Lock()
        self._max_age = max_age_seconds

    def create(self, kind: str) -> JobState:
        state = JobState(id=uuid.uuid4().hex, kind=kind)
        with self._lock:
            self._prune_locked()
            self._jobs[state.id] = state
        return state

    def get(self, job_id: str) -> JobState | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _prune_locked(self) -> None:
        cutoff = time.time() - self._max_age
        stale = [
            k for k, v in self._jobs.items()
            if v.created_at < cutoff and v.status in ("done", "error")
        ]
        for k in stale:
            self._jobs.pop(k, None)
