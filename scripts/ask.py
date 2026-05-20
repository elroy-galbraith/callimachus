#!/usr/bin/env python3
"""ask.py — CLI shim around callimachus.engine.ask.

Natural-language QA over the compliance ontology.

Usage:
    python scripts/ask.py "Which obligations apply to a data controller?"
    python scripts/ask.py "What does the DPA say about biometric data?" --show-sparql
    python scripts/ask.py "List every defined term" --build-vault

Environment:
    ANTHROPIC_API_KEY — required (loaded from .env at repo root if present).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except ImportError:
    pass

import anthropic                           # noqa: E402

from callimachus.engine import ask as engine   # noqa: E402
from callimachus.engine import store as store_engine  # noqa: E402
from callimachus.pack import load_builtin      # noqa: E402

SCHEMA_TTL = REPO_ROOT / "schema" / "carib_compliance.ttl"
VAULT_TTL = REPO_ROOT / "vault" / "vault.ttl"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ask natural-language questions about the ontology."
    )
    parser.add_argument("question", nargs="+", help="The question to ask (quote it).")
    parser.add_argument("--show-sparql", action="store_true",
                        help="Print the generated SPARQL and the result table.")
    parser.add_argument("--build-vault", action="store_true",
                        help="Run to_turtle.py first to refresh vault/vault.ttl.")
    parser.add_argument("--pack", default="compliance",
                        help="Built-in pack name (default: compliance).")
    parser.add_argument("--model", default=None,
                        help="Anthropic model (default: pack.models.ask).")
    args = parser.parse_args()

    pack = load_builtin(args.pack)
    model = args.model or pack.models.ask
    question = " ".join(args.question)

    if args.build_vault:
        print("[ask] regenerating vault/vault.ttl ...")
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "to_turtle.py")],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            sys.exit(1)

    store = store_engine.load_store(SCHEMA_TTL, VAULT_TTL)
    schema = SCHEMA_TTL.read_text(encoding="utf-8")
    catalog = engine.entity_catalog(store, pack)
    examples = engine.few_shot_examples(pack)
    client = anthropic.Anthropic()

    print(f"[ask] question: {question}")
    print(f"[ask] synthesising SPARQL with {model} ...")
    sparql, rationale = engine.synthesize_sparql(
        client, model, question, schema, catalog, examples
    )

    if args.show_sparql:
        print("\n--- SPARQL ---")
        print(sparql)
        print(f"\nRationale: {rationale}")

    print("[ask] executing query ...")
    try:
        results = engine.run_sparql(store, sparql)
    except Exception as e:
        print(f"[ask] query failed: {e}", file=sys.stderr)
        print("\nThe generated SPARQL was:")
        print(sparql)
        sys.exit(2)

    if args.show_sparql:
        print("\n--- Results ---")
        engine.print_results(results)

    print(f"[ask] summarising with {model} ...")
    answer = engine.summarise(client, model, question, sparql, rationale, results)

    print("\n" + "=" * 60)
    print("ANSWER")
    print("=" * 60)
    print(answer)
    print()


if __name__ == "__main__":
    main()
