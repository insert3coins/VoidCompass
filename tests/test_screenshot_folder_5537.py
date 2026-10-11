"""5.5.3.7: screenshots with OneDrive (and other cloud sync apps).

Reported: screenshots and OneDrive. Two causes:

* The folder. With OneDrive's folder backup, Windows keeps Pictures in
  OneDrive and Elite saves its screenshots there, but Void Compass assumed
  the user folder's Pictures (and saved that guess), so it watched an empty
  or missing folder. It now asks Windows where Pictures is, and repairs a
  saved guess.
* The converter. A sync app locks a new file while it uploads it: the BMP
  couldn't be deleted after its PNG was made, so it was converted again on
  every pass (a pile of numbered copies). A save cut short left half a PNG.
  And cloud-only placeholders would have been downloaded to be converted.
"""

import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from voidcompass.core import platform_support
from voidcompass.core.platform_support import default_screenshot_path, repaired_screenshot_path
from voidcompass.core.screenshot_handler import ScreenshotHandler
from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin


def bitmap(path):
    from PIL import Image
    Image.new("RGB", (64, 36), (20, 60, 120)).save(path, "BMP")
    return path


class FolderTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        self.legacy = Path(self.home.name, "Pictures", "Frontier Developments", "Elite Dangerous")
        self.onedrive_pictures = Path(self.home.name, "OneDrive", "Pictures")
        self.onedrive = self.onedrive_pictures / "Frontier Developments" / "Elite Dangerous"

    def repaired(self, configured):
        return repaired_screenshot_path(str(configured), home=self.home.name, pictures=str(self.onedrive_pictures))

    def test_windows_says_where_pictures_is(self):
        if os.name != "nt":
            self.skipTest("Windows only")
        found = platform_support.windows_pictures_folder()
        self.assertTrue(found and os.path.isabs(found))
        with patch.object(platform_support, "windows_pictures_folder", return_value=r"C:\Users\Cmdr\OneDrive\Pictures"):
            self.assertEqual(default_screenshot_path(),
                             r"C:\Users\Cmdr\OneDrive\Pictures\Frontier Developments\Elite Dangerous")

    def test_the_old_guess_moves_to_onedrive(self):
        self.onedrive.mkdir(parents=True)
        self.assertEqual(self.repaired(self.legacy), str(self.onedrive), "the guessed folder isn't there")
        self.legacy.mkdir(parents=True)
        self.assertEqual(self.repaired(self.legacy), str(self.onedrive),
                         "there but only the old guess: Elite saves to OneDrive's Pictures")
        self.assertEqual(self.repaired(""), str(self.onedrive))

    def test_a_folder_you_chose_stays(self):
        self.onedrive.mkdir(parents=True)
        chosen = Path(self.home.name, "Shots")
        chosen.mkdir()
        self.assertEqual(self.repaired(chosen), str(chosen))
        # Nowhere better to go: what was set stays.
        self.onedrive.rmdir()
        self.assertEqual(self.repaired(self.legacy), str(self.legacy))

    def test_the_app_repairs_and_saves_it(self):
        self.onedrive.mkdir(parents=True)

        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        saved = []
        deck.config = {"screenshots_path": str(self.legacy), "journal_path": ""}
        deck._persist_config = lambda: saved.append(dict(deck.config))
        deck.log = lambda message: None
        with patch("voidcompass.dashboard.dashboard_keepsakes_mixin.repaired_screenshot_path",
                   side_effect=lambda configured, journal: self.repaired(configured)):
            self.assertTrue(deck._repair_screenshot_path())
            self.assertFalse(deck._repair_screenshot_path(), "once")
        self.assertEqual(deck.config["screenshots_path"], str(self.onedrive))
        self.assertEqual(len(saved), 1)


class ConverterTests(unittest.TestCase):
    def handler(self, folder):
        handler = ScreenshotHandler({"screenshots_enabled": False, "screenshots_path": folder}, lambda: "Sol")
        self.addCleanup(handler.stop)
        return handler

    def test_a_locked_bmp_is_converted_once(self):
        with tempfile.TemporaryDirectory() as folder:
            bmp = bitmap(os.path.join(folder, "Screenshot_0001.bmp"))
            handler = self.handler(folder)
            real_remove = os.remove
            locked = {"tries": 3}

            def remove(path):
                if path == bmp and locked["tries"]:
                    locked["tries"] -= 1
                    raise PermissionError("OneDrive is uploading it")
                real_remove(path)
            with patch("voidcompass.core.screenshot_handler.os.remove", side_effect=remove):
                for _ in range(5):
                    handler.process_folder(folder)
            names = sorted(os.listdir(folder))
            self.assertEqual(len([name for name in names if name.endswith(".png")]), 1, names)
            self.assertNotIn("Screenshot_0001.bmp", names, "deleted once the lock let go")

    def test_a_save_cut_short_leaves_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            bitmap(os.path.join(folder, "Screenshot_0002.bmp"))
            handler = self.handler(folder)
            with patch("voidcompass.core.screenshot_handler.os.replace", side_effect=PermissionError("locked")):
                handler.process_folder(folder)
            self.assertEqual(sorted(os.listdir(folder)), ["Screenshot_0002.bmp"], "no half PNG, no .part")
            handler.process_folder(folder)
            self.assertEqual(len([name for name in os.listdir(folder) if name.endswith(".png")]), 1)

    def test_cloud_only_files_are_left_in_the_cloud(self):
        with tempfile.TemporaryDirectory() as folder:
            bitmap(os.path.join(folder, "Screenshot_0003.bmp"))
            handler = self.handler(folder)
            with patch("voidcompass.core.screenshot_handler.os.stat",
                       return_value=SimpleNamespace(st_file_attributes=0x400000)):
                handler.process_folder(folder)
            self.assertEqual(os.listdir(folder), ["Screenshot_0003.bmp"], "not downloaded to be converted")


if __name__ == "__main__":
    unittest.main()
