"""5.6.8: the pet-only overlay has room above its activities."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

from voidcompass.overlays.hatchling_hud import PET_HEIGHT_FACTOR, PET_SIZES, ROAMS, hatchling_pet_window
from voidcompass.overlays.html_hatchling_overlay import HtmlHatchlingBridge
from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin

WEB = Path(__file__).resolve().parents[1] / "web"


class PetOnlyWindowTests(unittest.TestCase):
    def test_all_size_and_roam_choices_reserve_extra_height(self):
        for size, pixels in PET_SIZES.items():
            for roam, factor in ROAMS.items():
                with self.subTest(size=size, roam=roam):
                    width, height = hatchling_pet_window({"hatchling_look": "pet", "hatchling_pet_size": size,
                                                           "hatchling_roam": roam})
                    self.assertEqual(width, round(pixels * factor))
                    self.assertEqual(height, round(pixels * PET_HEIGHT_FACTOR))
                    self.assertGreaterEqual(height, pixels * 2.75)

    def test_studio_look_change_is_published_by_the_running_bridge(self):
        config = {"hatchling_overlay_enabled": True, "hatchling_look": "panel", "hatchling_hud_x": 160,
                  "hatchling_hud_y": 240}
        master = SimpleNamespace(_voidcompass_startup_presentation_held=False)
        win = SimpleNamespace(master=master, state=lambda: "normal", winfo_x=lambda: 160, winfo_y=lambda: 240,
                              call_later=lambda *_args: None)
        overlay = SimpleNamespace(win=win, config=config, _palette={}, _html_render_model={"name": "Pip"})
        surface = SimpleNamespace(startup_failed=False, ready=True, server=SimpleNamespace(
            rendered_content_height=lambda _id: 176), publish=Mock())
        bridge = HtmlHatchlingBridge.__new__(HtmlHatchlingBridge)
        for key, value in {
            "overlay": overlay, "win": win, "config": config, "overlay_id": "hatchling",
            "title": "Hatchling", "enabled_key": "hatchling_overlay_enabled", "x_key": "hatchling_hud_x",
            "y_key": "hatchling_hud_y", "template": "hatchling", "snapshot_key": "hatchling",
            "model_attr": "_html_render_model", "log_name": "Hatchling", "width": 250,
            "min_height": 110, "default_height": 176, "max_height": 320, "surface": surface,
            "_ready": False, "_disposed": False, "_sync_job": None, "_last_fingerprint": None,
            "_last_quick_fingerprint": None, "_browser_content_height": 0,
        }.items():
            setattr(bridge, key, value)
        bridge._sync()
        panel = surface.publish.call_args.args[0]["window"]
        self.assertEqual((panel["width"], panel["height"]), (250, 176))

        refresh = Mock(side_effect=lambda force: setattr(overlay, "_html_render_model", {
            "name": "Pip", "options": {"look": config["hatchling_look"]}}))
        deck = SimpleNamespace(config=config, _persist_config=lambda: None, update_hud=lambda: None,
                               _schedule_html_dashboard_publish=lambda **_kw: None, _hatchling_overlay_refresh=refresh)
        HtmlOverlayStudioMixin._html_overlay_settings_save(deck, {"hatchling_look": "pet"})
        refresh.assert_called_with(force=True)
        bridge._sync()
        pet = surface.publish.call_args.args[0]["window"]
        self.assertEqual((pet["width"], pet["height"]), hatchling_pet_window(config))
        self.assertGreater(pet["height"], panel["height"])
        self.assertEqual(overlay._html_window_size, (pet["width"], pet["height"]))

        HtmlOverlayStudioMixin._html_overlay_settings_save(deck, {"hatchling_look": "panel"})
        bridge._sync()
        again = surface.publish.call_args.args[0]["window"]
        self.assertEqual((again["width"], again["height"]), (250, 176))

    def test_studio_clamps_an_expanding_pet_window_on_its_scaled_monitor(self):
        config = {"hatchling_look": "panel", "hatchling_hud_x": -900, "hatchling_hud_y": 900}
        move = Mock(side_effect=lambda _attr, x, y, **_kw: config.update(hatchling_hud_x=x, hatchling_hud_y=y))
        deck = SimpleNamespace(config=config, hatchling_hud=SimpleNamespace(_html_window_size=(250, 176)),
                               _set_overlay_position=move, _persist_config=Mock(), update_hud=Mock(),
                               _schedule_html_dashboard_publish=Mock(), _hatchling_overlay_refresh=Mock())
        with patch("voidcompass.dashboard.html_overlay_studio.monitor_scale", return_value=1.5), \
             patch("voidcompass.dashboard.html_overlay_studio.monitor_bounds", return_value=(-1920, 0, 0, 1080)) as bounds:
            HtmlOverlayStudioMixin._html_overlay_settings_save(deck, {"hatchling_look": "pet"})
            bounds.assert_called_once_with(-712, 1032)
            move.assert_called_once_with("hatchling_hud", -900, 693, authority_s=3.0)
            self.assertEqual(config["hatchling_hud_y"], 693)
            deck._persist_config.assert_called_once()

            # A later manual placement isn't silently changed by unrelated
            # settings or by saving an already-selected look.
            config["hatchling_hud_y"] = 900
            HtmlOverlayStudioMixin._html_overlay_settings_save(deck, {"hatchling_look": "pet"})
            HtmlOverlayStudioMixin._html_overlay_settings_save(deck, {"hatchling_chatter": "chatty"})
            self.assertEqual(move.call_count, 1)
            self.assertEqual(config["hatchling_hud_y"], 900)

    def test_studio_does_not_move_a_pet_window_that_already_fits(self):
        config = {"hatchling_look": "panel", "hatchling_hud_x": 50, "hatchling_hud_y": 100}
        move = Mock()
        deck = SimpleNamespace(config=config, hatchling_hud=SimpleNamespace(_html_window_size=(250, 176)),
                               _set_overlay_position=move, _persist_config=Mock(), update_hud=Mock(),
                               _schedule_html_dashboard_publish=Mock(), _hatchling_overlay_refresh=Mock())
        with patch("voidcompass.dashboard.html_overlay_studio.monitor_scale", return_value=1), \
             patch("voidcompass.dashboard.html_overlay_studio.monitor_bounds", return_value=(0, 0, 1920, 1080)):
            HtmlOverlayStudioMixin._html_overlay_settings_save(deck, {"hatchling_look": "pet"})
        move.assert_not_called()


class PetOnlyVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def test_3d_limpet_is_not_clipped_by_the_renderer_above_the_pet(self):
        page = self.browser.new_page(viewport={"width": 320, "height": 320})
        self.addCleanup(page.close)

        def serve(route):
            file = WEB / urlsplit(route.request.url).path.lstrip("/")
            return route.fulfill(path=str(file)) if file.is_file() else route.fulfill(status=404, body="")

        page.route("http://height.test/**", serve)
        page.goto("http://height.test/hatchling/index.html")
        page.wait_for_function("Boolean(window.Hatchling3D)")
        result = page.evaluate("""() => {
          const c = document.createElement('canvas'); c.width = c.height = 320;
          const ctx = c.getContext('2d');
          const pet = {species: 'larva', stage: 'juvenile', needs: {mood: 85}};
          const args = {x: 160, y: 160, size: 150, t: 1.25, aura: false};
          function draw(activity) {
            ctx.clearRect(0, 0, 320, 320);
            Hatchling3D.draw(ctx, pet, {...args, activity});
            return ctx.getImageData(125, 0, 70, 40).data;
          }
          const empty = draw({name: 'idle'});
          const playing = draw({name: 'keepy', ball: {x: 0, y: -135, spin: 0}});
          let changed = 0;
          for (let i = 0; i < empty.length; i += 4)
            if (Math.abs(empty[i + 3] - playing[i + 3]) > 12 ||
                Math.abs(empty[i] - playing[i]) > 12) changed++;
          return changed;
        }""")
        self.assertGreater(result, 10, "the high limpet must render above the old 3D canvas edge")

    def test_large_speech_fits_the_narrow_pet_only_windows(self):
        page = self.browser.new_page(viewport={"width": 320, "height": 320})
        self.addCleanup(page.close)

        def serve(route):
            file = WEB / urlsplit(route.request.url).path.lstrip("/")
            return route.fulfill(path=str(file)) if file.is_file() else route.fulfill(status=404, body="")

        page.route("http://height.test/**", serve)
        page.goto("http://height.test/hatchling/index.html")
        page.wait_for_function("Boolean(window.HatchlingLife && window.HatchlingArt)")
        rows = page.evaluate("""sizes => sizes.map(size => {
          const canvas = document.createElement('canvas');
          canvas.width = Math.round(size * 1.7); canvas.height = Math.round(size * 2.8);
          const ctx = canvas.getContext('2d'), text = [];
          ctx.fillText = (word, x, y) => text.push({word, x, y, width: ctx.measureText(word).width});
          const life = HatchlingLife.create({size, range: (canvas.width - size) / 2,
            top: canvas.height - size * .5, ink: 9.5, text: 2});
          const pet = {species: 'larva', stage: 'adult', needs: {mood: 80},
            chat: {text: 'Hello, Synuefe AB-C d1-2. We found something alive.', at: Date.now() / 1000}};
          life.step(.05, pet); life.front(ctx, pet, canvas.width / 2, canvas.height - size * .5);
          return {width: canvas.width, height: canvas.height, text};
        })""", list(PET_SIZES.values()))
        for row in rows:
            self.assertGreater(len(row["text"]), 1, "long words wrap in the small window")
            for line in row["text"]:
                self.assertGreaterEqual(line["x"] - line["width"] / 2, 0)
                self.assertLessEqual(line["x"] + line["width"] / 2, row["width"])
                self.assertGreaterEqual(line["y"], 0)
                self.assertLessEqual(line["y"], row["height"])


if __name__ == "__main__":
    unittest.main()
