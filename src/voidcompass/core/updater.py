"""In-app updates (5.5.2.5): download the GitHub release, check it, and swap
it in over the portable install.

The release zip is checked twice before anything is unpacked: against the
SHA-256 digest GitHub publishes for the asset and against the .sha256 file
uploaded beside it. Every unpacked file is then checked against the release's
own RELEASE_MANIFEST.json.

Only the files a release ships (its manifest) are ever replaced. Config,
commander profiles, logs and everything else the app writes beside itself are
never in a manifest, so they are never touched.

A running exe cannot be overwritten, so the swap is done by the NEW release's
exe, started from the staging folder with ``--finish-update``. It waits for
this app to close, backs up every file it is about to replace, copies the new
ones in, and starts the updated app. If any copy fails it puts the backups
back and starts the old version again. The outcome is left in
``updates/last_update.json`` for the next start to report.

The ``--finish-update`` arguments are a contract between releases: the exe
that does the swap is always the newer one, so keep them stable."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile

from voidcompass.core.platform_support import application_dir

ASSET_PATTERN = re.compile(r"^VoidCompass-v[0-9][0-9A-Za-z.\-]*-Windows-x64\.zip$")
EXE_NAME = "VoidCompass.exe"
MANIFEST_NAME = "RELEASE_MANIFEST.json"
RESULT_NAME = "last_update.json"
FINISH_FLAG = "--finish-update"
_DOWNLOAD_HOSTS = ("https://github.com/insert3coins/VoidCompass/releases/download/",)
_CHUNK = 1 << 20


def updates_dir(base=None) -> Path:
    return Path(base or application_dir()) / "updates"


def supported() -> bool:
    """Only the packaged Windows app updates itself; a source checkout is
    updated with git."""
    return bool(getattr(sys, "frozen", False)) and os.name == "nt"


def release_asset(release):
    """The Windows zip of a GitHub release (``releases/latest`` JSON), with the
    hashes to check it against: ``None`` when the release has none."""
    assets = [item for item in (release or {}).get("assets") or () if isinstance(item, dict)]
    by_name = {str(item.get("name") or ""): item for item in assets}
    for name, item in by_name.items():
        url = str(item.get("browser_download_url") or "")
        if not ASSET_PATTERN.match(name) or not url.startswith(_DOWNLOAD_HOSTS):
            continue
        digest = str(item.get("digest") or "")
        checksum = by_name.get(f"{name}.sha256") or {}
        checksum_url = str(checksum.get("browser_download_url") or "")
        return {
            "name": name, "url": url, "size": int(item.get("size") or 0),
            "sha256": digest[7:].lower() if digest.lower().startswith("sha256:") else "",
            "checksum_url": checksum_url if checksum_url.startswith(_DOWNLOAD_HOSTS) else "",
        }
    return None


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(name):
    """A manifest or zip path that stays inside the folder it is unpacked to."""
    path = PurePosixPath(str(name).replace("\\", "/"))
    if not path.parts or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        return None
    return path


class UpdateDownloader:
    """Downloads, checks and stages one release in the background. ``state``
    is what the command deck shows: idle, downloading, verifying, ready or
    failed (with ``error``)."""

    def __init__(self, session_get, base_dir=None, on_change=None, user_agent="VoidCompass"):
        self._get = session_get
        self.base = Path(base_dir or application_dir())
        self.on_change = on_change or (lambda: None)
        self.user_agent = user_agent
        self.lock = threading.Lock()
        self.state = {"state": "idle", "version": "", "received": 0, "total": 0, "error": "", "staged": ""}
        self._cancel = threading.Event()

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def _set(self, **changes):
        with self.lock:
            self.state.update(changes)
        try:
            self.on_change()
        except Exception:
            logging.exception("Update progress publish failed")

    def busy(self):
        return self.snapshot()["state"] in ("downloading", "verifying")

    def start(self, asset, version):
        if self.busy() or not asset:
            return False
        self._cancel.clear()
        self._set(state="downloading", version=str(version), received=0, total=int(asset.get("size") or 0), error="", staged="")
        threading.Thread(target=self._run, args=(dict(asset), str(version)), name="release-download", daemon=True).start()
        return True

    def cancel(self):
        self._cancel.set()

    def _run(self, asset, version):
        try:
            staged = self.download_and_stage(asset, version)
        except Exception as exc:
            logging.warning("Update download failed: %s", exc)
            self._set(state="failed", error=str(exc)[:300])
            return
        self._set(state="ready", staged=str(staged))

    # Split from _run so tests can drive it without a thread.
    def download_and_stage(self, asset, version):
        folder = updates_dir(self.base)
        folder.mkdir(parents=True, exist_ok=True)
        expected = {asset.get("sha256") or ""}
        if asset.get("checksum_url"):
            reply = self._get(asset["checksum_url"], headers={"User-Agent": self.user_agent}, timeout=30)
            reply.raise_for_status()
            words = reply.text.split()
            expected.add(words[0].lower() if words else "")
        expected.discard("")
        if not expected:
            raise RuntimeError("The release has no checksum to verify the download against.")
        if len(expected) > 1:
            raise RuntimeError("The release's two checksums disagree; not installing it.")

        part = folder / f"{asset['name']}.part"
        digest, received = hashlib.sha256(), 0
        reply = self._get(asset["url"], headers={"User-Agent": self.user_agent}, timeout=60, stream=True)
        reply.raise_for_status()
        try:
            with open(part, "wb") as handle:
                for block in reply.iter_content(_CHUNK):
                    if self._cancel.is_set():
                        raise RuntimeError("Download cancelled.")
                    if not block:
                        continue
                    handle.write(block)
                    digest.update(block)
                    received += len(block)
                    self._set(received=received)
        finally:
            close = getattr(reply, "close", None)
            if close:
                close()
        self._set(state="verifying")
        if digest.hexdigest() not in expected:
            part.unlink(missing_ok=True)
            raise RuntimeError("The download did not match the release's checksum. Nothing was installed.")
        archive = folder / asset["name"]
        os.replace(part, archive)
        return stage_release(archive, folder / f"staged-{version}", version)


def stage_release(archive, staging, version):
    """Unpack the release zip and check every file against its manifest.
    Returns the folder holding VoidCompass.exe."""
    staging = Path(staging)
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            relative = _safe_relative(info.filename)
            if relative is None:
                raise RuntimeError(f"The release contains an unsafe path: {info.filename}")
            target = staging.joinpath(*relative.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source, open(target, "wb") as sink:
                shutil.copyfileobj(source, sink, _CHUNK)
    roots = [path.parent for path in staging.rglob(MANIFEST_NAME) if (path.parent / EXE_NAME).is_file()]
    if len(roots) != 1:
        raise RuntimeError("The release zip is not laid out as expected.")
    root = roots[0]
    manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    if str(manifest.get("version") or "") != str(version):
        raise RuntimeError(f"The release says it is v{manifest.get('version')}, not v{version}.")
    files = manifest.get("files") or {}
    if EXE_NAME not in files:
        raise RuntimeError("The release manifest does not list the app itself.")
    for name, info in files.items():
        relative = _safe_relative(name)
        path = root.joinpath(*relative.parts) if relative else None
        if path is None or not path.is_file() or _sha256_file(path) != str((info or {}).get("sha256") or "").lower():
            raise RuntimeError(f"{name} in the release failed its check.")
    return root


def _quiet_env():
    """A new onefile exe started from this one must unpack its own copy, not
    reuse ours (PyInstaller 6.9+)."""
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def _spawn(exe, args=(), cwd=None):
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen([str(exe), *args], cwd=str(cwd or Path(exe).parent), env=_quiet_env(),
                            close_fds=True, creationflags=flags)


def launch_install(staged_root, from_version, install_dir=None, pid=None):
    """Start the staged exe to swap itself in once this process has exited."""
    staged_root = Path(staged_root)
    return _spawn(staged_root / EXE_NAME, [
        FINISH_FLAG, "--pid", str(pid or os.getpid()), "--target", str(install_dir or application_dir()),
        "--from-version", str(from_version),
    ], cwd=staged_root)


# -- the swap, run by the new exe ---------------------------------------------
def _wait_for_exit(pid, timeout=120.0):
    if os.name != "nt" or not pid:
        return
    import ctypes
    kernel = ctypes.windll.kernel32
    handle = kernel.OpenProcess(0x00100000, False, int(pid))  # SYNCHRONIZE
    if not handle:
        return  # already gone
    try:
        kernel.WaitForSingleObject(handle, int(timeout * 1000))
    finally:
        kernel.CloseHandle(handle)


def _copy_with_retry(source, target, deadline):
    """The old exe stays locked for a moment after the app closes (its
    overlay and deck processes, and the onefile unpacker, finish after it)."""
    while True:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            return
        except PermissionError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)


def install_files(staged_root, target, from_version, wait_s=90.0):
    """Swap a staged release into ``target``. Returns the result recorded in
    ``updates/last_update.json``; raises nothing."""
    staged_root, target = Path(staged_root), Path(target)
    new = json.loads((staged_root / MANIFEST_NAME).read_text(encoding="utf-8"))
    version = str(new.get("version") or "")
    names = [name for name in new.get("files") or {} if _safe_relative(name)] + [MANIFEST_NAME]
    old_names = []
    try:
        old_names = list((json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8")).get("files") or {}))
    except (OSError, ValueError):
        pass
    gone = [name for name in old_names if name not in names and _safe_relative(name)]
    backup = updates_dir(target) / f"backup-{from_version}"
    shutil.rmtree(backup, ignore_errors=True)
    replaced, created = [], []
    deadline = time.monotonic() + wait_s
    result = {"ok": False, "from": str(from_version), "to": version, "ts": time.time(), "error": ""}
    try:
        for name in names + gone:
            relative = _safe_relative(name)
            current = target.joinpath(*relative.parts)
            if current.is_file():
                saved = backup.joinpath(*relative.parts)
                saved.parent.mkdir(parents=True, exist_ok=True)
                _copy_with_retry(current, saved, deadline)
                replaced.append((current, saved))
        for name in names:
            relative = _safe_relative(name)
            current = target.joinpath(*relative.parts)
            existed = current.exists()
            _copy_with_retry(staged_root.joinpath(*relative.parts), current, deadline)
            if not existed:
                created.append(current)
        for name in gone:
            target.joinpath(*_safe_relative(name).parts).unlink(missing_ok=True)
        result["ok"] = True
    except Exception as exc:
        result["error"] = str(exc)[:300]
        for current in created:
            try:
                current.unlink(missing_ok=True)
            except OSError:
                pass
        for current, saved in replaced:
            try:
                _copy_with_retry(saved, current, time.monotonic() + wait_s)
            except Exception:
                logging.exception("Could not restore %s", current)
    try:
        updates_dir(target).mkdir(parents=True, exist_ok=True)
        (updates_dir(target) / RESULT_NAME).write_text(json.dumps(result), encoding="utf-8")
    except OSError:
        pass
    return result


def finish_update(argv) -> int:
    """``VoidCompass.exe --finish-update --pid N --target DIR --from-version V``,
    run from the staging folder."""
    args = dict(zip(argv[::2], argv[1::2]))
    target = Path(args.get("--target") or "")
    if not target.is_dir():
        return 2
    folder = updates_dir(target)
    folder.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(folder / "update.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    staged_root = Path(sys.executable).resolve().parent
    logging.info("Installing from %s into %s", staged_root, target)
    _wait_for_exit(args.get("--pid"))
    result = install_files(staged_root, target, args.get("--from-version") or "")
    logging.info("Result: %s", result)
    try:
        _spawn(target / EXE_NAME, cwd=target)
    except OSError:
        logging.exception("Could not start Void Compass after the update")
        return 1
    return 0 if result["ok"] else 1


# -- after the restart ----------------------------------------------------------
def take_result(base=None):
    """The last update's outcome, once: the file is removed as it is read."""
    path = updates_dir(base) / RESULT_NAME
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        path.unlink()
    except OSError:
        pass
    return result if isinstance(result, dict) else None


def clean_up(base=None, keep_backup=None):
    """Remove downloads and staging folders; keep only the newest backup (the
    version just replaced) for putting it back by hand."""
    folder = updates_dir(base)
    if not folder.is_dir():
        return
    backups = sorted((path for path in folder.glob("backup-*") if path.is_dir()), key=lambda path: path.stat().st_mtime)
    keep = folder / f"backup-{keep_backup}" if keep_backup else (backups[-1] if backups else None)
    for path in folder.iterdir():
        if path.name in (RESULT_NAME, "update.log") or path == keep:
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            try:
                path.unlink()
            except OSError:
                pass
