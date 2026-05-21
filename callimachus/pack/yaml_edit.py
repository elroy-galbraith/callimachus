"""Round-trip-safe edits to pack.yaml.

The rest of the codebase reads pack.yaml via PyYAML's `safe_load` -- fast,
simple, and we don't need formatting fidelity for reads. But the UI write
path (PATCH /api/projects/{name}/pack/models) round-trips the file, and
naive `safe_dump` strips every comment and reorders / reformats. pack.yaml
ships with explanatory comments (e.g. the "Swap the provider prefix..."
hint over `models:`), and users hand-edit their project copies too, so a
silent comment-eating write would be a real loss.

ruamel.yaml's default round-trip loader preserves comments, key order,
quoting style, and indentation. We mutate the loaded structure in place
(rather than building a fresh dict) so comments *inside* the touched
block survive too.
"""
from __future__ import annotations

import io

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap


def _rt_yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    return y


def update_pack_models(
    text: str,
    *,
    extractor: str | None = None,
    ask: str | None = None,
) -> str:
    """Return `text` with `models.extractor` / `models.ask` updated.

    Comments, key order, and formatting are preserved. None for either
    field leaves the existing value unchanged. Output is valid YAML
    readable by `yaml.safe_load`.
    """
    yaml = _rt_yaml()
    data = yaml.load(io.StringIO(text))
    if data is None:
        data = CommentedMap()
    if "models" not in data or data["models"] is None:
        data["models"] = CommentedMap()
    if extractor is not None:
        data["models"]["extractor"] = extractor
    if ask is not None:
        data["models"]["ask"] = ask
    buf = io.StringIO()
    yaml.dump(data, buf)
    return buf.getvalue()
