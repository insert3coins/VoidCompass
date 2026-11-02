"""5.7.3: the Watcher's uplink. Asked where to sell or buy a commodity (or to
look it up online), it runs the Trading page's Spansh search in the
background, says so now, and answers your question from what Spansh sends
when it comes. Spansh is faked; replies use the ship's plain wording."""

import unittest
from unittest import mock

from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.overlays import watcher_copilot as copilot
from voidcompass.overlays import watcher_mind

PAINITE = [("painite", "Painite")]
BEST = [{"station": "Hub", "system": "Colonia", "distance": 12.4, "price": 520000, "stock": 800, "pad": "L", "market_id": 1},
        {"station": "Ratraii Port", "system": "Ratraii", "distance": 30.0, "price": 480000, "stock": 200, "pad": "M",
         "market_id": 2}]
NEAR = [{"station": "Jaques Station", "system": "Colonia", "distance": 0, "price": 300000, "stock": 20, "pad": "L",
         "market_id": 3}]


class RequestTests(unittest.TestCase):
    def test_what_the_uplink_answers(self):
        self.assertEqual(copilot.uplink_request("Where can I sell painite?", PAINITE), {"kind": "sell", "commodity": "Painite"})
        self.assertEqual(copilot.uplink_request("Look up the best place to sell painite", PAINITE)["kind"], "sell")
        self.assertEqual(copilot.uplink_request("Who sells painite near here?", PAINITE)["kind"], "buy")
        self.assertEqual(copilot.uplink_request("Where can I buy painite cheapest?", PAINITE)["kind"], "buy")
        self.assertEqual(copilot.uplink_request("Can you look it up online?", []), {"kind": None, "commodity": ""})

    def test_what_stays_local(self):
        self.assertIsNone(copilot.uplink_request("What's painite going for?", PAINITE), "the market file answers that")
        self.assertIsNone(copilot.uplink_request("Where can I sell exploration data?", []), "the data, not the uplink")
        self.assertIsNone(copilot.uplink_request("How are you?", []))


class LineTests(unittest.TestCase):
    def test_the_best_the_next_and_the_nearest(self):
        lines = copilot.uplink_lines("sell", "Painite", BEST, NEAR, "Colonia", 50)
        self.assertEqual(lines, [
            "Through the uplink, the best place to sell Painite within 50 light years: Hub in Colonia: "
            "520,000 credits a tonne, demand 800, 12.4 light years away, large pads",
            "Next best: Ratraii Port in Ratraii: 480,000 credits a tonne, demand 200, 30.0 light years away, medium pads",
            "The nearest station that buys Painite: Jaques Station in Colonia: 300,000 credits a tonne, demand 20, "
            "in this system, large pads"])

    def test_buying_and_the_age_of_the_prices(self):
        row = {"station": "Depot", "system": "Sol", "distance": 4.2, "price": 9000, "stock": 5000, "market_id": 9,
               "updated": 0.0, "carrier": True}
        lines = copilot.uplink_lines("buy", "Tritium", [dict(row, updated=1000.0)], [dict(row)], "Alpha Centauri", 50,
                                     now=1000.0 + 3 * 86400)
        self.assertEqual(lines, ["Through the uplink, the best place to buy Tritium within 50 light years: Depot in Sol: "
                                 "9,000 credits a tonne, stock 5,000, 4.2 light years away, a fleet carrier, "
                                 "prices 3 days old"], "the nearest is the same station: said once")

    def test_nothing_found_and_a_failure(self):
        self.assertIn("knows no station near Colonia that buys Painite", copilot.uplink_lines("sell", "Painite", system="Colonia")[0])
        self.assertEqual(copilot.uplink_lines("sell", "Painite", error="timed out"),
                         ["The uplink to Spansh failed: timed out"])


class MindTests(unittest.TestCase):
    def test_said_now_answered_when_it_replies(self):
        mind = watcher_mind.WatcherMind(None, {})
        mind.action_provider = lambda words: {"waiting": True, "say": "Opening the uplink."}
        self.assertTrue(mind.talk("Where can I sell painite?"))
        self.assertEqual(mind.current()["text"], "Opening the uplink.")
        self.assertTrue(mind.talk_waiting(), "the page keeps its dots while the uplink asks")
        self.assertEqual(mind.memory["talk"][-1]["it"], "", "the answer, not the opening line, goes in the talk")
        lines = copilot.uplink_lines("sell", "Painite", BEST, NEAR, "Colonia", 50)
        self.assertTrue(mind.uplink_answer("Where can I sell painite?", lines))
        reply = mind.current()
        self.assertEqual(reply["text"], copilot.plain_answer(lines))
        self.assertIn("520,000 credits a tonne", reply["text"])
        self.assertIn("Jaques Station", reply["text"])
        self.assertEqual(mind.memory["talk"][-1]["it"], reply["text"])
        self.assertFalse(mind.talk_waiting())

    def test_a_late_reply_to_an_old_question_is_dropped(self):
        mind = watcher_mind.WatcherMind(None, {})
        mind.action_provider = lambda words: {"waiting": True, "say": "Opening the uplink."} if "sell" in words else None
        mind.talk("Where can I sell painite?")
        mind.talk("Where are we?")
        self.assertFalse(mind.uplink_answer("Where can I sell painite?", ["Hub in Colonia"]))


class FakeNames:
    def spansh_name(self, text):
        return str(text)

    def all_names(self):
        return ["Painite", "Tritium"]


class FakeMind:
    def __init__(self):
        self.answers = []
        self.random = None

    def uplink_answer(self, words, lines):
        self.answers.append((words, lines))
        return True


def spansh_reply(*stations):
    return {"results": [{"name": name, "system_name": system, "distance": distance, "has_large_pad": True,
                         "market": [{"commodity": "Painite", "sell_price": price, "demand": 500}]}
                        for name, system, distance, price in stations]}


class Deck(DashboardWatcherVoiceMixin):
    def __init__(self, online=True):
        self.config = {}
        self.mind = FakeMind()
        self.heartbeat_hud = type("Hud", (), {"mind": self.mind})()
        self.trading_names = FakeNames()
        self.current_sys = "Colonia"
        self.online = online
        self.tasks = []

    def _trading_online(self):
        return self.online

    def _trading_cargo_options(self, payload=None):
        return {"radius": 50, "large": False, "carriers": False, "planetary": True}

    def _trading_cargo(self):
        return [{"symbol": "painite", "name": "Painite", "count": 12, "stolen": 0}]

    def _trading_spansh_names(self):
        return {}

    def _watcher_market_file(self):
        return {"items": []}

    def _trading_task(self, name, work, on_done, cache_key=None):
        self.tasks.append(cache_key)
        on_done(work(), "")
        return True

    def _ui_post(self, callback, *args, key=None, **kwargs):
        callback(*args, **kwargs)

    def _watcher_mind_watch(self):
        pass


class DeckTests(unittest.TestCase):
    def test_the_uplink_asks_spansh_and_answers(self):
        deck = Deck()
        replies = [spansh_reply(("Hub", "Colonia", 12.4, 520000), ("Ratraii Port", "Ratraii", 30.0, 480000)),
                   spansh_reply(("Jaques Station", "Colonia", 0.0, 300000))]
        with mock.patch("voidcompass.services.spansh.commodity_stations", side_effect=replies) as search:
            said = deck._watcher_mind_action("Where can I sell painite?")
        self.assertTrue(said["waiting"])
        self.assertIn("Painite", said["say"])
        best_call, near_call = search.call_args_list
        self.assertEqual(best_call.args[:4], ("sell", "Colonia", "Painite", 12), "your tonnage, from the hold")
        self.assertEqual(best_call.kwargs["sort"], "price")
        self.assertEqual(best_call.kwargs["radius"], 50, "the Sell cargo radius")
        self.assertNotIn("sort", near_call.kwargs)
        (words, lines), = deck.mind.answers
        self.assertEqual(words, "Where can I sell painite?")
        self.assertIn("Hub in Colonia: 520,000 credits a tonne", lines[0])
        self.assertIn("Jaques Station", lines[-1])

    def test_with_trading_searches_off_it_says_so(self):
        deck = Deck(online=False)
        self.assertIn("uplink is off", deck._watcher_mind_action("Where can I sell painite?"))
        self.assertEqual(deck.tasks, [])

    def test_asked_online_for_nothing_it_can_find(self):
        self.assertIn("Spansh's markets", Deck()._watcher_mind_action("Can you look it up online?"))

    def test_your_cargo_when_no_commodity_is_named(self):
        deck = Deck()
        self.assertEqual(deck._watcher_uplink_commodities("Where can I sell my cargo?"), [("painite", "Painite")])


if __name__ == "__main__":
    unittest.main()
