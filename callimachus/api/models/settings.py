"""Settings response model.

API key *values* are never returned — only which providers have one set
in the environment. The React app uses ``providers`` to show a per-vendor
status grid and a banner when no provider is configured.
"""
from __future__ import annotations

from pydantic import BaseModel


class ProviderStatus(BaseModel):
    """One row in the provider-key status grid."""

    id: str            # canonical provider id, e.g. "anthropic", "openai"
    label: str         # human-readable name, e.g. "Anthropic Claude"
    env_var: str       # the env var the user sets, e.g. "ANTHROPIC_API_KEY"
    configured: bool   # True iff the env var is set and non-empty


class SettingsOut(BaseModel):
    # Back-compat: True iff *any* provider key is set. Older clients
    # (and the legacy Streamlit UI) read just this field.
    api_key_set: bool
    providers: list[ProviderStatus]
    repo_root: str
    projects_dir: str
