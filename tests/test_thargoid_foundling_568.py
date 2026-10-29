"""5.6.8: a new Thargoid companion, inspired by the field guide."""

import json
import random
import unittest
from pathlib import Path
from string import Formatter
from urllib.parse import urlsplit

from tests.test_hatchling_563 import HOUR
from voidcompass.core import hatchling, hatchling_chatter
from voidcompass.core.hatchling_thargoid_lines import THARGOID_LINES
from voidcompass.dashboard.dashboard_games_mixin import DashboardGamesMixin
from voidcompass.overlays.hatchling_hud import build_hatchling_model, hatchling_overlay_options

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class FoundlingTests(unittest.TestCase):
    def setUp(self):
        self.state = hatchling.new_state()
        self.assertTrue(hatchling.act(self.state, "hatch", {"species": "thargoid", "name": "Ember"}, 0)[0])

    def stage(self, age):
        # Test growth without letting unrelated hunger decay obscure the result.
        now = 100 * HOUR
        self.state["pet"]["born"] = now - age * HOUR
        self.state["pet"]["last"] = now - 1
        return hatchling.view(self.state, now)["pet"]

    def test_growth_is_saved_and_reaches_the_overlay(self):
        self.assertEqual((self.stage(.1)["stage"], self.stage(.1)["stage_name"]), ("egg", "Egg"))
        for age, stage, name in ((1, "hatchling", "Scout"), (25, "juvenile", "Thargon"), (73, "adult", "Orthrus")):
            pet = self.stage(age)
            self.assertEqual((pet["species"], pet["stage"], pet["stage_name"]), ("thargoid", stage, name))
            overlay = build_hatchling_model({"pet": pet}, 100 * HOUR)
            self.assertEqual((overlay["species"], overlay["stage"], overlay["stage_name"]), ("thargoid", stage, name))
        loaded = hatchling.load_state(json.dumps(self.state))
        self.assertEqual((loaded["pet"]["species"], loaded["pet"]["stage"], loaded["pet"]["name"]),
                         ("thargoid", "adult", "Ember"))

    def test_food_medicine_growth_forms_and_old_companions(self):
        self.assertIn("foodcartridges", self.state["pet"]["larder"])
        self.assertIn("Basic Medicines", hatchling._medicine_names("thargoid"))
        hatchling.observe(self.state, {"event": "MarketBuy", "Type": "fish", "Count": 1}, 1)
        self.assertEqual(self.state["pet"]["larder"]["fish"], 1)
        for species in ("larva", "bot", "sample"):
            old = hatchling.new_state()
            self.assertTrue(hatchling.act(old, "hatch", {"species": species}, 0)[0])
            self.assertEqual(hatchling.load_state(json.dumps(old))["pet"]["species"], species)
        for form in ("standard", "explored", "scarred", "neglected", "rare"):
            self.assertIn(form, hatchling.SPECIES["thargoid"]["forms"])

    def test_own_text_lines_are_triggered_by_journal_and_growth(self):
        self.assertGreaterEqual(len(THARGOID_LINES), 40)
        self.assertTrue(set(hatchling.CUES.values()) <= set(THARGOID_LINES))
        for lines in THARGOID_LINES.values():
            for line in lines:
                fields = {field for _, field, _, _ in Formatter().parse(line) if field}
                self.assertTrue(fields <= {"toy", "food", "dream", "system", "body", "ship", "to"}, line)
        pet = self.stage(1)
        hatchling.observe(self.state, {"event": "FSDJump", "StarSystem": "Sol", "FuelLevel": 20}, 100 * HOUR + 1)
        pet = hatchling.view(self.state, 100 * HOUR + 1)["pet"]
        pool = hatchling_chatter._pool(pet, "arrive")
        self.assertTrue(pool)
        self.assertTrue(any("Sol" in line for line in pool))
        line = hatchling_chatter.chatter(self.state, pet, "arrive", 100 * HOUR + 1, "chatty", rng=random.Random(3), force=True)
        self.assertTrue(line)
        self.assertIsNone(hatchling_chatter.chatter(self.state, pet, "arrive", 100 * HOUR + 2, "off", force=True))

    def test_play_cue_is_shared_without_masking_fresh_danger(self):
        self.stage(1)
        now = 100 * HOUR + 2
        self.assertTrue(hatchling.act(self.state, "play", {"game": "limpet", "won": True}, now)[0])
        pet = hatchling.view(self.state, now)["pet"]
        self.assertEqual(pet["cue"]["kind"], "game_limpet")
        self.assertEqual(build_hatchling_model({"pet": pet}, now)["cue"], pet["cue"])
        hatchling.observe(self.state, {"event": "UnderAttack"}, now + 2)
        self.assertTrue(hatchling.act(self.state, "play", {"game": "thargon", "won": True}, now + 3)[0])
        self.assertEqual(self.state["pet"]["cue"]["kind"], "danger")

    def test_deck_and_overlay_receive_the_same_identity_and_activity_inputs(self):
        import time
        now = time.time()
        state = hatchling.new_state()
        hatchling.act(state, "hatch", {"species": "thargoid", "name": "Ember"}, now - HOUR)
        hatchling.advance(state, now)
        state["pet"]["reaction"] = "excited"
        state["pet"]["reaction_at"] = now - 120
        config = {"hatchling_look": "pet", "hatchling_roam": "wide"}

        class Deck(DashboardGamesMixin):
            def __init__(self):
                self.config = config

            def _hatchling_state(self):
                return state

            def _hatchling_music(self):
                return False

            def _hatchling_watcher_seen(self, side=None):
                return None

        deck_pet = Deck()._games_live("hatchling")["pet"]
        overlay = build_hatchling_model(hatchling.view(state, time.time()), time.time(),
                                        options=hatchling_overlay_options(config))
        for key in ("name", "born", "species", "kind", "stage", "form", "needs", "traits", "toys", "tricks", "place", "world", "music", "music_started_at", "cue", "reaction"):
            self.assertEqual(deck_pet[key], overlay[key], key)
        self.assertEqual(deck_pet["options"], overlay["options"])


class FoundlingBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def open_overlay(self):
        page = self.browser.new_page(viewport={"width": 294, "height": 189})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))
        stub = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
                "window.renderPet = options.render; return {rerender() {}}; }};")

        def serve(route):
            file = WEB / urlsplit(route.request.url).path.lstrip("/")
            if not file.is_file():
                return route.fulfill(status=404, body="")
            if file.name == "overlay-client.js":
                return route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + stub)
            return route.fulfill(path=str(file))

        page.route("http://foundling.test/**", serve)
        page.goto("http://foundling.test/hatchling/index.html")
        page.wait_for_function("Boolean(window.Hatchling3D && window.HatchlingArt && window.renderPet)")
        return page

    def test_3d_and_fallback_draw_each_stage_transparently(self):
        page = self.open_overlay()
        rows = page.evaluate("""() => {
          const canvas = document.createElement('canvas');
          canvas.width = canvas.height = 320;
          const ctx = canvas.getContext('2d');
          const result = [];
          for (const stage of ['egg', 'hatchling', 'juvenile', 'adult']) {
            const pet = {species: 'thargoid', stage, needs: {mood: 85}};
            for (const mode of ['three', 'fallback']) {
              ctx.clearRect(0, 0, 320, 320);
              const args = {x: 160, y: 160, size: 150, t: 1.25, look: [.3, -.2], aura: false};
              const ok = mode === 'three' ? Hatchling3D.draw(ctx, pet, args) : (HatchlingArt.draw(ctx, pet, args), true);
              const pixels = ctx.getImageData(0, 0, 320, 320).data;
              let visible = 0;
              for (let i = 3; i < pixels.length; i += 4) if (pixels[i] > 0) visible++;
              result.push({stage, mode, ok, visible, corner: pixels[3]});
            }
          }
          return result;
        }""")
        self.assertTrue(all(row["ok"] and row["visible"] > 300 and row["corner"] == 0 for row in rows), rows)
        self.assertEqual(len({row["visible"] for row in rows if row["mode"] == "three"}), 4, rows)

    def test_the_overlay_names_the_growth_stage(self):
        page = self.open_overlay()
        page.evaluate("""() => renderPet({theme: {}, effects: {}, hatchling: {
          name: 'Ember', species: 'thargoid', stage: 'juvenile', stage_name: 'Thargon', title: 'THARGOID FOUNDLING',
          needs: {hunger: 80, mood: 80, clean: 80, health: 80, energy: 80}, options: {look: 'panel'}}})""")
        self.assertIn("THARGON", page.locator("#title").inner_text())

    def test_petting_poses_each_companion_without_squashing_its_body(self):
        page = self.open_overlay()
        rows = page.evaluate("""() => {
          const kinds = [
            {species:'larva'}, {species:'bot'}, {species:'thargoid'},
            {species:'sample', kind:'bacterium'}, {species:'sample', kind:'tubus'},
            {species:'sample', kind:'fungoida'}
          ];
          return kinds.map(kind => {
            const canvas=document.createElement('canvas'); canvas.width=canvas.height=320;
            const ctx=canvas.getContext('2d');
            const pet={...kind, stage:'juvenile', needs:{mood:85}};
            const args={x:160, y:160, size:150, t:1.25, aura:false, shadow:false};
            Hatchling3D.draw(ctx, pet, {...args, activity:{name:'idle'}});
            function draw(elapsed, squash) {
              ctx.clearRect(0,0,320,320);
              const ok=Hatchling3D.draw(ctx, pet, {...args, squash, activity:{name:'pat',t:elapsed}});
              const body=Hatchling3D.views.get(canvas).model.body;
              return {ok, scale:[body.scale.x,body.scale.y], pixels:Array.from(ctx.getImageData(0,0,320,320).data)};
            }
            const start=draw(0,0), pose=draw(.9,1);
            let changed=0;
            for (let i=0; i<start.pixels.length; i+=4)
              if (Math.abs(start.pixels[i+3]-pose.pixels[i+3]) > 12 ||
                  Math.abs(start.pixels[i]-pose.pixels[i]) > 12) changed++;
            return {kind, ok:start.ok && pose.ok, scales:[start.scale,pose.scale], changed};
          });
        }""")
        for row in rows:
            self.assertTrue(row["ok"], row)
            self.assertEqual(row["scales"][0], row["scales"][1], row)
            self.assertGreater(row["changed"], 30, row)


if __name__ == "__main__":
    unittest.main()
