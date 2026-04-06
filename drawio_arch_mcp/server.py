"""
FastMCP server v0.3.0 — Context Fusion.

Tools:
  v0.1 (carried forward):
    parse_drawio_file, summarize_architecture, analyze_tradeoff

  v0.2 (carried forward):
    export_architecture_graph, apply_graph_patch, convert_graph_to_drawio,
    review_architecture

  v0.3 (new — real implementations):
    search_repo_context, read_repo_file, get_repo_context, map_component_to_repo,
    search_confluence_context, read_confluence_page, get_confluence_context,
    get_component_context, hydrate_architecture_context,
    validate_architecture_consistency, review_architecture_contextual

Resources:
    archgraph:///{drawio_filename}
    component:///{component_name}/summary
    mapping:///component_map
    mapping:///aliases

Configure with env vars:
    DRAWIO_MCP_ALLOWED_ROOTS  — comma-separated allowed directories
    DRAWIO_MCP_MAPPINGS_DIR   — directory containing component_map.json / aliases.json
    DRAWIO_MCP_CACHE_DIR      — optional cache directory
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from drawio_arch_mcp.analysis import analyze_tradeoff as _analyze_tradeoff
from drawio_arch_mcp.analysis import summarize_architecture as _summarize
from drawio_arch_mcp.cache import cache_get, cache_put
from drawio_arch_mcp.confluence_context import (
    read_doc_file,
    search_docs,
    build_docs_evidence,
    scan_docs,
)
from drawio_arch_mcp.consistency import validate_consistency
from drawio_arch_mcp.contextual_review import (
    review_architecture_contextual as _contextual_review,
)
from drawio_arch_mcp.drawio_writer import write_drawio_file
from drawio_arch_mcp.graph_export import export_graph
from drawio_arch_mcp.graph_mutation import apply_graph_patch as _apply_patch
from drawio_arch_mcp.hydration import hydrate_all_components, hydrate_component
from drawio_arch_mcp.mappings import (
    get_component_entry,
    load_aliases,
    load_component_map,
    resolve_component_name,
)
from drawio_arch_mcp.parser import parse_drawio_file as _load_diagram
from drawio_arch_mcp.path_validation import (
    PathValidationError,
    load_allowed_roots_from_env,
    resolve_drawio_path,
    resolve_local_dir,
    resolve_local_file,
    resolve_output_path,
)
from drawio_arch_mcp.repo_context import (
    build_repo_evidence,
    read_repo_file as _read_repo_file,
    scan_repo,
    search_repo,
)
from drawio_arch_mcp.resources import (
    aliases_resource,
    component_summary_resource,
    graph_resource,
    mapping_resource,
)
from drawio_arch_mcp.review import format_review, review_architecture as _review

mcp = FastMCP(
    name="drawio-architecture",
    instructions=(
        "Tools to parse local .drawio files into a normalized graph, export, "
        "mutate, convert back to .drawio, review architecture, fuse context "
        "from repos, Confluence exports, and mapping files. "
        "Always pass absolute paths under an allowed root directory."
    ),
)


def _roots() -> tuple[str, ...]:
    return load_allowed_roots_from_env()


def _mappings_dir() -> str:
    return os.environ.get("DRAWIO_MCP_MAPPINGS_DIR", "")


def _load(drawio_path: str) -> dict[str, Any] | str:
    """Validate path + parse; return graph dict or error string."""
    try:
        p = resolve_drawio_path(drawio_path, _roots())
    except PathValidationError as e:
        return str(e)

    cached = cache_get(str(p), "graph")
    if cached:
        return cached

    graph = dict(_load_diagram(p))
    cache_put(str(p), graph, "graph")
    return graph


def _resolve_dir(path: str, label: str) -> Path | str:
    try:
        return resolve_local_dir(path, _roots(), label)
    except PathValidationError as e:
        return str(e)


def _resolve_file(path: str, label: str, suffixes: tuple[str, ...] | None = None) -> Path | str:
    try:
        return resolve_local_file(path, _roots(), label, suffixes)
    except PathValidationError as e:
        return str(e)


# ─────────────────────── v0.1.0 tools (carried forward) ───────────────────────


@mcp.tool
def parse_drawio_file(drawio_path: str) -> dict[str, Any]:
    """
    Read a local `.drawio` file, parse mxGraph XML, and return normalized graph JSON:
    diagram_id, pages, nodes, edges, groups, warnings.
    """
    result = _load(drawio_path)
    if isinstance(result, str):
        return {"error": result, "diagram_id": "", "pages": [], "nodes": [], "edges": [], "groups": [], "warnings": []}
    return result


@mcp.tool
def summarize_architecture(drawio_path: str) -> str:
    """
    Build a concise architecture summary: inferred services, databases, externals,
    containers, and notable dependencies from the diagram structure.
    """
    result = _load(drawio_path)
    if isinstance(result, str):
        return f"Path validation failed: {result}"
    return _summarize(result)


@mcp.tool
def analyze_tradeoff(drawio_path: str, proposal: str) -> str:
    """
    Grounded tradeoff / risk discussion from the diagram (e.g. splitting a service,
    shared database risk, coupling). Uses topology and labels only.
    """
    result = _load(drawio_path)
    if isinstance(result, str):
        return f"Path validation failed: {result}"
    return _analyze_tradeoff(result, proposal)


# ────────────────────────── v0.2.0 tools (carried forward) ────────────────────


@mcp.tool
def export_architecture_graph(drawio_path: str) -> dict[str, Any]:
    """
    Parse the `.drawio` file and return the normalized graph as an explicit,
    versioned JSON artifact.
    """
    result = _load(drawio_path)
    if isinstance(result, str):
        return {"error": result}
    return export_graph(result)


@mcp.tool
def apply_graph_patch(graph: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """
    Apply a structured patch to a normalized graph.

    Patch keys: add_nodes, remove_nodes, update_nodes,
    add_edges, remove_edges, update_edges.
    Returns {"graph": <mutated>, "mutation_warnings": [...]}.
    """
    return _apply_patch(graph, patch)


@mcp.tool
def convert_graph_to_drawio(graph: dict[str, Any], output_path: str) -> dict[str, str]:
    """
    Convert a normalized graph JSON back into a valid `.drawio` file.
    The file is written to *output_path* (must be under an allowed root).
    """
    try:
        p = resolve_output_path(output_path, _roots())
    except PathValidationError as e:
        return {"error": str(e)}
    written = write_drawio_file(graph, p)
    return {"status": "ok", "output_path": str(written)}


@mcp.tool
def review_architecture(drawio_path: str) -> str:
    """
    Diagram-only structural review: shared databases, direct DB access,
    gateway bypass, unlabeled edges, tight coupling.
    Returns Markdown-formatted findings with severity.
    """
    result = _load(drawio_path)
    if isinstance(result, str):
        return f"Path validation failed: {result}"
    findings = _review(result)
    return format_review(findings)


# ─────────────────────── v0.3.0 repo context tools ───────────────────────────


@mcp.tool
def search_repo_context(query: str, repo_path: str) -> dict[str, Any]:
    """
    Search a local repository for architecture-relevant content matching *query*.
    Scans READMEs, OpenAPI specs, deployment manifests, ADRs, config files.
    """
    rp = _resolve_dir(repo_path, "Repo")
    if isinstance(rp, str):
        return {"error": rp}
    hits = search_repo(rp, query)
    return {"query": query, "repo_path": str(rp), "results": hits, "count": len(hits)}


@mcp.tool
def read_repo_file(repo_path: str, relative_path: str) -> dict[str, Any]:
    """
    Read a single file from a local repository.
    *relative_path* is relative to *repo_path*.
    """
    rp = _resolve_dir(repo_path, "Repo")
    if isinstance(rp, str):
        return {"error": rp}
    return _read_repo_file(rp, relative_path)


@mcp.tool
def get_repo_context(component_name: str, repo_path: str = "") -> dict[str, Any]:
    """
    Get architecture-relevant repo context for a component.
    If *repo_path* is empty, looks up the component in the mapping file.
    """
    effective = repo_path
    if not effective:
        _, entry = get_component_entry(component_name, _mappings_dir() or None)
        if entry and entry.get("repo_path"):
            effective = entry["repo_path"]
    if not effective:
        return {"error": f"No repo_path for `{component_name}`. Provide repo_path or add a mapping."}
    rp = _resolve_dir(effective, "Repo")
    if isinstance(rp, str):
        return {"error": rp}
    evidence = build_repo_evidence(rp, component_name)
    files = scan_repo(rp)
    return {
        "component_name": component_name,
        "repo_path": str(rp),
        "arch_files": files,
        "evidence": evidence,
    }


@mcp.tool
def map_component_to_repo(component_name: str) -> dict[str, Any]:
    """
    Look up the mapping entry for a diagram component: repo path, docs,
    owner, tags, aliases.
    """
    canonical, entry = get_component_entry(component_name, _mappings_dir() or None)
    result: dict[str, Any] = {"canonical_name": canonical}
    if entry:
        result["mapping"] = dict(entry)
    else:
        result["mapping"] = None
        result["warning"] = f"No mapping found for `{canonical}`."
    return result


# ─────────────────────── v0.3.0 confluence-export tools ──────────────────────


@mcp.tool
def search_confluence_context(query: str, docs_path: str = "") -> dict[str, Any]:
    """
    Search local Confluence-export files (HTML, Markdown, XML, text) for *query*.
    """
    if not docs_path:
        return {"error": "docs_path is required for local Confluence-export search."}
    dp = _resolve_dir(docs_path, "Docs")
    if isinstance(dp, str):
        return {"error": dp}
    hits = search_docs(dp, query)
    return {"query": query, "docs_path": str(dp), "results": hits, "count": len(hits)}


@mcp.tool
def read_confluence_page(local_path: str) -> dict[str, Any]:
    """
    Read a local exported Confluence page (HTML, Markdown, XML, or text).
    Returns plain-text content (HTML tags stripped).
    """
    fp = _resolve_file(local_path, "Doc file", (".html", ".htm", ".md", ".xml", ".txt", ".rst"))
    if isinstance(fp, str):
        return {"error": fp}
    return read_doc_file(fp)


@mcp.tool
def get_confluence_context(component_name: str, docs_path: str = "") -> dict[str, Any]:
    """
    Get Confluence-export context for a component.
    Uses mapping docs_paths and/or a provided docs directory.
    """
    _, entry = get_component_entry(component_name, _mappings_dir() or None)
    doc_paths: list[str] = []
    if docs_path:
        doc_paths.append(docs_path)
    if entry and entry.get("docs_paths"):
        doc_paths.extend(entry["docs_paths"])
    if not doc_paths:
        return {"error": f"No docs paths for `{component_name}`. Provide docs_path or add mapping."}
    evidence = build_docs_evidence(doc_paths, component_name)
    return {
        "component_name": component_name,
        "docs_paths": doc_paths,
        "evidence": evidence,
    }


# ─────────────────── v0.3.0 context hydration tools ──────────────────────────


@mcp.tool
def get_component_context(
    component_name: str,
    drawio_path: str,
    repo_path: str = "",
    docs_path: str = "",
) -> dict[str, Any]:
    """
    Unified context: merge diagram + repo + Confluence-export + mapping evidence
    for a single component. Returns evidence separated by source with confidence.
    """
    result = _load(drawio_path)
    if isinstance(result, str):
        return {"error": result}
    ctx = hydrate_component(
        component_name, result,
        repo_path=repo_path,
        docs_path=docs_path,
        mappings_dir=_mappings_dir(),
    )
    return dict(ctx)


@mcp.tool
def hydrate_architecture_context(drawio_path: str) -> dict[str, Any]:
    """
    Enrich all components in the diagram with repo and doc context from mappings.
    Returns per-component evidence separated by source.
    """
    result = _load(drawio_path)
    if isinstance(result, str):
        return {"error": result}
    return hydrate_all_components(result, mappings_dir=_mappings_dir())


# ──────────────── v0.3.0 consistency & contextual review ─────────────────────


@mcp.tool
def validate_architecture_consistency(drawio_path: str) -> dict[str, Any]:
    """
    Cross-source consistency validation: detect components in the diagram with
    no mapping, mapped repos that don't exist, missing docs, orphan aliases, etc.
    """
    result = _load(drawio_path)
    if isinstance(result, str):
        return {"error": result}
    return validate_consistency(result, mappings_dir=_mappings_dir())


@mcp.tool
def review_architecture_contextual(drawio_path: str) -> dict[str, Any]:
    """
    Multi-source architecture review: diagram-derived findings, cross-source
    consistency checks, and counts. More comprehensive than review_architecture.
    """
    result = _load(drawio_path)
    if isinstance(result, str):
        return {"error": result}
    return _contextual_review(result, mappings_dir=_mappings_dir())


# ──────────────────────── MCP Resources ──────────────────────────────────────


@mcp.resource("archgraph:///{drawio_filename}")
def archgraph_resource(drawio_filename: str) -> str:
    """Parsed graph JSON for a .drawio file (looked up under allowed roots)."""
    for root in _roots():
        candidate = Path(root) / drawio_filename
        if candidate.is_file():
            result = _load(str(candidate))
            if not isinstance(result, str):
                return graph_resource(result)
    return json.dumps({"error": f"Diagram not found: {drawio_filename}"})


@mcp.resource("component:///{component_name}/summary")
def component_summary(component_name: str) -> str:
    """Plain-text summary for a component (from mapping + any loaded graph)."""
    return component_summary_resource(component_name, {}, _mappings_dir())


@mcp.resource("mapping:///component_map")
def component_map_resource() -> str:
    """Current component_map.json contents."""
    return mapping_resource(_mappings_dir())


@mcp.resource("mapping:///aliases")
def aliases_map_resource() -> str:
    """Current aliases.json contents."""
    return aliases_resource(_mappings_dir())


# ──────────────────────────── CLI entry ──────────────────────────────────────


def main() -> None:
    """
    CLI entry.

    * Default: **stdio** (VS Code / clients spawn this process).
    * ``--http``: streamable HTTP on localhost.
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="drawio-arch-mcp")
    parser.add_argument("--http", action="store_true")
    parser.add_argument("--host", default=os.environ.get("DRAWIO_MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DRAWIO_MCP_PORT", "8000")))
    parser.add_argument("--path", default=os.environ.get("DRAWIO_MCP_PATH", "/mcp"))
    args, _unknown = parser.parse_known_args()

    if os.environ.get("DRAWIO_MCP_LOG_ROOTS"):
        print(f"drawio-arch-mcp allowed roots: {_roots()}", file=sys.stderr)

    transport_env = os.environ.get("DRAWIO_MCP_TRANSPORT", "").strip().lower()
    use_http = args.http or transport_env in ("http", "streamable-http", "streamable_http")

    if use_http:
        path = args.path if args.path.startswith("/") else f"/{args.path}"
        url = f"http://{args.host}:{args.port}{path}"
        print(f"drawio-arch-mcp HTTP MCP → {url}", file=sys.stderr)
        mcp.run(transport="http", host=args.host, port=args.port, path=path)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
