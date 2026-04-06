"""
FastMCP server: tools for parsing Draw.io diagrams and discussing architecture.

Configure allowed directories with env var ``DRAWIO_MCP_ALLOWED_ROOTS`` (comma-separated).
Defaults to the process current working directory if unset.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from drawio_arch_mcp.analysis import analyze_tradeoff as analyze_tradeoff_from_graph
from drawio_arch_mcp.analysis import summarize_architecture as summarize_architecture_from_graph
from drawio_arch_mcp.path_validation import PathValidationError, load_allowed_roots_from_env, resolve_drawio_path
from drawio_arch_mcp.parser import parse_drawio_file as load_diagram_from_path

mcp = FastMCP(
    name="drawio-architecture",
    instructions=(
        "Tools to parse local .drawio files into a normalized graph and summarize or analyze "
        "architecture tradeoffs. Always pass an absolute or rooted path under an allowed directory."
    ),
)


def _roots() -> tuple[str, ...]:
    return load_allowed_roots_from_env()


def _parse_resolved(path: Path) -> dict[str, Any]:
    graph = load_diagram_from_path(path)
    return dict(graph)


@mcp.tool
def parse_drawio_file(drawio_path: str) -> dict[str, Any]:
    """
    Read a local `.drawio` file, parse mxGraph XML, and return normalized graph JSON:
    diagram_id, pages, nodes, edges, groups, warnings.

    Path must lie under an allowed root (see DRAWIO_MCP_ALLOWED_ROOTS).
    """
    try:
        p = resolve_drawio_path(drawio_path, _roots())
    except PathValidationError as e:
        return {"error": str(e), "diagram_id": "", "pages": [], "nodes": [], "edges": [], "groups": [], "warnings": []}
    return _parse_resolved(p)


@mcp.tool
def summarize_architecture(drawio_path: str) -> str:
    """
    Build a concise architecture summary: inferred services, databases, externals,
    containers, and notable dependencies from the diagram structure.
    """
    try:
        p = resolve_drawio_path(drawio_path, _roots())
    except PathValidationError as e:
        return f"Path validation failed: {e}"
    graph = load_diagram_from_path(p)
    return summarize_architecture_from_graph(graph)


@mcp.tool
def analyze_tradeoff(drawio_path: str, proposal: str) -> str:
    """
    Grounded tradeoff / risk discussion from the diagram (e.g. splitting a service,
    shared database risk, coupling). Uses topology and labels only.
    """
    try:
        p = resolve_drawio_path(drawio_path, _roots())
    except PathValidationError as e:
        return f"Path validation failed: {e}"
    graph = load_diagram_from_path(p)
    return analyze_tradeoff_from_graph(graph, proposal)


def main() -> None:
    """
    CLI entry.

    * Default: **stdio** (VS Code / clients spawn this process — no TCP).
    * ``--http`` or ``DRAWIO_MCP_TRANSPORT=http``: **streamable HTTP** on localhost for ``mcp.json`` ``type: http``.
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="drawio-arch-mcp")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Listen on HTTP (streamable MCP) for clients that connect via URL in mcp.json.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("DRAWIO_MCP_HOST", "127.0.0.1"),
        help="Bind address (default 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("DRAWIO_MCP_PORT", "8000")),
        help="TCP port (default 8000).",
    )
    parser.add_argument(
        "--path",
        default=os.environ.get("DRAWIO_MCP_PATH", "/mcp"),
        help="URL path for MCP (default /mcp).",
    )
    args, _unknown = parser.parse_known_args()

    if os.environ.get("DRAWIO_MCP_LOG_ROOTS"):
        roots = _roots()
        print(f"drawio-arch-mcp allowed roots: {roots}", file=sys.stderr)

    transport_env = os.environ.get("DRAWIO_MCP_TRANSPORT", "").strip().lower()
    use_http = args.http or transport_env in ("http", "streamable-http", "streamable_http")

    if use_http:
        path = args.path if args.path.startswith("/") else f"/{args.path}"
        url = f"http://{args.host}:{args.port}{path}"
        print(
            f"drawio-arch-mcp HTTP MCP → {url}\n"
            f"Use in .vscode/mcp.json: \"type\": \"http\", \"url\": \"{url}\"",
            file=sys.stderr,
        )
        mcp.run(transport="http", host=args.host, port=args.port, path=path)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
