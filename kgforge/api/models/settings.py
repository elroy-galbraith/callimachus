"""Settings response model.

The API key value itself is never returned — only whether it's set. The
React app shows an instructional banner when ``api_key_set`` is false.
"""
from __future__ import annotations

from pydantic import BaseModel


class SettingsOut(BaseModel):
    api_key_set: bool
    repo_root: str
    projects_dir: str
