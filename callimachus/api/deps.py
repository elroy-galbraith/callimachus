"""FastAPI dependencies.

``get_project`` resolves the ``{name}`` path param into a loaded ``Project``
dataclass. Loaded projects are LRU-cached at module scope; mutations
(create project, clear caches) call ``clear_project_cache()`` to invalidate.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Path, Request

from callimachus.api.jobs import JobRegistry
from callimachus.project import Project, load_project


# Project names must look like snake_case identifiers (same constraint
# ProjectCreateIn enforces on create). The pattern doubles as path-
# traversal defence: without it, a request like
# ``GET /api/projects/..%2F..%2Ffoo`` would let ``load_project`` resolve
# outside the projects directory.
_PROJECT_NAME_PATTERN = r"^[a-z][a-z0-9_]*$"


@lru_cache(maxsize=32)
def _load_cached(name: str) -> Project:
    return load_project(name)


def clear_project_cache() -> None:
    """Drop the LRU cache. Called by create-project and cache/clear routes."""
    _load_cached.cache_clear()


def get_project(
    name: str = Path(
        ...,
        pattern=_PROJECT_NAME_PATTERN,
        description="Project name (snake_case)",
    ),
) -> Project:
    try:
        return _load_cached(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


def get_jobs(request: Request) -> JobRegistry:
    return request.app.state.jobs
