"""The boot design presents actual startup work around the shared Watcher."""
import copy
from pathlib import Path
import unittest

from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
from tests.test_dashboard_overview_visuals import overview_state

ROOT=Path(__file__).resolve().parents[1]


class BootDesignTests(unittest.TestCase):
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
        server=HtmlDashboardServer(ROOT/'web/dashboard',image_root=ROOT/'assets/images',command_callback=lambda p:True)
        self.addCleanup(server.stop)
        self.server=server
        self.state=overview_state()
        self.state['app']={'version':'5.6.8'}
        self.state['boot']={'active':True,'status':'RESTORING RECENT JOURNAL','detail':'Reading recent flight records',
                            'progress':.8,'events':4286,'eye':'hal','journal_live':False,'overlays_total':19,'overlays_ready':12,
                            'systems':{'profile':'ready','survey':'background','journal':'working','cockpit':'working'}}
        self.state['update']={'checking':True}
        server.publish(self.state)
        context=self.browser.new_context(viewport={'width':1440,'height':900},bypass_csp=True)
        self.addCleanup(context.close)
        page=context.new_page()
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        self.addCleanup(lambda:self.assertEqual(errors,[]))
        page.goto(server.url)
        page.wait_for_function("window.bootScene?.state().orb?.renderer === 'three'")
        page.wait_for_selector('#boot-event-count:text-is("4,286")')
        return page

    def test_centrepiece_and_live_readouts_fit_the_boot_window(self):
        page=self.open()
        self.assertEqual(page.locator('.boot-wordmark').inner_text(),'VOID COMPASS')
        self.assertEqual(page.locator('#boot-overlay-count').inner_text(),'12 / 19 surfaces ready')
        self.assertEqual(page.locator('#boot-survey').inner_text(),'BACKGROUND')
        self.assertEqual(page.evaluate('bootScene.state().orb.base'),page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--red').trim()"))
        for width,height in [(1440,900),(1000,700),(960,480),(480,740)]:
            page.set_viewport_size({'width':width,'height':height})
            geometry=page.evaluate('''() => {
              const boot=document.querySelector('#boot'),eye=document.querySelector('#boot-orb').getBoundingClientRect();
              const facts=document.querySelector('.boot-transmission').getBoundingClientRect();
              return {centre:eye.x+eye.width/2,overflow:boot.scrollWidth>boot.clientWidth,
                factsClear:!facts.height||facts.top>=eye.bottom,
                progress:document.querySelector('.boot-copy').getBoundingClientRect().bottom};
            }''')
            self.assertAlmostEqual(geometry['centre'],width/2,delta=1)
            self.assertFalse(geometry['overflow'])
            self.assertTrue(geometry['factsClear'])
            if width>760:self.assertLess(geometry['progress'],height-30)
        page.locator('.boot-log summary').click()
        self.assertTrue(page.locator('.boot-log').evaluate('el=>el.open'))
        self.assertIn('RESTORING RECENT JOURNAL',page.locator('#boot-log').inner_text())

    def test_update_checks_never_hold_the_handoff_and_cached_states_are_explicit(self):
        page=self.open()
        for update,expected in [({'checking':True},'checking'),({'checked':True},'current'),
                                ({'checked':True,'available':True,'latest_version':'5.6.9'},'available'),
                                ({'checked':True,'error':'Offline'},'offline')]:
            self.state['update']=update
            self.server.publish(self.state)
            page.wait_for_selector(f'#boot-update[data-state="{expected}"]')
        self.state['boot']['systems']['journal']='cached'
        self.state['boot']['status']='JOURNAL LINK OFFLINE'
        self.server.publish(self.state)
        page.wait_for_selector('#boot-journal:text-is("CACHED")')
        self.assertEqual(page.locator('#boot-position-label').inner_text(),'LAST KNOWN SYSTEM')
        self.state['update']={'checking':True}
        self.state['boot'].update(active=False,progress=1)
        self.server.publish(self.state)
        page.wait_for_selector('body.ready',timeout=9000)
        page.wait_for_function('document.querySelector("#boot").hidden')
        self.assertEqual(page.locator('#boot-update').get_attribute('data-state'),'checking')


if __name__=='__main__':
    unittest.main()
