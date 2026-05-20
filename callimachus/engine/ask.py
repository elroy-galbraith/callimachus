"""Natural-language → SPARQL → answer pipeline.

Lifted from scripts/ask.py. Two LLM calls per question: synthesize the
SPARQL (tool-use), then summarise the rows. Both prompts are still
domain-leaning ("legal-research assistant", "Caribbean data-protection")
in Phase B; making these per-pack templates is a Phase C task.
"""
from __future__ import annotations

import json
import sys
from textwrap import dedent

import anthropic

try:
    import pyoxigraph
except ImportError as _exc:
    raise ImportError(
        "pyoxigraph is required by callimachus.engine.ask. "
        "Install with: pip install pyoxigraph"
    ) from _exc

from callimachus.pack import DomainPack


def entity_catalog(store: "pyoxigraph.Store", pack: DomainPack) -> str:
    """Compact list of every named entity: <prefix>:id · class · label."""
    q = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?s ?label ?cls WHERE {
        ?s a ?cls ;
           rdfs:label ?label .
    }
    ORDER BY ?cls ?label
    """
    rows = list(store.query(q))
    lines = []
    for r in rows:
        iri = str(r["s"]).strip("<>")
        if not iri.startswith(pack.entity_iri):
            continue
        local = iri[len(pack.entity_iri):]
        cls = str(r["cls"]).rsplit("/", 1)[-1].rstrip(">")
        label = str(r["label"]).split('"')[1] if '"' in str(r["label"]) else str(r["label"])
        lines.append(f"  {pack.entity_prefix}:{local}  ({cls})  — {label}")
    return "\n".join(lines) if lines else "  (vault is empty)"


def few_shot_examples(pack: DomainPack) -> str:
    """Concatenate every competency-question SPARQL file as in-context examples."""
    if pack.pack_dir is None:
        return "(no example queries available)"
    blocks = []
    for cq in pack.competency_questions:
        path = pack.pack_dir / cq.file
        if path.exists():
            blocks.append(f"# {cq.id}\n{path.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(blocks) if blocks else "(no example queries available)"


def synthesize_sparql(
    client: anthropic.Anthropic,
    model: str,
    question: str,
    schema: str,
    catalog: str,
    examples: str,
) -> tuple[str, str]:
    system = dedent("""\
        You are a SPARQL expert helping a researcher query a small RDF graph
        about Caribbean data-protection law. Generate exactly one SPARQL SELECT
        query that answers the user's question.

        Rules:
          • Use the prefixes shown in the schema and examples.
          • Always SELECT rdfs:label for any entity you return, so a human can
            read the result.
          • Use OPTIONAL for properties that may be absent.
          • Prefer label-based or class-based matches over hard-coded IRIs when
            the question is generic — that way new entities show up too.
          • If the question is open-ended, return the entity IRI plus its label
            and class, ordered by class then label.
    """)
    user = dedent(f"""\
        # Schema
        ```turtle
        {schema}
        ```

        # Entities currently in the graph
        ```
        {catalog}
        ```

        # Example queries (the project's competency questions)
        {examples}

        # Question
        {question}

        Use the `submit_sparql` tool to return your query and a one-sentence rationale.
    """)
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        tools=[
            {
                "name": "submit_sparql",
                "description": "Submit the final SPARQL query that answers the question.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sparql": {
                            "type": "string",
                            "description": "Complete SPARQL query, including PREFIX lines.",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "One sentence explaining how the query answers the question.",
                        },
                    },
                    "required": ["sparql", "rationale"],
                    "additionalProperties": False,
                },
            }
        ],
        tool_choice={"type": "tool", "name": "submit_sparql"},
        messages=[{"role": "user", "content": user}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input["sparql"], block.input["rationale"]
    raise RuntimeError("model did not return a SPARQL query")


def summarise(
    client: anthropic.Anthropic,
    model: str,
    question: str,
    sparql: str,
    rationale: str,
    results: dict,
) -> str:
    system = dedent("""\
        You are a legal-research assistant summarising SPARQL query results in
        plain prose for a researcher. Cite each entity as
        [Label](vault/<local-iri>.md), where <local-iri> is the part of the IRI
        after .../entity/. Be honest about empty results — say so directly. Keep
        the answer under 150 words.
    """)
    user = dedent(f"""\
        Question: {question}

        Generated SPARQL ({rationale}):
        ```sparql
        {sparql}
        ```

        Results (JSON):
        ```json
        {json.dumps(results, indent=2)}
        ```

        Answer the question.
    """)
    resp = client.messages.create(
        model=model,
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def run_sparql(store: "pyoxigraph.Store", sparql: str) -> dict:
    results = store.query(sparql)
    if isinstance(results, pyoxigraph.QuerySolutions):
        variables = [str(v) for v in results.variables]
        rows = []
        for sol in results:
            row = {}
            for v in results.variables:
                term = sol[v]
                row[str(v)] = str(term) if term is not None else None
            rows.append(row)
        return {"kind": "select", "variables": variables, "rows": rows}
    if isinstance(results, bool):
        return {"kind": "ask", "value": results}
    return {"kind": "graph", "triples": [str(t) for t in results]}


def print_results(results: dict) -> None:
    if results["kind"] == "select":
        rows = results["rows"]
        if not rows:
            print("  (no rows)")
            return
        cols = results["variables"]
        widths = {c: max(len(c), max(len(str(r[c] or "")) for r in rows)) for c in cols}
        print("  " + "  ".join(c.ljust(widths[c]) for c in cols))
        print("  " + "  ".join("-" * widths[c] for c in cols))
        for r in rows:
            print("  " + "  ".join(str(r[c] or "").ljust(widths[c]) for c in cols))
        print(f"\n  {len(rows)} row(s)")
    elif results["kind"] == "ask":
        print(f"  ASK → {results['value']}")
    else:
        for t in results["triples"]:
            print(f"  {t}")
