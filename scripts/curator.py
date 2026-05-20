#!/usr/bin/env python3
"""curator.py — CLI shim around callimachus.engine.curator.

Watch the inbox for new PDFs; run extraction; submit to the project's
ApprovalBackend (git for the existing compliance project, filesystem for
new projects).

Usage:
    python scripts/curator.py                # watch loop
    python scripts/curator.py --once         # process existing files then exit
    python scripts/curator.py --backend filesystem   # in-app approve flow
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except ImportError:
    pass

from callimachus.approval import make_backend   # noqa: E402
from callimachus.engine import curator as engine  # noqa: E402
from callimachus.pack import load_builtin       # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [curator] %(message)s",
    datefmt="%H:%M:%S",
)

VAULT_DIR = REPO_ROOT / "vault"
INBOX_DIR = REPO_ROOT / "inbox"
SOURCES_DIR = REPO_ROOT / "vault" / "sources"


def main() -> None:
    parser = argparse.ArgumentParser(description="Curator-agent: watch inbox for PDFs.")
    parser.add_argument("--inbox", default=str(INBOX_DIR), help="Inbox directory to watch.")
    parser.add_argument("--once", action="store_true",
                        help="Process existing inbox files then exit (no watch loop).")
    parser.add_argument("--pack", default="compliance",
                        help="Built-in pack name (default: compliance).")
    parser.add_argument("--backend", default="git",
                        choices=["git", "filesystem"],
                        help="Approval backend (default: git, preserving the carib-comp-ont workflow).")
    parser.add_argument("--prompt-version", default="extractor-v1")
    args = parser.parse_args()

    pack = load_builtin(args.pack)
    inbox_dir = Path(args.inbox)

    if args.backend == "git":
        approval = make_backend("git", repo_root=REPO_ROOT)
    else:
        approval = make_backend("filesystem", vault_dir=VAULT_DIR)

    kwargs = dict(
        pack=pack,
        vault_dir=VAULT_DIR,
        sources_dir=SOURCES_DIR,
        approval=approval,
        prompt_version=args.prompt_version,
    )

    if args.once:
        inbox_dir.mkdir(parents=True, exist_ok=True)
        engine.process_existing(inbox_dir, **kwargs)
    else:
        engine.watch(inbox_dir, **kwargs)


if __name__ == "__main__":
    main()
