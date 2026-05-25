"""Run CQ1 (codes ranked by excerpt count) against the thematic project.

Used by the asciinema demo at docs/demo/thematic.cast — kept as its own
file so the cast's final command is something a viewer can actually replay.

Prereq: `python scripts/to_turtle.py --vault projects/thematic/vault
         --pack thematic --out projects/thematic/vault/vault.ttl` first.
"""
from __future__ import annotations

from pathlib import Path

import pyoxigraph as ox

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = REPO_ROOT / "callimachus" / "pack" / "builtin" / "thematic" / "schema.ttl"
VAULT = REPO_ROOT / "projects" / "thematic" / "vault" / "vault.ttl"
CQ1 = REPO_ROOT / "callimachus" / "pack" / "builtin" / "thematic" / "sparql" / "cq1_codes_recur.rq"


def main() -> None:
    store = ox.Store()
    store.load(SCHEMA.read_bytes(), ox.RdfFormat.TURTLE)
    store.load(VAULT.read_bytes(), ox.RdfFormat.TURTLE)
    print("-- CQ1: codes ranked by excerpt count --")
    print(f'{"label":35s} {"n":>3}')
    for row in store.query(CQ1.read_text(encoding="utf-8")):
        label = str(row["label"]).strip('"').split('"')[0]
        n = str(row["nExcerpts"]).split('"')[1]
        print(f"{label:35s} {n:>3}")


if __name__ == "__main__":
    main()
