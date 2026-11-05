"""The companion page redesign (5.7.4): switcher, BRIDGE, LOG and SETUP."""
import unittest

from tests import test_watcher_talk_573 as talk


class CompanionPageTests(unittest.TestCase):
    setUpClass = classmethod(talk.TalkPageTests.setUpClass.__func__)
    tearDownClass = classmethod(talk.TalkPageTests.tearDownClass.__func__)
    setUp = talk.TalkPageTests.setUp
    load_module = talk.TalkPageTests.load_module
    render = talk.TalkPageTests.render
    commands = talk.TalkPageTests.commands

    def test_switcher_is_compact_and_in_alphabetical_order(self):
        names = self.page.locator(".companion-switch button b").all_text_contents()
        self.assertEqual(names, ["Aster", "Axiom", "Meridian", "The Watcher"])
        self.assertEqual(self.page.locator(".companion-picker").count(), 0)
        bar = self.page.locator(".companion-bar").bounding_box()
        self.assertLess(bar["height"], 90, "the switcher no longer pushes the page down")
        self.page.click('button[data-companion="meridian"]')
        self.assertIn({"page": "watcher", "operation": "companion_identity", "value": "meridian"}, self.commands())

    def test_bridge_holds_the_display_and_the_conversation_in_the_companions_name(self):
        self.data.update(identity="axiom", companion_name="Axiom", heartbeat={"orb": {"identity": "axiom", "motion": False}})
        self.render()
        self.page.click('[data-watcher-tab="now"]')
        self.assertEqual(self.page.locator("[data-watcher-tab]").all_text_contents()[0], "BRIDGE")
        for selector in ("#watcher-orb", ".talk-console", "#watcher-talk-text", ".watcher-now-story"):
            self.assertTrue(self.page.is_visible(selector), selector)
        self.assertEqual(self.page.inner_text("#watcher-talk-title"), "TALK TO AXIOM")
        self.assertEqual(set(self.page.locator(".talk-it small").all_text_contents()), {"AXIOM"})
        self.assertNotIn("THE WATCHER", self.page.inner_text("#watcher-talk-log"))
        self.assertIn("Ask Axiom", self.page.get_attribute("#watcher-talk-text", "placeholder"))
        self.assertFalse(self.page.is_visible("#watcher-question"), "no empty question card while nothing is asked")
        # Its own role, readings and notes (5.7.4), not the Watcher's.
        self.assertIn("ROLE", self.page.inner_text("#watcher-character"))
        self.assertIn("Survey intelligence", self.page.inner_text("#watcher-character"))
        self.data["deeper"] = {"question": None, "memories": [], "answers": [], "met": [], "notes_title": "OVERNIGHT NOTES",
                               "dreams": [{"at": 1793300000, "text": "Recount complete."}],
                               "feeling": {"trust": "confident", "mood": "steady", "trust_value": 60, "mood_value": 0,
                                           "labels": ["CERTAINTY", "OUTLOOK"], "story": {"title": "The Census", "note": "chapter II of 8"}},
                               "pilgrimage": {"kind": "black_hole", "words": "a black hole", "how": "Any black hole", "asked": True,
                                              "accepted": None, "reached": False}}
        self.render()
        feeling = self.page.inner_text("#watcher-feeling")
        for word in ("CERTAINTY", "OUTLOOK", "STORY", "The Census"):
            self.assertIn(word, feeling)
        self.assertIn("ASKED", self.page.inner_text("#watcher-wish"))
        self.page.click('[data-watcher-tab="you"]')
        self.assertTrue(self.page.is_visible("#watcher-dreams"))
        self.assertIn("OVERNIGHT NOTES", self.page.inner_text(".watcher-card:has(#watcher-dreams) header"))
        self.assertTrue(self.page.is_visible("#watcher-code"), "share codes work for every companion")

    def test_setup_holds_thoughts_voice_and_reset_and_old_tabs_still_land(self):
        self.page.evaluate("() => localStorage.setItem('voidcompass.watcherTab', 'voice')")
        self.page.reload()
        self.load_module()
        self.render()
        self.assertEqual(self.page.get_attribute('[data-watcher-tab="settings"]', "aria-selected"), "true")
        for selector in (".watcher-settings", ".watcher-voice", "#watcher-reset"):
            self.assertTrue(self.page.is_visible(selector), selector)
        self.page.click('[data-watcher-tab="said"]')
        self.assertEqual(self.page.inner_text('[data-watcher-tab="said"]'), "LOG")
        self.assertTrue(self.page.is_visible("#watcher-log"))

    def test_story_tab_shows_the_whole_crew(self):
        from voidcompass.overlays import crew_lore
        memory = {"crew_lore": [["crew_watcher_01", 1793300000]]}
        arcs = [{**crew_lore.arc_page(member, memory if member == "watcher" else {}, {"watcher", "aster"}),
                 "role": "", "flown": member in ("watcher", "aster")} for member in crew_lore.CREW]
        self.data["crew"] = {"arcs": arcs, "told": 1, "total": 24, "flown": 2}
        self.render()
        self.page.click('[data-watcher-tab="story"]')
        self.assertEqual(self.page.locator(".watcher-crew-arc").count(), 4)
        self.assertIn("1 OF 24 TOLD", self.page.inner_text("#watcher-crew-count"))
        watcher = self.page.locator('.watcher-crew-arc[data-crew="watcher"]')
        watcher.locator("summary").first.click()
        self.assertIn("I was here first", watcher.inner_text())
        self.assertIn("Fly with Axiom", watcher.inner_text())
        self.assertIn("NOT YET FLOWN WITH", self.page.locator('.watcher-crew-arc[data-crew="meridian"]').inner_text())

    def test_narrow_layout_has_no_page_overflow(self):
        self.page.set_viewport_size({"width": 390, "height": 900})
        self.page.click('[data-watcher-tab="now"]')
        self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), 391)


if __name__ == "__main__":
    unittest.main()
