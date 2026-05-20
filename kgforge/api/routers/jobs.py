"""Generic job-status + SSE stream endpoints.

Phase A: just the snapshot endpoint so ``main.py`` wires cleanly. The SSE
route uses ``events.sse_stream`` and lands here in Phase B when the first
job-emitting endpoint (NL ask) ships.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from kgforge.api.deps import get_jobs
from kgforge.api.events import sse_stream
from kgforge.api.jobs import JobRegistry
from kgforge.api.models import JobStateOut

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=JobStateOut)
def get_job(job_id: str, jobs: JobRegistry = Depends(get_jobs)) -> JobStateOut:
    state = jobs.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="no such job")
    return JobStateOut.model_validate(state.snapshot())


@router.get("/jobs/{job_id}/events")
def stream_job(job_id: str, jobs: JobRegistry = Depends(get_jobs)):
    state = jobs.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="no such job")
    return sse_stream(state)
