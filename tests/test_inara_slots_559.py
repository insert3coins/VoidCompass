"""5.5.9: each piece of Inara state has a slot of its own. The game rewrites
ShipLocker every time you board or disembark, and its empty categories' resets
went to Inara each time (200 of a session's 263 events); one locker category
could replace another still waiting; and a partial copy (LoadGame's ship, a
Rank without its Progress) went again after a restart."""

import json
from pathlib import Path

from tests.test_inara_restart_557 import InaraHarness, stamp


def locker(**groups):
    return {"timestamp": stamp(), "event": "ShipLocker",
            **{group: groups.get(group, []) for group in ("Items", "Components", "Consumables", "Data")}}


class SlotTests(InaraHarness):
    def sent_data(self, session):
        rows = []
        for call in session.post.call_args_list:
            rows += [(row["eventName"], row["eventData"]) for row in call.kwargs["json"]["events"]]
        return rows

    def test_the_locker_rewritten_again_and_again_goes_once(self):
        up, session = self.uploader()
        for _ in range(5):
            up.observe("ShipLocker", locker(Consumables=[{"Name": "healthpack", "Count": 87}]))
            up.flush(force=True)
        names = self.sent(session)
        self.assertEqual(names.count("resetCommanderInventory"), 3, "Items, Components and Data, once each")
        self.assertEqual(names.count("setCommanderInventory"), 1)

    def test_one_category_never_replaces_another(self):
        up, session = self.uploader()
        up.observe("ShipLocker", locker(Components=[{"Name": "graphene", "Count": 4}],
                                        Consumables=[{"Name": "healthpack", "Count": 87}]))
        up.flush(force=True)
        kinds = {data[0]["itemType"] for name, data in self.sent_data(session) if name == "setCommanderInventory"}
        self.assertEqual(kinds, {"Component", "Consumable"})

    def test_a_set_and_its_reset_share_a_slot(self):
        up, session = self.uploader()
        up.observe("ShipLocker", locker(Data=[{"Name": "geneticsample", "Count": 1}]))
        up.observe("ShipLocker", locker())  # sold it before the batch went
        up.flush(force=True)
        data = [(name, payload) for name, payload in self.sent_data(session)
                if (payload[0] if isinstance(payload, list) else payload).get("itemType") == "Data"]
        self.assertEqual(data, [("resetCommanderInventory", {"itemType": "Data", "itemLocation": "ShipLocker"})],
                         "only the latest of the two")

    def test_partial_copies_dont_go_again_after_a_restart(self):
        def session_events(up, startup):
            up.observe("LoadGame", {"timestamp": stamp(), "Commander": "insert3coins", "Credits": 5, "Loan": 0,
                                    "Ship": "Explorer_NX", "ShipID": 126, "ShipName": "ISS Relaint"}, startup=startup)
            up.observe("Rank", {"timestamp": stamp(), "Combat": 6, "Trade": 13}, startup=startup)
            up.observe("Progress", {"timestamp": stamp(), "Combat": 94, "Trade": 100}, startup=startup)
            up.observe("Loadout", {"timestamp": stamp(), "Ship": "explorer_nx", "ShipID": 126, "ShipName": "ISS Relaint",
                                   "CargoCapacity": 43, "Modules": []}, startup=startup)
            up.flush(force=True)
        first, _session = self.uploader()
        session_events(first, startup=False)
        first.stop()
        again, session = self.uploader()
        session_events(again, startup=True)
        self.assertEqual(self.sent(session), [], "LoadGame's ship and a Rank without its Progress wait, then aren't needed")

    def test_an_older_memory_file_is_set_aside(self):
        Path(self.sent_path).write_text(json.dumps({"state": {"setCommanderCredits": '{"commanderCredits": 5}'}}),
                                        encoding="utf-8")
        up, session = self.uploader()
        up.observe("LoadGame", {"timestamp": stamp(), "Commander": "insert3coins", "Credits": 5, "Loan": 0}, startup=True)
        up.flush(force=True)
        self.assertIn("setCommanderCredits", self.sent(session), "the old layout can't be trusted: sent once more")
        saved = json.loads(Path(self.sent_path).read_text(encoding="utf-8"))
        self.assertEqual(saved["version"], 2)
