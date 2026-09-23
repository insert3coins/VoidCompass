"""Browser checks for the commander Achievements workspace and its live controls."""

from pathlib import Path
import json
import unittest
from urllib.parse import urlsplit


WEB = Path(__file__).resolve().parents[1] / "web"


class AchievementWorkspaceVisualTests(unittest.TestCase):
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
        self.errors = []
        self.commands = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/api/events":
                route.fulfill(content_type="application/json", body='{"closing":true}')
                return
            if path == "/api/command":
                self.commands.append(route.request.post_data_json)
                route.fulfill(content_type="application/json", body='{"accepted":true}')
                return
            file = WEB / path.lstrip("/")
            if path == "/dashboard/app.js":
                source = file.read_text(encoding="utf-8")
                source += """
                  window.__achievementHarness = {
                    render(data) {
                      model = {workspace: {page: 'achievements', ready: true, data}};
                      document.body.classList.add('ready');
                      document.getElementById('boot').hidden = true;
                      document.querySelectorAll('.page').forEach(node =>
                        node.classList.toggle('active', node.dataset.pageName === 'achievements'));
                      renderAchievementsWorkspace(data);
                    },
                    theme(theme) { applyTheme(theme); }
                  };
                """
                route.fulfill(content_type="application/javascript", body=source)
            elif file.is_file():
                route.fulfill(path=str(file))
            else:
                route.fulfill(status=404, body="")

        self.page.route("http://achievements.test/**", serve)
        self.page.goto("http://achievements.test/dashboard/index.html")
        self.page.wait_for_function("Boolean(window.__achievementHarness)")

    def tearDown(self):
        self.page.close()

    def render(self, data):
        self.page.evaluate("data => window.__achievementHarness.render(data)", data)

    @staticmethod
    def row(id, title, category, current=0, target=1, *, unlocked=False, unlocked_at=""):
        return {
            "id": id, "title": title, "description": f"Discover {title}",
            "category": category, "points": 50, "current": current,
            "target": target, "unlocked": unlocked, "unlocked_at": unlocked_at,
        }

    def test_empty_record_and_200_percent_zoom_fit(self):
        self.render({"achievements": [], "total": 0, "unlocked": 0, "points": 0,
                     "categories": [], "enabled": True, "notifications_enabled": False})
        self.assertIn("CATALOGUE UNAVAILABLE", self.page.locator(".achievement-empty").inner_text())
        self.assertIn("0.0%", self.page.locator(".achievement-dial").inner_text())
        self.assertIn("next milestone awaits", self.page.locator(".achievement-spotlight").inner_text().lower())
        self.assertEqual(self.page.locator(".achievement-tile").count(), 0)

        self.page.locator("#achievements-workspace").evaluate("node => node.style.zoom = '200%'")
        geometry = self.page.evaluate("""() => {
          const root = document.querySelector('#achievements-workspace').getBoundingClientRect();
          return [...document.querySelectorAll('.achievement-overview,.achievement-spotlight,.achievement-preferences,.achievement-archive')]
            .map(node => {
              const box = node.getBoundingClientRect();
              return {name: node.className, left: box.left, right: box.right,
                fits: box.left >= root.left - 1 && box.right <= root.right + 1};
            });
        }""")
        self.assertTrue(all(item["fits"] for item in geometry), geometry)
        self.page.locator("#achievements-workspace").evaluate("node => node.style.zoom = ''")
        self.page.set_viewport_size({"width": 480, "height": 900})
        mobile = self.page.evaluate("""() => {
          const root = document.querySelector('#achievements-workspace').getBoundingClientRect();
          return [...document.querySelectorAll('.achievement-overview,.achievement-spotlight,.achievement-preferences,.achievement-archive')]
            .map(node => {
              const box = node.getBoundingClientRect();
              return {name: node.className,
                fits: box.left >= root.left - 1 && box.right <= root.right + 1};
            });
        }""")
        self.assertTrue(all(item["fits"] for item in mobile), mobile)
        self.assertFalse(self.errors, self.errors)

    def test_archive_filters_pagination_refresh_and_commands(self):
        rows = [self.row("near", "Nearest Discovery", "Exploration", 8, 10),
                self.row("bio", "First Sample", "Exobiology", 0, 1),
                self.row("earned", "Old Explorer", "Exploration", 1, 1,
                         unlocked=True, unlocked_at="2026-09-01T12:00:00Z")]
        rows.extend(self.row(f"locked-{index}", f"Uncharted {index}", "Exploration")
                    for index in range(28))
        data = {"achievements": rows, "total": len(rows), "unlocked": 1,
                "points": 50, "categories": ["Exploration", "Exobiology"],
                "enabled": True, "notifications_enabled": True}
        self.render(data)
        self.assertEqual(self.page.locator(".achievement-tile").count(), 24)
        self.assertIn("NEAREST DISCOVERY", self.page.locator(".achievement-spotlight h3").inner_text())
        self.assertIn("OLD EXPLORER", self.page.locator(".achievement-latest strong").inner_text())
        self.page.locator("#achievement-more").click()
        self.assertEqual(self.page.locator(".achievement-tile").count(), len(rows))

        self.page.locator('[data-achievement-category="Exobiology"]').click()
        self.assertEqual(self.page.locator(".achievement-tile").count(), 1)
        self.assertIn("First Sample", self.page.locator(".achievement-tile").inner_text())
        self.page.locator('[data-achievement-state="earned"]').click()
        self.assertIn("NO MILESTONES MATCH", self.page.locator(".achievement-empty").inner_text())
        self.page.locator('[data-achievement-category="all"]').click()
        self.assertIn("Old Explorer", self.page.locator(".achievement-tile").inner_text())
        self.page.locator('[data-achievement-state="all"]').click()
        self.page.locator("#achievement-filter").fill("Nearest")
        self.assertEqual(self.page.locator(".achievement-tile").count(), 1)
        self.render(data)
        self.assertEqual(self.page.locator("#achievement-filter").input_value(), "Nearest")
        self.assertEqual(self.page.locator(".achievement-tile").count(), 1)
        self.page.locator(".achievement-tile [data-ws-op='manual_unlock']").click()
        self.page.wait_for_timeout(50)
        self.assertTrue(any(command.get("page") == "achievements"
                            and command.get("operation") == "manual_unlock"
                            and command.get("achievement_id") == "near"
                            for command in self.commands), self.commands)
        self.page.locator('[data-ws-op="set_enabled"]').click()
        self.page.locator('[data-ws-op="set_notifications"]').click()
        self.page.wait_for_timeout(50)
        self.assertTrue(any(command.get("operation") == "set_enabled"
                            and command.get("enabled") is False
                            for command in self.commands), self.commands)
        self.assertTrue(any(command.get("operation") == "set_notifications"
                            and command.get("enabled") is False
                            for command in self.commands), self.commands)

        self.page.locator("#achievement-filter").fill("")
        self.page.locator("#achievements-workspace").evaluate("node => node.style.zoom = '200%'")
        geometry = self.page.evaluate("""() => [...document.querySelectorAll('.achievement-tile')].map(card => {
          const box = card.getBoundingClientRect();
          const footer = card.querySelector('footer').getBoundingClientRect();
          return {title: card.querySelector('h3').textContent,
            fits: footer.left >= box.left - 1 && footer.right <= box.right + 1,
            textFits: card.scrollWidth <= card.clientWidth + 1};
        })""")
        self.assertTrue(all(item["fits"] and item["textFits"] for item in geometry),
                        json.dumps(geometry, indent=2))
        self.assertFalse(self.errors, self.errors)

    def test_profile_palette_updates_achievement_workspace_in_place(self):
        data = {"achievements": [self.row("near", "Nearest Discovery", "Exploration", 8, 10),
                                 self.row("earned", "Old Explorer", "Exploration", 1, 1,
                                          unlocked=True, unlocked_at="2026-09-01T12:00:00Z")],
                "total": 2, "unlocked": 1, "points": 50,
                "categories": ["Exploration"], "enabled": True,
                "notifications_enabled": True}
        self.render(data)
        self.page.evaluate("""() => window.__achievementHarness.theme({
          name: 'Custom A', available: ['Custom A', 'Custom B'],
          palette: {bg: '#150e20', panel: '#21162c', panel_alt: '#301d3c',
            header: '#180f22', input: '#1c1226', inset: '#1e1428',
            border: '#654677', border_soft: '#482f59', selection: '#4a2b58',
            accent: '#f36ce0', orange: '#ffc250', text: '#f8eefa',
            muted: '#c2abc9', dim: '#967b9e', green: '#79e5a8',
            yellow: '#ffe079', red: '#ff829b'}
        })""")
        self.page.wait_for_function("""() => getComputedStyle(
          document.querySelector('.achievement-categories button[aria-pressed="true"]')
        ).color === 'rgb(243, 108, 224)'""")
        themed = self.page.evaluate("""() => {
          const css = selector => getComputedStyle(document.querySelector(selector));
          return {
            panel: css('.achievement-overview').backgroundImage,
            card: css('.achievement-tile').backgroundImage,
            dial: css('.achievement-dial').backgroundImage,
            accent: css('.achievement-kicker').color,
            active: css('.achievement-tile.active .achievement-state').color,
            earned: css('.achievement-tile.earned .achievement-state').color,
            control: css('.achievement-categories button[aria-pressed="true"]').color,
          };
        }""")
        self.assertIn("rgb(243, 108, 224)", themed["dial"])
        self.assertIn("rgb(33, 22, 44)", themed["panel"])
        self.assertIn("rgb(48, 29, 60)", themed["card"])
        self.assertEqual(themed["accent"], "rgb(243, 108, 224)")
        self.assertEqual(themed["active"], "rgb(255, 194, 80)")
        self.assertEqual(themed["earned"], "rgb(121, 229, 168)")
        self.assertEqual(themed["control"], "rgb(243, 108, 224)")

        self.page.evaluate("""() => window.__achievementHarness.theme({
          name: 'Custom B', available: ['Custom A', 'Custom B'],
          palette: {panel: '#141c25', panel_alt: '#1a2936', accent: '#68c8ff',
            orange: '#ff8c74', green: '#92f2b2'}
        })""")
        switched = self.page.evaluate("""() => ({
          accent: getComputedStyle(document.querySelector('.achievement-kicker')).color,
          active: getComputedStyle(document.querySelector('.achievement-tile.active .achievement-state')).color,
          earned: getComputedStyle(document.querySelector('.achievement-tile.earned .achievement-state')).color,
        })""")
        self.assertEqual(switched, {"accent": "rgb(104, 200, 255)",
                                    "active": "rgb(255, 140, 116)",
                                    "earned": "rgb(146, 242, 178)"})
        self.assertFalse(self.errors, self.errors)
