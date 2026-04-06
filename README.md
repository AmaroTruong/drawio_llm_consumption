# drawio-arch-mcp

Local-first MCP server that parses Draw.io diagrams into a normalized graph, lets you mutate and export the graph, convert it back to `.drawio`, review architecture, and fuse context from repos, Confluence exports, and mapping files.

## Requirements

- Python 3.11+
- A `.drawio` file to analyze
- (Optional) Local cloned repos, exported Confluence pages, and mapping files for context fusion

## Quick Start

```bash
git clone https://github.com/AmaroTruong/drawio_llm_consumption.git
cd drawio_llm_consumption

python3 -m venv .venv
.venv/bin/pip install -e .
```

## Local Context Layout (v0.3.0)

To use context fusion features (repo context, Confluence exports, mapping), set up a local directory layout like:

```text
/work/arch-context/
  diagrams/
    prod-system.drawio

  repos/
    auth-service/          # cloned repo
    account-service/       # cloned repo
    transfer-service/      # cloned repo

  confluence_exports/
    architecture/
      auth-service.html    # exported Confluence page
      transfer-service.html
    adrs/
      adr-001-service-boundaries.md
    runbooks/
      payment-failures.html

  mappings/
    component_map.json     # maps diagram labels → repos/docs/owners
    aliases.json           # shorthand aliases for component names

  cache/                   # optional: parsed graph / hydrated context cache
  output/                  # optional: exported diagrams and reports
```

### Mapping Files

**`component_map.json`** — maps diagram component labels to their repo, docs, owner, and tags:

```json
{
  "version": "1.0",
  "components": {
    "Auth Service": {
      "repo_path": "repos/auth-service",
      "docs_paths": ["confluence_exports/architecture/auth-service.html"],
      "owner": "platform-team",
      "tags": ["security", "identity"]
    },
    "Transfer Service": {
      "repo_path": "repos/transfer-service",
      "docs_paths": [
        "confluence_exports/architecture/transfer-service.html",
        "confluence_exports/runbooks/payment-failures.html"
      ],
      "owner": "payments-team",
      "tags": ["payments", "transfers"]
    }
  }
}
```

**`aliases.json`** — shorthand names that resolve to canonical component names:

```json
{
  "version": "1.0",
  "aliases": {
    "auth": "Auth Service",
    "auth-svc": "Auth Service",
    "transfers": "Transfer Service",
    "payments": "Transfer Service"
  }
}
```

Sample mapping files are included in `drawio_arch_mcp/samples/mappings/`.

## Running the MCP Server

### Option A: HTTP mode

```bash
export DRAWIO_MCP_ALLOWED_ROOTS="/work/arch-context"
export DRAWIO_MCP_MAPPINGS_DIR="/work/arch-context/mappings"
.venv/bin/python -m drawio_arch_mcp.server --http
```

Server listens on `http://127.0.0.1:8000/mcp`.

Configure your MCP client:

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

### Option B: stdio mode (VS Code spawns the server)

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "drawioArchitecture": {
      "type": "stdio",
      "command": "${workspaceFolder}/.venv/bin/python",
      "args": ["-m", "drawio_arch_mcp.server"],
      "env": {
        "DRAWIO_MCP_ALLOWED_ROOTS": "${workspaceFolder}/..,${workspaceFolder}",
        "DRAWIO_MCP_MAPPINGS_DIR": "/work/arch-context/mappings",
        "DRAWIO_MCP_CACHE_DIR": "/work/arch-context/cache"
      }
    }
  }
}
```

VS Code starts the server when you open the workspace.

## Configuration

| Env var | Purpose | Default |
|---------|---------|---------|
| `DRAWIO_MCP_ALLOWED_ROOTS` | Comma-separated directories files must be under | Current working directory |
| `DRAWIO_MCP_MAPPINGS_DIR` | Directory containing `component_map.json` / `aliases.json` | (none — mapping disabled) |
| `DRAWIO_MCP_CACHE_DIR` | Directory for cached parsed graphs and hydrated context | (none — caching disabled) |
| `DRAWIO_MCP_HOST` | Bind address (HTTP mode) | `127.0.0.1` |
| `DRAWIO_MCP_PORT` | Port (HTTP mode) | `8000` |

## Available Tools

### Core (v0.1)

| Tool | Description |
|------|-------------|
| `parse_drawio_file(drawio_path)` | Parse `.drawio` → normalized graph JSON |
| `summarize_architecture(drawio_path)` | Text summary of components and dependencies |
| `analyze_tradeoff(drawio_path, proposal)` | Tradeoff/risk analysis from diagram structure |

### Graph Operations (v0.2)

| Tool | Description |
|------|-------------|
| `export_architecture_graph(drawio_path)` | Return versioned graph JSON artifact |
| `apply_graph_patch(graph, patch)` | Add/remove/update nodes and edges |
| `convert_graph_to_drawio(graph, output_path)` | Write graph back to `.drawio` file |
| `review_architecture(drawio_path)` | Diagram-only structural review |

### Repo Context (v0.3)

| Tool | Description |
|------|-------------|
| `search_repo_context(query, repo_path)` | Search a local repo for architecture-relevant content |
| `read_repo_file(repo_path, relative_path)` | Read a single file from a repo |
| `get_repo_context(component_name, repo_path?)` | Architecture-relevant repo context for a component |
| `map_component_to_repo(component_name)` | Look up mapping entry (repo, docs, owner, tags) |

### Confluence-Export Context (v0.3)

| Tool | Description |
|------|-------------|
| `search_confluence_context(query, docs_path)` | Search local exported Confluence docs |
| `read_confluence_page(local_path)` | Read a local exported page (HTML/MD/XML/txt) |
| `get_confluence_context(component_name, docs_path?)` | Doc context for a component |

### Context Hydration (v0.3)

| Tool | Description |
|------|-------------|
| `get_component_context(component_name, drawio_path, repo_path?, docs_path?)` | Unified context: diagram + repo + docs + mapping evidence |
| `hydrate_architecture_context(drawio_path)` | Enrich all diagram components with context from mappings |

### Validation & Review (v0.3)

| Tool | Description |
|------|-------------|
| `validate_architecture_consistency(drawio_path)` | Cross-source consistency checks |
| `review_architecture_contextual(drawio_path)` | Multi-source review (diagram + consistency findings) |

### MCP Resources

| URI | Description |
|-----|-------------|
| `archgraph:///{drawio_filename}` | Parsed graph JSON for a diagram |
| `component:///{component_name}/summary` | Component summary from mapping + diagram |
| `mapping:///component_map` | Current component_map.json |
| `mapping:///aliases` | Current aliases.json |

## Example Usage

### Basic diagram analysis

```
Call parse_drawio_file with /work/arch-context/diagrams/prod-system.drawio
```

```
Call review_architecture with /work/arch-context/diagrams/prod-system.drawio
```

### Repo context

```
Call search_repo_context with query "authentication" and repo_path "/work/arch-context/repos/auth-service"
```

```
Call get_repo_context with component_name "Auth Service"
```

### Confluence-export context

```
Call search_confluence_context with query "service boundaries" and docs_path "/work/arch-context/confluence_exports"
```

```
Call read_confluence_page with local_path "/work/arch-context/confluence_exports/architecture/auth-service.html"
```

### Context hydration

```
Call get_component_context with component_name "Auth Service" and drawio_path "/work/arch-context/diagrams/prod-system.drawio"
```

```
Call hydrate_architecture_context with drawio_path "/work/arch-context/diagrams/prod-system.drawio"
```

### Cross-source validation

```
Call validate_architecture_consistency with drawio_path "/work/arch-context/diagrams/prod-system.drawio"
```

### Multi-source review

```
Call review_architecture_contextual with drawio_path "/work/arch-context/diagrams/prod-system.drawio"
```

## Evidence Model

Context fusion outputs separate evidence by source:

- **diagram** — from the parsed .drawio graph
- **repo** — from local repository files
- **docs** — from local Confluence-export files
- **mapping** — from component_map.json / aliases.json
- **inference** — system-generated observations

Each evidence entry includes a `confidence` level (`high`, `medium`, `low`).

## Sample Diagrams

Bundled under `drawio_arch_mcp/samples/`:

- `sample_architecture.drawio` — small order-processing system

Additional diagrams at repo root:

- `simple_bank_architecture_flawed_with_legend.drawio` — banking system with intentional flaws
- `fixed_simple_bank_architecture.drawio` — corrected version

## Try It Locally (no MCP client needed)

```bash
.venv/bin/python -m drawio_arch_mcp drawio_arch_mcp/samples/sample_architecture.drawio
```
