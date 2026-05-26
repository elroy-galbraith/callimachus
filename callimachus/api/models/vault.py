"""Vault browser models — per-document summary + single-file content."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from callimachus.api.models.pending import EntityCardOut


class VaultDocumentOut(BaseModel):
    """One row in the document list — the left pane of the vault browser."""

    doc_id: str
    source_document: str | None = None
    entity_count: int
    classes: list[str]


class VaultListOut(BaseModel):
    documents: list[VaultDocumentOut]


class VaultDocumentDetailOut(BaseModel):
    """The middle pane: entities extracted from one source document."""

    doc_id: str
    source_document: str | None = None
    entities: list[EntityCardOut]


class VaultFileOut(BaseModel):
    """The right pane: full markdown content of a single vault file."""

    filename: str
    frontmatter: dict[str, Any] = {}
    body: str
