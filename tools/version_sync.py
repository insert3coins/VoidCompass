"""Keep release metadata synchronized with the canonical application version."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from voidcompass.core.version import APP_VERSION


VERSION_TARGETS = {
    "pyproject.toml": re.compile(r'(?m)^(version\s*=\s*")[^"]+("\s*)$'),
    "README.md": re.compile(r'(?m)^(\*\*Current version:\s*)[^*]+(\*\*\s*)$'),
    "mini-readme.md": re.compile(r'(?m)^(##\s+v)[^\s]+(\s+//)'),
}


def synchronized_versions(project_root: Path = PROJECT_ROOT) -> dict[str, str | None]:
    """Return the version declared by each release metadata file."""
    versions: dict[str, str | None] = {}
    for relative, pattern in VERSION_TARGETS.items():
        text = (project_root / relative).read_text(encoding="utf-8")
        match = pattern.search(text)
        if not match:
            versions[relative] = None
            continue
        declaration = match.group(0)
        found = re.search(r"\d+(?:\.\d+)+", declaration)
        versions[relative] = found.group(0) if found else None
    return versions


def validate_version_sync(
    project_root: Path = PROJECT_ROOT,
    expected: str = APP_VERSION,
) -> list[str]:
    """Describe release metadata that does not match ``APP_VERSION``."""
    return [
        f"{relative}: expected {expected}, found {actual or 'no version declaration'}"
        for relative, actual in synchronized_versions(project_root).items()
        if actual != expected
    ]


def write_version_sync(
    project_root: Path = PROJECT_ROOT,
    version: str = APP_VERSION,
) -> None:
    """Update the few static metadata formats that cannot import Python."""
    if not re.fullmatch(r"\d+(?:\.\d+)+", version):
        raise ValueError(f"Invalid application version: {version!r}")
    for relative, pattern in VERSION_TARGETS.items():
        path = project_root / relative
        text = path.read_text(encoding="utf-8")
        updated, count = pattern.subn(rf"\g<1>{version}\g<2>", text, count=1)
        if count != 1:
            raise RuntimeError(f"Could not locate the version declaration in {relative}")
        path.write_text(updated, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="update static metadata")
    args = parser.parse_args()
    if args.write:
        write_version_sync(version=APP_VERSION)
    errors = validate_version_sync(expected=APP_VERSION)
    if errors:
        print("Version metadata is out of sync:", *errors, sep="\n- ")
        return 1
    print(f"Version metadata matches {APP_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
