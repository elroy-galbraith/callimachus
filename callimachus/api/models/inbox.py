"""Inbox + processing models."""
from __future__ import annotations

from pydantic import BaseModel


class InboxFileOut(BaseModel):
    """A file currently in the inbox, with a cheap chunking estimate.

    Text-like files (.txt, .md, .vtt) get an accurate char count and
    chunk estimate; PDFs only show byte size since chunking happens
    post-extraction.
    """

    name: str
    size_bytes: int
    suffix: str
    is_text_like: bool
    n_chars: int | None = None
    n_chunks_estimate: int | None = None


class InboxListOut(BaseModel):
    files: list[InboxFileOut]
    accepted_extensions: list[str]
    text_window_chars: int


class InboxClearOut(BaseModel):
    deleted: int


class InboxUploadOut(BaseModel):
    saved: list[InboxFileOut]
    skipped: list[dict[str, str]]  # [{name, reason}]
