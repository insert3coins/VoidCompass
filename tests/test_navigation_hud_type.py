"""The Navigation HUD's type is set in Overlay Studio.

Some of the HUD's small labels were hard to read, so the commander picks a
typeface (Cockpit, Clear or Terminal), the HUD's own text size (which grows
the window, as the overlay-wide size does), a floor for the small text that
keeps the window's size, and brighter labels. Every combination must still
fit the fixed cockpit layout in both layouts.
"""

from pathlib import Path
import re
import unittest
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit

from voidcompass.core import config as config_module
from voidcompass.core import theme_state, themes
from voidcompass.core.application_runtime import ApplicationRuntime
from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
from voidcompass.overlays.hud import (
    HUD_FONT_FACES, HUD_LABEL_SIZES, TacticalHUD, hud_text_scale_percent, hud_typography,
)
from tests.test_navigation_state_visuals import hud_snapshot, hud_state

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SHIP_ART = ROOT / "assets" / "images" / "ships"


class NavigationTypeSettingsTests(unittest.TestCase):
    def test_typography_is_sanitised(self):
        self.assertEqual(hud_typography({}), {"face": "cockpit", "labels": "standard", "bright": False})
        self.assertEqual(
            hud_typography({"hud_font_face": "Clear", "hud_label_size": "LARGER", "hud_bright_labels": True}),
            {"face": "clear", "labels": "larger", "bright": True})
        self.assertEqual(hud_typography({"hud_font_face": "comic", "hud_label_size": "huge"})["face"], "cockpit")
        self.assertEqual(hud_typography({"hud_label_size": "huge"})["labels"], "standard")

    def test_own_text_size_overrides_the_overlay_wide_one(self):
        self.assertEqual(hud_text_scale_percent({"overlay_text_scale_percent": 125}), 125)
        self.assertEqual(hud_text_scale_percent({"overlay_text_scale_percent": 125, "hud_text_scale_percent": 0}), 125)
        self.assertEqual(hud_text_scale_percent({"overlay_text_scale_percent": 125, "hud_text_scale_percent": 150}), 150)
        self.assertEqual(hud_text_scale_percent({"hud_text_scale_percent": 400}), 200)
        self.assertEqual(hud_text_scale_percent({"hud_text_scale_percent": "x"}), 100)

    def test_model_and_window_follow_the_hud_settings(self):
        root = ApplicationRuntime()
        try:
            hud = TacticalHUD(root, {"overlay_text_scale_percent": 100, "hud_text_scale_percent": 150,
                                     "hud_font_face": "clear", "hud_label_size": "large",
                                     "hud_bright_labels": True})
            try:
                hud.update("SYNUEFE XR-H D11-102", "", 0, 7, 16, None, {},
                           nav_context={"current": "SYNUEFE XR-H D11-102", "flight_state": "SUPERCRUISE"})
                model = hud._html_last_model
                self.assertEqual(model["theme"]["type"], {"face": "clear", "labels": "large", "bright": True})
                # Its own 150% grows the window just as 150% for all overlays does.
                self.assertEqual(model["theme"]["text_scale"], 1.5)
                self.assertEqual((model["window"]["width"], model["window"]["height"]), (750, 489))
            finally:
                hud.win.destroy()
        finally:
            root.close()

    def test_live_profile_theme_updates_flight_state_colour(self):
        original_name = themes.ACTIVE_THEME_NAME
        original_palette = dict(themes.ACTIVE_PALETTE)
        root = ApplicationRuntime()
        hud = None
        try:
            hud = TacticalHUD(root, {})
            hud.update("SYNUEFE XR-H D11-102", "", 0, 7, 16, None, {},
                       nav_context={"flight_state": "SUPERCRUISE", "fuel_percent": 71})
            _, profile_palette = themes.resolve_theme("Emerald")
            theme_state.apply_theme_live(root, "Emerald", profile_palette)
            hud.apply_theme(profile_palette)
            model = hud._html_last_model
            self.assertEqual(model["theme"]["orange"], profile_palette["orange"])
            self.assertEqual(model["state"]["color"], profile_palette["orange"])
            self.assertEqual(model["metrics"]["fuel"]["color"], profile_palette["green"])
            for label, slot in (
                ("FSS", "accent"), ("MASS LOCK", "yellow"),
                ("DOCK CLEARED", "green"), ("FLIGHT", "dim"),
            ):
                self.assertEqual(hud._state_color(label), profile_palette[slot], label)
        finally:
            theme_state.apply_theme_live(root, original_name, original_palette)
            if hud is not None:
                hud.win.destroy()
            root.close()

    def test_studio_saves_each_type_setting_on_its_own(self):
        class Studio(HtmlOverlayStudioMixin):
            def __init__(self):
                self.config = {"survey_spotlight_threshold": 12, "hud_compact_mode": True}
                self.hud_updates = 0

            def _persist_config(self):
                pass

            def update_hud(self):
                self.hud_updates += 1

            def _schedule_html_dashboard_publish(self, **kwargs):
                pass

        studio = Studio()
        studio._html_overlay_settings_save({"hud_font_face": "Terminal"})
        studio._html_overlay_settings_save({"hud_label_size": "larger"})
        studio._html_overlay_settings_save({"hud_text_scale_percent": "130"})
        self.assertEqual((studio.config["hud_font_face"], studio.config["hud_label_size"],
                          studio.config["hud_text_scale_percent"]), ("terminal", "larger", 130))
        studio._html_overlay_settings_save({"hud_font_face": "comic", "hud_label_size": "huge",
                                            "hud_text_scale_percent": "0"})
        self.assertEqual((studio.config["hud_font_face"], studio.config["hud_label_size"],
                          studio.config["hud_text_scale_percent"]), ("cockpit", "standard", 0))
        self.assertEqual(studio.config["survey_spotlight_threshold"], 12)
        self.assertTrue(studio._html_overlay_option_toggle("hud_bright_labels", True))
        self.assertTrue(studio.config["hud_bright_labels"])
        self.assertGreaterEqual(studio.hud_updates, 5, "the HUD picks every change up live")

    def test_settings_follow_the_commander_profile(self):
        self.assertIn("hud_text_scale_percent", config_module.PROFILE_VALUE_SETTINGS)
        self.assertIn("hud_font_face", config_module.PROFILE_TEXT_SETTINGS)
        self.assertIn("hud_label_size", config_module.PROFILE_TEXT_SETTINGS)
        self.assertIn("hud_bright_labels", config_module.PROFILE_BOOL_SETTINGS)

    def test_studio_offers_exactly_the_supported_choices(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = re.search(r'<section data-studio-settings="hud">(.*?)</section>', html, re.S).group(1)
        face = re.search(r'data-studio-setting="hud_font_face">(.*?)</select>', section, re.S).group(1)
        labels = re.search(r'data-studio-setting="hud_label_size">(.*?)</select>', section, re.S).group(1)
        self.assertEqual(tuple(re.findall(r'value="([a-z]+)"', face)), HUD_FONT_FACES)
        self.assertEqual(tuple(re.findall(r'value="([a-z]+)"', labels)), HUD_LABEL_SIZES)
        self.assertIn('data-studio-setting="hud_text_scale_percent"', section)
        self.assertIn('data-overlay-option="hud_bright_labels"', section)


# Every visible piece of text inside its row, and the chosen type applied.
FIT = """(expected) => {
  const failures = [];
  const root = document.documentElement;
  if (root.scrollWidth > innerWidth + 1 || root.scrollHeight > innerHeight + 1) failures.push('page scrolls');
  for (const selector of ['.status-plate', '.location', '.route-block', '.survey-block', '.context-rail']) {
    const section = document.querySelector(selector).getBoundingClientRect();
    for (const node of document.querySelectorAll(`${selector} *`)) {
      // The lamp strip shows what fits and clips the rest by design.
      if (node.closest('.lamps')) continue;
      if (node.childElementCount || !node.textContent.trim()) continue;
      const style = getComputedStyle(node);
      if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
      const box = node.getBoundingClientRect();
      if (!box.width || !box.height) continue;
      if (box.top < section.top - .5 || box.bottom > section.bottom + .5 || box.right > section.right + .5)
        failures.push(`${selector} ${node.id || node.className || node.tagName}`);
    }
  }
  const hud = document.getElementById('hud');
  if (hud.dataset.face !== expected.face || hud.dataset.labels !== expected.labels) failures.push('type not applied');
  const region = getComputedStyle(document.getElementById('region-label'));
  if (!region.fontFamily.includes(expected.family)) failures.push(`family ${region.fontFamily}`);
  if (parseFloat(region.fontSize) < expected.floor - .01) failures.push(`label ${region.fontSize} under floor`);
  return failures;
}"""
FAMILY = {"cockpit": "Bahnschrift", "clear": "Segoe UI", "terminal": "Cascadia Mono"}
FLOOR = {"standard": 0, "large": 10, "larger": 11.5}

NOTICE_FITS = """() => {
  const state = document.getElementById('state-label');
  const event = document.getElementById('event-notice');
  const host = event.parentElement.getBoundingClientRect();
  const eventBox = event.getBoundingClientRect();
  const deck = document.querySelector('.deck').getBoundingClientRect();
  const failures = [];
  if (getComputedStyle(state).textOverflow === 'ellipsis') failures.push('state uses ellipsis');
  if (state.scrollWidth > state.clientWidth + 1) failures.push('state text clipped');
  if (event.scrollWidth > event.clientWidth + 1 || event.scrollHeight > event.clientHeight + 1)
    failures.push('event text clipped');
  if (eventBox.left < host.left - 1 || eventBox.right > host.right + 1
      || eventBox.top < host.top - 1 || eventBox.bottom > host.bottom + 1)
    failures.push('event escapes its row');
  if (eventBox.left < deck.right && eventBox.right > deck.left
      && eventBox.top < deck.bottom && eventBox.bottom > deck.top)
    failures.push('event covers state visualization');
  return failures;
}"""
STATUS_GEOMETRY = """() => ['.instrument', '.deck', '#deck-canvas', '.systems-row']
  .map(selector => { const box = document.querySelector(selector).getBoundingClientRect();
    return [box.x, box.y, box.width, box.height].map(value => Math.round(value * 100) / 100); })"""


class NavigationTypeBrowserTests(unittest.TestCase):
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

    def open(self, width, height):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))

        def serve(route, _request=None):
            path = unquote(urlsplit(route.request.url).path)
            target = (SHIP_ART / path[len("/ship-art/"):] if path.startswith("/ship-art/")
                      else WEB / path.lstrip("/"))
            if target.is_file():
                route.fulfill(path=str(target))
            else:
                route.fulfill(status=404, body="")

        page.route("http://state.test/**", serve)
        page.goto("http://state.test/navigation_hud/index.html")
        return page

    def test_every_typeface_and_small_text_size_fits_both_layouts(self):
        for layout, width, height in (("standard", 500, 326), ("expanded", 620, 342)):
            page = self.open(width, height)
            for face in HUD_FONT_FACES:
                for labels in HUD_LABEL_SIZES:
                    for label in ("SUPERCRUISE", "FSD INJECTION +50%", "SUIT OXYGEN LOW"):
                        state = hud_state(label, landing_gear=True, hardpoints_deployed=True,
                                          cargo_scoop=True, night_vision=True, fuel_scooping=True)
                        snapshot = hud_snapshot(state, layout=layout)
                        snapshot["system"]["name"] = "PLAA AEC IZ-N C20-1 AB 12 C"
                        snapshot["theme"]["type"] = {"face": face, "labels": labels, "bright": True}
                        with self.subTest(layout=layout, face=face, labels=labels, label=label):
                            page.evaluate("snapshot => render(snapshot)", snapshot)
                            failures = page.evaluate(FIT, {"face": face, "labels": labels,
                                                           "family": FAMILY[face], "floor": FLOOR[labels]})
                            self.assertEqual(failures, [])

    def test_brighter_labels_lift_the_faded_ones(self):
        page = self.open(500, 326)
        colours = []
        for bright in (False, True):
            snapshot = hud_snapshot(hud_state("SUPERCRUISE"))
            snapshot["theme"]["type"] = {"face": "cockpit", "labels": "standard", "bright": bright}
            page.evaluate("snapshot => render(snapshot)", snapshot)
            colours.append(page.evaluate("""() => ['survey-title', 'traffic-label', 'region-label']
              .map((id) => getComputedStyle(document.getElementById(id)).color)"""))
        for faded, lifted in zip(*colours):
            self.assertNotEqual(faded, lifted)
        # Without type settings the HUD keeps its designed look.
        snapshot = hud_snapshot(hud_state("SUPERCRUISE"))
        page.evaluate("snapshot => render(snapshot)", snapshot)
        self.assertEqual(page.evaluate("""() => [document.getElementById('hud').dataset.face,
          getComputedStyle(document.getElementById('region-label')).fontSize]"""), ["cockpit", "8.5px"])

    def test_display_label_uses_exact_custom_profile_colour(self):
        page = self.open(500, 326)
        # The chosen accent deliberately matches a former hardcoded orange
        # mapping. It must remain the commander's accent, not become orange.
        palette = themes.normalize_theme({"accent": "#ff7a18", "orange": "#2874c2"})
        state = hud_state("FSS")
        state["color"] = palette["accent"]
        snapshot = hud_snapshot(state)
        snapshot["theme"].update(palette)
        page.evaluate("snapshot => render(snapshot)", snapshot)
        self.assertEqual(page.evaluate("""() => getComputedStyle(
            document.getElementById('state-label')).color"""), "rgb(255, 122, 24)")

    def test_flight_state_and_event_text_remain_complete(self):
        sequence = 0
        for layout, width, height, scale in (
            ("standard", 500, 326, 1), ("standard", 750, 489, 1.5),
            ("standard", 1000, 652, 2),
            ("expanded", 620, 342, 1),
        ):
            page = self.open(width, height)
            page.evaluate("snapshot => render(snapshot)",
                          hud_snapshot(hud_state("SUPERCRUISE"), layout=layout, scale=scale))
            normal_geometry = page.evaluate(STATUS_GEOMETRY)
            labels_to_check = page.evaluate(
                "() => [...Object.keys(DISPLAY_LABELS), 'SUPERCRUISE', 'PAD 07 CLEARED', 'PAD 999 CLEARED']"
            )
            for face in HUD_FONT_FACES:
                for labels in HUD_LABEL_SIZES:
                    for label in labels_to_check:
                        sequence += 1
                        state = hud_state(label)
                        state["notice"] = {
                            "seq": sequence, "text": "FIRST DISCOVERY",
                            "detail": "SYNUEFE XR-H D11-102 ABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
                            "duration": 5,
                        }
                        snapshot = hud_snapshot(state, layout=layout, scale=scale)
                        snapshot["theme"]["type"] = {"face": face, "labels": labels, "bright": True}
                        with self.subTest(layout=layout, scale=scale, face=face, labels=labels, state=label):
                            page.evaluate("snapshot => render(snapshot)", snapshot)
                            self.assertEqual(page.evaluate(NOTICE_FITS), [])
                            self.assertEqual(page.evaluate(STATUS_GEOMETRY), normal_geometry)

            # Once the transient notice expires, it must stop taking space.
            sequence += 1
            state = hud_state("SUPERCRUISE")
            state["notice"] = {"seq": sequence, "text": "SYSTEM SCAN", "duration": .01}
            page.evaluate("snapshot => render(snapshot)", hud_snapshot(state, layout=layout, scale=scale))
            page.wait_for_timeout(1100)
            self.assertEqual(page.evaluate("""() => {
              const event = document.getElementById('event-notice');
              const state = document.getElementById('state-label');
              return [document.getElementById('hud').classList.contains('event-inline')
                  || document.getElementById('hud').classList.contains('event-footer'),
                getComputedStyle(event).display, event.textContent,
                state.scrollWidth > state.clientWidth + 1];
            }"""), [False, "none", "", False])
            self.assertEqual(page.evaluate(STATUS_GEOMETRY), normal_geometry)

    def test_event_repositions_when_status_tag_changes(self):
        page = self.open(500, 326)
        state = hud_state("SC ASSIST")
        state["category"] = "drive"
        state["notice"] = {
            "seq": 1, "text": "FIRST DISCOVERY", "detail": "XXXXXX", "duration": 5,
        }
        page.evaluate("snapshot => render(snapshot)", hud_snapshot(state))
        geometry = page.evaluate(STATUS_GEOMETRY)
        self.assertTrue(page.evaluate("() => document.getElementById('hud').classList.contains('event-inline')"))

        # A telemetry update may widen the tag while the same notice is active.
        state["category"] = "alert"
        page.evaluate("snapshot => render(snapshot)", hud_snapshot(state))
        self.assertTrue(page.evaluate("() => document.getElementById('hud').classList.contains('event-footer')"))
        self.assertEqual(page.evaluate(NOTICE_FITS), [])
        self.assertEqual(page.evaluate(STATUS_GEOMETRY), geometry)


if __name__ == "__main__":
    unittest.main()
