"""Pending-submissions router — list, approve, reject.

Wraps ``project.approval`` (filesystem or git). Each pending ref is
hydrated with its entity-card data so the Dashboard can render the
proposed entities without a second round-trip.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from callimachus.api.deps import get_project
from callimachus.api.models import EntityCardOut, PendingSubmissionOut, RejectIn
from callimachus.api.vault_view import entity_card_from_path, vault_files_for
from callimachus.approval import SubmissionRef
from callimachus.project import Project

router = APIRouter(tags=["pending"])


def _find_ref(project: Project, handle: str) -> SubmissionRef:
    """Look up a SubmissionRef by handle in the project's pending list.

    ``project.approval.approve / reject`` only need the handle + backend +
    doc_id off the ref; we don't keep refs around between requests, so
    we re-list and match.
    """
    for ref in project.approval.list_pending():
        if ref.handle == handle:
            return ref
    raise HTTPException(404, f"no pending submission with handle {handle!r}")


@router.get(
    "/projects/{name}/pending",
    response_model=list[PendingSubmissionOut],
)
def list_pending(project: Project = Depends(get_project)) -> list[PendingSubmissionOut]:
    try:
        refs = project.approval.list_pending()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"failed to list pending: {exc}")
    out: list[PendingSubmissionOut] = []
    for ref in refs:
        files = vault_files_for(project, ref.doc_id)
        entities: list[EntityCardOut] = [entity_card_from_path(p) for p in files]
        out.append(
            PendingSubmissionOut(
                doc_id=ref.doc_id,
                backend=ref.backend,
                handle=ref.handle,
                review_url=ref.review_url,
                entities=entities,
            )
        )
    return out


@router.post(
    "/projects/{name}/pending/{handle}/approve",
    status_code=204,
)
def approve(
    handle: str,
    project: Project = Depends(get_project),
) -> None:
    ref = _find_ref(project, handle)
    try:
        project.approval.approve(ref)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"approve failed: {exc}")


@router.post(
    "/projects/{name}/pending/{handle}/reject",
    status_code=204,
)
def reject(
    handle: str,
    body: RejectIn | None = None,
    project: Project = Depends(get_project),
) -> None:
    ref = _find_ref(project, handle)
    reason = (body.reason if body else "Rejected via UI")
    try:
        project.approval.reject(ref, reason)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"reject failed: {exc}")
