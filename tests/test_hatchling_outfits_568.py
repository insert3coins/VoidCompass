"""5.6.8: accessories are fitted, visible Three.js parts on every companion."""
from pathlib import Path
import unittest
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
WEB=ROOT/'web'


class FittedOutfitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def open(self):
        page=self.browser.new_page()
        self.addCleanup(page.close)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        def serve(route):
            path=urlsplit(route.request.url).path
            if path=='/':
                return route.fulfill(content_type='text/html',body='<canvas width="500" height="420"></canvas><script src="/assets/hatchling-art.js"></script><script type="module" src="/assets/hatchling-3d.js"></script>')
            file=WEB/path.lstrip('/')
            route.fulfill(path=str(file)) if file.is_file() else route.fulfill(status=404,body='')
        page.route('http://outfits.test/**',serve)
        page.goto('http://outfits.test/')
        page.wait_for_function('Boolean(window.Hatchling3D)')
        self.addCleanup(lambda:self.assertEqual(errors,[]))
        return page

    def test_all_five_outfits_render_on_all_eight_companion_shapes(self):
        page=self.open()
        result=page.evaluate('''async () => {
          const THREE=await import('/galactic_map/vendor/three.module.min.js');
          const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d');
          const pets=[{species:'larva',stage:'juvenile'},{species:'bot',stage:'juvenile'},
            ...['bacterium','tubus','fungoida'].map(kind=>({species:'sample',kind,stage:'juvenile'})),
            ...['hatchling','juvenile','adult'].map(stage=>({species:'thargoid',stage}))];
          const signature=()=>{const data=ctx.getImageData(0,0,500,420).data;let hash=0,lit=0;for(let i=0;i<data.length;i+=4){hash=(Math.imul(hash,31)+data[i]+data[i+1]*3+data[i+2]*7)>>>0;if(data[i+3]>0)lit++;}return {hash,lit};};
          return pets.map(pet=>{
            const paint=outfit=>{ctx.clearRect(0,0,500,420);return Hatchling3D.draw(ctx,{...pet,outfit,needs:{mood:80}},{x:250,y:260,size:160,t:2.25,look:[.4,0],aura:false});};
            paint('');const naked=signature();
            return ['', 'visor','helmet','charm','scarf','bowtie'].map(outfit=>{
              const ok=paint(outfit),view=Hatchling3D.views.get(canvas),props=view.model.outfit;
              const bounds=new THREE.Box3().setFromObject(props.root);
              return {pet:pet.species+':'+(pet.kind||pet.stage),outfit,ok,...signature(),naked:naked.hash,
                attached:props.root.parent===view.model.body,parts:props.root.children.length,
                fits:!outfit||(bounds.max.y<view.camera.top&&bounds.min.y>view.camera.bottom&&bounds.max.x<view.camera.right&&bounds.min.x>view.camera.left)};
            });
          }).flat();
        }''')
        self.assertEqual(len(result),48)
        for row in result:
            with self.subTest(pet=row['pet'],outfit=row['outfit']):
                self.assertTrue(row['ok'])
                self.assertTrue(row['attached'])
                self.assertTrue(row['fits'],row)
                self.assertGreater(row['lit'],300)
                if row['outfit']:
                    self.assertGreater(row['parts'],0)
                    self.assertNotEqual(row['hash'],row['naked'],'the fitted accessory must appear in the rendered pixels')

    def test_orthrus_claws_fit_the_camera_through_its_animated_poses(self):
        page=self.open()
        result=page.evaluate('''async()=>{
          const THREE=await import('/galactic_map/vendor/three.module.min.js');
          const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d'),rows=[];
          const pet={species:'thargoid',stage:'adult',needs:{mood:80}};
          for(const name of ['', 'pat', 'unfurl', 'stretch', 'dance'])
            for(const style of name==='dance'?['sway','headbang','robot','shuffle','spin']:[''])
              for(const t of [0,.4,.8,1.2,1.6,2.25,4,7]) {
                Hatchling3D.draw(ctx,pet,{x:250,y:260,size:160,t,look:[Math.sin(t),Math.cos(t)],aura:false,
                  shadow:false,activity:{name,style,t,period:.5}});
                const view=Hatchling3D.views.get(canvas),box=new THREE.Box3().setFromObject(view.model.body);
                rows.push({name,style,t,fits:box.min.x>view.camera.left&&box.max.x<view.camera.right
                  &&box.min.y>view.camera.bottom&&box.max.y<view.camera.top});
              }
          return rows;
        }''')
        for row in result:
            with self.subTest(**row):self.assertTrue(row['fits'],row)


if __name__=='__main__':
    unittest.main()
