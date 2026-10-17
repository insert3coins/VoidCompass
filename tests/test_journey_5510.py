"""5.5.10, Your Journey, Told Back: Void Wrapped (with the year's fights and
everyday things from its journals), the Flight Recorder and the music diary."""

from datetime import datetime, timezone
import functools
import http.client
import http.server
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from voidcompass.dashboard.dashboard_journey_mixin import DashboardJourneyMixin
from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
from voidcompass.exploration import galactic_regions
from voidcompass.exploration.flight_log import flight_logs
from voidcompass.exploration.flight_recorder import recorder_sessions, tape
from voidcompass.exploration.galactic_map_server import GalacticMapServer
from voidcompass.exploration.void_wrapped import year_story, years_available
from voidcompass.exploration.year_record import YearRecord, compact
from voidcompass.services.music_diary import MusicDiary

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def stamp(year, month, day, hour=20, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def journey(year=2026, nights=6, jumps=12, far=False):
    """Travel rows and Captain's Log sessions: a few nights of jumping."""
    rows, sessions = [], []
    x, z = 0.0, 0.0
    for night in range(nights):
        start = datetime(year, 3, 1 + night * 3, 19, tzinfo=timezone.utc).timestamp()
        highlights = []
        for jump in range(jumps):
            x += 40 + (200 if far else 0)
            z += 55 + (2000 if far else 0)
            when = datetime.fromtimestamp(start + 600 + jump * 400, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            system = f"Test Sector {night}-{jump}"
            rows.append([when, system, x, 1.0, z, "K", 62.5, ""])
            highlights.append({"timestamp": when, "kind": "JUMP", "title": f"Arrived in {system}", "detail": "62.5 ly"})
        highlights.append({"timestamp": datetime.fromtimestamp(start + 1500, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "kind": "CODEX", "title": "Bacterium Aurasus", "detail": "Biological and Geological"})
        highlights.append({"timestamp": datetime.fromtimestamp(start + 1800, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "kind": "BIO", "title": "Bacterium Aurasus", "detail": "Test Sector 0-1 A 2"})
        rows.append([datetime.fromtimestamp(start + 600 + jumps * 400 + 300, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "Home Port", 10.0, 0.0, 20.0, "G", 30.0, ""])
        sessions.append({"started": datetime.fromtimestamp(start, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "ended": datetime.fromtimestamp(start + 600 + jumps * 400 + 900, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "commander": "Tester", "ship": "Mandalay", "start_system": "", "end_system": "Home Port",
                         "jumps": jumps + 1, "distance_ly": jumps * 62.5 + 30, "codex": 1, "bio_analyses": 1,
                         "first_discoveries": 40, "exploration_sales": 2_000_000, "biology_sales": 5_000_000,
                         "trade_profit": 0, "deaths": 0, "highlights": highlights})
    sessions.reverse()  # the Captain's Log lists newest first
    return rows, sessions


class VoidWrappedTests(unittest.TestCase):
    def test_a_year_is_told_card_by_card(self):
        rows, sessions = journey()
        story = year_story(2026, {"rows": rows, "sessions": sessions, "region_of": galactic_regions.find_region}, "weary", "Tester")
        kinds = [card["kind"] for card in story["cards"]]
        self.assertEqual(kinds[0], "intro")
        self.assertEqual(kinds[-2:], ["verdict", "finale"])
        for wanted in ("distance", "jumps", "time", "busiest", "longest_jump", "furthest", "regions", "home", "codex", "biology", "money"):
            self.assertIn(wanted, kinds)
        home = next(card for card in story["cards"] if card["kind"] == "home")
        self.assertEqual(home["system"], "Home Port")
        self.assertEqual(story["summary"]["jumps"], 6 * 13)
        self.assertEqual(story["elite_year"], 3312)

    def test_the_same_history_tells_the_same_story(self):
        rows, sessions = journey()
        sources = {"rows": rows, "sessions": sessions}
        self.assertEqual(json.dumps(year_story(2026, sources, "weary", "Tester")), json.dumps(year_story(2026, sources, "weary", "Tester")))

    def test_mining_is_not_trading(self):
        rows, sessions = journey()
        for session in sessions:
            session["first_discoveries"] = 0
            session["trade_profit"] = 500_000_000  # the Captain's log counts every sale as trade
        mined = [{"kind": "sell", "commodity": "Painite", "avg_paid": 0, "total": 500_000_000, "profit": 500_000_000,
                  "ts": datetime(2026, 3, 2).timestamp()}] * 6
        story = year_story(2026, {"rows": rows, "sessions": sessions, "trades": mined}, "normal", "Tester")
        money = next(card for card in story["cards"] if card["kind"] == "money")
        self.assertEqual((money["trade"], money["mining"], money["best_trade"]), (0, 3_000_000_000, None))
        self.assertEqual(story["cards"][-2]["archetype"], "miner")

    def test_an_explorer_is_a_pathfinder_with_some_mining_on_the_side(self):
        rows, sessions = journey(far=True)
        for row in rows:
            row[6] = 1500.0 if row[6] > 40 else row[6]
        for session in sessions:
            session["first_discoveries"] = 1500
        mined = [{"kind": "sell", "commodity": "Painite", "avg_paid": 0, "total": 400_000_000, "profit": 400_000_000,
                  "ts": datetime(2026, 3, 2).timestamp()}]
        story = year_story(2026, {"rows": rows, "sessions": sessions, "trades": mined}, "normal", "Tester")
        self.assertEqual(story["cards"][-2]["archetype"], "pathfinder")

    def test_a_trader_is_a_merchant(self):
        rows, sessions = journey(nights=3, jumps=3)
        for session in sessions:
            session["first_discoveries"] = 0
            session["trade_profit"] = 900_000_000
        verdict = year_story(2026, {"rows": rows, "sessions": sessions}, "normal", "Tester")["cards"][-2]
        self.assertEqual(verdict["archetype"], "merchant")
        self.assertIn("credits", verdict["words"])

    def test_a_quiet_year_says_so(self):
        rows, sessions = journey()
        story = year_story(2025, {"rows": rows, "sessions": sessions}, "weary", "Tester")
        self.assertTrue(story["empty"])
        self.assertEqual([card["kind"] for card in story["cards"]], ["intro"])

    def test_the_years_offered(self):
        rows, sessions = journey()
        self.assertEqual(years_available(rows, sessions), [{"year": 2026, "elite_year": 3312, "jumps": len(rows), "sessions": 6}])

    def test_the_busiest_session_says_where_it_began(self):
        rows, sessions = journey()
        busiest = next(card for card in year_story(2026, {"rows": rows, "sessions": sessions})["cards"] if card["kind"] == "busiest")
        self.assertTrue(busiest["from"])

    def test_extras_have_their_cards(self):
        rows, sessions = journey()
        when = datetime(2026, 4, 1, 20).timestamp()
        story = year_story(2026, {
            "rows": rows, "sessions": sessions,
            "bodies": [{"system": "S", "name": "1", "full_name": "S 1", "planet_class": "Earthlike body", "class": "Earthlike body",
                        "is_star": False, "was_discovered": False, "reward": 5, "dss_reward": 9, "when": when}],
            "trades": [{"kind": "sell", "commodity": "Gold", "profit": 9_000_000, "avg_paid": 9000, "count": 100, "ts": when}],
            "bgs": [{"faction": "Canonn", "kind": "mission", "system": "Varati"}] * 4,
            "music": [[when + index, "abc", "Weightless", "Marconi Union", ""] for index in range(6)],
            "achievements": [{"title": "First", "points": 10, "unlockedAt": "2026-05-01T10:00:00Z"}],
            "postcards": [{"id": "0123456789abcdef", "title": "Greetings", "at": when}],
        }, "weary", "Tester")
        kinds = [card["kind"] for card in story["cards"]]
        for wanted in ("rare", "bgs", "music", "achievements", "postcards", "discoveries"):
            self.assertIn(wanted, kinds)
        rare = next(card for card in story["cards"] if card["kind"] == "rare")
        self.assertEqual(rare["label"], "Earth-like world")


def events(year=2026):
    """A year's worth of journal rows, as the year record keeps them."""
    at = lambda month, day: datetime(year, month, day, 20, tzinfo=timezone.utc).timestamp()
    rows = [{"t": at(3, 1) + index, "e": "Bounty", "v": 120_000 + index * 1000, "n": "Python", "x": "Pirates"} for index in range(30)]
    rows += [{"t": at(4, 2) + index, "e": "FactionKillBond", "v": 80_000, "n": "Thargoids", "x": "thargoid"} for index in range(5)]
    rows += [{"t": at(5, 1), "e": "Interdicted", "v": 0, "n": "Bob", "x": "player"}, {"t": at(5, 1) + 9, "e": "EscapeInterdiction", "v": 0, "n": "Bob", "x": ""},
             {"t": at(5, 2), "e": "Died", "v": 0, "n": "Cmdr Nemesis", "x": "Fer-de-Lance"},
             {"t": at(6, 1), "e": "Promotion", "v": 6, "n": "Dangerous", "x": ""}]
    rows += [{"t": at(7, 1) + index, "e": "MissionCompleted", "v": 500_000, "n": "Courier", "x": ""} for index in range(12)]
    rows += [{"t": at(7, 2) + index, "e": "Docked", "v": 0, "n": "Jameson Memorial", "x": ""} for index in range(40)]
    rows += [{"t": at(7, 3) + index, "e": "FuelScoop", "v": 32.0, "n": "", "x": ""} for index in range(10)]
    rows += [{"t": at(8, 1), "e": "EngineerCraft", "v": 0, "n": "Felicity Farseer", "x": "FSD"},
             {"t": at(8, 2), "e": "ShipyardBuy", "v": 1, "n": "Mandalay", "x": ""}]
    return rows


class CombatAndEverydayTests(unittest.TestCase):
    def test_the_fights_of_the_year(self):
        rows, sessions = journey()
        story = year_story(2026, {"rows": rows, "sessions": sessions, "events": events()}, "weary", "Tester")
        combat = next(card for card in story["cards"] if card["kind"] == "combat")
        self.assertEqual((combat["kills"], combat["ax_kills"], combat["interdicted"], combat["escaped"]), (35, 5, 1, 1))
        self.assertEqual(combat["bounty_cr"], sum(120_000 + index * 1000 for index in range(30)))
        self.assertEqual(combat["bond_cr"], 400_000)
        self.assertEqual((combat["biggest"]["value"], combat["biggest"]["target"]), (149_000, "Python"))
        self.assertEqual((combat["nemesis"], combat["rank"]), ("Cmdr Nemesis", "Dangerous"))

    def test_the_everyday(self):
        rows, sessions = journey()
        story = year_story(2026, {"rows": rows, "sessions": sessions, "events": events()}, "weary", "Tester")
        everyday = next(card for card in story["cards"] if card["kind"] == "everyday")
        self.assertEqual((everyday["missions"], everyday["mission_cr"], everyday["docked"], everyday["scooped"]), (12, 6_000_000, 40, 320))
        self.assertEqual((everyday["engineered"], everyday["engineer"], everyday["ships"], everyday["station"]),
                         (1, "Felicity Farseer", ["Mandalay"], "Jameson Memorial"))

    def test_a_year_of_fighting_is_a_warriors_year(self):
        rows, sessions = journey(nights=3, jumps=2)
        for session in sessions:
            session["first_discoveries"] = 0
        fights = [{"t": datetime(2026, 3, 2, tzinfo=timezone.utc).timestamp() + index, "e": "Bounty", "v": 1_500_000, "n": "Anaconda", "x": ""}
                  for index in range(400)]
        verdict = year_story(2026, {"rows": rows, "sessions": sessions, "events": fights}, "normal", "Tester")["cards"][-2]
        self.assertEqual(verdict["archetype"], "warrior")
        self.assertIn("400", verdict["words"])

    def test_no_fights_no_combat_card(self):
        rows, sessions = journey()
        story = year_story(2026, {"rows": rows, "sessions": sessions, "events": []}, "weary", "Tester")
        self.assertNotIn("combat", [card["kind"] for card in story["cards"]])


class YearRecordTests(unittest.TestCase):
    def journals(self, lines, name="Journal.2026-03-01T200000.01.log"):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / name
        path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
        return folder.name, path

    def test_only_the_commanders_events_in_the_year(self):
        folder, _path = self.journals([
            {"timestamp": "2026-03-01T20:00:00Z", "event": "Commander", "FID": "F1", "Name": "Tester"},
            {"timestamp": "2026-03-01T20:01:00Z", "event": "Bounty", "Target": "python", "Target_Localised": "Python", "TotalReward": 50000,
             "VictimFaction": "Pirates"},
            {"timestamp": "2026-03-01T20:02:00Z", "event": "Touchdown", "PlayerControlled": False},
            {"timestamp": "2026-03-01T20:03:00Z", "event": "Commander", "FID": "F2", "Name": "Someone Else"},
            {"timestamp": "2026-03-01T20:04:00Z", "event": "Bounty", "TotalReward": 1},
        ])
        start, end = datetime(2026, 1, 1).timestamp(), datetime(2027, 1, 1).timestamp()
        rows = YearRecord().events(folder, start, end, "Tester", "F1")
        self.assertEqual([(row["e"], row["v"], row["n"]) for row in rows], [("Bounty", 50000, "Python")])
        self.assertEqual(YearRecord().events(folder, datetime(2025, 1, 1).timestamp(), start, "Tester", "F1"), [])

    def test_new_lines_are_read_again(self):
        folder, path = self.journals([{"timestamp": "2026-03-01T20:00:00Z", "event": "Docked", "StationName": "A"}])
        record = YearRecord()
        start, end = datetime(2026, 1, 1).timestamp(), datetime(2027, 1, 1).timestamp()
        self.assertEqual(len(record.events(folder, start, end)), 1)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": "2026-03-01T21:00:00Z", "event": "Docked", "StationName": "Longer name, changed size"}) + "\n")
        self.assertEqual(len(record.events(folder, start, end)), 2)

    def test_thargoid_bonds_and_who_killed_you(self):
        self.assertEqual(compact({"timestamp": "2026-03-01T20:00:00Z", "event": "FactionKillBond", "Reward": 80000,
                                  "VictimFaction": "$faction_Thargoid;", "VictimFaction_Localised": "Thargoids"})["x"], "thargoid")
        died = compact({"timestamp": "2026-03-01T20:00:00Z", "event": "Died", "Killers": [{"Name": "Cmdr Bob", "Ship": "ferdelance"}]})
        self.assertEqual((died["n"], died["x"]), ("Cmdr Bob", "ferdelance"))
        self.assertIsNone(compact({"timestamp": "2026-03-01T20:00:00Z", "event": "Promotion", "Explore": 5}))


class FlightRecorderTests(unittest.TestCase):
    def test_a_tape_is_the_session_on_one_clock(self):
        rows, sessions = journey(nights=1)
        session = sessions[0]
        recorded = tape(session, rows, music=[[datetime.fromisoformat(session["started"].replace("Z", "+00:00")).timestamp() + 60,
                                                "abc", "Weightless", "Marconi Union", ""]])
        self.assertEqual(recorded["arrivals"][0]["t"], 600.0)
        self.assertEqual([moment["kind"] for moment in recorded["moments"]], ["codex", "bio"])
        self.assertEqual(recorded["moments"][0]["t"], 1500.0)
        self.assertEqual(recorded["music"][0]["title"], "Weightless")
        self.assertTrue(recorded["words"])
        self.assertGreater(recorded["length"], 5000)

    def test_quiet_stretches_can_be_skipped(self):
        rows, sessions = journey(nights=1, jumps=2)
        recorded = tape(sessions[0], rows)
        self.assertTrue(recorded["quiet"])
        self.assertTrue(all(b > a for a, b in recorded["quiet"]))

    def test_flight_logs_say_where_a_session_began(self):
        rows, sessions = journey(nights=4)
        self.assertEqual(flight_logs(sessions, rows, [], "weary")[0]["start_system"], "Home Port")

    def test_sessions_say_where_they_began(self):
        rows, sessions = journey(nights=2)
        listed = recorder_sessions(sessions, rows=rows)
        self.assertEqual(listed[0]["start_system"], "Home Port")
        self.assertEqual(listed[0]["id"], sessions[0]["started"])


class MusicDiaryTests(unittest.TestCase):
    def test_plays_are_kept_once_and_found_by_time(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        diary = MusicDiary(str(Path(folder.name) / "music_diary.json"))
        self.assertTrue(diary.note(1000, "abc", "Weightless", "Marconi Union"))
        self.assertFalse(diary.note(1030, "abc", "Weightless", "Marconi Union"), "a pause isn't a new play")
        self.assertTrue(diary.note(1400, "def", "Holocene", "Bon Iver"))
        self.assertEqual([row[1] for row in diary.between(900, 1500)], ["abc", "def"])
        self.assertEqual(diary.playing_at(1200)[2], "Weightless")
        self.assertIsNone(diary.playing_at(10))


class Deck(DashboardJourneyMixin):
    """Just enough of MainDashboard for the journey mixin."""

    def __init__(self, rows, sessions):
        self.config = {"active_commander_name": "Tester", "active_commander_profile": "tester"}
        self.travel_history = type("History", (), {"lock": threading.RLock(), "rows": rows, "revision": 1})()
        self.captains_log = type("Log", (), {"sessions": lambda self: sessions})()
        self.current_sys = "Smoke Sector AB-C d1"
        self.published = 0

    def music_diary(self):
        if not hasattr(self, "_diary"):
            self._diary = MusicDiary("")
        return self._diary

    def _schedule_html_dashboard_publish(self, immediate=False):
        self.published += 1

    def _persist_config(self):
        pass


class JourneyMixinTests(unittest.TestCase):
    def test_a_year_is_gathered_off_the_app_loop(self):
        rows, sessions = journey()
        deck = Deck(rows, sessions)
        first = deck._wrapped_story(2026)
        self.assertTrue(first.get("working"))
        for _ in range(100):
            story = deck._wrapped_story(2026)
            if not story.get("working"):
                break
            time.sleep(.05)
        self.assertEqual(story["year"], 2026)
        self.assertIn("verdict", [card["kind"] for card in story["cards"]])
        self.assertIs(deck._wrapped_story(2026), story, "kept until something changes")

    def test_refresh_tells_the_year_again(self):
        rows, sessions = journey()
        deck = Deck(rows, sessions)
        told = []
        deck._tell_year = lambda year: told.append(year) or {"year": year, "cards": [{"kind": "intro"}]}

        def settle():
            for _ in range(100):
                story = deck._wrapped_story(2026)
                if not story.get("working"):
                    return story
                time.sleep(.02)
        settle()
        settle()
        self.assertEqual(told, [2026], "kept while nothing changes")
        self.assertTrue(deck._handle_wrapped_command("retell", {"year": 2026}))
        settle()
        self.assertEqual(told, [2026, 2026], "REFRESH tells it again")

    def test_the_deck_asks_by_name(self):
        deck = Deck(*journey())
        self.assertIsNone(deck._html_data("nothing", {}))
        self.assertIsNone(deck._html_data("book", {}))
        self.assertIsNone(deck._html_data("system-song", {}))

    def test_the_recorder_finds_a_session_by_its_start(self):
        rows, sessions = journey(nights=2)
        deck = Deck(rows, sessions)
        listed = deck._recorder_data({})["sessions"]
        recorded = deck._recorder_data({"id": listed[1]["id"]})
        self.assertEqual(recorded["id"], sessions[1]["started"])
        self.assertIsNone(deck._recorder_data({"id": "1999-01-01T00:00:00Z"}))

    def test_watch_again_asks_the_atlas(self):
        deck = Deck(*journey())
        deck._request_html_dashboard_page = lambda page: page == "map"
        self.assertTrue(deck._recorder_open("2026-03-01T19:00:00Z"))
        self.assertEqual(deck._recorder_request["id"], "2026-03-01T19:00:00Z")


class ServerTests(unittest.TestCase):
    def get(self, server, path):
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        self.addCleanup(connection.close)
        connection.request("GET", path)
        reply = connection.getresponse()
        return reply.status, reply.getheader("Content-Type"), reply.getheader("Content-Security-Policy"), reply.read()

    def test_the_deck_answers_by_name_with_its_token(self):
        server = HtmlDashboardServer(WEB)
        self.addCleanup(server.stop)
        server.data_provider = lambda name, query: ("application/json", b'{"year": 2026}') if name == "wrapped" else None
        status, kind, policy, body = self.get(server, f"/api/data/wrapped?token={server.token}")
        self.assertEqual((status, kind, body), (200, "application/json", b'{"year": 2026}'))
        self.assertIn("frame-ancestors 'none'", policy)
        self.assertEqual(self.get(server, "/api/data/wrapped")[0], 403)
        self.assertEqual(self.get(server, f"/api/data/nothing?token={server.token}")[0], 404)

    def test_the_atlas_serves_the_recorder(self):
        server = GalacticMapServer(WEB / "galactic_map", ROOT / "assets" / "missing.png",
                                   recorder_provider=lambda query: {"sessions": [], "asked": query})
        self.addCleanup(server.stop)
        status, kind, _policy, body = self.get(server, f"/api/recorder?id=abc&token={server.token}")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["asked"], {"id": "abc"})
        self.assertEqual(self.get(server, f"/recorder.js?token={server.token}")[0], 200)
        self.assertEqual(self.get(server, "/api/recorder")[0], 403)


class DeckWiringTests(unittest.TestCase):
    def test_the_pages_and_their_buttons(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        for needle in ('data-page="wrapped"', 'id="wrapped-workspace"', 'href="wrapped.css"'):
            self.assertIn(needle, html)
        app = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8")
        for needle in ('from "./wrapped.js"', "wrapped: (data) =>"):
            self.assertIn(needle, app)
        self.assertIn('data-wrapped="refresh"', (WEB / "dashboard" / "wrapped.js").read_text(encoding="utf-8"))
        self.assertIn("queue: () => playQueue(state.remote.tracks)", (WEB / "dashboard" / "music.js").read_text(encoding="utf-8"))
        self.assertIn("data-flightlog-watch", (WEB / "dashboard" / "flightlog.js").read_text(encoding="utf-8"))

    def test_the_pages_draw_in_place_and_fit_the_window(self):
        source = (WEB / "dashboard" / "wrapped.js").read_text(encoding="utf-8")
        self.assertIn('root.classList.remove("loading-panel")', source, "no loading circle once drawn")
        self.assertIn('document.querySelector(".statusbar")', source, "sized down to the status bar")

    def test_the_book_and_system_tunes_are_gone(self):
        for name in ("book.js", "book.css", "sonify.js"):
            self.assertFalse((WEB / "dashboard" / name).exists(), name)
        for name in ("journey_book.py", "system_song.py"):
            self.assertFalse((ROOT / "src" / "voidcompass" / "exploration" / name).exists(), name)
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        for needle in ('data-page="book"', "music-songs", "data-song-listen"):
            self.assertNotIn(needle, html)

    def test_the_atlas_has_the_recorder(self):
        html = (WEB / "galactic_map" / "index.html").read_text(encoding="utf-8")
        for needle in ('data-tab="recorder"', 'id="recorder"', 'id="recorder-scrub"', 'id="recorder-music"', 'id="recorder-feed"'):
            self.assertIn(needle, html)
        self.assertIn("import {createRecorder} from './recorder.js';", (WEB / "galactic_map" / "app.js").read_text(encoding="utf-8"))

    def test_new_settings_are_kept_per_commander(self):
        from voidcompass.core.config import PROFILE_SETTINGS
        self.assertIn("wrapped_noticed_year", PROFILE_SETTINGS)
        self.assertFalse([key for key in PROFILE_SETTINGS if key.startswith(("system_song", "journey_book"))])


class WrappedBrowserTests(unittest.TestCase):
    """The story plays in a browser: every card draws, and a saved card is a picture."""

    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f"Playwright Chromium is unavailable: {exc}")
        rows, sessions = journey()
        story = year_story(2026, {"rows": rows, "sessions": sessions, "region_of": galactic_regions.find_region, "events": events(),
                                  "music": [[datetime(2026, 4, 1).timestamp() + index, "abc", "Weightless", "Marconi Union", ""]
                                            for index in range(6)]}, "weary", "Tester")
        assert {"combat", "everyday"} <= {card["kind"] for card in story["cards"]}
        page = PAGE % json.dumps(story)

        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path == "/":
                    body = page.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                super().do_GET()

        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(WEB / "dashboard")))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.count = len(story["cards"])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.browser.close()
        cls.playwright.stop()

    def test_every_card_draws_and_saves(self):
        page = self.browser.new_page(viewport={"width": 1300, "height": 1200}, reduced_motion="reduce")
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"http://127.0.0.1:{self.server.server_address[1]}/")
        page.wait_for_function("window.harnessReady === true")
        page.wait_for_selector("#wrapped-start:not([hidden])")
        self.assertEqual(page.locator("#wrapped-index li").count(), self.count)
        page.click("#wrapped-start")
        for index in range(self.count):
            page.wait_for_timeout(60)
            self.assertIn(f"{index + 1} / {self.count}", page.inner_text("#wrapped-where"))
            page.keyboard.press("ArrowRight")
        page.click('[data-wrapped="save"]')
        page.wait_for_function("window.commands.length > 0")
        sent = page.evaluate("window.commands[0]")
        self.assertEqual((sent[0], sent[1]["page"], sent[1]["operation"]), ("workspace", "wrapped", "save"))
        self.assertTrue(sent[1]["picture"].startswith("data:image/jpeg;base64,"))
        self.assertEqual(errors, [])



PAGE = """<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/styles.css"><link rel="stylesheet" href="/wrapped.css"></head>
<body><section class="page active" data-page-name="wrapped"><div id="wrapped-workspace"></div></section><div id="toast"></div>
<script type="module">
const story = %s;
const realFetch = window.fetch;
window.fetch = async (url, options) => String(url).includes("/api/data/wrapped")
  ? new Response(JSON.stringify(story), {headers: {"Content-Type": "application/json"}}) : realFetch(url, options);
window.commands = [];
const ui = {byId: (id) => document.getElementById(id), escapeHtml: (v) => String(v ?? ""), showToast: () => {}, apiUrl: (p) => p,
  numeric: (v) => String(v), command: async (...args) => { window.commands.push(args); return true; }};
const {renderWrapped} = await import("/wrapped.js");
renderWrapped({years: [{year: 2026, elite_year: 3312, jumps: 78, sessions: 6}], saved: {count: 0}}, ui);
window.harnessReady = true;
</script></body></html>"""


if __name__ == "__main__":
    unittest.main()
