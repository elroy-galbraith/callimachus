"""Proposals router — list, status PATCH, run-consolidator job, apply job.

Consolidator and apply are both jobs (they're slow LLM / file-system
operations); list and PATCH stay sync since they only touch a handful
of markdown files.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from kgforge.api.deps import get_jobs, get_project
from kgforge.api.jobs import JobRegistry, JobState
from kgforge.api.models import (
    ApplyJobResultOut,
    ApplyResultOut,
    ConsolidatorJobResultOut,
    ProposalListOut,
    ProposalOut,
    ProposalStatusIn,
)
from kgforge.api.proposal_view import (
    VALID_STATUSES,
    find_proposal_file,
    payload_summary,
    proposal_dot,
)
from kgforge.engine.consolidator import (
    consolidate as run_consolidator_engine,
    list_proposal_files,
    load_proposal_file,
    set_proposal_status,
    write_proposal_files,
)
from kgforge.engine.proposal_applier import apply_approved
from kgforge.project import Project

router = APIRouter(tags=["proposals"])

# Operation-specific payload keys, mirrored from
# consolidator._to_proposal. The proposal markdown files store these as
# flat top-level frontmatter; we re-nest them into ``payload`` on the
# wire so the React typing has one place to look.
_PAYLOAD_KEYS = {
    "merge_entities": ("kept_id", "removed_id"),
    "group_codes": ("new_subtheme_label", "parent_theme_id", "member_code_ids"),
    "link_hierarchy": ("from_id", "property", "to_id"),
    "rename_label": ("entity_id", "new_label"),
}


def _to_proposal_out(path: Path, project: Project) -> ProposalOut | None:
    meta = load_proposal_file(path)
    if not meta:
        return None
    op = meta.get("operation", "?")
    payload = {k: meta.get(k) for k in _PAYLOAD_KEYS.get(op, ()) if k in meta}
    try:
        rel_filename = str(path.relative_to(project.vault_dir))
    except ValueError:
        rel_filename = path.name
    return ProposalOut(
        proposal_id=meta.get("proposal_id", path.stem),
        operation=op,
        status=meta.get("status", "pending"),
        confidence=meta.get("confidence", "medium"),
        payload=payload,
        rationale=meta.get("rationale", ""),
        evidence=meta.get("evidence") or [],
        reviewer_notes=meta.get("reviewer_notes"),
        created_at=meta.get("created_at"),
        model_snapshot=meta.get("model_snapshot"),
        dot=proposal_dot(meta),
        payload_summary=payload_summary(meta),
        filename=rel_filename,
    )


@router.get(
    "/projects/{name}/proposals",
    response_model=ProposalListOut,
)
def list_proposals(project: Project = Depends(get_project)) -> ProposalListOut:
    proposals: list[ProposalOut] = []
    for path in list_proposal_files(project.vault_dir):
        out = _to_proposal_out(path, project)
        if out is not None:
            proposals.append(out)
    counts: dict[str, int] = {s: 0 for s in VALID_STATUSES}
    for p in proposals:
        counts[p.status] = counts.get(p.status, 0) + 1
    return ProposalListOut(proposals=proposals, counts=counts)


@router.patch(
    "/projects/{name}/proposals/{proposal_id}",
    response_model=ProposalOut,
)
def patch_proposal(
    proposal_id: str,
    body: ProposalStatusIn,
    project: Project = Depends(get_project),
) -> ProposalOut:
    """Set ``status`` and optionally ``reviewer_notes`` on a proposal.

    Reviewer notes are preserved when ``reviewer_notes`` is omitted —
    matching the engine's ``set_proposal_status`` semantics.
    """
    path = find_proposal_file(project.vault_dir, proposal_id)
    if path is None:
        raise HTTPException(404, f"no proposal with id {proposal_id!r}")
    try:
        set_proposal_status(path, body.status, reviewer_notes=body.reviewer_notes)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    out = _to_proposal_out(path, project)
    if out is None:
        raise HTTPException(500, "proposal file became unreadable after patch")
    return out


@router.post(
    "/projects/{name}/proposals/run",
    status_code=202,
)
def kick_consolidator(
    bg: BackgroundTasks,
    project: Project = Depends(get_project),
    jobs: JobRegistry = Depends(get_jobs),
) -> dict[str, str]:
    """Run the LLM consolidator over the vault and write proposal files.

    Existing decisions (``status: approved`` etc.) are preserved across
    re-runs by ``write_proposal_files`` (proposal fingerprinting). The
    job emits one event per stage so the SSE drawer can show progress.
    """
    job = jobs.create("consolidator")
    bg.add_task(_run_consolidator_job, job, project)
    return {"job_id": job.id}


def _run_consolidator_job(job: JobState, project: Project) -> None:
    job.set_status("running")
    try:
        job.emit(
            "info",
            f"Calling consolidator via {project.pack.models.ask}…",
            {"stage": "consolidate", "model": project.pack.models.ask},
        )
        proposals = run_consolidator_engine(project.vault_dir, project.pack)
        job.emit(
            "info",
            f"LLM returned {len(proposals)} proposal(s)",
            {"stage": "consolidate.done", "count": len(proposals)},
        )

        paths = write_proposal_files(
            proposals,
            project.vault_dir,
            model_snapshot=project.pack.models.ask,
        )
        job.emit(
            "info",
            f"Wrote {len(paths)} proposal file(s)",
            {"stage": "write.done", "count": len(paths)},
        )
        out = ConsolidatorJobResultOut(
            proposals_written=len(paths),
            paths=[str(p.relative_to(project.vault_dir)) for p in paths],
        )
        job.set_status("done", result=out.model_dump(mode="json"))
    except Exception as exc:  # noqa: BLE001
        job.emit("error", f"consolidator failed: {exc}")
        job.set_status("error", error=str(exc))


@router.post(
    "/projects/{name}/proposals/apply",
    status_code=202,
)
def kick_apply(
    bg: BackgroundTasks,
    project: Project = Depends(get_project),
    jobs: JobRegistry = Depends(get_jobs),
) -> dict[str, str]:
    """Apply every proposal with ``status == approved`` to the vault."""
    job = jobs.create("apply_proposals")
    bg.add_task(_run_apply_job, job, project)
    return {"job_id": job.id}


def _run_apply_job(job: JobState, project: Project) -> None:
    job.set_status("running")
    try:
        job.emit("info", "Applying approved proposals…")
        results = apply_approved(project.vault_dir, project.pack)
        # Emit one event per result so the drawer reflects per-proposal status.
        succeeded = 0
        for r in results:
            level = "info" if r.ok else "error"
            icon = "ok" if r.ok else "failed"
            job.emit(
                level,
                f"  {icon}: {r.operation} — {r.message}",
                {
                    "proposal_id": r.proposal_id,
                    "operation": r.operation,
                    "ok": r.ok,
                    "touched": r.touched,
                },
            )
            if r.ok:
                succeeded += 1
        out = ApplyJobResultOut(
            results=[ApplyResultOut(**asdict(r)) for r in results],
            succeeded=succeeded,
            failed=len(results) - succeeded,
        )
        job.set_status("done", result=out.model_dump(mode="json"))
    except Exception as exc:  # noqa: BLE001
        job.emit("error", f"apply failed: {exc}")
        job.set_status("error", error=str(exc))
