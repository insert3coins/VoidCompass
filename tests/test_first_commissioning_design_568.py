"""The new commander's first welcome and four-step setup (5.6.8)."""
import copy
from pathlib import Path
import unittest

from voidcompass.core import themes
from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
from tests.test_dashboard_overview_visuals import overview_state

ROOT = Path(__file__).resolve().parents[1]


def setup_state():
    data = overview_state()
    data['app'] = {'version': '5.6.8'}
    data['boot'] = {'active': True, 'progress': .1, 'status': 'FIRST COMMISSIONING'}
    data['onboarding'] = {
        'active': True, 'session': 1, 'theme': 'Void Cyan',
        'themes': copy.deepcopy(themes.BUILTIN_THEMES), 'journal_path': 'C:/Saved Games/Elite Dangerous',
        'adaptive_command_enabled': True, 'overlay_enabled': True, 'overlay_mouse_passthrough': True,
        'probing': False, 'error': '', 'submitting': False,
        'probe': {'status': 'ok', 'auto': False, 'path': 'C:/Saved Games/Elite Dangerous',
                  'journals': 1200, 'commander': 'Jameson', 'ship': 'Krait Phantom', 'ship_name': 'The Long Way Home',
                  'system': 'Shinrarta Dezhra', 'first': '2020-09-10', 'latest': '2026-10-29',
                  'live_status': True, 'message': 'Journals found. Void Compass reads them; it never changes them.'},
    }
    return data


class FirstCommissioningDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def open(self, width=1440, height=900):
        self.commands = []
        self.server = HtmlDashboardServer(ROOT/'web/dashboard', image_root=ROOT/'assets/images',
            command_callback=lambda payload: self.commands.append(payload) or True)
        self.addCleanup(self.server.stop)
        self.data = setup_state()
        self.server.publish(self.data)
        self.context = self.browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce')
        self.addCleanup(self.context.close)
        page = self.context.new_page()
        self.errors = []
        page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(self.errors, []))
        page.goto(self.server.url)
        page.wait_for_selector('#commissioning:not([hidden])')
        page.wait_for_function("async () => (await import('/setup.js')).setupPresentationState().watcher?.renderer === 'three'")
        return page

    def step(self, page, name):
        page.locator(f'.setup-rail [data-setup-go="{name}"]').click()
        page.wait_for_selector(f'[data-step="{name}"]:not([hidden])')

    def test_the_four_steps_keep_choices_editable_and_submit_only_once(self):
        page = self.open()
        self.assertEqual(page.locator('.setup-brand').inner_text(), 'VOID COMPASS')
        page.locator('#setup-next').click()
        self.assertIn('LINKED', page.locator('#setup-probe').inner_text())
        self.assertIn('Jameson', page.locator('#setup-probe').inner_text())
        page.locator('#setup-next').click()
        page.locator('.setup-toggle:has(#onboarding-overlays)').click()
        page.locator('.setup-theme:has(input[value="Elite Orange"])').click()
        self.assertEqual(page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()"),
                         themes.BUILTIN_THEMES['Elite Orange']['accent'])
        page.locator('#setup-next').click()
        self.assertIn('CMDR Jameson', page.locator('#setup-launch-intro').inner_text())
        self.assertIn('Elite Orange', page.locator('#setup-summary').inner_text())
        page.get_by_role('button', name='Edit journal folder', exact=True).click()
        self.assertTrue(page.locator('[data-step="journal"]').is_visible())
        self.assertEqual(page.input_value('#onboarding-journal'), self.data['onboarding']['journal_path'])
        self.step(page, 'cockpit')
        self.assertFalse(page.locator('#onboarding-overlays').is_checked())
        self.assertTrue(page.locator('input[name="setup-theme"][value="Elite Orange"]').is_checked())
        self.step(page, 'launch')
        page.evaluate("""() => {
          const form=document.getElementById('onboarding-form');
          form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
          form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
        }""")
        page.wait_for_timeout(150)
        submitted = [item for item in self.commands if item.get('action') == 'onboarding_submit']
        self.assertEqual(len(submitted), 1)
        self.assertEqual(submitted[0]['ui_theme_name'], 'Elite Orange')
        self.assertFalse(submitted[0]['overlay_enabled'])
        self.assertTrue(submitted[0]['overlay_mouse_passthrough'])
        self.assertTrue(page.locator('#onboarding-submit').is_disabled())
        self.server.publish(self.data)
        page.wait_for_timeout(100)
        self.assertTrue(page.locator('#onboarding-submit').is_disabled(), 'an older snapshot cannot reopen a pending submission')
        self.data['onboarding']['error'] = 'Use a full journal folder path.'
        self.server.publish(self.data)
        page.wait_for_selector('#onboarding-error:text-is("Use a full journal folder path.")')
        self.assertTrue(page.locator('[data-step="journal"]').is_visible())
        self.assertFalse(page.locator('#onboarding-journal').is_disabled())

    def test_changed_folders_do_not_reuse_the_previous_commanders_confirmation(self):
        page = self.open()
        self.step(page, 'journal')
        page.evaluate("window.keptFact=document.querySelector('#setup-probe dd')")
        self.server.publish(self.data)
        page.wait_for_timeout(150)
        self.assertTrue(page.evaluate("window.keptFact === document.querySelector('#setup-probe dd')"))
        page.fill('#onboarding-journal', 'D:/Other Commander/Journals')
        self.assertIn('FOLDER CHANGED', page.locator('#setup-probe').inner_text())
        self.assertNotIn('Jameson', page.locator('#setup-probe').inner_text())
        self.assertNotIn('Jameson', page.locator('#setup-profile-name').inner_text())
        self.step(page, 'launch')
        self.assertIn('D:/Other Commander/Journals', page.locator('#setup-summary').inner_text())
        self.assertNotIn('Jameson', page.locator('#setup-summary').inner_text())
        self.step(page, 'journal')
        page.fill('#onboarding-journal', '')
        self.assertIn('FOLDER CHANGED', page.locator('#setup-probe').inner_text())
        self.step(page, 'launch')
        self.assertNotIn(self.data['onboarding']['journal_path'], page.locator('#setup-summary').inner_text())
        # Empty/missing journal folders are explained and do not trap a new pilot.
        self.step(page, 'journal')
        page.locator('#setup-check').click()
        self.data['onboarding'].update(journal_path='', probe={
            'status': 'empty', 'auto': True, 'path': 'C:/Saved Games/Elite Dangerous',
            'message': 'The folder exists but holds no journals yet.'})
        self.server.publish(self.data)
        self.step(page, 'journal')
        page.locator('#setup-probe').get_by_text('NO JOURNALS YET', exact=True).wait_for()
        self.assertTrue(page.locator('#setup-next').is_enabled())

    def test_all_steps_fit_short_narrow_windows_and_larger_text(self):
        page = self.open()
        self.data['onboarding']['probe']['commander'] = 'A Commander With A Very Long Display Name'
        self.data['onboarding']['probe']['ship_name'] = 'A Rather Long Name For A Ship Travelling Across The Galaxy'
        self.server.publish(self.data)
        for width, height, scale, minimum in ((1440,900,100,0), (1280,720,135,14),
                                               (960,480,120,12), (480,760,135,14)):
            page.set_viewport_size({'width': width, 'height': height})
            page.evaluate("""async ([scale,minimum]) => {
              (await import('/text-size.js')).applyTextSize(scale,minimum);
            }""", [scale, minimum])
            for name in ('welcome', 'journal', 'cockpit', 'launch'):
                with self.subTest(step=name, width=width, scale=scale):
                    self.step(page, name)
                    layout = page.evaluate("""() => {
                      const step=document.querySelector('.setup-step:not([hidden])');
                      const box=document.querySelector('.setup-actions').getBoundingClientRect();
                      return {stepFits:step.scrollWidth<=step.clientWidth+1,
                        shellFits:document.getElementById('boot').scrollWidth<=innerWidth+1,
                        actionsFit:box.left>=0&&box.right<=innerWidth+1&&box.bottom<=innerHeight+1,
                        buttonsFit:[...document.querySelectorAll('.setup-actions button')]
                          .filter(node=>node.getClientRects().length).every(node=>{
                            const b=node.getBoundingClientRect();return b.left>=box.left&&b.right<=box.right+1&&b.bottom<=innerHeight+1;
                          })};
                    }""")
                    self.assertTrue(all(layout.values()), layout)

    def test_the_welcome_watcher_respects_stillness_and_releases_its_renderer(self):
        page = self.open()
        snapshot = "async () => (await import('/setup.js')).setupPresentationState()"
        page.wait_for_timeout(250)
        first = page.evaluate(snapshot)
        page.wait_for_timeout(200)
        self.assertEqual(first['watcher']['frames'], page.evaluate(snapshot)['watcher']['frames'])
        self.step(page, 'journal')
        self.assertIsNone(page.evaluate(snapshot)['watcher'])
        self.step(page, 'welcome')
        page.wait_for_function("async () => (await import('/setup.js')).setupPresentationState().watcher?.renderer==='three'")
        self.data['onboarding']['active'] = False
        self.data['boot'].update(progress=.6, status='RESTORING RECENT JOURNAL')
        self.server.publish(self.data)
        page.wait_for_selector('#commissioning', state='hidden')
        self.assertIsNone(page.evaluate(snapshot)['watcher'])
        self.assertTrue(page.locator('#boot-loader').is_visible())


if __name__ == '__main__':
    unittest.main()
