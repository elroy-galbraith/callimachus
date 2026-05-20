"""Dashboard — upload, extract, review/approve.

Same in-process pipeline as `python scripts/curator.py --once`, but each
step is a clickable action rather than an autonomous loop.
"""
from __future__ import annotations

import re
import traceback
from pathlib import Path

import streamlit as st
import yaml

from callimachus.engine import curator as curator_engine
from callimachus.engine import chunker as chunker_engine
from callimachus.project import Project
# Bootstrap: ensure ``callimachus_ui`` resolves when Streamlit deep-links
# directly to this page without running app.py first.
import sys as _sys
from pathlib import Path as _Path
for _p in _Path(__file__).resolve().parents:
    if _p.name == "legacy-streamlit":
        if str(_p) not in _sys.path:
            _sys.path.insert(0, str(_p))
        break

from callimachus_ui.helpers import api_key_warning, project_chip, require_project

# Text-like extensions we can cheaply preview-chunk in the UI without
# running the full PDF extraction pipeline.
_TEXT_LIKE = {".txt", ".md", ".vtt"}

# ── helpers (defined first so the page-flow code below can call them) ────────

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _read_frontmatter(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def _matches_doc_id(path: Path, doc_id: str) -> bool:
    return _read_frontmatter(path).get("source_document") == doc_id


def _vault_files_for(project: Project, doc_id: str) -> list[Path]:
    """Files belonging to a given doc_id. Filename-prefix match first; then
    fall back to scanning frontmatter for source_document."""
    by_prefix = sorted(project.vault_dir.glob(f"{doc_id}*.md"))
    if by_prefix:
        return by_prefix
    return sorted(p for p in project.vault_dir.glob("*.md") if _matches_doc_id(p, doc_id))


def _render_entity_card(path: Path, project: Project) -> None:
    meta = _read_frontmatter(path)
    if not meta:
        st.caption(f"⚠ {path.name}: missing frontmatter")
        return

    cls = meta.get("class", "?")
    label = meta.get("label", path.stem)
    section = meta.get("source_section", "")
    page = meta.get("source_page")
    text = meta.get("source_text", "")
    properties = meta.get("properties") or {}

    title = f"`{project.pack.prefix}:{cls}` — **{label}**"
    if section:
        title += f"  ·  {section}"
    if page:
        title += f"  ·  page {page}"

    with st.container(border=True):
        st.markdown(title)
        if text:
            st.markdown(f"> {text}")
        if properties:
            st.caption(" · ".join(f"{k} → {v}" for k, v in properties.items()))
        st.caption(f"_{path.name}_")


# ── page ─────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Dashboard · Callimachus", layout="wide")
project_chip()
api_key_warning()

project = require_project()
project.ensure_dirs()

st.title("📊 Dashboard")
st.caption(f"Project: **{project.label}** · backend: `{project.approval_config.get('backend')}`")

# 1 — Upload
st.subheader("1 — Drop documents")
extensions = project.pack.inbox.accepted_extensions
ext_label = ", ".join(extensions)
uploads = st.file_uploader(
    f"Accepted: {ext_label}",
    type=[e.lstrip(".") for e in extensions],
    accept_multiple_files=True,
    key="upload",
)
if uploads:
    saved = []
    for up in uploads:
        dest = project.inbox_dir / up.name
        dest.write_bytes(up.getbuffer())
        saved.append(dest.name)
    st.success(f"Saved to inbox: {', '.join(saved)}")

# 2 — Inbox + extraction
st.subheader("2 — Inbox")
inbox_files = (
    sorted(
        p for p in project.inbox_dir.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    )
    if project.inbox_dir.exists()
    else []
)

def _chunk_preview(path: Path, max_chars: int) -> str:
    """Render a one-line chunking estimate for a single file.

    Text-like files are read and char-counted exactly. PDFs are sized
    by bytes only - actual chunking happens after PDF→text extraction.
    """
    size_kb = path.stat().st_size / 1024
    if path.suffix.lower() in _TEXT_LIKE:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return f"`{path.name}` ({size_kb:,.1f} KB)"
        n_chars = len(text)
        if n_chars <= max_chars:
            return f"`{path.name}` ({n_chars:,} chars)"
        n_chunks = chunker_engine.estimate_chunks(text, max_chars)
        return (
            f"`{path.name}` ({n_chars:,} chars) - "
            f"will split into ~**{n_chunks}** chunks at natural boundaries"
        )
    return f"`{path.name}` ({size_kb:,.1f} KB) - PDF, chunked after text extraction if needed"


if not inbox_files:
    st.info(f"No files in `{project.inbox_dir.name}/`. Drop a document above to get started.")
else:
    max_chars = project.pack.prompt.text_window_chars
    cols = st.columns([3, 1, 1])
    with cols[0]:
        for f in inbox_files:
            st.markdown(f"- {_chunk_preview(f, max_chars)}")
        st.caption(
            f"Chunk window: **{max_chars:,} chars** "
            f"(set in `pack.yaml` → `prompt.text_window_chars`)"
        )
    with cols[1]:
        run_clicked = st.button(
            "⚙ Process all", type="primary", width="stretch",
            help="Extract entities from every file. Each becomes a pending submission below.",
        )
    with cols[2]:
        if st.button("🗑 Clear inbox", width="stretch"):
            for f in inbox_files:
                f.unlink()
            st.rerun()

    if run_clicked:
        with st.status(f"Processing {len(inbox_files)} file(s)…", expanded=True) as status:
            for f in inbox_files:
                st.write(f"→ {f.name}")
                try:
                    curator_engine.process_pdf(
                        f,
                        pack=project.pack,
                        vault_dir=project.vault_dir,
                        sources_dir=project.sources_dir,
                        approval=project.approval,
                    )
                    st.write("  ✅ submitted")
                except Exception as exc:
                    st.write(f"  ❌ failed: {exc}")
                    st.code(traceback.format_exc())
            status.update(label=f"Processed {len(inbox_files)} file(s)", state="complete")
        st.rerun()

# 3 — Pending review queue
st.subheader("3 — Pending review")
try:
    pending = project.approval.list_pending()
except Exception as exc:
    st.error(f"Failed to list pending submissions: {exc}")
    pending = []

if not pending:
    st.info("Nothing pending. Drop a file above and click **Process all** to populate the queue.")
else:
    st.caption(f"{len(pending)} submission(s) awaiting human review.")
    for ref in pending:
        with st.expander(
            f"📥 `{ref.doc_id}` · backend={ref.backend} · handle={ref.handle}",
            expanded=False,
        ):
            vault_files = _vault_files_for(project, ref.doc_id)
            st.caption(f"{len(vault_files)} entity file(s)")
            for vf in vault_files:
                _render_entity_card(vf, project)

            cols = st.columns([1, 1, 4])
            with cols[0]:
                if st.button("✅ Approve", key=f"approve_{ref.handle}",
                             type="primary", width="stretch"):
                    try:
                        project.approval.approve(ref)
                        st.success(f"Approved {ref.doc_id}")
                        st.rerun()
                    except Exception as exc:
                        st.exception(exc)
            with cols[1]:
                if st.button("❌ Reject", key=f"reject_{ref.handle}",
                             width="stretch"):
                    try:
                        project.approval.reject(ref, reason="Rejected via UI")
                        st.warning(f"Rejected {ref.doc_id}")
                        st.rerun()
                    except Exception as exc:
                        st.exception(exc)
