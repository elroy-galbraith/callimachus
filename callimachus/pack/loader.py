"""Load a DomainPack from a pack directory containing pack.yaml.

Loads + validates the YAML, then optionally imports a `hooks.py` module
relative to the pack directory and attaches it to the pack so engine code
can call domain-specific overrides via getattr.
"""
from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType

import yaml

from callimachus.pack.model import DomainPack

# The compliance pack ships inside the package.
BUILTIN_DIR = Path(__file__).parent / "builtin"


def _load_hooks_module(pack_dir: Path, hook_relpath: str) -> ModuleType | None:
    """Import a hooks.py adjacent to pack.yaml; return None if missing.

    The module is given a unique name (callimachus.pack.user.<pack_name>) to
    avoid collisions when multiple packs each ship their own hooks.py.
    """
    hook_path = pack_dir / hook_relpath
    if not hook_path.exists():
        return None
    mod_name = f"callimachus.pack.user.{pack_dir.name}_hooks"
    spec = importlib.util.spec_from_file_location(mod_name, hook_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def load_pack(pack_dir: str | Path) -> DomainPack:
    """Load and validate the DomainPack at <pack_dir>/pack.yaml.

    Raises pydantic.ValidationError with field locations on bad config.
    Also resolves the optional hooks module declared by `hooks.module`.
    """
    pack_dir = Path(pack_dir).resolve()
    yaml_path = pack_dir / "pack.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"pack.yaml not found in {pack_dir}")

    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    pack = DomainPack.model_validate(raw)
    pack.pack_dir = pack_dir

    if pack.hooks.module:
        pack.hooks_module = _load_hooks_module(pack_dir, pack.hooks.module)

    return pack


@lru_cache(maxsize=8)
def load_builtin(name: str) -> DomainPack:
    """Convenience: load a pack shipped under callimachus/pack/builtin/<name>/."""
    return load_pack(BUILTIN_DIR / name)
