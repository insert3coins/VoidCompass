"""Talk along a route, and a Chatty that stays chatty (5.7.5)."""
import random
import unittest
from unittest import mock  # noqa: F401  (unittest.mock below)

from voidcompass.core import companions
from voidcompass.overlays import companion_personas, route_lines, watcher_mind
from tests.test_aster_companion import Clock

CREW = ("watcher", "aster", "axiom", "meridian", "lyra")


def mind(identity, frequency="chatty", seed=1):
    config = {"companion_identity": identity, f"{identity}_thoughts": frequency, "heartbeat_thoughts": frequency}
    companion = companions.create_mind(None, config, clock=Clock(), rng=random.Random(seed))
    companion.memory["hours"] = 20
    companion.session_start()
    return companion


def target(companion, left, star="K"):
    return companion.observe("FSDTarget", {"event": "FSDTarget", "Name": f"Next {left}", "StarClass": star,
                                           "RemainingJumpsInRoute": left})


def jump(companion, name="Somewhere", dist=30.0):
    companion.clock.now += 400  # past every rest, so only the route decides
    return companion.observe("FSDJump", {"event": "FSDJump", "StarSystem": name, "JumpDist": dist, "StarPos": [0, 0, 0]})


class RouteTests(unittest.TestCase):
    def test_a_route_is_plotted_counted_down_and_finished(self):
        with unittest.mock.patch.object(watcher_mind.WatcherMind, "_said_recently", return_value=False):
            for identity in CREW:
                companion = mind(identity)
                companion.random.random = lambda: 0.0  # always speak when allowed
                companion.clock.now += 60  # past the session's opening remark
                heard = [(target(companion, 12) or {}).get("topic")]
                for left in range(12, 0, -1):
                    thought = jump(companion, f"Next {left}")
                    heard.append(thought["topic"] if thought else None)
                    if left > 1:
                        target(companion, left - 1)
                for topic in ("route_plotted", "route_halfway", "route_progress", "route_last", "route_done"):
                    self.assertIn(topic, heard, identity)
                self.assertEqual(heard.count("route_progress"), 1, "five to go, once")
                self.assertIsNone(companion._route_left, "the route is over")

    def test_the_journals_own_order_counts_right_to_the_end(self):
        """As Elite writes it (5.7.6): the next leg is targeted mid-jump,
        before the arrival, and the route is cleared during the last jump.
        "Last jump" with one to go, and "route done" on arriving."""
        with unittest.mock.patch.object(watcher_mind.WatcherMind, "_said_recently", return_value=False):
            companion = mind("lyra")
            companion.random.random = lambda: 0.0
            companion.clock.now += 60
            companion.observe("NavRoute", {"event": "NavRoute"})
            names = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]
            self.assertEqual(companion.observe("FSDTarget", {"event": "FSDTarget", "Name": "Alpha", "StarClass": "K",
                                                             "RemainingJumpsInRoute": 6})["topic"], "route_plotted")
            heard = {}
            for index, name in enumerate(names):
                companion.observe("StartJump", {"event": "StartJump", "JumpType": "Hyperspace", "StarSystem": name, "StarClass": "K"})
                if index + 1 < len(names):
                    companion.observe("FSDTarget", {"event": "FSDTarget", "Name": names[index + 1], "StarClass": "K",
                                                    "RemainingJumpsInRoute": len(names) - index - 1})
                else:
                    companion.observe("NavRouteClear", {"event": "NavRouteClear"})
                heard[name] = ((jump(companion, name) or {}).get("topic"), companion._route_left)
            self.assertEqual(heard["Echo"], ("route_last", 1), "one jump to go")
            self.assertEqual(heard["Foxtrot"], ("route_done", None), "said on arriving at the end")
            self.assertEqual(heard["Alpha"][1], 5)
            self.assertNotIn("route_done", [topic for topic, _left in list(heard.values())[:-1]])

    def test_short_routes_and_cleared_routes_stay_quiet(self):
        companion = mind("meridian")
        self.assertIsNone(target(companion, 3), "three jumps isn't worth announcing")
        companion.observe("NavRouteClear", {"event": "NavRouteClear"})
        self.assertIsNone(companion._route_left)
        self.assertNotIn((jump(companion) or {}).get("topic"), {"route_done", "route_last"})

    def test_the_star_comes_from_the_target_not_the_jump(self):
        companion = mind("axiom")
        companion.observe("StartJump", {"event": "StartJump", "JumpType": "Hyperspace", "StarClass": "G"})
        self.assertEqual(companion._next_star, "G")
        jump(companion)
        self.assertEqual(companion._next_star, "", "used up by the arrival")
        self.assertEqual(route_lines.simple_class("M_RedGiant"), "M")
        self.assertEqual(route_lines.simple_class("N"), "")

    def test_a_star_with_no_fuel_is_named_on_a_route(self):
        self.assertEqual(route_lines.kind("N"), "neutron star")
        self.assertEqual(route_lines.kind("DAB"), "white dwarf")
        self.assertEqual(route_lines.kind("AeBe"), "Herbig Ae/Be star")
        self.assertEqual(route_lines.kind("K"), "")
        self.assertEqual(route_lines.kind("A_BlueWhiteSuperGiant"), "")
        companion = mind("aster")
        companion.random.random = lambda: 0.0
        target(companion, 8, star="N")
        target(companion, 7, star="N")  # the route's already plotted
        thought = jump(companion)
        self.assertEqual(thought["topic"], "no_scoop")
        self.assertIn("neutron star", thought["text"])

    def test_every_companion_has_every_route_topic_in_both_styles(self):
        for topic in route_lines.IMPORTANCE:
            self.assertGreaterEqual(len(watcher_mind.TOPICS[topic][1]), 10, topic)
            self.assertGreaterEqual(len(watcher_mind.WEARY[topic]), 10, topic)
            for identity in ("aster", "axiom", "meridian", "lyra"):
                lines = companion_personas.get(identity).lines
                self.assertGreaterEqual(len(lines.event_lines(topic)), 10, (identity, topic))
                self.assertGreaterEqual(len(lines.event_lines(topic, True)), 4, (identity, topic))
        self.assertEqual(companion_personas.get("meridian").interests["route_last"], 2, "the navigator's own business")


class ChattyTests(unittest.TestCase):
    def test_chatty_starts_a_new_round_where_occasional_goes_quiet(self):
        for identity in CREW:
            for frequency, speaks in (("chatty", True), ("occasional", False)):
                companion = mind(identity, frequency)
                # The Watcher is weary by default, with its own set of lines.
                lines = companion.event_lines("scooped") if identity != "watcher" else watcher_mind.WEARY["scooped"]
                said = []
                for _ in range(len(lines) + 3):
                    companion.clock.now += 3600
                    thought = companion.consider("scooped", {}, force=True)
                    said.append(thought["text"] if thought else None)
                used, after = said[:len(lines)], said[len(lines):]
                self.assertEqual(len(set(used)), len(lines), (identity, "every line once first"))
                self.assertEqual(all(after), speaks, (identity, frequency))
                if speaks:
                    self.assertNotEqual(after[0], used[-1], "never the same line twice in a row")

    def test_chatty_rests_less_and_speaks_up_more(self):
        chatty, occasional = watcher_mind.FREQUENCIES["chatty"], watcher_mind.FREQUENCIES["occasional"]
        self.assertLess(chatty["rest"], occasional["rest"])
        self.assertGreater(chatty.get("boost", 0), 0)
        self.assertNotIn("boost", occasional)
        self.assertFalse(occasional.get("cycle"))


if __name__ == "__main__":
    unittest.main()
