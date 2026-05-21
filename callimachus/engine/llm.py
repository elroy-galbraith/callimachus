"""Thin provider-agnostic wrapper around litellm.completion.

Two call shapes the engine uses:

1. `call_with_tool` -- forced function call for structured JSON output
   (extractor, consolidator, SPARQL synthesis).
2. `chat_text` -- plain text completion (answer summariser).

Model identifiers follow LiteLLM's `<provider>/<model>` convention
(e.g. `anthropic/claude-sonnet-4-6`, `openai/gpt-4o`, `gemini/gemini-2.5-pro`).
For backward compatibility, bare `claude-*` / `gpt-*` / `gemini-*` strings
are auto-prefixed with the obvious provider.

Provider credentials come from environment variables LiteLLM already
reads: ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY,
AWS_* for Bedrock, etc. Nothing in this module touches those directly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

# `import litellm` is deferred to the call sites. LiteLLM pulls in openai,
# tiktoken, aiohttp, etc.; importing it at module top would mean every API
# process pays that cost on startup whether or not an LLM endpoint is ever
# hit. Python caches imports, so the per-call overhead after the first hit
# is just a dict lookup.

from callimachus.providers import bare_prefix_map


def normalise_model_id(model: str) -> str:
    """Prefix a bare model name with its obvious provider if missing.

    `claude-sonnet-4-6` -> `anthropic/claude-sonnet-4-6`. Strings that
    already contain `/` are returned unchanged.
    """
    if "/" in model:
        return model
    lowered = model.lower()
    for stem, provider in bare_prefix_map().items():
        if lowered.startswith(stem):
            return f"{provider}/{model}"
    return model


@dataclass(frozen=True)
class ToolCallResult:
    """Outcome of a forced-tool call.

    `arguments` is empty (`{}`) when the model exhausted `max_tokens`
    before finishing the tool call -- callers should check
    `finish_reason == "length"` to distinguish "model returned nothing"
    from "model was truncated mid-emission".
    """
    arguments: dict[str, Any]
    finish_reason: str
    output_tokens: int


def call_with_tool(
    *,
    model: str,
    system: str,
    user: str,
    tool_name: str,
    tool_description: str,
    tool_schema: dict[str, Any],
    max_tokens: int,
) -> ToolCallResult:
    """Force the model to call `tool_name` and return its parsed input.

    `tool_schema` is a JSON-Schema object (the OpenAI `parameters` /
    Anthropic `input_schema` shape -- LiteLLM normalises these for us).
    """
    import litellm

    response = litellm.completion(
        model=normalise_model_id(model),
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": tool_schema,
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": tool_name}},
    )

    output_tokens = getattr(response.usage, "completion_tokens", 0) or 0

    # Gemini (and Anthropic with strong safety filtering) can return a
    # 200 with zero choices when the response is blocked. Treat that as
    # an empty tool call with a synthetic finish_reason so callers can
    # distinguish it from "model returned nothing".
    if not response.choices:
        return ToolCallResult({}, "no_choices", output_tokens)

    choice = response.choices[0]
    finish_reason = choice.finish_reason or ""

    tool_calls = getattr(choice.message, "tool_calls", None) or []
    if not tool_calls:
        return ToolCallResult({}, finish_reason, output_tokens)

    raw_args = tool_calls[0].function.arguments
    try:
        arguments = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
    except json.JSONDecodeError:
        arguments = {}
    return ToolCallResult(arguments, finish_reason, output_tokens)


def chat_text(
    *,
    model: str,
    system: str,
    user: str,
    max_tokens: int,
) -> str:
    """Plain chat completion returning the assistant text."""
    import litellm

    response = litellm.completion(
        model=normalise_model_id(model),
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    if not response.choices:
        return ""
    return (response.choices[0].message.content or "").strip()
