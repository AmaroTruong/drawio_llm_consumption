"""
Normalized graph-oriented JSON model for Draw.io diagrams.

This is the contract for ``parse_drawio_file`` output — not a raw XML mapping.

v0.2.0: added ``graph_version``, ``MutationWarningDict``, ``ReviewFindingDict``.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict

GRAPH_MODEL_VERSION = "0.2.0"


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
    graph_version: NotRequired[str]
    pages: list[PageDict]
    nodes: list[NodeDict]
    edges: list[EdgeDict]
    groups: list[GroupDict]
    warnings: list[str]


class MutationWarningDict(TypedDict):
    code: str
    message: str
    related_ids: NotRequired[list[str]]


class ReviewFindingDict(TypedDict):
    severity: str
    category: str
    message: str
    related_ids: list[str]
