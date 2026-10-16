"""5.5.7 the Local API: /api/v1 for the commander's own tools.

The server (services/local_api.py) is held to its promises: no key, but only
this PC (unless other devices are allowed) and only local pages from a browser;
read-only when control is off; secrets blanked; events by polling and by
stream. The dashboard's side (dashboard_api_mixin.py) answers from the app,
and api.md documents every endpoint the server has.
"""

from http.client import HTTPConnection
import json
from pathlib import Path
import re
import socket
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

from voidcompass.core import config as config_module
from voidcompass.dashboard.dashboard_api_mixin import API_HIDDEN_PAGES, DashboardApiMixin
from voidcompass.services.local_api import (
    PROVIDER_CALLS, ApiError, EventBus, LocalApi, _local_host, _local_origin, _loopback, markdown_page, redact,
)
from voidcompass.overlays.watcher_mind import WatcherMind

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Provider:
    def __init__(self):
        self.said = []

    def api_status(self):
        return {"version": "test", "edsm_api_key": "SECRET", "nested": {"carrier_discord_webhook_url": "https://x"}}

    def api_voice_say(self, text):
        self.said.append(text)
        return {"spoken": True}

    def api_journal_folder(self):
        return self.folder

    def api_overlay(self, overlay_id):
        raise ApiError(404, f"No overlay called {overlay_id}")


class ServerCase(unittest.TestCase):
    def setUp(self):
        self.provider = Provider()
        self.api = LocalApi(self.provider, version="test")
        self.port = free_port()
        self.assertTrue(self.api.configure(enabled=True, port=self.port))
        self.addCleanup(self.api.stop)

    def call(self, path, method="GET", body=None, raw=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        self.addCleanup(connection.close)
        sent = dict(headers or {})
        payload = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if payload is not None:
            sent["Content-Type"] = "application/json"
        connection.request(method, f"/api/v1{path}", body=payload, headers=sent)
        response = connection.getresponse()
        data = response.read().decode("utf-8")
        try:
            return response.status, json.loads(data)
        except ValueError:
            return response.status, data


class LocalApiServerTests(ServerCase):
    def test_no_key_is_needed(self):
        for path in ("", "/ping", "/docs", "/status"):
            self.assertEqual(self.call(path)[0], 200, path)
        self.assertEqual(self.call("/voice/say", "POST", {"text": "hello"})[0], 200)

    def test_websites_can_neither_read_nor_drive_it(self):
        for origin in ("https://example.com", "http://192.168.1.5", "http://evil.localhost.example.com"):
            status, body = self.call("/status", headers={"Origin": origin})
            self.assertEqual(status, 403, origin)
            self.assertIn("this PC", body["error"]["message"])
        # A body-less POST is a "simple" request that skips the preflight: refused too.
        self.assertEqual(self.call("/voice/stop", "POST", headers={"Origin": "https://example.com"})[0], 403)
        # DNS rebinding: a website's own name pointed at 127.0.0.1.
        self.assertEqual(self.call("/status", headers={"Host": f"rebind.example.com:{self.port}"})[0], 403)
        self.assertEqual(self.call("/status", headers={"Host": f"localhost:{self.port}"})[0], 200)

    def test_local_pages_obs_and_localhost_may(self):
        for origin in ("null", "http://absolute", "http://localhost:8080", "http://127.0.0.1:5500", "http://[::1]:3000"):
            self.assertTrue(_local_origin(origin), origin)
        for origin in ("https://example.com", "http://192.168.1.5", "file", ""):
            self.assertFalse(_local_origin(origin), origin)
        self.assertTrue(_local_origin("http://192.168.1.5", allow_lan=True), "network pages once devices are allowed")
        self.assertFalse(_local_origin("https://example.com", allow_lan=True))
        self.assertTrue(_local_host("127.0.0.1") and _local_host("localhost") and _local_host("::1"))
        self.assertFalse(_local_host("192.168.1.5"))
        self.assertTrue(_local_host("192.168.1.5", allow_lan=True) and _local_host("mypc.local", allow_lan=True))
        self.assertFalse(_local_host("rebind.example.com", allow_lan=True))

    def test_secrets_never_leave_the_app(self):
        status, body = self.call("/status")
        self.assertEqual(status, 200)
        self.assertEqual(body["edsm_api_key"], "<hidden>")
        self.assertEqual(body["nested"]["carrier_discord_webhook_url"], "<hidden>")
        self.assertEqual(body["version"], "test")

    def test_routes_methods_and_bodies(self):
        self.assertEqual(self.call("/nowhere")[0], 404)
        self.assertEqual(self.call("/voice/say")[0], 405, "say is a POST")
        self.assertEqual(self.call("/voice/say", "POST", raw=b"not json")[0], 400)
        self.assertEqual(self.call("/voice/say", "POST", raw=b"[1, 2]")[0], 400)
        self.assertEqual(self.call("/voice/say", "POST", {"text": "   "})[0], 400)
        self.assertEqual(self.call("/voice/say", "POST", raw=b"x" * (65 * 1024))[0], 413)
        status, body = self.call("/voice/say", "POST", {"text": "Carrier  departs\nsoon"})
        self.assertEqual((status, body), (200, {"spoken": True}))
        self.assertEqual(self.provider.said, ["Carrier departs soon"])
        status, body = self.call("/overlays/nothing")
        self.assertEqual(status, 404)
        self.assertEqual(self.call("/music")[0], 501, "a provider without music says so")

    def test_read_only_refuses_every_change(self):
        self.api.configure(enabled=True, port=self.port, allow_control=False)
        self.assertEqual(self.call("/voice/say", "POST", {"text": "hello"})[0], 403)
        self.assertEqual(self.provider.said, [])
        self.assertEqual(self.call("/status")[0], 200, "reading still works")

    def test_only_this_pc_unless_other_devices_are_allowed(self):
        self.assertTrue(_loopback("127.0.0.1"))
        self.assertTrue(_loopback("::1"))
        self.assertFalse(_loopback("192.168.1.20"))
        self.assertFalse(_loopback("not an address"))
        self.assertEqual(self.api.state()["lan"], False)

    def preflight(self, origin):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        self.addCleanup(connection.close)
        connection.request("OPTIONS", "/api/v1/voice/say", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        response = connection.getresponse()
        response.read()
        return response

    def test_local_browser_pages_may_call_it(self):
        response = self.preflight("null")
        self.assertEqual(response.status, 204)
        self.assertEqual(response.getheader("Access-Control-Allow-Origin"), "null")
        self.assertIn("Content-Type", response.getheader("Access-Control-Allow-Headers"))
        response = self.preflight("https://example.com")
        self.assertEqual(response.status, 403)
        self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))

    def test_the_index_lists_every_endpoint(self):
        status, body = self.call("")
        self.assertEqual(status, 200)
        paths = {(row["method"], row["path"]) for row in body["endpoints"]}
        self.assertIn(("POST", "/api/v1/overlays/{overlay}/toggle"), paths)
        self.assertIn(("GET", "/api/v1/dashboard/pages/{page}"), paths)
        self.assertTrue(all(row["control"] == (row["method"] == "POST") for row in body["endpoints"]))

    def test_events_wait_for_something_new(self):
        self.api.publish("journal", {"event": "FSDJump", "StarSystem": "Sol"})
        self.api.publish("journal", {"event": "Scan", "BodyName": "Earth"})
        status, body = self.call("/journal/events?event=FSDJump")
        self.assertEqual([row["event"] for row in body["events"]], ["FSDJump"])
        seq = body["seq"]
        threading.Timer(.4, lambda: self.api.publish("thought", {"text": "Hm."})).start()
        start = time.monotonic()
        status, body = self.call(f"/events?since={seq}&wait=5&types=thought")
        self.assertLess(time.monotonic() - start, 3, "answered when the thought came, not at the timeout")
        self.assertEqual([(row["type"], row["data"]["text"]) for row in body["events"]], [("thought", "Hm.")])
        self.assertEqual(self.call(f"/events?since={body['seq']}&wait=0")[1]["events"], [])

    def test_the_stream_sends_each_event_as_it_happens(self):
        self.api.publish("journal", {"event": "Docked", "StationName": "Jameson Memorial"})
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        self.addCleanup(connection.close)
        connection.request("GET", "/api/v1/events/stream?since=0&types=journal")
        response = connection.getresponse()
        self.assertEqual(response.getheader("Content-Type").split(";")[0], "text/event-stream")
        lines = [response.fp.readline().decode().strip() for _ in range(6)]
        self.assertIn("event: journal", lines)
        data = json.loads(next(line for line in lines if line.startswith("data: "))[6:])
        self.assertEqual(data["data"]["StationName"], "Jameson Memorial")

    def test_history_reads_the_journal_files_newest_first(self):
        with tempfile.TemporaryDirectory() as folder:
            self.provider.folder = folder
            older = Path(folder, "Journal.2026-10-01T100000.01.log")
            newer = Path(folder, "Journal.2026-10-02T100000.01.log")
            older.write_text("\n".join(json.dumps(row) for row in (
                {"timestamp": "2026-10-01T10:00:00Z", "event": "FSDJump", "StarSystem": "A"},
                {"timestamp": "2026-10-01T11:00:00Z", "event": "Scan", "BodyName": "A 1"})) + "\n", encoding="utf-8")
            newer.write_text("\n".join(json.dumps(row, separators=(",", ":")) for row in (
                {"timestamp": "2026-10-02T10:00:00Z", "event": "FSDJump", "StarSystem": "B"},
                {"timestamp": "2026-10-02T11:00:00Z", "event": "FSDJump", "StarSystem": "C"})) + "\n",
                encoding="utf-8")
            body = self.call("/journal/history?event=FSDJump")[1]
            self.assertEqual([row["StarSystem"] for row in body["events"]], ["C", "B", "A"])
            body = self.call("/journal/history?event=FSDJump&after=2026-10-02T10:30:00Z")[1]
            self.assertEqual([row["StarSystem"] for row in body["events"]], ["C"])
            files = self.call("/journal/files")[1]["files"]
            self.assertEqual([row["name"] for row in files], [newer.name, older.name])

    def test_settings_start_restart_and_stop_it(self):
        self.assertTrue(self.api.running)
        moved = free_port()
        self.assertTrue(self.api.configure(enabled=True, port=moved))
        self.port = moved
        self.assertEqual(self.call("/ping")[0], 200, "listening on the new port")
        self.assertTrue(self.api.configure(enabled=False, port=moved))
        self.assertFalse(self.api.running)
        with socket.socket() as taken:
            taken.bind(("127.0.0.1", 0))
            taken.listen(1)
            busy = taken.getsockname()[1]
            self.assertFalse(self.api.configure(enabled=True, port=busy))
            self.assertIn(str(busy), self.api.state()["error"])


class LocalApiPieceTests(unittest.TestCase):
    def test_redaction_reaches_every_depth(self):
        clean = redact({"inara_api_key": "abc", "list": [{"token": "t", "name": "Sol"}], "api_key": ""})
        self.assertEqual(clean, {"inara_api_key": "<hidden>", "list": [{"token": "<hidden>", "name": "Sol"}],
                                 "api_key": ""})

    def test_status_writes_with_nothing_new_are_dropped(self):
        bus = EventBus()
        bus.publish("status", {"Flags": 1})
        bus.publish("status", {"Flags": 1})
        bus.publish("status", {"Flags": 2})
        bus.publish("nonsense", {})
        self.assertEqual([row["data"]["Flags"] for row in bus.since(0)], [1, 2])

    def test_the_docs_page_reads_well(self):
        page = markdown_page("# Title\n\nSome `code` and **bold**.\n\n## Part\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
                             "```\nGET /api/v1 <x>\n```\n\n- one\n- two\n", "T")
        self.assertIn('<h2 id="part">Part</h2>', page)
        self.assertIn('<a href="#part">Part</a>', page, "a menu of the sections")
        self.assertIn("<td>1</td>", page)
        self.assertIn("GET /api/v1 &lt;x&gt;", page, "code is escaped")
        self.assertIn("<code>code</code>", page)
        self.assertIn("<li>two</li>", page)

    def test_api_md_documents_every_endpoint(self):
        docs = (ROOT / "api.md").read_text(encoding="utf-8")
        api = LocalApi(object())
        for row in api.endpoints():
            path = row["path"].replace("{overlay}", "{id}")
            if "{" in path and "|" in path:
                # /journal/{status|cargo|...}: each named on its own.
                stem, names = path.split("{", 1)
                for name in names.rstrip("}").split("|"):
                    self.assertIn(f"`{stem}{name}`", docs, name)
                continue
            self.assertIn(f"`{path}`", docs, path)

    def test_it_ships_with_the_app(self):
        build = (ROOT / "tools" / "build.py").read_text(encoding="utf-8")
        packager = (ROOT / "tools" / "release_packager.py").read_text(encoding="utf-8")
        self.assertIn('"api.md"', build)
        self.assertIn('"API.md"', packager)


class Dashboard(DashboardApiMixin):
    """Just enough of the app for the API's side of it."""

    _OWN_OPACITY_CHOICES = (0, 100, 90, 80, 70, 60, 50, 40)

    def __init__(self):
        self.config = {"overlay_opacity_percent": 100, "survey_status_overlay_enabled": True,
                       "survey_status_hud_x": 30, "survey_status_hud_y": 520}
        self.root = SimpleNamespace()
        self.toggled, self.moved, self.faded, self.feed = [], [], [], []
        self.current_sys = "---"
        self.current_docked = True
        self.voice_on = False
        self.toast_hud = None
        self.heartbeat_hud = None

    def _persist_config(self):
        pass

    def _html_overlay_records(self):
        return [{"id": "survey_status_hud", "x": self.config["survey_status_hud_x"],
                 "y": self.config["survey_status_hud_y"], "width": 420, "height": 340,
                 "enabled": bool(self.config["survey_status_overlay_enabled"]), "shown": True,
                 "own_opacity": self.config.get("own", 0), "hide_on_maps": True}]

    def _html_overlay_toggle(self, attr):
        self.toggled.append(attr)
        self.config["survey_status_overlay_enabled"] = not self.config["survey_status_overlay_enabled"]
        return True

    def _html_overlay_position(self, attr, x, y, persist=False):
        self.moved.append((attr, x, y, persist))
        self.config["survey_status_hud_x"], self.config["survey_status_hud_y"] = x, y
        return True

    def _set_overlay_own_opacity(self, attr, percent):
        self.faded.append(percent)
        self.config["own"] = percent
        return True

    def _html_workspace(self, page):
        return {"page": page, "ready": True, "data": {"systems": {"Sol", "Achenar"}}}

    def _watcher_voice_on(self):
        return self.voice_on

    def add_event_feed_entry(self, tag, message, severity="INFO"):
        self.feed.append((tag, message, severity))


class DashboardApiTests(unittest.TestCase):
    def test_the_real_dashboard_answers_every_call(self):
        from voidcompass.dashboard.dashboard import MainDashboard

        missing = [name for name in PROVIDER_CALLS if not callable(getattr(MainDashboard, name, None))]
        self.assertEqual(missing, [])

    def test_location_and_pages(self):
        app = Dashboard()
        self.assertEqual(app.api_location()["system"], "", "no system yet, not '---'")
        self.assertTrue(app.api_location()["docked"])
        self.assertEqual(sorted(app.api_page("explore")["data"]["systems"]), ["Achenar", "Sol"])
        for page in API_HIDDEN_PAGES:
            with self.assertRaises(ApiError) as caught:
                app.api_page(page)
            self.assertEqual(caught.exception.status, 403, page)
        with self.assertRaises(ApiError) as caught:
            app.api_page("nowhere")
        self.assertEqual(caught.exception.status, 404)

    def test_the_whole_deck_never_carries_settings_or_tools(self):
        app = Dashboard()
        server = SimpleNamespace(_snapshot_json="")
        app.root._voidcompass_html_dashboard_runtime = SimpleNamespace(server=server)
        for page in API_HIDDEN_PAGES:
            server._snapshot_json = json.dumps({"page": page, "workspace": {"page": page, "ready": True,
                                                                            "data": {"journal_path": "C:\\x"}}})
            self.assertEqual(app.api_dashboard()["workspace"], {"page": page, "ready": False, "shared": False})
        server._snapshot_json = json.dumps({"workspace": {"page": "explore", "ready": True, "data": {"a": 1}}})
        self.assertEqual(app.api_dashboard()["workspace"]["data"], {"a": 1})

    def test_overlays_switch_move_and_fade_by_either_id(self):
        app = Dashboard()
        row = app.api_set_overlay("survey", {"enabled": False, "x": 100, "y": 200, "opacity": 73})
        self.assertEqual(app.toggled, ["survey_status_hud"])
        self.assertEqual(app.moved, [("survey_status_hud", 100, 200, True)])
        self.assertEqual(app.faded, [70], "the nearest of Studio's own choices")
        self.assertEqual((row["id"], row["enabled"], row["x"], row["opacity"]), ("survey", False, 100, 70))
        app.api_set_overlay("survey_status_hud", {"enabled": False})
        self.assertEqual(app.toggled, ["survey_status_hud"], "already off: nothing to switch")
        app.api_toggle_overlay("survey")
        self.assertEqual(len(app.toggled), 2)
        with self.assertRaises(ApiError):
            app.api_set_overlay("nothing", {"enabled": True})

    def test_switched_off_features_say_where_to_switch_them_on(self):
        app = Dashboard()
        for call in (lambda: app.api_notify("Hi"), lambda: app.api_voice_say("Hi"),
                     lambda: app.api_watcher_thought("Hi")):
            with self.assertRaises(ApiError) as caught:
                call()
            self.assertEqual(caught.exception.status, 409)
        app.toast_hud = SimpleNamespace(pushed=[], push=lambda *args, **kwargs: app.toast_hud.pushed.append(args))
        app.api_notify("CARRIER", "Jump soon", "warn", 10)
        self.assertEqual(app.toast_hud.pushed, [("CARRIER", "Jump soon")])

    def test_the_feed_takes_a_line(self):
        app = Dashboard()
        app.api_add_feed("bot", "Hello", "success")
        self.assertEqual(app.feed, [("BOT", "Hello", "OK")])

    def test_the_watcher_shows_a_relayed_thought(self):
        with tempfile.TemporaryDirectory() as folder:
            mind = WatcherMind(Path(folder, "memory.json"), {})
            app = Dashboard()
            redraws = []
            app.heartbeat_hud = SimpleNamespace(mind=mind, _redraw=lambda: redraws.append(1))
            answer = app.api_watcher_thought("Chat says [[hi|hello]] ⟦o7⟧", "from chat", speak=False)
            self.assertEqual(answer["heading"], "FROM CHAT")
            self.assertEqual(answer["text"], "Chat says [hi|hello] o7", "no markup slips through")
            self.assertEqual(redraws, [1])
            thought = mind.current()
            self.assertEqual((thought["topic"], thought["kind"]), ("relay", "relay"))
            self.assertEqual(mind.spoken_words(thought), thought["text"], "said whole, if spoken")
            self.assertEqual(mind.relay("Quiet.")["heading"], "RELAYED")

    def test_a_relayed_thought_is_spoken_only_when_asked(self):
        from voidcompass.overlays.heartbeat_hud import HeartbeatHUD

        hud = HeartbeatHUD.__new__(HeartbeatHUD)
        hud.config = {"watcher_voice_level": "important"}
        hud.mind = SimpleNamespace(voice_active=True)
        hud.voice_listener = lambda words, key: True
        self.assertTrue(hud._speaks({"topic": "relay", "speak": True, "importance": 3}))
        self.assertFalse(hud._speaks({"topic": "relay", "speak": False, "importance": 3}))

    def test_a_relayed_thought_speaks_unless_told_not_to(self):
        api = LocalApi(SimpleNamespace(api_watcher_thought=lambda text, heading, speak: {"speak": speak}))
        ask = lambda body: api._thought(SimpleNamespace(body=body))
        self.assertTrue(ask({"text": "Hello"})["speak"], "the voice follows when it's on")
        self.assertTrue(ask({"text": "Hello", "speak": True})["speak"])
        self.assertFalse(ask({"text": "Hello", "speak": False})["speak"])


class DocsPageTests(unittest.TestCase):
    def test_sections_cards_tabs_and_exchanges(self):
        page = markdown_page(
            "# API\n\nIntro.\n\n<!-- group: Start here -->\n\n## Quick\n\n**PowerShell**\n\n```powershell\nirm x\n```\n\n"
            "**Python** (pip)\n\n```python\nprint(1)\n```\n\n### Live events\n\n<!-- group: Reference -->\n\n"
            "## Live events\n\n| Method | Path | What it does |\n|---|---|---|\n| GET | `/api/v1/events` | Since `seq` |\n\n"
            "```http\nGET /api/v1/events?wait=5\n```\n\n```json\n{\"seq\": 1}\n```\n\n**Example: a bot** (Python)\n\n"
            "```python\nwhile True: pass\n```\n", "T")
        self.assertIn('<section class="doc" data-section="overview"', page)
        self.assertIn('<h1 id="overview">API</h1>', page)
        self.assertIn('<h6>Start here</h6><a href="#overview">Overview</a><a href="#quick">Quick</a>', page)
        self.assertIn('<h6>Reference</h6><a href="#live-events">Live events</a>', page)
        self.assertIn('<h3 id="quick-live-events">', page, "an h3 never takes an h2's address")
        self.assertIn('<h2 id="live-events">Live events</h2>', page)
        self.assertIn('<article class="endpoint" id="get-api-v1-events" data-method="GET" data-path="/api/v1/events">', page)
        self.assertIn('<div class="tab" data-label="PowerShell">', page)
        self.assertIn('<p class="tab-note">pip</p>', page)
        self.assertIn('<div class="exchange">', page)
        self.assertIn('<span class="kicker">Example</span><b>a bot</b><small>Python</small>', page)
        self.assertIn('<pre data-lang="python">', page)
        self.assertIn(".endpoint", page.split("<style>", 1)[1], "the docs stylesheet is inlined")
        self.assertNotIn("</script", page.split("<script>", 1)[1].rsplit("</script>", 1)[0], "the script can't end early")

    def test_no_key_anywhere_in_the_reference(self):
        docs = (ROOT / "api.md").read_text(encoding="utf-8")
        for word in ("YOUR_KEY", "Bearer", "X-Api-Key", "?key=", "COPY KEY", "NEW KEY", "| 401 |"):
            self.assertNotIn(word, docs, word)
        self.assertIn("### No key needed", docs)

    def test_obs_has_its_own_section(self):
        docs = (ROOT / "api.md").read_text(encoding="utf-8")
        obs = docs.split("## OBS Studio", 1)[1].split("\n## ", 1)[0]
        for piece in ("### Browser source widgets", "**Now playing**", "**Session tally**", "EventSource(",
                      "Text (GDI+)", "obsws_python", "set_current_program_scene", "save_replay_buffer", "Local file"):
            self.assertIn(piece, obs, piece)


    def test_discord_has_its_own_section(self):
        docs = (ROOT / "api.md").read_text(encoding="utf-8")
        discord = docs.split("## Discord", 1)[1].split("\n## ", 1)[0]
        for piece in ("### Webhook: your game, posted", "### Bot: commands for your server", "WEBHOOK = ",
                      "app_commands", "@bot.tree.command", "/watcher/thought", "OWNER", "allowed_mentions"):
            self.assertIn(piece, discord, piece)
        for block in re.findall(r"```python\n(.*?)```", docs.replace("\r\n", "\n"), re.S):
            compile(block, "api.md example", "exec")


class DocsPageBrowserTests(ServerCase):
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
        super().setUp()
        self.page = self.browser.new_page(viewport={"width": 1380, "height": 850})
        self.addCleanup(self.page.close)
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

    def open(self, hash_=""):
        self.page.goto(f"http://127.0.0.1:{self.port}/api/v1/docs{hash_}")
        self.page.wait_for_selector("main.paged")

    def test_one_section_at_a_time(self):
        self.open()
        shown = self.page.locator("section.doc.shown")
        self.assertEqual(shown.count(), 1)
        self.assertEqual(shown.get_attribute("data-section"), "overview")
        self.assertGreater(self.page.locator(".cards .card").count(), 10, "the overview leads everywhere")
        self.page.click(".rail nav a[href='#obs-studio']")
        self.page.wait_for_function("document.querySelector('section.doc.shown').dataset.section === 'obs-studio'")
        self.assertEqual(self.page.locator("section.doc.shown .tab-bar button").count(), 3)
        self.page.click("section.doc.shown .tab-bar button:has-text('Now playing')")
        self.assertTrue(self.page.locator(".tab[data-label='Now playing']").is_visible())
        self.assertFalse(self.page.locator(".tab[data-label='Session tally']").is_visible())
        self.assertIn("OBS Studio", self.page.title())
        self.assertEqual(self.errors, [])

    def test_find_jumps_to_an_endpoint(self):
        self.open()
        self.page.fill("#find", "hide all")
        self.page.wait_for_selector("#results a")
        self.assertIn("/api/v1/overlays/hide-all", self.page.locator("#results a").first.inner_text())
        self.page.press("#find", "Enter")
        self.page.wait_for_function("document.querySelector('section.doc.shown').dataset.section === 'overlays'")
        self.assertEqual(self.errors, [])

    def test_try_answers_in_place_and_the_stream_listens(self):
        self.open("#app-and-status")
        self.page.click("#get-api-v1-status button.try-it")
        self.page.wait_for_selector("#get-api-v1-status .out .st")
        self.assertTrue(self.page.locator("#get-api-v1-status .out .st").inner_text().startswith("200"))
        self.assertIn("<hidden>", self.page.locator("#get-api-v1-status .out pre").inner_text())
        self.page.goto(f"http://127.0.0.1:{self.port}/api/v1/docs#get-api-v1-events-stream")
        self.page.click("#get-api-v1-events-stream button.try-it")
        self.page.click("#get-api-v1-events-stream button.send")
        self.page.wait_for_selector("#get-api-v1-events-stream .feed")
        self.page.wait_for_timeout(400)
        self.api.publish("thought", {"text": "Something stirs."})
        self.page.wait_for_selector("#get-api-v1-events-stream .feed .tx")
        self.assertIn("Something stirs.", self.page.locator("#get-api-v1-events-stream .feed .tx").first.inner_text())
        self.page.wait_for_selector("#live.idle")
        self.assertIn("GAME IDLE", self.page.locator("#live").inner_text())
        self.assertEqual(self.errors, [])


class BgsRouteTests(ServerCase):
    def setUp(self):
        super().setUp()
        self.asked = []
        self.provider.api_bgs_faction = lambda name: self.asked.append(("faction", name)) or {"name": name}
        self.provider.api_bgs_system = lambda address, days: self.asked.append(("system", address, days)) or {}
        self.provider.api_bgs_systems = lambda query, only: self.asked.append(("systems", query, only)) or {}
        self.provider.api_bgs_activity = lambda tick: self.asked.append(("activity", tick)) or {}

    def test_names_addresses_and_parameters(self):
        self.assertEqual(self.call("/bgs/factions/Jameson%20Holdings%20%26%20Co")[0], 200)
        self.assertEqual(self.call("/bgs/systems/3932277478106?days=99999")[0], 200)
        self.assertEqual(self.call("/bgs/systems?query=sol&only=conflicts")[0], 200)
        self.assertEqual(self.call("/bgs/activity?tick=1760605200")[0], 200)
        self.assertEqual(self.asked, [("faction", "Jameson Holdings & Co"), ("system", 3932277478106, 3650),
                                      ("systems", "sol", "conflicts"), ("activity", 1760605200.0)])
        self.assertEqual(self.call("/bgs/systems?only=everything")[0], 400)
        self.assertEqual(self.call("/bgs/activity?tick=yesterday")[0], 400)
        self.assertEqual(self.call("/bgs/systems/Sol")[0], 404, "a system is asked for by its address")

    def test_the_index_names_their_parts(self):
        paths = {row["path"] for row in self.call("")[1]["endpoints"]}
        self.assertIn("/api/v1/bgs/factions/{name}", paths)
        self.assertIn("/api/v1/bgs/systems/{address}", paths)


class BgsApiTests(unittest.TestCase):
    def setUp(self):
        from voidcompass.bgs.store import BgsStore
        from tests.test_bgs import LOS, arrival, play

        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store = BgsStore(str(Path(folder.name) / "bgs.db"))
        self.addCleanup(self.store.close)
        self.store.apply(play(arrival())[0])
        self.store.set_tracked("faction", "Los Services Ltd", True)
        self.los = LOS
        self.app = Dashboard()
        self.app.bgs_store = self.store
        self.app.current_system_address = LOS

    def test_the_overview_whatever_the_deck_shows(self):
        overview = self.app.api_bgs()
        self.assertEqual([row["name"] for row in overview["tracked_factions"]], ["Los Services Ltd"])
        self.assertEqual(overview["current_system"]["system"], "Los")
        self.assertIn("current_label", overview["tick"])
        self.assertIn("alerts", overview)

    def test_factions_systems_conflicts_and_activity(self):
        found = self.app.api_bgs_factions("los")
        self.assertEqual(([row["name"] for row in found["factions"]], found["total"]), (["Los Services Ltd"], 1))
        faction = self.app.api_bgs_faction("Los Services Ltd")
        self.assertEqual(faction["systems"][0]["system"], "Los")
        self.assertIn("alerts", faction)
        with self.assertRaises(ApiError) as caught:
            self.app.api_bgs_faction("Nobody At All")
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.app.api_bgs_systems("", "conflicts")["systems"][0]["system"], "Los")
        system = self.app.api_bgs_system(self.los, 30)
        self.assertEqual((system["system"], system["days"]), ("Los", 30))
        self.assertIn("history", system)
        with self.assertRaises(ApiError) as caught:
            self.app.api_bgs_system(1)
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.app.api_bgs_conflicts()["conflicts"][0]["type"], "election")
        self.assertIn("periods", self.app.api_bgs_activity())

    def test_no_record_yet_says_so(self):
        app = Dashboard()
        with self.assertRaises(ApiError) as caught:
            app.api_bgs()
        self.assertEqual(caught.exception.status, 409)


class SettingsTests(unittest.TestCase):
    def test_one_server_for_the_pc(self):
        self.assertNotIn("api_key", config_module.GLOBAL_ONLY_KEYS, "no key any more")
        for key in ("api_enabled", "api_port", "api_allow_lan", "api_allow_control"):
            self.assertIn(key, config_module.GLOBAL_ONLY_KEYS, key)
            for tuple_name in ("PROFILE_TEXT_SETTINGS", "PROFILE_BOOL_SETTINGS", "PROFILE_VALUE_SETTINGS"):
                self.assertNotIn(key, getattr(config_module, tuple_name), f"{key} in {tuple_name}")

    def test_settings_page_has_the_controls(self):
        app = (ROOT / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        group = re.search(r'settingGroup\("LOCAL API",(.*?)\n', app).group(1)
        for key in ("api_enabled", "api_port", "api_allow_control", "api_allow_lan"):
            self.assertIn(f'key: "{key}"', group, key)
        self.assertIn('data-ws-op="api_open_docs"', group)
        self.assertNotIn("api_key", group)
        server = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard.py").read_text(encoding="utf-8")
        for key in ("api_enabled", "api_port", "api_allow_lan", "api_allow_control"):
            self.assertIn(f'"{key}": ', server, f"{key} saves")


if __name__ == "__main__":
    unittest.main()
