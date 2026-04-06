"""
Convert a normalized architecture graph back into valid `.drawio` XML.

The generated file follows the standard mxfile hierarchy:

    mxfile
      └─ diagram  (one per page)
           └─ mxGraphModel
                └─ root
                     ├─ mxCell id="0"                  (root layer)
                     ├─ mxCell id="1" parent="0"       (default layer)
                     ├─ mxCell ... vertex="1"          (nodes/groups)
                     └─ mxCell ... edge="1"            (edges)

Priorities:
  - structural correctness (openable in Draw.io)
  - label, id, style, geometry preservation
  - NOT lossless visual round-trip

See also: drawio-ninja ``drawio.instructions.md`` for hierarchy rules.
"""

from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# Default canvas size
_PAGE_W = 1600
_PAGE_H = 1000
_GRID = 10


def _style_str(style: str) -> str:
    """Ensure style ends with ';' for Draw.io convention."""
    s = style.strip()
    if s and not s.endswith(";"):
        s += ";"
    return s


def _default_node_style(kind: str) -> str:
    defaults: dict[str, str] = {
        "service": "rounded=1;whiteSpace=wrap;html=1;",
        "database": "shape=cylinder;whiteSpace=wrap;html=1;boundedLbl=1;",
        "queue": "shape=cylinder;whiteSpace=wrap;html=1;fillColor=#fff2cc;",
        "gateway": "rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;",
        "external_system": "rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;",
        "storage": "shape=cylinder;whiteSpace=wrap;html=1;",
        "container": "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;fontStyle=1;",
        "swimlane": "swimlane;whiteSpace=wrap;html=1;fillColor=#f5f5f5;",
    }
    return defaults.get(kind, "rounded=1;whiteSpace=wrap;html=1;")


def _default_edge_style() -> str:
    return "endArrow=block;html=1;rounded=0;strokeWidth=2;"


def _xml_id(normalized_id: str) -> str:
    """
    Derive a short XML-safe id from a normalized id like ``n-page-foo``.

    Uses ``source_xml_id`` when available (caller passes it); this is a
    fallback that strips the ``n-`` / ``e-`` / ``g-`` prefix and page segment.
    """
    parts = normalized_id.split("-", 2)
    if len(parts) >= 3:
        return parts[2]
    return normalized_id


def _make_cell(
    parent: ET.Element,
    *,
    cell_id: str,
    value: str = "",
    style: str = "",
    vertex: bool = False,
    edge: bool = False,
    parent_id: str = "1",
    source: str = "",
    target: str = "",
    geo: dict[str, float] | None = None,
    relative_geo: bool = False,
) -> ET.Element:
    """Build an mxCell element and append it to *parent*."""
    attrs: dict[str, str] = {"id": cell_id, "parent": parent_id}
    if value:
        attrs["value"] = html.escape(value, quote=True)
    if style:
        attrs["style"] = _style_str(style)
    if vertex:
        attrs["vertex"] = "1"
    if edge:
        attrs["edge"] = "1"
    if source:
        attrs["source"] = source
    if target:
        attrs["target"] = target

    cell = ET.SubElement(parent, "mxCell", attrib=attrs)

    if geo or relative_geo:
        g_attrs: dict[str, str] = {}
        if relative_geo:
            g_attrs["relative"] = "1"
        else:
            g_attrs["x"] = str(geo.get("x", 0))
            g_attrs["y"] = str(geo.get("y", 0))
            g_attrs["width"] = str(geo.get("width", 120))
            g_attrs["height"] = str(geo.get("height", 60))
        g_attrs["as"] = "geometry"
        ET.SubElement(cell, "mxGeometry", attrib=g_attrs)

    return cell


def graph_to_drawio_xml(graph: dict[str, Any]) -> str:
    """
    Convert a normalized graph dict to a ``.drawio`` XML string.

    Returns well-formed XML that Draw.io can open.
    """
    mxfile = ET.Element("mxfile", attrib={
        "host": "drawio-arch-mcp",
        "modified": "2026-01-01T00:00:00.000Z",
        "agent": "drawio-arch-mcp-v0.2.0",
        "version": "24.0.0",
    })

    pages: list[dict[str, Any]] = graph.get("pages", [])
    if not pages:
        pages = [{"id": "page-0", "name": "Page-1", "node_ids": [], "edge_ids": [], "group_ids": []}]

    nodes_by_id: dict[str, dict[str, Any]] = {n["id"]: n for n in graph.get("nodes", [])}
    edges_by_id: dict[str, dict[str, Any]] = {e["id"]: e for e in graph.get("edges", [])}

    nodes_placed: set[str] = set()
    edges_placed: set[str] = set()

    for page in pages:
        diagram = ET.SubElement(mxfile, "diagram", attrib={
            "id": page.get("id", "page-0"),
            "name": page.get("name", "Page-1"),
        })
        model = ET.SubElement(diagram, "mxGraphModel", attrib={
            "dx": "1422",
            "dy": "794",
            "grid": "1",
            "gridSize": str(_GRID),
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": str(_PAGE_W),
            "pageHeight": str(_PAGE_H),
            "math": "0",
            "shadow": "0",
        })
        root = ET.SubElement(model, "root")

        # Required layer cells
        ET.SubElement(root, "mxCell", attrib={"id": "0"})
        ET.SubElement(root, "mxCell", attrib={"id": "1", "parent": "0"})

        page_node_ids = page.get("node_ids", [])
        page_edge_ids = page.get("edge_ids", [])

        # Emit nodes
        for nid in page_node_ids:
            if nid in nodes_placed:
                continue
            n = nodes_by_id.get(nid)
            if not n:
                continue

            xml_id = n.get("source_xml_id") or _xml_id(nid)
            style = n.get("style") or _default_node_style(n.get("kind", "unknown"))
            parent_xml = n.get("metadata", {}).get("parent", "1")
            if parent_xml in ("0", ""):
                parent_xml = "1"

            _make_cell(
                root,
                cell_id=xml_id,
                value=n.get("label", ""),
                style=style,
                vertex=True,
                parent_id=parent_xml,
                geo=dict(n.get("geometry", {})) or {"x": 0, "y": 0, "width": 120, "height": 60},
            )
            nodes_placed.add(nid)

        # Emit edges
        for eid in page_edge_ids:
            if eid in edges_placed:
                continue
            e = edges_by_id.get(eid)
            if not e:
                continue

            xml_id = e.get("source_xml_id") or _xml_id(eid)
            style = e.get("style") or _default_edge_style()
            src_node = nodes_by_id.get(e.get("source", ""))
            tgt_node = nodes_by_id.get(e.get("target", ""))
            src_xml = (src_node.get("source_xml_id") or _xml_id(e["source"])) if src_node else ""
            tgt_xml = (tgt_node.get("source_xml_id") or _xml_id(e["target"])) if tgt_node else ""

            _make_cell(
                root,
                cell_id=xml_id,
                value=e.get("label", ""),
                style=style,
                edge=True,
                source=src_xml,
                target=tgt_xml,
                relative_geo=True,
            )
            edges_placed.add(eid)

    # Catch any nodes/edges not assigned to a page
    unplaced_nodes = [n for n in graph.get("nodes", []) if n["id"] not in nodes_placed]
    unplaced_edges = [e for e in graph.get("edges", []) if e["id"] not in edges_placed]

    if unplaced_nodes or unplaced_edges:
        last_diagram = list(mxfile)[-1] if len(mxfile) else None
        if last_diagram is not None:
            last_root = last_diagram.find(".//root")
        else:
            last_root = None

        if last_root is None:
            diagram = ET.SubElement(mxfile, "diagram", attrib={"id": "overflow", "name": "Overflow"})
            model = ET.SubElement(diagram, "mxGraphModel")
            last_root = ET.SubElement(model, "root")
            ET.SubElement(last_root, "mxCell", attrib={"id": "0"})
            ET.SubElement(last_root, "mxCell", attrib={"id": "1", "parent": "0"})

        for n in unplaced_nodes:
            xml_id = n.get("source_xml_id") or _xml_id(n["id"])
            style = n.get("style") or _default_node_style(n.get("kind", "unknown"))
            _make_cell(
                last_root,
                cell_id=xml_id,
                value=n.get("label", ""),
                style=style,
                vertex=True,
                geo=dict(n.get("geometry", {})) or {"x": 0, "y": 0, "width": 120, "height": 60},
            )

        for e in unplaced_edges:
            xml_id = e.get("source_xml_id") or _xml_id(e["id"])
            style = e.get("style") or _default_edge_style()
            src_node = nodes_by_id.get(e.get("source", ""))
            tgt_node = nodes_by_id.get(e.get("target", ""))
            src_xml = (src_node.get("source_xml_id") or _xml_id(e["source"])) if src_node else ""
            tgt_xml = (tgt_node.get("source_xml_id") or _xml_id(e["target"])) if tgt_node else ""
            _make_cell(
                last_root,
                cell_id=xml_id,
                value=e.get("label", ""),
                style=style,
                edge=True,
                source=src_xml,
                target=tgt_xml,
                relative_geo=True,
            )

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def write_drawio_file(graph: dict[str, Any], output_path: Path) -> Path:
    """Write graph as ``.drawio`` to *output_path* and return the resolved path."""
    xml = graph_to_drawio_xml(graph)
    output_path.write_text(xml, encoding="utf-8")
    return output_path.resolve()
