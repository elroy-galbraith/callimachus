"""Single source of truth for LLM provider metadata.

Lists every provider Callimachus advertises in the UI and routes its
model ids to the correct env var. Consumed by:

- ``callimachus.api.routers.settings``  -- populates ``/api/settings.providers``
- ``callimachus.engine.llm``            -- auto-prefixes bare model names

To add a new vendor, append one entry here. The frontend's curated
model catalog (``frontend/src/models/catalog.ts``) is intentionally
decoupled: it lists *suggested models*, not *supported providers*.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    id: str               # LiteLLM provider prefix (e.g. "anthropic")
    label: str            # human-readable name
    env_var: str          # credential env var LiteLLM expects
    bare_prefixes: tuple[str, ...] = ()  # model-id stems that auto-prefix to this provider


PROVIDERS: tuple[Provider, ...] = (
    Provider("anthropic",   "Anthropic Claude",        "ANTHROPIC_API_KEY", ("claude",)),
    Provider("openai",      "OpenAI GPT / o-series",   "OPENAI_API_KEY",    ("gpt", "o1", "o3")),
    Provider("gemini",      "Google Gemini",           "GEMINI_API_KEY",    ("gemini",)),
    Provider("mistral",     "Mistral",                 "MISTRAL_API_KEY",   ("mistral",)),
    Provider("cohere",      "Cohere",                  "COHERE_API_KEY",    ("command",)),
    Provider("together_ai", "Together AI (Llama, ...)", "TOGETHER_API_KEY", ("llama",)),
)


def bare_prefix_map() -> dict[str, str]:
    """Stem-prefix -> provider-id, for ``normalise_model_id`` back-compat."""
    return {stem: p.id for p in PROVIDERS for stem in p.bare_prefixes}
