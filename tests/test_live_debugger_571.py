"""5.7.1: the live debugger. The app keeps its recent log in memory (secrets
scrubbed) and answers the Local API's /debug routes from this PC only, even
with its main thread stuck; tools/debug watches it from outside."""

from http.client import HTTPConnection
import importlib.util
import json
import logging
import os
from pathlib import Path
import socket
import threading
import time
import unittest

from voidcompass.core import debug_tap
from voidcompass.dashboard.dashboard_api_mixin import _secret_values
from voidcompass.services import local_api
from voidcompass.services.local_api import ApiError, LocalApi, _Request

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def debugger_module():
    spec = importlib.util.spec_from_file_location("void_debugger", ROOT / "tools" / "debug" / "void_debugger.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LogRingTests(unittest.TestCase):
    def setUp(self):
        debug_tap.install()
        self.addCleanup(debug_tap.set_verbose, False)
        self.since = debug_tap.records(10**12)["seq"]
        self.logger = logging.getLogger("voidcompass.test.debugger")

    def lines(self, **kwargs):
        return [row["text"] for row in debug_tap.records(self.since, **kwargs)["records"]
                if row["name"] == "voidcompass.test.debugger"]

    def test_secrets_are_scrubbed_as_lines_arrive(self):
        previous = debug_tap.secret_values
        self.addCleanup(setattr, debug_tap, "secret_values", previous)
        debug_tap.secret_values = lambda: ["my-own-inara-key-123"]
        debug_tap._secrets = ((), 0.0)
        self.logger.warning("EDSM https://www.edsm.net/api?apiKey=ABC123&commanderName=Jameson")
        self.logger.warning("posting to https://discord.com/api/webhooks/1/abcdef and Bearer tok.en-1")
        self.logger.warning("sent my-own-inara-key-123 to Inara")
        text = " ".join(self.lines())
        for secret in ("ABC123", "abcdef", "tok.en-1", "my-own-inara-key-123"):
            self.assertNotIn(secret, text)
        self.assertIn("apiKey=<hidden>&commanderName=Jameson", text)
        self.assertIn("<hidden webhook>", text)

    def test_debug_lines_only_while_verbose_and_never_on_the_console(self):
        import io
        stream = io.StringIO()
        console = logging.StreamHandler(stream)
        logging.getLogger().addHandler(console)
        self.addCleanup(logging.getLogger().removeHandler, console)
        self.logger.debug("quiet")
        self.assertEqual(self.lines(), [])
        self.assertGreater(debug_tap.set_verbose(True, 60), 50)
        self.logger.debug("now kept")
        self.assertEqual(self.lines(), ["now kept"])
        self.assertNotIn("now kept", stream.getvalue(), "the console keeps INFO")
        debug_tap._verbose_until = time.time() - 1
        self.assertEqual(debug_tap.verbose(), 0, "it ends by itself")
        self.assertEqual(logging.getLogger().level, debug_tap._quiet_level, "back where it was")
        self.assertLessEqual(debug_tap.set_verbose(True, 10**6), debug_tap.VERBOSE_MAX_S, "15 minutes at most")

    def test_levels_text_and_tracebacks(self):
        # The app logs at INFO; a test run's root logger may sit at WARNING.
        self.logger.setLevel(logging.INFO)
        self.addCleanup(self.logger.setLevel, logging.NOTSET)
        self.logger.info("an ordinary line")
        try:
            raise ValueError("a body with no BodyID")
        except ValueError:
            self.logger.exception("Scan handling failed")
        self.assertEqual(len(self.lines(level="ERROR")), 1)
        self.assertIn("ValueError: a body with no BodyID", self.lines(level="ERROR")[0])
        self.assertEqual(self.lines(text="ORDINARY"), ["an ordinary line"])

    def test_threads_and_the_process(self):
        stop = threading.Event()
        worker = threading.Thread(target=stop.wait, name="debugger-test-worker", daemon=True)
        worker.start()
        self.addCleanup(stop.set)
        threads = debug_tap.threads(stacks=True)
        self.assertEqual(threads[0]["name"], "MainThread", "the main thread first")
        row = next(row for row in threads if row["name"] == "debugger-test-worker")
        self.assertIn("wait", row["where"])
        self.assertTrue(row["stack"])
        process = debug_tap.process()
        self.assertEqual(process["pid"], os.getpid())
        if os.name == "nt":
            self.assertGreater(process["working_set_mb"], 1)
            self.assertGreater(process["memory_mb"], 1)
            self.assertLessEqual(process["memory_mb"], process["working_set_mb"], "its own pages are part of its working set")
            self.assertIn("cpu_s", process)


class Provider:
    def api_debug(self):
        return {"deck": {"ui_queue": 2}}


class DebugRouteTests(unittest.TestCase):
    def setUp(self):
        debug_tap.install()
        self.addCleanup(debug_tap.set_verbose, False)

    def serve(self, api):
        port = free_port()
        self.assertTrue(api.configure(enabled=True, port=port))
        self.addCleanup(api.stop)
        return port

    def call(self, port, path, method="GET", body=None):
        connection = HTTPConnection("127.0.0.1", port, timeout=10)
        self.addCleanup(connection.close)
        payload = json.dumps(body).encode() if body is not None else None
        connection.request(method, f"/api/v1{path}", body=payload,
                           headers={"Content-Type": "application/json"} if payload else {})
        response = connection.getresponse()
        return response.status, json.loads(response.read().decode("utf-8"))

    def test_the_snapshot_log_and_verbose_switch(self):
        port = self.serve(LocalApi(Provider(), version="test"))
        status, body = self.call(port, "/debug")
        self.assertEqual(status, 200)
        self.assertEqual(body["main_thread"], "free")
        self.assertEqual(body["app"], {"deck": {"ui_queue": 2}})
        self.assertEqual(body["process"]["pid"], os.getpid())
        self.assertIn("MainThread", [row["name"] for row in body["threads"]])
        self.assertIsInstance(body["ui_heartbeat_s"], float)
        logging.getLogger("voidcompass.test.debugger").warning("seen by the debugger")
        status, body = self.call(port, f"/debug/log?since={body['log_seq']}&level=WARNING")
        self.assertIn("seen by the debugger", [row["text"] for row in body["records"]])
        status, body = self.call(port, "/debug/verbose", "POST", {"on": True, "seconds": 60})
        self.assertEqual(status, 200)
        self.assertGreater(body["verbose_s"], 50)
        self.assertEqual(self.call(port, "/debug/verbose", "POST", {"on": False})[1]["verbose_s"], 0)

    def test_a_stuck_main_thread_still_answers(self):
        api = LocalApi(Provider(), run_on_main=lambda task: True, version="test")  # never runs the task
        port = self.serve(api)
        started = time.monotonic()
        status, body = self.call(port, "/debug")
        self.assertEqual(status, 200)
        self.assertEqual(body["main_thread"], "busy")
        self.assertNotIn("app", body)
        self.assertTrue(body["threads"])
        self.assertLess(time.monotonic() - started, local_api.MAIN_THREAD_TIMEOUT_S, "a short wait, not the usual one")

    def test_this_pc_only(self):
        api = LocalApi(Provider(), version="test")
        with self.assertRaises(ApiError) as caught:
            api._debug(_Request({}, {}, "192.168.1.20"))
        self.assertEqual(caught.exception.status, 403)
        for handler in (api._debug_log, api._debug_verbose):
            with self.assertRaises(ApiError):
                handler(_Request({}, {}, "192.168.1.20"))

    def test_every_setting_that_is_a_secret(self):
        found = _secret_values({"edsm_api_key": "K1", "inara_apikey": "K2", "theme": "dark",
                                "carriers": [{"discord_webhook_url": "https://discord.com/api/webhooks/9/x"}],
                                "raven": {"token": "T3", "name": "Raven"}, "empty_token": ""})
        self.assertEqual(sorted(found), sorted(["K1", "K2", "https://discord.com/api/webhooks/9/x", "T3"]))


class AppViewTests(unittest.TestCase):
    def test_the_app_view_with_the_real_parts(self):
        """The real api_debug, dispatcher, mind and model wrapper (a stand-in
        provider hid a UI-queue bug that failed every call in the app)."""
        from voidcompass.core.ui_dispatcher import ApplicationDispatcher
        from voidcompass.dashboard.dashboard_api_mixin import DashboardApiMixin
        from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
        from voidcompass.overlays.watcher_mind import WatcherMind

        root = type("Root", (), {"call_later": lambda self, ms, callback: None})()
        Deck = type("Deck", (DashboardApiMixin, DashboardWatcherVoiceMixin), {})
        deck = Deck.__new__(Deck)
        deck.config = {"edsm_api_key": "SECRET-KEY", "heartbeat_personality": "stoic"}
        deck.ui_dispatcher = ApplicationDispatcher(root)
        deck.ui_dispatcher.post(lambda: None)
        deck._ui_post = lambda callback, *args, key=None, **kwargs: callback(*args, **kwargs)
        mind = WatcherMind(None, deck.config)
        mind.llm = deck._watcher_llm()
        self.addCleanup(mind.llm.close)
        deck.heartbeat_hud = type("Hud", (), {"mind": mind, "_stalled": False})()
        deck._music_status = {"playing": True, "track_id": "a1", "position": 12.0, "duration": 300.0}
        deck.current_sys, deck.current_gui_focus = "Sol", 6
        view = deck.api_debug()
        self.assertEqual(view["deck"]["ui_queue"], 1)
        self.assertEqual(view["game"]["system"], "Sol")
        self.assertEqual(view["watcher"]["mind"]["nature"], "stoic")
        self.assertEqual(view["watcher"]["llm"]["stage"], "off")
        self.assertTrue(view["music"]["playing"])
        self.assertNotIn("SECRET-KEY", json.dumps(view))
        api = LocalApi(deck, version="test")
        port = free_port()
        self.assertTrue(api.configure(enabled=True, port=port))
        self.addCleanup(api.stop)
        connection = HTTPConnection("127.0.0.1", port, timeout=10)
        self.addCleanup(connection.close)
        connection.request("GET", "/api/v1/debug")
        answer = json.loads(connection.getresponse().read().decode("utf-8"))
        self.assertEqual(answer["main_thread"], "free")
        self.assertEqual(answer["app"]["watcher"]["mind"]["nature"], "stoic")


class MindDebugTests(unittest.TestCase):
    def test_the_watcher_says_what_it_is_doing(self):
        from voidcompass.overlays import watcher_llm, watcher_mind

        mind = watcher_mind.WatcherMind(None, {})
        state = mind.debug_state()
        for key in ("thought", "waiting", "feeling", "memory", "nature", "thoughts", "question", "in_danger"):
            self.assertIn(key, state)
        llm = watcher_llm.WatcherLLM(lambda: {})
        self.addCleanup(llm.close)
        debug = llm.debug_state()
        self.assertEqual((debug["stage"], debug["queued"], debug["recent"]), ("off", 0, []))


class ToolTests(unittest.TestCase):
    def test_it_serves_its_page_and_reads_the_process_tree(self):
        debugger = debugger_module()
        page = (ROOT / "tools" / "debug" / "web" / "index.html").read_text(encoding="utf-8")
        for needle in ('id="event-rows"', 'id="log-rows"', 'id="thread-rows"', 'id="mind"', 'id="procs"', "debugger.js"):
            self.assertIn(needle, page)
        script = (ROOT / "tools" / "debug" / "web" / "debugger.js").read_text(encoding="utf-8")
        for route in ("/debug", "/debug/log", "/debug/verbose", "/events/stream", "/overlays", "/local/procs"):
            self.assertIn(route, script)
        server = debugger._Server(("127.0.0.1", 0), debugger.handler_for(debugger.Debugger(None)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        port = server.server_address[1]
        for path, kind in (("/", "text/html"), ("/debugger.js", "text/javascript"), ("/debugger.css", "text/css")):
            connection = HTTPConnection("127.0.0.1", port, timeout=5)
            connection.request("GET", path)
            response = connection.getresponse()
            response.read()
            connection.close()
            self.assertEqual(response.status, 200, path)
            self.assertTrue(response.getheader("Content-Type").startswith(kind), path)
        connection = HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request("GET", "/../void_debugger.py")
        self.assertEqual(connection.getresponse().status, 404, "only its own page's files")
        connection.close()
        if os.name == "nt":
            sampler = debugger.Sampler()
            first = sampler.sample(os.getpid())
            self.assertEqual(first["processes"][0]["pid"], os.getpid())
            self.assertIsNone(first["processes"][0]["cpu"], "CPU needs two looks")
            looked = sampler.sample(os.getpid())
            second = looked["processes"][0]
            self.assertIsNotNone(second["cpu"])
            # Task Manager's CPU: the time, with the cores' boost over base clock.
            self.assertGreaterEqual(looked["boost"], 0.5)
            self.assertAlmostEqual(second["cpu"], round(second["cpu_time"] * looked["boost"], 1), delta=0.11)
            self.assertLessEqual(second["memory_mb"], second["working_mb"], "Task Manager's figure, not the working set")

    def test_its_own_window_never_a_browser(self):
        source = (ROOT / "tools" / "debug" / "void_debugger.py").read_text(encoding="utf-8")
        for browser in ("webbrowser", "msedge", "--app="):
            self.assertNotIn(browser, source)
        self.assertIn('webview.create_window("Void Compass Debugger"', source)

    def test_never_in_the_build(self):
        build = (ROOT / "tools" / "build.py").read_text(encoding="utf-8")
        self.assertNotIn("void_debugger", build)
        self.assertNotIn("tools/debug", build.replace("\\", "/"))
