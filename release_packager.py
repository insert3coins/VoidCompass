"""Create a clean, public Void Compass release from the local test build.

``dist`` is intentionally a runnable development installation and may contain
commander profiles, logs, downloaded voices, cached speech and multi-gigabyte
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
import tarfile
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
        if target_family not in {"windows", "linux"}:
            raise ValueError(f"Unsupported release platform: {target}")
        linux = target_family == "linux"
    else:
        if sys.platform == "win32":
            linux = False
        elif sys.platform.startswith("linux"):
            linux = True
        else:
            raise RuntimeError("Void Compass releases support Windows and Linux only.")
        target = f"Linux-{arch}" if linux else f"Windows-{arch}"
    executable = executable_name or ("VoidCompass" if linux else "VoidCompass.exe")
    return {
        "platform": target,
        "linux": linux,
        "executable": executable,
        "archive_format": "gztar" if linux else "zip",
        "archive_suffix": ".tar.gz" if linux else ".zip",
    }


def _write_start_here(path: Path, version: str, target) -> None:
    if target["linux"]:
        text = f"""VOID COMPASS v{version} // {target['platform'].upper()} PORTABLE TESTING RELEASE

Void Compass is self-contained. Python, pip and a virtual environment are not
required.

This is the native Linux testing build. Please include your distribution,
desktop session and overlay details when reporting Linux-specific problems.

INSTALL
1. Extract the entire .tar.gz into a normal writable folder.
2. If required, run: chmod +x VoidCompass
3. Start it from that folder with: ./VoidCompass
4. VoidCompass detects Elite Dangerous journals in standard Steam/Proton,
   Flatpak Steam and configured Steam-library prefixes. Browse manually during
   first-run setup if your prefix is elsewhere.

Void Compass creates configuration, commander profiles, logs and downloaded
data beside the application. Keep the whole folder together when moving it.
Piper voice packs and the optional market database are downloaded or built
from inside the app when requested. Linux voice playback uses pw-play, paplay,
aplay or ffplay, whichever is installed.

Linux overlay windows support X11/XWayland topmost positioning. Windows-only
chroma transparency, mouse passthrough and system-wide hotkeys are disabled;
the overlays use an opaque themed background and remain interactive.
"""
    else:
        text = f"""VOID COMPASS v{version} // WINDOWS x64 PORTABLE RELEASE

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
    if target["linux"]:
        executable.chmod(executable.stat().st_mode | 0o111)
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
    if target["linux"] and (project / "icon-source.png").is_file():
        shutil.copy2(project / "icon-source.png", package_dir / "VoidCompass.png")
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
        "platform": target["platform"],
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "python_required": False,
        "files": manifest_files,
    }
    (package_dir / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    allowed = PUBLIC_FILENAMES | optional_names | readme_images | {target["executable"]}
    if target["linux"]:
        allowed.add("VoidCompass.png")
    _assert_public_tree(package_dir, allowed)
    archive_base = release_root / package_name
    if target["linux"]:
        def portable_tar_info(info):
            info.mode = 0o755 if (info.isdir() or info.name.endswith("/VoidCompass")) else 0o644
            return info

        with tarfile.open(archive_path, "w:gz", format=tarfile.PAX_FORMAT) as archive:
            archive.add(
                package_dir, arcname=package_name, recursive=True,
                filter=portable_tar_info,
            )
        created_archive = archive_path
    else:
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
