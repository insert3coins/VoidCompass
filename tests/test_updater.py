"""5.5.2.5 in-app updates: the release asset, a download checked twice, a
staged release checked against its manifest, and a swap that only touches the
release's own files and puts everything back if it fails."""

import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
import zipfile

from voidcompass.core import updater

ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD = "https://github.com/insert3coins/VoidCompass/releases/download/5.5.2.5/"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def release_zip(version, files, tamper=None, extra=None):
    """A release zip laid out like tools/release_packager.py makes it."""
    top = f"VoidCompass-v{version}-Windows-x64/"
    manifest = {"product": "Void Compass", "version": version,
                "files": {name: {"bytes": len(data), "sha256": sha(data)} for name, data in files.items()}}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, data in files.items():
            bundle.writestr(top + name, tamper.get(name, data) if tamper else data)
        bundle.writestr(top + "RELEASE_MANIFEST.json", json.dumps(manifest))
        for name, data in (extra or {}).items():
            bundle.writestr(name, data)
    return buffer.getvalue()


class Reply:
    def __init__(self, content=b"", text=""):
        self.content, self.text = content, text

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        for start in range(0, len(self.content), size):
            yield self.content[start:start + size]


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def downloader(self, payload, checksum=None, digest=None):
        name = "VoidCompass-v5.5.2.5-Windows-x64.zip"
        replies = {DOWNLOAD + name: Reply(payload), DOWNLOAD + name + ".sha256": Reply(text=f"{checksum or sha(payload)}  {name}\n")}
        asset = {"name": name, "url": DOWNLOAD + name, "size": len(payload),
                 "sha256": sha(payload) if digest is None else digest, "checksum_url": DOWNLOAD + name + ".sha256"}
        return updater.UpdateDownloader(lambda url, **kw: replies[url], base_dir=self.tmp), asset

    def test_release_asset(self):
        release = {"assets": [
            {"name": "VoidCompass-v5.5.2.5-Windows-x64.zip", "size": 10, "digest": "sha256:ABC",
             "browser_download_url": DOWNLOAD + "VoidCompass-v5.5.2.5-Windows-x64.zip"},
            {"name": "VoidCompass-v5.5.2.5-Windows-x64.zip.sha256",
             "browser_download_url": DOWNLOAD + "VoidCompass-v5.5.2.5-Windows-x64.zip.sha256"},
        ]}
        asset = updater.release_asset(release)
        self.assertEqual((asset["sha256"], asset["checksum_url"].endswith(".sha256")), ("abc", True))
        elsewhere = {"assets": [{**release["assets"][0], "browser_download_url": "https://example.com/VoidCompass.zip"}]}
        self.assertIsNone(updater.release_asset(elsewhere), "only downloads from the project's own releases")
        self.assertIsNone(updater.release_asset({"assets": []}))

    def test_download_is_checked_then_staged(self):
        files = {"VoidCompass.exe": b"new exe", "data/codexRef.json": b"{}"}
        downloader, asset = self.downloader(release_zip("5.5.2.5", files))
        root = downloader.download_and_stage(asset, "5.5.2.5")
        self.assertEqual((root / "VoidCompass.exe").read_bytes(), b"new exe")

    def test_bad_downloads_are_refused(self):
        files = {"VoidCompass.exe": b"new exe"}
        payload = release_zip("5.5.2.5", files)
        cases = {
            "checksum": self.downloader(payload, checksum="0" * 64, digest=""),
            "disagree": self.downloader(payload, checksum="0" * 64),
            "manifest": self.downloader(release_zip("5.5.2.5", files, tamper={"VoidCompass.exe": b"evil"})),
            "version": self.downloader(release_zip("5.5.2.4", files)),
            "unsafe path": self.downloader(release_zip("5.5.2.5", files, extra={"../escape.txt": b"x"})),
        }
        for label, (downloader, asset) in cases.items():
            with self.subTest(label), self.assertRaises(RuntimeError):
                downloader.download_and_stage(asset, "5.5.2.5")
        self.assertFalse((self.tmp / "escape.txt").exists())
        self.assertFalse((self.tmp.parent / "escape.txt").exists())

    def install_setup(self):
        target, staged = self.tmp / "app", self.tmp / "staged"
        for folder in (target, staged):
            (folder / "data").mkdir(parents=True)
        old = {"VoidCompass.exe": b"old exe", "data/codexRef.json": b"old", "data/retired.json": b"gone"}
        for name, data in old.items():
            (target / name).write_bytes(data)
        (target / "RELEASE_MANIFEST.json").write_text(json.dumps({"version": "5.5.2.4.1", "files": {name: {} for name in old}}))
        (target / "config.json").write_text("mine")
        (target / "profiles").mkdir()
        (target / "profiles" / "cmdr.json").write_text("mine")
        new = {"VoidCompass.exe": b"new exe", "data/codexRef.json": b"new", "data/added.json": b"added"}
        for name, data in new.items():
            (staged / name).write_bytes(data)
        (staged / "RELEASE_MANIFEST.json").write_text(json.dumps({"version": "5.5.2.5", "files": {name: {} for name in new}}))
        return target, staged

    def test_install_swaps_only_release_files(self):
        target, staged = self.install_setup()
        result = updater.install_files(staged, target, "5.5.2.4.1", wait_s=1)
        self.assertTrue(result["ok"], result)
        self.assertEqual((target / "VoidCompass.exe").read_bytes(), b"new exe")
        self.assertEqual((target / "data" / "added.json").read_bytes(), b"added")
        self.assertFalse((target / "data" / "retired.json").exists(), "files a release dropped go")
        self.assertEqual(((target / "config.json").read_text(), (target / "profiles" / "cmdr.json").read_text()), ("mine", "mine"))
        self.assertEqual((target / "updates" / "backup-5.5.2.4.1" / "VoidCompass.exe").read_bytes(), b"old exe")
        self.assertEqual(updater.take_result(target)["to"], "5.5.2.5")
        self.assertIsNone(updater.take_result(target), "reported once")

    def test_failed_install_puts_everything_back(self):
        target, staged = self.install_setup()
        real_copy = shutil.copy2

        def copy(source, destination, *args, **kwargs):
            if Path(source) == staged / "data" / "added.json":
                raise OSError("disk full")
            return real_copy(source, destination, *args, **kwargs)
        with mock.patch.object(updater.shutil, "copy2", side_effect=copy):
            result = updater.install_files(staged, target, "5.5.2.4.1", wait_s=1)
        self.assertFalse(result["ok"])
        self.assertIn("disk full", result["error"])
        self.assertEqual((target / "VoidCompass.exe").read_bytes(), b"old exe")
        self.assertEqual((target / "data" / "codexRef.json").read_bytes(), b"old")
        self.assertTrue((target / "data" / "retired.json").exists())
        self.assertFalse((target / "data" / "added.json").exists())

    def test_clean_up_keeps_the_last_backup(self):
        folder = updater.updates_dir(self.tmp)
        for name in ("staged-5.5.2.5", "backup-5.5.2.4", "backup-5.5.2.4.1"):
            (folder / name).mkdir(parents=True)
        (folder / "VoidCompass-v5.5.2.5-Windows-x64.zip").write_bytes(b"zip")
        updater.clean_up(self.tmp, keep_backup="5.5.2.4.1")
        self.assertEqual(sorted(path.name for path in folder.iterdir()), ["backup-5.5.2.4.1"])

    def test_wired_into_the_deck(self):
        runtime = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard_runtime.py").read_text(encoding="utf-8")
        self.assertIn('"install_update", "restart_to_update"', runtime)
        self.assertIn('id="release-update-install"', (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8"))
        self.assertIn("--finish-update", (ROOT / "VoidCompass.py").read_text(encoding="utf-8"))
        self.assertFalse(updater.supported(), "a source run never updates itself")


if __name__ == "__main__":
    unittest.main()
