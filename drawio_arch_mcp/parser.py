"""
Parse Draw.io (mxGraph / mxfile) XML into a normalized diagram graph.

Supports typical uncompressed ``.drawio`` files. Compressed diagram payloads
are reported as warnings and skipped.
"""

from __future__ import annotations

import html
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element

from drawio_arch_mcp.models import (
    GRAPH_MODEL_VERSION,
    DiagramGraphDict,
    EdgeDict,
    GeometryDict,
    GroupDict,
    NodeDict,
    PageDict,
)

# Draw.io stores HTML snippets in `value`; strip tags for a plain label.
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html_label(raw: str | None) -> str:
    if not raw:
        return ""
    text = html.unescape(raw)
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def _parse_style(style: str | None) -> dict[str, str]:
    if not style:
        return {}
    out: dict[str, str] = {}
    for part in style.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, _, v = part.partition("=")
        out[k.strip()] = v.strip()
    return out


def _shape_from_style(sd: dict[str, str]) -> str:
    return sd.get("shape", "") or sd.get("type", "") or "default"


def infer_node_kind(label: str, style: str, shape_type: str) -> str:
    """Best-effort classification from Draw.io style and label text."""
    low = f"{label} {style} {shape_type}".lower()
    sd = _parse_style(style)

    if "group" in style.lower() or sd.get("container") == "1":
        return "container"
    if "swimlane" in style.lower():
        return "swimlane"
    if "actor" in style.lower() or "umlActor" in style:
        return "external_system"
    if "cloud" in style.lower():
        return "external_system"
    # Label/name before generic cylinder→DB so e.g. "Kafka" on a cylinder stays a queue
    if any(x in low for x in ("kafka", "sqs", "rabbit", "queue", "topic", "event hub")):
        return "queue"
    if any(
        x in low
        for x in (
            "postgres",
            "mysql",
            "mongo",
            "redis",
            "dynamodb",
            "sql",
            "database",
            "db ",
            " rds",
        )
    ):
        return "database"
    if "cylinder" in low or "cylinder3" in low or "datastore" in low:
        return "database"
    if any(x in low for x in ("api gateway", "gateway", "load balancer", "elb ", "nginx")):
        return "gateway"
    if any(x in low for x in ("s3", "blob", "bucket", "storage")):
        return "storage"
    if any(x in low for x in ("third party", "external", "vendor", "saas")):
        return "external_system"
    if "rounded=1" in style or "ellipse" in low or "rhombus" in low:
        return "service"
    return "unknown"


def infer_edge_kind(label: str, style: str) -> str:
    low = f"{label} {style}".lower()
    if any(x in low for x in ("async", "event", "message", "queue", "topic")):
        return "async"
    if any(x in low for x in ("sync", "http", "grpc", "rest", "rpc")):
        return "sync"
    if "dashed" in low:
        return "optional_or_async"
    return "unknown"


def _geometry_from_cell(cell: Element) -> GeometryDict:
    geo = cell.find("mxGeometry")
    if geo is None:
        return {}
    def f(attr: str) -> float | None:
        v = geo.get(attr)
        if v is None or v == "":
            return None
        try:
            return float(v)
        except ValueError:
            return None

    g: GeometryDict = {}
    for key in ("x", "y", "width", "height"):
        val = f(key)
        if val is not None:
            g[key] = val  # type: ignore[literal-required]
    return g


def _is_group_cell(style: str, vertex: bool) -> bool:
    if not vertex:
        return False
    s = style.lower()
    return "group" in s or "swimlane" in s or "container=1" in s


def parse_drawio_bytes(data: bytes, diagram_id: str | None = None) -> DiagramGraphDict:
    """
    Parse raw ``.drawio`` file bytes into a :class:`DiagramGraphDict`.
    """
    did = diagram_id or str(uuid.uuid4())
    warnings: list[str] = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        return DiagramGraphDict(
            diagram_id=did,
            pages=[],
            nodes=[],
            edges=[],
            groups=[],
            warnings=[f"XML parse error: {e}"],
        )

    if root.tag != "mxfile":
        warnings.append(f"Root element is {root.tag!r}, expected mxfile; attempting parse anyway.")

    pages_out: list[PageDict] = []
    nodes_out: list[NodeDict] = []
    edges_out: list[EdgeDict] = []
    groups_out: list[GroupDict] = []

    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    def q(tag: str) -> str:
        return f"{ns}{tag}" if ns else tag

    diagram_els = list(root.findall(q("diagram")))
    if not diagram_els:
        warnings.append("No <diagram> elements found.")
        return DiagramGraphDict(
            diagram_id=did,
            pages=[],
            nodes=[],
            edges=[],
            groups=[],
            warnings=warnings,
        )

    for diagram_el in diagram_els:
        page_id = diagram_el.get("id") or f"page-{len(pages_out)}"
        page_name = diagram_el.get("name") or page_id

        text_content = (diagram_el.text or "").strip()
        if text_content and not list(diagram_el):
            warnings.append(
                f"Page {page_name!r}: diagram body looks compressed or inline-only; "
                "skipping (MVP expects mxGraphModel XML elements)."
            )
            continue

        model_el = diagram_el.find(q("mxGraphModel"))
        if model_el is None:
            warnings.append(f"Page {page_name!r}: missing mxGraphModel; skipped.")
            continue

        root_el = model_el.find(q("root"))
        if root_el is None:
            warnings.append(f"Page {page_name!r}: missing root under mxGraphModel; skipped.")
            continue

        cells = root_el.findall(q("mxCell"))

        page_node_ids: list[str] = []
        page_edge_ids: list[str] = []
        page_group_ids: list[str] = []

        for cell in cells:
            cid = cell.get("id")
            if cid is None:
                warnings.append("Skipped mxCell with no id.")
                continue

            style = cell.get("style") or ""
            parent = cell.get("parent") or ""
            value_raw = cell.get("value")
            label = _strip_html_label(value_raw)

            is_vertex = cell.get("vertex") == "1"
            is_edge = cell.get("edge") == "1"

            if is_vertex:
                shape_type = _shape_from_style(_parse_style(style))
                kind = infer_node_kind(label, style, shape_type)
                meta: dict[str, Any] = {"parent": parent}
                if _is_group_cell(style, True):
                    gid = f"g-{page_id}-{cid}"
                    groups_out.append(
                        GroupDict(
                            id=gid,
                            label=label or f"group-{cid}",
                            kind="swimlane" if "swimlane" in style.lower() else "group",
                            child_node_ids=[],
                            child_group_ids=[],
                            style=style,
                            source_xml_id=cid,
                            page_id=page_id,
                        )
                    )
                    page_group_ids.append(gid)
                    # Also keep as node for edge endpoints that reference group cells
                    nid = f"n-{page_id}-{cid}"
                    nodes_out.append(
                        NodeDict(
                            id=nid,
                            label=label or f"shape-{cid}",
                            kind=kind,
                            shape_type=shape_type or "group",
                            geometry=_geometry_from_cell(cell),
                            style=style,
                            metadata=meta,
                            source_xml_id=cid,
                            page_id=page_id,
                        )
                    )
                    page_node_ids.append(nid)
                else:
                    nid = f"n-{page_id}-{cid}"
                    nodes_out.append(
                        NodeDict(
                            id=nid,
                            label=label or f"shape-{cid}",
                            kind=kind,
                            shape_type=shape_type,
                            geometry=_geometry_from_cell(cell),
                            style=style,
                            metadata=meta,
                            source_xml_id=cid,
                            page_id=page_id,
                        )
                    )
                    page_node_ids.append(nid)
                continue

            if is_edge:
                src_xml = cell.get("source") or ""
                tgt_xml = cell.get("target") or ""
                # Resolve geometry-only edges (no source/target) via mxGeometry
                if not src_xml or not tgt_xml:
                    term = cell.find(f".//{q('mxPoint')}")
                    if term is not None:
                        warnings.append(
                            f"Edge {cid} on page {page_name!r} missing source/target; "
                            "ignored for graph edges."
                        )
                    continue

                eid = f"e-{page_id}-{cid}"
                ek = infer_edge_kind(label, style)
                edges_out.append(
                    EdgeDict(
                        id=eid,
                        label=label,
                        source=f"n-{page_id}-{src_xml}",
                        target=f"n-{page_id}-{tgt_xml}",
                        kind=ek,
                        style=style,
                        source_xml_id=cid,
                        page_id=page_id,
                    )
                )
                page_edge_ids.append(eid)
                continue

            # mxCell without vertex/edge (e.g. layer id="0" / id="1") — skip quietly
            if cid in ("0", "1"):
                continue
            if not is_vertex and not is_edge:
                meta = {"parent": parent, "note": "non-vertex mxCell"}
                nid = f"n-{page_id}-{cid}"
                nodes_out.append(
                    NodeDict(
                        id=nid,
                        label=label or f"cell-{cid}",
                        kind="unknown",
                        shape_type="unclassified",
                        geometry=_geometry_from_cell(cell),
                        style=style,
                        metadata=meta,
                        source_xml_id=cid,
                        page_id=page_id,
                    )
                )
                page_node_ids.append(nid)

        pages_out.append(
            PageDict(
                id=page_id,
                name=page_name,
                node_ids=page_node_ids,
                edge_ids=page_edge_ids,
                group_ids=page_group_ids,
            )
        )

    # Fill group children by mxCell parent id == group's source_xml_id
    for g in groups_out:
        pid = g.get("page_id", "")
        gid_xml = g["source_xml_id"]
        child_nodes: list[str] = []
        child_groups: list[str] = []
        for n in nodes_out:
            if n.get("page_id") != pid:
                continue
            if n["metadata"].get("parent") != gid_xml:
                continue
            if n["source_xml_id"] == gid_xml:
                continue
            if _is_group_cell(n["style"], True):
                child_groups.append(n["id"])
            else:
                child_nodes.append(n["id"])
        g["child_node_ids"] = child_nodes
        g["child_group_ids"] = child_groups

    # Orphan edge check: endpoints not in nodes
    node_ids = {n["id"] for n in nodes_out}
    for e in edges_out:
        if e["source"] not in node_ids:
            warnings.append(
                f"Edge {e['source_xml_id']} references missing source node {e['source']!r}."
            )
        if e["target"] not in node_ids:
            warnings.append(
                f"Edge {e['source_xml_id']} references missing target node {e['target']!r}."
            )

    return DiagramGraphDict(
        diagram_id=did,
        graph_version=GRAPH_MODEL_VERSION,
        pages=pages_out,
        nodes=nodes_out,
        edges=edges_out,
        groups=groups_out,
        warnings=warnings,
    )


def parse_drawio_file(path: Path) -> DiagramGraphDict:
    """Read a ``.drawio`` file from disk and parse it."""
    data = path.read_bytes()
    return parse_drawio_bytes(data, diagram_id=path.stem)
