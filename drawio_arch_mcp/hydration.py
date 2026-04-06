"""
Component context hydration: merge diagram, repo, docs, and mapping sources
into a unified ComponentContextDict per component.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from drawio_arch_mcp.confluence_context import build_docs_evidence
from drawio_arch_mcp.mappings import (
    get_component_entry,
    load_aliases,
    load_component_map,
    resolve_component_name,
)
from drawio_arch_mcp.models import (
    ComponentContextDict,
    DiagramGraphDict,
    EvidenceDict,
)
from drawio_arch_mcp.repo_context import build_repo_evidence


def _diagram_evidence(graph: DiagramGraphDict, component_name: str) -> list[EvidenceDict]:
    """Extract evidence about *component_name* from the parsed diagram."""
    evidence: list[EvidenceDict] = []
    low = component_name.lower()

    for n in graph["nodes"]:
        if n["label"].lower() == low or low in n["label"].lower():
            ev = EvidenceDict(
                source="diagram",
                snippet=(
                    f"Node `{n['label']}` (kind={n['kind']}, shape={n['shape_type']})"
                ),
                confidence="high",
            )
            evidence.append(ev)

    for e in graph["edges"]:
        src_label = ""
        tgt_label = ""
        for n in graph["nodes"]:
            if n["id"] == e["source"]:
                src_label = n["label"]
            if n["id"] == e["target"]:
                tgt_label = n["label"]
        if low in src_label.lower() or low in tgt_label.lower():
            evidence.append(EvidenceDict(
                source="diagram",
                snippet=f"Edge: `{src_label}` → `{tgt_label}` (label={e['label']!r}, kind={e['kind']})",
                confidence="high",
            ))

    for g in graph["groups"]:
        if low in g["label"].lower():
            evidence.append(EvidenceDict(
                source="diagram",
                snippet=f"Group `{g['label']}` contains {len(g['child_node_ids'])} node(s)",
                confidence="medium",
            ))

    return evidence


def _mapping_evidence(
    component_name: str,
    entry: dict[str, Any] | None,
) -> list[EvidenceDict]:
    evidence: list[EvidenceDict] = []
    if not entry:
        evidence.append(EvidenceDict(
            source="mapping",
            snippet=f"No mapping entry found for `{component_name}`.",
            confidence="low",
        ))
        return evidence

    parts: list[str] = []
    if entry.get("repo_path"):
        parts.append(f"repo_path={entry['repo_path']}")
    if entry.get("owner"):
        parts.append(f"owner={entry['owner']}")
    if entry.get("tags"):
        parts.append(f"tags={entry['tags']}")
    docs = entry.get("docs_paths", [])
    if docs:
        parts.append(f"docs_paths ({len(docs)})")

    evidence.append(EvidenceDict(
        source="mapping",
        snippet=f"Mapping for `{component_name}`: {', '.join(parts)}",
        confidence="high",
    ))
    return evidence


def hydrate_component(
    component_name: str,
    graph: DiagramGraphDict,
    repo_path: str = "",
    docs_path: str = "",
    mappings_dir: str = "",
) -> ComponentContextDict:
    """
    Build a full context for one component from all available sources.
    """
    warnings: list[str] = []

    # Resolve canonical name
    cmap = load_component_map(mappings_dir or None)
    aliases = load_aliases(mappings_dir or None)
    canonical = resolve_component_name(component_name, aliases, cmap)
    entry = cmap["components"].get(canonical)

    if canonical != component_name:
        warnings.append(f"Resolved alias `{component_name}` → `{canonical}`.")

    # Diagram evidence
    diag_ev = _diagram_evidence(graph, canonical)
    if not diag_ev:
        warnings.append(f"No diagram nodes/edges matched `{canonical}`.")

    # Mapping evidence
    map_ev = _mapping_evidence(canonical, entry)

    # Repo evidence
    repo_ev: list[EvidenceDict] = []
    effective_repo = ""
    if repo_path:
        effective_repo = repo_path
    elif entry and entry.get("repo_path"):
        effective_repo = entry["repo_path"]

    if effective_repo:
        rp = Path(effective_repo).expanduser().resolve()
        if rp.is_dir():
            repo_ev = build_repo_evidence(rp, canonical)
        else:
            warnings.append(f"Repo path not found: {effective_repo}")

    # Docs evidence
    docs_ev: list[EvidenceDict] = []
    doc_paths_to_check: list[str] = []
    if docs_path:
        doc_paths_to_check.append(docs_path)
    if entry and entry.get("docs_paths"):
        doc_paths_to_check.extend(entry["docs_paths"])

    if doc_paths_to_check:
        docs_ev = build_docs_evidence(doc_paths_to_check, canonical)

    # Inferred evidence
    inferred: list[EvidenceDict] = []
    if not repo_ev and not docs_ev and diag_ev:
        inferred.append(EvidenceDict(
            source="inference",
            snippet=(
                f"`{canonical}` appears in the diagram but has no repo or doc context. "
                "Consider adding a mapping entry."
            ),
            confidence="low",
        ))

    return ComponentContextDict(
        component_name=canonical,
        diagram_evidence=diag_ev,
        repo_evidence=repo_ev,
        docs_evidence=docs_ev,
        mapping_evidence=map_ev,
        inferred=inferred,
        warnings=warnings,
    )


def hydrate_all_components(
    graph: DiagramGraphDict,
    mappings_dir: str = "",
) -> dict[str, Any]:
    """
    Hydrate context for every component in the diagram that has a non-trivial kind.
    """
    relevant_kinds = {"service", "database", "queue", "gateway", "storage", "external_system"}
    components: list[str] = []
    seen: set[str] = set()

    for n in graph["nodes"]:
        label = n["label"]
        if n["kind"] in relevant_kinds and label and label not in seen:
            components.append(label)
            seen.add(label)

    results: dict[str, ComponentContextDict] = {}
    warnings: list[str] = []

    for comp in components:
        ctx = hydrate_component(comp, graph, mappings_dir=mappings_dir)
        results[ctx["component_name"]] = ctx
        warnings.extend(ctx["warnings"])

    return {
        "diagram_id": graph.get("diagram_id", ""),
        "components_hydrated": len(results),
        "components": results,
        "warnings": warnings,
    }
