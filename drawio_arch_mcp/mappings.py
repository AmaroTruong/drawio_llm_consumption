"""
Load and resolve component_map.json and aliases.json for context fusion.

Mapping files are deterministic: they map diagram component labels to
repo paths, doc paths, owners, and aliases. No inference happens here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from drawio_arch_mcp.models import AliasConfig, ComponentMapEntry, MappingConfig


def _default_mappings_dir() -> Path | None:
    raw = os.environ.get("DRAWIO_MCP_MAPPINGS_DIR", "").strip()
    if raw:
        p = Path(raw).expanduser().resolve()
        return p if p.is_dir() else None
    return None


def load_component_map(mappings_dir: str | Path | None = None) -> MappingConfig:
    """Load ``component_map.json`` from *mappings_dir* or env default."""
    d = Path(mappings_dir) if mappings_dir else _default_mappings_dir()
    if not d:
        return MappingConfig(version="1.0", components={})
    path = d / "component_map.json"
    if not path.is_file():
        return MappingConfig(version="1.0", components={})
    raw = json.loads(path.read_text(encoding="utf-8"))
    return MappingConfig(
        version=raw.get("version", "1.0"),
        components={
            name: ComponentMapEntry(
                repo_path=entry.get("repo_path"),
                docs_paths=entry.get("docs_paths", []),
                owner=entry.get("owner"),
                tags=entry.get("tags", []),
            )
            for name, entry in raw.get("components", {}).items()
        },
    )


def load_aliases(mappings_dir: str | Path | None = None) -> AliasConfig:
    """Load ``aliases.json`` from *mappings_dir* or env default."""
    d = Path(mappings_dir) if mappings_dir else _default_mappings_dir()
    if not d:
        return AliasConfig(version="1.0", aliases={})
    path = d / "aliases.json"
    if not path.is_file():
        return AliasConfig(version="1.0", aliases={})
    raw = json.loads(path.read_text(encoding="utf-8"))
    return AliasConfig(
        version=raw.get("version", "1.0"),
        aliases=raw.get("aliases", {}),
    )


def resolve_component_name(
    name: str,
    aliases: AliasConfig,
    component_map: MappingConfig,
) -> str:
    """
    Resolve a name/alias to the canonical component name.

    Resolution order:
    1. Exact match in component_map
    2. Case-insensitive match in component_map
    3. Exact match in aliases
    4. Case-insensitive match in aliases
    5. Return original name unchanged
    """
    if name in component_map["components"]:
        return name

    lower_map = {k.lower(): k for k in component_map["components"]}
    if name.lower() in lower_map:
        return lower_map[name.lower()]

    if name in aliases["aliases"]:
        return aliases["aliases"][name]

    lower_aliases = {k.lower(): v for k, v in aliases["aliases"].items()}
    if name.lower() in lower_aliases:
        return lower_aliases[name.lower()]

    return name


def get_component_entry(
    component_name: str,
    mappings_dir: str | Path | None = None,
) -> tuple[str, ComponentMapEntry | None]:
    """
    Resolve *component_name* via aliases and return (canonical_name, entry_or_None).
    """
    cmap = load_component_map(mappings_dir)
    aliases = load_aliases(mappings_dir)
    canonical = resolve_component_name(component_name, aliases, cmap)
    return canonical, cmap["components"].get(canonical)
