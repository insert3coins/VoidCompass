"""5.5.3.1: the Mission Directive and the Focused Log know the newer
features: fuel, rare worlds, Codex colours, trade routes, colonisation."""

import unittest
from pathlib import Path

from voidcompass.exploration.explorer_decision_deck import explorer_decision, field_cues

ROOT = Path(__file__).resolve().parents[1]


def decide(cues, doctrine="balanced", actions=(), flight=None):
    return explorer_decision(doctrine, {}, {}, actions, flight or {}, {}, {}, {}, cues=cues)


class DirectiveCueTests(unittest.TestCase):
    def test_no_facts_no_cues(self):
        self.assertEqual(field_cues({}), [])

    def test_low_fuel_comes_first_and_warns(self):
        cues = field_cues({"fuel": {"percent": 18, "threshold_pct": 25, "docked": False, "scoopable_here": True}})
        survey = [{"id": "complete-fss", "kind": "survey", "priority": 110, "title": "Complete the FSS survey"}]
        decision = decide(cues, actions=survey)
        self.assertEqual(decision["id"], "low-fuel")
        self.assertEqual(decision["severity"], "WARN")
        self.assertIn("SCOOP FUEL", decision["title"])
        # Docked, or above the warning level: no cue.
        self.assertEqual(field_cues({"fuel": {"percent": 18, "threshold_pct": 25, "docked": True}}), [])
        self.assertEqual(field_cues({"fuel": {"percent": 60, "threshold_pct": 25}}), [])

    def test_a_green_gas_giant_leads_unless_mapped(self):
        worlds = [{"body": "A 4", "label": "GREEN GAS GIANT", "rarity": 4, "green": True, "mapped": False}]
        decision = decide(field_cues({"rare_worlds": worlds}))
        self.assertIn("GREEN GAS GIANT", decision["title"])
        self.assertEqual(decision["primary"]["target"], "explore")
        self.assertEqual(decision["confidence"], "LIVE FIELD CUE")
        self.assertEqual(field_cues({"rare_worlds": [dict(worlds[0], mapped=True)]}), [])

    def test_codex_colour_and_doctrine(self):
        cues = field_cues({"codex_new": {"body": "Prai 4"}})
        self.assertIn("PRAI 4", decide(cues, doctrine="codex")["title"])

    def test_trade_and_colonisation(self):
        trade = {"done": False, "action": "Buy 720 t Gold", "station": "Ray Gateway", "system": "Diaguandri",
                 "hop": 1, "hops": 3, "here": True}
        decision = decide(field_cues({"trade": trade}))
        self.assertEqual(decision["primary"]["target"], "trading")
        self.assertIn("RAY GATEWAY", decision["title"])
        colony = {"header": "Orbis at Col 285", "remaining": 4200, "trips": 6, "at_site": False}
        cue = field_cues({"colony": colony})[0]
        self.assertIn("4,200 t", cue["title"])
        self.assertIn("6 trips", cue["detail"])

    def test_focused_log_shows_the_new_parts(self):
        html = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        for node in ("flightlog-directive-primary", "flightlog-directive-tags", "flightlog-watcher",
                     "flightlog-flown", "flightlog-earned", "flightlog-firsts", "flightlog-rare"):
            self.assertIn(f'id="{node}"', html)


if __name__ == "__main__":
    unittest.main()
