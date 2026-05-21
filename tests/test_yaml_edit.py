"""Unit tests for callimachus.pack.yaml_edit.

The PATCH /api/projects/{name}/pack/models endpoint goes through this
helper; the contract it guarantees is "edits don't eat comments." Tested
in isolation here so a regression surfaces without spinning up the API.
"""
from __future__ import annotations

import yaml as pyyaml

from callimachus.pack.yaml_edit import update_pack_models


SAMPLE = """\
metadata:
  name: demo
  label: Demo pack

# top-level comment explaining the pack
classes:
  - name: Thing
    label: A thing

models:
  # LiteLLM model ids. Swap the provider prefix to use a different vendor:
  #   openai/gpt-4o, gemini/gemini-2.5-pro, mistral/mistral-large-latest, ...
  extractor: anthropic/claude-haiku-4-5-20251001
  ask:       anthropic/claude-sonnet-4-6

inbox:
  accepted_extensions: [".pdf"]
"""


def test_preserves_top_level_comment() -> None:
    out = update_pack_models(SAMPLE, extractor="openai/gpt-4o")
    assert "# top-level comment explaining the pack" in out


def test_preserves_inline_models_comment() -> None:
    # The "# LiteLLM model ids..." block lives *inside* the models: map.
    # Comments inside the touched block are the easiest to lose.
    out = update_pack_models(SAMPLE, extractor="openai/gpt-4o")
    assert "# LiteLLM model ids" in out
    assert "openai/gpt-4o, gemini/gemini-2.5-pro" in out


def test_applies_extractor_update() -> None:
    out = update_pack_models(SAMPLE, extractor="openai/gpt-4o")
    data = pyyaml.safe_load(out)
    assert data["models"]["extractor"] == "openai/gpt-4o"
    # ask was not passed, must be unchanged
    assert data["models"]["ask"] == "anthropic/claude-sonnet-4-6"


def test_applies_ask_update_only() -> None:
    out = update_pack_models(SAMPLE, ask="gemini/gemini-2.5-pro")
    data = pyyaml.safe_load(out)
    assert data["models"]["ask"] == "gemini/gemini-2.5-pro"
    assert data["models"]["extractor"] == "anthropic/claude-haiku-4-5-20251001"


def test_both_none_is_a_noop_on_values() -> None:
    out = update_pack_models(SAMPLE)
    data = pyyaml.safe_load(out)
    assert data["models"]["extractor"] == "anthropic/claude-haiku-4-5-20251001"
    assert data["models"]["ask"] == "anthropic/claude-sonnet-4-6"
    assert "# LiteLLM model ids" in out


def test_output_is_valid_yaml_readable_by_pyyaml() -> None:
    # The rest of the codebase reads via PyYAML; the helper's output must
    # not introduce ruamel-specific features that break safe_load.
    out = update_pack_models(SAMPLE, extractor="openai/gpt-4o", ask="gemini/gemini-2.5-pro")
    data = pyyaml.safe_load(out)
    assert data["metadata"]["name"] == "demo"
    assert data["classes"][0]["name"] == "Thing"
    assert data["inbox"]["accepted_extensions"] == [".pdf"]


def test_inserts_models_block_when_missing() -> None:
    without_models = """\
metadata:
  name: demo
classes:
  - name: Thing
    label: A thing
"""
    out = update_pack_models(without_models, extractor="openai/gpt-4o-mini")
    data = pyyaml.safe_load(out)
    assert data["models"]["extractor"] == "openai/gpt-4o-mini"


def test_empty_input_produces_models_block() -> None:
    out = update_pack_models("", extractor="openai/gpt-4o-mini", ask="anthropic/claude-sonnet-4-6")
    data = pyyaml.safe_load(out)
    assert data["models"]["extractor"] == "openai/gpt-4o-mini"
    assert data["models"]["ask"] == "anthropic/claude-sonnet-4-6"
