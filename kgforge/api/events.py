"""Server-Sent Events helpers.

One generic stream over a ``JobState`` covers every job kind. The SSE
generator is sync (not async) — FastAPI runs it on a worker thread, which
keeps the ``Condition.wait`` blocking call compatible with the rest of
the sync engine code.

Used by routers in Phase B+. The skeleton is here in Phase A so the job
contract is settled before we lean on it.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Iterator

from fastapi.responses import StreamingResponse

from kgforge.api.jobs import JobState


def _serialise_event(event_name: str, payload: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"


def sse_stream(state: JobState, heartbeat_seconds: float = 5.0) -> StreamingResponse:
    """Stream a JobState as ``text/event-stream``.

    Emits ``progress`` events for each new ``JobEvent`` and a final ``end``
    event when the job reaches ``done``/``error``. A comment-line heartbeat
    every ``heartbeat_seconds`` keeps reverse proxies from killing the
    connection on quiet jobs.
    """

    def gen() -> Iterator[str]:
        last_idx = 0
        while True:
            with state.cond:
                state.cond.wait(timeout=heartbeat_seconds)
                new_events = state.progress[last_idx:]
                last_idx = len(state.progress)
                terminal = state.status in ("done", "error")
                snapshot_status = state.status
            for ev in new_events:
                yield _serialise_event("progress", asdict(ev))
            if not new_events:
                # SSE comment line — keeps the connection warm without
                # showing up as a real event to ``EventSource`` consumers.
                yield ": heartbeat\n\n"
            if terminal:
                yield _serialise_event("end", {"status": snapshot_status})
                return

    return StreamingResponse(gen(), media_type="text/event-stream")
