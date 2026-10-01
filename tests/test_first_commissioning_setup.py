"""First commissioning setup (5.5.1.1): the journal probe, the runtime's
probe and theme handling, and the setup.js page wiring."""

import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from voidcompass.core import themes
from voidcompass.core.onboarding import probe_journal_folder
from voidcompass.dashboard.html_dashboard_runtime import HtmlDashboardRuntime

ROOT = Path(__file__).resolve().parents[1]


def _journal(folder, name, events):
    (Path(folder) / name).write_text("\n".join(json.dumps(row) for row in events) + "\n", encoding="utf-8")


class JournalProbeTests(unittest.TestCase):
    def test_a_journal_folder_reports_its_span_commander_ship_and_system(self):
        with tempfile.TemporaryDirectory() as folder:
            _journal(folder, "Journal.200910101500.01.log", [{"event": "Fileheader"}])
            _journal(folder, "Journal.2026-09-30T081500.01.log", [
                {"event": "LoadGame", "Commander": "Jameson", "Ship": "krait_light", "Ship_Localised": "Krait Phantom",
                 "ShipName": "Lantern", "GameMode": "Solo"},
                {"event": "FSDJump", "StarSystem": "Shinrarta Dezhra"},
                {"event": "FSDJump", "StarSystem": "Colonia"},
            ])
            (Path(folder) / "Status.json").write_text("{}", encoding="utf-8")
            (Path(folder) / "notes.txt").write_text("not a journal", encoding="utf-8")
            probe = probe_journal_folder(folder)
        self.assertEqual(probe["status"], "ok")
        self.assertFalse(probe["auto"])
        self.assertEqual(probe["journals"], 2)
        self.assertEqual((probe["first"], probe["latest"]), ("2020-09-10", "2026-09-30"))
        self.assertEqual(probe["commander"], "Jameson")
        self.assertEqual((probe["ship"], probe["ship_name"], probe["mode"]), ("Krait Phantom", "Lantern", "Solo"))
        self.assertEqual(probe["system"], "Colonia", "the last system is the newest jump")
        self.assertTrue(probe["live_status"])

    def test_empty_missing_and_relative_folders_say_what_is_wrong(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(probe_journal_folder(folder)["status"], "empty")
            self.assertEqual(probe_journal_folder(str(Path(folder) / "nope"))["status"], "missing")
        relative = probe_journal_folder("Saved Games/Elite")
        self.assertEqual(relative["status"], "invalid")
        self.assertIn("full folder path", relative["message"])


class CommissioningRuntimeTests(unittest.TestCase):
    def runtime(self):
        runtime = HtmlDashboardRuntime.__new__(HtmlDashboardRuntime)
        runtime.app_version = "5.5.1.1"
        runtime._latest_app_model = {"theme": {"name": "Void Cyan", "palette": {}, "available": []}}
        runtime._boot = {"active": True, "status": "", "detail": "", "progress": 0.0}
        runtime._commissioning_session = 0
        runtime._disposed = False
        runtime.server = SimpleNamespace(update_host_state=Mock(), publish=Mock())
        runtime.root = SimpleNamespace(call_later=lambda _ms, callback, *args: callback(*args))
        runtime._schedule_command_pump = Mock()
        return runtime

    def wait_for_probe(self, runtime):
        for thread in threading.enumerate():
            if thread.name == "setup-journal-probe":
                thread.join(5)

    def test_commissioning_offers_every_theme_and_probes_the_journal_folder(self):
        runtime = self.runtime()
        with tempfile.TemporaryDirectory() as folder:
            _journal(folder, "Journal.2026-09-30T081500.01.log", [{"event": "Commander", "Name": "Jameson", "FID": "F1"}])
            runtime.begin_commissioning({"journal_path": folder, "ui_theme_name": "Ice"}, Mock())
            self.wait_for_probe(runtime)
            state = runtime._onboarding
            self.assertEqual(state["theme"], "Ice")
            self.assertEqual(set(state["themes"]), set(themes.BUILTIN_THEMES))
            self.assertEqual(state["probe"]["commander"], "Jameson")
            self.assertFalse(state["probing"])
            # A new path from the page is checked again.
            runtime._handle_commissioning_command({"action": "onboarding_probe", "journal_path": str(Path(folder) / "missing")})
            self.wait_for_probe(runtime)
            self.assertEqual(runtime._onboarding["probe"]["status"], "missing")

    def test_submit_saves_a_known_theme_and_the_boot_screen_wears_it(self):
        runtime = self.runtime()
        callback = Mock()
        runtime.begin_commissioning({}, callback)
        self.wait_for_probe(runtime)
        runtime._handle_commissioning_command({
            "action": "onboarding_submit", "journal_path": "", "ui_theme_name": "Elite Orange",
            "adaptive_command_enabled": True, "overlay_enabled": False, "overlay_mouse_passthrough": True,
        })
        values = callback.call_args.args[0]
        self.assertEqual(values["ui_theme_name"], "Elite Orange")
        self.assertFalse(values["overlay_enabled"])
        self.assertTrue(values["onboarding_complete"])
        self.assertEqual(runtime._latest_app_model["theme"]["palette"], themes.BUILTIN_THEMES["Elite Orange"])

    def test_an_unknown_theme_is_not_saved(self):
        runtime = self.runtime()
        callback = Mock()
        runtime.begin_commissioning({}, callback)
        self.wait_for_probe(runtime)
        runtime._handle_commissioning_command({"action": "onboarding_submit", "journal_path": "", "ui_theme_name": "Not A Theme"})
        self.assertNotIn("ui_theme_name", callback.call_args.args[0])


class SetupPageWiringTests(unittest.TestCase):
    def test_setup_is_its_own_module_and_stylesheet(self):
        web = ROOT / "web" / "dashboard"
        app = (web / "app.js").read_text(encoding="utf-8")
        index = (web / "index.html").read_text(encoding="utf-8")
        setup = (web / "setup.js").read_text(encoding="utf-8")
        self.assertIn('from "./setup.js"', app)
        self.assertIn('href="setup.css"', index)
        self.assertIn("renderSetup(onboarding, SETUP_UI)", app)
        for step in ("welcome", "journal", "cockpit", "launch"):
            self.assertIn(f'data-step="{step}"', index)
            self.assertIn(f'data-setup-go="{step}"', index)
        for action in ("onboarding_probe", "onboarding_submit", "onboarding_cancel"):
            self.assertIn(f'"{action}"', setup)
        # The old single-form styles are gone.
        self.assertNotIn("commission-manifest", (web / "styles.css").read_text(encoding="utf-8"))
        self.assertNotIn("commission-manifest", index)


if __name__ == "__main__":
    unittest.main()
