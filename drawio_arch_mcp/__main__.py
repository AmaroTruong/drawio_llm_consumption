"""
Sample local parsing flow: ``python -m drawio_arch_mcp [path.drawio]``.

Prints a compact JSON view of the normalized graph to stdout.
Defaults to the bundled ``drawio_arch_mcp/samples/sample_architecture.drawio``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from drawio_arch_mcp.parser import parse_drawio_file


def _default_sample() -> Path:
    return Path(__file__).resolve().parent / "samples" / "sample_architecture.drawio"


def main() -> None:
    path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else _default_sample()
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)
    graph = parse_drawio_file(path)
    # Compact preview: full structure may be large
    preview = {
        "diagram_id": graph["diagram_id"],
        "pages": graph["pages"],
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        "group_count": len(graph["groups"]),
        "nodes": graph["nodes"],
        "edges": graph["edges"],
        "groups": graph["groups"],
        "warnings": graph["warnings"],
    }
    print(json.dumps(preview, indent=2))


if __name__ == "__main__":
    main()
