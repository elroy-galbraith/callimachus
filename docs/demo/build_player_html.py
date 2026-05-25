"""Embed thematic.cast into a self-contained HTML page playable in any browser.

Run after build_cast.py. Output: docs/demo/thematic.html — open with
file:// URL on Windows, no server / WSL / asciinema CLI needed. Uses
asciinema-player v3 from a CDN.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
CAST = HERE / "thematic.cast"
OUT = HERE / "thematic.html"

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Callimachus &mdash; thematic pack tour</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/asciinema-player@3.7.1/dist/bundle/asciinema-player.css">
<style>
  body {{ background: #1a1a1a; color: #ccc; font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 2rem; }}
  h1 {{ font-size: 1.1rem; font-weight: 500; margin: 0 0 1rem; color: #aaa; }}
  #player {{ max-width: 1100px; }}
  .note {{ max-width: 1100px; margin-top: 1rem; font-size: 0.85rem; color: #888; }}
</style>
</head>
<body>
<h1>Callimachus &mdash; thematic pack tour</h1>
<div id="player"></div>
<p class="note">Hand-built cast (real outputs, synthetic timing). Source: <code>docs/demo/build_cast.py</code>.</p>

<script src="https://cdn.jsdelivr.net/npm/asciinema-player@3.7.1/dist/bundle/asciinema-player.min.js"></script>
<script>
const CAST_TEXT = {cast_json};
AsciinemaPlayer.create(
  {{ data: CAST_TEXT }},
  document.getElementById('player'),
  {{ cols: 110, rows: 32, autoPlay: true, theme: 'asciinema', poster: 'npt:0:01' }}
);
</script>
</body>
</html>
"""


def main() -> None:
    cast_text = CAST.read_text(encoding="utf-8")
    html = TEMPLATE.format(cast_json=json.dumps(cast_text))
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")
    print("open with: start docs/demo/thematic.html  (Windows)")


if __name__ == "__main__":
    main()
