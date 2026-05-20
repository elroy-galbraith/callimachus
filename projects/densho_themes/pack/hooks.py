"""Thematic-pack hook overrides for the kgforge engine.

Two hooks are provided:

- derive_doc_id : normalises transcript filenames (e.g. "interview_03.txt"
  → "interview03") so generated entity IDs read naturally
  (interview03_code_lack_of_transparency rather than
  interview_03_txt_code_…).

- search_variants : when highlighting transcripts, prefer the speaker-line
  prefix ("P03 [00:14:22]: ") as the search needle so the highlighted span
  starts at the start of the turn. Falls back to longer prefixes.
"""
from __future__ import annotations

import re

# Match "P03", "P03 [00:14:22]:", "Participant 3 (00:14):", "R:" (researcher), etc.
_SPEAKER_PREFIX_RE = re.compile(
    r"^\s*(?:P(?:articipant)?\s*\d+|R|I|Researcher|Interviewer)"
    r"(?:\s*[\[(]\s*[\d:.,]+\s*[\])])?\s*:\s*",
    re.IGNORECASE,
)


def derive_doc_id(stem: str) -> str:
    """Map "interview_03" / "interview-03" / "interview 03" → "interview03".

    Conservative: only collapses underscores/dashes/spaces inside a leading
    "interview" prefix. Other filenames pass through the engine's default
    normalisation.
    """
    s = stem.lower().strip()
    m = re.match(r"^(interview)[\s_\-]+(\d+)$", s)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return s.replace("-", "_").replace(" ", "_")


def search_variants(source_text: str) -> list[str]:
    """Generate PDF/text needles for highlight injection.

    For transcripts the most distinctive substring is usually the speaker
    prefix plus the first few words of the quoted utterance. We strip the
    speaker prefix from the source_text (which is the verbatim quote
    itself, without the prefix), and provide several length-bounded
    variants for the highlighter to try.
    """
    if not source_text:
        return []
    full = source_text.strip()
    # If the source happens to include the speaker line, strip it before
    # building search needles — search_for matches the utterance body.
    body = _SPEAKER_PREFIX_RE.sub("", full)
    body = body.strip(" '\"")

    variants: list[str] = []
    for length in (80, 50, 30):
        v = body[:length].strip()
        if len(v) >= 15 and v not in variants:
            variants.append(v)
    return variants
