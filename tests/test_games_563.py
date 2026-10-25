"""5.6.3: the Games page. A card per game folder under web/games (with its
picture from assets/gamecards, or a drawn stand-in), each played in the deck
in a sandboxed frame, and the best runs kept per commander. The first
cabinet is Thargoid Swarm."""

import json
from pathlib import Path
import re
import tempfile
import time
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import urlopen

from voidcompass.dashboard import dashboard_games_mixin as games_module
from voidcompass.dashboard.dashboard_games_mixin import CARD_SIZE, DashboardGamesMixin, KEEP_RUNS, read_games
from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def fetch(url):
    try:
        with urlopen(url, timeout=5) as reply:
            return reply.status, dict(reply.headers), reply.read()
    except HTTPError as error:
        body = error.read()
        return error.code, dict(error.headers), body


class LibraryTests(unittest.TestCase):
    def test_the_first_cabinet_is_found(self):
        found = read_games()
        ids = [game["id"] for game in found]
        self.assertIn("thargoid-swarm", ids)
        self.assertEqual([game["title"].casefold() for game in found], sorted(game["title"].casefold() for game in found), "cards A to Z")
        self.assertNotIn("kit", ids, "the shared kit has no game.json, so no card")
        game = found[ids.index("thargoid-swarm")]
        self.assertEqual(game["title"], "Thargoid Swarm")
        self.assertEqual(game["entry"], "/games/thargoid-swarm/index.html")
        self.assertEqual(game["card_name"], "thargoid-swarm.png")
        self.assertEqual(game["stage"], "WAVE")
        self.assertTrue(game["controls"] and all(len(pair) == 2 for pair in game["controls"]))
        self.assertEqual(CARD_SIZE, (1200, 1350), "8:9 card pictures, an arcade screen")

    def test_each_folder_is_a_card_and_broken_ones_are_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            root, cards = Path(folder) / "games", Path(folder) / "cards"
            cards.mkdir()
            for name, manifest, page in (("zeta", {"title": "Zeta"}, True),
                                         ("alpha", {"title": "Alpha", "accent": "#ff00aa"}, True),
                                         ("companion", {"title": "Companion", "catalog": False}, True),
                                         ("nopage", {"title": "No page"}, False),
                                         ("Bad Name", {"title": "Bad"}, True),
                                         ("sneaky", {"title": "Sneaky", "entry": "../dashboard/app.js"}, True)):
                (root / name).mkdir(parents=True)
                (root / name / "game.json").write_text(json.dumps(manifest), encoding="utf-8")
                if page:
                    (root / name / "index.html").write_text("<!doctype html>", encoding="utf-8")
            (root / "broken").mkdir()
            (root / "broken" / "game.json").write_text("{not json", encoding="utf-8")
            (cards / "zeta.webp").write_bytes(b"RIFF")
            found = read_games(root, cards)
            self.assertEqual([game["id"] for game in found], ["alpha", "zeta"])
            self.assertEqual(found[0]["card"], "", "no picture: the page draws a stand-in")
            self.assertEqual(found[0]["accent"], "#ff00aa")
            self.assertEqual(found[1]["card"], "/gamecards/zeta.webp")


class ScoreTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = str(Path(folder.name) / "games.json")
        self.published = []

        class Deck(DashboardGamesMixin):
            pass

        self.deck = Deck()
        self.deck.config = {}
        self.deck._games_path = lambda: self.path
        self.deck._schedule_html_dashboard_publish = lambda immediate=False: self.published.append(immediate)

    def score(self, points, **extra):
        return self.deck._handle_games_command("score", {"game": "thargoid-swarm", "score": points, **extra})

    def test_best_runs_are_kept_best_first(self):
        for points in (500, 9000, 120, 4000):
            self.assertTrue(self.score(points, wave=3, accuracy=55, rank="NOVICE"))
        game = next(item for item in self.deck._html_games_workspace()["games"] if item["id"] == "thargoid-swarm")
        self.assertEqual([run["score"] for run in game["runs"]], [9000, 4000, 500, 120])
        self.assertEqual(game["best"]["score"], 9000)
        self.assertEqual(game["played"], 4)
        self.assertEqual(json.loads(Path(self.path).read_text(encoding="utf-8"))["thargoid-swarm"]["runs"][0]["rank"], "NOVICE")
        self.assertTrue(self.published)

    def test_only_the_best_ten_and_nothing_silly(self):
        for points in range(1, 16):
            self.score(points * 100)
        self.score(-5)
        self.score("lots", accuracy=900)
        record = json.loads(Path(self.path).read_text(encoding="utf-8"))["thargoid-swarm"]
        self.assertEqual(len(record["runs"]), KEEP_RUNS)
        self.assertEqual(record["runs"][0]["score"], 1500)
        self.assertEqual(record["played"], 17, "a zero run counts as played, not as a best")
        self.assertFalse(self.deck._handle_games_command("score", {"game": "not-a-game", "score": 10}))
        self.assertFalse(self.deck._handle_games_command("score", {"game": "../x", "score": 10}))
        self.assertFalse(self.deck._handle_games_command("delete", {"game": "thargoid-swarm"}))

    def test_scores_belong_to_the_commander(self):
        source = Path(games_module.__file__).read_text(encoding="utf-8")
        self.assertIn("get_profile_file(get_active_profile(", source)


class ServerTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.cards = Path(folder.name)
        (self.cards / "thargoid-swarm.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (self.cards / "notes.txt").write_text("not a picture", encoding="utf-8")
        self.server = HtmlDashboardServer(WEB / "dashboard", image_root=ROOT / "assets" / "images",
                                          games_root=WEB / "games", gamecard_root=self.cards)
        self.addCleanup(self.server.stop)

    def test_a_game_may_be_framed_by_the_deck_and_reaches_nothing(self):
        status, headers, body = fetch(f"{self.server.origin}/games/thargoid-swarm/index.html")
        self.assertEqual(status, 200)
        self.assertIn(b"game.js", body)
        policy = headers["Content-Security-Policy"]
        self.assertIn(f"frame-ancestors {self.server.origin}", policy)
        self.assertIn("connect-src 'none'", policy)
        self.assertIn("form-action 'none'", policy)
        status, headers, _ = fetch(f"{self.server.origin}/games/thargoid-swarm/game.js")
        self.assertEqual((status, headers["Content-Type"].split(";")[0]), (200, "text/javascript"))
        # The shared kit sits beside the games, under the same policies.
        status, headers, body = fetch(f"{self.server.origin}/games/kit/cabinet.js")
        self.assertEqual(status, 200)
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        self.assertIn(b"Kit.cabinet", body)
        # The deck's own pages still refuse to be framed.
        _, headers, _ = fetch(f"{self.server.origin}/index.html")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_nothing_outside_the_folders(self):
        for path in ("/games/../dashboard/app.js", "/games/thargoid-swarm/../../dashboard/index.html",
                     "/games/%2e%2e/dashboard/app.js", "/gamecards/notes.txt", "/gamecards/../README.txt", "/games/missing/index.html"):
            with self.subTest(path=path):
                self.assertEqual(fetch(f"{self.server.origin}{path}")[0], 404)

    def test_card_pictures(self):
        status, headers, body = fetch(f"{self.server.origin}/gamecards/thargoid-swarm.png")
        self.assertEqual((status, headers["Content-Type"]), (200, "image/png"))
        self.assertTrue(body.startswith(b"\x89PNG"))

    def test_the_build_bundles_the_cards(self):
        build = (ROOT / "tools" / "build.py").read_text(encoding="utf-8")
        self.assertIn('"assets" / "gamecards"}{data_sep}assets/gamecards', build)
        self.assertTrue((ROOT / "assets" / "gamecards" / "README.txt").is_file(), "the folder exists for the build")
        runtime = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard_runtime.py").read_text(encoding="utf-8")
        self.assertIn('gamecard_root=_resource_path(Path("assets") / "gamecards")', runtime)


class RailTests(unittest.TestCase):
    def test_games_and_hatchling_are_alphabetical_cockpit_destinations(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        rail = html.split('<nav class="nav"', 1)[1].split("</nav>", 1)[0]
        cockpit = rail.split("<p>COCKPIT</p>", 1)[1].split("<p>", 1)[0]
        self.assertEqual(re.findall(r'data-page="([a-z-]+)"', cockpit)[:4], ["constellation", "games", "hatchling", "music"])
        self.assertIn('data-page-name="games"', html)
        self.assertIn('id="games-workspace"', html)
        self.assertIn('data-page-name="hatchling"', html)
        self.assertIn('id="hatchling-workspace"', html)
        self.assertIn('href="games.css"', html)
        self.assertIn('href="hatchling.css"', html)
        app = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('import {renderGames} from "./games.js";', app)
        self.assertIn("games: (data) => renderGames(data, WORKSHOP_UI)", app)
        self.assertIn('import {renderHatchling, setHatchlingActive} from "./hatchling.js";', app)
        self.assertIn("hatchling: (data) => renderHatchling(data, WORKSHOP_UI)", app)


class PlayTests(unittest.TestCase):
    """The deck's Games page in a real browser, playing the real cabinet."""

    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f"Playwright Chromium is unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def open_deck(self, runs=(), real_csp=False, picture=True):
        from tests.test_dashboard_overview_visuals import overview_state
        self.commands = []
        server = HtmlDashboardServer(WEB / "dashboard", image_root=ROOT / "assets" / "images",
                                     gamecard_root=ROOT / "assets" / "gamecards",
                                     command_callback=lambda payload: self.commands.append(payload) or True)
        self.addCleanup(server.stop)
        state = overview_state()
        server.publish(state)
        # Playwright evaluates through eval, which the deck forbids: one test keeps
        # the real policies (and only looks), the rest bypass them.
        context = self.browser.new_context(viewport={"width": 1600, "height": 900}, bypass_csp=not real_csp)
        self.addCleanup(context.close)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: message.type == "error" and errors.append(message.text))
        self.addCleanup(lambda: self.assertEqual(errors, []))
        page.goto(server.url)
        page.wait_for_selector("body.ready", timeout=15000)
        page.locator('.nav-item[data-page="games"]').click()
        found = read_games()
        swarm = [game["id"] for game in found].index("thargoid-swarm")
        if runs:
            found[swarm] = {**found[swarm], "runs": list(runs), "best": runs[0], "played": len(runs)}
        if not picture:
            found[swarm] = {**found[swarm], "card": ""}
        state = {**state, "workspace": {"page": "games", "ready": True,
                                        "data": {"games": found, "card_size": list(CARD_SIZE), "card_folder": ""}}}
        server.publish(state)
        page.wait_for_selector(".game-card")
        return page

    def test_a_card_opens_the_game_and_a_run_is_kept(self):
        page = self.open_deck(runs=[{"score": 4200, "wave": 4, "accuracy": 40, "rank": "NOVICE", "at": int(time.time())}])
        card = page.locator('.game-card[data-game-open="thargoid-swarm"]')
        if (ROOT / "assets" / "gamecards" / "thargoid-swarm.png").is_file():
            card.locator(".game-art img").wait_for()
            page.wait_for_function("document.querySelector('.game-art img').complete")
            self.assertGreater(page.evaluate("document.querySelector('.game-art img').naturalWidth"), 0, "the card picture loads")
        self.assertIn("Scouts and Interceptors.", card.inner_text(), "the whole tagline, as written")
        self.assertIn("4,200", card.inner_text())
        card.click()
        page.wait_for_selector("#games-player:not([hidden]) iframe.games-frame")
        self.assertEqual(page.locator("iframe.games-frame").get_attribute("sandbox"), "allow-scripts")
        self.assertIn("4,200", page.locator("#games-runs").inner_text())
        game = page.frame_locator("iframe.games-frame")
        game.locator("canvas").wait_for()
        frame = next(item for item in page.frames if item.url.endswith("/games/thargoid-swarm/index.html"))
        frame.wait_for_function("window.thargoidSwarm && window.thargoidSwarm.state().state === 'title'")
        game.locator("canvas").click()
        frame.wait_for_function("window.thargoidSwarm.state().state === 'play'")
        frame.wait_for_function("window.thargoidSwarm.state().enemies === 40")
        page.keyboard.down("Space")
        page.wait_for_timeout(400)
        page.keyboard.up("Space")
        frame.evaluate("window.thargoidSwarm._wave(3)")
        boss = frame.evaluate("window.thargoidSwarm.state().boss")
        self.assertEqual((boss["name"], boss["hearts"]), ("CYCLOPS", 4))
        frame.evaluate("window.thargoidSwarm._over()")
        frame.wait_for_function("window.thargoidSwarm.state().state === 'over'")
        page.wait_for_function("document.querySelector('iframe.games-frame') !== null")
        deadline = time.time() + 5
        while time.time() < deadline and not any(item.get("operation") == "score" for item in self.commands):
            page.wait_for_timeout(50)
        score = next(item for item in self.commands if item.get("operation") == "score")
        self.assertEqual((score["page"], score["game"]), ("games", "thargoid-swarm"))
        self.assertGreater(score["score"], 0)
        self.assertEqual(score["wave"], 3)
        self.assertTrue(score["rank"])
        # Leaving the page pauses a run in progress (a new run once the
        # debrief's second is up: a held trigger doesn't skip it).
        page.wait_for_timeout(1100)
        game.locator("canvas").click()
        frame.wait_for_function("window.thargoidSwarm.state().state === 'play'")
        page.locator('.nav-item[data-page="music"]').click()
        frame.wait_for_function("window.thargoidSwarm.state().state === 'pause'")
        page.locator('.nav-item[data-page="games"]').click()
        page.click("[data-game-back]")
        self.assertEqual(page.evaluate("window.voidcompassGames.state()"),
                         {"games": [game["id"] for game in read_games()], "playing": "", "framed": False})

    def test_the_game_runs_under_its_real_policies(self):
        import io
        from PIL import Image
        page = self.open_deck(real_csp=True)
        page.locator('.game-card[data-game-open="thargoid-swarm"]').click()
        page.frame_locator("iframe.games-frame").locator("canvas").wait_for()
        page.wait_for_timeout(700)
        shot = Image.open(io.BytesIO(page.locator("iframe.games-frame").screenshot())).convert("RGB")
        green = sum(1 for r, g, b in shot.get_flattened_data() if g > 170 and g > r + 40 and g > b - 20)
        self.assertGreater(green, 300, "the title screen drawn: the game's scripts ran in its sandbox")

    def test_the_theme_reaches_the_game_and_the_sound_switch_is_kept(self):
        page = self.open_deck(picture=False)
        card = page.locator('.game-card[data-game-open="thargoid-swarm"]')
        self.assertIn("THARGOID SWARM", card.locator(".game-art-blank strong").inner_text().upper())
        self.assertIn("assets/gamecards/thargoid-swarm.png", card.inner_text(), "no picture: a stand-in naming its file")
        page.locator('.game-card[data-game-open="thargoid-swarm"]').click()
        page.wait_for_selector("iframe.games-frame")
        page.frame_locator("iframe.games-frame").locator("canvas").wait_for()
        frame = next(item for item in page.frames if item.url.endswith("/games/thargoid-swarm/index.html"))
        frame.wait_for_function("window.thargoidSwarm")
        page.frame_locator("iframe.games-frame").locator("canvas").click()
        page.keyboard.press("m")
        frame.wait_for_function("window.thargoidSwarm.state().muted")
        page.wait_for_function("localStorage.getItem('voidcompass.games.thargoid-swarm.muted') === '1'")
        page.click("[data-game-restart]")
        frame = None
        deadline = time.time() + 5
        while time.time() < deadline:
            frames = [item for item in page.frames if item.url.endswith("/games/thargoid-swarm/index.html")]
            if frames:
                try:
                    if frames[-1].evaluate("Boolean(window.thargoidSwarm && window.thargoidSwarm.state().muted)"):
                        frame = frames[-1]
                        break
                except Exception:
                    pass
            page.wait_for_timeout(50)
        self.assertIsNotNone(frame, "the new cabinet is told the sound is off")


if __name__ == "__main__":
    unittest.main()
