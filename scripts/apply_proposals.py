"""Apply every approved consolidator proposal to the vault.

Usage:
    python scripts/apply_proposals.py --project thematic
    python scripts/apply_proposals.py --project thematic --dry-run

Reads vault/proposals/*.md, applies proposals with status == approved,
and rewrites each proposal's status to "applied" on success. Idempotent.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from kgforge.engine.proposal_applier import apply_approved  # noqa: E402
from kgforge.project.project import load_project            # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be applied without mutating anything")
    args = ap.parse_args(argv)

    project = load_project(args.project)

    if args.dry_run:
        from kgforge.engine.consolidator import list_proposal_files, load_proposal_file
        approved = []
        for p in list_proposal_files(project.vault_dir):
            meta = load_proposal_file(p) or {}
            if meta.get("status") == "approved":
                approved.append((p, meta))
        if not approved:
            print("Nothing to apply.")
            return 0
        for p, meta in approved:
            print(f"would apply: {meta.get('operation')}  ({meta.get('proposal_id')})")
        return 0

    results = apply_approved(project.vault_dir, project.pack)
    if not results:
        print("Nothing to apply.")
        return 0

    n_ok = sum(1 for r in results if r.ok)
    for r in results:
        tag = "OK " if r.ok else "ERR"
        print(f"  {tag}  {r.operation}  ({r.proposal_id})  {r.message}")
        for t in r.touched:
            print(f"        touched: {t}")
    print(f"\nApplied {n_ok}/{len(results)} proposal(s).")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
