"""5.6.8: deck and overlay share one time-anchored companion life."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SynchronizedLifeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.add_script_tag(path=str(ROOT / "web" / "assets" / "hatchling-life.js"))

    def test_late_view_reconstructs_the_same_activity_and_prop_trajectory(self):
        result = self.page.evaluate("""() => {
          const make = size => HatchlingLife.create({size, range: size * .4, top: size, sync: true});
          const deck = make(330), overlay = make(92), late = make(64);
          const pet = {name:'Pip', species:'larva', stage:'juvenile', needs:{mood:90, energy:80},
            traits:{curious:1}, toys:[{kind:'pebble', label:'a pebble'}], tricks:[], place:'space',
            options:{roam:'short'}, cue:{kind:'game_limpet',at:1000}};
          for (let n=0; n<=300; n++) {
            const now=1000+n/60;
            deck.step(1/60, pet, {now, busy: true});
            if (n%2===0) overlay.step(1/30, pet, {now});
          }
          late.step(.01, pet, {now:1005});
          return [deck.state(), overlay.state(), late.state()];
        }""")
        self.assertTrue(all(row["act"] == "keepy" for row in result), result)
        for key in ("syncKey", "syncSteps", "elapsed", "x", "ball"):
            self.assertEqual(result[0][key], result[1][key], key)
            self.assertEqual(result[0][key], result[2][key], key)

    def test_fresh_journal_cue_preempts_idle_and_view_resume_rejoins(self):
        result = self.page.evaluate("""() => {
          const a = HatchlingLife.create({size:250, sync:true}), b = HatchlingLife.create({size:80, sync:true});
          const pet = {name:'Moss', species:'sample', kind:'tubus', stage:'adult', needs:{mood:80},
            traits:{}, toys:[], tricks:[], place:'space', options:{roam:'short'}};
          a.step(.02, pet, {now:2000}); b.step(.02, pet, {now:2000});
          pet.cue = {kind:'danger', at:2001};
          a.step(.02, pet, {now:2002});
          b.step(.02, pet, {now:2002});
          const immediate = [a.state(), b.state()];
          a.step(.02, pet, {now:2008});
          b.step(.02, pet, {now:2008});
          return {immediate, resumed:[a.state(),b.state()]};
        }""")
        self.assertEqual([row["act"] for row in result["immediate"]], ["hide", "hide"])
        self.assertEqual(result["resumed"][0]["syncKey"], result["resumed"][1]["syncKey"])
        self.assertEqual(result["resumed"][0]["x"], result["resumed"][1]["x"])
        self.assertEqual(result["resumed"][0]["syncSteps"], result["resumed"][1]["syncSteps"])

    def test_idle_and_music_select_the_same_activity_at_same_time(self):
        result = self.page.evaluate("""() => {
          const a = HatchlingLife.create({size:250, sync:true}), b = HatchlingLife.create({size:80, sync:true});
          const pet = {name:'Moss', species:'sample', kind:'tubus', stage:'adult', needs:{mood:80,energy:80},
            traits:{curious:1}, toys:[{kind:'relic',label:'a relic'}], tricks:[], place:'space', options:{roam:'wide'}};
          const out=[];
          for (const now of [3000, 3005, 3015, 3020]) {
            a.step(.02, pet, {now}); b.step(.04, pet, {now}); out.push([a.state(),b.state()]);
          }
          pet.music = true;
          a.step(.02, pet, {now:3060}); b.step(.04, pet, {now:3060});
          out.push([a.state(),b.state()]);
          return out;
        }""")
        for first, second in result:
            self.assertEqual((first["syncKey"], first["act"], first["syncSteps"], first["x"]),
                             (second["syncKey"], second["act"], second["syncSteps"], second["x"]))
        self.assertEqual(result[-1][0]["act"], "dance")

    def test_real_draw_receives_the_same_clock_and_normalized_toy_pose(self):
        result = self.page.evaluate("""() => {
          const calls=[];
          window.Hatchling3D = {draw(ctx, pet, args) {
            calls.push({t:args.t, x:args.x, y:args.y, size:args.size, activity:args.activity,
                        look:args.look, squash:args.squash, lift:args.lift, toys:args.toys});
            return true;
          }};
          const pet = {name:'Pip', species:'larva', stage:'juvenile', needs:{mood:90, energy:80},
            traits:{}, toys:[{kind:'pebble',label:'a pebble'}], tricks:[], place:'space',
            options:{roam:'short'}, cue:{kind:'game_limpet',at:1000}};
          const a=HatchlingLife.create({size:330, sync:true}), b=HatchlingLife.create({size:92, sync:true});
          a.step(.02,pet,{now:1004}); b.step(.02,pet,{now:1004});
          const ca=document.createElement('canvas').getContext('2d'), cb=document.createElement('canvas').getContext('2d');
          a.drawPet(ca,pet,{x:400,y:300,size:330,t:1004});
          b.drawPet(cb,pet,{x:150,y:180,size:92,t:1004});
          return calls;
        }""")
        self.assertEqual(result[0], result[1])
        deck = (ROOT / "web" / "dashboard" / "hatchling.js").read_text(encoding="utf-8")
        overlay = (ROOT / "web" / "hatchling" / "app.js").read_text(encoding="utf-8")
        self.assertIn("seconds = Date.now() / 1000", deck)
        self.assertIn("t: Date.now() / 1000", overlay)

    def test_overlay_sounds_play_live_but_not_when_catching_up(self):
        result = self.page.evaluate("""() => {
          const sounds = [], replaySounds = [];
          const live = HatchlingLife.create({sync:true, onSound: name => sounds.push(name)});
          const late = HatchlingLife.create({sync:true, onSound: name => replaySounds.push(name)});
          const pet = {name:'Pip', species:'larva', stage:'hatchling', needs:{mood:80}, traits:{},
            toys:[], tricks:[], place:'docked', options:{roam:'short'}, cue:{kind:'dock',at:1000}};
          live.step(.01, pet, {now:1000});
          late.step(.01, pet, {now:1005});
          return {sounds, replaySounds};
        }""")
        self.assertIn("chirp", result["sounds"])
        self.assertEqual(result["replaySounds"], [])

    def test_pointer_gaze_does_not_change_the_shared_activity(self):
        result = self.page.evaluate("""() => {
          const calls = [];
          window.Hatchling3D = {draw(ctx, pet, args) { calls.push(args.look); return true; }};
          const a = HatchlingLife.create({size:250, sync:true}), b = HatchlingLife.create({size:90, sync:true});
          const pet = {name:'Pip', species:'larva', stage:'juvenile', needs:{mood:80}, traits:{},
            toys:[], tricks:[], place:'space', options:{roam:'short'}, cue:{kind:'game_limpet',at:1000}};
          a.step(.02, pet, {now:1002}); b.step(.02, pet, {now:1002});
          a.lookAt([.75,-.25], 1);
          const canvas = document.createElement('canvas');
          a.drawPet(canvas.getContext('2d'), pet, {x:125,y:125,size:200,t:1002});
          b.drawPet(canvas.getContext('2d'), pet, {x:125,y:125,size:90,t:1002});
          return {looks:calls, states:[a.state(), b.state()]};
        }""")
        self.assertEqual(result["looks"][0], [.75, -.25])
        self.assertEqual(result["states"][0]["act"], result["states"][1]["act"])
        self.assertEqual(result["states"][0]["ball"], result["states"][1]["ball"])

    def test_music_start_is_shared_audio_reactive_and_journal_cues_take_priority(self):
        result = self.page.evaluate("""() => {
          const first = HatchlingLife.create({size:280, sync:true});
          const second = HatchlingLife.create({size:90, sync:true});
          const pet = {name:'Pip', born:1, species:'larva', stage:'juvenile', needs:{mood:80},
            traits:{}, toys:[], tricks:[], place:'space', options:{roam:'short'}, music:true, music_started_at:1000};
          const bands=Array(32).fill(30);
          for (let n=0; n<30; n++) {
            const now=1000+n*.12;
            first.step(.12,pet,{now}); second.step(.12,pet,{now});
            first.hear(bands,true); second.hear(bands,true);
          }
          const music=[first.state(),second.state()];
          pet.cue={kind:'danger',at:1004};
          first.step(.02,pet,{now:1004.2}); second.step(.02,pet,{now:1004.2});
          return {music, cue:[first.state(),second.state()]};
        }""")
        self.assertEqual([(row["act"], row["dance"]) for row in result["music"]], [("dance", "sway"), ("dance", "sway")])
        self.assertEqual([row["act"] for row in result["cue"]], ["hide", "hide"])

    def test_older_music_payloads_do_not_force_nonstop_dancing(self):
        acts = self.page.evaluate("""() => {
          const life = HatchlingLife.create({sync:true});
          const pet = {name:'Pip', species:'larva', stage:'juvenile', needs:{mood:80, energy:80},
            traits:{}, toys:[], tricks:[], place:'space', options:{roam:'short'}, music:true};
          const result = [];
          for (let n = 0; n < 20; n++) {
            life.step(.02, pet, {now: 3000 + n * 15});
            result.push(life.state().act);
          }
          return result;
        }""")
        self.assertIn("dance", acts)
        self.assertTrue(any(act != "dance" for act in acts), acts)


if __name__ == "__main__":
    unittest.main()
