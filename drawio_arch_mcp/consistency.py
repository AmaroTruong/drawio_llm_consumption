"""
Cross-source consistency validation: detect mismatches between diagram,
repo, docs, and mapping metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from drawio_arch_mcp.mappings import load_aliases, load_component_map
from drawio_arch_mcp.models import ConsistencyFindingDict, DiagramGraphDict


def validate_consistency(
    graph: DiagramGraphDict,
    mappings_dir: str = "",
) -> dict[str, Any]:
    """
    Check for cross-source inconsistencies.

    Categories:
      - unmapped_component   : in diagram but no mapping entry
      - mapped_not_in_diagram: in mapping but no matching diagram node
      - missing_repo         : mapping has repo_path but directory doesn't exist
      - missing_docs         : mapping has docs_paths but file(s) don't exist
      - missing_owner        : important component with no owner in mapping
      - orphan_alias         : alias target not in component_map
    """
    findings: list[ConsistencyFindingDict] = []
    cmap = load_component_map(mappings_dir or None)
    aliases = load_aliases(mappings_dir or None)

    relevant_kinds = {"service", "database", "queue", "gateway", "storage", "external_system"}
    diagram_labels: set[str] = set()
    for n in graph["nodes"]:
        if n["kind"] in relevant_kinds and n["label"]:
            diagram_labels.add(n["label"])

    mapped_names = set(cmap["components"].keys())

    # Components in diagram but not mapped
    for label in sorted(diagram_labels):
        if label not in mapped_names:
            lower_map = {k.lower(): k for k in mapped_names}
            if label.lower() not in lower_map:
                findings.append(ConsistencyFindingDict(
                    severity="warning",
                    category="unmapped_component",
                    message=f"`{label}` appears in the diagram but has no entry in component_map.json.",
                    source="diagram",
                    related_components=[label],
                ))

    # Components mapped but not in diagram
    for name in sorted(mapped_names):
        lower_diag = {l.lower() for l in diagram_labels}
        if name.lower() not in lower_diag:
            findings.append(ConsistencyFindingDict(
                severity="info",
                category="mapped_not_in_diagram",
                message=f"`{name}` is in component_map.json but not found in the diagram.",
                source="mapping",
                related_components=[name],
            ))

    # Missing repo paths
    for name, entry in cmap["components"].items():
        rp = entry.get("repo_path")
        if rp:
            if not Path(rp).expanduser().resolve().is_dir():
                findings.append(ConsistencyFindingDict(
                    severity="warning",
                    category="missing_repo",
                    message=f"`{name}` mapping references repo `{rp}` but directory not found.",
                    source="mapping",
                    related_components=[name],
                ))

    # Missing doc paths
    for name, entry in cmap["components"].items():
        for dp in entry.get("docs_paths", []):
            if not Path(dp).expanduser().resolve().exists():
                findings.append(ConsistencyFindingDict(
                    severity="info",
                    category="missing_docs",
                    message=f"`{name}` mapping references doc `{dp}` but path not found.",
                    source="mapping",
                    related_components=[name],
                ))

    # Missing owner for important components
    for label in sorted(diagram_labels):
        if label in mapped_names:
            entry = cmap["components"][label]
            if not entry.get("owner"):
                findings.append(ConsistencyFindingDict(
                    severity="info",
                    category="missing_owner",
                    message=f"`{label}` has a mapping entry but no owner specified.",
                    source="mapping",
                    related_components=[label],
                ))

    # Orphan aliases
    for alias, target in aliases["aliases"].items():
        if target not in mapped_names:
            findings.append(ConsistencyFindingDict(
                severity="info",
                category="orphan_alias",
                message=f"Alias `{alias}` → `{target}` but `{target}` is not in component_map.json.",
                source="mapping",
                related_components=[target],
            ))

    severity_order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: severity_order.get(f["severity"], 9))

    return {
        "diagram_id": graph.get("diagram_id", ""),
        "finding_count": len(findings),
        "findings": findings,
    }
