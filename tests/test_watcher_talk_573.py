"""The Watcher's command conversation, without a model or real microphone."""
import json
from pathlib import Path
import unittest
from urllib.parse import unquote, urlsplit

from voidcompass.core.themes import resolve_theme

ROOT = Path(__file__).resolve().parents[1]


class TalkPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f"Playwright Chromium is unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1600, "height": 1050})
        self.page.emulate_media(reduced_motion="reduce")
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.live = {"stage": "idle", "level": 0}

        def serve(route, _request=None):
            path = unquote(urlsplit(route.request.url).path)
            target = ROOT / "web" / path.lstrip("/")
            if path == "/test.html":
                route.fulfill(content_type="text/html", body="<!doctype html><head>"
                    "<link rel='stylesheet' href='/dashboard/styles.css'>"
                    "<link rel='stylesheet' href='/dashboard/watcher.css'></head>"
                    "<body style='margin:0;padding:12px;box-sizing:border-box'>"
                    "<div id='watcher-workspace'></div></body>")
            elif path == "/api/data/listen":
                route.fulfill(content_type="application/json", body=json.dumps(self.live))
            elif target.is_file():
                route.fulfill(path=str(target))
            else:
                route.fulfill(status=404, body="")

        self.page.route("http://watcher.test/**", serve)
        self.page.goto("http://watcher.test/test.html")
        self.load_module()
        self.data = {"enabled": True, "talk": {"orb_on": True, "talk": [
            {"at": 1793300000, "you": "Where are we?", "it": "We are in Sol."},
            {"at": 1793300001, "you": "Open the galaxy map", "it": "The galaxy map.", "voice": True}]},
            "listen": {"enabled": True, "installed": True, "mode": "hold", "stage": "idle"}}
        self.render()
        self.page.click('[data-watcher-tab="now"]')
        self.addCleanup(self.page.close)
        self.addCleanup(lambda: self.assertEqual(self.errors, []))

    def load_module(self):
        self.page.evaluate("""async () => {
          const module = await import('/dashboard/watcher.js');
          window.__sent = [];
          window.__ui = {byId: id => document.getElementById(id),
            escapeHtml: value => String(value ?? '').replace(/[&<>"']/g, ch =>
              ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[ch])),
            numeric: value => String(value ?? 0), showToast: () => {}, apiUrl: path => path,
            command: async (kind, payload) => { window.__sent.push(payload); return true; }};
          window.__render = data => module.renderWatcher(data, window.__ui);
        }""")

    def render(self):
        self.page.evaluate("data => __render(data)", self.data)

    def commands(self):
        return self.page.evaluate("() => __sent")

    def wait_for_operation(self, operation):
        self.page.wait_for_function("op => __sent.some(row => row.operation === op)", arg=operation)

    def test_talk_replaces_model_and_library_controls(self):
        self.assertEqual(self.page.locator("[data-watcher-tab]").all_text_contents(),
                         ["BRIDGE", "STORY", "YOU", "LOG", "SETUP"])
        self.assertEqual(self.page.locator('[data-watcher-panel="mind"], [data-watcher-panel="library"]').count(), 0)
        self.assertEqual(self.page.locator("#watcher-mind-on, #watcher-mind-model, #watcher-mind-download, [data-mind-vote]").count(), 0)
        self.assertTrue(self.page.is_visible("#watcher-talk-log"))
        self.assertIn("SPOKEN", self.page.inner_text("#watcher-talk-log"))
        self.assertIn("ask about your ship", self.page.inner_text(".talk-console footer .watcher-note"))
        setup = self.page.inner_text(".talk-setup").casefold()
        for word in ("settings › voice", "microphone", "talk key", "keyboard bindings", "sequences"):
            self.assertIn(word, setup)

    def test_typed_command_and_reply_round_trip_without_rebuilding_input(self):
        text = self.page.locator("#watcher-talk-text")
        text.fill("Open the system map")
        text.press("Enter")
        self.wait_for_operation("talk")
        self.assertEqual(self.commands()[-1], {"page": "watcher", "operation": "talk", "text": "Open the system map"})
        self.assertEqual(text.input_value(), "")
        self.data["talk"]["talk"].append({"at": 1793300002, "you": "Open the system map", "it": "The system map."})
        self.render()
        self.render()
        self.assertEqual(self.page.locator(".talk-turn").count(), 3)
        self.assertEqual(self.page.locator(".talk-it p").last.text_content(), "The system map.")
        self.assertEqual(self.page.inner_text("#watcher-talk-state"), "3 EXCHANGED")

    def test_forget_talk_and_example_commands(self):
        self.page.click('[data-talk-prompt="Open the galaxy map"]')
        self.wait_for_operation("talk")
        self.assertEqual(self.commands()[-1]["text"], "Open the galaxy map")
        self.page.click("#watcher-talk-forget")
        self.wait_for_operation("talk_forget")
        self.assertEqual(self.commands()[-1], {"page": "watcher", "operation": "talk_forget"})
        self.data["talk"]["talk"] = []
        self.render()
        self.assertEqual(self.page.locator(".talk-turn").count(), 0)
        self.assertIn("Say hello", self.page.inner_text("#watcher-talk-log"))

    def test_mic_hold_emits_start_and_stop(self):
        mic = self.page.locator("#watcher-talk-mic")
        self.assertTrue(mic.is_visible())
        self.assertTrue(mic.is_enabled())
        self.live = {"stage": "listening", "level": 0.12}
        box = mic.bounding_box()
        self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        self.page.mouse.down()
        self.wait_for_operation("listen_start")
        self.page.mouse.up()
        self.wait_for_operation("listen_stop")
        self.assertEqual([row["operation"] for row in self.commands()], ["listen_start", "listen_stop"])

    def test_mic_tap_and_transcription_stage_keep_the_text_and_focus(self):
        self.data["listen"]["mode"] = "tap"
        self.render()
        self.page.click("#watcher-talk-mic")
        self.wait_for_operation("listen_start")
        self.live = {"stage": "listening", "level": 0.15}
        self.data["listen"]["stage"] = "listening"
        self.render()
        self.page.click("#watcher-talk-mic")
        self.wait_for_operation("listen_stop")
        text = self.page.locator("#watcher-talk-text")
        text.fill("Gear down when I am ready")
        text.evaluate("node => node.dataset.original = 'same-input'")
        text.focus()
        self.data["listen"]["stage"] = "hearing"
        self.render()
        self.assertTrue(self.page.is_disabled("#watcher-talk-mic"))
        self.assertEqual(self.page.inner_text("#watcher-talk-state"), "HEARING YOU…")
        self.assertEqual(text.input_value(), "Gear down when I am ready")
        self.assertEqual(text.get_attribute("data-original"), "same-input")
        self.assertEqual(self.page.evaluate("() => document.activeElement.id"), "watcher-talk-text")

    def test_unavailable_mic_and_orb_do_not_offer_talk_actions(self):
        self.data["listen"].update(enabled=False, installed=False)
        self.render()
        self.assertTrue(self.page.locator("#watcher-talk-mic").is_hidden())
        self.data["listen"].update(enabled=True, installed=True)
        self.data["talk"]["orb_on"] = False
        self.render()
        for selector in ("#watcher-talk-mic", "#watcher-talk-send", "#watcher-talk-text", "[data-talk-prompt]"):
            self.assertTrue(self.page.locator(selector).first.is_disabled())
        self.assertIn("Switch it on in Overlay Studio", self.page.inner_text("#watcher-talk-note"))
        self.assertEqual(self.commands(), [])

    def test_old_stored_tabs_open_the_command_conversation(self):
        for old_tab, destination in {"mind": "now", "library": "now", "talk": "now", "voice": "settings", "overview": "now", "together": "you"}.items():
            with self.subTest(old_tab=old_tab):
                self.page.evaluate("tab => localStorage.setItem('voidcompass.watcherTab', tab)", old_tab)
                self.page.reload()
                self.load_module()
                self.render()
                self.assertEqual(self.page.locator(f'[data-watcher-tab="{destination}"]').get_attribute("aria-selected"), "true")
                self.assertTrue(self.page.locator(f'[data-watcher-panel="{destination}"]').is_visible())

    def test_transcript_opens_at_newest_reply_and_wraps_in_another_theme(self):
        self.data["talk"]["talk"] = [{"at": 1793300000 + index, "you": f"Question {index}",
                                      "it": f"The ship's answer, number {index}."} for index in range(20)]
        _, palette = resolve_theme("Elite Orange")
        self.page.evaluate("palette => Object.entries(palette).forEach(([key,value]) => document.documentElement.style.setProperty('--' + key.replaceAll('_', '-'), value))", palette)
        self.render()
        self.page.wait_for_function("() => { const log = document.getElementById('watcher-talk-log'); return log.scrollHeight - log.scrollTop - log.clientHeight < 4; }")
        self.assertEqual(self.page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()"), palette["accent"])
        for width in (1600, 850):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 950})
                console = self.page.locator(".talk-console").bounding_box()
                send = self.page.locator("#watcher-talk-send").bounding_box()
                self.assertLessEqual(send["x"] + send["width"], console["x"] + console["width"])
                self.assertLessEqual(self.page.evaluate("() => document.documentElement.scrollWidth"), width)


if __name__ == "__main__":
    unittest.main()
