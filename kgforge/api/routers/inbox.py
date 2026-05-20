"""Inbox router — upload, list, clear, process-job.

``POST /inbox/process`` is the second job in the system (after NL ask)
and the first that emits *per-file* progress events. The orchestrator
catches per-file failures and keeps going, mirroring the Streamlit
behaviour where a bad PDF doesn't abort the rest of the batch.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
)

from kgforge.api.deps import get_jobs, get_project
from kgforge.api.jobs import JobRegistry, JobState
from kgforge.api.models import (
    InboxClearOut,
    InboxFileOut,
    InboxListOut,
    InboxUploadOut,
)
from kgforge.engine import chunker as chunker_engine
from kgforge.engine import curator as curator_engine
from kgforge.project import Project

router = APIRouter(tags=["inbox"])

# Same convention as 2_Dashboard.py — these we can cheaply chunk-preview
# in the UI without running the full PDF pipeline.
_TEXT_LIKE = {".txt", ".md", ".vtt"}


def _file_view(path: Path, max_chars: int) -> InboxFileOut:
    size = path.stat().st_size
    suffix = path.suffix.lower()
    is_text = suffix in _TEXT_LIKE
    n_chars: int | None = None
    n_chunks: int | None = None
    if is_text:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            n_chars = len(text)
            if n_chars > max_chars:
                n_chunks = chunker_engine.estimate_chunks(text, max_chars)
        except OSError:
            pass
    return InboxFileOut(
        name=path.name,
        size_bytes=size,
        suffix=suffix,
        is_text_like=is_text,
        n_chars=n_chars,
        n_chunks_estimate=n_chunks,
    )


def _list_inbox(project: Project) -> list[Path]:
    if not project.inbox_dir.exists():
        return []
    accepted = {e.lower() for e in project.pack.inbox.accepted_extensions}
    return sorted(
        p for p in project.inbox_dir.iterdir()
        if p.is_file() and p.suffix.lower() in accepted
    )


@router.get("/projects/{name}/inbox", response_model=InboxListOut)
def list_inbox(project: Project = Depends(get_project)) -> InboxListOut:
    max_chars = project.pack.prompt.text_window_chars
    return InboxListOut(
        files=[_file_view(p, max_chars) for p in _list_inbox(project)],
        accepted_extensions=list(project.pack.inbox.accepted_extensions),
        text_window_chars=max_chars,
    )


@router.post(
    "/projects/{name}/inbox/upload",
    response_model=InboxUploadOut,
    status_code=201,
)
async def upload_inbox(
    files: list[UploadFile] = File(...),
    project: Project = Depends(get_project),
) -> InboxUploadOut:
    """Save uploaded files into the project inbox.

    Rejects files whose extension isn't in ``pack.inbox.accepted_extensions``;
    they appear in ``skipped`` rather than failing the whole batch.
    """
    project.ensure_dirs()
    accepted = {e.lower() for e in project.pack.inbox.accepted_extensions}
    max_chars = project.pack.prompt.text_window_chars

    saved: list[InboxFileOut] = []
    skipped: list[dict[str, str]] = []
    for up in files:
        # ``Path(name).name`` strips any traversal segments a malicious
        # client might send (foo/../../etc/passwd → passwd).
        safe_name = Path(up.filename or "upload").name
        if not safe_name:
            skipped.append({"name": up.filename or "", "reason": "empty filename"})
            continue
        ext = Path(safe_name).suffix.lower()
        if ext not in accepted:
            skipped.append(
                {
                    "name": safe_name,
                    "reason": (
                        f"extension {ext!r} not in accepted_extensions "
                        f"({sorted(accepted)})"
                    ),
                }
            )
            continue
        dest = project.inbox_dir / safe_name
        dest.write_bytes(await up.read())
        saved.append(_file_view(dest, max_chars))
    return InboxUploadOut(saved=saved, skipped=skipped)


@router.delete("/projects/{name}/inbox", response_model=InboxClearOut)
def clear_inbox(project: Project = Depends(get_project)) -> InboxClearOut:
    deleted = 0
    for f in _list_inbox(project):
        try:
            f.unlink()
            deleted += 1
        except OSError:
            continue
    return InboxClearOut(deleted=deleted)


@router.post("/projects/{name}/inbox/process", status_code=202)
def kick_process(
    bg: BackgroundTasks,
    project: Project = Depends(get_project),
    jobs: JobRegistry = Depends(get_jobs),
) -> dict[str, str]:
    """Process every file currently in the inbox. Returns ``{job_id}``.

    Each file runs ``curator.process_pdf`` in turn; per-file failures
    are caught and surfaced as ``error``-level progress events so the
    rest of the batch can finish.
    """
    files = _list_inbox(project)
    if not files:
        raise HTTPException(400, "inbox is empty")
    job = jobs.create("process_inbox")
    bg.add_task(_run_process, job, project, files)
    return {"job_id": job.id}


def _run_process(job: JobState, project: Project, files: list[Path]) -> None:
    job.set_status("running")
    succeeded = 0
    failed: list[dict[str, str]] = []
    job.emit("info", f"Processing {len(files)} file(s)…", {"total": len(files)})
    try:
        for f in files:
            job.emit("info", f"→ {f.name}", {"file": f.name})
            try:
                curator_engine.process_pdf(
                    f,
                    pack=project.pack,
                    vault_dir=project.vault_dir,
                    sources_dir=project.sources_dir,
                    approval=project.approval,
                )
                succeeded += 1
                job.emit(
                    "info",
                    f"  submitted {f.name}",
                    {"file": f.name, "status": "submitted"},
                )
            except Exception as exc:  # noqa: BLE001
                failed.append({"file": f.name, "error": str(exc)})
                job.emit(
                    "error",
                    f"  failed {f.name}: {exc}",
                    {"file": f.name, "error": str(exc)},
                )
        job.set_status(
            "done",
            result={
                "processed": len(files),
                "succeeded": succeeded,
                "failed": len(failed),
                "errors": failed,
            },
        )
    except Exception as exc:  # noqa: BLE001
        job.emit("error", f"orchestrator crashed: {exc}")
        job.set_status("error", error=str(exc))
