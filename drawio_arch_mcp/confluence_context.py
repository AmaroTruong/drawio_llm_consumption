"""
Local Confluence-export context: read exported HTML, Markdown, XML, and text
docs from a local directory tree and build evidence for context fusion.
"""

from __future__ import annotations

import html
import os
import re
from pathlib import Path
from typing import Any

from drawio_arch_mcp.models import DocFileInfo, EvidenceDict

_DOC_SUFFIXES = {".html", ".htm", ".md", ".xml", ".txt", ".rst"}
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv"}
_MAX_FILE_READ = 256_000
_MAX_SEARCH_RESULTS = 30

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(raw: str) -> str:
    text = html.unescape(raw)
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def _extract_title(path: Path, content: str) -> str:
    name = path.stem.replace("-", " ").replace("_", " ")
    if path.suffix.lower() in (".html", ".htm"):
        m = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
        if m:
            return _strip_html(m.group(1))
        m = re.search(r"<h1[^>]*>(.*?)</h1>", content, re.IGNORECASE | re.DOTALL)
        if m:
            return _strip_html(m.group(1))
    elif path.suffix.lower() in (".md", ".rst"):
        for line in content.splitlines()[:5]:
            stripped = line.strip().lstrip("#").strip()
            if stripped:
                return stripped
    return name


def scan_docs(docs_path: Path, max_depth: int = 5) -> list[DocFileInfo]:
    """Walk *docs_path* and return all document files."""
    results: list[DocFileInfo] = []
    docs_str = str(docs_path)

    for dirpath, dirnames, filenames in os.walk(docs_path):
        depth = dirpath[len(docs_str):].count(os.sep)
        if depth >= max_depth:
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]

        for fname in filenames:
            p = Path(dirpath) / fname
            if p.suffix.lower() not in _DOC_SUFFIXES:
                continue
            try:
                sz = p.stat().st_size
            except OSError:
                sz = 0
            try:
                snippet = p.read_text(encoding="utf-8", errors="replace")[:500]
            except OSError:
                snippet = ""
            title = _extract_title(p, snippet)
            fmt = p.suffix.lower().lstrip(".")
            if fmt in ("htm",):
                fmt = "html"
            results.append(DocFileInfo(
                path=str(p),
                format=fmt,
                title=title,
                size_bytes=sz,
            ))

    return results


def read_doc_file(file_path: Path) -> dict[str, Any]:
    """Read a single doc file and return its content (plain-text for HTML)."""
    if not file_path.is_file():
        return {"error": f"File not found: {file_path}"}
    try:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {"error": str(e)}

    truncated = len(raw) > _MAX_FILE_READ
    raw = raw[:_MAX_FILE_READ]

    if file_path.suffix.lower() in (".html", ".htm"):
        text = _strip_html(raw)
    else:
        text = raw

    title = _extract_title(file_path, raw)

    return {
        "path": str(file_path),
        "format": file_path.suffix.lower().lstrip("."),
        "title": title,
        "content": text,
        "size_bytes": file_path.stat().st_size,
        "truncated": truncated,
    }


def search_docs(docs_path: Path, query: str) -> list[dict[str, Any]]:
    """Search local doc exports for *query* (case-insensitive substring)."""
    query_lower = query.lower()
    files = scan_docs(docs_path)
    hits: list[dict[str, Any]] = []

    for fi in files:
        if len(hits) >= _MAX_SEARCH_RESULTS:
            break
        p = Path(fi["path"])
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")[:_MAX_FILE_READ]
        except OSError:
            continue

        if p.suffix.lower() in (".html", ".htm"):
            text = _strip_html(raw)
        else:
            text = raw

        lines = text.splitlines()
        for i, line in enumerate(lines):
            if query_lower in line.lower():
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                hits.append({
                    "file": str(p),
                    "title": fi["title"],
                    "format": fi["format"],
                    "line": i + 1,
                    "context": "\n".join(lines[start:end]),
                })
                if len(hits) >= _MAX_SEARCH_RESULTS:
                    break

    return hits


def build_docs_evidence(docs_paths: list[str | Path], component_name: str) -> list[EvidenceDict]:
    """Build evidence entries from doc files mapped to *component_name*."""
    evidence: list[EvidenceDict] = []

    for dp in docs_paths:
        p = Path(dp)
        if not p.exists():
            evidence.append(EvidenceDict(
                source="docs",
                path=str(p),
                snippet=f"Mapped doc path does not exist: {p}",
                confidence="low",
            ))
            continue

        if p.is_dir():
            files = scan_docs(p)
            for fi in files[:5]:
                result = read_doc_file(Path(fi["path"]))
                if "error" not in result:
                    evidence.append(EvidenceDict(
                        source="docs",
                        path=fi["path"],
                        snippet=result.get("content", "")[:500],
                        confidence="high",
                    ))
        elif p.is_file():
            result = read_doc_file(p)
            if "error" not in result:
                evidence.append(EvidenceDict(
                    source="docs",
                    path=str(p),
                    snippet=result.get("content", "")[:500],
                    confidence="high",
                ))

    return evidence
