"""Locate data files both from source and from a PyInstaller bundle."""

from __future__ import annotations

import sys
from pathlib import Path


def bundled_path(path: str | Path) -> Path | None:
    """Return a bundled resource path when running from a frozen executable."""
    candidate = Path(path)
    if candidate.is_absolute() or not getattr(sys, "frozen", False):
        return None
    bundle_root = getattr(sys, "_MEIPASS", None)
    if not bundle_root:
        return None
    bundled = Path(bundle_root) / candidate
    return bundled if bundled.exists() else None


def resolve_data_file(path: str | Path) -> Path:
    """Prefer a user-provided relative path, then fall back to bundled data."""
    candidate = Path(path)
    if candidate.is_file():
        return candidate
    return bundled_path(candidate) or candidate
