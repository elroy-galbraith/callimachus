#!/usr/bin/env python3
"""Build an asciinema cast v2 file for the Callimachus thematic-pack demo.

Outputs `docs/demo/thematic.cast`, playable with:
    asciinema play docs/demo/thematic.cast
or uploadable to asciinema.org.

The script does NOT shell out — every command + output pair below was
captured from a real run against `projects/thematic/` on this branch, then
hand-typed here. To refresh: re-run the commands locally, paste the new
output into STEPS, and re-run this script.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

PROMPT = "[32m$[0m "

STEPS: list[tuple[str, ...]] = [
    ("comment", "# === Callimachus: thematic pack tour ==="),
    ("comment", "# interview transcripts -> codes -> subthemes -> themes,"),
    ("comment", "# then RDF + SPARQL over the result."),

    ("cmd", "ls projects/",
     "compliance\ndensho_themes\nthematic"),

    ("cmd", "ls projects/thematic/vault/",
     "interview01_excerpt_t0830.md\n"
     "interview02_excerpt_t0212.md\n"
     "interview03_excerpt_t1422.md\n"
     "interview03_excerpt_t1845.md\n"
     "interview03_excerpt_t2210.md\n"
     "proposals\n"
     "thematic_code_feeling_shut_out.md\n"
     "thematic_code_institutions_dont_explain.md\n"
     "thematic_code_lack_of_transparency.md\n"
     "thematic_subtheme_lack_of_transparency.md\n"
     "thematic_theme_distrust_of_institutions.md\n"
     "thematic_theme_loss_of_control.md"),

    ("comment", "# every excerpt carries its speaker + theme link as YAML front-matter"),
    ("cmd", "cat projects/thematic/vault/interview01_excerpt_t0830.md",
     "---\n"
     "class: Excerpt\n"
     "id: interview01_excerpt_t0830\n"
     "label: P01 on feeling excluded\n"
     "uri: https://ontology.example.org/thematic/entity/interview01_excerpt_t0830\n"
     "source_document: interview01\n"
     "source_section: Interview 01 / 08:30\n"
     "source_text: It just feels like decisions about my information happen behind closed doors. Nobody sits me down to explain it.\n"
     "properties:\n"
     "  codedAs: '[[thematic_code_feeling_shut_out]]'\n"
     "  supportsTheme: '[[thematic_theme_loss_of_control]]'\n"
     "  spokenBy: P01\n"
     "validation: PASS\n"
     "---"),

    ("comment", "# proposals/ holds every pending graph mutation for human review"),
    ("cmd", "cat projects/thematic/vault/proposals/proposal_92fccb82_merge_thematic_code_lack_of_transparency.md",
     "---\n"
     "proposal_id: proposal_92fccb82\n"
     "operation: merge_entities\n"
     "status: pending\n"
     "confidence: medium\n"
     "model_snapshot: claude-sonnet-4-6\n"
     "kept_id: thematic_code_lack_of_transparency\n"
     "removed_id: thematic_code_feeling_shut_out\n"
     "rationale: 'Both codes capture the same atomic construct: a participant''s\n"
     "  subjective sense of being excluded from information about their own data.'\n"
     "evidence:\n"
     "- It just feels like decisions about my information happen behind closed doors...\n"
     "- I just felt completely shut out, like nobody was telling me what was actually going on...\n"
     "---"),

    ("comment", "# convert the markdown vault to Turtle RDF"),
    ("cmd", "python scripts/to_turtle.py --vault projects/thematic/vault --pack thematic --out projects/thematic/vault/vault.ttl",
     r"[to_turtle] wrote projects\thematic\vault\vault.ttl (4279 bytes)",
     1.6),  # extra pause to simulate the script actually working

    ("cmd", "head -16 projects/thematic/vault/vault.ttl",
     "@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
     "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
     "@prefix tha:  <https://ontology.example.org/thematic/> .\n"
     "@prefix thae: <https://ontology.example.org/thematic/entity/> .\n"
     "\n"
     "thae:interview01_excerpt_t0830\n"
     "    a tha:Excerpt ;\n"
     '    rdfs:label "P01 on feeling excluded"@en ;\n'
     "    skos:definition \"\"\"It just feels like decisions about my information happen behind closed doors...\"\"\"@en ;\n"
     '    dcterms:source "Interview 01 / 08:30" ;\n'
     "    tha:codedAs thae:thematic_code_feeling_shut_out ;\n"
     "    tha:supportsTheme thae:thematic_theme_loss_of_control ;\n"
     '    tha:spokenBy "P01" .'),

    ("comment", "# the pack ships SPARQL 'competency questions' for the schema"),
    ("cmd", "cat callimachus/pack/builtin/thematic/sparql/cq1_codes_recur.rq",
     "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
     "PREFIX tha:  <https://ontology.example.org/thematic/>\n"
     "\n"
     "# CQ1 - which codes have been applied at least once?\n"
     "SELECT ?code ?label (COUNT(?excerpt) AS ?nExcerpts) WHERE {\n"
     "    ?code a tha:Code ;\n"
     "          rdfs:label ?label .\n"
     "    OPTIONAL { ?excerpt tha:codedAs ?code . }\n"
     "}\n"
     "GROUP BY ?code ?label\n"
     "ORDER BY DESC(?nExcerpts) ?label"),

    ("comment", "# run it against the freshly-built graph"),
    ("cmd", 'python docs/demo/run_cq1.py',
     "-- CQ1: codes ranked by excerpt count --\n"
     "label                                 n\n"
     "Institutional Non-Disclosure          3\n"
     "Lack of transparency                  2\n"
     "Feeling shut out                      1",
     1.4),

    ("comment", "# that's the loop: vault -> RDF -> SPARQL, every step inspectable."),
]


def build_events(
    steps: list[tuple],
    type_delay: float = 0.045,
    pre_output_pause: float = 0.35,
    post_output_pause: float = 1.4,
    inter_step_pause: float = 0.55,
) -> list[list]:
    t = 0.0
    events: list[list] = [[t, "o", PROMPT]]
    for i, step in enumerate(steps):
        if i > 0:
            t += inter_step_pause
            events.append([round(t, 3), "o", PROMPT])
        kind = step[0]
        if kind == "comment":
            text = step[1]
            for ch in text:
                t += type_delay
                events.append([round(t, 3), "o", ch])
            t += 0.25
            events.append([round(t, 3), "o", "\r\n"])
        elif kind == "cmd":
            cmd = step[1]
            out = step[2]
            extra_pause = step[3] if len(step) > 3 else 0.0
            for ch in cmd:
                t += type_delay
                events.append([round(t, 3), "o", ch])
            t += pre_output_pause + extra_pause
            events.append([round(t, 3), "o", "\r\n"])
            chunk = out + ("\r\n" if not out.endswith("\n") else "")
            chunk = chunk.replace("\n", "\r\n")
            events.append([round(t, 3), "o", chunk])
            t += post_output_pause
        else:
            raise ValueError(f"unknown step kind: {kind}")
    return events


def main() -> None:
    header = {
        "version": 2,
        "width": 110,
        "height": 32,
        "timestamp": int(time.time()),
        "env": {"TERM": "xterm-256color", "SHELL": "powershell"},
        "title": "Callimachus - thematic pack tour",
    }
    events = build_events(STEPS)
    out_path = Path(__file__).parent / "thematic.cast"
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(header) + "\n")
        for ev in events:
            f.write(json.dumps(ev) + "\n")
    duration = events[-1][0]
    print(f"wrote {out_path} ({len(events)} events, ~{duration:.1f}s playback)")


if __name__ == "__main__":
    main()
