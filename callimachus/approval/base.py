"""ApprovalBackend ABC and the two simple value types it traffics in."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Submission:
    """A batch of vault files awaiting review for a single document."""

    doc_id: str
    vault_files: list[Path]
    pdf_path: Path | None = None
    pack_name: str = ""
    prompt_version: str = ""
    model: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


@dataclass
class SubmissionRef:
    """An opaque handle returned by submit() and consumed by approve/reject."""

    backend: str  # "filesystem" | "git"
    handle: str   # branch name OR audit-log row id
    review_url: str | None = None  # optional file:// or http:// link
    status: str = "PENDING"        # PENDING | APPROVED | REJECTED
    doc_id: str = ""


class ApprovalBackend(ABC):
    """Pluggable workflow for getting human sign-off on extracted entities."""

    name: str

    @abstractmethod
    def submit(self, sub: Submission) -> SubmissionRef:
        """Persist a submission. Returns a handle for later approval/rejection."""

    @abstractmethod
    def list_pending(self) -> list[SubmissionRef]:
        """All submissions awaiting human action."""

    @abstractmethod
    def approve(self, ref: SubmissionRef) -> None:
        """Mark a submission accepted. Idempotent — calling twice is fine."""

    @abstractmethod
    def reject(self, ref: SubmissionRef, reason: str) -> None:
        """Mark a submission rejected. May move files into a quarantine area."""
