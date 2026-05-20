#!/usr/bin/env python3
"""to_turtle.py — CLI shim around callimachus.engine.to_turtle.

Usage:
    python scripts/to_turtle.py                     # writes vault/vault.ttl
    python scripts/to_turtle.py --out path/to.ttl   # custom output path
    python scripts/to_turtle.py --print             # print to stdout
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from callimachus.engine import to_turtle as engine  # noqa: E402
from callimachus.pack import load_builtin           # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert vault/*.md to Turtle RDF.")
    parser.add_argument("--vault", default="vault", help="Vault directory (default: vault)")
    parser.add_argument("--out", default=None, help="Output .ttl path (default: vault/vault.ttl)")
    parser.add_argument("--print", dest="print_only", action="store_true",
                        help="Print to stdout instead of writing a file")
    parser.add_argument("--pack", default="compliance",
                        help="Built-in pack name (default: compliance).")
    args = parser.parse_args()

    vault_dir = Path(args.vault)
    if not vault_dir.is_dir():
        print(f"[to_turtle] ERROR: vault directory not found: {vault_dir}", file=sys.stderr)
        sys.exit(1)

    pack = load_builtin(args.pack)
    turtle = engine.build_turtle(vault_dir, pack)

    if args.print_only:
        print(turtle)
    else:
        out_path = Path(args.out) if args.out else vault_dir / "vault.ttl"
        out_path.write_text(turtle, encoding="utf-8")
        print(f"[to_turtle] wrote {out_path} ({len(turtle)} bytes)")


if __name__ == "__main__":
    main()
