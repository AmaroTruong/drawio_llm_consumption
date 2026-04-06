"""Resolve and validate local `.drawio` paths against allowed filesystem roots."""

from __future__ import annotations

import os
from pathlib import Path


class PathValidationError(ValueError):
    """Raised when a path is outside allowed roots or not a readable `.drawio` file."""


def _canonical_resolved(path: Path) -> Path:
    """Return absolute, resolved path (symlinks resolved)."""
    return path.expanduser().resolve(strict=False)


def resolve_drawio_path(drawio_path: str, allowed_roots: tuple[str, ...]) -> Path:
    """
    Validate `drawio_path` and return an absolute resolved `Path`.

    Rules:
    - Path must exist and be a regular file.
    - Suffix must be `.drawio` (case-insensitive).
    - Resolved path must be under one of `allowed_roots` (after resolving roots too).

    Raises:
        PathValidationError: If any rule fails.
    """
    if not drawio_path or not drawio_path.strip():
        raise PathValidationError("drawio_path must be a non-empty string.")

    candidate = _canonical_resolved(Path(drawio_path.strip()))

    if not candidate.exists():
        raise PathValidationError(f"Path does not exist: {candidate}")

    if not candidate.is_file():
        raise PathValidationError(f"Not a regular file: {candidate}")

    if candidate.suffix.lower() != ".drawio":
        raise PathValidationError(
            f"Expected a `.drawio` file, got suffix {candidate.suffix!r}: {candidate}"
        )

    if not os.access(candidate, os.R_OK):
        raise PathValidationError(f"File is not readable: {candidate}")

    if not allowed_roots:
        raise PathValidationError(
            "No allowed_roots configured; set DRAWIO_MCP_ALLOWED_ROOTS "
            "(comma-separated) or pass defaults in code."
        )

    resolved_roots = [_canonical_resolved(Path(r.strip())) for r in allowed_roots if r.strip()]
    if not resolved_roots:
        raise PathValidationError("allowed_roots resolved to an empty list.")

    under_any = False
    for root in resolved_roots:
        try:
            candidate.relative_to(root)
            under_any = True
            break
        except ValueError:
            continue

    if not under_any:
        roots_display = ", ".join(str(r) for r in resolved_roots)
        raise PathValidationError(
            f"Path must be under an allowed root. Got {candidate}, allowed: [{roots_display}]"
        )

    return candidate


def load_allowed_roots_from_env() -> tuple[str, ...]:
    """
    Read comma-separated roots from ``DRAWIO_MCP_ALLOWED_ROOTS``.

    Falls back to the current working directory if unset (local dev convenience).
    """
    raw = os.environ.get("DRAWIO_MCP_ALLOWED_ROOTS", "").strip()
    if not raw:
        return (str(Path.cwd().resolve()),)
    return tuple(p.strip() for p in raw.split(",") if p.strip())
