"""
Export the normalized architecture graph as an explicit, versioned artifact.

The parsed graph is already the right shape; this module exists so
``export_architecture_graph`` has a clear implementation home and can add
post-processing (filter, enrich) without touching the parser.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from drawio_arch_mcp.models import GRAPH_MODEL_VERSION, DiagramGraphDict


def export_graph(graph: DiagramGraphDict) -> dict[str, Any]:
    """
    Return a clean, deep-copied graph dict ready for external consumption.

    Ensures ``graph_version`` is stamped and trims internal-only metadata.
    """
    out: dict[str, Any] = deepcopy(dict(graph))
    out.setdefault("graph_version", GRAPH_MODEL_VERSION)

    nodes: list[dict[str, Any]] = out.get("nodes", [])
    for n in nodes:
        meta = n.get("metadata", {})
        meta.pop("note", None)

    return out
