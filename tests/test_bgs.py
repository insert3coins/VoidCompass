"""5.5.2.4 BGS: faction snapshots and BGS work from the journal, the record,
alerts, conflicts, per-tick activity and its report, EDSM lookups, ticks, the
history import and the BGS tab. Events are shaped like real journal events."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from urllib.parse import urlsplit

from voidcompass.bgs import edsm as bgs_edsm
from voidcompass.bgs import views
from voidcompass.bgs.importer import import_journals
from voidcompass.bgs.journal import BgsJournal, event_uid
from voidcompass.bgs.store import BgsStore
from voidcompass.bgs.ticks import tick_for
from voidcompass.core import config as config_module

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
LOS = 11887629902418


def arrival(at="2026-09-26T23:03:06Z", influences=(0.638362, 0.180819, 0.180819), controlling="Ukraine Colonist Alliance",
            conflicts=True, address=LOS, name="Los", event="FSDJump", **extra):
    names = ["Ukraine Colonist Alliance", "ICU Colonial Corps", "Los Services Ltd"]
    influences = list(influences) + [0.0] * (3 - len(influences))
    count = sum(1 for value in influences if value)
    factions = [
        {"Name": names[0], "FactionState": "Boom", "Government": "Corporate", "Influence": influences[0], "Allegiance": "Independent",
         "Happiness": "$Faction_HappinessBand2;", "Happiness_Localised": "Happy", "MyReputation": 0.0,
         "PendingStates": [{"State": "Expansion", "Trend": 0}], "RecoveringStates": [{"State": "Terrorism", "Trend": 0}],
         "ActiveStates": [{"State": "Boom"}]},
        {"Name": names[1], "FactionState": "Election", "Government": "Communism", "Influence": influences[1], "Allegiance": "Independent",
         "MyReputation": 0.73, "ActiveStates": [{"State": "CivilUnrest"}, {"State": "Election"}]},
        {"Name": names[2], "FactionState": "Election", "Government": "Democracy", "Influence": influences[2], "Allegiance": "Independent",
         "ActiveStates": [{"State": "Election"}]},
    ][:count]
    raw = {"timestamp": at, "event": event, "StarSystem": name, "SystemAddress": address, "Population": 3304936,
           "SystemAllegiance": "Independent", "SystemEconomy_Localised": "Service", "SystemGovernment_Localised": "Corporate",
           "SystemSecurity_Localised": "Medium Security", "Factions": factions, "SystemFaction": {"Name": controlling}, **extra}
    if conflicts:
        raw["Conflicts"] = [{"WarType": "election", "Status": "active",
                             "Faction1": {"Name": names[1], "Stake": "Dovzhenko's Lodgings", "WonDays": 1},
                             "Faction2": {"Name": names[2], "Stake": "Stoker Station", "WonDays": 2}}]
    return raw


def docked(at="2026-09-26T23:10:00Z", faction="Ukraine Colonist Alliance", station_type="Coriolis"):
    return {"timestamp": at, "event": "Docked", "StationName": "Stoker Station", "StationType": station_type,
            "StarSystem": "Los", "SystemAddress": LOS, "StationFaction": {"Name": faction}, "MarketID": 1}


def play(*events, reader=None):
    reader = reader or BgsJournal()
    records = []
    for raw in events:
        records.extend(reader.observe(raw))
    return records, reader


def activities(records):
    return [value for kind, value in records if kind in ("activity", "activity_upsert")]


class JournalTests(unittest.TestCase):
    def test_arrival_snapshot(self):
        records, _ = play(arrival())
        kind, snap = records[0]
        self.assertEqual(kind, "snapshot")
        self.assertEqual((snap["system"], snap["controlling"], snap["population"]), ("Los", "Ukraine Colonist Alliance", 3304936))
        first = snap["factions"][0]
        self.assertEqual((first["state"], first["active"], first["pending"][0]["state"], first["recovering"][0]["state"]),
                         ("Boom", ["Boom"], "Expansion", "Terrorism"))
        self.assertEqual(snap["conflicts"][0]["sides"][1], {"name": "Los Services Ltd", "stake": "Stoker Station", "won_days": 2})
        self.assertEqual(play({"timestamp": "2026-09-26T23:00:00Z", "event": "FSDJump", "StarSystem": "Nowhere", "SystemAddress": 5})[0], [],
                         "an unpopulated system has nothing to record")

    def test_missions(self):
        records, reader = play(arrival(), docked(),
                               {"timestamp": "2026-09-26T23:11:00Z", "event": "MissionAccepted", "MissionID": 7, "Faction": "ICU Colonial Corps",
                                "Name": "Mission_Courier_Elections_name"},
                               {"timestamp": "2026-09-26T23:30:00Z", "event": "MissionCompleted", "MissionID": 7, "Faction": "ICU Colonial Corps",
                                "Name": "Mission_Courier_Elections_name", "LocalisedName": "Courier",
                                "FactionEffects": [
                                    {"Faction": "ICU Colonial Corps", "Influence": [{"SystemAddress": LOS, "Trend": "UpGood", "Influence": "+++"}]},
                                    {"Faction": "Los Services Ltd", "Influence": [{"SystemAddress": LOS, "Trend": "DownBad", "Influence": "+"}]}]})
        work = activities(records)
        self.assertEqual([(row["kind"], row["faction"], row["amount"]) for row in work],
                         [("inf", "ICU Colonial Corps", 3), ("inf_secondary", "Los Services Ltd", -1)])
        # An election mission that reports no INF counts +1 (BGS-Tally's rule).
        records, _ = play({"timestamp": "2026-09-26T23:40:00Z", "event": "MissionAccepted", "MissionID": 8, "Faction": "ICU Colonial Corps",
                           "Name": "Mission_Courier_Elections_name"},
                          {"timestamp": "2026-09-26T23:50:00Z", "event": "MissionCompleted", "MissionID": 8, "Faction": "ICU Colonial Corps",
                           "Name": "Mission_Courier_Elections_name", "FactionEffects": [{"Faction": "ICU Colonial Corps", "Influence": []}]},
                          reader=reader)
        self.assertEqual([(row["kind"], row["amount"]) for row in activities(records)], [("inf", 1)])
        records, _ = play({"timestamp": "2026-09-27T00:00:00Z", "event": "MissionAccepted", "MissionID": 9, "Faction": "Los Services Ltd", "Name": "Mission_Delivery_name"},
                          {"timestamp": "2026-09-27T01:00:00Z", "event": "MissionFailed", "MissionID": 9, "Name": "Mission_Delivery_name"}, reader=reader)
        self.assertEqual([(row["kind"], row["faction"]) for row in activities(records)], [("mission_failed", "Los Services Ltd")])

    def test_vouchers_data_trade_and_rescue(self):
        events = [arrival(), docked(station_type="FleetCarrier"),
                  {"timestamp": "2026-09-26T23:12:00Z", "event": "RedeemVoucher", "Type": "bounty", "Amount": 100000,
                   "Factions": [{"Faction": "ICU Colonial Corps", "Amount": 100000}, {"Faction": "Elsewhere Inc", "Amount": 5}]},
                  docked(at="2026-09-26T23:20:00Z"),
                  {"timestamp": "2026-09-26T23:21:00Z", "event": "RedeemVoucher", "Type": "CombatBond", "Amount": 50000, "Faction": "Los Services Ltd"},
                  {"timestamp": "2026-09-26T23:22:00Z", "event": "MultiSellExplorationData", "BaseValue": 1000, "Bonus": 500, "TotalEarnings": 1200},
                  {"timestamp": "2026-09-26T23:23:00Z", "event": "SellOrganicData", "BioData": [{"Value": 100, "Bonus": 50}, {"Value": 10, "Bonus": 0}]},
                  {"timestamp": "2026-09-26T23:24:00Z", "event": "MarketSell", "Type": "gold", "Count": 10, "SellPrice": 50, "TotalSale": 500, "AvgPricePaid": 30},
                  {"timestamp": "2026-09-26T23:25:00Z", "event": "MarketSell", "Type": "silver", "Count": 10, "TotalSale": 100, "AvgPricePaid": 30},
                  {"timestamp": "2026-09-26T23:26:00Z", "event": "MarketSell", "Type": "slaves", "Count": 1, "TotalSale": 900, "AvgPricePaid": 0, "BlackMarket": True},
                  {"timestamp": "2026-09-26T23:27:00Z", "event": "SearchAndRescue", "Name": "occupiedcryopod", "Count": 2, "Reward": 9000}]
        work = {row["kind"]: row for row in activities(play(*events)[0])}
        self.assertEqual(work["bounties"]["amount"], 50000, "half at a fleet carrier, and only factions here")
        self.assertEqual(work["bonds"]["faction"], "Los Services Ltd")
        self.assertEqual(work["cartography"]["amount"], 1500, "never less than base plus bonus")
        self.assertEqual(work["exobiology"]["amount"], 160)
        self.assertEqual((work["trade_profit"]["amount"], work["trade_loss"]["amount"], work["black_market"]["amount"]), (200, -200, 900))
        self.assertEqual((work["search_rescue"]["count"], work["search_rescue"]["faction"]), (2, "Ukraine Colonist Alliance"))

    def test_conflict_zones(self):
        drop = {"timestamp": "2026-09-26T23:30:00Z", "event": "SupercruiseDestinationDrop", "Type": "$Warzone_PointRace_High:#index=1;"}
        bond = lambda at, reward=40000: {"timestamp": at, "event": "FactionKillBond", "AwardingFaction": "ICU Colonial Corps",
                                         "VictimFaction": "Los Services Ltd", "Reward": reward}
        records, reader = play(arrival(), drop, bond("2026-09-26T23:31:00Z"), bond("2026-09-26T23:32:00Z"))
        self.assertEqual([(row["kind"], row["detail"]) for row in activities(records)], [("space_cz", "h")], "one zone, counted once")
        settle = {"timestamp": "2026-09-26T23:40:00Z", "event": "ApproachSettlement", "Name": "Hobbs Landing"}
        records, _ = play(settle, bond("2026-09-26T23:41:00Z", 3000), bond("2026-09-26T23:42:00Z", 45000), reader=reader)
        work = activities(records)
        self.assertEqual([row["detail"] for row in work], ["l", "h"])
        self.assertEqual(work[0]["uid"], work[1]["uid"], "a bigger bond re-sizes the same ground zone")
        self.assertEqual(play(bond("2026-09-26T23:59:00Z"), reader=reader)[0], [], "too long after: not in a zone")

    def test_murders_go_to_the_ship_faction(self):
        records, _ = play(arrival(), {"timestamp": "2026-09-26T23:30:00Z", "event": "ShipTargeted", "TargetLocked": True,
                                      "PilotName": "$npc_name_decorate:#name=Bob;", "PilotName_Localised": "Bob", "Faction": "Los Services Ltd"},
                          {"timestamp": "2026-09-26T23:31:00Z", "event": "CommitCrime", "CrimeType": "murder", "Faction": "Ukraine Colonist Alliance", "Victim": "Bob"})
        self.assertEqual([(row["kind"], row["faction"]) for row in activities(records)], [("murder", "Los Services Ltd")])

    def test_ids_are_the_same_live_and_from_history(self):
        raw = arrival()
        self.assertEqual(event_uid(raw), event_uid(json.loads(json.dumps(raw))))


class StoreAndViewTests(unittest.TestCase):
    def store(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        store = BgsStore(os.path.join(folder.name, "bgs.db"))
        self.addCleanup(store.close)
        return store

    def test_record_and_picture(self):
        store = self.store()
        store.apply(play(arrival(at="2026-09-25T20:00:00Z", influences=(0.60, 0.20, 0.20)))[0])
        store.apply(play(arrival(influences=(0.55, 0.30, 0.15)))[0])
        store.apply(play(arrival(influences=(0.55, 0.30, 0.15)))[0])  # same event again: one visit
        self.assertEqual(store.query("SELECT visits FROM systems")[0]["visits"], 2)
        picture = views.system_picture(store, LOS, tracked={"ICU Colonial Corps"})
        rows = {row["name"]: row for row in picture["factions"]}
        self.assertAlmostEqual(rows["ICU Colonial Corps"]["delta"], 0.10)
        self.assertTrue(rows["ICU Colonial Corps"]["tracked"])
        # A faction that left is gone from the system's list.
        store.apply(play(arrival(at="2026-09-27T23:00:00Z", influences=(0.7, 0.3)))[0])
        self.assertEqual(len(store.query("SELECT * FROM presence WHERE system_address = ?", (LOS,))), 2)

    def test_alerts(self):
        store = self.store()
        store.apply(play(arrival(at="2026-09-25T20:00:00Z", influences=(0.50, 0.30, 0.20)))[0])
        store.apply(play(arrival(influences=(0.40, 0.38, 0.03), controlling="Ukraine Colonist Alliance"))[0])
        store.set_tracked("faction", "Ukraine Colonist Alliance", True)
        store.set_tracked("faction", "Los Services Ltd", True)
        texts = {(row["faction"], row["level"], row["text"].split(":")[0]) for row in views.alerts(store)}
        self.assertIn(("Los Services Ltd", "danger", "3.0% influence"), texts)
        self.assertIn(("Ukraine Colonist Alliance", "warn", "Influence fell 10.0 points since 2026-09-25 20"), texts)
        self.assertTrue(any(row["text"].startswith("Control at risk") for row in views.alerts(store)))
        self.assertTrue(any(row["text"] == "Expansion pending" and row["level"] == "info" for row in views.alerts(store)))
        self.assertTrue(any(row["text"] == "Election active" for row in views.alerts(store)))

    def test_activity_by_tick_and_report(self):
        store = self.store()
        store.apply(play(arrival(), docked(),
                         {"timestamp": "2026-09-26T23:22:00Z", "event": "SellExplorationData", "BaseValue": 2500000, "Bonus": 0, "TotalEarnings": 2500000},
                         {"timestamp": "2026-09-27T17:00:00Z", "event": "SellExplorationData", "BaseValue": 1000, "Bonus": 0, "TotalEarnings": 1000})[0])
        from datetime import datetime, timezone
        tick = datetime(2026, 9, 26, 17, 0, tzinfo=timezone.utc).timestamp()
        work = views.activity(store, None, [tick, tick + 86400])
        self.assertEqual([row["estimated"] for row in work["periods"]], [False, False])
        detail = views.activity(store, tick, [tick, tick + 86400])["detail"]
        self.assertEqual(detail["systems"][0]["factions"][0]["kinds"][0]["amount"], 2500000)
        self.assertIn("**Los**", detail["report"])
        self.assertIn("Ukraine Colonist Alliance: Cartographic data 2.5M", detail["report"])

    def test_history_breaks_where_a_faction_was_absent(self):
        import time as _time
        store = self.store()
        now = _time.time()
        store.add_edsm_points(LOS, [("Gone And Back", now - 5 * 86400, 0.2, "None"), ("Gone And Back", now - 4 * 86400, 0.0, ""),
                                    ("Gone And Back", now - 3 * 86400, 0.25, "Boom")])
        series = views.history(store, LOS)[0]
        self.assertEqual([row["influence"] for row in series["points"]], [0.2, None, 0.25])
        self.assertEqual(series["last"], 0.25)

    def test_conflicts_and_lists(self):
        store = self.store()
        store.apply(play(arrival())[0])
        store.set_tracked("faction", "Los Services Ltd", True)
        conflict = views.conflicts(store)[0]
        self.assertEqual((conflict["type"], conflict["tracked"]), ("election", True))
        rows, total = views.factions_list(store, "los")
        self.assertEqual(([row["name"] for row in rows], total), (["Los Services Ltd"], 1))
        systems, _ = views.systems_list(store, only="conflicts")
        self.assertEqual(systems[0]["system"], "Los")


class EdsmAndTickTests(unittest.TestCase):
    def test_edsm_conversion(self):
        data = {"id64": LOS, "name": "Los", "controllingFaction": {"name": "Ukraine Colonist Alliance", "allegiance": "Independent", "government": "Corporate"},
                "factions": [{"name": "Ukraine Colonist Alliance", "influence": 0.62475, "state": "Boom", "isPlayer": True, "lastUpdate": 1791075406,
                              "activeStates": [{"state": "Boom"}], "pendingStates": [], "recoveringStates": [{"state": "Civil war", "trend": 0}],
                              "influenceHistory": {"1783132330": 0.494929, "1783163673": 0.5}, "stateHistory": {"1783132330": "Pirate attack"}},
                             {"name": "Gone Corp", "influence": 0, "lastUpdate": 1}]}
        snap, points = bgs_edsm.from_edsm(data)
        self.assertEqual([row["name"] for row in snap["factions"]], ["Ukraine Colonist Alliance"])
        self.assertEqual(snap["factions"][0]["recovering"][0]["state"], "CivilWar")
        self.assertTrue(snap["factions"][0]["player"])
        self.assertEqual(points[0], ("Ukraine Colonist Alliance", 1783132330.0, 0.494929, "PirateAttack"))
        self.assertEqual(bgs_edsm.from_edsm({"id64": 1, "factions": []}), (None, []))

    def test_tick_estimates(self):
        known = [1000.0 + 86400 * 10]
        self.assertEqual(tick_for(1000.0 + 86400 * 10 + 50, known), (known[0], False))
        start, estimated = tick_for(1000.0 + 86400 * 3 + 50, known)
        self.assertEqual((start, estimated), (1000.0 + 86400 * 3, True))


class ImporterTests(unittest.TestCase):
    def test_reads_only_this_commander_and_only_once(self):
        with tempfile.TemporaryDirectory() as folder:
            journals = Path(folder) / "journals"
            journals.mkdir()
            rows = [{"timestamp": "2026-09-26T22:00:00Z", "event": "LoadGame", "Commander": "Old Name", "FID": "F1"}, arrival(),
                    {"timestamp": "2026-09-26T23:59:00Z", "event": "LoadGame", "Commander": "Alt", "FID": "F2"},
                    arrival(at="2026-09-27T00:30:00Z", address=99, name="Alt Home")]
            (journals / "Journal.2026-09-26T220000.01.log").write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            (journals / "Journal.2026-09-27T220000.01.log").write_text(json.dumps({"timestamp": "2026-09-27T22:00:00Z", "event": "Fileheader"}), encoding="utf-8")
            store = BgsStore(os.path.join(folder, "bgs.db"))
            self.assertEqual(import_journals(store, str(journals), "New Name", "F1"), 2)
            self.assertEqual([row["system"] for row in store.query("SELECT system FROM systems")], ["Los"], "the renamed commander's own, not the alt's")
            self.assertEqual(import_journals(store, str(journals), "New Name", "F1"), 1, "only the newest journal is read again")
            store.close()


class TabTests(unittest.TestCase):
    def deck(self, online=True):
        from voidcompass.dashboard.dashboard_bgs_mixin import DashboardBgsMixin
        from voidcompass.dashboard.html_bgs import HtmlBgsMixin

        class Deck(DashboardBgsMixin, HtmlBgsMixin):
            pass
        deck = Deck()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        deck.config = {"bgs_online_enabled": online}
        deck.bgs_store = BgsStore(os.path.join(folder.name, "bgs.db"))
        self.addCleanup(deck.bgs_store.close)
        deck.bgs_journal = BgsJournal()
        deck._bgs_generation = 1
        deck._bgs_import_state = {"running": False, "done": True}
        transient = {}
        deck._html_profile_transient = lambda key, default: transient.setdefault(key, default)
        deck._schedule_html_dashboard_publish = Mock()
        deck._html_copy_text = Mock(return_value=True)
        deck._ui_post = lambda callback, *args, key=None: callback(*args)
        deck.current_system_address = LOS
        deck.current_sys = "Los"
        deck.edsm = Mock()
        return deck

    def test_live_events_feed_the_record_and_the_tab(self):
        deck = self.deck()
        deck._html_dashboard_active_page = "bgs"
        for raw in (arrival(), docked(), {"timestamp": "2026-09-26T23:22:00Z", "event": "SellExplorationData", "TotalEarnings": 5000}):
            deck._bgs_observe(raw)
        data = deck._html_bgs_workspace()
        json.dumps(data)
        self.assertEqual(data["current"]["system"], "Los")
        self.assertTrue(data["this_tick"] is None or isinstance(data["this_tick"], dict))
        deck._handle_bgs_command("track_faction", {"name": "Los Services Ltd", "value": True})
        self.assertIn("Los Services Ltd", deck._html_bgs_workspace()["tracked_factions"])
        for view in ("factions", "systems", "conflicts", "activity", "states"):
            deck._handle_bgs_command("view", {"view": view})
            json.dumps(deck._html_bgs_workspace())
        deck._handle_bgs_command("faction", {"name": "Los Services Ltd"})
        self.assertEqual(deck._html_bgs_workspace()["faction"]["systems"][0]["system"], "Los")
        deck._handle_bgs_command("chart_days", {"days": 1})
        self.assertEqual(deck._bgs_ui()["chart_days"], 1, "a 24 hour range")
        deck._handle_bgs_command("chart_days", {"days": 2})
        self.assertEqual(deck._bgs_ui()["chart_days"], 90, "ranges the tab does not offer fall back")
        deck._handle_bgs_command("tick", {"start": ""})
        deck._handle_bgs_command("copy_report", {})
        deck._html_copy_text.assert_called_once()

    def test_lookup_any_system(self):
        deck = self.deck()
        reply = Mock()
        reply.json.return_value = {"id64": 42, "name": "Sol", "controllingFaction": {"name": "Mother Gaia"},
                                   "factions": [{"name": "Mother Gaia", "influence": 0.5, "state": "Boom", "lastUpdate": 1791000000,
                                                 "influenceHistory": {"1790000000": 0.4, "1791000000": 0.5}}]}
        deck.edsm._limited_get.return_value = reply
        import threading
        original = threading.Thread
        threading.Thread = lambda target, **kw: Mock(start=target)
        try:
            deck._handle_bgs_command("lookup", {"system": "Sol"})
        finally:
            threading.Thread = original
        data = deck._html_bgs_workspace()
        self.assertEqual((data["view"], data["system"]["system"], data["system"]["source"]), ("systems", "Sol", "edsm"))
        self.assertEqual(len(data["system"]["history"][0]["points"]), 2)
        self.assertNotIn("recheck", deck.edsm._limited_get.call_args.kwargs["params"], "a plain lookup may use EDSM's cache")
        offline = self.deck(online=False)
        offline._handle_bgs_command("lookup", {"system": "Sol"})
        self.assertIn("BGS online", offline._bgs_ui()["error"])
        offline.edsm._limited_get.assert_not_called()

    def test_refresh_reaches_edsm_and_says_what_changed(self):
        deck = self.deck()
        reply = Mock()
        edsm_reply = lambda ts: {"id64": 42, "name": "Sol", "controllingFaction": {"name": "Mother Gaia"},
                                 "factions": [{"name": "Mother Gaia", "influence": 0.5, "state": "Boom", "lastUpdate": ts,
                                               "influenceHistory": {str(ts): 0.5}}]}
        deck.edsm._limited_get.return_value = reply
        import threading
        original = threading.Thread
        threading.Thread = lambda target, **kw: Mock(start=target)
        try:
            def refresh(ts):
                reply.json.return_value = edsm_reply(ts)
                deck._handle_bgs_command("lookup", {"system": "Sol", "refresh": "1"})
                self.assertIn("recheck", deck.edsm._limited_get.call_args.kwargs["params"],
                              "a refresh gets past EDSM's day-long CDN cache")
                return deck._bgs_ui()["notice"]
            self.assertIn("Updated Sol from EDSM", refresh(1791000000))
            self.assertIn("nothing newer", refresh(1791000000), "the same report again is said, not silent")
            self.assertIn("Updated Sol", refresh(1791090000))
            deck.bgs_store.add_snapshot({**deck.bgs_store.snapshots(42)[-1], "ts": 1791200000.0, "source": "journal"})
            self.assertIn("older than your own visit", refresh(1791100000))
            self.assertEqual(deck._html_bgs_workspace()["system"]["source"], "journal", "a fresher visit is kept")
        finally:
            threading.Thread = original

    def test_registered(self):
        self.assertIn("bgs_online_enabled", config_module.PROFILE_BOOL_SETTINGS)
        deck = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-page="bgs"', deck)
        self.assertIn('href="bgs.css"', deck)
        script = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('settingGroup("BGS"', script)
        css = (WEB / "dashboard" / "bgs.css").read_text(encoding="utf-8")
        hexes = [line for line in css.splitlines() if "#" in line and "--bgs-s" not in line and not line.strip().startswith("#bgs-workspace")]
        self.assertEqual([line for line in hexes if __import__("re").search(r"#[0-9a-fA-F]{3,6}\b", line)], [],
                         "only the chart series palette is fixed colour")


class PageTests(unittest.TestCase):
    def test_every_view_renders(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Playwright is not installed")
        tab = TabTests()
        tab.addCleanup = self.addCleanup
        deck = tab.deck()
        for raw in (arrival(at="2026-09-20T20:00:00Z", influences=(0.6, 0.25, 0.15)), arrival(), docked(),
                    {"timestamp": "2026-09-26T23:22:00Z", "event": "SellExplorationData", "TotalEarnings": 5000}):
            deck._bgs_observe(raw)
        deck._handle_bgs_command("track_faction", {"name": "Los Services Ltd", "value": True})
        snapshots = {}
        for view, extra in (("overview", {}), ("factions", {"faction": "Los Services Ltd"}), ("systems", {"system": LOS}),
                            ("conflicts", {}), ("activity", {}), ("states", {})):
            deck._handle_bgs_command("view", {"view": view})
            if "faction" in extra:
                deck._handle_bgs_command("faction", {"name": extra["faction"]})
            if "system" in extra:
                deck._handle_bgs_command("system", {"address": extra["system"]})
                deck._handle_bgs_command("chart_days", {"days": 3650})
            snapshots[view] = json.loads(json.dumps(deck._html_bgs_workspace()))
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as exc:
                self.skipTest(f"Playwright Chromium is unavailable: {exc}")
            page = browser.new_page(viewport={"width": 1300, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def serve(route, _request=None):
                path = WEB / urlsplit(route.request.url).path.lstrip("/")
                if path.name == "blank.html":
                    route.fulfill(content_type="text/html", body="<!doctype html><section data-page-name='bgs'><div id='bgs-workspace'></div></section>")
                elif path.is_file():
                    route.fulfill(path=str(path), content_type="application/javascript" if path.suffix == ".js" else None)
                else:
                    route.fulfill(status=404, body="")
            page.route("http://bgs.test/**", serve)
            page.goto("http://bgs.test/blank.html")
            result = page.evaluate("""async (snapshots) => {
              const m = await import('/dashboard/bgs.js');
              const sent = [];
              const ui = {byId: (id) => document.getElementById(id), command: (...args) => { sent.push(args[1]); },
                          escapeHtml: (v) => String(v ?? '').replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)};
              const out = {};
              for (const [view, data] of Object.entries(snapshots)) {
                m.renderBgs(data, ui);
                out[view] = document.getElementById('bgs-workspace').innerText;
              }
              m.renderBgs(snapshots.systems, ui);
              out.lines = document.querySelectorAll('.bgs-chart .series').length;
              const svg = document.querySelector('.bgs-chart');
              const box = svg.getBoundingClientRect();
              svg.dispatchEvent(new MouseEvent('mousemove', {clientX: box.left + box.width * 0.4, clientY: box.top + 50, bubbles: true}));
              out.tooltip = document.querySelector('.bgs-tooltip').innerText;
              m.handleBgsClick({target: document.querySelector('[data-bgs-op="track_faction"]'), preventDefault() {}}, ui);
              const empty = {...snapshots.systems, system: {...snapshots.systems.system, chart_days: 1, history: []}};
              m.renderBgs(empty, ui);
              out.emptyRanges = [...document.querySelectorAll('.bgs-ranges button')].map((b) => b.textContent);
              out.emptyText = document.querySelector('.bgs-chart-head + .bgs-dim')?.textContent || '';
              out.sent = sent;
              return out;
            }""", snapshots)
            browser.close()
        self.assertEqual(errors, [])
        self.assertIn("YOU ARE IN", result["overview"])
        self.assertIn("ALERTS FOR WHAT YOU TRACK", result["overview"])
        self.assertIn("Los Services Ltd", result["factions"])
        self.assertIn("INFLUENCE OVER TIME", result["systems"])
        self.assertIn("DAYS WON", result["conflicts"])
        self.assertIn("COPY DISCORD REPORT", result["activity"])
        self.assertIn("Civil unrest", result["states"])
        self.assertEqual(result["lines"], 3)
        self.assertIn("%", result["tooltip"])
        self.assertEqual(result["sent"][-1]["operation"], "track_faction")
        self.assertEqual(result["emptyRanges"], ["24H", "7D", "30D", "90D", "1Y", "ALL"], "the ranges stay when there is nothing to chart")
        self.assertIn("last 24 hours", result["emptyText"])


if __name__ == "__main__":
    unittest.main()
