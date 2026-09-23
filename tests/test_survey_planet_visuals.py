"""Browser smoke checks for the journal-backed Survey planet atlas.

These exercise the real Survey markup, styling, and renderer headlessly.
Playwright is optional for the regular unittest suite.
"""

from pathlib import Path
import unittest
from urllib.parse import urlsplit


WEB = Path(__file__).resolve().parents[1] / "web"


class SurveyPlanetVisualTests(unittest.TestCase):
    def test_planet_classes_and_body_workflow(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Playwright is not installed")

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except Exception as exc:
                self.skipTest(f"Playwright Chromium is unavailable: {exc}")
            try:
                page = browser.new_page(viewport={"width": 520, "height": 900})
                failures = []
                page.on("pageerror", lambda error: failures.append(str(error)))

                def serve(route):
                    path = urlsplit(route.request.url).path
                    if path == "/assets/overlay-client.js":
                        # Capture the production renderer without starting the
                        # asynchronous overlay-server health loop.
                        route.fulfill(
                            content_type="application/javascript",
                            body="""
                              window.VoidCompassOverlay = {
                                applyTheme(root, palette, effects) {
                                  document.documentElement.style.setProperty('--scale',
                                    String(effects.text_scale || 1));
                                  root.classList.toggle('reduced-motion',
                                    Boolean(effects.reduced_motion));
                                  root.classList.toggle('no-crt', !effects.crt);
                                },
                                startPolling(options) {
                                  window.__surveyRender = options.render;
                                  window.__surveyContentHeight = options.contentHeight;
                                }
                              };
                            """,
                        )
                        return
                    file = WEB / path.lstrip("/")
                    if file.is_file():
                        route.fulfill(path=str(file))
                    else:
                        route.fulfill(status=404, body="")

                page.route("http://survey.test/**", serve)
                page.goto("http://survey.test/survey/index.html")

                def check_geometry():
                    # The host resizes to content_height after each render.
                    # Exercise the actual 420px overlay width, not just a
                    # generous browser viewport.
                    page.set_viewport_size({"width": 420, "height": 900})
                    host_height = page.evaluate("window.__surveyContentHeight()")
                    page.set_viewport_size({"width": 420, "height": host_height})
                    geometry = page.evaluate("""() => {
                      const box = selector => document.querySelector(selector).getBoundingClientRect();
                      const overview = box('#overview');
                      const content = box('#content'), footer = box('#footer');
                      const root = box('#survey');
                      const children = [...document.querySelector('#content').children];
                      const spheres = [...document.querySelectorAll('.target .planet-sphere')];
                      return {
                        bands: overview.top >= root.top - .5
                          && overview.bottom <= content.top + .5
                          && content.bottom <= footer.top + .5
                          && footer.bottom <= root.bottom + .5,
                        bandContentsFit: [...document.querySelector('#overview').children]
                            .every(child => child.getBoundingClientRect().bottom <= overview.bottom + 1),
                        bandOverflow: [...document.querySelectorAll('#overview > *')]
                          .map(child => ({name: child.className || child.tagName,
                            bottom: child.getBoundingClientRect().bottom,
                            limit: overview.bottom})),
                        titleStripAbsent: !document.querySelector('header')
                          && !document.body.textContent.includes('VOID COMPASS / FIELD ATLAS')
                          && !document.body.textContent.includes('SURVEY OPERATIONS'),
                        contentsFit: children.every(child => {
                          const bounds = child.getBoundingClientRect();
                          return bounds.top >= content.top - 1
                            && bounds.bottom <= content.bottom + 1
                            && bounds.left >= content.left - 1
                            && bounds.right <= content.right + 1;
                        }),
                        spheres: spheres.map(sphere => {
                          const bounds = sphere.getBoundingClientRect();
                          const card = sphere.closest('.target').getBoundingClientRect();
                          return bounds.width > 10 && bounds.height > 10
                            && bounds.left >= card.left - 1
                            && bounds.right <= card.right + 1
                            && bounds.top >= card.top - 1
                            && bounds.bottom <= card.bottom + 1
                            && getComputedStyle(sphere).backgroundImage !== 'none';
                        }),
                      };
                    }""")
                    self.assertTrue(geometry["bands"], geometry)
                    self.assertTrue(geometry["bandContentsFit"], geometry)
                    self.assertTrue(geometry["titleStripAbsent"], geometry)
                    self.assertTrue(geometry["contentsFit"], geometry)
                    self.assertTrue(geometry["spheres"], geometry)
                    self.assertTrue(all(geometry["spheres"]), geometry)
                    return host_height

                def collect_pages(expected_total, max_height=None, geometry_each_page=True):
                    """Walk the real page controller, keeping the host at its measured size."""
                    state = page.evaluate("window.VoidCompassSurveyAtlas.getState()")
                    self.assertEqual(state["total"], expected_total, state)
                    self.assertGreaterEqual(state["pages"], 1, state)
                    self.assertEqual(state["page"], 1, state)
                    collected = []
                    for number in range(1, state["pages"] + 1):
                        current = page.evaluate("window.VoidCompassSurveyAtlas.getState()")
                        self.assertEqual(current["page"], number, current)
                        if geometry_each_page or number in (1, state["pages"]):
                            height = check_geometry()
                            if max_height is not None:
                                self.assertLessEqual(height, max_height, current)
                        self.assertEqual(page.locator(".atlas-roster").count(), 0)
                        view = page.evaluate("""() => ({
                          banner: document.querySelector('.atlas-page-banner')?.textContent || '',
                          cards: [...document.querySelectorAll('.target')].map(card => ({
                            text: card.textContent,
                            designation: card.querySelector('.target-name')?.textContent,
                            kind: card.querySelector('.planet-orb')?.dataset.planetKind || null,
                            orbCount: card.querySelectorAll('.planet-orb').length,
                            orbWidth: card.querySelector('.planet-orb')?.getBoundingClientRect().width || 0,
                            ringed: Boolean(card.querySelector('.planet-orb.has-rings')),
                            details: [...card.querySelectorAll('.biological-name')]
                              .map(detail => detail.textContent),
                          })),
                          notable: [...document.querySelectorAll('.notable-card')].map(card => ({
                            text: card.textContent,
                            orbCount: card.querySelectorAll('.planet-orb').length,
                          })),
                        })""")
                        if state["pages"] > 1:
                            banner = view["banner"]
                            self.assertTrue(banner, current)
                            self.assertRegex(banner, rf"\b{number}\s*/\s*{state['pages']}\b")
                            self.assertRegex(banner, r"\d+\s*[-–—]\s*\d+")
                        collected.extend(view["cards"])
                        collected.extend(view["notable"])
                        page.evaluate("window.VoidCompassSurveyAtlas.nextPage()")
                    self.assertEqual(page.evaluate("window.VoidCompassSurveyAtlas.getState().page"), 1)
                    self.assertEqual(len(collected), expected_total, collected)
                    return collected

                classes = [
                    ("Earth-like world", "earthlike"),
                    ("Water world", "water"),
                    ("Ammonia world", "ammonia"),
                    ("Gas giant with water-based life", "gas-water"),
                    ("Icy body", "icy"),
                    ("Rocky body", "rocky"),
                    ("High metal content body", "metal"),
                    (None, "unknown"),
                ]
                rows = []
                for index, (planet_class, _) in enumerate(classes, 1):
                    rows.append({
                        "name": f"Atlas A {index}",
                        "display_name": f"Atlas A {index}",
                        "planet_class": planet_class,
                        "ring_count": 2 if index == 4 else 0,
                        "bio_count": 1,
                        "complete": 0,
                        "bio_details": [{"name": f"Genus {index}", "kind": "detected"}],
                        "needs_dss": True,
                        "priority": True,
                    })
                system = {
                    "survey": {
                        "mode": "system", "system": "Atlas", "rows": rows,
                        "total_known": True, "scanned": 4, "total": 8,
                    },
                    "effects": {"reduced_motion": True},
                }
                page.evaluate("snapshot => window.__surveyRender(snapshot)", system)
                rendered = page.evaluate("""() => ({
                  mode: document.querySelector('#survey').classList.contains('system'),
                  fss: document.querySelector('#overview').textContent,
                  modeLabel: document.querySelector('#mode-label')?.textContent,
                  systemName: document.querySelector('#system-name')?.textContent,
                  height: window.__surveyContentHeight(),
                  reduced: document.querySelector('#survey').classList.contains('reduced-motion'),
                  animated: [...document.querySelectorAll('.planet-orb, .planet-orb *')]
                    .some(element => ['','::before','::after'].some(pseudo =>
                      getComputedStyle(element, pseudo || null).animationName !== 'none')),
                })""")
                self.assertTrue(rendered["mode"])
                self.assertIn("FSS", rendered["fss"])
                self.assertIn("4/8", rendered["fss"])
                self.assertTrue(rendered["modeLabel"].startswith("SYSTEM"), rendered)
                self.assertEqual(rendered["systemName"], "Atlas")
                self.assertTrue(rendered["reduced"])
                self.assertFalse(rendered["animated"])
                self.assertGreater(rendered["height"], 90)
                cards = collect_pages(len(classes), max_height=700)
                for index, (_, expected_kind) in enumerate(classes, 1):
                    with self.subTest(index=index, kind=expected_kind):
                        matches = [card for card in cards
                                   if card["designation"] == f"A {index}"]
                        self.assertEqual(len(matches), 1, matches)
                        self.assertEqual(matches[0]["kind"], expected_kind)
                        self.assertEqual(matches[0]["orbCount"], 1)
                        self.assertLessEqual(matches[0]["orbWidth"], 32)
                        self.assertEqual(matches[0]["ringed"], index == 4)
                for scale in (1.5, 2):
                    with self.subTest(mode="system", text_scale=scale):
                        system["effects"]["text_scale"] = scale
                        page.evaluate("snapshot => window.__surveyRender(snapshot)", system)
                        scaled = collect_pages(len(classes), max_height=700)
                        self.assertEqual({card["designation"] for card in scaled},
                                         {f"A {index}" for index in range(1, len(classes) + 1)})

                crowded_rows = []
                for index in range(1, 25):
                    crowded_rows.append({
                        "name": f"Atlas B {index}",
                        "display_name": f"Atlas B {index}",
                        "planet_class": classes[(index - 1) % len(classes)][0],
                        "bio_count": 2,
                        "complete": 0,
                        "bio_details": [
                            {"name": f"Fungoid {index}", "kind": "detected"},
                            {"name": f"Tussock {index}", "kind": "predicted"},
                        ],
                        "needs_dss": True,
                        "priority": True,
                    })
                crowded = {
                    "survey": {
                        "mode": "system", "system": "Atlas", "rows": crowded_rows,
                        "total_known": True, "scanned": 18, "total": 24,
                    },
                    "effects": {"reduced_motion": True, "text_scale": 1},
                }
                page.evaluate("snapshot => window.__surveyRender(snapshot)", crowded)
                state = page.evaluate("window.VoidCompassSurveyAtlas.getState()")
                self.assertGreater(state["pages"], 1, state)
                crowded_names = [f"B {index}" for index in range(1, 25)]
                crowded_cards = collect_pages(
                    len(crowded_rows), max_height=700,
                )
                self.assertEqual([card["designation"] for card in crowded_cards],
                                 crowded_names)
                for index, card in enumerate(crowded_cards, 1):
                    self.assertEqual(card["orbCount"], 1)
                    self.assertEqual(card["details"],
                                     [f"Fungoid {index}", f"Tussock {index}"])
                # Reduced motion must turn off visual animation, not hide later pages.
                self.assertTrue(page.evaluate("document.querySelector('#survey').classList.contains('reduced-motion')"))

                page.emulate_media(reduced_motion="no-preference")
                crowded["effects"]["reduced_motion"] = False
                page.evaluate("snapshot => window.__surveyRender(snapshot)", crowded)
                animation = page.evaluate("""() => {
                  const sphere = document.querySelector('.planet-earthlike .planet-sphere');
                  return {
                    surface: getComputedStyle(sphere, '::before').animationName,
                    fixedLight: getComputedStyle(sphere, '::after').animationName,
                    transform: getComputedStyle(sphere, '::before').transform,
                  };
                }""")
                self.assertEqual(animation["surface"], "planet-turn")
                self.assertEqual(animation["fixedLight"], "none")
                page.wait_for_timeout(250)
                moved = page.evaluate("""() => getComputedStyle(
                  document.querySelector('.planet-earthlike .planet-sphere'),
                  '::before').transform""")
                self.assertNotEqual(moved, animation["transform"])
                crowded["effects"]["reduced_motion"] = True
                page.evaluate("snapshot => window.__surveyRender(snapshot)", crowded)
                self.assertEqual(page.evaluate("""() => getComputedStyle(
                  document.querySelector('.planet-earthlike .planet-sphere'),
                  '::before').animationName"""), "none")

                stress_rows = [{
                    "name": f"Atlas C {index}", "display_name": f"Atlas C {index}",
                    "planet_class": "Rocky body", "bio_count": 1,
                    "complete": 0, "needs_dss": True, "priority": True,
                } for index in range(1, 102)]
                stress = {
                    "survey": {
                        "mode": "system", "system": "Atlas", "rows": stress_rows,
                        "total_known": True, "scanned": 21, "total": 101,
                    },
                    "effects": {"reduced_motion": True, "text_scale": 1},
                }
                page.evaluate("snapshot => window.__surveyRender(snapshot)", stress)
                stress_state = page.evaluate("window.VoidCompassSurveyAtlas.getState()")
                self.assertGreater(stress_state["pages"], 10, stress_state)
                stress_names = [f"C {index}" for index in range(1, 102)]
                stress_cards = collect_pages(
                    101, max_height=700, geometry_each_page=False,
                )
                self.assertEqual([card["designation"] for card in stress_cards],
                                 stress_names)
                self.assertTrue(all(card["orbCount"] == 1 for card in stress_cards))

                body = {
                    "survey": {
                        "mode": "body", "system": "Atlas",
                        "body": {
                            "name": "Atlas A 2", "planet_class": "Water world",
                            "bio_count": 2, "organic_complete_count": 0,
                            "geo_count": 1, "landable": True,
                        },
                        "body_display": "Atlas A 2", "min_value": 100000,
                        "max_value": 200000,
                        "rows": [
                            {"name": "Bacterium Sample", "kind": "sample", "progress": 2},
                            {"name": "Fonticulua Detected", "kind": "detected"},
                        ],
                        "sampling": {
                            "species": "Bacterium Sample", "progress": 2,
                            "clear": False, "min_distance_m": 240,
                            "colony_m": 500,
                        },
                    },
                    "effects": {"reduced_motion": True},
                }
                page.evaluate("snapshot => window.__surveyRender(snapshot)", body)
                focused = page.evaluate("""() => ({
                  mode: document.querySelector('#survey').classList.contains('body'),
                  modeLabel: document.querySelector('#mode-label')?.textContent,
                  systemName: document.querySelector('#system-name')?.textContent,
                  targetCount: document.querySelectorAll('.target').length,
                  kind: document.querySelector('.target .planet-orb')?.dataset.planetKind,
                  sampleCount: document.querySelectorAll('.sample-card').length,
                  sampleDone: document.querySelectorAll('.sample-node.done').length,
                  text: document.querySelector('#content').textContent,
                })""")
                self.assertTrue(focused["mode"])
                self.assertTrue(focused["modeLabel"].startswith("BODY"), focused)
                self.assertEqual(focused["systemName"], "Atlas")
                self.assertEqual(focused["targetCount"], 1)
                self.assertEqual(focused["kind"], "water")
                self.assertEqual(focused["sampleCount"], 1)
                self.assertEqual(focused["sampleDone"], 2)
                self.assertEqual(focused["text"].count("Bacterium Sample"), 1)
                self.assertEqual(focused["text"].count("Fonticulua Detected"), 1)
                self.assertEqual(page.locator(".atlas-roster").count(), 0)
                check_geometry()
                for scale in (1.5, 2):
                    with self.subTest(text_scale=scale):
                        body["effects"]["text_scale"] = scale
                        page.evaluate("snapshot => window.__surveyRender(snapshot)", body)
                        check_geometry()
                self.assertEqual(failures, [])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
