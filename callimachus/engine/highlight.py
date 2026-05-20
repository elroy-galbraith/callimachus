"""Inject yellow highlight annotations into source PDFs at extracted-text locations.

Lifted from scripts/highlight.py. The legal-definition term-name regex
moves to the compliance pack's hooks.py; this module's _search_variants
falls back to a generic longest-prefix matcher when the hook is absent.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import yaml

try:
    import fitz  # PyMuPDF
except ImportError as _exc:
    # Library modules must not sys.exit — re-raise so callers (CLI shim, UI,
    # tests) can decide how to surface the missing dependency.
    raise ImportError(
        "pymupdf is required by callimachus.engine.highlight. "
        "Install with: pip install pymupdf"
    ) from _exc

from callimachus.pack import DomainPack

HIGHLIGHT_COLOR = (1.0, 0.95, 0.4)
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _annot_title(pack: DomainPack) -> str:
    return f"{pack.prefix}:provenance"


def _clear_existing_highlights(doc: "fitz.Document", marker: str) -> int:
    """Remove highlights previously created by this script (idempotency)."""
    removed = 0
    for page in doc:
        targets = []
        for annot in page.annots() or []:
            try:
                if (annot.info or {}).get("title") == marker:
                    targets.append(annot)
            except Exception:
                continue
        for annot in targets:
            page.delete_annot(annot)
            removed += 1
    return removed


def _default_search_variants(source_text: str) -> list[str]:
    """Generic fallback when the pack does not provide a custom hook.

    Returns longer-prefix snippets of the (quote-stripped) source text. Less
    surgical than the legal-definition regex, but works for any domain.
    """
    if not source_text:
        return []
    full = source_text.strip()
    no_quotes = re.sub(r"[‘’“”`'\"]+", "", full)
    variants: list[str] = []
    for length in (80, 50, 30):
        v = no_quotes[:length].strip()
        if len(v) >= 15 and v not in variants:
            variants.append(v)
    return variants


def _search_variants(source_text: str, pack: DomainPack) -> list[str]:
    """Use the pack's custom hook if present; else the generic fallback."""
    hook = None
    if pack.hooks_module is not None:
        hook = getattr(pack.hooks_module, "search_variants", None)
    if hook is not None:
        return hook(source_text)
    return _default_search_variants(source_text)


def _find_rects(page: "fitz.Page", source_text: str, pack: DomainPack) -> list["fitz.Rect"]:
    """Try multiple needle variants until one returns a non-empty rect list."""
    for needle in _search_variants(source_text, pack):
        rects = page.search_for(needle)
        if rects:
            return rects
    return []


def _collect_entities(vault_dir: Path, doc_id: str) -> list[dict]:
    """Read all vault/*.md whose source_document == doc_id and have a source_page."""
    entities = []
    for path in sorted(vault_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            continue
        if meta.get("source_document") != doc_id:
            continue
        page = meta.get("source_page")
        src = meta.get("source_text")
        if not page or not src:
            continue
        entities.append(
            {
                "file": path.name,
                "eid": meta.get("id", path.stem),
                "label": meta.get("label", path.stem),
                "page": int(page),
                "source_text": src,
            }
        )
    return entities


def highlight_pdf(
    pdf_path: Path,
    vault_dir: Path,
    doc_id: str,
    pack: DomainPack,
) -> tuple[int, int]:
    """Generate one highlighted PDF per vault entity for doc_id.

    The pristine source PDF at `pdf_path` is kept clean (any prior provenance
    highlights are cleared). For each entity, a copy is written alongside as
    `<entity_id>.pdf` with exactly one yellow highlight at the matched location.
    Returns (matched_count, unmatched_count).
    """
    marker = _annot_title(pack)
    src = fitz.open(pdf_path)
    cleared = _clear_existing_highlights(src, marker)
    if cleared:
        print(
            f"[highlight] cleared {cleared} prior {marker} annotations on source",
            file=sys.stderr,
        )
        # Write cleared source via a sibling temp file + atomic rename so an
        # interrupted save can't truncate the original PDF. (We only persist
        # to disk when we actually changed something — for the no-prior-
        # annotations case, the src.write() below still gives us the bytes
        # we need for the per-entity copies without touching pdf_path.)
        tmp_path = pdf_path.with_suffix(pdf_path.suffix + ".tmp")
        src.save(str(tmp_path), encryption=fitz.PDF_ENCRYPT_KEEP)
        src.close()
        os.replace(tmp_path, pdf_path)
        src = fitz.open(pdf_path)
    pristine_bytes = src.write()
    src.close()

    entities = _collect_entities(vault_dir, doc_id)
    if not entities:
        print(f"[highlight] no entities found for doc_id={doc_id} in {vault_dir}", file=sys.stderr)
        return 0, 0

    # Clean up stale per-entity PDFs (idempotent re-runs).
    for stale in pdf_path.parent.glob(f"{doc_id}_*.pdf"):
        stale.unlink()

    matched = 0
    unmatched = 0
    for entity in entities:
        out_path = pdf_path.parent / f"{entity['eid']}.pdf"
        out_path.write_bytes(pristine_bytes)
        doc = fitz.open(out_path)
        page = doc[entity["page"] - 1]
        rects = _find_rects(page, entity["source_text"], pack)
        if not rects:
            doc.close()
            out_path.unlink()
            print(f"  no rect match: {entity['file']} (page {entity['page']})")
            unmatched += 1
            continue
        annot = page.add_highlight_annot(rects)
        annot.set_colors(stroke=HIGHLIGHT_COLOR)
        annot.set_info(title=marker, content=entity["label"], subject=entity["file"])
        annot.update()
        doc.save(out_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        doc.close()
        matched += 1
        print(
            f"  wrote {out_path.name} (page {entity['page']}, "
            f"{len(rects)} rect{'s' if len(rects) != 1 else ''})"
        )

    return matched, unmatched
