"""Render the system + user prompt strings for the LLM call.

The DomainPack carries the templates with {placeholder} markers; this
module formats them with the call-time context.
"""
from __future__ import annotations

from callimachus.pack import DomainPack


def render_prompts(
    pack: DomainPack,
    doc_id: str,
    prompt_version: str,
    text: str,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) ready for client.messages.create.

    The text is truncated to pack.prompt.text_window_chars before
    substitution.
    """
    system = pack.prompt.system.format(doc_id=doc_id)
    user = pack.prompt.user.format(
        few_shot=pack.prompt.few_shot,
        doc_id=doc_id,
        prompt_version=prompt_version,
        text_window=text[: pack.prompt.text_window_chars],
    )
    return system, user
