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
                        targetCount: document.querySelectorAll('.target').length,
                        noBioDuplicates: (() => {
                          const targets = new Set([...document.querySelectorAll('.target-name')]
                            .map(item => item.textContent));
                          return [...document.querySelectorAll('.bio-pin-name')]
                            .every(item => !targets.has(item.textContent));
                        })(),
                        pinContentsFit: [...document.querySelectorAll('.bio-pin')]
                          .every(pin => {
                            const bounds = pin.getBoundingClientRect();
                            return [...pin.querySelectorAll(
                              '.bio-pin-name, .bio-pin-class, .bio-pin-badges, .bio-pin-detail')]
                              .every(item => {
                                const part = item.getBoundingClientRect();
                                return part.left >= bounds.left - 1
                                  && part.right <= bounds.right + 1
                                  && part.top >= bounds.top - 1
                                  && part.bottom <= bounds.bottom + 1;
                              });
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
                    self.assertTrue(geometry["noBioDuplicates"], geometry)
                    self.assertTrue(geometry["pinContentsFit"], geometry)
                    self.assertEqual(len(geometry["spheres"]),
                                     geometry["targetCount"], geometry)
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

                def collect_routine_pages(expected_total, max_height=None):
                    """Walk the independent, height-bounded routine planet strip."""
                    state = page.evaluate("window.VoidCompassSurveyAtlas.getState()")
                    self.assertEqual(state["routine"], expected_total, state)
                    self.assertGreaterEqual(state["routinePages"], 1, state)
                    self.assertEqual(state["routinePage"], 1, state)
                    collected = []
                    for number in range(1, state["routinePages"] + 1):
                        current = page.evaluate("window.VoidCompassSurveyAtlas.getState()")
                        self.assertEqual(current["routinePage"], number, current)
                        if number in (1, state["routinePages"]):
                            height = check_geometry()
                            if max_height is not None:
                                self.assertLessEqual(height, max_height, current)
                        chips = page.locator(".routine-pin")
                        self.assertGreater(chips.count(), 0)
                        collected.extend(page.locator(
                            ".routine-pin-name").all_text_contents())
                        page.evaluate("window.VoidCompassSurveyAtlas.nextRoutinePage()")
                    self.assertEqual(page.evaluate(
                        "window.VoidCompassSurveyAtlas.getState().routinePage"), 1)
                    self.assertEqual(len(collected), expected_total, collected)
                    return collected

                def collect_bio_pin_pages(expected_total, max_height=None):
                    """Walk scanned biology independently of the detailed atlas."""
                    state = page.evaluate("window.VoidCompassSurveyAtlas.getState()")
                    self.assertEqual(state["pinned"], expected_total, state)
                    self.assertGreaterEqual(state["pinPages"], 1, state)
                    self.assertEqual(state["pinPage"], 1, state)
                    collected = []
                    for number in range(1, state["pinPages"] + 1):
                        current = page.evaluate("window.VoidCompassSurveyAtlas.getState()")
                        self.assertEqual(current["pinPage"], number, current)
                        height = check_geometry()
                        if max_height is not None:
                            stack = page.evaluate("""() => ({
                              overview: document.querySelector('#overview').getBoundingClientRect().height,
                              content: document.querySelector('#content').getBoundingClientRect().height,
                              children: [...document.querySelector('#content').children]
                                .map(el => ({name: el.className, height: el.getBoundingClientRect().height})),
                            })""")
                            self.assertLessEqual(height, max_height, (current, stack))
                        pins = page.evaluate("""() => [...document.querySelectorAll('.bio-pin')]
                          .map(pin => ({
                            name: pin.querySelector('.bio-pin-name')?.textContent,
                            text: pin.textContent,
                            detail: pin.querySelector('.bio-pin-detail')?.textContent,
                            planetClass: pin.querySelector('.bio-pin-class')?.textContent,
                            badges: [...pin.querySelectorAll('.bio-pin-badges .badge')]
                              .map(badge => badge.textContent),
                            kind: pin.querySelector('.planet-orb')?.dataset.planetKind,
                            orbCount: pin.querySelectorAll('.planet-orb').length,
                            orbWidth: pin.querySelector('.planet-orb')?.getBoundingClientRect().width || 0,
                            ringed: Boolean(pin.querySelector('.planet-orb.has-rings')),
                          }))""")
                        self.assertGreater(len(pins), 0)
                        collected.extend(pins)
                        page.evaluate("window.VoidCompassSurveyAtlas.nextPinPage()")
                    self.assertEqual(page.evaluate(
                        "window.VoidCompassSurveyAtlas.getState().pinPage"), 1)
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
                        "geo_count": 3 if index == 6 else 0,
                        "mining_count": 2 if index == 6 else 0,
                        **({"landable": True, "first_footfall": True}
                           if index == 6 else {}),
                        "bio_details": [{"name": f"Genus {index}",
                                         "display_name": "Genus 2 Species" if index == 2 else None,
                                         "kind": "sample" if index == 2 else
                                         "complete" if index == 3 else "detected"}],
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
                # A body with a known PlanetClass and biology is represented
                # once, in the persistent bio pins. The unclassified
                # signal-only body remains in the detailed atlas.
                self.assertEqual(page.locator(".target-name").all_text_contents(), ["A 8"])
                self.assertEqual(page.locator(".bio-pinboard").count(), 1)
                cards = collect_bio_pin_pages(len(classes) - 1, max_height=700)
                for index, (_, expected_kind) in enumerate(classes, 1):
                    with self.subTest(index=index, kind=expected_kind):
                        if expected_kind == "unknown":
                            self.assertEqual(page.locator(".target .planet-orb").first.get_attribute(
                                "data-planet-kind"), expected_kind)
                            continue
                        matches = [card for card in cards
                                   if card["name"] == f"A {index}"]
                        self.assertEqual(len(matches), 1, matches)
                        self.assertEqual(matches[0]["kind"], expected_kind)
                        self.assertEqual(matches[0]["planetClass"],
                                         classes[index - 1][0].removesuffix(" body"))
                        self.assertEqual(matches[0]["orbCount"], 1)
                        self.assertLessEqual(matches[0]["orbWidth"], 32)
                        self.assertEqual(matches[0]["ringed"], index == 4)
                        expected_bio = "Genus 2 Species" if index == 2 else f"Genus {index}"
                        self.assertIn(expected_bio, matches[0]["detail"])
                        self.assertIn("BIO 0/1", matches[0]["badges"])
                        self.assertIn("DSS", matches[0]["badges"])
                rocky_pin = next(card for card in cards if card["name"] == "A 6")
                for badge in ("GEO 3", "MINING 2", "LAND", "1ST FOOTFALL"):
                    self.assertIn(badge, rocky_pin["badges"])
                for scale in (1.5, 2):
                    with self.subTest(mode="system", text_scale=scale):
                        system["effects"]["text_scale"] = scale
                        page.evaluate("snapshot => window.__surveyRender(snapshot)", system)
                        scaled = collect_bio_pin_pages(len(classes) - 1, max_height=700)
                        self.assertEqual({card["name"] for card in scaled},
                                         {f"A {index}" for index in range(1, len(classes))})
                        self.assertEqual(page.locator(".target-name").all_text_contents(), ["A 8"])

                completed_only = {
                    "survey": {
                        "mode": "system", "system": "Atlas", "scanned": 1,
                        "total": 1, "total_known": True,
                        "rows": [{
                            "name": "Atlas D 1", "planet_class": "Rocky body",
                            "bio_count": 2, "complete": 2, "bio_complete": True,
                            "priority": False, "geo_count": 1,
                            "bio_details": [
                                {"name": "Bacterium D", "kind": "complete"},
                                {"name": "Fungoid D", "kind": "complete"},
                            ],
                        }],
                    },
                    "effects": {"reduced_motion": True},
                }
                page.evaluate("snapshot => window.__surveyRender(snapshot)", completed_only)
                self.assertEqual(page.locator(".target").count(), 0)
                self.assertEqual(page.locator(".bio-pin.complete").count(), 1)
                self.assertEqual(page.evaluate(
                    "window.VoidCompassSurveyAtlas.getState().pinned"), 1)
                completed = page.locator(".bio-pin").first
                self.assertEqual(completed.locator(".bio-pin-name").text_content(), "D 1")
                self.assertEqual(completed.locator(".bio-pin-class").text_content(), "Rocky")
                self.assertIn("Bacterium D", completed.locator(".bio-pin-detail").text_content())
                self.assertIn("Fungoid D", completed.locator(".bio-pin-detail").text_content())
                self.assertIn("BIO 2/2", completed.locator(".bio-pin-badges").text_content())
                self.assertIn("GEO 1", completed.locator(".bio-pin-badges").text_content())
                self.assertLessEqual(check_geometry(), 700)

                moving_rows = [{
                    "name": f"Atlas E {index}", "planet_class": "Rocky body",
                    "bio_count": 1, "complete": 0,
                    "bio_details": [{"name": f"Bacterium {index}",
                                     "kind": "detected"}],
                } for index in range(1, 10)]
                moving = {
                    "survey": {
                        "mode": "system", "system": "Atlas", "scanned": 9,
                        "total": 9, "total_known": True, "rows": moving_rows,
                    },
                    "effects": {"reduced_motion": True},
                }
                page.evaluate("snapshot => window.__surveyRender(snapshot)", moving)
                self.assertGreater(page.evaluate(
                    "window.VoidCompassSurveyAtlas.getState().pinPages"), 1)
                page.evaluate("window.VoidCompassSurveyAtlas.nextPinPage()")
                self.assertEqual(page.evaluate(
                    "window.VoidCompassSurveyAtlas.getState().pinPage"), 2)
                # Completing a world may move it to the end of the backend's
                # active-then-complete sort. Follow that world across pages.
                finished = moving_rows.pop(5)
                finished.update({"complete": 1, "bio_complete": True,
                                 "bio_details": [{"name": "Bacterium 6",
                                                  "kind": "complete"}]})
                moving_rows.append(finished)
                page.evaluate("snapshot => window.__surveyRender(snapshot)", moving)
                state = page.evaluate("window.VoidCompassSurveyAtlas.getState()")
                self.assertEqual(state["pinPage"], state["pinPages"], state)
                self.assertIn("E 6", page.locator(".bio-pin-name").all_text_contents())
                self.assertEqual(page.locator(".bio-pin.complete").count(), 1)
                self.assertEqual(page.locator(".target").count(), 0)
                self.assertLessEqual(check_geometry(), 700)

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
                # Three signal-only rows lack a scanned PlanetClass and stay
                # in the atlas until a matching Scan confirms the planet.
                self.assertEqual(state["total"], 3, state)
                self.assertEqual(state["pinned"], 21)
                first_pin_count = page.locator(".bio-pin").count()
                self.assertGreater(first_pin_count, 0)
                self.assertLess(first_pin_count, 21)
                self.assertEqual(state["pinPages"],
                                 (21 + first_pin_count - 1) // first_pin_count)
                first_pins = page.locator(".bio-pin-name").all_text_contents()
                page.evaluate("window.VoidCompassSurveyAtlas.nextPage()")
                self.assertEqual(page.locator(".bio-pin-name").all_text_contents(), first_pins)
                page.evaluate("window.VoidCompassSurveyAtlas.nextPinPage()")
                second_pins = page.locator(".bio-pin-name").all_text_contents()
                self.assertNotEqual(second_pins, first_pins)
                page.evaluate("window.VoidCompassSurveyAtlas.nextPage()")
                self.assertEqual(page.locator(".bio-pin-name").all_text_contents(), second_pins)
                self.assertEqual(page.locator(".target").count(),
                                 len(page.locator(".target-name").all_text_contents()))
                check_geometry()
                # Start independent atlases from their first pages again.
                page.evaluate("snapshot => window.__surveyRender(snapshot)", system)
                page.evaluate("snapshot => window.__surveyRender(snapshot)", crowded)
                pin_cards = collect_bio_pin_pages(21, max_height=700)
                self.assertEqual([pin["name"] for pin in pin_cards],
                                 [f"B {index}" for index in range(1, 25)
                                  if index % len(classes) != 0])
                for pin in pin_cards:
                    index = int(pin["name"].split()[-1])
                    self.assertIn(f"Fungoid {index}", pin["detail"])
                    self.assertNotIn(f"Tussock {index}", pin["text"])
                mixed = {
                    "survey": {
                        **crowded["survey"],
                        "rows": crowded_rows + [{
                            "name": "Atlas B 25", "planet_class": "Rocky body",
                            "needs_dss": True, "priority": False,
                        }, {
                            "name": "Atlas B 26", "planet_class": "Icy body",
                            "needs_dss": False, "priority": False,
                        }],
                    },
                    "effects": crowded["effects"],
                }
                page.evaluate("snapshot => window.__surveyRender(snapshot)", mixed)
                self.assertEqual(page.locator(".routine-pin-name").all_text_contents(),
                                 ["B 25", "B 26"])
                pin_type = page.evaluate("""() => Object.fromEntries([
                  '.routine-strip-heading', '.routine-pin-name', '.routine-pin-class',
                  '.routine-pin-status', '.bio-pinboard-heading', '.bio-pin-name',
                  '.bio-pin-class', '.bio-pin-badges .badge',
                ].map(selector => [selector, parseFloat(getComputedStyle(
                  document.querySelector(selector)).fontSize)]))""")
                self.assertGreaterEqual(pin_type[".routine-strip-heading"], 10)
                self.assertGreaterEqual(pin_type[".routine-pin-name"], 11)
                self.assertGreaterEqual(pin_type[".routine-pin-class"], 10)
                self.assertGreaterEqual(pin_type[".routine-pin-status"], 10)
                self.assertGreaterEqual(pin_type[".bio-pinboard-heading"], 10)
                self.assertGreaterEqual(pin_type[".bio-pin-name"], 11)
                self.assertGreaterEqual(pin_type[".bio-pin-class"], 10)
                self.assertGreaterEqual(pin_type[".bio-pin-badges .badge"], 9)
                self.assertEqual(page.evaluate(
                    "window.VoidCompassSurveyAtlas.getState().total"), 3)
                self.assertTrue(page.evaluate("""() => {
                  const strip = document.querySelector('.routine-strip');
                  const target = document.querySelector('.target');
                  return strip && target
                    && strip.getBoundingClientRect().bottom <= target.getBoundingClientRect().top;
                }"""))
                routine_names = page.locator(".routine-pin-name").all_text_contents()
                page.evaluate("window.VoidCompassSurveyAtlas.nextPage()")
                self.assertEqual(page.locator(".routine-pin-name").all_text_contents(),
                                 routine_names)
                self.assertLessEqual(check_geometry(), 700)
                mixed["effects"] = {"reduced_motion": True, "text_scale": 2}
                mixed["survey"]["sampling"] = {
                    "species": "Fungoid 1", "progress": 2,
                    "min_distance_m": 240, "colony_m": 500,
                }
                page.evaluate("snapshot => window.__surveyRender(snapshot)", mixed)
                self.assertEqual(page.locator(".bio-pin").count(), 1)
                self.assertEqual(page.locator(".routine-pin").count(), 2)
                self.assertEqual(page.locator(".sample-card").count(), 1)
                mixed_height = check_geometry()
                mixed_stack = page.evaluate("""() => ({
                  cards: document.querySelectorAll('.target').length,
                  children: [...document.querySelector('#content').children]
                    .map(el => ({name: el.className, height: el.getBoundingClientRect().height})),
                  pieces: Object.fromEntries([
                    '.bio-pinboard-heading', '.bio-pinboard-grid', '.bio-pin',
                    '.bio-pin-eyebrow', '.bio-pin-name', '.bio-pin-environment',
                    '.bio-pin-badges', '.bio-pin-detail', '.bio-pin-detail .biological-row',
                    '.bio-pin .planet-orb', '.target-head', '.target-detail',
                    '.target .planet-orb', '.target .badges',
                  ].map(selector => [selector, [...document.querySelectorAll(selector)]
                    .map(el => ({width: el.getBoundingClientRect().width,
                                 height: el.getBoundingClientRect().height}))])),
                })""")
                self.assertLessEqual(mixed_height, 700, mixed_stack)
                routine_names = page.locator(".routine-pin-name").all_text_contents()
                bio_names = page.locator(".bio-pin-name").all_text_contents()
                page.evaluate("window.VoidCompassSurveyAtlas.nextPage()")
                self.assertEqual(page.locator(".routine-pin-name").all_text_contents(),
                                 routine_names)
                self.assertEqual(page.locator(".bio-pin-name").all_text_contents(),
                                 bio_names)
                self.assertLessEqual(check_geometry(), 700)
                # Restore the first atlas/pin pages for the page-walking check.
                page.evaluate("snapshot => window.__surveyRender(snapshot)", system)
                page.evaluate("snapshot => window.__surveyRender(snapshot)", crowded)
                crowded_names = ["B 8", "B 16", "B 24"]
                crowded_cards = collect_pages(
                    len(crowded_names), max_height=700,
                )
                self.assertEqual([card["designation"] for card in crowded_cards],
                                 crowded_names)
                for index, card in zip((8, 16, 24), crowded_cards):
                    self.assertEqual(card["orbCount"], 1)
                    self.assertEqual(card["details"],
                                     [f"Fungoid {index}", f"Tussock {index}"])
                crowded["effects"]["text_scale"] = 2
                crowded["survey"]["sampling"] = {
                    "species": "Fungoid 1", "progress": 2,
                    "min_distance_m": 240, "colony_m": 500,
                }
                page.evaluate("snapshot => window.__surveyRender(snapshot)", crowded)
                self.assertEqual(page.locator(".bio-pin").count(), 1)
                self.assertEqual(page.locator(".sample-card").count(), 1)
                crowded_height = check_geometry()
                crowded_stack = page.evaluate("""() => [...document.querySelector('#content').children]
                  .map(el => ({name: el.className, height: el.getBoundingClientRect().height}))""")
                self.assertLessEqual(crowded_height, 700, crowded_stack)
                crowded["effects"]["text_scale"] = 1
                crowded["survey"].pop("sampling")
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
                # Pin paging must survive a system with no main atlas cards.
                self.assertEqual(stress_state["total"], 0, stress_state)
                self.assertEqual(stress_state["pages"], 0, stress_state)
                self.assertGreater(stress_state["pinPages"], 10, stress_state)
                self.assertEqual(page.locator(".target").count(), 0)
                stress_first_pin_count = page.locator(".bio-pin").count()
                stress_names = [f"C {index}" for index in range(1, 102)]
                stress_pins = collect_bio_pin_pages(101, max_height=700)
                self.assertEqual([pin["name"] for pin in stress_pins],
                                 stress_names)
                self.assertTrue(all(pin["orbCount"] == 1 for pin in stress_pins))
                self.assertTrue(all("TYPES NOT IDENTIFIED" in pin["detail"]
                                    for pin in stress_pins))
                self.assertEqual(page.evaluate(
                    "window.VoidCompassSurveyAtlas.getState().pinned"), 101)
                self.assertEqual(page.locator(".bio-pin").count(), stress_first_pin_count)

                for row in stress_rows:
                    row["bio_count"] = 0
                    row["priority"] = False
                page.evaluate("snapshot => window.__surveyRender(snapshot)", stress)
                self.assertEqual(page.locator(".bio-pinboard").count(), 0)
                routine_state = page.evaluate("window.VoidCompassSurveyAtlas.getState()")
                self.assertEqual(routine_state["total"], 0, routine_state)
                self.assertEqual(routine_state["pages"], 0, routine_state)
                self.assertEqual(page.locator(".target").count(), 0)
                self.assertEqual(page.locator(".routine-pin").count(), 8)
                self.assertIn("Rocky", page.locator(".routine-pin").first.text_content())
                self.assertIn("DSS", page.locator(".routine-pin").first.text_content())
                self.assertEqual(collect_routine_pages(101, max_height=700), stress_names)
                stress["effects"]["text_scale"] = 2
                page.evaluate("snapshot => window.__surveyRender(snapshot)", stress)
                self.assertEqual(page.locator(".routine-pin").count(), 4)
                self.assertLessEqual(check_geometry(), 700)
                stress["effects"]["text_scale"] = 1

                for row in stress_rows:
                    row["expanded"] = True
                stress["survey"]["scope"] = "all"
                page.evaluate("snapshot => window.__surveyRender(snapshot)", stress)
                self.assertEqual(page.evaluate(
                    "window.VoidCompassSurveyAtlas.getState().routine"), 101)
                expanded_cards = collect_pages(
                    101, max_height=700, geometry_each_page=False,
                )
                self.assertEqual([card["designation"] for card in expanded_cards],
                                 stress_names)
                self.assertTrue(all(card["orbWidth"] >= 30 for card in expanded_cards))

                stress_rows[0].update({"bio_count": 1, "priority": True,
                                       "expanded": False})
                page.evaluate("snapshot => window.__surveyRender(snapshot)", stress)
                self.assertEqual(page.locator(".bio-pin-name").all_text_contents(),
                                 ["C 1"])
                self.assertNotIn("C 1", page.locator(".target-name").all_text_contents())
                stress_rows[0].update({"complete": 1, "bio_complete": True})
                page.evaluate("snapshot => window.__surveyRender(snapshot)", stress)
                self.assertEqual(page.locator(".bio-pin.complete").count(), 1)
                stress_rows[0]["planet_class"] = None
                page.evaluate("snapshot => window.__surveyRender(snapshot)", stress)
                self.assertEqual(page.locator(".bio-pinboard").count(), 0)
                # C 1 is complete and can sit on a later detailed-atlas page.
                signal_names = []
                signal_pages = page.evaluate("window.VoidCompassSurveyAtlas.getState().pages")
                for _ in range(signal_pages):
                    signal_names.extend(page.locator(".target-name").all_text_contents())
                    page.evaluate("window.VoidCompassSurveyAtlas.nextPage()")
                self.assertIn("C 1", signal_names)

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
                self.assertIn("260 M TO SAMPLE 03", focused["text"])
                self.assertIn("240 / 500 M SPACING", focused["text"])
                self.assertEqual(page.locator(".atlas-roster").count(), 0)
                check_geometry()
                for scale in (1.5, 2):
                    with self.subTest(text_scale=scale):
                        body["effects"]["text_scale"] = scale
                        page.evaluate("snapshot => window.__surveyRender(snapshot)", body)
                        check_geometry()
                        readout_fits = page.evaluate("""() =>
                          [...document.querySelectorAll('.sample-action, .sample-distance')]
                            .every(item => item.scrollWidth <= item.clientWidth + 1)
                        """)
                        self.assertTrue(readout_fits, scale)

                body["effects"]["text_scale"] = 1
                sampling = body["survey"]["sampling"]
                sampling["min_distance_m"] = 410
                page.evaluate("snapshot => window.__surveyRender(snapshot)", body)
                self.assertIn("90 M TO SAMPLE 03", page.locator(".sample-action").text_content())
                self.assertIn("410 / 500 M SPACING", page.locator(".sample-distance").text_content())
                sampling.update({"min_distance_m": 530, "clear": True})
                page.evaluate("snapshot => window.__surveyRender(snapshot)", body)
                self.assertEqual(page.locator(".sample-action").text_content(), "READY FOR SAMPLE 03")
                self.assertEqual(page.locator(".sample-distance").text_content(), "530 / 500 M SPACING")
                self.assertEqual(page.locator(".sample-card.ready").count(), 1)
                check_geometry()

                sampling["progress"] = 3
                page.evaluate("snapshot => window.__surveyRender(snapshot)", body)
                self.assertEqual(page.locator(".sample-node.done").count(), 3)
                self.assertEqual(page.locator(".sample-action").text_content(), "SAMPLES SECURED")
                self.assertEqual(page.locator(".sample-distance").text_content(), "AWAITING ANALYSIS")
                self.assertEqual(page.locator(".sample-range-meter").count(), 0)
                check_geometry()

                sampling.update({"progress": 1, "clear": False, "min_distance_m": 0})
                page.evaluate("snapshot => window.__surveyRender(snapshot)", body)
                self.assertEqual(page.locator(".sample-node.done").count(), 1)
                self.assertEqual(page.locator(".sample-action").text_content(), "500 M TO SAMPLE 02")
                sampling["min_distance_m"] = None
                page.evaluate("snapshot => window.__surveyRender(snapshot)", body)
                self.assertEqual(page.locator(".sample-action").text_content(), "DISTANCE UNAVAILABLE")
                self.assertEqual(page.locator(".sample-distance").text_content(), "500 M REQUIRED")
                sampling["colony_m"] = None
                page.evaluate("snapshot => window.__surveyRender(snapshot)", body)
                self.assertEqual(page.locator(".sample-distance").text_content(), "COLONY SPACING UNKNOWN")
                check_geometry()

                body["survey"]["sampling"] = None
                page.evaluate("snapshot => window.__surveyRender(snapshot)", body)
                self.assertEqual(page.locator(".sample-card").count(), 0)
                body["survey"]["body"]["organic_complete_count"] = 2
                body["survey"]["rows"] = [
                    {"name": "Bacterium Sample", "kind": "complete", "progress": 3},
                    {"name": "Fonticulua Detected", "kind": "complete", "progress": 3},
                ]
                page.evaluate("snapshot => window.__surveyRender(snapshot)", body)
                self.assertEqual(page.locator(".focus-target.complete .biological-row.complete").count(), 2)
                self.assertIn("Fonticulua Detected", page.locator(".focus-target").text_content())
                self.assertLessEqual(check_geometry(), 700)

                routine = {
                    "survey": {
                        "mode": "system", "system": "Atlas", "scanned": 2,
                        "total": 2, "total_known": True, "scope": "priority",
                        "rows": [{
                            "name": "Atlas R 1", "planet_class": "Rocky body",
                            "priority": False, "recent_scan": True,
                            "scan_timestamp": "2026-09-23T08:00:00Z",
                        }],
                    },
                    "effects": {"reduced_motion": False},
                }
                page.evaluate("snapshot => window.__surveyRender(snapshot)", routine)
                routine["survey"]["rows"] = [{
                    "name": "Atlas R 2", "planet_class": "Icy body",
                    "priority": False, "recent_scan": True,
                    "scan_timestamp": "2026-09-23T08:01:00Z",
                }]
                page.evaluate("snapshot => window.__surveyRender(snapshot)", routine)
                self.assertEqual(page.locator(".routine-pin-name").text_content(), "R 2")
                self.assertEqual(page.locator(".routine-pin.recent").count(), 1)
                self.assertEqual(page.locator(".target").count(), 0)
                page.wait_for_timeout(650)
                check_geometry()

                routine["survey"].update({
                    "mode": "body", "body": routine["survey"]["rows"][0],
                    "body_display": "Atlas R 2", "rows": [],
                })
                page.evaluate("snapshot => window.__surveyRender(snapshot)", routine)
                self.assertEqual(page.locator(".focus-target").count(), 1)
                check_geometry()
                self.assertEqual(failures, [])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
