"""
Simple file-based cache for parsed graphs and hydrated context.

Cache key = hash of source file path + mtime. Cached artifacts are JSON
files in ``DRAWIO_MCP_CACHE_DIR`` (default: no caching).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _cache_dir() -> Path | None:
    raw = os.environ.get("DRAWIO_MCP_CACHE_DIR", "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cache_key(source_path: str, namespace: str) -> str:
    p = Path(source_path).resolve()
    try:
        mtime = str(p.stat().st_mtime)
    except OSError:
        mtime = "0"
    raw = f"{namespace}:{p}:{mtime}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def cache_get(source_path: str, namespace: str = "graph") -> dict[str, Any] | None:
    """Return cached JSON dict or None."""
    d = _cache_dir()
    if not d:
        return None
    key = _cache_key(source_path, namespace)
    cache_file = d / f"{namespace}_{key}.json"
    if cache_file.is_file():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def cache_put(source_path: str, data: dict[str, Any], namespace: str = "graph") -> None:
    """Store *data* in the cache."""
    d = _cache_dir()
    if not d:
        return
    key = _cache_key(source_path, namespace)
    cache_file = d / f"{namespace}_{key}.json"
    try:
        cache_file.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def cache_clear(namespace: str | None = None) -> int:
    """Remove cached files. Returns count of files deleted."""
    d = _cache_dir()
    if not d:
        return 0
    count = 0
    for f in d.iterdir():
        if not f.is_file() or not f.suffix == ".json":
            continue
        if namespace and not f.name.startswith(f"{namespace}_"):
            continue
        f.unlink(missing_ok=True)
        count += 1
    return count
