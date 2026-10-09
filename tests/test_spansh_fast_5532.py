"""Faster trading lookups (after EDNexus): one kept-alive Spansh session,
stations/search instead of the slow /commodity endpoint, filters sent to
Spansh, a disk cache with a time-to-live, and one retry when Spansh is busy."""

import tempfile
import unittest
from unittest.mock import Mock, patch

from voidcompass.services import spansh


def reply(status=200, data=None, headers=None):
    response = Mock(status_code=status, headers=headers or {})
    response.json.return_value = data if data is not None else {"results": []}
    return response


class FastSpanshTests(unittest.TestCase):
    def setUp(self):
        spansh.set_cache_dir(tempfile.mkdtemp())
        self.addCleanup(spansh.set_cache_dir, None)

    def test_commodity_search_asks_for_the_nearest_stations_with_filters(self):
        session = Mock()
        session.post.return_value = reply(data={"results": [{"name": "Ehrlich City"}]})
        session.get.return_value = reply(data={"values": ["Coriolis Starport", "Drake-Class Carrier", "Outpost"]})
        with patch.object(spansh, "http", return_value=session):
            result = spansh.commodity_stations("sell", "Sol", "Gold", 100, large_pad=True, carriers=False, planetary=False)
        self.assertEqual(result["results"][0]["name"], "Ehrlich City")
        url = session.post.call_args.args[0]
        body = session.post.call_args.kwargs["json"]
        self.assertTrue(url.endswith("/stations/search"))
        market = body["filters"]["market"][0]
        self.assertEqual((market["name"], market["demand"]["value"][0], market["demand"]["comparison"]), ("Gold", 100, "<=>"))
        self.assertEqual(body["filters"]["has_large_pad"], {"value": True})
        self.assertEqual(body["filters"]["is_planetary"], {"value": False})
        self.assertEqual(body["filters"]["type"]["value"], ["Coriolis Starport", "Outpost"], "carriers left out")
        self.assertEqual(body["sort"], [{"distance": {"direction": "asc"}}])
        self.assertEqual(body["reference_system"], "Sol")

    def test_a_repeat_comes_from_the_disk_cache(self):
        session = Mock()
        session.post.return_value = reply(data={"results": [{"name": "A"}]})
        with patch.object(spansh, "http", return_value=session):
            spansh.commodity_stations("buy", "Sol", "Gold")
            again = spansh.commodity_stations("buy", "Sol", "Gold")
        self.assertEqual(session.post.call_count, 1)
        self.assertEqual(again["results"][0]["name"], "A")

    def test_a_fresh_station_check_skips_the_cache(self):
        session = Mock()
        session.get.return_value = reply(data={"record": {"name": "Jameson Memorial"}})
        with patch.object(spansh, "http", return_value=session):
            spansh.station_market(128666762)
            spansh.station_market(128666762)
            spansh.station_market(128666762, fresh=True)
        self.assertEqual(session.get.call_count, 2)

    def test_a_busy_spansh_gets_one_retry(self):
        busy, ok = reply(429, headers={"Retry-After": "0"}), reply(200)
        with patch("requests.Session.request", side_effect=[busy, ok]) as send, patch.object(spansh.time, "sleep"):
            response = spansh._Session().request("GET", "https://spansh.co.uk/api/x")
        self.assertIs(response, ok)
        self.assertEqual(send.call_count, 2)

    def test_errors_are_reported_not_cached(self):
        session = Mock()
        session.post.side_effect = [reply(500, data={"error": "boom"}), reply(data={"results": [{"name": "B"}]})]
        with patch.object(spansh, "http", return_value=session):
            with self.assertRaises(spansh.SpanshError):
                spansh.commodity_stations("buy", "Sol", "Gold")
            self.assertEqual(spansh.commodity_stations("buy", "Sol", "Gold")["results"][0]["name"], "B")


if __name__ == "__main__":
    unittest.main()
