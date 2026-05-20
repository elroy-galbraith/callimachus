"""Ad-hoc smoke test for the LiteLLM integration against Gemini.

Not part of the test suite -- this hits the real Gemini API and spends
real money. Run manually:

    python scripts/_smoke_gemini.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env", override=True)

from callimachus.engine import llm  # noqa: E402
from callimachus.engine import extractor as extractor_engine  # noqa: E402
from callimachus.pack import load_builtin  # noqa: E402


MODEL = "gemini/gemini-2.5-flash"
FALLBACK_MODEL = "gemini/gemini-2.5-pro"


def _with_retry(fn, *, label: str):
    """Retry once on a 5xx, then fall back to FALLBACK_MODEL on the next 5xx."""
    import litellm
    for attempt in (1, 2):
        try:
            return fn(MODEL), MODEL
        except litellm.exceptions.ServiceUnavailableError as exc:
            msg = str(getattr(exc, "message", exc))[:120]
            print(f"  [{label}] {MODEL} 503 (attempt {attempt}): {msg}")
            time.sleep(2.0 * attempt)
    print(f"  [{label}] falling back to {FALLBACK_MODEL}")
    return fn(FALLBACK_MODEL), FALLBACK_MODEL


def stage_chat_text() -> None:
    print(f"\n[stage 1] chat_text against {MODEL}")
    def _call(model):
        return llm.chat_text(
            model=model,
            system="You answer in exactly one short sentence.",
            user="What is RDF in 20 words or fewer?",
            max_tokens=120,
        )
    out, used = _with_retry(_call, label="stage 1")
    print(f"  [{used}] -> {out!r}")
    assert out, "empty response"


def stage_call_with_tool() -> None:
    print(f"\n[stage 2] call_with_tool against {MODEL}")
    def _call(model):
        return llm.call_with_tool(
            model=model,
            system="Extract entities from the user's text.",
            user=(
                'Section 5 of the Data Protection Act 2020 defines '
                '"data controller" as a person who determines the purposes '
                'of processing.'
            ),
            tool_name="extract_entities",
            tool_description="Return the entities you can identify in the text.",
            tool_schema={
                "type": "object",
                "properties": {
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id":    {"type": "string"},
                                "label": {"type": "string"},
                                "kind":  {
                                    "type": "string",
                                    "enum": ["Section", "Definition", "Statute"],
                                },
                            },
                            "required": ["id", "label", "kind"],
                        },
                    }
                },
                "required": ["entities"],
            },
            max_tokens=600,
        )
    result, used = _with_retry(_call, label="stage 2")
    print(f"  [{used}] finish_reason={result.finish_reason}  output_tokens={result.output_tokens}")
    print(f"  arguments={json.dumps(result.arguments, indent=2)}")
    assert result.arguments.get("entities"), "model returned no entities"


def stage_extractor_end_to_end() -> None:
    print(f"\n[stage 3] full extractor.call_llm against {MODEL} (compliance pack)")
    text = (
        "5.--(1) A data controller shall comply with the data protection "
        "standards set out in section 6. (2) In this section, \"data "
        "controller\" means the person who, alone or jointly with others, "
        "determines the purposes for which and the manner in which any "
        "personal data is or is to be processed."
    )
    def _call(model):
        pack = load_builtin("compliance")
        pack.models.extractor = model
        return extractor_engine.call_llm(
            pack=pack,
            text=text,
            doc_id="gemini_smoke",
            prompt_version=pack.prompt.version,
        )
    entities, used = _with_retry(_call, label="stage 3")
    print(f"  [{used}] extracted {len(entities)} entities:")
    print(f"  full first entity: {json.dumps(entities[0], indent=2)}")
    for e in entities:
        cls = str(e.get("class") or e.get("cls") or e.get("type") or "?")[:20]
        eid = str(e.get("id", "?"))[:40]
        label = str(e.get("label", "?"))
        print(f"   * {cls:<20} {eid:<40} {label}")
    assert entities, "extractor returned zero entities"


if __name__ == "__main__":
    stage_chat_text()
    stage_call_with_tool()
    stage_extractor_end_to_end()
    print("\n[ok] all three Gemini smoke stages passed.")
