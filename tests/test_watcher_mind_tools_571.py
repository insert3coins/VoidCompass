"""5.7.1: the Watcher's mind, sharper. Its LIBRARY searched by meaning (a
small model on the CPU), what could live on a world from Survey's own
predictions, and your 👍/👎 shaping its voice. No model runs here: the search
model and the mind are stand-ins."""

import math
from pathlib import Path
import shutil
import tempfile
import threading
import unittest

from voidcompass.llm import library_sources
from voidcompass.llm.library_sources import SourceLibrary
from voidcompass.llm.llm_embed import Embedder, EmbedServer, pack, similarity, unpack
from voidcompass.overlays import watcher_copilot, watcher_mind
from tests.test_watcher_llm_571 import FakeServer, mind_llm, wait_ready, whole

ROOT = Path(__file__).resolve().parents[1]


class FakeEmbedder:
    """Meaning as a few made-up dimensions: fuel, carriers, life, places."""

    WORDS = {"fuel": 0, "tritium": 0, "burn": 0, "carrier": 1, "carriers": 1, "builds": 1, "brewer": 1,
             "life": 2, "grows": 2, "bacteria": 2, "colonia": 3, "region": 3}

    def __init__(self):
        self.asked = 0

    def available(self):
        return True

    def _vector(self, text):
        vector = [0.0] * 5
        for word in str(text).casefold().replace("?", " ").replace(".", " ").replace(":", " ").split():
            if word in self.WORDS:
                vector[self.WORDS[word]] += 1.0
        if not any(vector):
            vector[4] = 1.0  # about none of it
        return vector

    def vectors(self, texts):
        self.asked += len(texts)
        return [pack(self._vector(text)) for text in texts]

    def question(self, text):
        return pack(self._vector(text))


def library(test, embedder=None, builtin=None):
    folder = Path(tempfile.mkdtemp())
    test.addCleanup(shutil.rmtree, folder, True)
    return SourceLibrary(folder, embedder=embedder, builtin=builtin, sleep=lambda _s: None), folder


def finish(sources):
    for thread in (sources._thread, sources._vector_thread):
        if thread is not None:
            thread.join(10)


BUILTIN = [{"title": "Colonia", "text": "Colonia is a settled region far from Sol.", "subject": "THE GALAXY"},
           {"title": "Where life grows", "text": "Life grows on thin-atmosphere worlds; bacteria are common.",
            "subject": "EXOBIOLOGY"}]


class MeaningTests(unittest.TestCase):
    def test_vectors_are_small_and_compared_by_meaning(self):
        packed = pack([3.0, 4.0, 0.0])
        self.assertEqual(len(unpack(packed)), 3)
        self.assertAlmostEqual(similarity(unpack(packed), unpack(packed)), 1.0, places=2)
        self.assertAlmostEqual(similarity(unpack(pack([1.0, 0.0])), unpack(pack([0.0, 1.0]))), 0.0, places=2)
        self.assertLess(len(packed), 10, "one byte a number, in base64")

    def test_its_own_cards_and_yours_are_searched_by_meaning(self):
        embedder = FakeEmbedder()
        sources, folder = library(self, embedder, lambda: BUILTIN)
        with sources._lock:
            sources._sources = [{"id": "s1", "url": "https://wiki.example/x", "host": "wiki.example", "title": "Carriers"}]
            sources._cards["s1"] = [{"title": "Drake-Class Carrier", "text": "Built by the Brewer Corporation.", "url": "x"},
                                    {"title": "Jumping", "text": "A carrier burns tritium for each jump.", "url": "x"}]
        self.assertTrue(sources.fill_vectors())
        finish(sources)
        self.assertTrue(all(card.get("vec") for card in sources._cards["s1"]))
        self.assertTrue((folder / "builtin-vectors.json").is_file(), "its own cards read once, then kept")
        found = sources.search("What does it burn for fuel?")
        self.assertEqual(found[0]["title"], "Jumping")
        self.assertNotIn("vec", found[0])
        self.assertEqual(sources.search("Is there any life out here?")[0]["subject"], "EXOBIOLOGY")
        self.assertTrue(sources.search("Is there any life out here?")[0]["own"])
        self.assertEqual(sources.search("lasagne recipes"), [], "nothing near enough")
        asked = embedder.asked
        again = SourceLibrary(folder, embedder=embedder, builtin=lambda: BUILTIN)
        again._sources, again._cards = sources._sources, sources._cards
        self.assertFalse(again.fill_vectors() and (finish(again) or embedder.asked > asked), "nothing to read again")

    def test_words_only_without_its_search_model(self):
        sources, _folder = library(self, None, lambda: BUILTIN)
        self.assertEqual(sources.search("Where is Colonia?")[0]["title"], "Colonia")
        self.assertFalse(sources.fill_vectors())

    def test_the_search_server(self):
        args = EmbedServer("e.exe", "bge.gguf", gpu=False).arguments()
        for flag in ("--embedding", "--pooling", "--device", "--api-key"):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index("--device") + 1], "none", "the CPU only: the graphics card stays the game's")
        self.assertFalse(Embedder(base=tempfile.gettempdir()).available(), "not downloaded: words only")


class LifeTests(unittest.TestCase):
    GENERA = [{"name": "Bacterium", "min_value": 1000000, "max_value": 1000000,
               "species": [{"name": "Bacterium Aurasus", "value": 1000000}]},
              {"name": "Stratum", "min_value": 2637500, "max_value": 19010800,
               "species": [{"name": "Stratum Tectonicas", "value": 19010800}, {"name": "Stratum Paleas", "value": 1362000}]}]

    def test_what_could_live_there(self):
        self.assertEqual(watcher_copilot.topics_for("What could live on 3 a?"), ["life"])
        self.assertIn("life", watcher_copilot.topics_for("any bacteria here?"))
        lines = watcher_copilot.life_lines([{"name": "Hypio 3 a", "signals": 3, "known": ["Bacterium"],
                                             "genera": self.GENERA, "colours": {"stratum tectonicas": "Emerald"}}])
        self.assertEqual(lines[0], "Hypio 3 a: 3 biological signals, found so far: Bacterium")
        self.assertEqual(lines[1], "Could grow on Hypio 3 a: Stratum (2,637,500 to 19,010,800 credits), "
                                   "Bacterium (1,000,000 credits)")
        self.assertEqual(lines[2], "On Hypio 3 a, Stratum Tectonicas would fetch 19,010,800 credits, in Emerald")
        self.assertEqual(watcher_copilot.life_lines([]), ["No world scanned here has any sign of life yet."])
        self.assertIn("Nothing in the species data fits", watcher_copilot.life_lines([{"name": "X", "genera": []}])[1])

    def test_the_world_you_name_or_where_you_are(self):
        from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin

        deck = DashboardWatcherVoiceMixin.__new__(type("Deck", (DashboardWatcherVoiceMixin,), {}))
        deck.scan_items = [
            {"body_id": 1, "name": "3 a", "full_name": "Hypio 3 a", "bio_count": 3, "genuses": ["Bacterium"],
             "predicted_genuses": self.GENERA},
            {"body_id": 2, "name": "5", "full_name": "Hypio 5", "bio_count": 0, "predicted_genuses": self.GENERA[:1]},
            {"body_id": 3, "name": "A", "full_name": "Hypio A", "is_star": True}]
        deck._survey_codex_variants = lambda body_id: {"stratum tectonicas": [{"colour": "Emerald"}]} if body_id == 1 else {}
        self.assertTrue(deck._watcher_lookup_life("what could live on 5?")[0].startswith("Hypio 5:"))
        deck.current_body_name = "Hypio 5"
        self.assertTrue(deck._watcher_lookup_life("what lives here?")[0].startswith("Hypio 5:"), "where you are")
        deck.current_body_name = ""
        lines = deck._watcher_lookup_life("any life in this system?")
        self.assertTrue(lines[0].startswith("Hypio 3 a: 3 biological signals"), "the worlds with signals")
        self.assertIn("in Emerald", " ".join(lines))


class VoteTests(unittest.TestCase):
    def test_your_votes_shape_its_voice(self):
        llm, _settings = mind_llm(self)
        wait_ready(llm)
        mind = watcher_mind.WatcherMind(None, {"heartbeat_personality": "stoic"})
        mind.llm = llm
        FakeServer.replies = ["52.0 light years. The dark goes on."]
        mind._reword("jump_long", "jump_long:0", "52.0 light years.", {"dist": "52.0"}, 2, None, 1.0)
        mind._llm_pending["job"].done.wait(2)
        mind.follow_up()
        said = mind.memory["own_said"][-1]
        self.assertEqual((said["topic"], said["text"]), ("jump_long", "52.0 light years. The dark goes on."))
        self.assertTrue(mind.rate(said["text"], "up"))
        self.assertTrue(mind.rate("44.0 light years. Hm.", "down", "jump_long"))
        self.assertFalse(mind.rate("", "up"))
        FakeServer.replies = ["61.0 light years. Onward."]
        mind._reword("jump_long", "jump_long:1", "61.0 light years.", {"dist": "61.0"}, 2, None, 2.0)
        job = mind._llm_pending["job"]
        job.done.wait(2)
        asked = whole(job.messages)
        self.assertIn("never reuse their words):\n- 52.0 light years. The dark goes on.", asked, "liked first")
        self.assertIn("never sound like these):\n- 44.0 light years. Hm.", asked)
        self.assertIn("44.0 light years. Hm.", job.copied, "its phrases count as copying")
        self.assertTrue(mind.rate(said["text"], "clear"))
        self.assertEqual(mind.memory["liked"], [])

    def test_liked_answers_set_its_talk(self):
        llm, _settings = mind_llm(self)
        wait_ready(llm)
        mind = watcher_mind.WatcherMind(None, {})
        mind.llm = llm
        mind.rate("Sol. Home, for what it's worth.", "up", "talk")
        FakeServer.replies = ["Sol. Docked."]
        mind.talk("Where are we?")
        mind._talk_pending["job"].done.wait(2)
        reply = mind.follow_up()
        self.assertIn("Answers of yours the commander liked (for your tone only):\n- Sol. Home, for what it's worth.",
                      whole(FakeServer.made[-1].asked[-1]))
        self.assertEqual(mind.memory["own_said"][-1], {"at": mind.memory["own_said"][-1]["at"], "topic": "talk",
                                                       "text": reply["text"]})

    def test_the_mind_page_and_its_command(self):
        from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin

        mind = watcher_mind.WatcherMind(None, {})
        mind.save = lambda: None
        mind.memory["own_said"] = [{"at": 1.0, "topic": "arrival", "text": "Sol again."},
                                   {"at": 2.0, "topic": "scooped", "text": "Fuel's in."}]
        deck = DashboardWatcherVoiceMixin.__new__(type("Deck", (DashboardWatcherVoiceMixin,), {}))
        deck.config = {}
        deck._watcher_mind = lambda: mind
        self.assertTrue(deck._handle_watcher_settings_command("mind_rate", {"text": "Sol again.", "vote": "up"}))
        said = deck._html_watcher_said(mind)
        self.assertEqual([(row["text"], row["vote"]) for row in said], [("Fuel's in.", ""), ("Sol again.", "up")])
        self.assertEqual(mind.memory["liked"][0]["topic"], "arrival", "its moment found from what it said")


class PageTests(unittest.TestCase):
    def test_the_pages_have_the_new_parts(self):
        script = (ROOT / "web" / "dashboard" / "watcher.js").read_text(encoding="utf-8")
        for needle in ('id="watcher-said"', 'id="watcher-liked"', 'id="watcher-disliked"', '"mind_rate"',
                       'id="lib-search-mode"', "BY MEANING", "Downloading its library search"):
            self.assertIn(needle, script)
        library = script[script.index("function libraryPanel()"):script.index("let librarySubject")]
        order = [library.index(label) for label in ('aria-label="Search its library"', 'aria-label="Your sources"',
                                                    'aria-label="Teach it"')]
        self.assertEqual(order, sorted(order), "search first, then your sources, then what it knows of you")
