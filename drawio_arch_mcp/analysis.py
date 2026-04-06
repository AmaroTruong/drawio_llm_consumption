"""
Heuristic summarization and tradeoff reasoning from a parsed diagram graph.

Outputs are **grounded** in structure (nodes, edges, groups, degrees); they are
not substitutes for domain validation.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable

from drawio_arch_mcp.models import DiagramGraphDict, EdgeDict, NodeDict


def _nodes_by_id(nodes: Iterable[NodeDict]) -> dict[str, NodeDict]:
    return {n["id"]: n for n in nodes}


def _kind_counts(nodes: Iterable[NodeDict]) -> Counter[str]:
    return Counter(n["kind"] for n in nodes)


def _degree_maps(edges: list[EdgeDict]) -> tuple[dict[str, int], dict[str, int], dict[str, set[str]]]:
    out_d: dict[str, int] = defaultdict(int)
    in_d: dict[str, int] = defaultdict(int)
    neighbors: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        s, t = e["source"], e["target"]
        out_d[s] += 1
        in_d[t] += 1
        neighbors[s].add(t)
        neighbors[t].add(s)
    return out_d, in_d, neighbors


def summarize_architecture(graph: DiagramGraphDict) -> str:
    """Produce a concise text summary from parsed diagram data."""
    if not graph["nodes"] and not graph["warnings"]:
        return "Diagram has no extractable nodes (empty or unsupported format)."

    lines: list[str] = []
    lines.append(f"Diagram `{graph['diagram_id']}` — {len(graph['pages'])} page(s), ")
    lines.append(
        f"{len(graph['nodes'])} node(s), {len(graph['edges'])} edge(s), {len(graph['groups'])} group(s)."
    )

    kc = _kind_counts(graph["nodes"])
    if kc:
        top = ", ".join(f"{k}:{kc[k]}" for k in sorted(kc.keys()))
        lines.append(f"\nInferred kinds (counts): {top}.")

    by_kind: dict[str, list[str]] = defaultdict(list)
    for n in graph["nodes"]:
        if n["label"]:
            by_kind[n["kind"]].append(n["label"])

    def bullet(title: str, kinds: tuple[str, ...]) -> None:
        names: list[str] = []
        for k in kinds:
            names.extend(by_kind.get(k, []))
        if names:
            preview = ", ".join(names[:12])
            if len(names) > 12:
                preview += ", …"
            lines.append(f"\n**{title}**: {preview}")

    bullet("Likely services / app components", ("service", "unknown"))
    bullet("Databases", ("database",))
    bullet("Queues / async", ("queue",))
    bullet("External systems", ("external_system",))
    bullet("Gateways", ("gateway",))
    bullet("Storage", ("storage",))
    bullet("Containers / swimlanes", ("container", "swimlane"))

    out_d, _, _ = _degree_maps(graph["edges"])
    if graph["edges"]:
        hubs = sorted(out_d.items(), key=lambda x: -x[1])[:5]
        hub_txt = ", ".join(f"{nid} (out={deg})" for nid, deg in hubs if deg > 0)
        if hub_txt:
            lines.append("\n**High outbound connectivity (possible orchestrators)**: " + hub_txt + ".")

    if graph["warnings"]:
        lines.append(f"\n**Parse warnings** ({len(graph['warnings'])}): first few — ")
        lines.append("; ".join(graph["warnings"][:5]) + ("…" if len(graph["warnings"]) > 5 else ""))

    return "".join(lines)


def analyze_tradeoff(graph: DiagramGraphDict, proposal: str) -> str:
    """
    Answer a tradeoff-style question using graph structure and simple keyword hooks.

    The response cites concrete node labels and edge patterns where possible.
    """
    prop = proposal.strip()
    if not prop:
        return "Please provide a non-empty `proposal` question."

    out_d, in_d, neighbors = _degree_maps(graph["edges"])
    by_id = _nodes_by_id(graph["nodes"])
    low = prop.lower()

    chunks: list[str] = []

    def label(nid: str) -> str:
        n = by_id.get(nid)
        return n["label"] if n and n["label"] else nid

    # Shared database risk
    if "database" in low or "shared" in low and "db" in low:
        dbs = [n for n in graph["nodes"] if n["kind"] == "database"]
        consumers: dict[str, list[str]] = defaultdict(list)
        for e in graph["edges"]:
            tgt = by_id.get(e["target"])
            src = by_id.get(e["source"])
            if tgt and tgt["kind"] == "database":
                consumers[tgt["id"]].append(e["source"])
        chunks.append("**Shared / central database (from diagram edges)**:\n")
        if not dbs:
            chunks.append("- No nodes were classified as `database`; risk analysis is limited.\n")
        for db in dbs:
            inc = in_d.get(db["id"], 0)
            srcs = consumers.get(db["id"], [])
            uniq = sorted({label(s) for s in srcs})
            chunks.append(
                f"- `{db['label'] or db['id']}`: {inc} inbound edge(s) from "
                f"{len(uniq)} source shape(s)"
                + (f" ({', '.join(uniq[:6])}" + ("…" if len(uniq) > 6 else "") + ")" if uniq else "")
                + ".\n"
            )
        chunks.append(
            "\n*Grounded takeaway*: multiple inbound dependencies on one DB increase "
            "blast radius, schema coupling, and migration coordination cost — "
            "exact severity depends on workloads not shown in the diagram.\n"
        )

    # Split service / decomposition
    if "split" in low or "service" in low and ("micro" in low or "decompos" in low):
        hubs = sorted(out_d.items(), key=lambda x: (-x[1], x[0]))
        chunks.append("**Splitting / decomposition (structural hints)**:\n")
        for nid, deg in hubs[:8]:
            if deg < 2:
                break
            n = by_id.get(nid)
            neigh = sorted(neighbors.get(nid, []), key=lambda x: -out_d.get(x, 0))
            neigh_labs = [label(x) for x in neigh[:6]]
            chunks.append(
                f"- `{label(nid)}` fans out to {deg} target(s); neighbors include "
                f"{', '.join(neigh_labs) if neigh_labs else '(none listed)'}.\n"
            )
        chunks.append(
            "\n*Grounded takeaway*: high out-degree nodes often become boundaries when splitting; "
            "new seams should cut edges that are few and stable, not dense cross-talk.\n"
        )

    # Tight coupling
    if "coupl" in low or "tight" in low:
        undirected_pairs: dict[frozenset[str], int] = defaultdict(int)
        for e in graph["edges"]:
            pair = frozenset((e["source"], e["target"]))
            undirected_pairs[pair] += 1
        multi = [(pair, c) for pair, c in undirected_pairs.items() if c > 1]
        multi.sort(key=lambda x: -x[1])
        chunks.append("**Coupling (edge multiplicity)**:\n")
        if not multi:
            chunks.append("- No parallel edges between the same pair of nodes were found.\n")
        for pair, c in multi[:10]:
            a, b = tuple(pair)
            chunks.append(f"- `{label(a)}` ↔ `{label(b)}`: {c} parallel edge(s).\n")
        deg_ge_3 = [(nid, len(neighbors[nid])) for nid in neighbors if len(neighbors[nid]) >= 3]
        deg_ge_3.sort(key=lambda x: -x[1])
        if deg_ge_3:
            chunks.append("\n**Highly connected nodes (many distinct neighbors)**:\n")
            for nid, d in deg_ge_3[:8]:
                chunks.append(f"- `{label(nid)}`: {d} neighbor(s).\n")
        chunks.append(
            "\n*Grounded takeaway*: many distinct neighbors or parallel edges suggest "
            "higher coordination cost when evolving either side.\n"
        )

    # Generic fallback
    if not chunks:
        kc = _kind_counts(graph["nodes"])
        chunks.append(
            "**General structural read (no specific keyword match in your question)**:\n"
        )
        chunks.append(f"- Shape kinds present: {dict(kc)}.\n")
        chunks.append(f"- Total edges: {len(graph['edges'])}.\n")
        chunks.append(
            "\nTry mentioning topics like `shared database`, `split service`, or `tight coupling` "
            "for more targeted, diagram-grounded commentary.\n"
        )

    chunks.append("\n---\n*Reminder*: This MVP reasons from diagram topology and labels only.\n")
    return "".join(chunks)
