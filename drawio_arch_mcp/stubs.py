"""
Stubbed MCP tools for Confluence, repository, and combined context.

These are intentionally unimplemented in v0.2.0 — they exist so the tool
surface is visible to MCP clients, enabling forward planning and integration
testing without a live backend.
"""

from __future__ import annotations

_NOT_IMPLEMENTED = (
    "This tool is stubbed for v0.2.0 and not yet implemented. "
    "It will be available in a future release."
)


def _stub(tool_name: str, **kwargs: str) -> dict[str, str]:
    params = ", ".join(f"{k}={v!r}" for k, v in kwargs.items() if v)
    return {
        "status": "not_implemented",
        "tool": tool_name,
        "params_received": params,
        "message": _NOT_IMPLEMENTED,
    }


# ---- Confluence stubs ----

def search_confluence_context(query: str) -> dict[str, str]:
    """Search Confluence for pages matching *query*. (Stubbed — not yet implemented.)"""
    return _stub("search_confluence_context", query=query)


def read_confluence_page(page_id: str) -> dict[str, str]:
    """Read a Confluence page by *page_id*. (Stubbed — not yet implemented.)"""
    return _stub("read_confluence_page", page_id=page_id)


def get_confluence_context(component_name: str) -> dict[str, str]:
    """Get Confluence context for a named component. (Stubbed — not yet implemented.)"""
    return _stub("get_confluence_context", component_name=component_name)


# ---- Repo stubs ----

def search_repo_context(query: str, repo_path: str = "") -> dict[str, str]:
    """Search a local repository for *query*. (Stubbed — not yet implemented.)"""
    return _stub("search_repo_context", query=query, repo_path=repo_path)


def get_repo_context(component_name: str, repo_path: str = "") -> dict[str, str]:
    """Get repo-level context for a named component. (Stubbed — not yet implemented.)"""
    return _stub("get_repo_context", component_name=component_name, repo_path=repo_path)


def map_component_to_repo(component_name: str) -> dict[str, str]:
    """Map a diagram component to a repo directory/service. (Stubbed — not yet implemented.)"""
    return _stub("map_component_to_repo", component_name=component_name)


# ---- Combined context stubs ----

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
    return _stub(
        "get_component_context",
        component_name=component_name,
        drawio_path=drawio_path,
        repo_path=repo_path,
        confluence_ref=confluence_ref,
    )


def hydrate_architecture_context(drawio_path: str) -> dict[str, str]:
    """
    Enrich the entire architecture graph with repo and Confluence context.
    (Stubbed — not yet implemented.)
    """
    return _stub("hydrate_architecture_context", drawio_path=drawio_path)
