"""A commander renamed in game keeps their Frontier ID, so they keep
their profile (history, settings, theme) under the new name, and their
journals from before the rename still count as theirs."""

import unittest

from voidcompass.core.config import commander_profile_key, rename_commander_profile, resolve_commander_profile
from voidcompass.exploration.captains_log import CaptainsLog
from voidcompass.exploration.travel_history import commander_matches

OLD_KEY = commander_profile_key("Old Name", "F777")


def config_with_profile(**profile):
    return {"active_commander_profile": OLD_KEY, "active_commander_name": "Old Name", "edsm_cmdr_name": "Old Name",
            "commander_profiles": {OLD_KEY: {"commander_name": "Old Name", "fid": "F777", "edsm_cmdr_name": "Old Name", **profile}}}


class ResolveTests(unittest.TestCase):
    def test_a_renamed_commander_keeps_their_profile(self):
        self.assertEqual(resolve_commander_profile(config_with_profile(), "New Name", "F777"), (OLD_KEY, "Old Name"))
        self.assertEqual(resolve_commander_profile(config_with_profile(), "old name", "f777"), (OLD_KEY, None),
                         "a change of case is not a rename")

    def test_other_commanders_and_unknown_fids(self):
        config = config_with_profile()
        self.assertEqual(resolve_commander_profile(config, "Alt", "F999"), (commander_profile_key("Alt", "F999"), None))
        self.assertEqual(resolve_commander_profile(config, "New Name", ""), (commander_profile_key("New Name", ""), None),
                         "without an FID only the name can tell")
        self.assertEqual(resolve_commander_profile({}, "New Name", "F777"), (commander_profile_key("New Name", "F777"), None))

    def test_a_profile_already_under_the_new_name_wins(self):
        config = config_with_profile()
        new_key = commander_profile_key("New Name", "F777")
        config["commander_profiles"][new_key] = {"commander_name": "New Name", "fid": "F777"}
        self.assertEqual(resolve_commander_profile(config, "New Name", "F777"), (new_key, None))

    def test_rename_carries_the_edsm_name_unless_it_was_custom(self):
        config = config_with_profile()
        rename_commander_profile(config, OLD_KEY, "New Name", "Old Name")
        profile = config["commander_profiles"][OLD_KEY]
        self.assertEqual((profile["commander_name"], profile["edsm_cmdr_name"], config["edsm_cmdr_name"]),
                         ("New Name", "New Name", "New Name"))
        self.assertEqual(profile["previous_names"], ["Old Name"])
        config = config_with_profile(edsm_cmdr_name="EDSM Handle")
        config["edsm_cmdr_name"] = "EDSM Handle"
        rename_commander_profile(config, OLD_KEY, "New Name", "Old Name")
        self.assertEqual(config["commander_profiles"][OLD_KEY]["edsm_cmdr_name"], "EDSM Handle")


class HistoryMatchingTests(unittest.TestCase):
    def test_journals_from_before_the_rename_still_count(self):
        old_event = {"event": "LoadGame", "Commander": "Old Name", "FID": "F777"}
        self.assertTrue(commander_matches(old_event, "New Name", "F777"))
        self.assertTrue(CaptainsLog._commander_matches(old_event, "New Name", "F777"))
        self.assertFalse(CaptainsLog._commander_matches({"event": "LoadGame", "Commander": "New Name", "FID": "F999"}, "New Name", "F777"),
                         "another account with the same name is not this commander")
        self.assertTrue(CaptainsLog._commander_matches({"event": "LoadGame", "Commander": "New Name"}, "New Name", "F777"))

    def test_carrier_history_follows_the_frontier_id(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from voidcompass.services import carrier_tracker

        import threading

        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "Journal.2026-09-01T100000.01.log").write_text("\n".join(json.dumps(row) for row in (
                {"event": "LoadGame", "Commander": "Old Name", "FID": "F777"},
                {"event": "CarrierStats", "CarrierID": 1, "Callsign": "ABC-123", "Name": "MINE"},
                {"event": "LoadGame", "Commander": "New Name", "FID": "F999"},
                {"event": "CarrierStats", "CarrierID": 2, "Callsign": "XYZ-999", "Name": "SOMEONE ELSE"},
            )), encoding="utf-8")
            tracker = carrier_tracker.CarrierTracker.__new__(carrier_tracker.CarrierTracker)
            tracker._profile_generation = 0
            tracker._profile_lock = threading.RLock()
            tracker._carriers = {}
            tracker.on_updated = tracker.on_panel_updated = tracker.on_status_changed = None
            replayed = []
            with patch.object(carrier_tracker.CarrierTracker, "_process_event_unlocked", lambda self, raw: replayed.append(raw)), \
                 patch.object(carrier_tracker.CarrierTracker, "_restore_active_carrier", lambda self: None), \
                 patch.object(carrier_tracker.CarrierTracker, "save_state", lambda self: None):
                tracker.scan_journal_history(folder, commander="New Name", fid="F777")
        self.assertEqual([raw["CarrierID"] for raw in replayed], [1])


if __name__ == "__main__":
    unittest.main()
