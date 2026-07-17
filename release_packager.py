"""Create a clean, public Void Compass release from the local test build.

``dist`` is intentionally a runnable development installation and may contain
commander profiles, logs, downloaded voices, cached speech and multi-gigabyte
databases.  This module copies only an explicit public allowlist into a fresh,
versioned release folder, then creates a ZIP and SHA-256 checksum.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from version import APP_VERSION


PRODUCT_NAME = "VoidCompass"
PLATFORM_NAME = "Windows-x64"
PUBLIC_FILENAMES = {
    "VoidCompass.exe",
    "README.md",
    "UPDATE_LOG.md",
    "START_HERE.txt",
    "RELEASE_MANIFEST.json",
    "mining_data.db",
    "codexRef.json",
}
OPTIONAL_LICENSE_PATTERNS = ("LICENSE", "LICENSE.*", "COPYING", "COPYING.*")
README_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
PUBLIC_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_required(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Required release file is missing: {source}")
    shutil.copy2(source, destination)


def _sanitize_mining_database(source: Path, destination: Path) -> None:
    """Copy the public hotspot seed while removing any commander-owned rows."""
    if not source.is_file():
        raise FileNotFoundError(f"Required release file is missing: {source}")
    source_uri = source.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source_db:
        with closing(sqlite3.connect(destination)) as release_db:
            source_db.backup(release_db)
            tables = {
                row[0]
                for row in release_db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            for private_table in ("mining_bookmarks", "mining_sessions"):
                if private_table in tables:
                    release_db.execute(f'DELETE FROM "{private_table}"')
            release_db.commit()
            release_db.execute("VACUUM")


def _write_start_here(path: Path, version: str) -> None:
    path.write_text(
        f"""VOID COMPASS v{version} // WINDOWS x64 PORTABLE RELEASE

Void Compass is self-contained. Python, pip and a virtual environment are not
required.

INSTALL
1. Extract the entire ZIP into a normal writable folder.
2. Run VoidCompass.exe. Do not run it from inside the ZIP.
3. Select your Elite Dangerous journal folder if it is not detected.

Void Compass creates configuration, commander profiles, logs and downloaded
data beside the application. Keep the whole folder together when moving it.
Piper voice packs and the optional market database are downloaded or built
from inside the app when requested.

Windows SmartScreen may display an unrecognised-app warning because community
builds are not code-signed. The ZIP checksum is published alongside this file.
""",
        encoding="utf-8",
    )


def _copy_readme_images(project: Path, package_dir: Path) -> set[str]:
    """Copy local screenshots referenced by README without widening the allowlist."""
    readme = (project / "README.md").read_text(encoding="utf-8")
    copied: set[str] = set()
    for match in README_IMAGE_PATTERN.finditer(readme):
        reference = match.group(1).strip().strip("<>").split(maxsplit=1)[0]
        if not reference or "://" in reference or reference.startswith("data:"):
            continue
        parts = [part for part in reference.replace("\\", "/").split("/") if part]
        relative = Path(*parts)
        if relative.suffix.casefold() not in PUBLIC_IMAGE_EXTENSIONS:
            continue
        source = (project / relative).resolve()
        try:
            safe_relative = source.relative_to(project)
        except ValueError as exc:
            raise RuntimeError(f"README image escapes the project folder: {reference}") from exc
        if not source.is_file():
            raise FileNotFoundError(f"README image is missing: {source}")
        destination = package_dir / safe_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.add(safe_relative.as_posix())
    return copied


def _assert_public_tree(package_dir: Path, allowed: set[str]) -> None:
    unexpected = []
    for path in package_dir.rglob("*"):
        if path.is_file() and path.relative_to(package_dir).as_posix() not in allowed:
            unexpected.append(path.relative_to(package_dir).as_posix())
    if unexpected:
        raise RuntimeError(
            "Release privacy guard rejected unexpected content: "
            + ", ".join(sorted(unexpected))
        )


def create_release(project_dir: str | Path = ".", version: str = APP_VERSION) -> dict:
    project = Path(project_dir).resolve()
    dist_dir = project / "dist"
    release_root = project / "release"
    package_name = f"{PRODUCT_NAME}-v{version}-{PLATFORM_NAME}"
    package_dir = release_root / package_name
    zip_path = release_root / f"{package_name}.zip"
    checksum_path = release_root / f"{package_name}.zip.sha256"

    release_root.mkdir(parents=True, exist_ok=True)
    if package_dir.parent.resolve() != release_root.resolve():
        raise RuntimeError("Refusing to clean a release path outside release/.")
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir()
    zip_path.unlink(missing_ok=True)
    checksum_path.unlink(missing_ok=True)

    _copy_required(dist_dir / "VoidCompass.exe", package_dir / "VoidCompass.exe")
    _copy_required(project / "README.md", package_dir / "README.md")
    _copy_required(project / "mini-readme.md", package_dir / "UPDATE_LOG.md")
    _copy_required(project / "codexRef.json", package_dir / "codexRef.json")
    _sanitize_mining_database(
        project / "mining_data.db", package_dir / "mining_data.db"
    )
    _write_start_here(package_dir / "START_HERE.txt", version)
    readme_images = _copy_readme_images(project, package_dir)

    optional_names: set[str] = set()
    for pattern in OPTIONAL_LICENSE_PATTERNS:
        for source in project.glob(pattern):
            if source.is_file() and source.name not in optional_names:
                shutil.copy2(source, package_dir / source.name)
                optional_names.add(source.name)

    manifest_files = {}
    for path in sorted(package_dir.rglob("*"), key=lambda item: str(item).casefold()):
        if path.is_file():
            relative_name = path.relative_to(package_dir).as_posix()
            manifest_files[relative_name] = {
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
    manifest = {
        "product": "Void Compass",
        "version": version,
        "platform": PLATFORM_NAME,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "python_required": False,
        "files": manifest_files,
    }
    (package_dir / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    allowed = PUBLIC_FILENAMES | optional_names | readme_images
    _assert_public_tree(package_dir, allowed)
    archive_base = release_root / package_name
    shutil.make_archive(
        str(archive_base), "zip", root_dir=release_root, base_dir=package_name
    )
    zip_digest = _sha256(zip_path)
    checksum_path.write_text(
        f"{zip_digest}  {zip_path.name}\n", encoding="ascii"
    )
    return {
        "package_dir": str(package_dir),
        "zip_path": str(zip_path),
        "checksum_path": str(checksum_path),
        "sha256": zip_digest,
        "license_included": bool(optional_names),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package the existing dist/VoidCompass.exe for public release."
    )
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--version", default=APP_VERSION)
    args = parser.parse_args()
    result = create_release(args.project_dir, args.version)
    print(f"Release folder: {result['package_dir']}")
    print(f"Release ZIP:    {result['zip_path']}")
    print(f"SHA-256:        {result['sha256']}")
    if not result["license_included"]:
        print("Warning: no LICENSE or COPYING file was found to include.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
