"""Split long documents into ordered chunks at natural boundaries.

The extractor calls this when an input exceeds the pack's
`text_window_chars`. Each Chunk is sent to the LLM as its own
extraction request; the consolidator handles cross-chunk duplicates
afterwards.

Boundary strategy (in priority order):
  1. Speaker turns / timestamps  — for transcripts: `P03 [00:14:22]:` etc.
  2. Markdown headings           — `# ...`, `## ...`, `§ ...`
  3. Paragraph breaks            — blank lines
  4. Sentence endings            — `. ` followed by capital letter
  5. Hard character cut          — last resort, logged as a warning

The picker prefers the highest-priority boundary that fits; it walks
boundaries greedily until adding the next segment would exceed
`max_chars`, then emits a chunk.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

log = logging.getLogger("callimachus.chunker")


@dataclass
class Chunk:
    index: int           # 0-based position
    text: str
    section_hint: str    # e.g. "P03 [00:14:22]" or "Paragraphs 5-8"


# ── Boundary detectors ────────────────────────────────────────────────────────

# A speaker line (Densho/transcription conventions):
#   GH:                  | P03:                 | P03 [00:14:22]:
#   <Speaker> [time]:    | <NAME>:
_SPEAKER_LINE_RE = re.compile(
    r"(?m)^[ \t]*"
    r"(?:[A-Z][A-Za-z0-9_.\-]{1,30}|P\d+)"
    r"(?:[ \t]*\[[^\]]{1,40}\])?"
    r"[ \t]*:[ \t]"
)
# Standalone timestamp markers: `[00:14:22]`, `(14:22)`, `14:22 — `
_TIMESTAMP_RE = re.compile(r"(?m)^[ \t]*[\[\(]\d{1,2}:\d{2}(?::\d{2})?[\]\)]")
# Markdown / section headings.
_HEADING_RE = re.compile(r"(?m)^[ \t]*(?:#+|§)\s")
# Paragraph break: a blank line.
_PARAGRAPH_RE = re.compile(r"\n[ \t]*\n")
# Sentence end: '.' '?' '!' followed by whitespace then a capital letter.
_SENTENCE_RE = re.compile(r"[\.!?][\"')\]]?\s+(?=[A-Z])")


# Priorities: higher = preferred. The picker uses the highest priority
# strategy that yields at least one boundary inside the current window.
_STRATEGIES = (
    ("speaker_turn", _SPEAKER_LINE_RE, 5),
    ("timestamp",    _TIMESTAMP_RE,    4),
    ("heading",      _HEADING_RE,      3),
    ("paragraph",    _PARAGRAPH_RE,    2),
    ("sentence",     _SENTENCE_RE,     1),
)


def _find_boundaries(text: str) -> list[tuple[int, str, int]]:
    """Return [(position, strategy_name, priority), ...] sorted by position.

    A `position` is the character offset where the NEXT chunk would start
    (i.e. just after the matched boundary token). We always include 0 (start)
    and len(text) (end) as virtual boundaries so the picker has anchors.
    """
    found: list[tuple[int, str, int]] = []
    for name, pattern, prio in _STRATEGIES:
        for m in pattern.finditer(text):
            found.append((m.start(), name, prio))
    found.sort(key=lambda t: t[0])
    # Deduplicate adjacent identical positions, keeping the highest priority.
    pruned: list[tuple[int, str, int]] = []
    for pos, name, prio in found:
        if pruned and pruned[-1][0] == pos:
            if prio > pruned[-1][2]:
                pruned[-1] = (pos, name, prio)
            continue
        pruned.append((pos, name, prio))
    return pruned


def _section_hint(chunk_text: str) -> str:
    """Best-effort section label for the chunk's start."""
    m = _SPEAKER_LINE_RE.search(chunk_text[:500])
    if m:
        # Strip the trailing colon and any whitespace.
        return m.group(0).strip().rstrip(":").strip()
    m = _TIMESTAMP_RE.search(chunk_text[:500])
    if m:
        return m.group(0).strip()
    m = _HEADING_RE.search(chunk_text[:500])
    if m:
        line_end = chunk_text.find("\n", m.start())
        if line_end == -1:
            line_end = min(len(chunk_text), m.start() + 120)
        return chunk_text[m.start():line_end].strip()
    # Fall back to "first N words".
    head = " ".join(chunk_text.split()[:8])
    return (head[:80] + "…") if len(head) > 80 else head


# ── Public API ────────────────────────────────────────────────────────────────


def chunk_text(text: str, max_chars: int) -> list[Chunk]:
    """Split text into chunks no larger than `max_chars`.

    Returns a single chunk if the input already fits. Greedy: at each step,
    advance to the LAST boundary that keeps the current chunk under
    max_chars; if no boundary exists in the window, fall back to a hard
    character cut at max_chars (with a warning).
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    text = text or ""
    if len(text) <= max_chars:
        return [Chunk(index=0, text=text, section_hint=_section_hint(text))]

    boundaries = _find_boundaries(text)
    # Always have an explicit end so the last chunk terminates cleanly.
    bnd_positions = [b[0] for b in boundaries] + [len(text)]

    chunks: list[Chunk] = []
    start = 0
    cursor = 0
    while start < len(text):
        # Find the LAST boundary position within [start+1, start+max_chars].
        window_end = start + max_chars
        # Binary-search would be ideal; the linear scan is fine for the
        # sizes involved (a few hundred boundaries per document).
        chosen = -1
        for p in bnd_positions:
            if p <= start:
                continue
            if p > window_end:
                break
            chosen = p
        if chosen == -1:
            # No boundary in the window — hard cut and warn.
            log.warning(
                "no natural boundary in window [%d, %d]; hard-cutting",
                start, window_end,
            )
            chosen = window_end
        body = text[start:chosen].rstrip()
        if not body:
            # Shouldn't happen, but guard against an infinite loop.
            break
        chunks.append(Chunk(
            index=len(chunks),
            text=body,
            section_hint=_section_hint(body),
        ))
        start = chosen
        cursor += 1
        if cursor > 1000:  # paranoid: prevent runaway loops on adversarial input
            log.error("chunker exceeded 1000 iterations; aborting")
            break
    return chunks


def estimate_chunks(text: str, max_chars: int) -> int:
    """Cheap estimate without actually building chunk texts. Used by the UI."""
    if not text or max_chars <= 0:
        return 0
    if len(text) <= max_chars:
        return 1
    # The real chunker pays attention to boundaries; this rough estimate is
    # good enough for "this transcript will split into ~N chunks" UI hints.
    return (len(text) + max_chars - 1) // max_chars
