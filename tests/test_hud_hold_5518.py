"""5.5.18: the Navigation HUD keeps what you were doing. When nothing needs
the screen it no longer drops straight back to NAV: a fight stays up a
little while after it, a mining visit until you're back in supercruise, and
a system's survey until you jump or it's done."""

import unittest
from unittest.mock import Mock

from voidcompass.overlays import hud_pages as hp

ENABLED = list(hp.PAGES)


class HoldTests(unittest.TestCase):
    def test_the_survey_stays_until_you_jump_or_it_is_done(self):
        memory, facts = {}, {"system": "Col 285 Sector AB-C d14-7"}
        hp.remember_page(memory, "survey", {"motion": "scanner"}, facts, 0.0)
        self.assertEqual(hp.hold_page("nav", memory, facts, 5.0, ENABLED), "survey", "out of the FSS, still surveying")
        self.assertEqual(hp.hold_page("planet", memory, facts, 5.0, ENABLED), "planet", "something that needs the screen wins")
        self.assertEqual(hp.hold_page("nav", memory, facts, 5.0, ENABLED, survey_left=lambda: False), "nav", "the system is done")
        self.assertEqual(hp.hold_page("nav", memory, {"system": "Next system"}, 5.0, ENABLED), "nav", "a new system starts afresh")
        self.assertEqual(hp.hold_page("nav", memory, facts, 5.0, [page for page in ENABLED if page != "survey"]), "nav",
                         "not with the survey page switched off")

    def test_a_fight_stays_a_little_while(self):
        memory = {}
        hp.remember_page(memory, "combat", {"motion": "combat"}, {}, 100.0)
        self.assertEqual(hp.hold_page("nav", memory, {}, 100.0 + hp.COMBAT_HOLD_S - 1, ENABLED), "combat")
        self.assertEqual(hp.hold_page("nav", memory, {}, 100.0 + hp.COMBAT_HOLD_S + 1, ENABLED), "nav")

    def test_a_mining_visit_stays_until_supercruise(self):
        memory = {}
        hp.remember_page(memory, "mining", {"motion": "asteroid_field"}, {}, 0.0)
        hp.remember_page(memory, "nav", {"motion": "flight"}, {}, 60.0)
        self.assertEqual(hp.hold_page("nav", memory, {}, 60.0, ENABLED), "mining", "still out among the rocks")
        hp.remember_page(memory, "nav", {"motion": "supercruise"}, {}, 90.0)
        self.assertEqual(hp.hold_page("nav", memory, {}, 90.0, ENABLED), "nav", "gone once you're back in supercruise")


class DeckTests(unittest.TestCase):
    def test_the_hud_stays_on_survey_out_of_the_fss(self):
        from voidcompass.dashboard.dashboard_hud_pages_mixin import DashboardHudPagesMixin

        class Deck(DashboardHudPagesMixin):
            pass

        def facts(**extra):
            base = {"docked": False, "on_planet": False, "in_rhino": False, "rigs_here": False, "at_colony": False,
                    "on_own_carrier": False, "prospecting": False, "target": False, "trading": False,
                    "has_jump": False, "has_carrier": False, "system": deck.current_sys}
            return {**base, **extra}

        deck = Deck()
        deck.config = {"hud_pages": "auto", "overlay_enabled": True}
        deck.hud = Mock()
        deck.current_sys = "Synuefe XR-H d11-102"
        deck._hud_pages_facts = facts
        deck._hud_page_build = lambda page: {"id": page, "blocks": []}
        deck._hud_survey_left = lambda: True
        deck.hud._html_last_model = {"state": {"motion": "scanner", "category": "scan"}}
        self.assertEqual(deck._hud_pages_payload()["active"], "survey")
        deck.hud._html_last_model = {"state": {"motion": "supercruise", "category": "drive"}}
        self.assertEqual(deck._hud_pages_payload()["active"], "survey", "out of the FSS, flying to a body")
        deck.hud._html_last_model = {"state": {"motion": "fsd_charge", "category": "drive"}}
        deck._hud_pages_facts = lambda: facts(has_jump=True)
        self.assertEqual(deck._hud_pages_payload()["active"], "jump", "charging to jump: the jump page")
        deck.current_sys = "Plaa Aec IZ-N c20-1"
        deck._hud_pages_facts = facts
        deck.hud._html_last_model = {"state": {"motion": "supercruise", "category": "drive"}}
        self.assertEqual(deck._hud_pages_payload()["active"], "nav", "the next system starts on NAV")


if __name__ == "__main__":
    unittest.main()
