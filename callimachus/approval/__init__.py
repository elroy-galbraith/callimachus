"""Approval backends: how does an extracted batch of entities get reviewed?

Two implementations ship today:
- FilesystemBackend (default): vault writes happen directly; an SQLite
  audit log records each submission; approve/reject mutate that log
  (and on reject, move the files to vault/.rejected/<doc_id>_<ts>/).
- GitBackend: extracted files land on a `proposals/<doc_id>` branch
  awaiting human merge. Mirrors the original carib-comp-ont workflow.

The Project model picks the backend by name; engine code never branches
on backend type.
"""
from callimachus.approval.base import ApprovalBackend, Submission, SubmissionRef
from callimachus.approval.filesystem import FilesystemBackend
from callimachus.approval.git import GitBackend

__all__ = [
    "ApprovalBackend",
    "Submission",
    "SubmissionRef",
    "FilesystemBackend",
    "GitBackend",
    "make_backend",
]


def make_backend(name: str, **kwargs) -> ApprovalBackend:
    """Factory: pick a backend by name (used by Project loaders)."""
    if name == "filesystem":
        return FilesystemBackend(**kwargs)
    if name == "git":
        return GitBackend(**kwargs)
    raise ValueError(f"unknown approval backend: {name!r}")
