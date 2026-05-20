#!/usr/bin/env python3
"""extractor.py — CLI shim around callimachus.engine.extractor.

Pipeline: PDF path → text extraction (Docling or pdfplumber fallback)
          → Claude Haiku (JSON Schema tool use) → Markdown+YAML vault files.

Usage:
    python scripts/extractor.py path/to/statute.pdf
    python scripts/extractor.py path/to/statute.pdf --vault vault/ --doc-id dpa2020_s3
    python scripts/extractor.py --text "Section 6 ..." --doc-id dpa2020_s6  # raw text mode
    python scripts/extractor.py path/to.pdf --dry-run

Environment:
    ANTHROPIC_API_KEY — required (loaded from .env at repo root if present).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except ImportError:
    pass

from callimachus.engine import extractor as engine  # noqa: E402
from callimachus.pack import load_builtin           # noqa: E402

DEFAULT_VAULT = REPO_ROOT / "vault"


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract legal entities from a PDF or text.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("pdf", nargs="?", help="Path to a PDF file.")
    src.add_argument("--text", metavar="TEXT", help="Raw statutory text (instead of PDF).")
    parser.add_argument("--doc-id", default=None,
                        help="Document identifier prefix (default: PDF stem).")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT),
                        help="Output vault directory.")
    parser.add_argument("--prompt-version", default="extractor-v1")
    parser.add_argument("--pack", default="compliance",
                        help="Built-in pack name (default: compliance).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print extracted JSON without writing files.")
    args = parser.parse_args()

    pack = load_builtin(args.pack)

    if args.text:
        doc_id = args.doc_id or "unknown_doc"
        result = engine.extract(
            pack,
            text=args.text,
            doc_id=doc_id,
            prompt_version=args.prompt_version,
            vault_dir=Path(args.vault),
            dry_run=args.dry_run,
        )
    else:
        pdf_path = Path(args.pdf)
        if not pdf_path.exists():
            print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
            sys.exit(1)
        doc_id = args.doc_id or pdf_path.stem.lower().replace("-", "_").replace(" ", "_")
        result = engine.extract(
            pack,
            pdf_path=pdf_path,
            doc_id=doc_id,
            prompt_version=args.prompt_version,
            vault_dir=Path(args.vault),
            dry_run=args.dry_run,
        )

    if args.dry_run:
        print(json.dumps({"entities": result}, indent=2, ensure_ascii=False))
    else:
        print(f"[extractor] {len(result)} files written to {args.vault}")


if __name__ == "__main__":
    main()
