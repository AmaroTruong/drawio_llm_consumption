# drawio-arch-mcp

Local-first MCP server that parses Draw.io diagrams into a normalized graph, lets you mutate and export the graph, convert it back to `.drawio`, and review the architecture for structural concerns.

## Requirements

- Python 3.11+
- A `.drawio` file to analyze

## Quick Start

```bash
git clone https://github.com/AmaroTruong/drawio_llm_consumption.git
cd drawio_llm_consumption

python3 -m venv .venv
.venv/bin/pip install -e .
```

## Running the MCP Server

### Option A: HTTP mode (recommended for first-time setup)

Start the server in a terminal and leave it running:

```bash
export DRAWIO_MCP_ALLOWED_ROOTS="$PWD"
.venv/bin/python -m drawio_arch_mcp.server --http
```

The server listens on `http://127.0.0.1:8000/mcp` by default.

Optional flags:

```bash
.venv/bin/python -m drawio_arch_mcp.server --http --host 127.0.0.1 --port 8765
```

Then configure your MCP client (e.g. VS Code `.vscode/mcp.json`):

```json
{
  "servers": {
    "drawioArchitecture": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

### Option B: stdio mode (VS Code spawns the server automatically)

No terminal needed. Add this to `.vscode/mcp.json`:

```json
{
  "servers": {
    "drawioArchitecture": {
      "type": "stdio",
      "command": "${workspaceFolder}/.venv/bin/python",
      "args": ["-m", "drawio_arch_mcp.server"],
      "env": {
        "DRAWIO_MCP_ALLOWED_ROOTS": "${workspaceFolder}"
      }
    }
  }
}
```

VS Code starts the server when you open the workspace. Use **MCP: List Servers** in the Command Palette to verify it's running.

## Configuration

| Env var | Purpose | Default |
|---------|---------|---------|
| `DRAWIO_MCP_ALLOWED_ROOTS` | Comma-separated directories your `.drawio` files live under | Current working directory |
| `DRAWIO_MCP_HOST` | Bind address (HTTP mode) | `127.0.0.1` |
| `DRAWIO_MCP_PORT` | Port (HTTP mode) | `8000` |

## Available Tools (15)

### Core

| Tool | What it does |
|------|-------------|
| `parse_drawio_file` | Parse `.drawio` → normalized graph JSON |
| `summarize_architecture` | Text summary of components and dependencies |
| `analyze_tradeoff` | Answer tradeoff/risk questions from diagram structure |

### Graph Operations

| Tool | What it does |
|------|-------------|
| `export_architecture_graph` | Return versioned graph JSON artifact |
| `apply_graph_patch` | Add/remove/update nodes and edges |
| `convert_graph_to_drawio` | Write graph back to a `.drawio` file |
| `review_architecture` | Structural review (shared DB, coupling, bypass, etc.) |

### Stubs (not yet implemented)

| Tool | Future purpose |
|------|---------------|
| `search_confluence_context` | Search Confluence pages |
| `read_confluence_page` | Read a Confluence page |
| `get_confluence_context` | Confluence context for a component |
| `search_repo_context` | Search a local repo |
| `get_repo_context` | Repo context for a component |
| `map_component_to_repo` | Map diagram label → repo path |
| `get_component_context` | Unified diagram + repo + Confluence context |
| `hydrate_architecture_context` | Enrich full graph with external context |

## Example Usage

All file-based tools take an **absolute path** to a `.drawio` file under an allowed root.

In Copilot Chat or any MCP client:

> "Call `parse_drawio_file` with `/path/to/my-architecture.drawio`"

> "Call `review_architecture` with `/path/to/my-architecture.drawio`"

> "Call `analyze_tradeoff` with path `/path/to/my-architecture.drawio` and proposal `What is the risk of the shared database?`"

## Sample Diagrams

Bundled under `drawio_arch_mcp/samples/`:

- `sample_architecture.drawio` — small order-processing system
- `simple_bank_architecture_flawed_with_legend.drawio` — banking system with intentional flaws for testing

## Try It Locally (no MCP client needed)

```bash
.venv/bin/python -m drawio_arch_mcp drawio_arch_mcp/samples/simple_bank_architecture_flawed_with_legend.drawio
```

Prints the normalized graph JSON to stdout.
