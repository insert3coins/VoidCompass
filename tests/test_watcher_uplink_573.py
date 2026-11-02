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
NOW = 1_800_000_000
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
    def test_selling_returns_two_results_without_a_third_nearest_station(self):
        best = [dict(BEST[0], updated=NOW - 3600), dict(BEST[1], updated=NOW - 7200)]
        lines = copilot.uplink_lines("sell", "Painite", best, NEAR, "Colonia", 50, now=NOW)
        self.assertEqual(lines, [
            "Through the uplink, places to sell Painite within 50 light years, prices from the last 24 hours first: Hub in Colonia: "
            "520,000 credits a tonne, demand 800, 12.4 light years away, large pads, prices 1 hour old",
            "Second result: Ratraii Port in Ratraii: 480,000 credits a tonne, demand 200, 30.0 light years away, medium pads, prices 2 hours old"])

    def test_recent_prices_come_before_higher_stale_prices_and_duplicates_use_the_latest_report(self):
        fresh = dict(BEST[0], updated=NOW - 86400, price=100)
        stale_duplicate = dict(fresh, updated=NOW - 3 * 86400, price=999999)
        stale = dict(BEST[1], updated=NOW - 86401, price=800000)
        unknown = dict(NEAR[0], price=900000)
        rows = copilot.uplink_sell_results([stale_duplicate, stale, fresh, unknown], NOW)
        self.assertEqual(rows, [fresh, stale])
        lines = copilot.uplink_lines("sell", "Painite", [stale_duplicate, stale, fresh, unknown], now=NOW)
        self.assertEqual(len(lines), 2)
        self.assertIn("prices 1 day old", lines[0])
        self.assertIn("100 credits a tonne", lines[0])
        self.assertIn("800,000 credits a tonne", lines[1])

    def test_missing_dates_are_labelled_and_one_buyer_is_not_repeated(self):
        unknown = dict(BEST[0], market_id=None)
        duplicate = dict(unknown, station="HUB", system="COLONIA")
        lines = copilot.uplink_lines("sell", "Painite", [unknown, duplicate], now=NOW)
        self.assertEqual(len(lines), 1)
        self.assertIn("price age unknown", lines[0])

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
        self.assertNotIn("Jaques Station", reply["text"])
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


def spansh_reply(*stations, updated=NOW - 3600):
    return {"results": [{"name": name, "system_name": system, "distance": distance, "has_large_pad": True,
                         "market_updated_at": updated,
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
        replies = [spansh_reply(("Hub", "Colonia", 12.4, 520000), ("Ratraii Port", "Ratraii", 30.0, 480000))]
        with mock.patch("voidcompass.services.spansh.commodity_stations", side_effect=replies) as search, \
                mock.patch("voidcompass.dashboard.dashboard_watcher_voice_mixin.time.time", return_value=NOW):
            said = deck._watcher_mind_action("Where can I sell painite?")
        self.assertTrue(said["waiting"])
        self.assertIn("Painite", said["say"])
        search.assert_called_once()
        best_call = search.call_args
        self.assertEqual(best_call.args[:4], ("sell", "Colonia", "Painite", 12), "your tonnage, from the hold")
        self.assertEqual(best_call.kwargs["sort"], "price")
        self.assertEqual(best_call.kwargs["radius"], 50, "the Sell cargo radius")
        self.assertEqual(best_call.kwargs["max_age_days"], 1)
        (words, lines), = deck.mind.answers
        self.assertEqual(words, "Where can I sell painite?")
        self.assertIn("Hub in Colonia: 520,000 credits a tonne", lines[0])
        self.assertEqual(len(lines), 2)
        self.assertIn("Ratraii Port", lines[-1])

    def test_fewer_recent_reports_are_filled_with_older_buyers_using_the_same_filters(self):
        deck = Deck()
        recent = spansh_reply(("Hub", "Colonia", 12.4, 520000))
        older = spansh_reply(("Hub", "Colonia", 12.4, 900000), ("Ratraii Port", "Ratraii", 30, 800000), updated=NOW - 3 * 86400)
        with mock.patch("voidcompass.services.spansh.commodity_stations", side_effect=[recent, older]) as search, \
                mock.patch("voidcompass.dashboard.dashboard_watcher_voice_mixin.time.time", return_value=NOW):
            deck._watcher_mind_action("Where can I sell painite?")
        fresh_call, fallback_call = search.call_args_list
        self.assertEqual(fresh_call.kwargs["max_age_days"], 1)
        self.assertNotIn("max_age_days", fallback_call.kwargs)
        for call in (fresh_call, fallback_call):
            self.assertEqual(call.kwargs["sort"], "price")
            self.assertEqual(call.kwargs["radius"], 50)
            self.assertFalse(call.kwargs["carriers"])
            self.assertEqual(call.args[3], 12)
        lines = deck.mind.answers[0][1]
        self.assertEqual(len(lines), 2)
        self.assertIn("Hub in Colonia: 520,000", lines[0])
        self.assertIn("Ratraii Port", lines[1])
        self.assertIn("prices 3 days old", lines[1])

    def test_buying_keeps_its_existing_queries(self):
        deck = Deck()
        with mock.patch("voidcompass.services.spansh.commodity_stations", return_value={"results": []}) as search:
            deck._watcher_mind_action("Where can I buy tritium?")
        self.assertEqual(search.call_count, 2)
        self.assertTrue(all("max_age_days" not in call.kwargs for call in search.call_args_list))

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
