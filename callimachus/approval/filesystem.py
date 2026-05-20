"""FilesystemBackend — default approval workflow.

submit:   vault files are already on disk; a row is inserted in
          <project>/audit.sqlite recording the submission.
approve:  status row → APPROVED.
reject:   status row → REJECTED, vault files moved to vault/.rejected/
          <doc_id>_<ts>/ for safekeeping.

No git involvement. Suitable for solo researchers and for the Streamlit UI's
in-app approve/reject flow.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from callimachus.approval.base import ApprovalBackend, Submission, SubmissionRef

log = logging.getLogger("callimachus.approval.filesystem")


class FilesystemBackend(ApprovalBackend):
    name = "filesystem"

    def __init__(self, vault_dir: Path, audit_db: Path | None = None) -> None:
        self.vault_dir = Path(vault_dir)
        self.audit_db = Path(audit_db) if audit_db else self.vault_dir.parent / "audit.sqlite"
        self.rejected_dir = self.vault_dir / ".rejected"
        self._ensure_schema()

    # ── persistence ─────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        # timeout=10s: the curator and the Streamlit UI can both hold
        # connections to the same audit.sqlite. Without a timeout, concurrent
        # writes raise "database is locked" immediately; this lets the second
        # writer wait up to 10s for the first to release the lock.
        self.audit_db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.audit_db, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_id(self, ref: SubmissionRef) -> int:
        """Validate and unwrap a SubmissionRef into a row id, with a clear error."""
        if ref.backend != self.name:
            raise ValueError(
                f"{self.name} backend can't handle a ref from backend "
                f"{ref.backend!r} (handle={ref.handle!r})"
            )
        try:
            return int(ref.handle)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{self.name} backend expected an integer row-id handle, got "
                f"{ref.handle!r}"
            ) from exc

    def _ensure_schema(self) -> None:
        with self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS submissions (
                  id              INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp       TEXT    NOT NULL,
                  doc_id          TEXT    NOT NULL,
                  status          TEXT    NOT NULL CHECK(status IN ('PENDING','APPROVED','REJECTED')),
                  files_json      TEXT    NOT NULL,
                  pdf_path        TEXT,
                  pack_name       TEXT,
                  prompt_version  TEXT,
                  model           TEXT,
                  reviewer        TEXT,
                  notes           TEXT
                )
                """
            )

    # ── ApprovalBackend API ─────────────────────────────────────────────────

    def submit(self, sub: Submission) -> SubmissionRef:
        files_json = json.dumps([str(p) for p in sub.vault_files])
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO submissions
                  (timestamp, doc_id, status, files_json, pdf_path,
                   pack_name, prompt_version, model)
                VALUES (?, ?, 'PENDING', ?, ?, ?, ?, ?)
                """,
                (
                    sub.timestamp,
                    sub.doc_id,
                    files_json,
                    str(sub.pdf_path) if sub.pdf_path else None,
                    sub.pack_name,
                    sub.prompt_version,
                    sub.model,
                ),
            )
            row_id = cur.lastrowid
        log.info("submitted doc_id=%s as audit row %d", sub.doc_id, row_id)
        return SubmissionRef(
            backend=self.name,
            handle=str(row_id),
            review_url=self.audit_db.as_uri(),
            status="PENDING",
            doc_id=sub.doc_id,
        )

    def list_pending(self) -> list[SubmissionRef]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, doc_id FROM submissions WHERE status='PENDING' ORDER BY id"
            ).fetchall()
        return [
            SubmissionRef(
                backend=self.name,
                handle=str(r["id"]),
                review_url=self.audit_db.as_uri(),
                status="PENDING",
                doc_id=r["doc_id"],
            )
            for r in rows
        ]

    def approve(self, ref: SubmissionRef) -> None:
        row_id = self._row_id(ref)
        with self._conn() as c:
            c.execute(
                "UPDATE submissions SET status='APPROVED' WHERE id=?",
                (row_id,),
            )
        log.info("approved audit row %s (doc_id=%s)", ref.handle, ref.doc_id)
        ref.status = "APPROVED"

    def reject(self, ref: SubmissionRef, reason: str) -> None:
        row_id = self._row_id(ref)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        with self._conn() as c:
            row = c.execute(
                "SELECT doc_id, files_json FROM submissions WHERE id=?",
                (row_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"no submission with id={ref.handle}")
            files = [Path(p) for p in json.loads(row["files_json"])]
            dest_dir = self.rejected_dir / f"{row['doc_id']}_{ts}"

            # Pre-flight: confirm we can write to the destination before we
            # touch any source files. Files that already vanished are skipped
            # (idempotent retry) rather than failing the whole reject.
            present = [src for src in files if src.exists()]
            if present:
                dest_dir.mkdir(parents=True, exist_ok=True)
                if not os.access(dest_dir, os.W_OK):
                    raise PermissionError(
                        f"reject: dest_dir not writable: {dest_dir}"
                    )

            moved: list[Path] = []
            try:
                for src in present:
                    shutil.move(str(src), dest_dir / src.name)
                    moved.append(src)
            except OSError as exc:
                # Best-effort rollback: put back what we already moved so the
                # vault and the audit log stay consistent.
                for src in moved:
                    try:
                        shutil.move(str(dest_dir / src.name), str(src))
                    except OSError:
                        log.exception("rollback failed for %s", src)
                raise OSError(
                    f"reject: failed mid-move at file {len(moved) + 1}/"
                    f"{len(present)} (rolled back). Original error: {exc}"
                ) from exc

            c.execute(
                "UPDATE submissions SET status='REJECTED', notes=? WHERE id=?",
                (reason, row_id),
            )
        log.info("rejected audit row %s (doc_id=%s) → %s", ref.handle, ref.doc_id, dest_dir)
        ref.status = "REJECTED"
