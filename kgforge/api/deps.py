"""FastAPI dependencies.

``get_project`` resolves the ``{name}`` path param into a loaded ``Project``
dataclass. Loaded projects are LRU-cached at module scope; mutations
(create project, clear caches) call ``clear_project_cache()`` to invalidate.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Path, Request

from kgforge.api.jobs import JobRegistry
from kgforge.project import Project, load_project


@lru_cache(maxsize=32)
def _load_cached(name: str) -> Project:
    return load_project(name)


def clear_project_cache() -> None:
    """Drop the LRU cache. Called by create-project and cache/clear routes."""
    _load_cached.cache_clear()


def get_project(name: str = Path(..., description="Project name")) -> Project:
    try:
        return _load_cached(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


def get_jobs(request: Request) -> JobRegistry:
    return request.app.state.jobs
