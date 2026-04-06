"""Resolve and validate local paths against allowed filesystem roots."""

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


def resolve_output_path(output_path: str, allowed_roots: tuple[str, ...]) -> Path:
    """
    Validate an output ``.drawio`` path for writing.

    Rules mirror ``resolve_drawio_path`` except the file need not exist yet.
    Parent directory must exist and be writable.
    """
    if not output_path or not output_path.strip():
        raise PathValidationError("output_path must be a non-empty string.")

    candidate = _canonical_resolved(Path(output_path.strip()))

    if candidate.suffix.lower() != ".drawio":
        raise PathValidationError(
            f"Expected a `.drawio` suffix, got {candidate.suffix!r}: {candidate}"
        )

    parent = candidate.parent
    if not parent.exists():
        raise PathValidationError(f"Parent directory does not exist: {parent}")
    if not os.access(parent, os.W_OK):
        raise PathValidationError(f"Parent directory is not writable: {parent}")

    if not allowed_roots:
        raise PathValidationError("No allowed_roots configured.")

    resolved_roots = [_canonical_resolved(Path(r.strip())) for r in allowed_roots if r.strip()]
    under_any = any(_is_under(candidate, root) for root in resolved_roots)
    if not under_any:
        roots_display = ", ".join(str(r) for r in resolved_roots)
        raise PathValidationError(
            f"Output path must be under an allowed root. Got {candidate}, allowed: [{roots_display}]"
        )

    return candidate


def _is_under(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _check_under_roots(candidate: Path, allowed_roots: tuple[str, ...], label: str) -> Path:
    """Shared root-check for all path validators."""
    if not allowed_roots:
        raise PathValidationError(f"No allowed_roots configured for {label}.")
    resolved_roots = [_canonical_resolved(Path(r.strip())) for r in allowed_roots if r.strip()]
    if not any(_is_under(candidate, root) for root in resolved_roots):
        roots_display = ", ".join(str(r) for r in resolved_roots)
        raise PathValidationError(
            f"{label} must be under an allowed root. Got {candidate}, allowed: [{roots_display}]"
        )
    return candidate


def resolve_local_dir(dir_path: str, allowed_roots: tuple[str, ...], label: str = "Directory") -> Path:
    """Validate a readable local directory under allowed roots."""
    if not dir_path or not dir_path.strip():
        raise PathValidationError(f"{label} path must be a non-empty string.")
    candidate = _canonical_resolved(Path(dir_path.strip()))
    if not candidate.exists():
        raise PathValidationError(f"{label} does not exist: {candidate}")
    if not candidate.is_dir():
        raise PathValidationError(f"{label} is not a directory: {candidate}")
    if not os.access(candidate, os.R_OK):
        raise PathValidationError(f"{label} is not readable: {candidate}")
    return _check_under_roots(candidate, allowed_roots, label)


def resolve_local_file(
    file_path: str,
    allowed_roots: tuple[str, ...],
    label: str = "File",
    allowed_suffixes: tuple[str, ...] | None = None,
) -> Path:
    """Validate a readable local file under allowed roots, with optional suffix filter."""
    if not file_path or not file_path.strip():
        raise PathValidationError(f"{label} path must be a non-empty string.")
    candidate = _canonical_resolved(Path(file_path.strip()))
    if not candidate.exists():
        raise PathValidationError(f"{label} does not exist: {candidate}")
    if not candidate.is_file():
        raise PathValidationError(f"{label} is not a regular file: {candidate}")
    if allowed_suffixes:
        if candidate.suffix.lower() not in allowed_suffixes:
            raise PathValidationError(
                f"{label}: expected suffix in {allowed_suffixes}, got {candidate.suffix!r}: {candidate}"
            )
    if not os.access(candidate, os.R_OK):
        raise PathValidationError(f"{label} is not readable: {candidate}")
    return _check_under_roots(candidate, allowed_roots, label)


def load_allowed_roots_from_env() -> tuple[str, ...]:
    """
    Read comma-separated roots from ``DRAWIO_MCP_ALLOWED_ROOTS``.

    Falls back to the current working directory if unset (local dev convenience).
    """
    raw = os.environ.get("DRAWIO_MCP_ALLOWED_ROOTS", "").strip()
    if not raw:
        return (str(Path.cwd().resolve()),)
    return tuple(p.strip() for p in raw.split(",") if p.strip())
