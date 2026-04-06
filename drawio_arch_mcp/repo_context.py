"""
Local repository context: scan repos for architecture-relevant files,
search content, and build evidence for context fusion.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any

from drawio_arch_mcp.models import EvidenceDict, RepoFileInfo

# Patterns that indicate architecture-relevant files
_ARCH_PATTERNS: list[tuple[str, str]] = [
    ("README.md", "readme"),
    ("README.rst", "readme"),
    ("readme.*", "readme"),
    ("openapi.yaml", "openapi"),
    ("openapi.yml", "openapi"),
    ("openapi.json", "openapi"),
    ("swagger.yaml", "openapi"),
    ("swagger.json", "openapi"),
    ("*.proto", "openapi"),
    ("Dockerfile", "config"),
    ("Dockerfile.*", "config"),
    ("docker-compose.yml", "config"),
    ("docker-compose.yaml", "config"),
    ("Makefile", "config"),
    ("*.tf", "terraform"),
    ("*.tfvars", "terraform"),
    ("Chart.yaml", "helm"),
    ("values.yaml", "helm"),
    ("values.*.yaml", "helm"),
    ("templates/*.yaml", "helm"),
    ("*.k8s.yaml", "k8s"),
    ("*.k8s.yml", "k8s"),
    ("*deployment*.yaml", "k8s"),
    ("*service*.yaml", "k8s"),
    ("*ingress*.yaml", "k8s"),
    ("kustomization.yaml", "k8s"),
]

_ARCH_DIR_NAMES = {"docs", "doc", "documentation", "adrs", "adr", "deploy", "deployment", "k8s", "helm", "terraform", "infra"}

_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".tox", ".mypy_cache", "dist", "build", ".eggs"}

_MAX_FILE_READ = 256_000  # 256 KB cap per file read
_MAX_SEARCH_RESULTS = 30


def _categorize(rel: str) -> str:
    name = Path(rel).name.lower()
    rel_lower = rel.lower()
    for pattern, cat in _ARCH_PATTERNS:
        if fnmatch.fnmatch(name, pattern.lower()):
            return cat
    parts = set(Path(rel_lower).parts)
    if parts & {"docs", "doc", "documentation"}:
        return "docs"
    if parts & {"adrs", "adr"}:
        return "adr"
    if parts & {"deploy", "deployment", "k8s", "kubernetes"}:
        return "k8s"
    if parts & {"helm"}:
        return "helm"
    if parts & {"terraform", "infra"}:
        return "terraform"
    return "other"


def scan_repo(repo_path: Path, max_depth: int = 6) -> list[RepoFileInfo]:
    """Walk *repo_path* and return architecture-relevant files."""
    results: list[RepoFileInfo] = []
    repo_str = str(repo_path)

    for dirpath, dirnames, filenames in os.walk(repo_path):
        depth = dirpath[len(repo_str):].count(os.sep)
        if depth >= max_depth:
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]

        rel_dir = os.path.relpath(dirpath, repo_path)
        dir_parts = set(Path(rel_dir).parts)

        is_arch_dir = bool(dir_parts & _ARCH_DIR_NAMES) or rel_dir == "."

        for fname in filenames:
            rel = os.path.join(rel_dir, fname) if rel_dir != "." else fname
            cat = _categorize(rel)
            if cat != "other" or is_arch_dir:
                full = os.path.join(dirpath, fname)
                try:
                    sz = os.path.getsize(full)
                except OSError:
                    sz = 0
                results.append(RepoFileInfo(relative_path=rel, category=cat, size_bytes=sz))

    return results


def read_repo_file(repo_path: Path, relative_path: str) -> dict[str, Any]:
    """Read a single file from a repo."""
    full = (repo_path / relative_path).resolve()
    if not full.is_file():
        return {"error": f"File not found: {relative_path}"}
    try:
        full.relative_to(repo_path.resolve())
    except ValueError:
        return {"error": f"Path escapes repo root: {relative_path}"}
    try:
        sz = full.stat().st_size
        if sz > _MAX_FILE_READ:
            content = full.read_text(encoding="utf-8", errors="replace")[:_MAX_FILE_READ]
            truncated = True
        else:
            content = full.read_text(encoding="utf-8", errors="replace")
            truncated = False
    except OSError as e:
        return {"error": str(e)}
    return {
        "relative_path": relative_path,
        "content": content,
        "size_bytes": sz,
        "truncated": truncated,
    }


def search_repo(repo_path: Path, query: str) -> list[dict[str, Any]]:
    """
    Simple content search across architecture-relevant files.

    Returns up to ``_MAX_SEARCH_RESULTS`` matches with surrounding context.
    """
    query_lower = query.lower()
    files = scan_repo(repo_path)
    hits: list[dict[str, Any]] = []

    for fi in files:
        if len(hits) >= _MAX_SEARCH_RESULTS:
            break
        full = repo_path / fi["relative_path"]
        try:
            text = full.read_text(encoding="utf-8", errors="replace")[:_MAX_FILE_READ]
        except OSError:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if query_lower in line.lower():
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                hits.append({
                    "file": fi["relative_path"],
                    "category": fi["category"],
                    "line": i + 1,
                    "context": "\n".join(lines[start:end]),
                })
                if len(hits) >= _MAX_SEARCH_RESULTS:
                    break

    return hits


def build_repo_evidence(repo_path: Path, component_name: str) -> list[EvidenceDict]:
    """Build evidence entries from a repo scan relevant to *component_name*."""
    evidence: list[EvidenceDict] = []
    files = scan_repo(repo_path)

    if not files:
        return evidence

    # README summary
    readmes = [f for f in files if f["category"] == "readme"]
    for rm in readmes[:1]:
        full = repo_path / rm["relative_path"]
        try:
            text = full.read_text(encoding="utf-8", errors="replace")[:2000]
        except OSError:
            continue
        evidence.append(EvidenceDict(
            source="repo",
            path=rm["relative_path"],
            snippet=text.strip()[:500],
            confidence="high",
        ))

    # File inventory summary
    cats = {}
    for f in files:
        cats.setdefault(f["category"], []).append(f["relative_path"])
    inv_lines = [f"{cat}: {len(paths)} file(s)" for cat, paths in sorted(cats.items())]
    evidence.append(EvidenceDict(
        source="repo",
        snippet=f"Repo file inventory for {component_name}:\n" + "\n".join(inv_lines),
        confidence="high",
    ))

    # OpenAPI presence
    apis = [f for f in files if f["category"] == "openapi"]
    for api in apis[:2]:
        full = repo_path / api["relative_path"]
        try:
            text = full.read_text(encoding="utf-8", errors="replace")[:1000]
        except OSError:
            continue
        evidence.append(EvidenceDict(
            source="repo",
            path=api["relative_path"],
            snippet=text.strip()[:400],
            confidence="high",
        ))

    return evidence
