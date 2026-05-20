"""Inbox watcher: PDF lands → extract → archive → highlight → submit for review.

Lifted from scripts/curator.py. Two key changes from the legacy version:
1. The extractor runs in-process via callimachus.engine.extractor.extract — no
   subprocess. An exception in extract is caught and logged; the PDF moves
   to vault/sources/.errors/ so the watchdog loop continues.
2. Branch creation + commit + PR-message logic is delegated to the
   project's ApprovalBackend — the curator no longer hardcodes git.
"""
from __future__ import annotations

import logging
import shutil
import sys
import threading
import time
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from callimachus.approval import ApprovalBackend, Submission
from callimachus.engine import extractor as extractor_engine
from callimachus.engine import highlight as highlight_engine
from callimachus.pack import DomainPack

log = logging.getLogger("callimachus.curator")


def doc_id_from_path(pdf_path: Path) -> str:
    stem = pdf_path.stem.lower()
    return stem.replace("-", "_").replace(" ", "_")


def archive_pdf(pdf_path: Path, sources_dir: Path) -> Path:
    sources_dir.mkdir(parents=True, exist_ok=True)
    dest = sources_dir / pdf_path.name
    if dest.exists():
        dest.unlink()
    shutil.move(str(pdf_path), dest)
    log.info("archived %s -> %s", pdf_path.name, dest)
    return dest


def quarantine_pdf(pdf_path: Path, sources_dir: Path) -> Path:
    """Move a PDF whose extraction failed to vault/sources/.errors/<name>."""
    err_dir = sources_dir / ".errors"
    err_dir.mkdir(parents=True, exist_ok=True)
    dest = err_dir / pdf_path.name
    if dest.exists():
        dest.unlink()
    shutil.move(str(pdf_path), dest)
    log.warning("quarantined %s -> %s", pdf_path.name, dest)
    return dest


def inject_highlights(archived_pdf: Path, vault_dir: Path, doc_id: str, pack: DomainPack) -> None:
    """Run highlight injection on the archived PDF (best-effort)."""
    try:
        matched, unmatched = highlight_engine.highlight_pdf(archived_pdf, vault_dir, doc_id, pack)
        log.info(
            "highlights: matched=%d unmatched=%d on %s",
            matched, unmatched, archived_pdf.name,
        )
    except Exception as e:
        log.warning("highlight injection failed for %s: %s", archived_pdf.name, e)


def process_pdf(
    pdf_path: Path,
    *,
    pack: DomainPack,
    vault_dir: Path,
    sources_dir: Path,
    approval: ApprovalBackend,
    prompt_version: str = "extractor-v1",
) -> None:
    """End-to-end pipeline for a single PDF.

    extract → submit-to-approval → archive → highlight. On failure, the PDF
    is moved into a quarantine subfolder so the watch loop keeps running.
    """
    log.info("=" * 50)
    log.info("processing: %s", pdf_path.name)

    doc_id = doc_id_from_path(pdf_path)
    try:
        result = extractor_engine.extract(
            pack,
            pdf_path=pdf_path,
            doc_id=doc_id,
            prompt_version=prompt_version,
            vault_dir=vault_dir,
            dry_run=False,
        )
    except Exception as exc:
        log.error("extractor failed for %s: %s", pdf_path.name, exc)
        quarantine_pdf(pdf_path, sources_dir)
        return

    vault_files: list[Path] = result  # type: ignore[assignment]
    if not vault_files:
        log.warning("extractor produced no vault files for %s", doc_id)
        return

    # Archive PDF before submitting so per-entity highlight files end up
    # in the same directory as the source.
    archived = archive_pdf(pdf_path, sources_dir)

    sub = Submission(
        doc_id=doc_id,
        vault_files=vault_files,
        pdf_path=archived,
        pack_name=pack.metadata.name,
        prompt_version=prompt_version,
        model=pack.models.extractor,
    )
    ref = approval.submit(sub)

    inject_highlights(archived, vault_dir, doc_id, pack)

    log.info("=" * 50)
    log.info("PROPOSAL READY")
    log.info("  backend: %s", ref.backend)
    log.info("  handle:  %s", ref.handle)
    log.info("  doc_id:  %s", ref.doc_id)
    log.info("  files:   %d", len(vault_files))
    if ref.review_url:
        log.info("  review:  %s", ref.review_url)
    log.info("=" * 50)


# ── Watchdog handler ──────────────────────────────────────────────────────────


class _InboxHandler(FileSystemEventHandler):
    """Dispatch each new file to a worker thread so the observer thread
    stays responsive. The worker waits a short settle-time for the writer
    to finish flushing before extraction starts (PDF copies can arrive in
    multiple write events)."""

    SETTLE_SECONDS = 1.0

    def __init__(self, **kwargs):
        super().__init__()
        self.kwargs = kwargs

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in self.kwargs["pack"].inbox.accepted_extensions:
            return

        def _worker() -> None:
            # Settle: give the producer a beat to finish writing. Done in a
            # worker thread so the watchdog observer keeps draining events.
            time.sleep(self.SETTLE_SECONDS)
            try:
                process_pdf(path, **self.kwargs)
            except Exception as exc:
                log.error("unhandled error processing %s: %s", path.name, exc)

        threading.Thread(target=_worker, name=f"curator-{path.stem}",
                         daemon=True).start()


def process_existing(inbox_dir: Path, **kwargs) -> None:
    pdfs = sorted(p for p in inbox_dir.iterdir()
                  if p.suffix.lower() in kwargs["pack"].inbox.accepted_extensions)
    if not pdfs:
        log.info("no input files found in %s", inbox_dir)
        return
    for pdf in pdfs:
        try:
            process_pdf(pdf, **kwargs)
        except Exception as exc:
            log.error("failed: %s - %s", pdf.name, exc)


def watch(
    inbox_dir: Path,
    *,
    pack: DomainPack,
    vault_dir: Path,
    sources_dir: Path,
    approval: ApprovalBackend,
    prompt_version: str = "extractor-v1",
) -> None:
    """Block on the watchdog loop until Ctrl-C."""
    inbox_dir.mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        pack=pack,
        vault_dir=vault_dir,
        sources_dir=sources_dir,
        approval=approval,
        prompt_version=prompt_version,
    )
    process_existing(inbox_dir, **kwargs)

    log.info("watching %s for new files (Ctrl-C to stop)", inbox_dir)
    handler = _InboxHandler(**kwargs)
    observer = Observer()
    observer.schedule(handler, str(inbox_dir), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    log.info("curator stopped.")
