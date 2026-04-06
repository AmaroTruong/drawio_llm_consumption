"""
Contextual architecture review: combines diagram-only findings, cross-source
consistency findings, and per-source evidence into a single report.
"""

from __future__ import annotations

from typing import Any

from drawio_arch_mcp.consistency import validate_consistency
from drawio_arch_mcp.models import DiagramGraphDict, ReviewFindingDict
from drawio_arch_mcp.review import review_architecture as diagram_review


def review_architecture_contextual(
    graph: DiagramGraphDict,
    mappings_dir: str = "",
) -> dict[str, Any]:
    """
    Run a multi-source architecture review.

    Returns separate sections for:
      - diagram_findings      : from structural review (v0.2)
      - consistency_findings  : cross-source mismatches
      - summary               : high-level counts and narrative
    """
    # Diagram-only structural findings
    diag_findings: list[ReviewFindingDict] = diagram_review(graph)

    # Cross-source consistency
    consistency = validate_consistency(graph, mappings_dir=mappings_dir)
    cons_findings = consistency.get("findings", [])

    # Build summary
    warning_count = sum(
        1 for f in diag_findings if f["severity"] == "warning"
    ) + sum(
        1 for f in cons_findings if f["severity"] == "warning"
    )
    info_count = sum(
        1 for f in diag_findings if f["severity"] == "info"
    ) + sum(
        1 for f in cons_findings if f["severity"] == "info"
    )

    summary_lines: list[str] = []
    summary_lines.append(
        f"Reviewed diagram `{graph.get('diagram_id', '?')}`: "
        f"{len(graph['nodes'])} nodes, {len(graph['edges'])} edges."
    )
    summary_lines.append(
        f"Diagram findings: {len(diag_findings)}. "
        f"Consistency findings: {len(cons_findings)}."
    )
    if warning_count:
        summary_lines.append(f"{warning_count} warning(s) require attention.")
    if info_count:
        summary_lines.append(f"{info_count} informational finding(s).")

    return {
        "diagram_id": graph.get("diagram_id", ""),
        "diagram_findings": diag_findings,
        "consistency_findings": cons_findings,
        "summary": "\n".join(summary_lines),
        "counts": {
            "diagram_warnings": sum(1 for f in diag_findings if f["severity"] == "warning"),
            "diagram_info": sum(1 for f in diag_findings if f["severity"] == "info"),
            "consistency_warnings": sum(1 for f in cons_findings if f["severity"] == "warning"),
            "consistency_info": sum(1 for f in cons_findings if f["severity"] == "info"),
        },
    }
