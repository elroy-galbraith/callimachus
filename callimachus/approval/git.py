"""GitBackend — preserves the original carib-comp-ont workflow.

submit:   create branch `proposals/<doc_id>`, stage vault files, commit
          with the structured curator message.
approve:  checkout main, merge the branch.
reject:   delete the branch.

Used by the compliance project to keep the existing PR-as-mutation
methodology intact for the UWI demo.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

try:
    import git as _git  # gitpython
except ImportError:  # pragma: no cover - tested at install time
    _git = None  # type: ignore

from callimachus.approval.base import ApprovalBackend, Submission, SubmissionRef

log = logging.getLogger("callimachus.approval.git")


class GitBackend(ApprovalBackend):
    name = "git"

    def __init__(self, repo_root: Path) -> None:
        if _git is None:
            raise ImportError("gitpython is required for GitBackend. Install with: pip install gitpython")
        self.repo_root = Path(repo_root)
        self.repo = _git.Repo(self.repo_root)

    # ── ApprovalBackend API ─────────────────────────────────────────────────

    def submit(self, sub: Submission) -> SubmissionRef:
        branch_name = f"proposals/{sub.doc_id}"
        # Switch to main (or master) first
        try:
            self.repo.git.checkout("main")
        except _git.GitCommandError:
            try:
                self.repo.git.checkout("master")
            except _git.GitCommandError:
                pass

        # Create or reset the proposals branch
        if branch_name in [b.name for b in self.repo.branches]:
            log.info("branch %s already exists - resetting to HEAD", branch_name)
            self.repo.git.branch("-D", branch_name)
        self.repo.git.checkout("-b", branch_name)
        log.info("created branch %s", branch_name)

        # Stage files (paths relative to repo root). The git backend can only
        # commit files inside the repo working tree; surface a clear error if
        # a project misconfiguration points its vault elsewhere.
        rel_paths: list[str] = []
        for f in sub.vault_files:
            try:
                rel_paths.append(str(f.resolve().relative_to(self.repo_root.resolve())))
            except ValueError as exc:
                raise ValueError(
                    f"GitBackend cannot stage {f!r}: path is not inside the repo "
                    f"root {self.repo_root}. Move the vault into the repo or "
                    f"switch this project's approval backend to 'filesystem'."
                ) from exc
        self.repo.index.add(rel_paths)

        timestamp = sub.timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        commit_msg = (
            f"curator: extract {sub.doc_id} [{len(rel_paths)} entities]\n\n"
            f"source:         {sub.pdf_path.name if sub.pdf_path else 'n/a'}\n"
            f"prompt_version: {sub.prompt_version}\n"
            f"model_snapshot: {sub.model}\n"
            f"timestamp:      {timestamp}\n"
            f"validation:     PENDING - review before merging\n\n"
            f"Files:\n" + "\n".join(f"  {p}" for p in rel_paths)
        )
        self.repo.index.commit(commit_msg)
        log.info("committed %d file(s) on %s", len(rel_paths), branch_name)
        return SubmissionRef(
            backend=self.name,
            handle=branch_name,
            review_url=None,
            status="PENDING",
            doc_id=sub.doc_id,
        )

    def list_pending(self) -> list[SubmissionRef]:
        return [
            SubmissionRef(
                backend=self.name,
                handle=b.name,
                review_url=None,
                status="PENDING",
                doc_id=b.name.removeprefix("proposals/"),
            )
            for b in self.repo.branches
            if b.name.startswith("proposals/")
        ]

    def approve(self, ref: SubmissionRef) -> None:
        try:
            self.repo.git.checkout("main")
        except _git.GitCommandError:
            self.repo.git.checkout("master")
        self.repo.git.merge(ref.handle)
        log.info("merged %s", ref.handle)
        ref.status = "APPROVED"

    def reject(self, ref: SubmissionRef, reason: str) -> None:
        try:
            self.repo.git.checkout("main")
        except _git.GitCommandError:
            self.repo.git.checkout("master")
        self.repo.git.branch("-D", ref.handle)
        log.info("deleted branch %s (reason: %s)", ref.handle, reason)
        ref.status = "REJECTED"
