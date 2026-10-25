"""5.6.7: the Hatchling's shared, transparent Three.js renderer."""

from __future__ import annotations

import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HatchlingRenderer3DTests(unittest.TestCase):
    def test_both_views_load_the_shared_local_renderer(self):
        game = (ROOT / "web" / "games" / "hatchling" / "index.html").read_text(encoding="utf-8")
        overlay = (ROOT / "web" / "hatchling" / "index.html").read_text(encoding="utf-8")
        renderer = (ROOT / "web" / "assets" / "hatchling-3d.js").read_text(encoding="utf-8")
        life = (ROOT / "web" / "assets" / "hatchling-life.js").read_text(encoding="utf-8")

        self.assertIn('src="../../assets/hatchling-3d.js"', game)
        self.assertIn('src="/assets/hatchling-3d.js"', overlay)
        self.assertIn('from "../galactic_map/vendor/three.module.min.js"', renderer)
        self.assertIn('alpha: true', renderer)
        game_script = (ROOT / "web" / "games" / "hatchling" / "game.js").read_text(encoding="utf-8")
        self.assertIn('<script defer src="game.js"></script>', game)
        self.assertIn("if (!window.Hatchling3D)", game_script)
        self.assertIn("threeOnly: true", game_script)
        self.assertNotIn("HatchlingArt.draw(ctx, egg, art)", game_script)
        self.assertIn("window.Hatchling3D?.draw(ctx, egg, art)", game_script)
        self.assertIn("window.Hatchling3D?.draw(ctx, shown", life)
        self.assertIn("threeOnly = false", life)
        self.assertIn("if (!rendered3d && !threeOnly)", life)
        egg_model = renderer.split("function makeEgg(root, pet, tone) {", 1)[1].split("function formMarks", 1)[0]
        self.assertNotIn("TorusGeometry", egg_model, "the egg has no ring around its base")

    def test_dashboard_serves_only_the_renderer_and_its_two_three_modules(self):
        from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer

        server = HtmlDashboardServer.__new__(HtmlDashboardServer)
        server.static_root = (ROOT / "web" / "dashboard").resolve()
        server.image_root = None
        for path, expected in (
            ("/assets/hatchling-3d.js", ROOT / "web" / "assets" / "hatchling-3d.js"),
            ("/galactic_map/vendor/three.module.min.js", ROOT / "web" / "galactic_map" / "vendor" / "three.module.min.js"),
            ("/galactic_map/vendor/three.core.min.js", ROOT / "web" / "galactic_map" / "vendor" / "three.core.min.js"),
        ):
            self.assertEqual(server._static_path(path), expected.resolve())
        self.assertIsNone(server._static_path("/../assets/hatchling-3d.js"))

    def test_renderer_draws_all_pet_families_in_a_browser(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")

        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            functools.partial(QuietHandler, directory=str(ROOT / "web")),
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 800, "height": 600})
                errors = []
                page.on("console", lambda message: errors.append(message.text)
                        if message.type == "error" or "Hatchling's 3D renderer unavailable" in message.text else None)
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_address[1]}/games/hatchling/")
                page.wait_for_function("Boolean(window.Hatchling3D)")
                page.evaluate("""() => {
                  const draw = window.Hatchling3D.draw.bind(window.Hatchling3D);
                  let calls = 0;
                  window.Hatchling3D.draw = (...args) => { calls++; return draw(...args); };
                  window.hatchling3dCalls = () => calls;
                }""")
                page.wait_for_function("window.hatchling3dCalls() >= 3")
                result = page.evaluate("""async () => {
              const canvas = document.createElement('canvas');
              canvas.width = canvas.height = 420;
              const ctx = canvas.getContext('2d');
              const families = [
                {species: 'larva', stage: 'adult', form: 'rare'},
                {species: 'bot', stage: 'juvenile'},
                {species: 'bot', stage: 'adult', form: 'scarred'},
                {species: 'larva', stage: 'juvenile', form: 'explored'},
                {species: 'sample', kind: 'bacterium', stage: 'hatchling'},
                {species: 'sample', kind: 'tubus', stage: 'adult'},
                {species: 'sample', kind: 'fungoida', stage: 'juvenile'},
                {species: 'sample', kind: 'fungoida', stage: 'adult', dormant: true},
                {species: 'larva', stage: 'egg'},
              ];
              const gl = document.createElement('canvas').getContext('webgl2');
              const life = window.HatchlingLife.create({size: 150, range: 0});
              const rows = [];
              for (const [index, pet] of families.entries()) {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                const rendered = window.Hatchling3D.draw(ctx, {
                  ...pet, needs: {mood: 85}, mood_word: 'HAPPY', reaction: 'happy',
                }, {x: 210, y: 190, size: 150, t: index * .7, look: [.4, -.2], aura: true});
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                life.drawPet(ctx, {...pet, needs: {mood: 85}, mood_word: 'HAPPY', reaction: 'happy'},
                  {x: 210, y: 190, size: 150, t: index * .7});
                const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
                let visible = 0;
                for (let i = 3; i < pixels.length; i += 4) if (pixels[i] > 0) visible++;
                const cornerAlpha = ctx.getImageData(0, 0, 1, 1).data[3];
                rows.push({species: pet.species, kind: pet.kind || '', rendered, visible, cornerAlpha});
              }
              const activities = [
                {name: 'idle', t: 1},
                {name: 'toy', t: 2, toy: {kind: 'relic', x: 32}},
                {name: 'keepy', t: 3, ball: {x: -12, y: -62, spin: .4}},
                {name: 'tower', t: 4, tower: {x: 55, cans: 3, lean: .08, drop: {y: -45}}},
                {name: 'tag', t: 5, thargon: {x: 42, y: -30, spin: .6}},
                {name: 'chase', t: 6, mote: {x: -48, y: -34}},
                {name: 'stars', t: 7, stars: {points: [{x:-50,y:-65},{x:-18,y:-40},{x:20,y:-72},{x:52,y:-48}], lit: 3, fade: 1}},
                {name: 'stargaze', t: 8, star: {x: 35, y: -54}},
                {name: 'holo', t: 9, orb: {x: -28, y: -60}},
                {name: 'trick', trick: 'juggle', t: 2.5},
              ];
              const propRows = activities.map((activity, index) => {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                const rendered = window.Hatchling3D.draw(ctx, {species: 'larva', stage: 'juvenile', needs: {mood: 90}}, {
                  x: 210, y: 190, size: 150, t: index * .6, activity,
                  toys: ['pebble', 'relic', 'sensor', 'fragment', 'beacon', 'model'].map((kind, i) => ({kind, x: (i - 3) * 24, y: 66})),
                });
                const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
                let visible = 0;
                for (let i = 3; i < pixels.length; i += 4) if (pixels[i] > 0) visible++;
                return {name: activity.name, rendered, visible};
              });
              return {webgl2: Boolean(gl), rows, propRows, idleActs: life.acts};
                }""")
                self.assertEqual(len(result["rows"]), 9)
                self.assertTrue(result["webgl2"], "Chromium must expose WebGL2 to exercise the renderer")
                if result["webgl2"]:
                    self.assertTrue(all(row["rendered"] for row in result["rows"]), result)
                self.assertTrue(all(row["visible"] > 0 for row in result["rows"]), result)
                self.assertTrue(all(row["cornerAlpha"] == 0 for row in result["rows"]), result)
                self.assertEqual(len(result["propRows"]), 10)
                self.assertTrue(all(row["rendered"] and row["visible"] > 0 for row in result["propRows"]), {**result, "console": errors})
                self.assertTrue({"stretch", "groom", "holo"}.issubset(result["idleActs"]), result)
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_three_modules_load_inside_the_dashboard_games_sandbox(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer

        server = HtmlDashboardServer(ROOT / "web" / "dashboard", games_root=ROOT / "web" / "games")
        self.addCleanup(server.stop)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                errors = []
                page_errors = []
                module_headers = {}
                page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
                page.on("pageerror", lambda error: page_errors.append(str(error)))

                def record_module(response):
                    for path in ("/assets/hatchling-3d.js", "/galactic_map/vendor/three.module.min.js",
                                 "/galactic_map/vendor/three.core.min.js"):
                        if response.url.endswith(path):
                            module_headers[path] = response.headers.get("access-control-allow-origin")

                page.on("response", record_module)
                page.goto(server.url, wait_until="domcontentloaded")
                page.evaluate("""() => {
                  const frame = document.createElement('iframe');
                  frame.setAttribute('sandbox', 'allow-scripts');
                  frame.src = '/games/hatchling/index.html';
                  document.body.append(frame);
                }""")
                frame = None
                for _ in range(100):
                    frame = next((candidate for candidate in page.frames
                                  if candidate.url.endswith("/games/hatchling/index.html")), None)
                    if frame:
                        break
                    page.wait_for_timeout(50)
                self.assertIsNotNone(frame, "dashboard did not load the sandboxed Hatchling cabinet")
                frame.wait_for_load_state("load")
                page.wait_for_timeout(500)
                self.assertEqual(frame.evaluate("typeof window.Hatchling3D"), "object",
                                 f"module_headers={module_headers}; console={errors}; page_errors={page_errors}")
                self.assertEqual(set(module_headers), {
                    "/assets/hatchling-3d.js", "/galactic_map/vendor/three.module.min.js",
                    "/galactic_map/vendor/three.core.min.js",
                })
                self.assertEqual(set(module_headers.values()), {"*"})
                self.assertFalse([error for error in errors if "CORS" in error or "module script" in error], errors)
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
