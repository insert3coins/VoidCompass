"""Browser checks for the journal-backed Survey Operations overlay.

These drive the real Survey markup, styling and renderer headlessly at the
host's fixed 420 px width. Playwright is optional for the regular unittest
suite.

Layout under test: one detailed *spotlight* card, a one-line-per-world
*biology manifest*, and a tiered *catalogue* (surface, notable, landable,
other) — all advanced by a single shared clock and fitted to a height budget.
"""

from pathlib import Path
import unittest
from urllib.parse import urlsplit


WEB = Path(__file__).resolve().parents[1] / "web"

# Capture the production renderer without starting the asynchronous
# overlay-server health loop.
CLIENT_STUB = """
  window.VoidCompassOverlay = {
    applyTheme(root, palette, effects) {
      document.documentElement.style.setProperty('--scale', String(effects.text_scale || 1));
      root.classList.toggle('reduced-motion', Boolean(effects.reduced_motion));
      root.classList.toggle('no-crt', !effects.crt);
    },
    startPolling(options) {
      window.__surveyRender = options.render;
      window.__surveyContentHeight = options.contentHeight;
    }
  };
"""

GEOMETRY_JS = """() => {
  const box = element => element.getBoundingClientRect();
  const inside = (inner, outer, slack = 1) => inner.left >= outer.left - slack
    && inner.right <= outer.right + slack && inner.top >= outer.top - slack
    && inner.bottom <= outer.bottom + slack;
  const root = box(document.querySelector('#survey'));
  const overview = box(document.querySelector('#overview'));
  const content = box(document.querySelector('#content'));
  const footer = box(document.querySelector('#footer'));
  const children = [...document.querySelector('#content').children];
  // Children hidden at a text scale (display: none) have no box to check.
  const escaped = selector => [...document.querySelectorAll(selector)].filter(element => {
    const bounds = box(element);
    return ![...element.children].filter(child => child.getClientRects().length)
      .every(child => inside(box(child), bounds, 1.5));
  }).map(element => element.className);
  return {
    bands: overview.top >= root.top - .5 && overview.bottom <= content.top + .5
      && content.bottom <= footer.top + .5 && footer.bottom <= root.bottom + .5,
    headerFits: [...document.querySelectorAll('#overview > *')]
      .every(child => inside(box(child), overview)),
    contentFits: children.every(child => inside(box(child), content)),
    overflowing: children.filter(child => !inside(box(child), content))
      .map(child => ({name: child.className, bottom: box(child).bottom, limit: content.bottom})),
    rowsEscaping: escaped('.body-row, .body-chip'),
    spotlightFits: [...document.querySelectorAll('.spotlight')].every(card => {
      const bounds = box(card);
      return [...card.querySelectorAll('.spot-title, .target-environment, .badges, .target-detail')]
        .every(part => inside(box(part), bounds));
    }),
    noHorizontalScroll: document.documentElement.scrollWidth <= 421,
    spheres: [...document.querySelectorAll('.planet-sphere')].every(sphere => {
      const bounds = box(sphere);
      return bounds.width > 8 && bounds.height > 8
        && getComputedStyle(sphere).backgroundImage !== 'none';
    }),
    titleStripAbsent: !document.querySelector('header')
      && !document.body.textContent.includes('VOID COMPASS / FIELD ATLAS')
      && !document.body.textContent.includes('SURVEY OPERATIONS'),
  };
}"""

SPOTLIGHT_JS = """() => {
  const card = document.querySelector('.spotlight');
  if (!card) return null;
  const orb = card.querySelector('.planet-orb');
  return {
    name: card.querySelector('.spot-name').textContent,
    kicker: card.querySelector('.spot-kicker')?.textContent || '',
    kind: orb.dataset.planetKind,
    orbCount: card.querySelectorAll('.planet-orb').length,
    orbWidth: orb.getBoundingClientRect().width,
    ringed: orb.classList.contains('has-rings'),
    planetClass: card.querySelector('.target-class').textContent,
    badges: [...card.querySelectorAll('.badges .badge')].map(badge => badge.textContent),
    species: [...card.querySelectorAll('.biological-name')].map(name => name.textContent),
    text: card.textContent,
    complete: card.classList.contains('complete'),
    spotlit: [...document.querySelectorAll('.manifest .body-row.spotlit .row-name strong')]
      .map(name => name.textContent),
  };
}"""

CLASSES = [
    ("Earth-like world", "earthlike"),
    ("Water world", "water"),
    ("Ammonia world", "ammonia"),
    ("Gas giant with water-based life", "gas-water"),
    ("Icy body", "icy"),
    ("Rocky body", "rocky"),
    ("High metal content body", "metal"),
    (None, "unknown"),
]


def system_snapshot(rows, name="Atlas", scale=1, scanned=None, total=None, rotation=None, **survey):
    scanned = len(rows) if scanned is None else scanned
    total = len(rows) if total is None else total
    snapshot = {
        "survey": {"mode": "system", "system": name, "rows": rows,
                   "total_known": True, "scanned": scanned, "total": total, **survey},
        "effects": {"reduced_motion": True, "text_scale": scale},
    }
    # The Studio's Spotlight rotation (default: auto above 8 worlds).
    if rotation is not None:
        snapshot["options"] = rotation
    return snapshot


ALWAYS = {"spotlight_rotation": "always"}


def bio_world(name, planet_class="Rocky body", details=(), bio_count=None, **extra):
    details = list(details)
    return {
        "name": name, "display_name": name, "planet_class": planet_class,
        "bio_count": len(details) if bio_count is None else bio_count,
        "complete": 0, "bio_details": details, "needs_dss": True, "priority": True,
        **extra,
    }


def quiet_body(name, planet_class="Icy body", **extra):
    return {"name": name, "planet_class": planet_class, "needs_dss": True,
            "priority": False, "landable": False, "landable_known": True, **extra}


class SurveyOverlayBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        cls._playwright = sync_playwright().start()
        try:
            cls.browser = cls._playwright.chromium.launch(headless=True)
        except Exception as exc:
            cls._playwright.stop()
            raise unittest.SkipTest(f"Playwright Chromium is unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls._playwright.stop()

    def setUp(self):
        # Render at the host's real 420 px width: chip line-wrapping and the
        # height budget are measured from live layout.
        self.page = self.browser.new_page(viewport={"width": 420, "height": 900})
        self.failures = []
        self.page.on("pageerror", lambda error: self.failures.append(str(error)))

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/assets/overlay-client.js":
                route.fulfill(content_type="application/javascript", body=CLIENT_STUB)
                return
            file = WEB / path.lstrip("/")
            if file.is_file():
                route.fulfill(path=str(file))
            else:
                route.fulfill(status=404, body="")

        self.page.route("http://survey.test/**", serve)
        self.page.goto("http://survey.test/survey/index.html")

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.failures, [])

    # -- helpers ---------------------------------------------------------

    def render(self, snapshot):
        self.page.set_viewport_size({"width": 420, "height": 900})
        self.page.evaluate("snapshot => window.__surveyRender(snapshot)", snapshot)

    def state(self):
        return self.page.evaluate("window.VoidCompassSurveyAtlas.getState()")

    def tick(self):
        self.page.evaluate("window.VoidCompassSurveyAtlas.tick()")

    def spotlight(self):
        return self.page.evaluate(SPOTLIGHT_JS)

    def manifest_names(self):
        return self.page.locator(".manifest .body-row .row-name strong").all_text_contents()

    def group_names(self, key):
        selector = (f'.catalogue-group[data-group="{key}"] .chip-name, '
                    f'.catalogue-group[data-group="{key}"] .row-name strong')
        return self.page.locator(selector).all_text_contents()

    def check_geometry(self):
        """Size the host to the measured content and verify every band fits."""
        self.page.set_viewport_size({"width": 420, "height": 900})
        height = self.page.evaluate("window.__surveyContentHeight()")
        self.page.set_viewport_size({"width": 420, "height": height})
        geometry = self.page.evaluate(GEOMETRY_JS)
        for key in ("bands", "headerFits", "contentFits", "spotlightFits",
                    "noHorizontalScroll", "spheres", "titleStripAbsent"):
            self.assertTrue(geometry[key], (key, geometry))
        self.assertEqual(geometry["rowsEscaping"], [], geometry)
        return height

    def walk_spotlight(self, expected, max_height=700, geometry_every=1):
        """Turn the shared clock through every biology world once.

        Returns the spotlight cards in manifest order, checking that the
        manifest window always shows and highlights the spotlit world.
        """
        state = self.state()
        self.assertEqual(state["bio"], expected, state)
        start = state["spotIndex"]
        cards = []
        for step in range(expected):
            current = self.state()
            if step % geometry_every == 0 or step == expected - 1:
                self.assertLessEqual(self.check_geometry(), max_height, current)
            card = self.spotlight()
            self.assertEqual(card["name"], current["spotlight"], current)
            if current["manifestPages"]:
                self.assertEqual(card["spotlit"], [card["name"]], current)
            cards.append(card)
            self.tick()
        self.assertEqual(self.state()["spotIndex"], start)
        offset = (start - 1) % expected
        return cards[-offset:] + cards[:-offset] if offset else cards

    def walk_group(self, key):
        """Collect every body a catalogue group shows across its pages."""
        pages = self.state()["groups"][key]["pages"]
        names = []
        for _ in range(pages):
            names.extend(self.group_names(key))
            self.tick()
        return names

    # -- system survey ---------------------------------------------------

    def test_every_planet_class_reaches_the_spotlight(self):
        rows = []
        for index, (planet_class, _) in enumerate(CLASSES, 1):
            kind = "sample" if index == 2 else "complete" if index == 3 else "detected"
            rows.append(bio_world(
                f"Atlas A {index}", planet_class,
                [{"name": f"Genus {index}",
                  "display_name": "Genus 2 Species" if index == 2 else None, "kind": kind}],
                ring_count=2 if index == 4 else 0,
                geo_count=3 if index == 6 else 0, mining_count=2 if index == 6 else 0,
                **({"landable": True, "first_footfall": True} if index == 6 else {}),
            ))
        system = system_snapshot(rows, scanned=4, total=8, rotation=ALWAYS)
        self.render(system)
        header = self.page.evaluate("""() => ({
          text: document.querySelector('#overview').textContent,
          mode: document.querySelector('#mode-label')?.textContent,
          system: document.querySelector('#system-name')?.textContent,
          height: window.__surveyContentHeight(),
          reduced: document.querySelector('#survey').classList.contains('reduced-motion'),
          animated: [...document.querySelectorAll('.planet-orb, .planet-orb *')]
            .some(element => ['', '::before', '::after'].some(pseudo =>
              getComputedStyle(element, pseudo || null).animationName !== 'none')),
        })""")
        self.assertIn("FSS 4/8", header["text"])
        self.assertTrue(header["mode"].startswith("SYSTEM"), header)
        self.assertEqual(header["system"], "Atlas")
        self.assertGreater(header["height"], 90)
        self.assertTrue(header["reduced"])
        self.assertFalse(header["animated"])

        # Every biology world — scanned or signal-only — is one manifest row,
        # in designation order, drawn with its class illustration.
        self.assertEqual(self.manifest_names(), [f"A {index}" for index in range(1, 9)])
        rows_drawn = self.page.evaluate("""() => [...document.querySelectorAll('.manifest .body-row')]
          .map(row => ({kind: row.querySelector('.planet-orb').dataset.planetKind,
                        width: row.querySelector('.planet-orb').getBoundingClientRect().width,
                        unclassified: row.classList.contains('unclassified')}))""")
        self.assertEqual([row["kind"] for row in rows_drawn], [kind for _, kind in CLASSES])
        self.assertTrue(all(row["width"] <= 24 for row in rows_drawn), rows_drawn)
        self.assertEqual([row["unclassified"] for row in rows_drawn],
                         [kind == "unknown" for _, kind in CLASSES])

        cards = {card["name"]: card for card in self.walk_spotlight(8)}
        for index, (planet_class, kind) in enumerate(CLASSES, 1):
            with self.subTest(index=index, kind=kind):
                card = cards[f"A {index}"]
                self.assertEqual(card["kind"], kind)
                self.assertEqual(card["orbCount"], 1)
                self.assertEqual(card["ringed"], index == 4)
                self.assertEqual(card["planetClass"], planet_class.removesuffix(" body")
                                 if planet_class else "CLASS UNCONFIRMED")
                self.assertIn("Genus 2 Species" if index == 2 else f"Genus {index}",
                              card["species"])
                self.assertIn("BIO 0/1", card["badges"])
                self.assertIn("DSS", card["badges"])
        for badge in ("GEO 3", "MINING 2", "LAND", "1ST FOOTFALL"):
            self.assertIn(badge, cards["A 6"]["badges"])

        for scale in (1.5, 2):
            with self.subTest(text_scale=scale):
                system["effects"]["text_scale"] = scale
                self.render(system)
                scaled = self.walk_spotlight(8)
                self.assertEqual([card["name"] for card in scaled],
                                 [f"A {index}" for index in range(1, 9)])

    def test_single_world_is_described_by_the_spotlight_alone(self):
        self.render(system_snapshot([bio_world(
            "Atlas D 1", "Rocky body",
            [{"name": "Bacterium D", "kind": "complete"}, {"name": "Fungoid D", "kind": "complete"}],
            complete=2, bio_complete=True, priority=False, geo_count=1,
        )]))
        self.assertEqual(self.page.locator(".manifest").count(), 0)
        self.assertEqual(self.page.locator(".spotlight.complete").count(), 1)
        card = self.spotlight()
        self.assertEqual(card["name"], "D 1")
        self.assertEqual(card["planetClass"], "Rocky")
        self.assertEqual(card["species"], ["Bacterium D", "Fungoid D"])
        self.assertIn("BIO 2/2", card["badges"])
        self.assertIn("GEO 1", card["badges"])
        state = self.state()
        self.assertEqual(state["bio"], 1)
        # Nothing to rotate: no clock, no countdown hairline.
        self.assertFalse(state["rotating"])
        self.assertEqual(self.page.locator(".spot-meter").count(), 0)
        self.assertLessEqual(self.check_geometry(), 700)

    def test_spotlight_follows_journal_updates_and_holds(self):
        rows = [bio_world(f"Atlas E {index}", "Rocky body",
                          [{"name": f"Bacterium {index}", "kind": "detected"}])
                for index in range(1, 13)]
        moving = system_snapshot(rows)
        self.render(moving)
        state = self.state()
        self.assertEqual(state["spotlight"], "E 1")
        self.assertFalse(state["held"])
        self.assertGreater(state["manifestPages"], 1)
        self.tick()
        self.assertEqual(self.state()["spotlight"], "E 2")

        # Completing a world settles it to the bottom of the manifest. The
        # spotlight jumps to it, the manifest window follows, and the event
        # holds the spotlight there for reading.
        finished = rows.pop(5)
        finished.update({"complete": 1, "bio_complete": True,
                         "bio_details": [{"name": "Bacterium 6", "kind": "complete"}]})
        rows.append(finished)
        self.render(moving)
        state = self.state()
        self.assertEqual(state["spotlight"], "E 6")
        self.assertTrue(state["held"])
        self.assertEqual(state["manifestPage"], state["manifestPages"])
        self.assertEqual(self.manifest_names()[-1], "E 6")
        spotlit = self.page.locator(".manifest .body-row.spotlit")
        self.assertEqual(spotlit.count(), 1)
        self.assertIn("complete", spotlit.get_attribute("class"))
        self.assertEqual(self.spotlight()["kicker"], "UPDATED")
        self.assertLessEqual(self.check_geometry(), 700)

        # A repaint that carries no journal change moves nothing.
        self.render(moving)
        self.assertEqual(self.state()["spotlight"], "E 6")
        # The clock resumes from the held world: E 6 is last, so it wraps.
        self.tick()
        state = self.state()
        self.assertEqual((state["spotlight"], state["manifestPage"]), ("E 1", 1))

    def test_latest_scan_takes_the_spotlight(self):
        rows = [bio_world(f"Atlas L {index}", "Icy body", [{"name": f"Stratum {index}", "kind": "detected"}])
                for index in range(1, 5)]
        rows[2]["recent_scan"] = True
        snapshot = system_snapshot(rows)
        self.render(snapshot)
        state = self.state()
        self.assertEqual(state["spotlight"], "L 3")
        self.assertTrue(state["held"])
        self.assertEqual(self.spotlight()["kicker"], "LATEST SCAN")
        # The manifest keeps designation order and tags the newest row.
        self.assertEqual(self.manifest_names(), ["L 1", "L 2", "L 3", "L 4"])
        self.assertEqual(self.page.locator(".manifest .body-row.recent .row-tag.new").count(), 1)
        rows[2]["recent_scan"] = False
        rows[0].update({"recent_scan": True, "scan_timestamp": "2026-09-26T10:00:00Z"})
        self.render(snapshot)
        self.assertEqual(self.state()["spotlight"], "L 1")

    def test_crowded_system_turns_on_one_clock(self):
        rows = []
        for index in range(1, 25):
            rows.append(bio_world(
                f"Atlas B {index}", CLASSES[(index - 1) % len(CLASSES)][0],
                [{"name": f"Fungoid {index}", "kind": "detected"},
                 {"name": f"Tussock {index}", "kind": "predicted"}], bio_count=2,
            ))
        rows += [quiet_body(f"Atlas B {index}", "Icy body" if index % 2 else "Rocky ice body",
                            needs_dss=bool(index % 3)) for index in range(25, 55)]
        crowded = system_snapshot(rows, scanned=18, total=60)
        self.render(crowded)
        state = self.state()
        self.assertEqual(state["bio"], 24)
        self.assertGreater(state["manifestPages"], 1)
        other = state["groups"]["other"]
        self.assertGreater(other["pages"], 1)

        # One beat turns the spotlight (and its manifest window) and every
        # overflowing catalogue group together.
        before = state["spotlight"]
        self.tick()
        after = self.state()
        self.assertNotEqual(after["spotlight"], before)
        self.assertEqual(after["groups"]["other"]["page"], other["page"] % other["pages"] + 1)
        # A data repaint with nothing new turns nothing.
        self.render(crowded)
        repainted = self.state()
        self.assertEqual(repainted["spotlight"], after["spotlight"])
        self.assertEqual(repainted["groups"]["other"]["page"], after["groups"]["other"]["page"])
        self.assertEqual(self.page.locator(".group-other .group-count").text_content().split()[0], "30")

        # Journal-confirmed biology only: predictions never reach the system view.
        cards = self.walk_spotlight(24, geometry_every=6)
        self.assertEqual([card["name"] for card in cards], [f"B {index}" for index in range(1, 25)])
        for card in cards:
            index = int(card["name"].split()[-1])
            self.assertEqual(card["species"], [f"Fungoid {index}"])
            self.assertNotIn(f"Tussock {index}", card["text"])
        self.assertEqual(sorted(self.walk_group("other"), key=lambda name: int(name.split()[-1])),
                         [f"B {index}" for index in range(25, 55)])

    def test_catalogue_sorts_bodies_into_tiers(self):
        rows = [
            bio_world("Atlas T 1", "Rocky body", [{"name": "Bacterium Cerbrus", "kind": "detected"}]),
            bio_world("Atlas T 2", "Icy body", [{"name": "Fonticulua Campestris", "kind": "detected"}]),
            {"name": "Atlas T 3", "planet_class": "High metal content body", "geo_count": 3,
             "landable": True, "landable_known": True, "needs_dss": True, "priority": True},
            {"name": "Atlas T 4", "planet_class": "Water world", "terraformable": True,
             "notable": {"value_line": "1.2M CR  ·  DSS 3.4M CR"}, "landable": False,
             "landable_known": True, "needs_dss": True, "priority": True},
            {"name": "Atlas T 5", "planet_class": "Icy body", "landable": True,
             "landable_known": True, "needs_dss": True, "priority": True},
            quiet_body("Atlas T 6", "Sudarsky class I gas giant", needs_dss=False),
            quiet_body("Atlas T 7", "Icy body", recent_scan=True),
        ]
        self.render(system_snapshot(rows))
        groups = self.page.evaluate("""() => [...document.querySelectorAll('.catalogue-group')]
          .map(group => ({key: group.dataset.group,
                          label: group.querySelector('.group-label strong').textContent,
                          layout: group.classList.contains('layout-chips') ? 'chips' : 'rows',
                          names: [...group.querySelectorAll('.row-name strong, .chip-name')]
                            .map(name => name.textContent)}))""")
        self.assertEqual(groups, [
            {"key": "surface", "label": "SURFACE", "layout": "rows", "names": ["T 3"]},
            {"key": "notable", "label": "NOTABLE", "layout": "rows", "names": ["T 4"]},
            {"key": "landable", "label": "LANDABLE", "layout": "chips", "names": ["T 5"]},
            {"key": "other", "label": "OTHER", "layout": "chips", "names": ["T 6", "T 7"]},
        ])
        self.assertEqual(self.manifest_names(), ["T 1", "T 2"])
        self.assertIn("GEO 3", self.page.locator(".row-surface .row-meta").text_content())
        notable = self.page.locator(".row-notable").text_content()
        # The value line already quotes the unclaimed DSS reward once.
        self.assertIn("1.2M CR · DSS 3.4M CR", notable)
        self.assertEqual(notable.count("DSS"), 1)
        self.assertEqual(self.page.locator(".body-chip.recent .chip-flag.new").count(), 1)
        self.assertEqual(self.page.locator('.body-chip.mapped[aria-label*="T 6"]').count(), 1)
        self.assertEqual(self.page.locator(".chip-class").first.text_content(), "Icy")
        # Groups that fit do not spend a line on a count.
        self.assertEqual(self.page.locator(".group-count:not([hidden])").count(), 0)

        order = self.page.evaluate("""() => ['.spotlight', '.manifest', '.catalogue']
          .map(selector => document.querySelector(selector).getBoundingClientRect().top)""")
        self.assertEqual(order, sorted(order))
        # Legibility floor for the dense rows (raised deliberately in 7bc05da).
        sizes = self.page.evaluate("""() => Object.fromEntries([
          '.section-head', '.row-name strong', '.row-class', '.group-label strong',
          '.chip-name', '.chip-class', '.spotlight .badge', '.biological-name',
        ].map(selector => [selector, parseFloat(getComputedStyle(
          document.querySelector(selector)).fontSize)]))""")
        for selector, floor in ((".section-head", 10), (".row-name strong", 11),
                                (".row-class", 10), (".group-label strong", 10),
                                (".chip-name", 11), (".chip-class", 10),
                                (".spotlight .badge", 9), (".biological-name", 11)):
            self.assertGreaterEqual(sizes[selector], floor, (selector, sizes))
        self.assertLessEqual(self.check_geometry(), 700)

    def test_height_budget_keeps_sampling_on_screen(self):
        rows = [bio_world(f"Atlas S {index}", "Rocky body",
                          [{"name": f"Fungoid {index}", "kind": "sample" if index == 1 else "detected",
                            "progress": 2 if index == 1 else 0},
                           {"name": f"Stratum {index}", "kind": "detected"}])
                for index in range(1, 11)]
        rows += [{"name": f"Atlas S {index}", "planet_class": "High metal content body",
                  "geo_count": 2, "needs_dss": True, "priority": True} for index in (11, 12)]
        rows.append({"name": "Atlas S 13", "planet_class": "Earthlike body", "priority": True,
                     "needs_dss": True, "notable": {"value_line": "2.1M CR"}})
        rows += [{"name": f"Atlas S {index}", "planet_class": "Icy body", "landable": True,
                  "landable_known": True, "needs_dss": True, "priority": True}
                 for index in (14, 15, 16)]
        rows += [quiet_body(f"Atlas S {index}") for index in range(17, 23)]
        catalogue = {f"S {index}" for index in range(11, 23)}
        sampling = system_snapshot(rows, scale=2, sampling={
            "species": "Fungoid 1", "progress": 2, "min_distance_m": 240, "colony_m": 500,
        })
        self.render(sampling)
        self.assertLessEqual(self.check_geometry(), 700)
        self.assertEqual(self.page.locator(".sample-card").count(), 1)
        state = self.state()
        self.assertTrue(state["locked"])
        self.assertEqual(state["spotlight"], "S 1")
        card = self.spotlight()
        self.assertEqual(card["kicker"], "SAMPLING")
        # The genetic-sequence card owns the species in hand.
        self.assertEqual(card["species"], ["Stratum 1"])
        self.assertGreaterEqual(self.page.locator(".manifest .body-row").count(), 2)
        # Sampling locks the spotlight; the catalogue keeps turning, and every
        # body still comes round even when the budget folds the tiers.
        seen = set()
        for key in self.state()["groups"]:
            seen.update(self.walk_group(key))
        self.assertEqual(seen, catalogue)
        self.assertEqual(self.state()["spotlight"], "S 1")
        if "bodies" in self.state()["groups"]:
            flags = self.page.evaluate("""() => [...document.querySelectorAll('.chip-flag')]
              .map(flag => flag.textContent)""")
            self.assertTrue(all(flag for flag in flags), flags)

        # Six worlds at 2x without sampling keep several rows on screen.
        compact = system_snapshot([bio_world(
            f"Atlas F {index}", "Rocky body", [{"name": f"Fungoid {index}", "kind": "detected"}],
        ) for index in range(1, 7)], name="Atlas Compact", scale=2)
        self.render(compact)
        self.assertGreaterEqual(self.page.locator(".manifest .body-row").count(), 3)
        self.assertLessEqual(self.check_geometry(), 700)

    def test_stress_systems_stay_bounded_and_reachable(self):
        rows = [bio_world(f"Atlas C {index}", "Rocky body", bio_count=1)
                for index in range(1, 102)]
        names = [f"C {index}" for index in range(1, 102)]
        stress = system_snapshot(rows, scanned=21, total=101)
        self.render(stress)
        state = self.state()
        self.assertGreater(state["manifestPages"], 10, state)
        cards = self.walk_spotlight(101, geometry_every=25)
        self.assertEqual([card["name"] for card in cards], names)
        self.assertTrue(all(card["orbCount"] == 1 for card in cards))
        self.assertTrue(all("TYPES NOT IDENTIFIED" in card["text"] for card in cards))

        for row in rows:
            row.update({"bio_count": 0, "priority": False})
        self.render(stress)
        self.assertEqual(self.page.locator(".spotlight, .manifest").count(), 0)
        self.assertLessEqual(self.check_geometry(), 700)
        # Auto holds a system without biology still: the catalogue shows what
        # fits the height cap and counts the rest rather than paging.
        shown = self.group_names("other")
        self.assertEqual(self.state()["groups"]["other"]["pages"], 1)
        self.assertEqual(shown, names[:len(shown)])
        self.assertEqual(self.page.locator('.catalogue-group[data-group="other"] .group-count').text_content(),
                         f"+{101 - len(shown)} MORE")
        self.assertFalse(self.state()["rotating"])
        # Always keeps every body coming round on the clock.
        stress["options"] = ALWAYS
        self.render(stress)
        chip_size = lambda: self.page.evaluate("""() => parseFloat(getComputedStyle(
          document.querySelector('.chip-name')).fontSize)""")
        normal_size = chip_size()
        self.assertIn("Rocky", self.page.locator(".body-chip").first.text_content())
        self.assertEqual(self.walk_group("other"), names)
        # Larger text pages the same bodies at full size rather than shrinking
        # them to fit; the class illustration stands in for the class label.
        stress["effects"]["text_scale"] = 2
        self.render(stress)
        self.assertAlmostEqual(chip_size(), normal_size * 2, delta=0.5)
        self.assertEqual(self.page.locator(".chip-class:visible").count(), 0)
        self.assertLessEqual(self.check_geometry(), 700)
        self.assertEqual(self.walk_group("other"), names)
        stress["effects"]["text_scale"] = 1

        # The expanded scope lists quiet bodies as full rows, still paged.
        for row in rows:
            row["expanded"] = True
        stress["survey"]["scope"] = "all"
        self.render(stress)
        self.assertEqual(self.page.locator(".body-chip").count(), 0)
        self.assertLessEqual(self.check_geometry(), 700)
        widths = self.page.evaluate("""() => [...document.querySelectorAll('.row-other .planet-orb')]
          .map(orb => orb.getBoundingClientRect().width)""")
        self.assertTrue(widths and all(width >= 18 for width in widths), widths)
        self.assertEqual(self.walk_group("other"), names)
        self.assertIn("ALL BODIES", self.page.locator("#footer").text_content())

        rows[0].update({"bio_count": 1, "priority": True, "expanded": False})
        self.render(stress)
        self.assertEqual(self.spotlight()["name"], "C 1")
        self.assertNotIn("C 1", self.group_names("other"))
        rows[0].update({"complete": 1, "bio_complete": True})
        self.render(stress)
        self.assertTrue(self.spotlight()["complete"])
        # A world whose Scan has not arrived keeps its biology visible.
        rows[0]["planet_class"] = None
        self.render(stress)
        card = self.spotlight()
        self.assertEqual((card["name"], card["kind"]), ("C 1", "unknown"))
        self.assertLessEqual(self.check_geometry(), 700)

    def test_planets_rotate_unless_motion_is_reduced(self):
        rows = [bio_world(f"Atlas M {index}", CLASSES[index % 3][0],
                          [{"name": f"Fungoid {index}", "kind": "detected"}]) for index in range(1, 4)]
        snapshot = system_snapshot(rows, rotation=ALWAYS)
        snapshot["effects"]["reduced_motion"] = False
        self.page.emulate_media(reduced_motion="no-preference")
        self.render(snapshot)
        animation = self.page.evaluate("""() => {
          const sphere = document.querySelector('.planet-earthlike .planet-sphere');
          return {
            surface: getComputedStyle(sphere, '::before').animationName,
            fixedLight: getComputedStyle(sphere, '::after').animationName,
            transform: getComputedStyle(sphere, '::before').transform,
            meter: getComputedStyle(document.querySelector('.spot-meter')).animationName,
          };
        }""")
        self.assertEqual(animation["surface"], "planet-turn")
        self.assertEqual(animation["fixedLight"], "none")
        self.assertEqual(animation["meter"], "spot-meter")
        self.page.wait_for_timeout(250)
        moved = self.page.evaluate("""() => getComputedStyle(
          document.querySelector('.planet-earthlike .planet-sphere'), '::before').transform""")
        self.assertNotEqual(moved, animation["transform"])
        snapshot["effects"]["reduced_motion"] = True
        self.render(snapshot)
        stilled = self.page.evaluate("""() => [
          getComputedStyle(document.querySelector('.planet-earthlike .planet-sphere'), '::before').animationName,
          getComputedStyle(document.querySelector('.spot-meter')).animationName]""")
        self.assertEqual(stilled, ["none", "none"])
        # Reduced motion stills animation; it never stops the clock itself.
        before = self.state()["spotlight"]
        self.tick()
        self.assertNotEqual(self.state()["spotlight"], before)

    def test_auto_holds_the_overlay_still_up_to_its_threshold(self):
        # Reported live: Auto set to rotate above 15 worlds still cycled a
        # smaller system, because its manifest and catalogue kept paging.
        def worlds(count, system):
            return [bio_world(f"{system} R {index}", "Rocky body",
                              [{"name": f"Tussock {index}", "kind": "detected"}])
                    for index in range(1, count + 1)]
        # More quiet bodies than the default three chip lines hold, which a
        # rotating overlay would page.
        quiet = [quiet_body(f"Atlas Still B {index}") for index in range(1, 17)]
        limit = {"spotlight_rotation": "auto", "spotlight_threshold": 15}
        self.render(system_snapshot(worlds(12, "Atlas Still") + quiet, name="Atlas Still", rotation=limit))
        state = self.state()
        self.assertEqual((state["spotlightTurns"], state["rotating"], state["manifestPages"]),
                         (False, False, 1), state)
        self.assertEqual(len(self.manifest_names()), 12, "every world listed at once")
        self.assertEqual(state["groups"]["other"], {"total": 16, "page": 1, "pages": 1}, state)
        self.assertEqual(len(self.group_names("other")), 16, "every body shown at once")
        before = (state["spotlight"], self.manifest_names(), self.page.locator("#content").inner_text())
        self.tick()
        self.assertEqual((self.state()["spotlight"], self.manifest_names(),
                          self.page.locator("#content").inner_text()), before)
        self.assertLessEqual(self.check_geometry(), 700)
        # At the threshold, with more quiet bodies than fit, the worlds all
        # still show; the catalogue counts what it cannot fit, and nothing
        # pages.
        crowd = [quiet_body(f"Atlas Crowd B {index}") for index in range(1, 61)]
        self.render(system_snapshot(worlds(15, "Atlas Crowd") + crowd, name="Atlas Crowd", rotation=limit))
        state = self.state()
        self.assertEqual((state["rotating"], state["manifestPages"]), (False, 1), state)
        self.assertEqual(len(self.manifest_names()), 15)
        self.assertTrue(all(group["pages"] == 1 for group in state["groups"].values()), state)
        counts = self.page.locator(".group-count:visible").all_text_contents()
        self.assertTrue(any(text.startswith("+") and text.endswith(" MORE") for text in counts), counts)
        self.assertLessEqual(self.check_geometry(), 700)
        # Above the threshold the same overlay turns again.
        self.render(system_snapshot(worlds(16, "Atlas Turn") + quiet, name="Atlas Turn", rotation=limit))
        self.assertTrue(self.state()["spotlightTurns"])
        self.assertTrue(self.state()["rotating"])

    def test_spotlight_rotation_follows_the_studio_choice(self):
        few = [bio_world(f"Atlas P {index}", "Rocky body",
                         [{"name": f"Bacterium {index}", "kind": "detected"}]) for index in range(1, 4)]
        # Auto (the default) leaves a small system still: no turning, no meter.
        self.render(system_snapshot(few))
        state = self.state()
        self.assertFalse(state["spotlightTurns"], state)
        self.assertFalse(state["rotating"], state)
        self.assertEqual(self.page.locator(".spot-meter").count(), 0)
        before = state["spotlight"]
        self.tick()
        self.assertEqual(self.state()["spotlight"], before)
        # A lower Auto limit, or Always, turns the same three worlds.
        for rotation in ({"spotlight_rotation": "auto", "spotlight_threshold": 2}, ALWAYS):
            with self.subTest(rotation=rotation):
                self.render(system_snapshot(few, rotation=rotation))
                self.assertTrue(self.state()["spotlightTurns"])
                before = self.state()["spotlight"]
                self.tick()
                self.assertNotEqual(self.state()["spotlight"], before)

        many = [bio_world(f"Atlas Off Q {index}", "Rocky body",
                          [{"name": f"Stratum {index}", "kind": "detected"}]) for index in range(1, 13)]
        off = system_snapshot(many, name="Atlas Off", rotation={"spotlight_rotation": "off"})
        self.render(off)
        state = self.state()
        # Off holds the whole overlay still: every world is listed at once
        # and nothing turns on the clock.
        self.assertFalse(state["spotlightTurns"], state)
        self.assertFalse(state["rotating"], state)
        self.assertEqual(state["manifestPages"], 1, state)
        listed = self.manifest_names()
        self.assertEqual(sorted(listed, key=lambda name: int(name.split()[-1])),
                         [f"Q {index}" for index in range(1, 13)])
        start = state["spotlight"]
        self.tick()
        self.assertEqual((self.state()["spotlight"], self.manifest_names()), (start, listed))
        # Journal activity still moves the spotlight, which then stays put.
        many[10]["bio_details"] = [{"name": "Stratum 11", "kind": "sample", "progress": 1}]
        self.render(off)
        self.assertEqual(self.state()["spotlight"], "Q 11")
        self.assertEqual(self.page.locator(".manifest .body-row.spotlit").count(), 1)
        self.tick()
        self.tick()
        self.assertEqual(self.state()["spotlight"], "Q 11")
        self.assertLessEqual(self.check_geometry(), 700)

    def test_latest_quiet_scan_is_marked_and_focusable(self):
        routine = {
            "survey": {
                "mode": "system", "system": "Atlas", "scanned": 2, "total": 2,
                "total_known": True, "scope": "priority",
                "rows": [{"name": "Atlas R 1", "planet_class": "Rocky body",
                          "priority": False, "recent_scan": True,
                          "scan_timestamp": "2026-09-23T08:00:00Z"}],
            },
            "effects": {"reduced_motion": False},
        }
        self.render(routine)
        routine["survey"]["rows"] = [{"name": "Atlas R 2", "planet_class": "Icy body",
                                      "priority": False, "recent_scan": True,
                                      "scan_timestamp": "2026-09-23T08:01:00Z"}]
        self.render(routine)
        self.assertEqual(self.page.locator(".chip-name").all_text_contents(), ["R 2"])
        self.assertEqual(self.page.locator(".body-chip.recent").count(), 1)
        self.assertEqual(self.page.locator(".spotlight").count(), 0)
        self.page.wait_for_timeout(650)
        self.check_geometry()

        routine["survey"].update({
            "mode": "body", "body": routine["survey"]["rows"][0],
            "body_display": "Atlas R 2", "rows": [],
        })
        self.render(routine)
        self.assertEqual(self.page.locator(".focus-target").count(), 1)
        self.check_geometry()

    # -- body focus ------------------------------------------------------

    def test_body_focus_and_sampling_readouts(self):
        body = {
            "survey": {
                "mode": "body", "system": "Atlas",
                "body": {
                    "name": "Atlas A 2", "planet_class": "Water world",
                    "bio_count": 2, "organic_complete_count": 0,
                    "geo_count": 1, "landable": True, "gravity_g": 0.34,
                },
                "body_display": "Atlas A 2", "min_value": 100000, "max_value": 200000,
                "rows": [
                    {"name": "Bacterium Sample", "kind": "sample", "progress": 2},
                    {"name": "Fonticulua Detected", "kind": "detected"},
                ],
                "sampling": {
                    "species": "Bacterium Sample", "progress": 2,
                    "clear": False, "min_distance_m": 240, "colony_m": 500,
                },
            },
            "effects": {"reduced_motion": True},
        }
        self.render(body)
        focused = self.page.evaluate("""() => ({
          mode: document.querySelector('#survey').classList.contains('body'),
          modeLabel: document.querySelector('#mode-label')?.textContent,
          systemName: document.querySelector('#system-name')?.textContent,
          targetCount: document.querySelectorAll('.target').length,
          kind: document.querySelector('.target .planet-orb')?.dataset.planetKind,
          name: document.querySelector('.focus-target .spot-name')?.textContent,
          sampleCount: document.querySelectorAll('.sample-card').length,
          sampleDone: document.querySelectorAll('.sample-node.done').length,
          text: document.querySelector('#content').textContent,
          header: document.querySelector('#overview').textContent,
        })""")
        self.assertTrue(focused["mode"])
        self.assertTrue(focused["modeLabel"].startswith("BODY"), focused)
        self.assertEqual(focused["systemName"], "Atlas")
        self.assertEqual(focused["targetCount"], 1)
        self.assertEqual(focused["kind"], "water")
        self.assertEqual(focused["name"], "A 2")
        self.assertEqual(focused["sampleCount"], 1)
        self.assertEqual(focused["sampleDone"], 2)
        # The species in hand appears once, in the genetic-sequence card.
        self.assertEqual(focused["text"].count("Bacterium Sample"), 1)
        self.assertEqual(focused["text"].count("Fonticulua Detected"), 1)
        self.assertIn("260 M TO SAMPLE 03", focused["text"])
        self.assertIn("240 / 500 M SPACING", focused["text"])
        self.assertIn("0.34 G", focused["text"])
        self.assertIn("0/2", focused["header"])
        self.assertNotIn("A 2", focused["header"])
        self.check_geometry()
        for scale in (1.5, 2):
            with self.subTest(text_scale=scale):
                body["effects"]["text_scale"] = scale
                self.render(body)
                self.check_geometry()
                readout_fits = self.page.evaluate("""() =>
                  [...document.querySelectorAll('.sample-action, .sample-distance, .spot-name')]
                    .every(item => item.scrollWidth <= item.clientWidth + 1)""")
                self.assertTrue(readout_fits, scale)

        body["effects"]["text_scale"] = 1
        sampling = body["survey"]["sampling"]
        sampling["min_distance_m"] = 410
        self.render(body)
        self.assertIn("90 M TO SAMPLE 03", self.page.locator(".sample-action").text_content())
        self.assertIn("410 / 500 M SPACING", self.page.locator(".sample-distance").text_content())
        sampling.update({"min_distance_m": 530, "clear": True})
        self.render(body)
        self.assertEqual(self.page.locator(".sample-action").text_content(), "READY FOR SAMPLE 03")
        self.assertEqual(self.page.locator(".sample-distance").text_content(), "530 / 500 M SPACING")
        self.assertEqual(self.page.locator(".sample-card.ready").count(), 1)
        self.check_geometry()

        sampling["progress"] = 3
        self.render(body)
        self.assertEqual(self.page.locator(".sample-node.done").count(), 3)
        self.assertEqual(self.page.locator(".sample-action").text_content(), "SAMPLES SECURED")
        self.assertEqual(self.page.locator(".sample-distance").text_content(), "AWAITING ANALYSIS")
        self.assertEqual(self.page.locator(".sample-range-meter").count(), 0)
        self.check_geometry()

        sampling.update({"progress": 1, "clear": False, "min_distance_m": 0})
        self.render(body)
        self.assertEqual(self.page.locator(".sample-node.done").count(), 1)
        self.assertEqual(self.page.locator(".sample-action").text_content(), "500 M TO SAMPLE 02")
        sampling["min_distance_m"] = None
        self.render(body)
        self.assertEqual(self.page.locator(".sample-action").text_content(), "DISTANCE UNAVAILABLE")
        self.assertEqual(self.page.locator(".sample-distance").text_content(), "500 M REQUIRED")
        sampling["colony_m"] = None
        self.render(body)
        self.assertEqual(self.page.locator(".sample-distance").text_content(), "COLONY SPACING UNKNOWN")
        self.check_geometry()

        body["survey"]["sampling"] = None
        self.render(body)
        self.assertEqual(self.page.locator(".sample-card").count(), 0)
        body["survey"]["body"]["organic_complete_count"] = 2
        body["survey"]["rows"] = [
            {"name": "Bacterium Sample", "kind": "complete", "progress": 3},
            {"name": "Fonticulua Detected", "kind": "complete", "progress": 3},
        ]
        self.render(body)
        self.assertEqual(self.page.locator(".focus-target.complete .biological-row.complete").count(), 2)
        self.assertIn("Fonticulua Detected", self.page.locator(".focus-target").text_content())
        self.assertLessEqual(self.check_geometry(), 700)


if __name__ == "__main__":
    unittest.main()
