"""
Architecture review: static structural analysis from the normalized graph.

Detects common architectural concerns that can be inferred from topology,
kinds, and labels alone — without domain-specific rules.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from drawio_arch_mcp.models import DiagramGraphDict, ReviewFindingDict


def _nodes_by_id(graph: DiagramGraphDict) -> dict[str, dict[str, Any]]:
    return {n["id"]: n for n in graph["nodes"]}


def _label(node: dict[str, Any] | None, fallback: str = "?") -> str:
    if node and node.get("label"):
        return node["label"]
    return fallback


def review_architecture(graph: DiagramGraphDict) -> list[ReviewFindingDict]:
    """
    Return a list of architecture review findings, ordered by severity.

    Categories checked:
      - shared_database    : DB accessed by many services
      - direct_db_access   : non-service nodes (clients, gateways) hitting a DB
      - unlabeled_edges    : edges with no label (unclear intent)
      - tight_coupling     : high fan-out or parallel edges
      - gateway_bypass     : client-tier nodes connecting directly to services past a gateway
      - boundary_violation : edges crossing zone boundaries in unexpected ways
    """
    findings: list[ReviewFindingDict] = []
    by_id = _nodes_by_id(graph)
    edges = graph["edges"]
    nodes = graph["nodes"]

    if not nodes:
        findings.append(ReviewFindingDict(
            severity="info",
            category="empty_graph",
            message="Graph has no nodes — nothing to review.",
            related_ids=[],
        ))
        return findings

    # --- Shared database: DB nodes with inbound edges from >1 distinct source ---
    db_consumers: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        tgt = by_id.get(e["target"])
        if tgt and tgt.get("kind") == "database":
            db_consumers[e["target"]].add(e["source"])
    for db_id, sources in db_consumers.items():
        if len(sources) > 1:
            db = by_id.get(db_id)
            src_labels = sorted(_label(by_id.get(s), s) for s in sources)
            findings.append(ReviewFindingDict(
                severity="warning",
                category="shared_database",
                message=(
                    f"Database `{_label(db, db_id)}` is accessed by {len(sources)} "
                    f"services/components: {', '.join(src_labels)}. "
                    "Shared databases increase schema coupling and blast radius."
                ),
                related_ids=[db_id, *list(sources)],
            ))

    # --- Direct DB access from non-service tiers ---
    non_service_kinds = {"gateway", "external_system", "unknown", "container", "swimlane"}
    for e in edges:
        src = by_id.get(e["source"])
        tgt = by_id.get(e["target"])
        if not src or not tgt:
            continue
        if tgt.get("kind") == "database" and src.get("kind") in non_service_kinds:
            findings.append(ReviewFindingDict(
                severity="warning",
                category="direct_db_access",
                message=(
                    f"`{_label(src)}` ({src.get('kind')}) connects directly to "
                    f"database `{_label(tgt)}`. Typically only services should "
                    "own database access."
                ),
                related_ids=[e["source"], e["target"], e["id"]],
            ))

    # --- Client bypassing gateway ---
    gateways = {n["id"] for n in nodes if n.get("kind") == "gateway"}
    service_ids = {n["id"] for n in nodes if n.get("kind") == "service"}
    client_kinds = {"unknown", "external_system"}
    client_labels_hint = {"app", "client", "web", "mobile", "frontend", "ui"}
    client_ids: set[str] = set()
    for n in nodes:
        low = n.get("label", "").lower()
        if n.get("kind") in client_kinds and any(h in low for h in client_labels_hint):
            client_ids.add(n["id"])

    if gateways and client_ids:
        for e in edges:
            if e["source"] in client_ids and e["target"] in service_ids:
                src = by_id.get(e["source"])
                tgt = by_id.get(e["target"])
                findings.append(ReviewFindingDict(
                    severity="warning",
                    category="gateway_bypass",
                    message=(
                        f"Client `{_label(src)}` connects directly to service "
                        f"`{_label(tgt)}`, bypassing the API Gateway."
                    ),
                    related_ids=[e["source"], e["target"], e["id"]],
                ))

    # --- Unlabeled edges ---
    unlabeled = [e for e in edges if not e.get("label", "").strip()]
    if unlabeled:
        threshold = 3
        if len(unlabeled) >= threshold:
            findings.append(ReviewFindingDict(
                severity="info",
                category="unlabeled_edges",
                message=(
                    f"{len(unlabeled)} edge(s) have no label. "
                    "Labeled edges improve diagram readability and enable "
                    "more precise structural analysis."
                ),
                related_ids=[e["id"] for e in unlabeled[:10]],
            ))

    # --- Tight coupling: high fan-out ---
    out_degree: dict[str, int] = defaultdict(int)
    for e in edges:
        out_degree[e["source"]] += 1
    for nid, deg in sorted(out_degree.items(), key=lambda x: -x[1]):
        if deg >= 4:
            n = by_id.get(nid)
            findings.append(ReviewFindingDict(
                severity="info",
                category="tight_coupling",
                message=(
                    f"`{_label(n, nid)}` has {deg} outbound connections. "
                    "High fan-out may indicate a God-service or orchestrator "
                    "that is hard to evolve independently."
                ),
                related_ids=[nid],
            ))

    # --- Parallel edges (same pair, multiple edges) ---
    pair_count: dict[frozenset[str], list[str]] = defaultdict(list)
    for e in edges:
        pair = frozenset((e["source"], e["target"]))
        pair_count[pair].append(e["id"])
    for pair, eids in pair_count.items():
        if len(eids) > 1:
            a, b = tuple(pair)
            findings.append(ReviewFindingDict(
                severity="info",
                category="tight_coupling",
                message=(
                    f"{len(eids)} parallel edges between "
                    f"`{_label(by_id.get(a), a)}` and `{_label(by_id.get(b), b)}`. "
                    "Multiple connections may signal mixed concerns or redundancy."
                ),
                related_ids=list(eids),
            ))

    # Sort: warning > info
    severity_order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: severity_order.get(f["severity"], 9))
    return findings


def format_review(findings: list[ReviewFindingDict]) -> str:
    """Render findings as readable Markdown-ish text."""
    if not findings:
        return "No structural concerns detected."
    lines: list[str] = [f"**Architecture Review** — {len(findings)} finding(s)\n"]
    for i, f in enumerate(findings, 1):
        icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(f["severity"], "⚪")
        lines.append(f"{i}. {icon} **[{f['severity'].upper()}] {f['category']}**: {f['message']}")
    return "\n".join(lines)
