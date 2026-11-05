"""The boot screen presents the commander's selected companion (5.7.4)."""
import unittest

from tests import test_boot_design_568 as boot_design
from voidcompass.core import companions


class BootCompanionBrowserTests(unittest.TestCase):
    setUpClass = classmethod(boot_design.BootDesignTests.setUpClass.__func__)
    tearDownClass = classmethod(boot_design.BootDesignTests.tearDownClass.__func__)

    def open(self, identity):
        # Reuse the established fixture, then publish the selected companion.
        page = boot_design.BootDesignTests.open(self)
        self.state["boot"]["companion"] = {"identity": identity, "name": companions.NAMES[identity], "accent": "signature",
                                           "motion": True, "focus": "tracking", "liveliness": "standard"}
        self.server.publish(self.state)
        return page

    def test_each_companion_presents_its_own_display(self):
        for identity in ("aster", "axiom", "meridian"):
            with self.subTest(identity=identity):
                page = self.open(identity)
                page.wait_for_function(f"window.bootScene.state().companion === '{identity}'", timeout=20000)
                page.wait_for_function("window.bootScene.state().companionDisplay !== null", timeout=20000)
                found = page.evaluate('''() => {
                  const holder = document.querySelector('#boot-track');
                  const own = holder.querySelector('.aster-instrument, .crew-instrument');
                  return {own: Boolean(own && getComputedStyle(own).display !== 'none'),
                          orbHidden: getComputedStyle(document.querySelector('#boot-orb')).opacity === '0',
                          marked: document.querySelector('#boot').dataset.companion,
                          note: document.querySelector('#boot-journal-note').textContent};
                }''')
                self.assertTrue(found["own"], found)
                self.assertTrue(found["orbHidden"], "the Watcher orb steps aside")
                self.assertEqual(found["marked"], identity)
                self.assertIn(companions.NAMES[identity], found["note"])

    def test_the_watcher_stays_the_default(self):
        page = boot_design.BootDesignTests.open(self)
        self.assertEqual(page.evaluate("window.bootScene.state().companion"), "watcher")
        self.assertEqual(page.evaluate("document.querySelectorAll('#boot-track .aster-instrument, #boot-track .crew-instrument').length"), 0)
        self.assertNotEqual(page.evaluate("getComputedStyle(document.querySelector('#boot-orb')).opacity"), "0")


if __name__ == "__main__":
    unittest.main()
