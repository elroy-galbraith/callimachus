#!/usr/bin/env python3
"""load_to_oxigraph.py — CLI shim around callimachus.engine.store.

Load schema + vault Turtle into an in-memory Oxigraph store and run
SPARQL competency queries.

Usage:
    python scripts/load_to_oxigraph.py
    python scripts/load_to_oxigraph.py --query sparql/cq1_obligations_on_controller.rq
    python scripts/load_to_oxigraph.py --build-vault
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from callimachus.engine import store as engine  # noqa: E402
from callimachus.pack import load_builtin       # noqa: E402

SCHEMA_TTL = REPO_ROOT / "schema" / "carib_compliance.ttl"
VAULT_TTL = REPO_ROOT / "vault" / "vault.ttl"
SPARQL_DIR = REPO_ROOT / "sparql"


def build_vault_ttl() -> None:
    print("[load] Building vault/vault.ttl from vault/*.md …")
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "to_turtle.py")],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    print(result.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Load vault into Oxigraph and run SPARQL.")
    parser.add_argument("--build-vault", action="store_true",
                        help="Run to_turtle.py first to regenerate vault/vault.ttl")
    parser.add_argument("--query", metavar="FILE",
                        help="Run a single .rq file instead of all CQs")
    parser.add_argument("--pack", default="compliance",
                        help="Built-in pack name (default: compliance).")
    args = parser.parse_args()

    if args.build_vault:
        build_vault_ttl()

    pack = load_builtin(args.pack)
    store = engine.load_store(SCHEMA_TTL, VAULT_TTL)

    if args.query:
        qpath = Path(args.query)
        sparql = qpath.read_text(encoding="utf-8")
        engine.run_query(store, sparql, qpath.name)
    else:
        for cq in pack.competency_questions:
            qpath = SPARQL_DIR / Path(cq.file).name
            if not qpath.exists():
                print(f"[load] WARNING: query file not found: {qpath}", file=sys.stderr)
                continue
            sparql = qpath.read_text(encoding="utf-8")
            engine.run_query(store, sparql, cq.label)

    print(f"\n[load] done. Store contains {sum(1 for _ in store)} triples total.\n")


if __name__ == "__main__":
    main()
