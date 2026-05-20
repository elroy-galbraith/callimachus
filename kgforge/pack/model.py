"""DomainPack — Pydantic model for the YAML configuration that drives the engine.

Phase A scope: model declares the shape; load it via loader.py and feed it to
existing scripts as a drop-in replacement for module-level constants.

Renderers (build_entity_schema, render_prompts, etc.) are NOT defined here;
they live in kgforge.engine.* in Phase B. For Phase A the existing scripts
import the model directly and inline-render.
"""
from __future__ import annotations

import warnings
from pathlib import Path
from types import ModuleType  # noqa: F401  (used for the hooks_module annotation)
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    description: str | None = None
    version: str = "0.1.0"
    author: str | None = None


class Namespaces(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_iri: str
    entity_iri: str
    prefix: str = Field(..., pattern=r"^[a-z][a-z0-9]*$")
    entity_prefix: str = Field(..., pattern=r"^[a-z][a-z0-9]*$")


class EntityClass(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., pattern=r"^[A-Z][A-Za-z0-9]*$")
    label: str
    description: str | None = None
    parent: str | None = None
    iri: str | None = None  # auto-derived from namespaces.base_iri + name when None


class EntityProperty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., pattern=r"^[a-z][A-Za-z0-9]*$")
    label: str | None = None
    domain: str | None = None
    range: str | None = None
    iri: str | None = None  # auto-derived; supports overriding to e.g. dcterms:isPartOf
    datatype: bool = False  # True = literal value, no entity link
    prompt_hint: str | None = None


class PromptSpec(BaseModel):
    """Templates rendered with str.format(**context).

    Available placeholders: {doc_id}, {prompt_version}, {few_shot},
    {text_window}, {classes_block}, {properties_block}.
    """
    model_config = ConfigDict(extra="forbid")

    version: str = "v1"
    system: str
    user: str
    few_shot: str = ""
    text_window_chars: int = 8000
    # Cap on tool-call output tokens per chunk. The model emits structured
    # entity JSON via tool use, and exhausting this budget mid-emission
    # produces an empty tool_use input (a hard zero-entities failure, not a
    # partial result). Rule of thumb: ~1 output token per 2 input chars,
    # so leave roughly text_window_chars/2 tokens of headroom.
    max_output_tokens: int = 4096


class CompetencyQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    file: str  # relative to pack dir


class HooksSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: str | None = None  # relative to pack dir; None = no hooks


class ModelsSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extractor: str = "claude-haiku-4-5-20251001"
    ask: str = "claude-sonnet-4-6"


class InboxSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted_extensions: list[str] = Field(default_factory=lambda: [".pdf"])


class DomainPack(BaseModel):
    """The single configuration object the engine consumes.

    Loaded from <pack_dir>/pack.yaml via kgforge.pack.loader.load_pack.
    `pack_dir` is set by the loader and used to resolve relative paths
    (schema.ttl, sparql/*.rq, hooks.py). `hooks_module` is the imported
    Python module if hooks.module is set in the YAML, else None.
    """
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    schema_version: int = 1
    metadata: Metadata
    namespaces: Namespaces
    # min_length=1: a pack with zero classes is meaningless and would break
    # downstream callers that index into class_names for a fallback type.
    classes: list[EntityClass] = Field(..., min_length=1)
    properties: list[EntityProperty] = Field(default_factory=list)
    prompt: PromptSpec
    competency_questions: list[CompetencyQuestion] = Field(default_factory=list)
    hooks: HooksSpec = Field(default_factory=HooksSpec)
    models: ModelsSpec = Field(default_factory=ModelsSpec)
    inbox: InboxSpec = Field(default_factory=InboxSpec)

    # Set by the loader; not present in YAML.
    pack_dir: Path | None = Field(default=None, exclude=True)
    # The loaded hooks module (or None when hooks.module is null / absent).
    # Engine code reads functions off this with getattr(..., None).
    hooks_module: Any | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _validate_references(self) -> DomainPack:
        class_names = {c.name for c in self.classes}
        for c in self.classes:
            if c.parent is not None and c.parent not in class_names:
                raise ValueError(
                    f"class {c.name!r} references unknown parent {c.parent!r}"
                )
        for p in self.properties:
            if p.domain and p.domain not in class_names:
                raise ValueError(
                    f"property {p.name!r} has unknown domain class {p.domain!r}"
                )
            if p.range and not p.datatype and p.range not in class_names:
                # range can be a class OR an XSD datatype (when datatype=True);
                # for object properties we expect it to match a class. Stay
                # warn-only (not raise) so half-built packs still load — the
                # author sees the warning and can fix the typo without being
                # blocked.
                warnings.warn(
                    f"property {p.name!r} has range {p.range!r} which is not "
                    f"a known class in this pack; treating as a placeholder. "
                    f"Known classes: {sorted(class_names)}",
                    UserWarning,
                    stacklevel=2,
                )
        return self

    # ── convenience accessors used by refactored scripts ────────────────────

    @property
    def class_names(self) -> list[str]:
        return [c.name for c in self.classes]

    @property
    def property_names(self) -> list[str]:
        return [p.name for p in self.properties]

    @property
    def prefix(self) -> str:
        return self.namespaces.prefix

    @property
    def entity_prefix(self) -> str:
        return self.namespaces.entity_prefix

    @property
    def base_iri(self) -> str:
        return self.namespaces.base_iri

    @property
    def entity_iri(self) -> str:
        return self.namespaces.entity_iri

    def property_iri(self, prop_name: str) -> str:
        """Return the prefixed IRI to write into Turtle for a property name.

        If the property declares an explicit `iri:` (e.g., dcterms:isPartOf),
        use that verbatim; otherwise derive `<prefix>:<name>`.
        """
        for p in self.properties:
            if p.name == prop_name:
                if p.iri:
                    return p.iri
                return f"{self.namespaces.prefix}:{p.name}"
        raise KeyError(prop_name)

    def property_map(self) -> dict[str, str]:
        """Return {property_name: prefixed_iri} for all properties.

        Drop-in replacement for the hardcoded PROP_MAP dict in to_turtle.py.
        Single pass over self.properties (was O(N²) when delegating to
        property_iri per item).
        """
        return {
            p.name: (p.iri if p.iri else f"{self.namespaces.prefix}:{p.name}")
            for p in self.properties
        }

    def class_iri(self, cls_name: str) -> str:
        for c in self.classes:
            if c.name == cls_name:
                if c.iri:
                    return c.iri
                return f"{self.namespaces.prefix}:{c.name}"
        raise KeyError(cls_name)

    def render_classes_block(self) -> str:
        """Bullet list of classes for the prompt template's {classes_block}."""
        lines = []
        for c in self.classes:
            desc = f": {c.description}" if c.description else ""
            lines.append(f"  - {c.name}{desc}")
        return "\n".join(lines)

    def render_properties_block(self) -> str:
        """Bullet list of properties for {properties_block}."""
        lines = []
        for p in self.properties:
            dom = p.domain or "any"
            rng = p.range or "any"
            hint = f" — {p.prompt_hint}" if p.prompt_hint else ""
            lines.append(f"  - {p.name} ({dom} → {rng}){hint}")
        return "\n".join(lines)

    def schema_property_keys(self) -> dict[str, dict[str, Any]]:
        """JSON-Schema fragment for the `properties` field of an entity.

        Drop-in for the hand-written dict in extractor.py L91-95.
        """
        return {p.name: {"type": "string"} for p in self.properties}
