"""
Normalized graph-oriented JSON model for Draw.io diagrams and context fusion.

v0.2.0: graph_version, MutationWarningDict, ReviewFindingDict.
v0.3.0: EvidenceDict, ComponentContextDict, ConsistencyFindingDict,
        ComponentMapEntry, MappingConfig.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict

GRAPH_MODEL_VERSION = "0.3.0"


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


# ── v0.3.0 context-fusion types ──────────────────────────────────────────────


class EvidenceDict(TypedDict):
    """A single piece of evidence from one source."""
    source: str  # "diagram" | "repo" | "docs" | "mapping" | "inference"
    path: NotRequired[str]
    snippet: str
    confidence: NotRequired[str]  # "high" | "medium" | "low"


class RepoFileInfo(TypedDict):
    relative_path: str
    category: str  # "readme", "openapi", "k8s", "helm", "terraform", "adr", "config", "docs", "other"
    size_bytes: int


class DocFileInfo(TypedDict):
    path: str
    format: str  # "html", "md", "xml", "txt"
    title: str
    size_bytes: int


class ComponentMapEntry(TypedDict):
    repo_path: NotRequired[str]
    docs_paths: NotRequired[list[str]]
    owner: NotRequired[str]
    tags: NotRequired[list[str]]


class MappingConfig(TypedDict):
    version: str
    components: dict[str, ComponentMapEntry]


class AliasConfig(TypedDict):
    version: str
    aliases: dict[str, str]


class ComponentContextDict(TypedDict):
    component_name: str
    diagram_evidence: list[EvidenceDict]
    repo_evidence: list[EvidenceDict]
    docs_evidence: list[EvidenceDict]
    mapping_evidence: list[EvidenceDict]
    inferred: list[EvidenceDict]
    warnings: list[str]


class ConsistencyFindingDict(TypedDict):
    severity: str
    category: str
    message: str
    source: str  # which source triggered the finding
    related_components: list[str]
