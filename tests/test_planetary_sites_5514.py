"""5.5.14: Planetary Operations' SITES shows every saved site, grouped by
planet, when you're not on a planet with saved sites (it used to show an
empty planet from the system you were in)."""

import unittest

from tests import test_planetary_page_5512 as base

page_data = base.page_data


def away_from_planets():
    data = page_data()
    data["current_position"] = None
    data["ground"]["on_planet"] = False
    data["system"] = "Ba Po"
    data["sites"] += [
        {"id": 4, "system": "Ba Po", "body": "Ba Po A 1", "name": "Glacier", "latitude": -12.0, "longitude": 88.0, "materials": "Bromellite"},
        {"id": 5, "system": "Wregoe JU-E c25-18", "body": "Wregoe JU-E c25-18 3 a", "name": "Bright vein",
         "latitude": 3.0, "longitude": 4.0, "materials": "Painite, Platinum"},
    ]
    return data


class AllSitesTests(unittest.TestCase):
    setUpClass = classmethod(base.PageTests.setUpClass.__func__)
    tearDownClass = classmethod(base.PageTests.tearDownClass.__func__)
    setUp = base.PageTests.setUp
    tearDown = base.PageTests.tearDown

    def show(self, data):
        self.page.evaluate("data => window.__planet(data)", data)
        self.page.click('[data-po-op="view"][data-view="sites"]')

    def groups(self):
        return self.page.evaluate("() => [...document.querySelectorAll('.po-group')].filter(g => !g.hidden).map(g => g.querySelector('b').textContent)")

    def test_away_from_a_planet_every_site_by_planet(self):
        self.show(away_from_planets())
        self.assertTrue(self.page.inner_text(".po-subtabs button.active").startswith("ALL SITES"))
        self.assertEqual(self.groups(), ["Ba Po / A 1", "Ba Po / C 3", "Wregoe JU-E c25-18 / 3 a"], "this system first, then A to Z")
        self.assertEqual(self.page.locator(".po-group details.po-site").count(), 3)
        self.assertFalse(self.errors, self.errors)

    def test_find_narrows_it_without_losing_your_place(self):
        self.show(away_from_planets())
        self.page.fill("[data-po-site-search]", "painite")
        self.assertEqual(self.groups(), ["Wregoe JU-E c25-18 / 3 a"])
        self.assertTrue(self.page.evaluate("() => document.activeElement.matches('[data-po-site-search]')"))
        self.page.fill("[data-po-site-search]", "nothing like it")
        self.assertTrue(self.page.is_visible("[data-po-no-match]"))

    def test_this_planet_opens_its_own_view(self):
        self.show(away_from_planets())
        self.page.click('[data-po-op="open_planet"] >> nth=1')
        self.assertEqual(self.page.inner_text(".po-subtabs button.active"), "THIS PLANET")
        self.assertEqual(self.page.evaluate("() => document.querySelector('[data-po-planet]').selectedOptions[0].textContent"), "Ba Po / C 3")

    def test_send_to_compass_from_the_list(self):
        self.show(away_from_planets())
        self.page.click("[data-site-navigate='5']")
        self.page.wait_for_timeout(200)
        self.assertIn(("planet-materials", "navigate_site"), [(row.get("page"), row.get("operation")) for row in self.sent])

    def test_on_a_planet_with_sites_it_opens_on_that_planet(self):
        data = page_data()
        data["current_position"].update(system="Ba Po", body="Ba Po C 3")
        self.show(data)
        self.assertEqual(self.page.inner_text(".po-subtabs button.active"), "THIS PLANET")


if __name__ == "__main__":
    unittest.main()
