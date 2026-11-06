"""Distinct companion palettes survive Studio saves and reach both displays."""
from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageChops
from tests import test_crew_motion_studio_574 as motion
from tests import test_crew_ui_574 as crew
from tests import test_watcher_three_568 as three
from tests.test_heartbeat_orb import snapshot, THEME
from voidcompass.core import companions


PALETTES = {
    "aster": ("Aster cyan", "#65e4ef", "#a8b4ff"),
    "axiom": ("Axiom violet", "#a897ff", "#65e4ef"),
    "meridian": ("Meridian gold", "#e8c48c", "#74bbff"),
    "lyra": ("Lyra aurora", "#74ddff", "#ec9fdb"),
}
ARTIFACTS = Path(tempfile.gettempdir()) / "voidcompass-companion-palettes"
ARTIFACTS.mkdir(exist_ok=True)


class PaletteSettingsTests(unittest.TestCase):
    def test_defaults_and_legacy_red_use_signature_without_overwriting_explicit_choices(self):
        for identity in PALETTES:
            values = {**companions.new_defaults(), "companion_identity": identity}
            self.assertEqual(companions.display_accent(values), "signature")
            self.assertEqual(companions.display_accent(dict(values, **{f"{identity}_hud_accent": "hal"})), "signature")
            for accent in ("theme", "cyan", "brass"):
                self.assertEqual(companions.normalize_accent(identity, accent), accent)
        self.assertEqual(companions.display_accent({"heartbeat_eye_color": "hal"}), "hal")
        self.assertEqual(companions.display_accent({}), "theme")

    def test_signature_and_legacy_studio_saves_publish_the_active_profile_only(self):
        for identity in PALETTES:
            studio, hud, bridge = motion.live_studio(identity)
            for payload in ({"companion_accent": "signature"},
                            {"companion_accent": "hal"},
                            {f"{identity}_hud_accent": "hal"}):
                studio.config[f"{identity}_hud_accent"] = "theme"
                self.assertTrue(studio._handle_html_overlay_studio_command({"operation": "save_settings", **payload}))
                self.assertEqual(studio.config[f"{identity}_hud_accent"], "signature")
                self.assertEqual(bridge.surface.publish.call_args.args[0]["heartbeat"]["orb"]["accent"], "signature")
                self.assertEqual(studio._html_overlay_studio()["options"]["companion_accent"], "signature")
            self.assertNotEqual(studio.config.get("heartbeat_eye_color"), "signature")


class PaletteOverlayTests(unittest.TestCase):
    setUpClass = classmethod(three.WatcherThreeBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(three.WatcherThreeBrowserTests.tearDownClass.__func__)
    open_page = three.WatcherThreeBrowserTests.open_page

    def test_studio_offers_the_selected_signature_and_retains_watcher_hal_red(self):
        page = self.open_page("dashboard/index.html")
        choices = page.evaluate('''async () => {
            const {renderCompanionStudio} = await import('/dashboard/companion-ui.js');
            return ['watcher','aster','axiom','meridian','lyra'].map(identity => {
                renderCompanionStudio({companion_identity:identity, companion_accent:'hal'});
                const field = document.querySelector('[data-studio-setting="companion_accent"]');
                return {identity,value:field.value,options:[...field.options].map(o=>[o.value,o.textContent])};
            });
        }''')
        for row in choices:
            watcher = row["identity"] == "watcher"
            expected = ("hal", "HAL red") if watcher else ("signature", PALETTES[row["identity"]][0])
            self.assertEqual(row["value"], expected[0])
            self.assertEqual(tuple(row["options"][0]), expected)
            self.assertEqual([option[0] for option in row["options"][1:]], ["theme", "cyan", "brass"])

    def test_floating_palettes_repaint_and_eye_colour_captions_follow_them(self):
        page = self.open_page("heartbeat/index.html", reduced=True)
        page.set_viewport_size({"width": 192, "height": 192})
        page.route("http://watcher3d.test/api/live*", lambda route: route.fulfill(content_type="application/json", body="{}"))
        page.wait_for_function("Boolean(window.CrewCompanion && window.AsterCompanion && window.renderHeartbeat)")
        for identity, (_, primary, secondary) in PALETTES.items():
            data = snapshot(crt=False, reduced=True)
            data["theme"]["accent"] = "#44bb66"
            data["heartbeat"]["orb"].update(identity=identity, accent="signature", size=192, motion=False, focus_movement="off")
            page.evaluate("data => renderHeartbeat(data)", data)
            display = "AsterCompanion" if identity == "aster" else "CrewCompanion"
            inspect = f'{display}.inspect(document.getElementById("orb"))'
            page.wait_for_function(f"{inspect}?.frames > 0")
            info = page.evaluate(inspect)
            self.assertEqual((info["accent"], info["secondary"]), (primary, secondary))
            signature = Image.open(BytesIO(page.screenshot(path=str(ARTIFACTS / f"{identity}-signature.png")))).convert("RGB")
            data["heartbeat"]["orb"]["accent"] = "theme"
            page.evaluate("data => renderHeartbeat(data)", data)
            page.wait_for_timeout(90)
            themed = Image.open(BytesIO(page.screenshot())).convert("RGB")
            diff = ImageChops.difference(signature, themed)
            self.assertGreater(sum(max(rgb) > 20 for rgb in diff.get_flattened_data()), 100)
            self.assertEqual(page.evaluate(inspect)["accent"], "#44bb66")
            # Old non-Watcher red settings select the real signature, including captions.
            data["heartbeat"]["orb"]["accent"] = "hal"
            data["heartbeat"]["thought"] = {"id": 1, "text": "On watch.", "style": {"colour": "eye"}}
            page.evaluate("data => renderHeartbeat(data)", data)
            self.assertEqual(page.evaluate(inspect)["accent"], primary)
            self.assertEqual(page.get_attribute("body", "data-thought-colour"), "companion")
            self.assertEqual(page.evaluate('getComputedStyle(document.querySelector(".thought")).getPropertyValue("--thought-ink").trim()'), primary)
        page.evaluate("data => renderHeartbeat(data)", snapshot(eye="hal"))
        self.assertEqual(page.evaluate("heartbeatOrb.state().base"), THEME["red"])


class PaletteDeckTests(unittest.TestCase):
    setUpClass = crew.CrewPageTests.__dict__["setUpClass"]
    tearDownClass = crew.CrewPageTests.__dict__["tearDownClass"]
    setUp = crew.CrewPageTests.setUp
    load_module = crew.CrewPageTests.load_module
    render = crew.CrewPageTests.render
    commands = crew.CrewPageTests.commands

    def test_panel_and_display_use_own_palette_and_theme_choice_uses_global_theme(self):
        for identity, (_, primary, secondary) in PALETTES.items():
            self.data.update(identity=identity, companion_name=companions.NAMES[identity],
                             heartbeat={"orb": {"identity": identity, "accent": "signature", "motion": False}})
            self.render()
            self.page.click('[data-watcher-tab="now"]')
            self.assertEqual(self.page.locator(".watcher-eye-panel").evaluate('node=>node.style.getPropertyValue("--accent")'), primary)
            display = "AsterCompanion" if identity == "aster" else "CrewCompanion"
            inspect = f'{display}.inspect(document.getElementById("watcher-orb"))'
            self.page.wait_for_function(f"{inspect}?.frames > 0")
            info = self.page.evaluate(inspect)
            self.assertEqual((info["accent"], info["secondary"]), (primary, secondary))
            self.data["heartbeat"]["orb"]["accent"] = "theme"
            self.page.evaluate('document.documentElement.style.setProperty("--accent", "#72bb88")')
            self.render()
            self.assertEqual(self.page.evaluate(inspect)["accent"], "#72bb88")
        self.data.update(identity="watcher", heartbeat={"orb": {"eye": "hal"}})
        self.render()
        self.assertEqual(self.page.locator(".watcher-eye-panel").evaluate('node=>node.style.getPropertyValue("--accent")'), "")
