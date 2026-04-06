"""
Normalized graph-oriented JSON model for Draw.io diagrams.

This is the contract for ``parse_drawio_file`` output — not a raw XML mapping.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class GeometryDict(TypedDict, total=False):
    x: float
    y: float
    width: float
    height: float


class NodeDict(TypedDict):
    id: str
    label: str
    kind: str
    shape_type: str
    geometry: GeometryDict
    style: str
    metadata: dict[str, Any]
    source_xml_id: str
    page_id: NotRequired[str]


class EdgeDict(TypedDict):
    id: str
    label: str
    source: str
    target: str
    kind: str
    style: str
    source_xml_id: str
    page_id: NotRequired[str]


class GroupDict(TypedDict):
    id: str
    label: str
    kind: str
    child_node_ids: list[str]
    child_group_ids: list[str]
    style: str
    source_xml_id: str
    page_id: NotRequired[str]


class PageDict(TypedDict):
    id: str
    name: str
    node_ids: list[str]
    edge_ids: list[str]
    group_ids: list[str]


class DiagramGraphDict(TypedDict):
    diagram_id: str
    pages: list[PageDict]
    nodes: list[NodeDict]
    edges: list[EdgeDict]
    groups: list[GroupDict]
    warnings: list[str]
