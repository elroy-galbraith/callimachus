"""End-to-end extraction: PDF/text → LLM tool-use → vault Markdown files.

Orchestrates pdf_text + chunker + schema_builder + prompt + Anthropic API
+ vault_writer. The script in scripts/extractor.py is now a CLI shim
around this module.

When the input exceeds `pack.prompt.text_window_chars`, the body is
split into chunks via kgforge.engine.chunker and the LLM is called once
per chunk. Each chunk's entities get an `_c<N>` doc_id suffix so IDs
stay unique across chunks; cross-chunk semantic duplicates are
resolved later by the consolidator, not here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import anthropic

from kgforge.engine import (
    chunker as chunker_mod,
    pdf_text,
    prompt as prompt_mod,
    schema_builder,
    vault_writer,
)
from kgforge.pack import DomainPack


def call_llm(
    pack: DomainPack,
    text: str,
    doc_id: str,
    prompt_version: str,
) -> list[dict]:
    """Single-shot extraction call. Returns the raw `entities` list."""
    client = anthropic.Anthropic()
    system, user = prompt_mod.render_prompts(pack, doc_id, prompt_version, text)

    response = client.messages.create(
        model=pack.models.extractor,
        max_tokens=4096,
        system=system,
        tools=[
            {
                "name": "extract_entities",
                "description": "Extract ontology entities from the source text.",
                "input_schema": schema_builder.build_entity_schema(pack),
            }
        ],
        tool_choice={"type": "tool", "name": "extract_entities"},
        messages=[{"role": "user", "content": user}],
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input.get("entities", [])
    return []


def _enrich_source_section(entity: dict, chunk: chunker_mod.Chunk, total: int) -> None:
    """Prepend the chunk locator to source_section in-place."""
    if total <= 1:
        return
    prefix = f"chunk {chunk.index + 1}/{total}"
    if chunk.section_hint:
        prefix = f"{prefix} ({chunk.section_hint})"
    existing = (entity.get("source_section") or "").strip()
    if existing:
        entity["source_section"] = f"{prefix} / {existing}"
    else:
        entity["source_section"] = prefix


def extract(
    pack: DomainPack,
    *,
    pdf_path: Path | None = None,
    text: str | None = None,
    doc_id: str,
    prompt_version: str,
    vault_dir: Path,
    dry_run: bool = False,
) -> list[dict] | list[Path]:
    """Run the full pipeline.

    Returns:
        - list[dict] (raw entities) if dry_run=True
        - list[Path] (written vault files) otherwise
    """
    page_texts: dict[int, str] = {}
    if text is not None:
        body = text
    elif pdf_path is not None:
        # Despite the parameter name, this dispatches by extension:
        # PDFs go through docling/pdfplumber; .txt/.md/.vtt are read as-is.
        body, page_texts = pdf_text.extract_input(pdf_path)
    else:
        raise ValueError("extract: must pass either pdf_path or text")

    max_chars = pack.prompt.text_window_chars
    chunks = chunker_mod.chunk_text(body, max_chars)
    total_chunks = len(chunks)
    if total_chunks > 1:
        print(
            f"[extractor] {len(body):,} chars > {max_chars:,} window; "
            f"split into {total_chunks} chunks",
            file=sys.stderr,
        )

    all_entities: list[dict] = []
    for chunk in chunks:
        # Suffix the doc_id so the LLM's mandated `{doc_id}_` ID prefix
        # naturally disambiguates entities across chunks. The vault writer
        # still records the un-suffixed doc_id as source_document so the
        # whole document remains one logical unit in the Dashboard.
        chunk_doc_id = doc_id if total_chunks == 1 else f"{doc_id}_c{chunk.index}"
        print(
            f"[extractor] calling {pack.models.extractor} "
            f"(doc_id={chunk_doc_id}, {len(chunk.text):,} chars) …",
            file=sys.stderr,
        )
        entities = call_llm(pack, chunk.text, chunk_doc_id, prompt_version)
        for e in entities:
            _enrich_source_section(e, chunk, total_chunks)
        print(
            f"[extractor] chunk {chunk.index + 1}/{total_chunks}: "
            f"{len(entities)} entities",
            file=sys.stderr,
        )
        all_entities.extend(entities)

    print(f"[extractor] {len(all_entities)} entities total", file=sys.stderr)

    # Backfill source_page from the page-text map (PDF inputs only).
    if page_texts:
        matched = 0
        for entity in all_entities:
            page = pdf_text.find_page_for_text(entity.get("source_text", ""), page_texts)
            if page is not None:
                entity["source_page"] = page
                matched += 1
        print(
            f"[extractor] source_page resolved for {matched}/{len(all_entities)} entities",
            file=sys.stderr,
        )

    if dry_run:
        return all_entities

    return vault_writer.write_vault_files(
        all_entities, vault_dir, doc_id, prompt_version, pack.models.extractor, pack
    )
