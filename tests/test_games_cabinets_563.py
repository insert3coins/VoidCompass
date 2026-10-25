"""5.6.3: the Games page's cabinets on the shared kit (web/games/kit). Every
game loads under its real policies, starts, and reports a score to the deck;
their card pictures are screenshots of the games themselves."""

import io
import re
import time
import unittest
from pathlib import Path

from voidcompass.core import hatchling
from voidcompass.dashboard.dashboard_games_mixin import CARD_SIZE, read_games
from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
GAMES = WEB / "games"
CABINETS = ("canyon-run", "docking-computer", "no-fire-zone", "pod-rescue", "rock-rats", "scarab-patrol", "settlement-run",
            "shield-breaker", "station-defence", "supercruise-runner", "thargoid-swarm", "touchdown", "trumble-trouble")
KIT = ("sound.js", "input.js", "draw.js", "cabinet.js")


class LibraryTests(unittest.TestCase):
    def test_thirteen_arcade_cabinets_a_to_z(self):
        found = read_games()
        self.assertEqual([game["id"] for game in found], list(CABINETS))
        self.assertNotIn("hatchling", [game["id"] for game in found], "the companion has its own Cockpit page")
        self.assertEqual(found[0]["title"], "Canyon Run")

    def test_each_is_on_the_kit_and_reaches_nothing(self):
        for game_id in CABINETS:
            with self.subTest(game=game_id):
                page = (GAMES / game_id / "index.html").read_text(encoding="utf-8")
                scripts = re.findall(r'<script src="([^"]+)"', page)
                self.assertEqual(scripts[:4], [f"../kit/{name}" for name in KIT], "the kit, in order")
                self.assertEqual(scripts[-1], "game.js")
                self.assertIn('href="../kit/cabinet.css"', page)
                source = (GAMES / game_id / "game.js").read_text(encoding="utf-8")
                self.assertIn("Kit.cabinet(", source)
                for word in ("fetch(", "XMLHttpRequest", "WebSocket", "http://", "https://", "localStorage", "Gamepad", "getGamepads"):
                    self.assertNotIn(word, source, f"{game_id} uses {word}")
                self.assertIn("card", source, "it stages its own card picture")
        for name in KIT:
            source = (GAMES / "kit" / name).read_text(encoding="utf-8")
            for word in ("fetch(", "XMLHttpRequest", "WebSocket", "getGamepads"):
                self.assertNotIn(word, source)

    def test_every_card_is_a_screenshot_at_the_card_size(self):
        from PIL import Image
        for game in read_games():
            with self.subTest(game=game["id"]):
                self.assertEqual(game["card"], f"/gamecards/{game['id']}.png")
                with Image.open(ROOT / "assets" / "gamecards" / f"{game['id']}.png") as picture:
                    self.assertEqual(picture.size, CARD_SIZE)
                self.assertTrue(game["controls"] and len(game["controls"]) <= 8)
                self.assertTrue(game["stage"])
        tool = (ROOT / "tools" / "game_cards.py").read_text(encoding="utf-8")
        self.assertIn("window.cabinet.card()", tool)
        self.assertIn('"width": 600, "height": 675', tool, "half the card size, drawn at twice the pixels")


class CabinetTests(unittest.TestCase):
    """The deck's Games page in a real browser, playing every cabinet."""

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

    def open_deck(self, real_csp=False, live=None):
        from tests.test_dashboard_overview_visuals import overview_state
        self.commands = []
        server = HtmlDashboardServer(WEB / "dashboard", image_root=ROOT / "assets" / "images",
                                     gamecard_root=ROOT / "assets" / "gamecards",
                                     command_callback=lambda payload: self.commands.append(payload) or True)
        self.addCleanup(server.stop)
        self.server = server
        state = overview_state()
        server.publish(state)
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
        self.state = state
        self.publish_games(live or {})
        page.wait_for_selector(".game-card")
        return page

    def publish_games(self, live):
        found = [{**game, "live": live.get(game["id"])} for game in read_games()]
        self.server.publish({**self.state, "workspace": {"page": "games", "ready": True,
                                                         "data": {"games": found, "card_size": list(CARD_SIZE), "card_folder": ""}}})

    def frame_for(self, page, game_id):
        deadline = time.time() + 10
        while time.time() < deadline:
            frames = [item for item in page.frames if item.url.endswith(f"/games/{game_id}/index.html")]
            if frames:
                return frames[-1]
            page.wait_for_timeout(50)
        self.fail(f"{game_id} never framed")

    def wait_for_command(self, page, test):
        deadline = time.time() + 6
        while time.time() < deadline:
            found = [item for item in self.commands if test(item)]
            if found:
                return found[-1]
            page.wait_for_timeout(50)
        self.fail(f"no such command in {self.commands}")

    def test_each_cabinet_draws_under_its_real_policies(self):
        from PIL import Image
        page = self.open_deck(real_csp=True)
        for game_id in CABINETS:
            with self.subTest(game=game_id):
                page.locator(f'.game-card[data-game-open="{game_id}"]').click()
                page.frame_locator("iframe.games-frame").locator("canvas").wait_for()
                page.wait_for_timeout(600)
                shot = Image.open(io.BytesIO(page.locator("iframe.games-frame").screenshot())).convert("RGB")
                lit = sum(1 for r, g, b in shot.get_flattened_data() if max(r, g, b) > 120)
                self.assertGreater(lit, 1500, f"{game_id}'s scripts ran in its sandbox and drew its screen")
                page.click("[data-game-back]")

    def test_each_cabinet_starts_and_reports_a_score(self):
        page = self.open_deck()
        for game_id in CABINETS:
            with self.subTest(game=game_id):
                page.locator(f'.game-card[data-game-open="{game_id}"]').click()
                page.wait_for_selector("#games-player:not([hidden]) iframe.games-frame")
                self.assertEqual(page.locator("iframe.games-frame").get_attribute("sandbox"), "allow-scripts")
                frame = self.frame_for(page, game_id)
                frame.wait_for_function("window.cabinet && window.cabinet.state().state === 'title'")
                page.frame_locator("iframe.games-frame").locator("canvas").click()
                frame.wait_for_function("window.cabinet.state().state === 'play'")
                page.wait_for_timeout(400)
                self.assertEqual(frame.evaluate("window.cabinet.state().state"), "play", f"{game_id} keeps playing")
                frame.evaluate("window.cabinet.end()")
                frame.wait_for_function("window.cabinet.state().state === 'over'", timeout=5000)
                score = self.wait_for_command(page, lambda item: item.get("operation") == "score" and item.get("game") == game_id)
                self.assertEqual(score["page"], "games")
                self.assertGreater(score["score"], 0)
                self.assertTrue(score["rank"])
                page.click("[data-game-back]")

    def test_the_crt_switch_is_kept_per_game(self):
        page = self.open_deck()
        page.locator('.game-card[data-game-open="docking-computer"]').click()
        frame = self.frame_for(page, "docking-computer")
        frame.wait_for_function("window.cabinet && window.cabinet.state().crt === true", timeout=5000)
        page.frame_locator("iframe.games-frame").locator("canvas").click()
        page.keyboard.press("c")
        frame.wait_for_function("window.cabinet.state().crt === false")
        page.wait_for_function("localStorage.getItem('voidcompass.games.docking-computer.crt') === '0'")
        self.assertIsNone(page.evaluate("localStorage.getItem('voidcompass.games.thargoid-swarm.crt')"), "only that game")
        page.click("[data-game-restart]")
        page.wait_for_timeout(300)
        frame = self.frame_for(page, "docking-computer")
        frame.wait_for_function("window.cabinet && window.cabinet.state().crt === false", timeout=5000)

    def test_keys_only_or_mouse_only_per_game(self):
        page = self.open_deck()
        page.locator('.game-card[data-game-open="rock-rats"]').click()
        frame = self.frame_for(page, "rock-rats")
        frame.wait_for_function("window.cabinet && window.cabinet.state().input === 'both'", timeout=5000)
        self.assertEqual(page.get_attribute('[data-game-input="both"]', "aria-pressed"), "true")
        page.click('[data-game-input="keys"]')
        frame.wait_for_function("window.cabinet.state().input === 'keys'")
        self.assertEqual(page.evaluate("localStorage.getItem('voidcompass.games.rock-rats.input')"), "keys")
        canvas = page.frame_locator("iframe.games-frame").locator("canvas")
        canvas.click()
        frame.wait_for_function("window.cabinet.state().state === 'play'")
        canvas.hover(position={"x": 40, "y": 40})
        canvas.hover(position={"x": 200, "y": 200})
        self.assertFalse(frame.evaluate("window.cabinet.state().pointer"), "the mouse doesn't steer on keys only")
        page.click('[data-game-input="mouse"]')
        frame.wait_for_function("window.cabinet.state().input === 'mouse'")
        page.click("[data-game-restart]")
        frame = self.frame_for(page, "rock-rats")
        frame.wait_for_function("window.cabinet && window.cabinet.state().input === 'mouse'", timeout=5000)
        page.click("[data-game-back]")

    def test_touchdown_and_the_scarab_go_at_the_journals_gravity(self):
        world = {"body": "Synuefe AB-C d1-2 3 a", "gravity": 2.4}
        page = self.open_deck(live={"touchdown": world, "scarab-patrol": world})
        for game_id in ("touchdown", "scarab-patrol"):
            with self.subTest(game=game_id):
                page.locator(f'.game-card[data-game-open="{game_id}"]').click()
                frame = self.frame_for(page, game_id)
                frame.wait_for_function("window.cabinet && window.cabinet.state().state === 'title'")
                page.frame_locator("iframe.games-frame").locator("canvas").click()
                frame.wait_for_function("window.cabinet.state().state === 'play'")
                state = frame.evaluate("window.cabinet.state()")
                self.assertEqual((state["gravity"], state["real"], state["body"]), (2.4, True, "Synuefe AB-C d1-2 3 a"))
                page.click("[data-game-back]")

    def test_hatchling_has_a_dedicated_three_js_cockpit_workspace(self):
        state = hatchling.new_state()
        page = self.open_deck(live={"hatchling": hatchling.view(state, time.time())})
        page.locator('.nav-item[data-page="hatchling"]').click()
        self.server.publish({**self.state, "workspace": {"page": "hatchling", "ready": True,
                                                           "data": hatchling.view(state, time.time())}})
        page.wait_for_selector(".hatchling-deck")
        page.wait_for_function("typeof window.Hatchling3D === 'object'")
        page.wait_for_function("document.querySelector('[data-hl-canvas]').width > 0")
        page.wait_for_function("document.querySelector('[data-hl-link]').textContent === 'READY TO HATCH'")
        page.evaluate("""() => {
          let calls = 0;
          const draw = window.Hatchling3D.draw.bind(window.Hatchling3D);
          window.Hatchling3D.draw = (...args) => { calls += 1; return draw(...args); };
          window.hatchlingDrawCalls = () => calls;
        }""")
        page.wait_for_function("window.hatchlingDrawCalls() > 1")
        self.assertNotIn("hatchling", [game["id"] for game in read_games()], "the pet is no longer an arcade card")
        page.locator("[data-hl-name]").fill("Moss")
        page.locator("[data-hl-act='hatch']").click()
        command = self.wait_for_command(page, lambda item: item.get("page") == "hatchling" and item.get("operation") == "action")
        self.assertEqual((command["action"], command["page"], command["act"]), ("workspace", "hatchling", "hatch"))
        self.assertEqual(command["value"]["name"], "Moss")


if __name__ == "__main__":
    unittest.main()
