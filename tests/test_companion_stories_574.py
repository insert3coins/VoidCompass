"""Aster, Axiom and Meridian stories, personas, echoes, API and boot (5.7.4)."""
import random
import string
from types import SimpleNamespace
import unittest

from voidcompass.core import companions
from voidcompass.dashboard.dashboard_api_mixin import DashboardApiMixin
from voidcompass.dashboard.html_dashboard_runtime import HtmlDashboardRuntime
from voidcompass.overlays import aster_lines, companion_personas, companion_story, persona_lines
from voidcompass.services.local_api import ApiError, LocalApi
from tests.test_aster_companion import Clock

PERSONAS = ("aster", "axiom", "meridian", "lyra")
# Names that belong to one story: they must never appear in another
# companion's words, or in ordinary banks before their chapter is heard.
STORY_NAMES = {
    "aster": ("Marr", "Haskell", "Varga", "Okonkwo", "Quist", "Pell"),
    "axiom": ("Lattice", "Moreau", "Errand"),
    "meridian": ("Leadline", "Rook", "Penhallow", "Ellery", "Sallow", "Wayfarer"),
}
FORMAT = string.Formatter()


def fields_of(line):
    return {name for _, name, _, _ in FORMAT.parse(line) if name}


def mind(identity, **config):
    values = {"companion_identity": identity, f"{identity}_thoughts": "chatty", **config}
    return companions.create_mind(None, values, clock=Clock(), rng=random.Random(5))


class StoryEngineTests(unittest.TestCase):
    def test_every_story_is_complete_ordered_and_sealed(self):
        for identity in PERSONAS:
            story = companion_personas.get(identity).story
            with self.subTest(identity=identity):
                self.assertEqual(len(story.chapters), 8)
                self.assertEqual(len(story.passages), 48)
                ids = [row[0] for row in story.passages]
                self.assertEqual(len(ids), len(set(ids)), "stable unique passage IDs")
                self.assertEqual([row[3] for row in story.passages], sorted(row[3] for row in story.passages))
                page = story.page({}, 0)
                self.assertTrue(all(row["title"] == "Unopened" and row["unlock"] for row in page["chapters"]))
                self.assertFalse(page["books"])
                self.assertEqual(page["next"]["hours"], .25)
                for index, chapter in enumerate(story.chapters[1:], 1):
                    gate = chapter["gate"]
                    self.assertTrue(gate["label"] and gate["how"])
                    self.assertFalse(story.gate_met({}, index, chapter["hours"][0]))
                    self.assertTrue(story.gate_met({"aster_marks": {gate["signals"][-1]: gate["count"]}}, index, 0))
                    self.assertTrue(story.gate_met({}, index, chapter["hours"][0] + story.grace_hours))

    def test_due_honours_hours_gates_days_and_order(self):
        story = companion_personas.get("axiom").story
        memory = {"lore": []}
        first = story.due(memory, 0.3, now=1000)
        self.assertEqual(first[0], story.passages[0][0])
        memory["lore"] = [[row[0], 1000] for row in story.passages[:6]]
        self.assertIsNone(story.due(memory, 7, now=2000), "chapter II waits for its scans")
        self.assertEqual(story.page(memory, 7, now=2000)["next"]["waits_for"], "ten detailed scans")
        memory["aster_marks"] = {"scan": 10}
        self.assertEqual(story.due(memory, 7, now=2000)[0], story.chapter_ids(1)[0])
        memory["lore"] = [[row[0], 1000] for row in story.passages[:36]]
        self.assertIsNone(story.due(memory, 500, now=1000 + 86400), "chapter VII waits two real days")
        self.assertEqual(story.due(memory, 500, now=1000 + 2 * 86400 + 1)[0], story.chapter_ids(6)[0])
        memory["lore"] = [[row[0], 1000] for row in story.passages]
        page = story.page(memory, 500)
        self.assertTrue(page["complete"])
        self.assertEqual(len(page["books"][0]["chapters"]), 8)

    def test_journal_signals_are_real_fields_only(self):
        self.assertEqual(companion_story.signals("FSDJump", {"JumpDist": 60, "StarPos": [0, 0, 12000]}),
                         {"jump", "long_jump", "far"})
        self.assertEqual(companion_story.signals("Scan", {"BodyName": "A 1", "WasDiscovered": False, "PlanetClass": "Water world"}),
                         {"scan", "first", "water_world"})
        self.assertIn("neutron", companion_story.signals("StartJump", {"StarClass": "N"}))
        self.assertEqual(companion_story.signals("MissionCompleted", {}), {"delivery", "mission"})
        self.assertEqual(companion_story.signals("FSDJump", {"StarPos": "nonsense"}), {"jump"})


class FrozenBuildTests(unittest.TestCase):
    def test_every_persona_module_is_imported_by_name_for_pyinstaller(self):
        # The frozen app crashed when the registry imported modules by string:
        # PyInstaller only bundles what it can see imported.
        import ast
        from pathlib import Path
        source = Path(companion_personas.__file__).read_text(encoding="utf-8")
        self.assertNotIn("importlib.import_module", source)
        self.assertNotIn("import importlib", source)
        imported = {alias.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)
                    for alias in node.names}
        for spec in companion_personas._SPEC.values():
            for key in ("lines", "lore", "name", "postcards"):
                self.assertIn(spec[key], imported, spec[key])


class PersonaBankTests(unittest.TestCase):
    def test_every_topic_and_command_in_both_modes_with_valid_fields(self):
        own_story = {identity: set(companion_personas.get(identity).story.echo_topics()) for identity in PERSONAS}
        for identity in ("axiom", "meridian", "lyra"):
            lines = companion_personas.get(identity).lines
            with self.subTest(identity=identity):
                # Nobody takes the watch from, or remarks on, itself.
                needed = [topic for topic in aster_lines.EVENTS if topic not in own_story["aster"]
                          and topic not in {f"handover_from_{identity}", f"idle_crew_{identity}"}]
                self.assertEqual(persona_lines.missing(lines.BANK, needed), [])
                for topic in needed:
                    self.assertGreaterEqual(len(lines.event_lines(topic, True)), 1, topic)
                    allowed = set().union(*(fields_of(line) for line in aster_lines.EVENTS[topic]))
                    for line in lines.EVENTS[topic]:
                        self.assertLessEqual(fields_of(line) - allowed - {f"c{n}" for n in ("I", "II", "III", "IV", "V", "VI", "VII", "VIII")},
                                             set(), f"{topic}: {line}")
                self.assertEqual(set(lines.COMMANDS), set(aster_lines.COMMANDS))
                self.assertGreaterEqual(len(lines.GREETINGS), 30)
                self.assertGreaterEqual(len(lines.CAPABILITIES), 6)
                for line in lines.event_lines("sign_off") + lines.event_lines("sign_off", True):
                    self.assertIn("{summary}.", line, "the session summary ends before the farewell")

    def test_no_story_names_leak_into_ordinary_words_or_other_companions(self):
        for identity in PERSONAS:
            persona = companion_personas.get(identity)
            story_topics = {"idle_aster_lore", "aster_lore_recall", "aster_after", *persona.story.echo_topics()}
            ordinary = [line for topic, rows in persona.lines.EVENTS.items() if topic not in story_topics for line in rows]
            ordinary += list(persona.lines.GREETINGS) + list(persona.lines.CAPABILITIES)
            ordinary += [line for rows in persona.naming.lines.values() for line in rows]
            ordinary += [line for bank in (persona.postcards.PLAIN, persona.postcards.DRY) for rows in bank.values() for line in rows]
            ordinary += list(persona.story.musings)
            ordinary += [echo["how"] for echo in persona.story.echoes.values()] + [echo["label"] for echo in persona.story.echoes.values()]
            ordinary += [line for chapter in persona.story.chapters if chapter["gate"] for line in (chapter["gate"]["label"], chapter["gate"]["how"])]
            with self.subTest(identity=identity):
                for owner, names in STORY_NAMES.items():
                    for name in names:
                        for line in ordinary:
                            self.assertNotIn(name, line, f"{identity} says {name} outside its story")
                        if owner != identity:
                            for row in persona.story.passages:
                                self.assertNotIn(name, row[5])


class PersonaMindTests(unittest.TestCase):
    def test_echo_follows_a_real_event_only_after_its_chapter(self):
        for identity, event, raw, chapter in (("aster", "MarketSell", {}, 1),
                                              ("axiom", "FSSAllBodiesFound", {}, 1),
                                              ("meridian", "FSDJump", {"StarSystem": "A", "JumpDist": 70}, 1)):
            with self.subTest(identity=identity):
                companion = mind(identity)
                story = companion.persona.story
                companion.session_start()
                companion.clock.now += 300
                before = companion.observe(event, raw)
                self.assertFalse(str((before or {}).get("topic") or "").startswith("echo_"))
                companion.memory["lore"] = [[row[0], 0] for row in story.passages if row[4] <= chapter]
                after = None
                # A minor remark may choose silence; the next real event can still stir it.
                for attempt in range(8):
                    companion.clock.now += 300
                    after = companion.observe(event, dict(raw, StarSystem=f"S{attempt}") if raw else raw)
                    if str((after or {}).get("topic") or "").startswith("echo_"):
                        break
                self.assertTrue(after["topic"].startswith("echo_"), after)
                self.assertEqual(after["heading"], story.title.upper())
                self.assertIn(after["text"], companion.persona.lines.EVENTS[after["topic"]])

    def test_commentary_setting_is_per_persona(self):
        for identity in ("axiom", "meridian", "lyra"):
            restrained = mind(identity, **{f"{identity}_humour": "off"})
            voiced = mind(identity)
            self.assertLess(len(restrained.event_lines("arrival")), len(voiced.event_lines("arrival")))
            self.assertEqual(set(restrained.event_lines("arrival")),
                             set(companion_personas.get(identity).lines.RESTRAINED_EVENTS["arrival"]))
            self.assertIn(f"{identity}_humour", companions.new_defaults())

    def test_story_heading_and_personalised_passage(self):
        companion = mind("meridian")
        companion.session_start()
        companion.memory["hours"] = 5
        companion.clock.now += 3600
        thought = companion.remember()
        self.assertEqual(thought["heading"], "LOG · I. TAKING STATION · 1 OF 6")
        self.assertEqual(companion.persona.story.page(companion.memory, 5)["chapters"][0]["told"][0]["text"], thought["text"])


class _Deck(DashboardApiMixin):
    def __init__(self, identity="watcher"):
        self.config = {"companion_identity": identity}
        self._companion_generation = 4
        self.switched = []

    def _companion_switch(self, selected):
        self.switched.append(selected)
        self.config["companion_identity"] = selected
        self._companion_generation += 1
        return True


class CompanionApiTests(unittest.TestCase):
    def test_guard_tags_capabilities_and_selection(self):
        deck = _Deck("aster")
        self.assertEqual(deck._api_companion_tag(), {"identity": "aster", "name": "Aster", "generation": 4})
        deck._api_expect(None)
        deck._api_expect("aster")
        with self.assertRaises(ApiError) as caught:
            deck._api_expect("meridian")
        self.assertEqual(caught.exception.status, 409)
        with self.assertRaises(ApiError) as caught:
            deck._api_expect("nobody")
        self.assertEqual(caught.exception.status, 404)
        deck._api_require("share_code")  # 5.7.4: friend codes work for every companion
        with self.assertRaises(ApiError):
            deck._api_require("a_feature_nobody_has")
        listing = deck.api_companions_list()
        self.assertEqual([row["identity"] for row in listing["data"]], list(companions.IDENTITIES))
        self.assertEqual(listing["active"], "aster")
        self.assertIn("meet", next(row for row in listing["data"] if row["identity"] == "watcher")["capabilities"])
        self.assertEqual(deck.api_companion_select("axiom")["identity"], "axiom")
        self.assertEqual(deck.switched, ["axiom"])
        with self.assertRaises(ApiError):
            deck.api_companion_select("unknown")

    def test_routes_pass_the_identity_guard_only_when_sent(self):
        calls = []
        provider = SimpleNamespace(api_watcher_poke=lambda **kw: calls.append(kw) or {"answered": True})
        api = LocalApi(provider)
        route = next(handler for _method, pattern, handler, _control in api._routes if "companion/poke" in pattern.pattern)
        route(SimpleNamespace(body={}))
        route(SimpleNamespace(body={"identity": "axiom"}))
        self.assertEqual(calls, [{}, {"expect": "axiom"}])
        paths = {row["path"] for row in api.endpoints()}
        for path in ("/api/v1/companion", "/api/v1/companions", "/api/v1/companions/{id}", "/api/v1/companion/select",
                     "/api/v1/watcher"):
            self.assertIn(path, paths)


class BootCompanionTests(unittest.TestCase):
    def test_boot_payload_names_the_saved_companion(self):
        for identity in companions.IDENTITIES:
            data = HtmlDashboardRuntime._boot_companion({"companion_identity": identity})
            self.assertEqual(data["identity"], identity)
            self.assertEqual(data["name"], companions.NAMES[identity])
        self.assertEqual(HtmlDashboardRuntime._boot_companion({})["identity"], "watcher")
        self.assertEqual(HtmlDashboardRuntime._boot_companion({"companion_identity": "nobody"})["identity"], "watcher")


if __name__ == "__main__":
    unittest.main()
