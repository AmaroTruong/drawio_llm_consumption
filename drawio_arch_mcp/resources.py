"""
MCP resources: expose stable, read-only artifacts as MCP resources.

Resources are registered in server.py via the ``@mcp.resource()`` decorator.
This module provides the helper functions that produce the resource content.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drawio_arch_mcp.mappings import (
    get_component_entry,
    load_aliases,
    load_component_map,
)


def graph_resource(graph: dict[str, Any]) -> str:
    """Serialize a parsed graph to compact JSON for MCP resource consumption."""
    return json.dumps(graph, indent=2)


def component_summary_resource(
    component_name: str,
    graph: dict[str, Any],
    mappings_dir: str = "",
) -> str:
    """Build a plain-text summary for a single component."""
    canonical, entry = get_component_entry(component_name, mappings_dir or None)

    lines = [f"# Component: {canonical}", ""]

    if entry:
        if entry.get("owner"):
            lines.append(f"Owner: {entry['owner']}")
        if entry.get("repo_path"):
            lines.append(f"Repo: {entry['repo_path']}")
        if entry.get("tags"):
            lines.append(f"Tags: {', '.join(entry['tags'])}")
        if entry.get("docs_paths"):
            lines.append(f"Docs: {len(entry['docs_paths'])} path(s)")
    else:
        lines.append("No mapping entry found.")

    # Diagram presence
    low = canonical.lower()
    matched_nodes = [n for n in graph.get("nodes", []) if low in n.get("label", "").lower()]
    if matched_nodes:
        lines.append("")
        lines.append(f"Diagram nodes ({len(matched_nodes)}):")
        for n in matched_nodes:
            lines.append(f"  - {n['label']} (kind={n['kind']})")

    return "\n".join(lines)


def mapping_resource(mappings_dir: str = "") -> str:
    """Return component_map.json content as formatted JSON."""
    cmap = load_component_map(mappings_dir or None)
    return json.dumps(dict(cmap), indent=2)


def aliases_resource(mappings_dir: str = "") -> str:
    """Return aliases.json content as formatted JSON."""
    al = load_aliases(mappings_dir or None)
    return json.dumps(dict(al), indent=2)
