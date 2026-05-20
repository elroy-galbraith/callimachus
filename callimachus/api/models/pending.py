"""Pending-submission models for the approval queue."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class EntityCardOut(BaseModel):
    """A single extracted entity as the Dashboard renders it.

    Mirrors the YAML frontmatter that ``vault_writer`` emits, plus the
    vault-relative filename so the UI can deep-link to the markdown.
    """

    filename: str
    cls: str | None = None  # YAML 'class' (Python keyword renamed)
    label: str | None = None
    source_section: str | None = None
    source_page: int | None = None
    source_text: str | None = None
    properties: dict[str, Any] = {}


class PendingSubmissionOut(BaseModel):
    doc_id: str
    backend: str
    handle: str
    review_url: str | None = None
    entities: list[EntityCardOut]


class RejectIn(BaseModel):
    reason: str = "Rejected via UI"
