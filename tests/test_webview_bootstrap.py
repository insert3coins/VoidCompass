import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from voidcompass.core.webview_bootstrap import configure_embedded_navigation


class WebviewNavigationTests(unittest.TestCase):
    def test_error_document_disabled_before_navigation_and_patch_is_idempotent(self):
        settings = SimpleNamespace(IsBuiltInErrorPageEnabled=True)
        observed = []

        class Browser:
            def on_navigation_start(self, sender, args):
                observed.append(settings.IsBuiltInErrorPageEnabled)
                return "started"

            def on_navigation_completed(self, sender, args):
                return "completed"

        module = SimpleNamespace(EdgeChrome=Browser)
        self.assertTrue(configure_embedded_navigation(module))
        patched_start = Browser.on_navigation_start
        self.assertTrue(configure_embedded_navigation(module))
        self.assertIs(Browser.on_navigation_start, patched_start)
        browser = Browser()
        browser.webview = SimpleNamespace(CoreWebView2=SimpleNamespace(Settings=settings))
        browser.url = "http://127.0.0.1:1234/heartbeat/index.html?token=secret"
        self.assertEqual(browser.on_navigation_start(None, None), "started")
        self.assertEqual(observed, [False])
        browser.pywebview_window = SimpleNamespace(transparent=True, focus=False)
        with patch("builtins.print") as output:
            result = browser.on_navigation_completed(None, SimpleNamespace(
                IsSuccess=False, WebErrorStatus="ConnectionAborted",
            ))
        self.assertEqual(result, "completed")
        message = output.call_args.args[0]
        self.assertIn("/heartbeat/index.html", message)
        self.assertIn("ConnectionAborted", message)
        self.assertNotIn("secret", message)
        self.assertTrue(browser.pywebview_window._voidcompass_navigation_failed)
        browser.on_navigation_completed(None, SimpleNamespace(IsSuccess=True))
        self.assertFalse(browser.pywebview_window._voidcompass_navigation_failed)

    def test_optional_setting_failure_keeps_navigation_working(self):
        original = Mock(return_value="started")
        browser_type = type("Browser", (), {
            "on_navigation_start": original,
            "on_navigation_completed": Mock(),
        })
        self.assertTrue(configure_embedded_navigation(SimpleNamespace(EdgeChrome=browser_type)))
        with patch("builtins.print"):
            self.assertEqual(browser_type().on_navigation_start(None, None), "started")
        original.assert_called_once()

    def test_overlay_navigation_does_not_force_show_or_activate(self):
        original = Mock()
        browser_type = type("Browser", (), {
            "on_navigation_start": original,
            "on_navigation_completed": Mock(),
        })
        self.assertTrue(configure_embedded_navigation(SimpleNamespace(EdgeChrome=browser_type)))
        browser = browser_type()
        settings = SimpleNamespace(IsBuiltInErrorPageEnabled=True)
        browser.webview = SimpleNamespace(CoreWebView2=SimpleNamespace(Settings=settings))
        browser.pywebview_window = SimpleNamespace(transparent=True, focus=False)
        browser.on_navigation_start(None, None)
        original.assert_not_called()
        self.assertFalse(settings.IsBuiltInErrorPageEnabled)

    def test_every_window_records_how_its_navigation_ended(self):
        browser_type = type("Browser", (), {
            "on_navigation_start": Mock(),
            "on_navigation_completed": Mock(return_value="completed"),
        })
        self.assertTrue(configure_embedded_navigation(SimpleNamespace(EdgeChrome=browser_type)))
        browser = browser_type()
        browser.url = "http://127.0.0.1:1234/?token=secret"
        # The command deck is an ordinary window, not a transparent overlay.
        browser.pywebview_window = SimpleNamespace(transparent=False)
        with patch("builtins.print"), \
                patch("voidcompass.core.webview_bootstrap.time.monotonic", return_value=42.0):
            browser.on_navigation_completed(None, SimpleNamespace(
                IsSuccess=False, WebErrorStatus="ConnectionReset",
            ))
        self.assertTrue(browser.pywebview_window._voidcompass_navigation_failed)
        self.assertEqual(browser.pywebview_window._voidcompass_navigation_completed_at, 42.0)

    def test_failed_webview2_start_marks_the_window_and_keeps_pywebview_handler(self):
        original_ready = Mock(return_value="ready")
        browser_type = type("Browser", (), {
            "on_navigation_start": Mock(),
            "on_navigation_completed": Mock(),
            "on_webview_ready": original_ready,
        })
        self.assertTrue(configure_embedded_navigation(SimpleNamespace(EdgeChrome=browser_type)))
        browser = browser_type()
        browser.pywebview_window = SimpleNamespace()
        with patch("builtins.print") as output:
            self.assertEqual(browser.on_webview_ready(None, SimpleNamespace(
                IsSuccess=False, InitializationException=RuntimeError("0x8007139F"),
            )), "ready")
        self.assertTrue(browser.pywebview_window._voidcompass_renderer_failed)
        self.assertIn("RuntimeError", output.call_args.args[0])
        original_ready.assert_called_once()

        healthy = browser_type()
        healthy.pywebview_window = SimpleNamespace()
        healthy.on_webview_ready(None, SimpleNamespace(IsSuccess=True))
        self.assertFalse(hasattr(healthy.pywebview_window, "_voidcompass_renderer_failed"))
