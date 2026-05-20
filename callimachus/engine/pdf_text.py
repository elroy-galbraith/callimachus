"""Document text extraction with optional page-number tracking.

Dispatch by file extension:
    .pdf            → docling (preferred) or pdfplumber fallback, with page map
    .txt .md .vtt   → plain UTF-8 read, no page map

The two-tuple return shape (flat_text, page_texts_dict) is preserved
across both paths. Page-text dict is empty for text inputs, so
find_page_for_text harmlessly returns None for every entity (vault writer
then omits source_page from the frontmatter).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def extract_text_docling(pdf_path: Path) -> tuple[str, dict[int, str]]:
    """Returns (flat_markdown_for_llm, {page_no: page_text}) using docling.

    The page map enables clickable "page N" provenance links.
    """
    from docling.document_converter import DocumentConverter  # type: ignore

    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    doc = result.document
    pages: dict[int, list[str]] = {}
    for item, _level in doc.iterate_items():
        text = (getattr(item, "text", "") or "").strip()
        if not text:
            continue
        prov = getattr(item, "prov", None)
        if not prov:
            continue
        page_no = prov[0].page_no
        pages.setdefault(page_no, []).append(text)
    page_texts = {p: "\n".join(parts) for p, parts in pages.items()}
    flat = doc.export_to_markdown()
    return flat, page_texts


def extract_text_pdfplumber(pdf_path: Path) -> tuple[str, dict[int, str]]:
    """Returns (flat_text, {page_no: page_text}) using pdfplumber."""
    import pdfplumber  # type: ignore

    page_texts: dict[int, str] = {}
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text:
                page_texts[i] = text
    flat = "\n\n".join(page_texts[p] for p in sorted(page_texts))
    return flat, page_texts


def extract_text(pdf_path: Path) -> tuple[str, dict[int, str]]:
    try:
        flat, pages = extract_text_docling(pdf_path)
        print(
            f"[extractor] text extracted via docling ({len(flat)} chars, {len(pages)} pages)",
            file=sys.stderr,
        )
        return flat, pages
    except ImportError:
        pass
    except Exception as e:
        print(f"[extractor] docling failed ({e}), trying pdfplumber…", file=sys.stderr)

    try:
        flat, pages = extract_text_pdfplumber(pdf_path)
        print(
            f"[extractor] text extracted via pdfplumber ({len(flat)} chars, {len(pages)} pages)",
            file=sys.stderr,
        )
        return flat, pages
    except ImportError:
        pass

    print("ERROR: no PDF extractor available. Install docling or pdfplumber.", file=sys.stderr)
    sys.exit(1)


_TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".vtt", ".srt"}


def extract_input(path: Path) -> tuple[str, dict[int, str]]:
    """Dispatch on file extension. Returns (flat_text, page_map).

    For text-shaped inputs the page_map is empty; the engine then writes
    entities without source_page (which is appropriate for transcripts,
    journals, prose where "page" isn't the right granularity).
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text(path)
    if suffix in _TEXT_EXTENSIONS:
        body = path.read_text(encoding="utf-8")
        print(
            f"[extractor] text input read ({len(body)} chars, no page map)",
            file=sys.stderr,
        )
        return body, {}
    # Library code shouldn't kill the interpreter — raise so the caller
    # (CLI shim, UI, tests) can surface the problem in context.
    raise ValueError(
        f"Unsupported input extension {suffix!r}. "
        f"Add it to pack.inbox.accepted_extensions and a handler in "
        f"callimachus.engine.pdf_text.extract_input."
    )


def _normalize_for_match(text: str) -> str:
    """Lowercase, collapse whitespace, and strip quote characters and punctuation
    that commonly differ between PDF OCR output and statutory text snippets."""
    text = text.lower()
    text = re.sub(r"[‘’“”`'\"]+", "", text)
    text = re.sub(r"[\s\-–—.,;:()]+", " ", text)
    return text.strip()


def find_page_for_text(source_text: str, page_texts: dict[int, str]) -> int | None:
    """Locate which PDF page a source_text snippet came from.

    Two-stage match:
        1. Substring search of the normalised snippet in normalised page text.
        2. If that fails for long snippets (≥40 chars), retry with the first
           ~30 chars only — handles cases where extracted text wraps across
           a layout boundary that the PDF text stream preserves but the
           normalised page text doesn't.
    """
    if not source_text or not page_texts:
        return None

    needle = _normalize_for_match(source_text)
    if not needle:
        return None

    for page_no in sorted(page_texts):
        haystack = _normalize_for_match(page_texts[page_no])
        if needle in haystack:
            return page_no

    if len(needle) >= 40:
        short_needle = needle[:30]
        for page_no in sorted(page_texts):
            haystack = _normalize_for_match(page_texts[page_no])
            if short_needle in haystack:
                return page_no

    return None
