"""5.6.8: distinct companions, grounded in growth and live journal cues."""

import json
import random
import unittest

from tests.test_hatchling_563 import HOUR, hatched
from voidcompass.core import hatchling, hatchling_chatter
from voidcompass.core.hatchling_growth_lines import FORM_LINES
from voidcompass.core.hatchling_sample_lines import SAMPLE_LINES
from voidcompass.core.hatchling_species_lines import SPECIES_LINES
from voidcompass.dashboard.dashboard_games_mixin import DashboardGamesMixin


class DistinctChatterTests(unittest.TestCase):
    def pet(self, species, kind="", stage="hatchling", form=""):
        return {"species": species, "kind": kind, "stage": stage, "form": form,
                "dreams": ["Sol"], "world": {"body": "Sol 3"}, "ship": "Krait",
                "toys": [{"label": "a pebble"}], "favourite_food": "Algae",
                "trip": {"to": "Colonia"}}

    def test_five_families_have_distinct_journal_and_companion_lines(self):
        pets = [self.pet("larva"), self.pet("bot"), *(self.pet("sample", kind) for kind in SAMPLE_LINES)]
        for situation in ("jump", "arrive", "touchdown", "danger", "biology", "toy", "answer"):
            pools = [set(hatchling_chatter._pool(pet, situation)) for pet in pets]
            self.assertTrue(all(pool for pool in pools), situation)
            for index, pool in enumerate(pools):
                other = set().union(*(row for n, row in enumerate(pools) if n != index))
                self.assertTrue(pool - other, f"{situation}: companion {index} needs its own words")
                self.assertTrue(all("{" not in line for line in pool))

    def test_banks_cover_the_actual_cues_and_only_known_fields(self):
        from string import Formatter
        supported = {"toy", "food", "dream", "system", "body", "ship", "to"}
        for family, bank in {**SPECIES_LINES, **SAMPLE_LINES}.items():
            with self.subTest(family=family):
                self.assertGreaterEqual(len(bank), 40)
                self.assertTrue(set(hatchling.CUES.values()) <= set(bank))
                for lines in bank.values():
                    for line in lines:
                        fields = {field for _, field, _, _ in Formatter().parse(line) if field}
                        self.assertTrue(fields <= supported, (family, line))
        for pet in (self.pet("larva"), self.pet("bot"), self.pet("sample", "tubus")):
            pet.update(dreams=[], world=None, toys=[], ship="", favourite_food="", trip=None)
            for situation in ("idle", "arrive", "toy", "biology"):
                self.assertTrue(all("{" not in line for line in hatchling_chatter._pool(pet, situation)))

    def test_adult_forms_are_only_available_after_that_form_is_earned(self):
        for species, forms in FORM_LINES.items():
            for form, lines in forms.items():
                pet = self.pet(species, "bacterium", stage="adult", form=form)
                adult = hatchling_chatter._pool(pet, "idle")
                self.assertTrue(all(line in adult for line in lines), (species, form))
                pet["stage"] = "juvenile"
                self.assertTrue(all(line not in hatchling_chatter._pool(pet, "idle") for line in lines))

    def test_personality_lines_keep_each_familys_voice(self):
        for family, bank in {**SPECIES_LINES, **SAMPLE_LINES}.items():
            pet = self.pet("sample", family) if family in SAMPLE_LINES else self.pet(family)
            for trait in hatchling.TRAITS:
                pet["trait"] = trait
                self.assertTrue(bank.get(trait), (family, trait))
                self.assertTrue(any(line in hatchling_chatter._pool(pet, "idle") for line in bank[trait]))

    def test_recent_lines_are_not_repeated_when_wording_is_revoiced(self):
        state = hatched("larva")
        pet = hatchling.view(state, 2 * HOUR)["pet"]
        rng = random.Random(5)
        lines = []
        for index in range(3):
            hatchling_chatter.chatter(state, pet, "dock", 2 * HOUR + index, "chatty", rng=rng, force=True)
            lines.append(state["pet"]["chat"]["line"])
        self.assertEqual(len(set(lines)), 3)
        again = hatchling.load_state(json.dumps(state))
        self.assertEqual(again["pet"]["chat"]["recent"], lines)
        hatchling_chatter.chatter(state, pet, "dock", 2 * HOUR + 4, "chatty", rng=rng, force=True)
        self.assertNotEqual(state["pet"]["chat"]["line"], lines[-1])
        self.assertLessEqual(len(state["pet"]["chat"]["recent"]), 6)

    def test_legacy_chatter_and_silence_settings_still_work(self):
        state = hatched("bot")
        pet = hatchling.view(state, 2 * HOUR)["pet"]
        first = hatchling_chatter._pool(pet, "dock")[0]
        state["pet"]["chat"] = {"text": "BEEP. " + first, "at": 1}
        hatchling_chatter.chatter(state, pet, "dock", 2 * HOUR, "chatty", rng=random.Random(1), force=True)
        self.assertNotEqual(state["pet"]["chat"]["line"], first)
        for kwargs in ({"mode": "off"}, {"mode": "chatty", "watcher_busy": True}):
            self.assertIsNone(hatchling_chatter.chatter(state, pet, "dock", 3 * HOUR, force=True, **kwargs))

    def test_biology_cue_is_not_hidden_by_the_toy_it_also_finds(self):
        state = hatched("sample", kind="fungoida")
        now = 2 * HOUR
        hatchling.observe(state, {"event": "ScanOrganic", "ScanType": "Analyse", "Species_Localised": "Fungoida"}, now)
        self.assertEqual(state["pet"]["moment"]["kind"], "toy")
        self.assertEqual(state["pet"]["cue"]["kind"], "biology")

        class Deck(DashboardGamesMixin):
            def _hatchling_chat(self, situation):
                self.situation = situation

        deck = Deck()
        deck._hatchling_react(state, {})
        self.assertEqual(deck.situation, "biology")


if __name__ == "__main__":
    unittest.main()
