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
        self.assertEqual(self.page.locator("#studio-overlay-opacity").input_value(), "65")
        self.assertEqual(self.page.locator("#studio-global-fade-value").text_content(), "65%")
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
