"""
FastMCP server v0.2.0 — Graph Mutation & Export.

Tools:
  v0.1 (carried forward):
    parse_drawio_file, summarize_architecture, analyze_tradeoff

  v0.2 new:
    export_architecture_graph, apply_graph_patch, convert_graph_to_drawio,
    review_architecture

  v0.2 stubs (future):
    search_confluence_context, read_confluence_page, get_confluence_context,
    search_repo_context, get_repo_context, map_component_to_repo,
    get_component_context, hydrate_architecture_context

Configure allowed directories with ``DRAWIO_MCP_ALLOWED_ROOTS`` (comma-separated).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from drawio_arch_mcp.analysis import analyze_tradeoff as _analyze_tradeoff
from drawio_arch_mcp.analysis import summarize_architecture as _summarize
from drawio_arch_mcp.drawio_writer import graph_to_drawio_xml, write_drawio_file
from drawio_arch_mcp.graph_export import export_graph
from drawio_arch_mcp.graph_mutation import apply_graph_patch as _apply_patch
from drawio_arch_mcp.parser import parse_drawio_file as _load_diagram
from drawio_arch_mcp.path_validation import (
    PathValidationError,
    load_allowed_roots_from_env,
    resolve_drawio_path,
    resolve_output_path,
)
from drawio_arch_mcp.review import format_review, review_architecture as _review
from drawio_arch_mcp import stubs

mcp = FastMCP(
    name="drawio-architecture",
    instructions=(
        "Tools to parse local .drawio files into a normalized graph, export, "
        "mutate, convert back to .drawio, and review architecture. "
        "Always pass absolute paths under an allowed root directory."
    ),
)


def _roots() -> tuple[str, ...]:
    return load_allowed_roots_from_env()


def _load(drawio_path: str) -> dict[str, Any] | str:
    """Validate path + parse; return graph dict or error string."""
    try:
        p = resolve_drawio_path(drawio_path, _roots())
    except PathValidationError as e:
        return str(e)
    return dict(_load_diagram(p))


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


# ────────────────────────── v0.2.0 tools (new) ────────────────────────────────

@mcp.tool
def export_architecture_graph(drawio_path: str) -> dict[str, Any]:
    """
    Parse the `.drawio` file and return the normalized graph as an explicit,
    versioned JSON artifact. Use this when you need the raw graph structure.
    """
    result = _load(drawio_path)
    if isinstance(result, str):
        return {"error": result}
    return export_graph(result)


@mcp.tool
def apply_graph_patch(graph: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """
    Apply a structured patch to a normalized graph.

    Patch keys:
      add_nodes, remove_nodes, update_nodes,
      add_edges, remove_edges, update_edges

    Returns {"graph": <mutated>, "mutation_warnings": [...]}.
    """
    return _apply_patch(graph, patch)


@mcp.tool
def convert_graph_to_drawio(graph: dict[str, Any], output_path: str) -> dict[str, str]:
    """
    Convert a normalized graph JSON back into a valid `.drawio` file.

    The file is written to *output_path* (must be under an allowed root).
    Returns the resolved output path or an error.
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
    Run structural architecture review: shared databases, direct DB access,
    gateway bypass, unlabeled edges, tight coupling, and more.
    Returns a Markdown-formatted list of findings with severity.
    """
    result = _load(drawio_path)
    if isinstance(result, str):
        return f"Path validation failed: {result}"
    findings = _review(result)
    return format_review(findings)


# ──────────────────── v0.2.0 stubs (future integration) ──────────────────────

@mcp.tool
def search_confluence_context(query: str) -> dict[str, str]:
    """Search Confluence for pages matching a query. (Stubbed — not yet implemented.)"""
    return stubs.search_confluence_context(query)


@mcp.tool
def read_confluence_page(page_id: str) -> dict[str, str]:
    """Read a Confluence page by page_id. (Stubbed — not yet implemented.)"""
    return stubs.read_confluence_page(page_id)


@mcp.tool
def get_confluence_context(component_name: str) -> dict[str, str]:
    """Get Confluence context for a named architecture component. (Stubbed — not yet implemented.)"""
    return stubs.get_confluence_context(component_name)


@mcp.tool
def search_repo_context(query: str, repo_path: str = "") -> dict[str, str]:
    """Search a local repository for code matching a query. (Stubbed — not yet implemented.)"""
    return stubs.search_repo_context(query, repo_path)


@mcp.tool
def get_repo_context(component_name: str, repo_path: str = "") -> dict[str, str]:
    """Get repo-level context for a named component. (Stubbed — not yet implemented.)"""
    return stubs.get_repo_context(component_name, repo_path)


@mcp.tool
def map_component_to_repo(component_name: str) -> dict[str, str]:
    """Map a diagram component label to a repository directory or service. (Stubbed — not yet implemented.)"""
    return stubs.map_component_to_repo(component_name)


@mcp.tool
def get_component_context(
    component_name: str,
    drawio_path: str,
    repo_path: str = "",
    confluence_ref: str = "",
) -> dict[str, str]:
    """
    Unified context: merge diagram + repo + Confluence for one component.
    (Stubbed — not yet implemented.)
    """
    return stubs.get_component_context(component_name, drawio_path, repo_path, confluence_ref)


@mcp.tool
def hydrate_architecture_context(drawio_path: str) -> dict[str, str]:
    """
    Enrich the entire architecture graph with repo and Confluence context.
    (Stubbed — not yet implemented.)
    """
    return stubs.hydrate_architecture_context(drawio_path)


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
