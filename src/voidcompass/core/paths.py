"""Stable project and bundled-resource paths for source and frozen runs."""

from __future__ import annotations

from pathlib import Path
import sys


def project_root() -> Path:
    """Return the repository root for a source checkout."""
    return Path(__file__).resolve().parents[3]


def bundle_root() -> Path:
    """Return the PyInstaller extraction root or source repository root."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    return Path(frozen_root).resolve() if frozen_root else project_root()


def resource_path(*parts) -> Path:
    """Resolve a read-only bundled asset in both source and frozen modes."""
    return bundle_root().joinpath(*parts)


def source_launcher_path() -> Path:
    """Return the compatibility launcher used by source child processes."""
    return project_root() / "VoidCompass.py"
