"""Create a clean, public Void Compass release from the local test build.

``dist`` is intentionally a runnable development installation and may contain
commander profiles, logs, downloaded data and multi-gigabyte
databases. This module copies only an explicit public allowlist into a fresh,
versioned release folder, then creates a platform-native archive and SHA-256
checksum.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from version import APP_VERSION


PRODUCT_NAME = "VoidCompass"
PUBLIC_FILENAMES = {
    "README.md",
    "UPDATE_LOG.md",
    "START_HERE.txt",
    "THIRD_PARTY_NOTICES.md",
    "RELEASE_MANIFEST.json",
    "mining_data.db",
    "codexRef.json",
}
OPTIONAL_LICENSE_PATTERNS = ("LICENSE", "LICENSE.*", "COPYING", "COPYING.*")
README_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
PUBLIC_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
PUBLIC_RUNTIME_IMAGE_DOCUMENTS = {
    # Attribution and provenance for the bundled ship-art catalogue. Keep the
    # runtime image tree strict: this is the only intentional non-image file.
    "Images/ships/README.md",
}
REQUIRED_RUNTIME_IMAGES = {
    "Images/Galaxy/voidcompass-galactic-atlas.png",
}


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


def _release_target(platform_name=None, executable_name=None):
    machine = platform.machine().casefold()
    arch = "arm64" if machine in {"arm64", "aarch64"} else "x64"
    if platform_name:
        target = str(platform_name)
        target_family = target.casefold().split("-", 1)[0]
        if target_family != "windows":
            raise ValueError(f"Unsupported release platform: {target}")
    else:
        if sys.platform != "win32":
            raise RuntimeError("Void Compass 5.3.9 releases require Windows/WebView2.")
        target = f"Windows-{arch}"
    executable = executable_name or "VoidCompass.exe"
    return {
        "platform": target,
        "linux": False,
        "executable": executable,
        "archive_format": "zip",
        "archive_suffix": ".zip",
    }


def _write_start_here(path: Path, version: str, target) -> None:
    text = f"""VOID COMPASS v{version} // WINDOWS x64 PORTABLE RELEASE

Void Compass is self-contained. Python, pip and a virtual environment are not
required.

INSTALL
1. Extract the entire ZIP into a normal writable folder.
2. Run VoidCompass.exe. Do not run it from inside the ZIP.
3. Select your Elite Dangerous journal folder if it is not detected.

Void Compass creates configuration, commander profiles, logs and downloaded
data beside the application. Keep the whole folder together when moving it.

Windows SmartScreen may display an unrecognised-app warning because community
builds are not code-signed. The ZIP checksum is published alongside this file.
"""
    path.write_text(text, encoding="utf-8")


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


def _copy_runtime_images(project: Path, package_dir: Path) -> set[str]:
    """Copy the public runtime image tree without weakening the privacy guard."""
    source_root = project / "Images"
    if not source_root.is_dir():
        raise FileNotFoundError(f"Required runtime image folder is missing: {source_root}")
    copied: set[str] = set()
    for source in sorted(source_root.rglob("*"), key=lambda item: str(item).casefold()):
        if source.is_symlink():
            raise RuntimeError(f"Release image tree contains a symlink: {source}")
        if not source.is_file():
            continue
        resolved = source.resolve()
        try:
            safe_relative = resolved.relative_to(project)
        except ValueError as exc:
            raise RuntimeError(f"Release image escapes the project folder: {source}") from exc
        relative_name = safe_relative.as_posix()
        if (
            source.suffix.casefold() not in PUBLIC_IMAGE_EXTENSIONS
            and relative_name not in PUBLIC_RUNTIME_IMAGE_DOCUMENTS
        ):
            raise RuntimeError(f"Release image tree contains a non-image file: {source}")
        destination = package_dir / safe_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved, destination)
        copied.add(safe_relative.as_posix())
    missing = REQUIRED_RUNTIME_IMAGES - copied
    if missing:
        raise FileNotFoundError(
            "Required runtime image assets are missing: " + ", ".join(sorted(missing))
        )
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


def create_release(
    project_dir: str | Path = ".",
    version: str = APP_VERSION,
    platform_name=None,
    executable_name=None,
) -> dict:
    project = Path(project_dir).resolve()
    dist_dir = project / "dist"
    release_root = project / "release"
    target = _release_target(platform_name, executable_name)
    package_name = f"{PRODUCT_NAME}-v{version}-{target['platform']}"
    package_dir = release_root / package_name
    archive_path = release_root / f"{package_name}{target['archive_suffix']}"
    checksum_path = release_root / f"{archive_path.name}.sha256"

    release_root.mkdir(parents=True, exist_ok=True)
    if package_dir.parent.resolve() != release_root.resolve():
        raise RuntimeError("Refusing to clean a release path outside release/.")
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir()
    archive_path.unlink(missing_ok=True)
    checksum_path.unlink(missing_ok=True)

    executable = package_dir / target["executable"]
    _copy_required(dist_dir / target["executable"], executable)
    _copy_required(project / "README.md", package_dir / "README.md")
    _copy_required(project / "mini-readme.md", package_dir / "UPDATE_LOG.md")
    _copy_required(
        project / "THIRD_PARTY_NOTICES.md",
        package_dir / "THIRD_PARTY_NOTICES.md",
    )
    _copy_required(project / "codexRef.json", package_dir / "codexRef.json")
    _sanitize_mining_database(
        project / "mining_data.db", package_dir / "mining_data.db"
    )
    _write_start_here(package_dir / "START_HERE.txt", version, target)
    readme_images = _copy_readme_images(project, package_dir)
    runtime_images = _copy_runtime_images(project, package_dir)

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
        "platform": target["platform"],
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "python_required": False,
        "files": manifest_files,
    }
    (package_dir / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    allowed = (
        PUBLIC_FILENAMES | optional_names | readme_images | runtime_images
        | {target["executable"]}
    )
    _assert_public_tree(package_dir, allowed)
    archive_base = release_root / package_name
    created_archive = Path(shutil.make_archive(
        str(archive_base), target["archive_format"],
        root_dir=release_root, base_dir=package_name,
    ))
    if created_archive != archive_path:
        raise RuntimeError(
            f"Release archive mismatch: expected {archive_path}, got {created_archive}"
        )
    archive_digest = _sha256(archive_path)
    checksum_path.write_text(
        f"{archive_digest}  {archive_path.name}\n", encoding="ascii"
    )
    return {
        "package_dir": str(package_dir),
        "archive_path": str(archive_path),
        # Compatibility for existing build tooling and any private scripts.
        "zip_path": str(archive_path),
        "checksum_path": str(checksum_path),
        "sha256": archive_digest,
        "platform": target["platform"],
        "license_included": bool(optional_names),
        "runtime_image_count": sum(
            Path(name).suffix.casefold() in PUBLIC_IMAGE_EXTENSIONS
            for name in runtime_images
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package the existing dist/VoidCompass build for public release."
    )
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--version", default=APP_VERSION)
    args = parser.parse_args()
    result = create_release(args.project_dir, args.version)
    print(f"Release folder: {result['package_dir']}")
    print(f"Release archive: {result['archive_path']}")
    print(f"SHA-256:        {result['sha256']}")
    if not result["license_included"]:
        print("Warning: no LICENSE or COPYING file was found to include.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
