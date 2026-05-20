"""Consolidator-proposal request/response models."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


ProposalOperation = Literal[
    "merge_entities", "group_codes", "link_hierarchy", "rename_label"
]
ProposalStatus = Literal["pending", "approved", "rejected", "deferred", "applied"]
ProposalConfidence = Literal["high", "medium", "low"]


class ProposalOut(BaseModel):
    proposal_id: str
    operation: ProposalOperation
    status: ProposalStatus
    confidence: ProposalConfidence
    payload: dict[str, Any]
    rationale: str
    evidence: list[str]
    reviewer_notes: str | None = None
    created_at: str | None = None
    model_snapshot: str | None = None
    dot: str | None = None
    payload_summary: str
    filename: str  # vault-relative path to the proposal markdown


class ProposalListOut(BaseModel):
    proposals: list[ProposalOut]
    counts: dict[str, int]  # by status: pending/approved/rejected/deferred/applied


class ProposalStatusIn(BaseModel):
    status: ProposalStatus
    reviewer_notes: str | None = None


class ApplyResultOut(BaseModel):
    proposal_id: str
    operation: str
    ok: bool
    message: str
    touched: list[str]


class ApplyJobResultOut(BaseModel):
    """What the apply-approved job lands in ``JobState.result``."""

    results: list[ApplyResultOut]
    succeeded: int
    failed: int


class ConsolidatorJobResultOut(BaseModel):
    """What the consolidator job lands in ``JobState.result``."""

    proposals_written: int
    paths: list[str]
