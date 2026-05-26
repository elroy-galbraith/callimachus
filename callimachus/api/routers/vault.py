"""Vault browser router — read-only views of the approved vault.

The vault is the canonical artifact: per-entity Markdown files written
by ``vault_writer`` after a submission is approved. These endpoints
mirror the value of pointing Obsidian at ``vault/`` — group the files by
source document, show what's inside each, render one file in full —
without the external dependency.

Editing is deliberately out of scope. Any vault mutation goes through
the Proposals flow.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from callimachus.api.deps import get_project
from callimachus.api.models import (
    EntityCardOut,
    VaultDocumentDetailOut,
    VaultDocumentOut,
    VaultFileOut,
    VaultListOut,
)
from callimachus.api.vault_view import (
    entity_card_from_path,
    list_vault_documents,
    read_frontmatter,
    read_vault_file,
    vault_files_for,
)
from callimachus.project import Project

router = APIRouter(tags=["vault"])

# Filenames are passed through the URL so we constrain them at the
# boundary. Vault files are written by ``vault_writer`` as plain ASCII
# slugs (``{doc_id}_e{N}.md``); anything outside this charset would not
# be a legitimate vault file. The pattern doubles as path-traversal
# defence even though ``read_vault_file`` resolves and checks containment.
_FILENAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._\-]*\.md$"

# Doc-ids inherit the same shape — they're either the slug used by
# ``vault_writer`` for filenames, or the value of ``source_document`` in
# frontmatter (set to the input filename's stem). Keep them filesystem-safe.
_DOC_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._\-]*$"


@router.get(
    "/projects/{name}/vault",
    response_model=VaultListOut,
)
def list_vault(project: Project = Depends(get_project)) -> VaultListOut:
    """Approved vault grouped by source document."""
    docs = [VaultDocumentOut(**d) for d in list_vault_documents(project)]
    return VaultListOut(documents=docs)


@router.get(
    "/projects/{name}/vault/documents/{doc_id}",
    response_model=VaultDocumentDetailOut,
)
def get_vault_document(
    doc_id: str = Path(..., pattern=_DOC_ID_PATTERN),
    project: Project = Depends(get_project),
) -> VaultDocumentDetailOut:
    """Entity cards for one source document.

    Same precedence as the Dashboard's pending view: filename prefix
    first, then frontmatter ``source_document`` as a fallback.
    """
    files = vault_files_for(project, doc_id)
    if not files:
        raise HTTPException(404, f"no vault entries for doc_id {doc_id!r}")
    entities: list[EntityCardOut] = [entity_card_from_path(p) for p in files]
    # source_document on disk may differ from the doc_id slug (the slug
    # is the filename prefix; source_document is the original filename).
    src = read_frontmatter(files[0]).get("source_document")
    return VaultDocumentDetailOut(
        doc_id=doc_id,
        source_document=src if isinstance(src, str) else None,
        entities=entities,
    )


@router.get(
    "/projects/{name}/vault/files/{filename}",
    response_model=VaultFileOut,
)
def get_vault_file(
    filename: str = Path(..., pattern=_FILENAME_PATTERN),
    project: Project = Depends(get_project),
) -> VaultFileOut:
    """Full markdown content of one vault file (frontmatter split out)."""
    out = read_vault_file(project, filename)
    if out is None:
        raise HTTPException(404, f"no vault file {filename!r}")
    return VaultFileOut(**out)
