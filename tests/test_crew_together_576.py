"""The crew, together (5.7.6): the watch rota, expedition debriefs and log
postscripts, the crew's own story, and the crew card in Void Wrapped."""
import random
import unittest
from unittest import mock
from pathlib import Path

from voidcompass.core import companions, config as config_module, crew_rota
from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.exploration import flight_log, void_wrapped
from voidcompass.overlays import crew_debrief, crew_lore, crew_story
from tests.test_aster_companion import Clock

ROOT = Path(__file__).resolve().parents[1]
CREW = ("watcher", "aster", "axiom", "meridian", "lyra")


def mind(identity, flown=CREW, **crew):
    config = {"companion_identity": identity, f"{identity}_thoughts": "chatty", "heartbeat_thoughts": "chatty"}
    companion = companions.create_mind(None, config, clock=Clock(), rng=random.Random(4))
    companion.session_start()
    companion.learn({"crew": {"flown": list(flown), **crew}})
    return companion


def drain(companion, seconds, step=1.0):
    said = []
    for _ in range(int(seconds / step)):
        companion.clock.now += step
        thought = companion.tick()
        if thought and thought.get("topic") in ("crew_debrief", "crew_story"):
            said.append(thought)
    return said


class RotaTests(unittest.TestCase):
    def test_who_wants_the_watch(self):
        self.assertEqual(crew_rota.wanted({"docked": True, "route_left": 4}), "aster", "docked comes first")
        self.assertEqual(crew_rota.wanted({"gui_focus": crew_rota.FSS_FOCUS}), "axiom")
        self.assertEqual(crew_rota.wanted({"gui_focus": crew_rota.SAA_FOCUS}), "axiom")
        self.assertEqual(crew_rota.wanted({"on_planet": True, "in_srv": True}), "axiom")
        self.assertEqual(crew_rota.wanted({"on_planet": True, "on_foot": True}), "axiom")
        self.assertEqual(crew_rota.wanted({"route_left": 3, "home_ly": 5000}), "meridian", "a route beats deep space")
        self.assertEqual(crew_rota.wanted({"home_ly": 1500}), "watcher")
        self.assertEqual(crew_rota.wanted({"home_ly": 200}), "lyra", "ordinary flight is Lyra's watch")
        self.assertIsNone(crew_rota.wanted({"on_planet": True, "home_ly": 5000}), "landed in the ship isn't deep space")
        self.assertIsNone(crew_rota.wanted({"route_left": "x", "home_ly": None}))

    def test_settles_waits_and_holds(self):
        rota = crew_rota.Rota()
        docked = {"docked": True}
        self.assertIsNone(rota.step(docked, 0, "watcher"), "first sighting only starts the clock")
        self.assertIsNone(rota.step(docked, crew_rota.SETTLE_S - 1, "watcher"))
        self.assertEqual(rota.step(docked, crew_rota.SETTLE_S, "watcher"), "aster")
        now = crew_rota.SETTLE_S
        self.assertIsNone(rota.step(docked, now + 1, "aster"), "already on watch")
        scanning = {"gui_focus": crew_rota.FSS_FOCUS}
        rota.step(scanning, now + 10, "aster")
        self.assertIsNone(rota.step(scanning, now + 10 + crew_rota.SETTLE_S, "aster"), "too soon after the last change")
        self.assertEqual(rota.step(scanning, now + crew_rota.MIN_GAP_S, "aster"), "axiom")
        rota.step({"route_left": 2}, 1000, "axiom")
        self.assertIsNone(rota.step({}, 1001, "axiom"), "nothing to do resets the candidate")
        self.assertIsNone(rota.step({"route_left": 2}, 1001 + crew_rota.SETTLE_S, "axiom"), "a fresh candidate settles again")
        rota.hold(2000)
        self.assertIsNone(rota.step(docked, 2000 + crew_rota.SETTLE_S * 2, "axiom"))
        self.assertIsNone(rota.step(docked, 2000 + crew_rota.HOLD_S - 1, "axiom"), "your choice holds")
        rota.step(docked, 2000 + crew_rota.HOLD_S, "axiom")
        self.assertEqual(rota.step(docked, 2000 + crew_rota.HOLD_S + crew_rota.SETTLE_S, "axiom"), "aster")
        self.assertIsNone(crew_rota.Rota().step(docked, 999, "watcher", enabled=False))

    def test_the_deck_switches_only_when_on(self):
        class Deck(DashboardWatcherVoiceMixin):
            def __init__(self):
                self.config = {"companion_identity": "watcher"}
                self.heartbeat_hud = object()
                self.current_docked = True
                self.switched = []

            def _companion_switch(self, selected, by_rota=False):
                self.switched.append((selected, by_rota))
                self.config["companion_identity"] = selected
                return True

        deck = Deck()
        self.assertIsNone(deck._crew_rota_tick(0))
        self.assertIsNone(deck._crew_rota_tick(100), "off by default")
        deck.config["crew_rota"] = True
        deck._crew_rota_tick(200)
        self.assertEqual(deck._crew_rota_tick(200 + crew_rota.SETTLE_S), "aster")
        self.assertEqual(deck.switched, [("aster", True)])

    def test_you_choose_who_takes_each_duty(self):
        self.assertEqual(crew_rota.duties({}), crew_rota.DEFAULT_DUTIES)
        chosen = crew_rota.duties({"crew_rota_docked": "meridian", "crew_rota_deep": "keep", "crew_rota_route": "nobody"})
        self.assertEqual((chosen["docked"], chosen["deep"], chosen["route"]), ("meridian", "keep", "meridian"),
                         "an unknown choice falls back to the default")
        self.assertEqual(crew_rota.wanted({"docked": True}, chosen), "meridian")
        self.assertIsNone(crew_rota.wanted({"home_ly": 5000}, chosen), "keep leaves whoever has the watch")
        self.assertEqual(crew_rota.duty_of({"on_planet": True, "in_srv": True}), "surface")
        self.assertEqual(crew_rota.duty_of({"gui_focus": crew_rota.FSS_FOCUS}), "scanning")
        # Ordinary flight: in the ship, no route, near home. Lyra's, unless you choose.
        self.assertEqual(crew_rota.duty_of({"home_ly": 334}), "flight")
        self.assertEqual(crew_rota.wanted({"home_ly": 334}), "lyra")
        self.assertIsNone(crew_rota.wanted({"home_ly": 334}, crew_rota.duties({"crew_rota_flight": "keep"})),
                          "keep leaves whoever's on watch")
        self.assertEqual(crew_rota.wanted({"home_ly": 334}, crew_rota.duties({"crew_rota_flight": "meridian"})), "meridian")
        self.assertIsNone(crew_rota.duty_of({"on_planet": True}), "landed in the ship isn't flight")
        # Where deep space starts is yours to choose too.
        self.assertEqual(crew_rota.deep_ly({}), 1000)
        self.assertEqual(crew_rota.deep_ly({"crew_rota_deep_ly": 250}), 250)
        self.assertEqual(crew_rota.deep_ly({"crew_rota_deep_ly": 123}), 1000, "only the offered distances")
        self.assertEqual(crew_rota.duty_of({"home_ly": 334, "deep_ly": 250}), "deep")
        self.assertEqual(crew_rota.duty_of({"home_ly": 334, "deep_ly": 500}), "flight")
        self.assertIn("crew_rota_deep_ly", config_module.PROFILE_SETTINGS)
        for duty, _label, _who in crew_rota.DUTIES:
            self.assertIn(crew_rota.duty_key(duty), config_module.PROFILE_SETTINGS)

    def test_it_changes_the_watch_even_when_status_is_quiet(self):
        class Root:
            def __init__(self):
                self.jobs = []

            def call_later(self, ms, callback):
                self.jobs.append((ms, callback))
                return len(self.jobs)

        class Deck(DashboardWatcherVoiceMixin):
            def __init__(self):
                self.config = {"companion_identity": "meridian", "crew_rota": True, "crew_rota_docked": "aster"}
                self.root = Root()
                self.heartbeat_hud = object()
                self.current_docked = True
                self.switched = []

            def _companion_switch(self, selected, by_rota=False):
                self.switched.append(selected)
                self.config["companion_identity"] = selected
                return True

        deck = Deck()
        clock = [1000.0]
        with mock.patch("voidcompass.dashboard.dashboard_watcher_voice_mixin.time.time", side_effect=lambda: clock[0]):
            deck._crew_rota_tick()  # the one Status.json update, docked
            self.assertEqual(len(deck.root.jobs), 1, "it looks again without waiting for Status.json")
            self.assertEqual(deck.root.jobs[0][0], int(crew_rota.TICK_S * 1000))
            for _ in range(12):
                clock[0] += crew_rota.TICK_S
                _ms, look = deck.root.jobs.pop(0)
                look()
        self.assertEqual(deck.switched, ["aster"], "docked and idle: Aster takes the watch")
        deck.config["crew_rota"] = False
        _ms, look = deck.root.jobs.pop(0)
        look()
        self.assertEqual(deck.root.jobs, [], "switched off, it stops looking")

    def test_every_status_update_reaches_the_rota(self):
        # On the main thread a status update was applied directly and the rota
        # never ran, so its timer never started (5.7.6, found live).
        from voidcompass.dashboard.dashboard_scan_mixin import DashboardScanMixin

        class Deck(DashboardScanMixin):
            def __init__(self):
                self.applied, self.rota = [], 0
                self.root = type("Root", (), {"call_later": lambda _self, _ms, callback: callback()})()

            def _apply_status_update(self, data):
                self.applied.append(data)

            def _crew_rota_tick(self):
                self.rota += 1

        deck = Deck()
        deck.update_status({"Flags": 1})
        self.assertEqual((deck.applied, deck.rota), ([{"Flags": 1}], 1), "on the main thread")
        import threading
        worker = threading.Thread(target=deck.update_status, args=({"Flags": 2},))
        worker.start()
        worker.join()
        self.assertEqual((deck.applied[-1], deck.rota), ({"Flags": 2}, 2), "from the journal watcher's thread")

    def test_duties_are_saved_from_the_page(self):
        class Deck(DashboardWatcherVoiceMixin):
            def __init__(self):
                self.config = {"companion_identity": "watcher"}
                self.saved = 0

            def _persist_config(self):
                self.saved += 1

            def _schedule_html_dashboard_publish(self, immediate=False):
                pass

        deck = Deck()
        self.assertTrue(deck._handle_watcher_settings_command("settings", {"values": {"crew_rota_docked": "meridian"}}))
        self.assertEqual(deck.config["crew_rota_docked"], "meridian")
        self.assertTrue(deck._handle_watcher_settings_command("settings", {"values": {"crew_rota_deep": "keep"}}))
        self.assertFalse(deck._handle_watcher_settings_command("settings", {"values": {"crew_rota_route": "jameson"}}))
        self.assertTrue(deck._handle_watcher_settings_command("settings", {"values": {"crew_rota_deep_ly": "500"}}))
        self.assertEqual(deck.config["crew_rota_deep_ly"], 500)
        self.assertFalse(deck._handle_watcher_settings_command("settings", {"values": {"crew_rota_deep_ly": "42"}}))
        script = (ROOT / "web/dashboard/watcher.js").read_text(encoding="utf-8")
        self.assertIn("crew_rota_${duty}", script)
        self.assertIn('["keep", "Whoever\'s on watch"]', script)

    def test_setting_is_per_profile_and_offered(self):
        self.assertIn("crew_rota", config_module.PROFILE_BOOL_SETTINGS)
        self.assertIn('toggle("crew_rota"', (ROOT / "web/dashboard/watcher.js").read_text(encoding="utf-8"))


class DebriefTests(unittest.TestCase):
    def test_crewmates_add_a_line_each_in_turn(self):
        companion = mind("watcher", flown=("watcher", "aster", "meridian"))
        companion.clock.now += 400
        first = companion.note("expedition_set_out", {"name": "Colonia Run"})
        self.assertEqual((first or {}).get("topic"), "expedition_set_out")
        said = drain(companion, crew_debrief.SPACING_S * 3)
        self.assertEqual([thought.get("speaker") for thought in said], ["meridian", "aster"], "only those you've flown with")
        for thought in said:
            self.assertIn(thought["text"], [line.format(name="Colonia Run") for line in crew_debrief.DEBRIEF[thought["speaker"]]])
            self.assertIn("OFF WATCH", thought.get("heading", ""))

    def test_old_lines_are_let_go(self):
        companion = mind("aster")
        companion.clock.now += 400
        companion.note("expedition_set_out", {"name": "Sag A* Dash"})
        companion.clock.now += crew_debrief.EXPIRES_S + crew_debrief.SPACING_S * 4 + 5
        self.assertEqual(drain(companion, 30), [])

    def test_lines_are_whole(self):
        for speaker in crew_debrief.ORDER:
            self.assertGreaterEqual(len(crew_debrief.DEBRIEF[speaker]), 6)
            self.assertGreaterEqual(len(crew_debrief.POSTSCRIPTS[speaker]), 5)
            for line in crew_debrief.DEBRIEF[speaker]:
                self.assertNotIn("{", line.format(name="X"), speaker)
            for line in crew_debrief.POSTSCRIPTS[speaker]:
                self.assertNotIn("{", line, speaker)

    def test_the_log_is_signed_by_everyone_on_watch(self):
        session = {"started": "2026-03-01T10:00:00Z", "ended": "2026-03-01T12:00:00Z", "companion": "aster",
                   "companions": ["aster", "axiom", "watcher", "axiom"]}
        entry = flight_log.flight_log(session)
        names = [row["name"] for row in entry["postscripts"]]
        self.assertEqual(names, ["Axiom", "the Watcher"], "the one who wrote it doesn't sign twice")
        self.assertEqual(entry, flight_log.flight_log(session), "the same session signs the same way")
        self.assertEqual(flight_log.flight_log({**session, "companions": ["aster"]})["postscripts"], [])
        self.assertIn("flightlog-ps", (ROOT / "web/dashboard/flightlog.js").read_text(encoding="utf-8"))


class StoryTests(unittest.TestCase):
    def test_locked_until_every_account_is_told(self):
        self.assertIsNone(crew_story.due({}, (), False, 10 ** 9))
        self.assertEqual(crew_story.due({}, (), True, 10 ** 9)[0], "night_1")
        self.assertEqual(crew_story.due({}, ("night_1",), True, 10 ** 9)[0], "night_2", "shared progress")
        self.assertIsNone(crew_story.due({"crew_story": [["night_1", 100.0]]}, (), True, 100 + crew_story.GAP_S - 1))
        self.assertIsNone(crew_story.due({}, crew_story.IDS, True, 10 ** 9), "all told")

    def test_scenes_are_five_voices(self):
        for scene_id, _title, lines in crew_story.SCENES:
            self.assertEqual(sorted(speaker for speaker, _line in lines), sorted(CREW), scene_id)
            self.assertEqual(len(crew_story.heading(scene_id).split(" · ")), 3)
        self.assertEqual(len(crew_story.IDS), len(set(crew_story.IDS)))

    def test_told_in_turn_each_in_its_own_voice(self):
        total = sum(len(arc) for arc in crew_lore.PASSAGES.values())
        companion = mind("meridian", told=total, total=total, story=[])
        companion.memory["crew_lore"] = [[passage[0], 1.0] for passage in crew_lore.PASSAGES["meridian"]]
        companion.clock.now += 300
        first = companion._crew_passage(companion.clock.now)
        self.assertEqual(first["topic"], "crew_story")
        self.assertTrue(first["heading"].startswith("THE NIGHT WATCH"))
        rest = drain(companion, crew_story.SPACING_S * 4)
        lines = [first] + rest
        expected = crew_story.SCENES[0][2]
        self.assertEqual([thought["text"] for thought in lines], [line for _speaker, line in expected])
        self.assertEqual([thought.get("speaker") or "meridian" for thought in lines], [speaker for speaker, _line in expected])
        self.assertEqual(crew_story.told(companion.memory), {"night_1"})
        companion.clock.now += 60
        self.assertIsNone(companion._crew_story_scene(companion.clock.now), "one scene, then a long gap")

    def test_not_before_the_accounts(self):
        companion = mind("watcher", told=3, total=35, story=[])
        companion.clock.now += 10 ** 6
        self.assertIsNone(companion._crew_story_scene(companion.clock.now))

    def test_the_story_tab(self):
        page = crew_story.page(["night_2"], True)
        self.assertEqual((page["told"], page["total"]), (1, len(crew_story.SCENES)))
        heard = [scene for scene in page["scenes"] if scene["heard"]]
        self.assertEqual([scene["id"] for scene in heard], ["night_2"])
        self.assertEqual(len(heard[0]["lines"]), 5)
        self.assertTrue(all(not scene["lines"] for scene in page["scenes"] if not scene["heard"]), "untold scenes stay hidden")
        script = (ROOT / "web/dashboard/watcher.js").read_text(encoding="utf-8")
        self.assertIn('id="watcher-crew-story"', script)
        self.assertIn("crew.ensemble", script)


class WrappedTests(unittest.TestCase):
    def setUp(self):
        self.start, self.end = void_wrapped.year_bounds(2026)
        self.sessions = void_wrapped._sessions_in([
            {"started": "2026-03-01T10:00:00Z", "ended": "2026-03-01T13:00:00Z", "companion": "aster", "companions": ["watcher", "aster"]},
            {"started": "2026-04-01T10:00:00Z", "ended": "2026-04-01T12:00:00Z", "companion": "axiom"},
            {"started": "2026-05-01T10:00:00Z", "ended": "2026-05-01T11:00:00Z"},
            {"started": "2025-04-01T10:00:00Z", "ended": "2025-04-01T20:00:00Z", "companion": "meridian"}], self.start, self.end)

    def test_hours_are_shared_and_only_this_year(self):
        start = self.start
        memories = {"aster": {"log": [[start + 9, "jump", "Jump complete. Logged at the usual hour, Commander."],
                                      [start + 9, "crew_lore", "A story passage, never to be quoted on a card."],
                                      [start - 9, "jump", "Last year's line, which stays in last year."]],
                              "lore": [["aster_01", start + 5], ["aster_00", start - 5]],
                              "crew_story": [["night_1", start + 30]]},
                    "meridian": {"log": [[start + 9, "relay", "Relayed words from somebody else entirely."]]}}
        card = void_wrapped.crew_card(self.sessions, memories, self.start, self.end, 3)
        by_id = {member["id"]: member for member in card["members"]}
        self.assertEqual(set(by_id), {"watcher", "aster", "axiom"}, "Meridian only flew last year")
        self.assertEqual((by_id["watcher"]["hours"], by_id["aster"]["hours"], by_id["axiom"]["hours"]), (2.5, 1.5, 2.0))
        self.assertEqual(card["top"], "The Watcher")
        self.assertEqual(by_id["aster"]["line"], "Jump complete. Logged at the usual hour, Commander.")
        self.assertEqual(by_id["aster"]["stories"], 1)
        self.assertEqual(card["night_watch"], 1)

    def test_in_the_year_and_drawn(self):
        story = void_wrapped.year_story(2026, {"sessions": [row[2] for row in self.sessions], "crew": {}})
        self.assertIn("crew", [card["kind"] for card in story["cards"]])
        self.assertIsNone(void_wrapped.crew_card([], {}, self.start, self.end, 1), "no sessions, no card")
        script = (ROOT / "web/dashboard/wrapped.js").read_text(encoding="utf-8")
        self.assertIn('crew: "The crew"', script)
        self.assertIn("crew: [", script)
        self.assertIn("crew(c, card, t, colour)", script)


if __name__ == "__main__":
    unittest.main()
