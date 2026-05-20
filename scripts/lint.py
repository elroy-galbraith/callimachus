"""CLI for the deterministic vault linter.

Usage:
    python scripts/lint.py --project densho_themes
    python scripts/lint.py --project densho_themes --json
    python scripts/lint.py --project densho_themes --strict   # exit non-zero on warns too

Exit codes:
    0 — clean (or only warns/infos and --strict not set)
    1 — errors found, or warns when --strict
"""
from __future__ import annotations

import argparse
import json
import sys

from callimachus.engine.linter import lint_vault, summarise
from callimachus.project.project import load_project

SEV_TAG = {"error": "ERR ", "warn": "WARN", "info": "INFO"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True,
                    help="project name (under projects/) or path to project.json's folder")
    ap.add_argument("--json", action="store_true", help="emit findings as JSON")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero on warns as well as errors")
    args = ap.parse_args(argv)

    project = load_project(args.project)
    findings = lint_vault(project.vault_dir, project.pack)

    if args.json:
        json.dump(
            {"project": project.name, "findings": [f.to_dict() for f in findings]},
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
    else:
        for f in findings:
            tag = SEV_TAG.get(f.severity, f.severity.upper())
            who = f.entity_id or "(no id)"
            print(f"  {tag}  [{f.rule}]  {who}")
            print(f"        {f.message}")
            if f.suggested_fix:
                print(f"        fix: {f.suggested_fix}")
            print(f"        in {f.file}")
        counts = summarise(findings)
        total = sum(counts.values())
        print(
            f"\n{total} finding(s): "
            f"{counts['error']} error, {counts['warn']} warn, {counts['info']} info"
        )

    counts = summarise(findings)
    if counts["error"] > 0:
        return 1
    if args.strict and counts["warn"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
