"""5.6.9: the Navigation HUD counts down to the real jump.

The game writes no event when the jump key is pressed. Status.json's charging
flags show it, StartJump follows during the countdown, Status' FsdJump bit
rises as the ship enters the tunnel and FSDJump says it has arrived. The jump
clock (src/voidcompass/dashboard/jump_clock.py) notes those moments for each
jump and learns from the commander's own jumps how long each part takes; the
HUD's rail fills to the jump and counts the last seconds down, and the scene
builds with the charge. Nothing is counted before a jump has been measured.
"""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from tests import test_navigation_scene as scene_tests
from tests.test_navigation_state_visuals import hud_state
from voidcompass.core.journal_watcher import JournalWatcher
from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.dashboard.dashboard_jump_info_mixin import DashboardJumpInfoMixin
from voidcompass.dashboard.jump_clock import KEEP, TRANSIT, JumpClock


def measured_jump(clock, t0, lead=9.0, countdown=4.0, tunnel=14.0, kind="hyperspace"):
    clock.charging(kind, t0)
    clock.started(kind, t0 + lead - countdown)
    clock.charge_dropped(t0 + lead - countdown + .1)
    clock.tunnel(t0 + lead)
    return clock.arrived(kind, t0 + lead + tunnel)


class JumpClockTests(unittest.TestCase):
    def test_the_first_jump_is_not_counted_and_teaches_the_clock(self):
        clock = JumpClock()
        clock.charging("hyperspace", 100.0)
        view = clock.view(101.0)
        self.assertEqual((view["kind"], view["press"], view["jump"], view["exact"]), ("hyperspace", 100000, None, False))
        clock.started("hyperspace", 105.0)
        # The journals' StartJump-to-arrival time stands in until a tunnel is measured.
        self.assertEqual(clock.view(105.5)["arrive"], int((105.0 + TRANSIT["hyperspace"]) * 1000))
        clock.tunnel(109.0)
        view = clock.view(109.5)
        self.assertTrue(view["jumped"])
        self.assertEqual(view["jump"], 109000)
        self.assertTrue(clock.arrived("hyperspace", 123.0))
        self.assertIsNone(clock.view(123.5))
        self.assertEqual(clock.samples["hyperspace"], {"lead": [9.0], "countdown": [4.0], "tunnel": [14.0]})

    def test_a_measured_jump_counts_from_the_press(self):
        clock = JumpClock()
        measured_jump(clock, 0.0)
        clock.charging("hyperspace", 200.0)
        view = clock.view(201.0)
        self.assertTrue(view["exact"])
        self.assertEqual((view["jump"], view["arrive"]), (209000, 223000))
        # StartJump close to the prediction keeps the more precise press anchor.
        clock.started("hyperspace", 205.4)
        self.assertEqual(clock.view(206.0)["jump"], 209000)

    def test_a_held_charge_re_anchors_on_start_jump(self):
        clock = JumpClock()
        measured_jump(clock, 0.0)
        clock.charging("hyperspace", 200.0)
        clock.started("hyperspace", 212.0)
        self.assertEqual(clock.view(212.5)["jump"], 216000)

    def test_the_hyperdrive_bit_a_write_later_keeps_the_press(self):
        clock = JumpClock()
        clock.charging("supercruise", 50.0)
        clock.charging("hyperspace", 50.4)
        self.assertEqual((clock.jump["kind"], clock.jump["press"]), ("hyperspace", 50.0))

    def test_a_cancelled_charge_is_forgotten_and_not_learned(self):
        clock = JumpClock()
        clock.charging("hyperspace", 10.0)
        clock.charge_dropped(12.0)
        self.assertIsNotNone(clock.view(13.0))
        self.assertIsNone(clock.view(14.5))
        clock.charging("hyperspace", 30.0)
        self.assertEqual(clock.jump["press"], 30.0)
        self.assertEqual(clock.samples["hyperspace"]["lead"], [])

    def test_kinds_are_learned_apart_with_a_median_of_the_last_few(self):
        clock = JumpClock()
        for index, lead in enumerate([5.0, 5.2, 30.5, 5.1, 99.0]):
            measured_jump(clock, index * 100.0, lead=lead, countdown=1.0, tunnel=4.0, kind="supercruise")
        rows = clock.samples["supercruise"]
        self.assertEqual(rows["lead"], [5.0, 5.2, 30.5, 5.1], "a 99 s charge was held, not learned")
        self.assertAlmostEqual(clock.expected("supercruise", "lead"), 5.15)
        self.assertEqual(clock.samples["hyperspace"]["lead"], [])
        for index in range(KEEP + 3):
            measured_jump(clock, 1000.0 + index * 100.0, kind="supercruise")
        self.assertEqual(len(clock.samples["supercruise"]["lead"]), KEEP)

    def test_a_late_status_after_arrival_starts_nothing(self):
        clock = JumpClock()
        measured_jump(clock, 0.0)
        clock.tunnel(24.0)
        self.assertIsNone(clock.view(24.5))

    def test_learned_timings_survive_a_restart(self):
        clock = JumpClock()
        measured_jump(clock, 0.0)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "jump_timing.json")
            clock.save(path)
            again = JumpClock.load(path)
            self.assertEqual(again.samples, clock.samples)
            Path(path).write_text("not json", encoding="utf-8")
            self.assertEqual(JumpClock.load(path).samples["hyperspace"]["lead"], [])


class CooldownClockTests(unittest.TestCase):
    def test_the_cooldown_is_learned_by_what_caused_it(self):
        clock = JumpClock()
        clock.arrived("hyperspace", 100.0)
        clock.cooling(99.6)  # Status can be read just before the journal's FSDJump
        self.assertEqual(clock.cool_view(101.0), {"after": "hyperspace", "start": 99600, "ready": None, "exact": False})
        self.assertTrue(clock.cooled(109.6))
        clock.dropped(200.0)
        clock.cooling(200.5)
        self.assertTrue(clock.cooled(205.5))
        self.assertEqual(clock.cooldown["hyperspace"], [10.0])
        self.assertEqual(clock.cooldown["drop"], [5.0])
        clock.arrived("hyperspace", 300.0)
        clock.cooling(300.2)
        self.assertEqual(clock.cool_view(301.0)["ready"], 310200, "the next one counts down to the measured length")
        self.assertTrue(clock.cool_view(301.0)["exact"])
        # Nothing near it: an interdiction, a reboot... learned apart.
        clock.cooling(900.0)
        self.assertEqual(clock.cool_view(901.0)["after"], "other")
        self.assertFalse(clock.cooled(1100.0), "two hundred seconds is no cooldown")

    def test_cooldowns_survive_a_restart_and_older_files_still_load(self):
        clock = JumpClock()
        clock.cooling(10.0)
        clock.cooled(15.0)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "jump_timing.json")
            clock.save(path)
            self.assertEqual(JumpClock.load(path).cooldown["other"], [5.0])
            Path(path).write_text(json.dumps({"samples": {"hyperspace": {"lead": [15.1]}}}), encoding="utf-8")
            older = JumpClock.load(path)
            self.assertEqual((older.samples["hyperspace"]["lead"], older.cooldown["other"]), ([15.1], []))


class Deck(DashboardJumpInfoMixin):
    def __init__(self, folder):
        self.folder = folder
        self.current_fsd_charging = self.current_fsd_hyperdrive_charging = self.current_fsd_jumping = False
        self.hurried = []
        deck = self

        class Watcher:
            def hurry(self, seconds):
                deck.hurried.append(seconds)
        self.watcher = Watcher()

    def _profile_path(self, filename):
        return os.path.join(self.folder, filename)

    def status(self, written, charging=False, hyper=False, jumping=False, cooling=False):
        was = (self.current_fsd_charging, self.current_fsd_hyperdrive_charging, self.current_fsd_jumping,
               getattr(self, "current_fsd_cooldown", False))
        self.current_fsd_charging, self.current_fsd_hyperdrive_charging, self.current_fsd_jumping = charging, hyper, jumping
        self.current_fsd_cooldown = cooling
        self._jump_clock_status({"Flags": 0, "_written": written}, was)


class DashboardJumpClockTests(unittest.TestCase):
    def test_status_writes_and_journal_events_drive_the_clock_and_save_it(self):
        with tempfile.TemporaryDirectory() as folder:
            deck = Deck(folder)
            pressed = time.time() - 9.5
            deck.status(pressed, charging=True, hyper=True)
            self.assertEqual(deck._jump_clock_view()["press"], int(round(pressed * 1000)),
                             "the press is Status.json's own write time")
            self.assertEqual(deck.hurried[-1], 45.0, "the watcher checks often while a jump is under way")
            deck._jump_clock_event("StartJump", {"JumpType": "Hyperspace", "StarSystem": "Sol"})
            deck.status(pressed + 9.5, charging=False, jumping=True)
            self.assertTrue(deck._jump_clock_view()["jumped"])
            deck._jump_clock_event("FSDJump", {"StarSystem": "Sol"})
            self.assertEqual(deck.hurried[-1], 0)
            saved = json.loads(Path(folder, "jump_timing.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["samples"]["hyperspace"]["lead"], [9.5])
            # A replayed journal at startup never touches the clock.
            deck._jump_clock_event("StartJump", {"JumpType": "Hyperspace"}, startup_replay=True)
            self.assertIsNone(deck._jump_clock_view())
            # The cooldown after it: the bit rises and falls, and is saved.
            deck.status(pressed + 10, cooling=True)
            self.assertEqual(deck._jump_clock_cooldown_view()["after"], "hyperspace")
            deck.status(pressed + 20.5)
            self.assertIsNone(deck._jump_clock_cooldown_view())
            saved = json.loads(Path(folder, "jump_timing.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["cooldown"]["hyperspace"], [10.5])


class RouteRetargetTests(unittest.TestCase):
    """On a route Elite targets the next system itself, mid-jump (FSDTarget
    comes 5-20 s before FSDJump), and Status' Destination follows as the jump
    ends. That plays no SYSTEM TARGET; a target the commander picks still does."""

    def deck(self):
        deck = MainDashboard.__new__(MainDashboard)
        deck._navigation_target_status_seen = True
        deck._navigation_jump_phase = ""
        deck.pulses = []
        deck._publish_navigation_transient = lambda kind, label, *args: deck.pulses.append(label) or True
        return deck

    def test_the_routes_own_next_system_after_a_jump_plays_no_target(self):
        deck = self.deck()
        old, new = {"System": 1, "Name": "Old Star"}, {"System": 2, "Name": "Next Star"}
        deck._navigation_jump_phase = "hyperspace"
        self.assertFalse(deck._observe_navigation_target_transition(old, new))
        self.assertFalse(deck._observe_navigation_hud_event("FSDTarget", {"Name": "Next Star"}, {}))
        deck._navigation_jump_phase = ""
        deck._navigation_last_arrival = time.monotonic() - 4
        self.assertFalse(deck._observe_navigation_target_transition(old, new))
        self.assertFalse(deck._observe_navigation_target_transition(new, {}), "the route's end clears it quietly too")
        # A body in the new system is the commander's own pick.
        self.assertTrue(deck._observe_navigation_target_transition(new, {"System": 2, "Body": 3, "Name": "Next Star 1"}))
        self.assertEqual(deck.pulses, ["BODY TARGET"])

    def test_a_system_the_commander_targets_still_shows(self):
        deck = self.deck()
        deck._navigation_last_arrival = time.monotonic() - 60
        self.assertTrue(deck._observe_navigation_target_transition({}, {"System": 9, "Name": "Colonia"}))
        self.assertTrue(deck._observe_navigation_target_transition({"System": 9, "Name": "Colonia"}, {}))
        self.assertEqual(deck.pulses, ["SYSTEM TARGET", "TARGET CLEARED"])


class WatcherTests(unittest.TestCase):
    def test_status_carries_its_write_time_and_jumps_are_checked_often(self):
        with tempfile.TemporaryDirectory() as folder:
            status = Path(folder, "Status.json")
            status.write_text(json.dumps({"Flags": 131072}), encoding="utf-8")
            os.utime(status, (1700000000.25, 1700000000.25))
            watcher = JournalWatcher(folder)
            seen = []
            watcher.status_callback = seen.append
            watcher._check_special_files()
            self.assertEqual(seen[-1]["_written"], 1700000000.25)
            watcher._startup_catchup_done = True
            self.assertEqual(watcher._cycle_pause(), 1.0)
            watcher.hurry(45)
            self.assertEqual(watcher._cycle_pause(), .2)
            watcher.hurry(0)
            self.assertEqual(watcher._cycle_pause(), 1.0)


def clock(now_ms, **fields):
    base = {"kind": "hyperspace", "press": None, "start": None, "jump": None, "jumped": False, "arrive": None, "exact": False}
    base.update(fields)
    return base


class JumpClockHudTests(unittest.TestCase):
    # The navigation scene tests' page harness, with a browser of our own.
    open = scene_tests.NavigationSceneBrowserTests.open
    render = scene_tests.NavigationSceneBrowserTests.render

    @classmethod
    def setUpClass(cls):
        scene_tests.NavigationSceneBrowserTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        scene_tests.NavigationSceneBrowserTests.tearDownClass.__func__(cls)

    def charge(self, page, label="HYPER CHARGE", reduced=False, **fields):
        now = page.evaluate("Date.now()")
        state = hud_state(label)
        state["jump_clock"] = clock(now, **{key: (now + value if key in {"press", "start", "jump", "arrive"} and value is not None else value)
                                            for key, value in fields.items()})
        self.render(page, state, reduced=reduced)
        return now

    def readout(self, page):
        return page.locator("#instrument-readout").text_content()

    def test_the_rail_counts_the_last_seconds_down_to_the_jump(self):
        page = self.open()
        self.charge(page, press=-6000, jump=2600, exact=True)
        self.assertEqual(page.locator("#instrument").get_attribute("data-instrument"), "jump")
        self.assertEqual(self.readout(page), "JUMP IN 3")
        self.assertIn("count-pop", page.locator("#instrument-readout").get_attribute("class"))
        transition = page.evaluate("document.getElementById('instrument-fill').style.transition")
        self.assertRegex(transition, r"transform \d+ms linear")
        page.wait_for_function("document.getElementById('instrument-readout').textContent === 'JUMP IN 2'", timeout=2500)
        page.wait_for_function("document.getElementById('instrument-readout').textContent === 'ENGAGE'", timeout=4000)

    def test_long_before_the_count_it_reads_charging_and_unmeasured_never_counts(self):
        page = self.open()
        self.charge(page, press=-1000, jump=9000, exact=True)
        self.assertEqual(self.readout(page), "FSD CHARGING")
        self.charge(page, press=-3000, exact=False)
        self.assertEqual(self.readout(page), "FSD CHARGING")
        self.assertIn("unmeasured", page.locator("#instrument").get_attribute("class"))
        page.wait_for_timeout(1200)
        self.assertEqual(self.readout(page), "FSD CHARGING")

    def test_the_tunnel_fills_to_the_arrival_and_supercruise_has_its_own_words(self):
        page = self.open()
        self.charge(page, label="HYPERSPACE", jump=-3000, jumped=True, arrive=12000, exact=True)
        self.assertEqual(self.readout(page), "WITCH SPACE")
        filled = page.evaluate("new DOMMatrix(getComputedStyle(document.getElementById('instrument-fill')).transform).a")
        self.assertTrue(.15 < filled < .45, filled)
        self.assertGreater(page.evaluate("navigationScene.state.travel"), .15)
        self.charge(page, label="FSD CHARGE", kind="supercruise", press=-2000, jump=1500, exact=True)
        self.assertEqual(self.readout(page), "SUPERCRUISE IN 2")
        # A clock on a state that is not a jump shows nothing of it.
        self.charge(page, label="FLIGHT", press=-2000, jump=1500, exact=True)
        self.assertNotEqual(page.locator("#instrument").get_attribute("data-instrument"), "jump")
        self.assertEqual(self.readout(page), "")

    def test_the_scene_builds_with_the_charge_and_beats_each_second(self):
        page = self.open()
        self.charge(page, press=-5000, jump=5000, exact=True)
        page.wait_for_function("navigationScene.state.charge > .45", timeout=3000)
        self.assertLess(page.evaluate("navigationScene.state.charge"), .7)
        self.charge(page, press=-8000, jump=1700, exact=True)
        page.wait_for_function("navigationScene.state.beat > .5", timeout=2500)
        # Unmeasured, the charge builds but never reaches the jump.
        self.charge(page, press=-2000, exact=False)
        page.evaluate("navigationScene.state.age = 600")
        page.wait_for_timeout(500)
        self.assertLess(page.evaluate("navigationScene.state.charge"), .86)

    def test_reduced_motion_steps_the_rail_and_still_paints_the_charge(self):
        page = self.open()
        self.charge(page, press=-5000, jump=5000, exact=True, reduced=True)
        self.assertEqual(page.evaluate("document.getElementById('instrument-fill').style.transition"), "none")
        filled = page.evaluate("new DOMMatrix(getComputedStyle(document.getElementById('instrument-fill')).transform).a")
        self.assertTrue(.4 < filled < .6, filled)
        self.assertFalse(page.evaluate("navigationScene.running"))
        self.assertTrue(.4 < page.evaluate("navigationScene.state.charge") < .6)

    def test_counting_scenes_stay_cheap_to_draw(self):
        page = self.open()
        worst = []
        for label, fields in (("HYPER CHARGE", {"press": -8000, "jump": 3000, "exact": True}),
                              ("FSD CHARGE", {"kind": "supercruise", "press": -3000, "jump": 3000, "exact": True}),
                              ("HYPERSPACE", {"jump": -2000, "jumped": True, "arrive": 12000, "exact": True})):
            self.charge(page, label=label, **fields)
            page.wait_for_timeout(600)
            cost = page.evaluate("""() => new Promise((resolve, reject) => {
              const scene = navigationScene, draw = scene.draw, samples = [];
              const timeout = setTimeout(() => { scene.draw = draw; reject(Error('no frames')); }, 5000);
              scene.draw = function(now) {
                const start = performance.now();
                draw.call(this, now);
                samples.push(performance.now() - start);
                if (samples.length === 30) {
                  scene.draw = draw; clearTimeout(timeout);
                  samples.sort((a, b) => a - b);
                  resolve(samples[Math.ceil(samples.length * .9) - 1]);
                }
              };
            })""")
            worst.append((label, cost))
        self.assertLess(max(cost for _, cost in worst), 4.0, worst)


if __name__ == "__main__":
    unittest.main()
