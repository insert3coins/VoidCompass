"""Regression coverage for shared hatchling movement, patting and speech."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HatchlingLifeFixTests(unittest.TestCase):
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

    def test_boundary_motion_and_late_join_agree(self):
        result = self.page.evaluate("""() => {
          const pet = {name:'Pip', born:1, species:'larva', stage:'juvenile',
            needs:{mood:90,energy:80}, traits:{curious:1}, toys:[], tricks:[],
            place:'space', options:{roam:'wide'}};
          const deck=HatchlingLife.create({size:300,sync:true});
          const overlay=HatchlingLife.create({size:100,sync:true});
          let previous=null, biggest=0, maxDifference=0;
          for (let i=0; i<=1800; i++) {
            const now=3000+i/60;
            deck.step(1/60,pet,{now}); overlay.step(1/60,pet,{now});
            const x=overlay.x;
            if (previous!==null) biggest=Math.max(biggest,Math.abs(x-previous));
            maxDifference=Math.max(maxDifference,Math.abs(deck.x/3-x));
            previous=x;
          }
          const late=HatchlingLife.create({size:100,sync:true});
          late.step(1/60,pet,{now:3030});
          return {biggest,maxDifference,late:late.x,current:overlay.x};
        }""")
        self.assertLess(result["biggest"], 3)
        self.assertAlmostEqual(result["maxDifference"], 0, places=6)
        self.assertAlmostEqual(result["late"], result["current"], places=5)

    def test_new_cue_and_snapshot_do_not_teleport_and_rejoin_late_view(self):
        result = self.page.evaluate("""() => {
          const pet = {name:'Moss', species:'sample', kind:'tubus', stage:'adult',
            needs:{mood:80,energy:80}, traits:{}, toys:[], tricks:[], place:'space', options:{roam:'wide'}};
          const a=HatchlingLife.create({size:100,sync:true});
          let prev=null, biggest=0;
          for (let n=0;n<360;n++) {
            const now=2000+n/60;
            if (n===90) pet.cue={kind:'danger',at:now};
            if (n===180) pet.needs={mood:30,energy:45};
            a.step(1/60,pet,{now});
            if (prev!==null) biggest=Math.max(biggest,Math.abs(a.x-prev));
            prev=a.x;
          }
          const late=HatchlingLife.create({size:100,sync:true});
          late.step(1/60,pet,{now:2000+359/60});
          return {biggest,current:a.x,late:late.x,act:a.act};
        }""")
        self.assertLess(result["biggest"], 5)
        self.assertAlmostEqual(result["current"], result["late"], delta=.01)
        self.assertEqual(result["act"], "hide")

    def test_pat_uses_dedicated_pose_without_body_squash(self):
        result = self.page.evaluate("""() => {
          const poses=[];
          window.Hatchling3D={draw(ctx,pet,args) { poses.push(args); return true; }};
          const pet={name:'Pip',species:'larva',stage:'juvenile',needs:{mood:80},traits:{},
            toys:[],tricks:[],options:{roam:'short'},cue:{kind:'petted',at:1000}};
          const life=HatchlingLife.create({sync:true});
          const ctx=document.createElement('canvas').getContext('2d');
          life.step(1/60,pet,{now:1001});
          life.drawPet(ctx,pet,{x:100,y:100,size:100,t:1001});
          return {act:life.act,pose:poses[0].activity,squash:poses[0].squash};
        }""")
        self.assertEqual(result["act"], "pat")
        self.assertEqual(result["pose"]["name"], "pat")
        self.assertGreater(result["pose"]["t"], 0)
        self.assertEqual(result["squash"], 0)

    def test_speech_is_borderless_wrapped_and_inside_canvas(self):
        result = self.page.evaluate("""() => {
          window.HatchlingArt={tones:()=>({line:'#f80',glow:'#fff',vein:'#fff'})};
          const pet={name:'Pip',species:'larva',stage:'juvenile',needs:{mood:80},traits:{},
            toys:[],tricks:[],options:{roam:'short'},chat:{at:1000,text:
            'A very long transmission from our little travelling companion, with supercalifragilisticexpialidocious in it.'}};
          const life=HatchlingLife.create({size:100,sync:true});
          life.step(1/60,pet,{now:1001});
          const canvas=document.createElement('canvas'); canvas.width=180; canvas.height=100;
          const ctx=canvas.getContext('2d'), lines=[], boxes=[]; let strokes=0;
          const fillText=ctx.fillText.bind(ctx), stroke=ctx.stroke.bind(ctx), roundRect=ctx.roundRect.bind(ctx);
          ctx.fillText=(text,x,y)=>{ const m=ctx.getTransform(); lines.push({text,x:m.e+x*m.a,y:m.f+y*m.d,width:ctx.measureText(text).width*m.a}); fillText(text,x,y); };
          ctx.stroke=()=>{ strokes++; stroke(); };
          ctx.roundRect=(x,y,w,h,r)=>{const m=ctx.getTransform(); boxes.push({x:m.e+x*m.a,y:m.f+y*m.d,w:w*m.a,h:h*m.d}); roundRect(x,y,w,h,r);};
          life.front(ctx,pet,90,75);
          return {lines,boxes,strokes};
        }""")
        self.assertEqual(result["strokes"], 0)
        self.assertGreater(len(result["lines"]), 1)
        self.assertEqual(len(result["boxes"]), 1)
        box = result["boxes"][0]
        self.assertGreaterEqual(box["x"], 0)
        self.assertGreaterEqual(box["y"], 0)
        self.assertLessEqual(box["x"] + box["w"], 180)
        self.assertLessEqual(box["y"] + box["h"], 100)
        for line in result["lines"]:
            self.assertGreaterEqual(line["x"] - line["width"] / 2, 0)
            self.assertLessEqual(line["x"] + line["width"] / 2, 180)
            self.assertTrue(0 <= line["y"] <= 100)


if __name__ == "__main__":
    unittest.main()
