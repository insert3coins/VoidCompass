"""Cross-platform desktop helpers and Elite Dangerous path discovery."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys


ELITE_DANGEROUS_STEAM_APP_ID = "359320"
_JOURNAL_PARTS = ("Saved Games", "Frontier Developments", "Elite Dangerous")
_SCREENSHOT_PARTS = ("Pictures", "Frontier Developments", "Elite Dangerous")


def application_dir() -> Path:
    """Writable portable application directory for source and frozen runs."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def open_path(path) -> bool:
    """Open a local file or folder with the platform's desktop handler."""
    target = str(path or "").strip()
    if not target:
        return False
    try:
        if os.name == "nt":
            os.startfile(target)
        elif sys.platform == "darwin":
            subprocess.Popen(
                ["open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        else:
            subprocess.Popen(
                ["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        return True
    except (AttributeError, OSError):
        return False


def _unique_paths(paths):
    result = []
    seen = set()
    for value in paths:
        if not value:
            continue
        path = Path(value).expanduser()
        key = os.path.normcase(os.path.abspath(str(path)))
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _steam_roots(home: Path, environ) -> list[Path]:
    roots = [
        home / ".local/share/Steam",
        home / ".steam/steam",
        home / ".steam/root",
        home / ".steam/debian-installation",
        home / ".var/app/com.valvesoftware.Steam/data/Steam",
        home / ".var/app/com.valvesoftware.Steam/.steam/steam",
        home / "snap/steam/common/.local/share/Steam",
    ]
    for key in ("STEAM_DIR", "STEAM_HOME"):
        if environ.get(key):
            roots.append(Path(environ[key]))

    # Steam records extra library folders in VDF. Only read these small,
    # explicit manifests; never recursively search mounted disks.
    libraries = list(_unique_paths(roots))
    for root in tuple(libraries):
        manifest = root / "steamapps/libraryfolders.vdf"
        try:
            text = manifest.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in re.finditer(r'"path"\s+"([^"]+)"', text, flags=re.IGNORECASE):
            raw = match.group(1).replace(r"\\", "\\")
            libraries.append(Path(raw))
    return _unique_paths(libraries)


def _proton_prefixes(home: Path, environ) -> list[Path]:
    prefixes = []
    compat = environ.get("STEAM_COMPAT_DATA_PATH")
    if compat:
        compat_path = Path(compat).expanduser()
        prefixes.append(compat_path / "pfx" if compat_path.name != "pfx" else compat_path)
    for library in _steam_roots(home, environ):
        steamapps = library if library.name == "steamapps" else library / "steamapps"
        prefixes.append(
            steamapps / "compatdata" / ELITE_DANGEROUS_STEAM_APP_ID / "pfx"
        )
    wine_prefix = environ.get("WINEPREFIX")
    if wine_prefix:
        prefixes.append(Path(wine_prefix).expanduser())
    prefixes.append(home / ".wine")
    return _unique_paths(prefixes)


def _prefix_user_dirs(prefix: Path) -> list[Path]:
    users = prefix / "drive_c/users"
    candidates = [users / "steamuser"]
    try:
        candidates.extend(
            path for path in users.iterdir()
            if path.is_dir() and path.name.casefold() not in {"public", "all users", "default"}
        )
    except OSError:
        pass
    return _unique_paths(candidates)


def elite_journal_candidates(home=None, environ=None) -> list[Path]:
    """Return bounded Windows or Steam/Proton journal candidates."""
    environ = dict(os.environ if environ is None else environ)
    home_path = Path(home).expanduser() if home is not None else Path.home()
    if os.name == "nt" and home is None:
        windows_home = Path(environ.get("USERPROFILE") or home_path)
        return [windows_home.joinpath(*_JOURNAL_PARTS)]

    candidates = []
    for prefix in _proton_prefixes(home_path, environ):
        for user_dir in _prefix_user_dirs(prefix):
            candidates.append(user_dir.joinpath(*_JOURNAL_PARTS))
    return _unique_paths(candidates)


def _journal_freshness(path: Path):
    latest = 0
    journal_count = 0
    try:
        for item in path.iterdir():
            if item.is_file() and item.name.startswith("Journal.") and item.suffix == ".log":
                journal_count += 1
                latest = max(latest, item.stat().st_mtime_ns)
        if not latest:
            latest = path.stat().st_mtime_ns
    except OSError:
        pass
    return journal_count, latest


def detect_elite_journal_path(home=None, environ=None) -> str:
    """Choose the most recently used existing Elite journal directory."""
    existing = [path for path in elite_journal_candidates(home, environ) if path.is_dir()]
    if not existing:
        return ""
    existing.sort(key=_journal_freshness, reverse=True)
    return str(existing[0])


def default_screenshot_path(journal_path=None, home=None, environ=None) -> str:
    """Return the Proton-linked or native screenshot directory."""
    if journal_path:
        journal = Path(journal_path).expanduser()
        try:
            user_dir = journal.parents[2]
            candidate = user_dir.joinpath(*_SCREENSHOT_PARTS)
            if "drive_c" in {part.casefold() for part in candidate.parts}:
                return str(candidate)
        except (IndexError, OSError):
            pass
    home_path = Path(home).expanduser() if home is not None else Path.home()
    if os.name != "nt" or home is not None:
        for prefix in _proton_prefixes(home_path, dict(os.environ if environ is None else environ)):
            for user_dir in _prefix_user_dirs(prefix):
                candidate = user_dir.joinpath(*_SCREENSHOT_PARTS)
                if candidate.is_dir():
                    return str(candidate)
    return str(home_path.joinpath(*_SCREENSHOT_PARTS))
