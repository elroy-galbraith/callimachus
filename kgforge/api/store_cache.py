"""Per-project in-memory pyoxigraph store cache.

The store is expensive to rebuild (RDF parse, triple ingest) but cheap to
keep around between requests. We cache by ``(project_name, schema_ttl_mtime,
vault_ttl_mtime)`` so any on-disk edit invalidates the entry on next access
without an explicit ``cache_clear`` call.

Explicit invalidation is still wired up (``invalidate(project_name)``) for
the "Rebuild vault.ttl" button.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from kgforge.engine import store as store_engine
from kgforge.engine import to_turtle as to_turtle_engine
from kgforge.project import Project

if TYPE_CHECKING:
    import pyoxigraph


def _mtime_or_zero(path: Path | None) -> float:
    if path is None or not path.exists():
        return 0.0
    return path.stat().st_mtime


class StoreCache:
    """Thread-safe (name -> store) cache with mtime-based invalidation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # name -> (cache_key, store)
        self._cache: dict[str, tuple[tuple, "pyoxigraph.Store"]] = {}

    def _key(self, project: Project) -> tuple:
        return (
            project.name,
            _mtime_or_zero(project.schema_ttl),
            _mtime_or_zero(project.vault_ttl),
        )

    def get(self, project: Project) -> "pyoxigraph.Store":
        key = self._key(project)
        with self._lock:
            cached = self._cache.get(project.name)
            if cached and cached[0] == key:
                return cached[1]
        # Build outside the lock — loading is slow and we don't want to
        # block other projects' requests on it.
        paths: list[Path] = []
        if project.schema_ttl and project.schema_ttl.exists():
            paths.append(project.schema_ttl)
        if project.vault_ttl.exists():
            paths.append(project.vault_ttl)
        store = store_engine.load_store(*paths)
        with self._lock:
            self._cache[project.name] = (key, store)
        return store

    def invalidate(self, project_name: str) -> None:
        with self._lock:
            self._cache.pop(project_name, None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


def ensure_vault_ttl(project: Project) -> tuple[bool, int]:
    """Build ``vault.ttl`` if missing. Returns (existed_or_built, size_bytes)."""
    if not project.vault_dir.exists():
        raise FileNotFoundError(f"vault dir not found: {project.vault_dir}")
    if project.vault_ttl.exists():
        return False, project.vault_ttl.stat().st_size
    turtle = to_turtle_engine.build_turtle(project.vault_dir, project.pack)
    project.vault_ttl.parent.mkdir(parents=True, exist_ok=True)
    project.vault_ttl.write_text(turtle, encoding="utf-8")
    return True, project.vault_ttl.stat().st_size


def rebuild_vault_ttl(project: Project) -> int:
    """Force-regenerate ``vault.ttl`` from the markdown vault."""
    if project.vault_ttl.exists():
        project.vault_ttl.unlink()
    _, size = ensure_vault_ttl(project)
    return size


def resolve_cq_sparql(project: Project, cq_id: str) -> str:
    """Return the SPARQL body for a competency question id.

    Resolution mirrors ``DomainPackOut.from_pack``: pack-relative first,
    then ``project.sparql_dir / basename`` as a legacy fallback.
    """
    pack = project.pack
    for cq in pack.competency_questions:
        if cq.id != cq_id:
            continue
        candidate: Path | None = None
        if pack.pack_dir is not None:
            candidate = pack.pack_dir / cq.file
            if not candidate.exists() and project.sparql_dir is not None:
                candidate = project.sparql_dir / Path(cq.file).name
        elif project.sparql_dir is not None:
            candidate = project.sparql_dir / Path(cq.file).name
        if candidate is None or not candidate.exists():
            raise FileNotFoundError(
                f"SPARQL file not found for cq {cq_id!r}: {cq.file}"
            )
        return candidate.read_text(encoding="utf-8")
    raise KeyError(f"no competency question with id {cq_id!r}")
