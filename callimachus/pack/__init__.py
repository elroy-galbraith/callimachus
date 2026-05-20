"""DomainPack: declarative configuration for a knowledge-extraction domain.

A pack lives on disk as a folder containing pack.yaml plus optional
schema.ttl, sparql/*.rq, and hooks.py. The Pydantic model in model.py is
the in-memory representation; loader.py parses the YAML and resolves the
optional hooks module.
"""
from callimachus.pack.model import DomainPack
from callimachus.pack.loader import load_pack, load_builtin

__all__ = ["DomainPack", "load_pack", "load_builtin"]
