"""CLI for the LLM consolidator. Read-only: prints proposals, mutates nothing.

Usage:
    python scripts/consolidate.py --project thematic
    python scripts/consolidate.py --project densho_themes --json
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

from kgforge.engine.consolidator import consolidate  # noqa: E402
from kgforge.project.project import load_project    # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--model", default=None, help="override pack.models.ask")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    project = load_project(args.project)
    print(f"[consolidator] loading vault {project.vault_dir}", file=sys.stderr)
    proposals = consolidate(project.vault_dir, project.pack, model=args.model)

    if args.json:
        json.dump(
            {"project": project.name, "proposals": [p.to_dict() for p in proposals]},
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
        return 0

    if not proposals:
        print("No proposals. Vault looks consolidated.")
        return 0

    for i, p in enumerate(proposals, 1):
        print(f"\n[{i}] {p.operation}  ({p.confidence})")
        for k, v in p.payload.items():
            print(f"    {k}: {v}")
        print(f"    rationale: {p.rationale}")
        if p.evidence:
            print("    evidence:")
            for q in p.evidence:
                print(f"      > {q}")
    print(f"\n{len(proposals)} proposal(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
