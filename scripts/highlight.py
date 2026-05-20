#!/usr/bin/env python3
"""highlight.py — CLI shim around callimachus.engine.highlight.

Inject yellow highlight annotations into a vault source PDF at the
location of each entity's source_text.

Usage:
    python scripts/highlight.py vault/sources/dpa_2020_s6.pdf
    python scripts/highlight.py --doc-id dpa_2020_s6
    python scripts/highlight.py vault/sources/dpa_2020_s6.pdf --vault vault/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from callimachus.engine import highlight as engine  # noqa: E402
from callimachus.pack import load_builtin           # noqa: E402

DEFAULT_VAULT = REPO_ROOT / "vault"


def main() -> None:
    parser = argparse.ArgumentParser(description="Inject highlight annotations into a vault source PDF.")
    parser.add_argument("pdf", nargs="?", help="Path to the PDF (default: vault/sources/<doc-id>.pdf).")
    parser.add_argument("--doc-id", default=None, help="Document ID (default: PDF stem).")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="Vault directory.")
    parser.add_argument("--pack", default="compliance",
                        help="Built-in pack name (default: compliance).")
    args = parser.parse_args()

    if args.pdf:
        pdf_path = Path(args.pdf)
    elif args.doc_id:
        pdf_path = REPO_ROOT / "vault" / "sources" / f"{args.doc_id}.pdf"
    else:
        parser.error("must provide either a PDF path or --doc-id")

    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    doc_id = args.doc_id or pdf_path.stem.lower().replace("-", "_").replace(" ", "_")
    pack = load_builtin(args.pack)

    matched, unmatched = engine.highlight_pdf(pdf_path, Path(args.vault), doc_id, pack)
    print(f"[highlight] matched {matched}, unmatched {unmatched} -> {pdf_path}")


if __name__ == "__main__":
    main()
