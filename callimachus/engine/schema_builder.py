"""Build the JSON Schema fed to Claude's tool-use call from a DomainPack.

Lifted from scripts/extractor.py:_build_entity_schema. The "skip
partOfStatute from the LLM-facing schema" filter mirrors the legacy
extractor — partOfStatute is a vault-side fallback predicate, never
emitted by the model.
"""
from __future__ import annotations

from callimachus.pack import DomainPack


def build_entity_schema(pack: DomainPack) -> dict:
    """Construct the tool-use input schema from a DomainPack.

    The schema describes an `entities` array; each item has a `class` enum
    drawn from pack.classes, plus an open-ish `properties` map keyed by
    pack.properties names. Object properties (datatype=False, no explicit
    iri-with-colon override) appear in the schema; the legacy partOfStatute
    is filtered to preserve byte-identical output against the pre-Phase-B
    extractor.
    """
    object_props = {
        p.name: {"type": "string"}
        for p in pack.properties
        if p.name != "partOfStatute"
    }
    return {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "description": "All legal entities extracted from the text.",
                "items": {
                    "type": "object",
                    "properties": {
                        "class": {
                            "type": "string",
                            "enum": pack.class_names,
                            "description": "OWL class this entity belongs to.",
                        },
                        "id": {
                            "type": "string",
                            "pattern": "^[a-z][a-z0-9_]*$",
                            "description": "Snake-case identifier, prefixed with doc_id.",
                        },
                        "label": {
                            "type": "string",
                            "description": "Human-readable name.",
                        },
                        "source_section": {
                            "type": "string",
                            "description": "Section reference, e.g. §6 or §2(1)(a).",
                        },
                        "source_text": {
                            "type": "string",
                            "description": "Verbatim statutory text being encoded (max ~300 chars).",
                        },
                        "properties": {
                            "type": "object",
                            "description": "Ontology property values (entity IDs, not labels).",
                            "properties": object_props,
                            "additionalProperties": False,
                        },
                    },
                    "required": ["class", "id", "label", "source_section", "source_text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["entities"],
        "additionalProperties": False,
    }
