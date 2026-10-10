"""5.5.3.4: the command deck froze for a whole session. The journal replay ran
past the startup timeout, so startup went live without it; the replay's own
progress reports kept arriving and turned the boot screen back on. The deck
refuses a booting snapshot once it has gone live ("Stale boot snapshot
persisted after handoff" in the dashboard host log), so it never updated
again. Once boot has finished, only setup may bring it back."""

import unittest
from unittest.mock import Mock

from voidcompass.dashboard.html_dashboard_runtime import HtmlDashboardRuntime


def runtime():
    rt = HtmlDashboardRuntime.__new__(HtmlDashboardRuntime)
    rt._boot = {"active": True, "status": "", "detail": "", "progress": 0.0}
    rt._onboarding = {"active": False, "session": 0}
    rt._latest_app_model = {}
    rt.app_version = "test"
    rt.server = Mock()
    rt._disposed = False
    return rt


def published(rt):
    return rt.server.publish.call_args.args[0]


class BootStaysFinishedTests(unittest.TestCase):
    def test_late_progress_after_the_handoff_keeps_the_deck_live(self):
        rt = runtime()
        rt.set_runtime_status("RESTORING JOURNAL", "1,200 events", .5, 1200)
        self.assertTrue(published(rt)["boot"]["active"])
        # 17:04:39 the journal timeout went live without the replay; 17:04:40 boot stopped.
        rt.set_runtime_status("JOURNAL LINK OFFLINE", "No live tail was available", .9)
        rt.stop()
        self.assertFalse(published(rt)["boot"]["active"])
        # The replay carried on and reported in, and reached the live tail at 17:04:46.
        rt.set_runtime_status("RESTORING JOURNAL", "2,400 events", .7, 2400)
        rt.set_runtime_status("LIVE JOURNAL TAIL REACHED", "2,900 recent events restored", .88, 2900)
        self.assertFalse(rt._boot["active"], "boot stays finished")
        self.assertFalse(published(rt)["boot"]["active"])
        rt.server.update_host_state.assert_called_with({"boot_active": False, "onboarding_active": False})

    def test_setup_may_show_the_boot_screen_again(self):
        rt = runtime()
        rt.stop()
        rt._commissioning_session = 0
        rt._probe_journals = Mock()
        rt._schedule_command_pump = Mock()
        rt.begin_commissioning({"journal_path": ""}, lambda values: None)
        self.assertTrue(rt._boot["active"])
        rt.set_runtime_status("COMMISSIONING", "", .2)
        self.assertEqual(rt._boot["status"], "COMMISSIONING", "setup's own progress still shows")


if __name__ == "__main__":
    unittest.main()
