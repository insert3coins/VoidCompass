"""Browser checks for the redesigned dashboard pages outside Galactic Atlas."""

from pathlib import Path
import json
import unittest
from urllib.parse import urlsplit

from tests.test_dashboard_overview_visuals import overview_state


WEB = Path(__file__).resolve().parents[1] / "web"
IMAGE_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "images"
BRIDGE_PAGES = (
    "planet-materials", "explore", "records", "operations", "profile",
    "analytics", "chronicle", "mission", "ground", "mining",
    "engineering", "build-planner", "powerplay", "carrier", "recon",
    "achievements", "ledger", "settings", "overlay-studio", "about",
)
WORKSPACE_PAGES = (
    "planet-materials", "explore", "profile", "analytics", "chronicle",
    "mission", "ground", "mining", "engineering", "build-planner",
    "powerplay", "carrier", "recon", "achievements", "ledger", "settings",
)


class DashboardBridgePagesVisualTests(unittest.TestCase):
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

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1600, "height": 900})
        self.page.emulate_media(reduced_motion="reduce")
        self.errors = []
        self.missing = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/api/events":
                route.fulfill(content_type="application/json", body='{"closing":true}')
                return
            if path == "/api/command":
                route.fulfill(content_type="application/json", body='{"accepted":true}')
                return
            if path == "/api/snapshot":
                route.fulfill(content_type="application/json", body=json.dumps(overview_state()))
                return
            file = (IMAGE_ASSETS / path.removeprefix("/dashboard/images/")
                    if path.startswith("/dashboard/images/") else WEB / path.lstrip("/"))
            if path == "/dashboard/app.js":
                source = file.read_text(encoding="utf-8")
                source += """
                  window.__bridgeHarness = {
                    render(data) {
                      model = data;
                      applyTheme(data.theme || {});
                      document.body.classList.add('ready');
                      document.getElementById('boot').hidden = true;
                      document.getElementById('app').setAttribute('aria-hidden', 'false');
                      renderDashboard(data);
                    },
                    activate(name) {
                      document.querySelectorAll('.page').forEach(node =>
                        node.classList.toggle('active', node.dataset.pageName === name));
                    },
                    workspace(name, data) {
                      this.activate(name);
                      currentPage = name;
                      model.workspace = {page: name, ready: true, data};
                      workspaceFingerprints[name] = '';
                      renderWorkspace(model);
                    },
                    studio(data) {
                      this.activate('overlay-studio');
                      currentPage = 'overlay-studio';
                      model.overlay_studio = data;
                      renderOverlayStudio(model);
                    },
                    theme(value) { applyTheme(value); }
                  };
                """
                route.fulfill(content_type="application/javascript", body=source)
            elif file.is_file():
                route.fulfill(path=str(file))
            else:
                self.missing.append(path)
                route.fulfill(status=404, body="")

        self.page.route("http://bridge.test/**", serve)
        self.page.goto("http://bridge.test/dashboard/index.html")
        self.page.wait_for_function("Boolean(window.__bridgeHarness)")
        self.page.evaluate("data => window.__bridgeHarness.render(data)", overview_state())

    def tearDown(self):
        self.page.close()

    def test_every_non_map_page_keeps_its_masthead_in_bounds(self):
        found = self.page.locator(".page[data-page-name]").evaluate_all(
            "nodes => nodes.map(node => node.dataset.pageName)")
        self.assertEqual(set(BRIDGE_PAGES), set(found) - {"overview", "map"})
        for width, height in ((1600, 900), (980, 680)):
            self.page.set_viewport_size({"width": width, "height": height})
            for name in BRIDGE_PAGES:
                with self.subTest(page=name, width=width):
                    self.page.evaluate("name => window.__bridgeHarness.activate(name)", name)
                    geometry = self.page.evaluate("""name => {
                      const page = document.querySelector(`.page[data-page-name="${name}"]`);
                      const title = page.querySelector(':scope > .page-title, :scope > .about-hero');
                      const box = node => node.getBoundingClientRect();
                      const outer = box(page), heading = box(title);
                      const status = box(document.querySelector('.statusbar'));
                      return {
                        title: Boolean(title && title.querySelector('h2')),
                        headingFits: heading.left >= outer.left - 1 && heading.right <= outer.right + 1,
                        pageFits: page.scrollWidth <= page.clientWidth + 1,
                        statusVisible: status.height >= 25 && Math.abs(status.bottom - innerHeight) <= 1,
                      };
                    }""", name)
                    self.assertTrue(all(geometry.values()), (name, width, geometry))
        self.assertFalse(self.missing, self.missing)
        self.assertFalse(self.errors, self.errors)

    def test_global_overlay_fade_is_visible_and_sends_live_setting(self):
        snapshot = overview_state()
        snapshot["overlay_studio"] = {
            "desktop": {}, "overlays": [], "presets": [],
            "options": {"overlay_opacity_percent": 75},
        }
        self.page.evaluate("data => window.__bridgeHarness.render(data)", snapshot)
        self.page.evaluate("data => window.__bridgeHarness.studio(data)", snapshot["overlay_studio"])
        fade = self.page.locator("#studio-global-fade")
        self.assertTrue(fade.is_visible())
        self.assertEqual(fade.input_value(), "75")
        with self.page.expect_request(lambda request: "/api/command" in request.url
                                      and '"set_opacity"' in (request.post_data or "")) as submitted:
            fade.evaluate("input => { input.value = '65'; input.dispatchEvent(new Event('input', {bubbles: true})); }")
        payload = submitted.value.post_data_json
        self.assertEqual(payload["operation"], "set_opacity")
        self.assertEqual(payload["value"], 65)
        self.assertEqual(self.page.locator("#studio-global-fade-value").text_content(), "65%")
        self.assertFalse(self.errors, self.errors)

    def studio_snapshot(self):
        snapshot = overview_state()
        monitors = [
            {"id": "display-1", "number": 1, "label": "DISPLAY 1", "primary": True,
             "left": 0, "top": 0, "width": 2560, "height": 1440},
            {"id": "display-2", "number": 2, "label": "DISPLAY 2", "primary": False,
             "left": 2560, "top": 0, "width": 2560, "height": 1440},
        ]
        row = lambda id, label, short, x, monitor, enabled=True: {
            "id": id, "label": label, "short_label": short, "x": x, "y": 200,
            "width": 520, "height": 340, "enabled": enabled, "shown": enabled,
            "html_ready": enabled, "state": "HTML" if enabled else "OFF", "monitor": monitor}
        snapshot["overlay_studio"] = {
            "desktop": {"left": 0, "top": 0, "width": 5120, "height": 1440}, "monitors": monitors,
            "overlays": [row("hud", "Navigation HUD", "NAVIGATION", 40, "display-1"),
                         row("survey_status_hud", "Survey Operations", "SURVEY", 900, "display-1"),
                         row("cargo_hud", "Cargo Manifest", "CARGO", 3000, "display-2", False)],
            "presets": [], "ground_target": {},
            "options": {"overlay_opacity_percent": 90, "survey_spotlight_rotation": "auto",
                        "survey_spotlight_threshold": 15, "overlay_text_scale_percent": 100},
        }
        return snapshot

    def test_studio_is_one_view_showing_one_display_at_a_time(self):
        snapshot = self.studio_snapshot()
        self.page.evaluate("data => window.__bridgeHarness.render(data)", snapshot)
        self.page.evaluate("data => window.__bridgeHarness.studio(data)", snapshot["overlay_studio"])
        self.assertEqual(self.page.locator("[data-studio-view]").count(), 0, "no second view to switch to")
        cards = lambda: self.page.locator(".studio-overlay-card").evaluate_all(
            "nodes => nodes.map(node => node.dataset.overlayId)")
        self.assertEqual(cards(), ["hud", "survey_status_hud"])
        self.assertEqual(self.page.locator(".studio-monitor").count(), 2)
        # A display tab brings that screen onto the stage.
        self.page.locator('[data-studio-display="display-2"]').click()
        self.assertEqual(cards(), ["cargo_hud"])
        self.assertIn("DISPLAY 2", self.page.locator("#studio-desktop-label").text_content())
        # Choosing a surface in the roster follows it to its display.
        self.page.locator('.studio-index-row[data-overlay-id="survey_status_hud"] .studio-index-select').click()
        self.assertEqual(cards(), ["hud", "survey_status_hud"])
        # The inspector shows only that surface's own settings.
        visible = self.page.locator("[data-studio-settings]:visible").evaluate_all(
            "nodes => nodes.map(node => node.dataset.studioSettings)")
        self.assertEqual(visible, ["survey_status_hud"])
        self.assertEqual(self.page.locator("#studio-survey-threshold").input_value(), "15")
        self.assertFalse(self.errors, self.errors)

    def test_studio_names_every_surface_however_small(self):
        # A 34 px bar and a 54 px orb shrink to a sliver on the stage; each
        # still has to show its name in full, as the larger cards do.
        snapshot = self.studio_snapshot()
        studio = snapshot["overlay_studio"]
        sized = lambda id, short, x, y, width, height: {
            **studio["overlays"][0], "id": id, "label": short.title(), "short_label": short,
            "x": x, "y": y, "width": width, "height": height}
        studio["overlays"] = [studio["overlays"][0],
                              sized("galnet_ticker_hud", "GALNET", 850, 12, 860, 34),
                              sized("heartbeat_hud", "HEARTBEAT", 24, 1360, 54, 54),
                              sized("toast_hud", "NOTIFY", 2480, 80, 54, 54)]
        self.page.evaluate("data => window.__bridgeHarness.render(data)", snapshot)
        self.page.evaluate("data => window.__bridgeHarness.studio(data)", studio)
        labels = self.page.evaluate("""() => {
          const stage = document.getElementById('studio-overlay-cards').getBoundingClientRect();
          return Object.fromEntries([...document.querySelectorAll('.studio-overlay-card')].map(card => {
            const span = card.querySelector('span');
            const box = span.getBoundingClientRect();
            return [card.dataset.overlayId, {
              text: span.textContent.trim(),
              whole: span.scrollWidth <= span.clientWidth + 1 && box.height >= 8,
              onStage: box.left >= stage.left - 1 && box.right <= stage.right + 1,
              classes: [...card.classList].filter(name => ['slim', 'tiny', 'label-left'].includes(name)),
            }];
          }));
        }""")
        for overlay_id, text in (("hud", "NAVIGATION"), ("galnet_ticker_hud", "GALNET"),
                                 ("heartbeat_hud", "HEARTBEAT"), ("toast_hud", "NOTIFY")):
            with self.subTest(overlay=overlay_id):
                self.assertEqual(labels[overlay_id]["text"], text)
                self.assertTrue(labels[overlay_id]["whole"], labels[overlay_id])
                self.assertTrue(labels[overlay_id]["onStage"], labels[overlay_id])
        self.assertEqual(labels["hud"]["classes"], [])
        self.assertEqual(labels["galnet_ticker_hud"]["classes"], ["slim"])
        self.assertIn("tiny", labels["heartbeat_hud"]["classes"])
        self.assertNotIn("label-left", labels["heartbeat_hud"]["classes"])
        # One at the screen's right edge hangs its name inward.
        self.assertIn("label-left", labels["toast_hud"]["classes"])
        self.assertFalse(self.errors, self.errors)

    def test_studio_saves_each_setting_alone_and_moves_between_displays(self):
        snapshot = self.studio_snapshot()
        self.page.evaluate("data => window.__bridgeHarness.render(data)", snapshot)
        self.page.evaluate("data => window.__bridgeHarness.studio(data)", snapshot["overlay_studio"])
        self.page.locator('.studio-index-row[data-overlay-id="survey_status_hud"] .studio-index-select').click()
        with self.page.expect_request(lambda request: "/api/command" in request.url
                                      and '"save_settings"' in (request.post_data or "")) as saved:
            self.page.locator("#studio-survey-threshold").fill("20")
            self.page.locator("#studio-survey-threshold").dispatch_event("change")
        payload = saved.value.post_data_json
        self.assertEqual({key: payload[key] for key in payload if key not in {"action", "page"}},
                         {"operation": "save_settings", "survey_spotlight_threshold": "20"})
        # A surface keeps its place on its screen when it moves display.
        with self.page.expect_request(lambda request: "/api/command" in request.url
                                      and '"move"' in (request.post_data or "")) as moved:
            self.page.locator('[data-studio-move-display="display-2"]').click()
        payload = moved.value.post_data_json
        self.assertEqual((payload["overlay_id"], payload["x"], payload["y"], payload["commit"]),
                         ("survey_status_hud", 2560 + 900, 200, True))
        # The roster's switch enables a surface without selecting away.
        with self.page.expect_request(lambda request: "/api/command" in request.url
                                      and '"toggle"' in (request.post_data or "")) as toggled:
            self.page.locator('.studio-index-row[data-overlay-id="cargo_hud"] .studio-row-switch').click()
        self.assertEqual(toggled.value.post_data_json["overlay_id"], "cargo_hud")
        self.assertFalse(self.errors, self.errors)

    def test_live_workspaces_render_without_clipping_or_script_errors(self):
        for width, height in ((1600, 900), (980, 680)):
            self.page.set_viewport_size({"width": width, "height": height})
            for name in WORKSPACE_PAGES:
                with self.subTest(page=name, width=width):
                    data = ({"position": {"lat": None, "lon": None,
                                           "heading": None}} if name == "ground" else
                            {"selected_dossier": {"name": "Aisling Duval",
                                                  "slug": "aisling-duval",
                                                  "portrait": "aisling_duval.jpg"}}
                            if name == "powerplay" else {})
                    self.page.evaluate("args => window.__bridgeHarness.workspace(args.name, args.data)",
                                       {"name": name, "data": data})
                    geometry = self.page.evaluate("""name => {
                      const page = document.querySelector(`.page[data-page-name="${name}"]`);
                      const root = document.getElementById(`${name}-workspace`);
                      return {
                        loaded: Boolean(root && !root.classList.contains('loading-panel')),
                        content: Boolean(root && root.textContent.trim()),
                        pageFits: page.scrollWidth <= page.clientWidth + 1,
                      };
                    }""", name)
                    self.assertTrue(all(geometry.values()), (name, width, geometry))
        self.assertFalse(self.missing, self.missing)
        self.assertFalse(self.errors, self.errors)

    def test_galactic_atlas_is_visually_unchanged_by_bridge_styles(self):
        self.page.evaluate("window.__bridgeHarness.activate('map')")
        sample = """() => ['.atlas-page', '.atlas-dockbar', '.atlas-frame-shell',
                            '.atlas-placeholder'].map(selector => {
          const style = getComputedStyle(document.querySelector(selector));
          return [style.backgroundImage, style.backgroundColor, style.borderColor,
                  style.padding, style.fontSize, style.color];
        })"""
        with_bridge = self.page.evaluate(sample)
        self.page.evaluate("""() => document.querySelectorAll(
          'link[href="bridge-pages.css"], link[href="bridge-exploration.css"], link[href="bridge-systems.css"]'
        ).forEach(link => { link.disabled = true; })""")
        without_bridge = self.page.evaluate(sample)
        self.assertEqual(with_bridge, without_bridge)
        self.assertFalse(self.errors, self.errors)

    def test_non_map_bridge_pages_follow_profile_palette(self):
        selectors = (
            '.page[data-page-name="explore"] > .page-title',
            '.page[data-page-name="mining"] > .page-title',
            '.page[data-page-name="settings"] > .page-title',
        )
        sample = """selectors => selectors.map(selector => {
          const style = getComputedStyle(document.querySelector(selector));
          return [style.borderBottomColor, style.backgroundImage];
        })"""
        baseline = self.page.evaluate(sample, selectors)
        self.page.evaluate("theme => window.__bridgeHarness.theme(theme)", {
            "name": "Bridge Test", "palette": {
                "accent": "#bf73ff", "orange": "#ffcb55", "green": "#46dd87",
            },
        })
        themed = self.page.evaluate(sample, selectors)
        self.assertEqual(len(baseline), len(themed))
        for before, after in zip(baseline, themed):
            self.assertNotEqual(before, after)
        self.assertFalse(self.errors, self.errors)


if __name__ == "__main__":
    unittest.main()
