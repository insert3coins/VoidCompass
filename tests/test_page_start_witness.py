"""The command deck survives, and explains, files lost in its first second.

Some launches lose a burst of the deck's files: stylesheets (a half-styled
deck) or app.js (a frozen boot screen). page-start.js runs before any module,
fetches a lost stylesheet again, reloads once when app.js cannot load, and
reports what the browser saw; the host logs Chromium's error code for each
failed request.
"""

import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from voidcompass.core.diagnostic_logs import TimestampedStream
from voidcompass.core.webview_bootstrap import configure_embedded_navigation
from voidcompass.dashboard.html_dashboard_host import DashboardHost
from voidcompass.dashboard.html_dashboard_runtime import HtmlDashboardRuntime


WEB = Path(__file__).resolve().parents[1] / "web"


class _Receiver:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


class _Core:
    """Enough of CoreWebView2's DevTools surface to drive the witness."""

    def __init__(self):
        self.receivers = {}
        self.calls = []

    def GetDevToolsProtocolEventReceiver(self, name):
        receiver = self.receivers.setdefault(name, _Receiver())
        return SimpleNamespace(DevToolsProtocolEventReceived=receiver)

    def CallDevToolsProtocolMethodAsync(self, method, params):
        self.calls.append((method, params))

    def fire(self, name, **data):
        for handler in self.receivers[name].handlers:
            handler(None, SimpleNamespace(ParameterObjectAsJson=json.dumps(data)))


class HostLogTests(unittest.TestCase):
    def test_host_output_lines_carry_the_time(self):
        target = io.StringIO()
        stream = TimestampedStream(target)
        with patch("voidcompass.core.diagnostic_logs.log_clock", return_value="17:00:54.693"):
            stream.write("Dashboard page recovered\nsecond line\n")
            stream.write("partial ")
            stream.write("line\n\n")
        self.assertEqual(target.getvalue(), "17:00:54.693 Dashboard page recovered\n"
                         "17:00:54.693 second line\n17:00:54.693 partial line\n\n")

    def test_runtime_entries_are_timed_but_the_session_banner_is_not(self):
        runtime = HtmlDashboardRuntime.__new__(HtmlDashboardRuntime)
        runtime._host_log = io.BytesIO()
        runtime._host_log_lock = __import__("threading").Lock()
        with patch("voidcompass.dashboard.html_dashboard_runtime.log_clock", return_value="17:00:55.047"):
            runtime._write_host_log("\n=== Void Compass HTML dashboard host // 2026-09-26 17:00:52 ===")
            runtime._write_host_log("Browser boot frame presented")
        self.assertEqual(runtime._host_log.getvalue().decode("utf-8").splitlines()[1:], [
            "=== Void Compass HTML dashboard host // 2026-09-26 17:00:52 ===",
            "17:00:55.047 Browser boot frame presented",
        ])

    def test_failed_requests_are_logged_with_chromiums_error(self):
        host = DashboardHost("http://127.0.0.1:8765/?token=secret")
        core = _Core()
        self.assertTrue(host.watch_network(SimpleNamespace(CoreWebView2=core)))
        self.assertEqual(core.calls, [("Network.enable", "{}")])
        core.fire("Network.requestWillBeSent", requestId="1",
                  request={"url": "http://127.0.0.1:8765/explore.css"})
        core.fire("Network.requestWillBeSent", requestId="2",
                  request={"url": "http://127.0.0.1:8765/api/events?token=secret&since=4"})
        core.fire("Network.requestWillBeSent", requestId="3",
                  request={"url": "http://127.0.0.1:8765/app.js"})
        with patch("builtins.print") as output:
            core.fire("Network.loadingFailed", requestId="1", errorText="net::ERR_CONNECTION_RESET")
            # A long-poll cut off by a reload is not a failure worth logging.
            core.fire("Network.loadingFailed", requestId="2", errorText="net::ERR_ABORTED", canceled=True)
            core.fire("Network.loadingFinished", requestId="3")
        lines = [call.args[0] for call in output.call_args_list]
        self.assertEqual(lines, ["Dashboard request failed: /explore.css net::ERR_CONNECTION_RESET"])
        self.assertNotIn("secret", "".join(lines))

    def test_ready_hook_runs_after_pywebview_on_success_only(self):
        order = []
        browser_type = type("Browser", (), {
            "on_navigation_start": lambda self, sender, args: None,
            "on_navigation_completed": lambda self, sender, args: None,
            "on_webview_ready": lambda self, sender, args: order.append("pywebview"),
        })
        self.assertTrue(configure_embedded_navigation(SimpleNamespace(EdgeChrome=browser_type)))
        browser = browser_type()
        browser.pywebview_window = SimpleNamespace(
            _voidcompass_after_ready=lambda control: order.append(("hook", control)))
        browser.on_webview_ready("control", SimpleNamespace(IsSuccess=True))
        self.assertEqual(order, ["pywebview", ("hook", "control")])
        order.clear()
        with patch("builtins.print"):
            browser.on_webview_ready("control", SimpleNamespace(IsSuccess=False, InitializationException=None))
        self.assertEqual(order, ["pywebview"])


class PageStartBrowserTests(unittest.TestCase):
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

    def load(self, lose=None, times=1):
        """Open the deck, dropping the first ``times`` requests for ``lose``."""
        page = self.browser.new_page()
        self.addCleanup(page.close)
        reports, lost, loads = [], [], []

        def serve(route, _request=None):
            path = urlsplit(route.request.url).path
            if path == "/":
                loads.append(path)
            if path == "/api/command":
                body = route.request.post_data_json or {}
                if body.get("source") == "page-start":
                    reports.append(body.get("message", ""))
                route.fulfill(content_type="application/json", body='{"accepted":true}')
            elif path == "/api/events":
                route.fulfill(content_type="application/json", body='{"closing":true}')
            elif path == "/api/snapshot":
                route.fulfill(content_type="application/json", body="{}")
            elif lose and path == lose and len(lost) < times:
                lost.append(path)
                route.abort("connectionreset")
            else:
                target = WEB / ("assets" if path.startswith("/assets/") else "dashboard")
                target = target / (path.removeprefix("/assets/").lstrip("/") or "index.html")
                route.fulfill(path=str(target)) if target.is_file() else route.fulfill(status=404, body="")

        page.route("http://deck.test/**", serve)
        page.goto("http://deck.test/?token=t")
        page.wait_for_function("window.__voidcompassDeckStarted === true || document.readyState === 'complete'")
        page.wait_for_timeout(900)
        return page, reports, loads

    def test_a_lost_stylesheet_is_fetched_again(self):
        page, reports, loads = self.load(lose="/explore.css")
        self.assertEqual(len(loads), 1, "a stylesheet never reloads the page")
        self.assertTrue(page.evaluate("window.__voidcompassDeckStarted === true"))
        self.assertTrue(page.evaluate("""() => [...document.styleSheets]
          .some((sheet) => (sheet.href || '').includes('/explore.css?retry=1'))"""))
        self.assertIn("before client start: failed to load /explore.css · fetching again", reports)

    def test_a_lost_client_reloads_the_page_once_and_starts(self):
        page, reports, loads = self.load(lose="/app.js")
        self.assertEqual(len(loads), 2, "one reload, by the page itself")
        self.assertTrue(page.evaluate("window.__voidcompassDeckStarted === true"))
        self.assertIn("before client start: failed to load /app.js · reloading the page", reports)

    def test_a_client_that_cannot_load_reloads_once_then_reports(self):
        page, reports, loads = self.load(lose="/app.js", times=99)
        page.wait_for_timeout(600)
        self.assertEqual(len(loads), 2, "a genuinely broken build must not reload forever")
        summaries = [report for report in reports if report.startswith("client not started")]
        self.assertEqual(len(summaries), 1)
        self.assertIn("/app.js ?", summaries[0])

    def test_a_healthy_page_reports_nothing(self):
        page, reports, loads = self.load()
        self.assertTrue(page.evaluate("window.__voidcompassDeckStarted === true"))
        self.assertEqual((reports, len(loads)), ([], 1))


if __name__ == "__main__":
    unittest.main()
