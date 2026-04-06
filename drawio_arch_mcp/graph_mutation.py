"""
Deterministic graph mutation: apply structured patches to a normalized graph.

Supported operations (via ``patch`` dict):
  - add_nodes      : list[NodeDict]
  - remove_nodes   : list[str]          (node ids)
  - update_nodes   : list[dict]         (partial dicts keyed by ``id``)
  - add_edges      : list[EdgeDict]
  - remove_edges   : list[str]          (edge ids)
  - update_edges   : list[dict]         (partial dicts keyed by ``id``)

All mutations are applied to a **deep copy** of the input graph.
Warnings are collected for anything ambiguous or unsafe.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from drawio_arch_mcp.models import (
    GRAPH_MODEL_VERSION,
    DiagramGraphDict,
    EdgeDict,
    MutationWarningDict,
    NodeDict,
)


def _warn(code: str, msg: str, ids: list[str] | None = None) -> MutationWarningDict:
    w: MutationWarningDict = {"code": code, "message": msg}
    if ids:
        w["related_ids"] = ids
    return w


def apply_graph_patch(
    graph: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    """
    Apply a structured patch and return ``{"graph": ..., "mutation_warnings": [...]}``.

    The input graph is not modified; a deep copy is used.
    """
    g: dict[str, Any] = deepcopy(graph)
    g.setdefault("graph_version", GRAPH_MODEL_VERSION)
    warnings: list[MutationWarningDict] = []

    node_idx: dict[str, int] = {n["id"]: i for i, n in enumerate(g.get("nodes", []))}
    edge_idx: dict[str, int] = {e["id"]: i for i, e in enumerate(g.get("edges", []))}

    # --- remove_edges first (before nodes, so orphan checks make sense) ---
    for eid in patch.get("remove_edges", []):
        if eid in edge_idx:
            g["edges"][edge_idx[eid]] = None  # mark for sweep
            for page in g.get("pages", []):
                if eid in page.get("edge_ids", []):
                    page["edge_ids"].remove(eid)
        else:
            warnings.append(_warn("EDGE_NOT_FOUND", f"Cannot remove edge {eid!r}: not in graph.", [eid]))
    g["edges"] = [e for e in g.get("edges", []) if e is not None]
    edge_idx = {e["id"]: i for i, e in enumerate(g["edges"])}

    # --- remove_nodes ---
    for nid in patch.get("remove_nodes", []):
        if nid in node_idx:
            g["nodes"][node_idx[nid]] = None
            for page in g.get("pages", []):
                if nid in page.get("node_ids", []):
                    page["node_ids"].remove(nid)
            orphaned = [e["id"] for e in g.get("edges", []) if e and (e["source"] == nid or e["target"] == nid)]
            if orphaned:
                warnings.append(_warn(
                    "ORPHANED_EDGES",
                    f"Removing node {nid!r} orphans {len(orphaned)} edge(s).",
                    orphaned,
                ))
                for oe in orphaned:
                    idx = edge_idx.get(oe)
                    if idx is not None and g["edges"][idx] is not None:
                        g["edges"][idx] = None
                        for page in g.get("pages", []):
                            if oe in page.get("edge_ids", []):
                                page["edge_ids"].remove(oe)
        else:
            warnings.append(_warn("NODE_NOT_FOUND", f"Cannot remove node {nid!r}: not in graph.", [nid]))
    g["nodes"] = [n for n in g.get("nodes", []) if n is not None]
    g["edges"] = [e for e in g.get("edges", []) if e is not None]
    node_idx = {n["id"]: i for i, n in enumerate(g["nodes"])}
    edge_idx = {e["id"]: i for i, e in enumerate(g["edges"])}

    # --- add_nodes ---
    for new_node in patch.get("add_nodes", []):
        nid = new_node.get("id", "")
        if not nid:
            warnings.append(_warn("MISSING_ID", "Skipped add_node with no id."))
            continue
        if nid in node_idx:
            warnings.append(_warn("DUPLICATE_NODE", f"Node {nid!r} already exists; skipped add.", [nid]))
            continue
        node: dict[str, Any] = {
            "id": nid,
            "label": new_node.get("label", ""),
            "kind": new_node.get("kind", "unknown"),
            "shape_type": new_node.get("shape_type", "default"),
            "geometry": new_node.get("geometry", {}),
            "style": new_node.get("style", "rounded=1;whiteSpace=wrap;html=1;"),
            "metadata": new_node.get("metadata", {}),
            "source_xml_id": new_node.get("source_xml_id", nid),
        }
        if "page_id" in new_node:
            node["page_id"] = new_node["page_id"]
        g["nodes"].append(node)
        node_idx[nid] = len(g["nodes"]) - 1
        page_id = new_node.get("page_id")
        if page_id:
            for page in g.get("pages", []):
                if page["id"] == page_id:
                    page["node_ids"].append(nid)
                    break

    # --- update_nodes ---
    for upd in patch.get("update_nodes", []):
        nid = upd.get("id", "")
        if nid not in node_idx:
            warnings.append(_warn("NODE_NOT_FOUND", f"Cannot update node {nid!r}: not in graph.", [nid]))
            continue
        target = g["nodes"][node_idx[nid]]
        for key in ("label", "kind", "shape_type", "geometry", "style", "metadata"):
            if key in upd:
                target[key] = upd[key]

    # --- add_edges ---
    for new_edge in patch.get("add_edges", []):
        eid = new_edge.get("id", "")
        if not eid:
            warnings.append(_warn("MISSING_ID", "Skipped add_edge with no id."))
            continue
        if eid in edge_idx:
            warnings.append(_warn("DUPLICATE_EDGE", f"Edge {eid!r} already exists; skipped add.", [eid]))
            continue
        src = new_edge.get("source", "")
        tgt = new_edge.get("target", "")
        if src and src not in node_idx:
            warnings.append(_warn("MISSING_ENDPOINT", f"Edge {eid!r} source {src!r} not in graph.", [eid, src]))
        if tgt and tgt not in node_idx:
            warnings.append(_warn("MISSING_ENDPOINT", f"Edge {eid!r} target {tgt!r} not in graph.", [eid, tgt]))
        edge: dict[str, Any] = {
            "id": eid,
            "label": new_edge.get("label", ""),
            "source": src,
            "target": tgt,
            "kind": new_edge.get("kind", "unknown"),
            "style": new_edge.get("style", "endArrow=block;html=1;"),
            "source_xml_id": new_edge.get("source_xml_id", eid),
        }
        if "page_id" in new_edge:
            edge["page_id"] = new_edge["page_id"]
        g["edges"].append(edge)
        edge_idx[eid] = len(g["edges"]) - 1
        page_id = new_edge.get("page_id")
        if page_id:
            for page in g.get("pages", []):
                if page["id"] == page_id:
                    page["edge_ids"].append(eid)
                    break

    # --- update_edges ---
    for upd in patch.get("update_edges", []):
        eid = upd.get("id", "")
        if eid not in edge_idx:
            warnings.append(_warn("EDGE_NOT_FOUND", f"Cannot update edge {eid!r}: not in graph.", [eid]))
            continue
        target = g["edges"][edge_idx[eid]]
        for key in ("label", "source", "target", "kind", "style"):
            if key in upd:
                target[key] = upd[key]
        if "source" in upd and upd["source"] not in node_idx:
            warnings.append(_warn("MISSING_ENDPOINT", f"Updated edge {eid!r} source {upd['source']!r} not in graph.", [eid]))
        if "target" in upd and upd["target"] not in node_idx:
            warnings.append(_warn("MISSING_ENDPOINT", f"Updated edge {eid!r} target {upd['target']!r} not in graph.", [eid]))

    return {"graph": g, "mutation_warnings": warnings}
