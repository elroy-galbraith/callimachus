"""Load schema + vault Turtle into pyoxigraph and run SPARQL.

Lifted from scripts/load_to_oxigraph.py. The competency-question list and
the vault TTL path come from the caller (which knows about a project /
DomainPack); this module is pack-agnostic.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import pyoxigraph
except ImportError as _exc:
    raise ImportError(
        "pyoxigraph is required by callimachus.engine.store. "
        "Install with: pip install pyoxigraph"
    ) from _exc


def load_store(*ttl_paths: Path) -> "pyoxigraph.Store":
    """Create an in-memory store and load each Turtle file in order."""
    store = pyoxigraph.Store()
    for ttl_path in ttl_paths:
        if not ttl_path.exists():
            print(f"[load] WARNING: {ttl_path} not found — skipping", file=sys.stderr)
            continue
        data = ttl_path.read_bytes()
        store.load(data, pyoxigraph.RdfFormat.TURTLE, base_iri=str(ttl_path.as_uri()))
        print(
            f"[load] loaded {ttl_path.name} ({len(data)} bytes, "
            f"{sum(1 for _ in store)} triples total)"
        )
    return store


def run_query(store: "pyoxigraph.Store", sparql: str, title: str) -> None:
    """Print a SPARQL query result in the table format used by the CLI."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")

    results = store.query(sparql)

    if isinstance(results, pyoxigraph.QuerySolutions):
        variables = results.variables
        rows = list(results)
        if not rows:
            print("  (no results)")
            return
        widths = [len(str(v)) for v in variables]
        str_rows = []
        for row in rows:
            sr = [str(row[v]) if row[v] is not None else "" for v in variables]
            for i, cell in enumerate(sr):
                widths[i] = max(widths[i], len(cell))
            str_rows.append(sr)
        header = "  " + "  ".join(str(v).ljust(widths[i]) for i, v in enumerate(variables))
        sep = "  " + "  ".join("-" * w for w in widths)
        print(header)
        print(sep)
        for sr in str_rows:
            print("  " + "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(sr)))
        print(f"\n  {len(str_rows)} row(s)")
    elif isinstance(results, bool):
        print(f"  ASK → {results}")
    else:
        triples = list(results)
        for t in triples:
            print(f"  {t}")
        print(f"\n  {len(triples)} triple(s)")
