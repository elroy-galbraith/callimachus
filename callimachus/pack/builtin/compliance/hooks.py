"""Compliance-pack hook overrides for the callimachus engine.

Phase B: moves the legal-definition term-name regex (formerly in
scripts/highlight.py L58-102) into the pack so the engine's highlight.py
stays domain-neutral. Other packs either omit hooks entirely (engine
falls back to a generic longest-prefix matcher) or ship their own
versions for transcript turns, paper sentences, etc.
"""
from __future__ import annotations

import re

# Match the leading quoted term in a statutory definition:
#   'biometric data' means …  → biometric data
#   "Court" means …           → Court
_TERM_NAME_RE = re.compile(
    r"^\s*['\"`‘“]+([^'\"`’”]+?)['\"`’”]+(?=\s*(?:,|means\b|is\b|shall\b|\Z))",
    re.IGNORECASE,
)


def _extract_term_name(source_text: str) -> str | None:
    if not source_text:
        return None
    m = _TERM_NAME_RE.match(source_text.strip())
    return m.group(1).strip() if m else None


def search_variants(source_text: str) -> list[str]:
    """PDF-search needles for highlighting, prioritising the quoted term name.

    Falls back to longer-prefix snippets when the source_text is not a
    statutory definition (no quoted term at the start).
    """
    if not source_text:
        return []
    full = source_text.strip()
    variants: list[str] = []

    term = _extract_term_name(full)
    if term:
        # Try quoted variants first — most specific to the definition line.
        variants.extend([f"'{term}'", f'"{term}"', f"‘{term}’", f"“{term}”"])
        variants.append(term)

    # Final fallback: longer prefixes (rarely match due to line wrapping, but cheap).
    no_quotes = re.sub(r"[‘’“”`'\"]+", "", full)
    for length in (50, 30):
        v = no_quotes[:length].strip()
        if len(v) >= 15:
            variants.append(v)

    # Dedupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out
