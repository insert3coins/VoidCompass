"""Keep transient WebView2 navigation failures out of application windows."""

import time
from urllib.parse import urlparse


def configure_embedded_navigation(edge_module=None):
    """Configure before creating any WebViews, while keeping pywebview hooks.

    pywebview enables Edge's full built-in error document during initialization.
    Turn it off on the UI thread before each navigation; the owning host retains
    responsibility for readiness, retrying and presenting its actual content.
    Each window therefore records how its last navigation ended, and whether
    WebView2 itself failed to start, so that host can see what to recover.
    """
    try:
        if edge_module is None:
            from webview.platforms import edgechromium as edge_module
        browser_type = edge_module.EdgeChrome
        original_start = browser_type.on_navigation_start
        if getattr(original_start, "_voidcompass_navigation", False) is True:
            return True
        original_completed = browser_type.on_navigation_completed
        original_ready = getattr(browser_type, "on_webview_ready", None)

        def on_navigation_start(browser, sender, args):
            try:
                browser.webview.CoreWebView2.Settings.IsBuiltInErrorPageEnabled = False
            except Exception as exc:
                print(f"WebView navigation settings unavailable: {type(exc).__name__}", flush=True)
            window = getattr(browser, "pywebview_window", None)
            if getattr(window, "transparent", False) and not getattr(window, "focus", True):
                # pywebview's transparent-window workaround calls Show() and
                # Activate() on every navigation, including error/retry pages.
                # Our overlay controller owns their non-activating reveal.
                return None
            return original_start(browser, sender, args)

        def on_navigation_completed(browser, sender, args):
            success = bool(getattr(args, "IsSuccess", True))
            window = getattr(browser, "pywebview_window", None)
            if window is not None:
                # With the error document off, a failed load is an empty
                # window. Record it so the owning host retries promptly: the
                # overlay host within its watchdog, the command deck at all.
                window._voidcompass_navigation_failed = not success
                window._voidcompass_navigation_completed_at = time.monotonic()
            if not success:
                # Never put the loopback authentication token in diagnostics.
                path = urlparse(str(getattr(browser, "url", "") or "")).path
                status = str(getattr(args, "WebErrorStatus", "unknown"))
                print(f"WebView navigation failed: {path} ({status})", flush=True)
            return original_completed(browser, sender, args)

        def on_webview_ready(browser, sender, args):
            # pywebview only logs a failed WebView2 start and leaves the window
            # empty for good; a fresh host process is the only way back.
            if not bool(getattr(args, "IsSuccess", True)):
                window = getattr(browser, "pywebview_window", None)
                if window is not None:
                    window._voidcompass_renderer_failed = True
                error = getattr(args, "InitializationException", None)
                print(f"WebView2 failed to initialise: {type(error).__name__}", flush=True)
            return original_ready(browser, sender, args)

        on_navigation_start._voidcompass_navigation = True
        browser_type.on_navigation_start = on_navigation_start
        browser_type.on_navigation_completed = on_navigation_completed
        if callable(original_ready):
            browser_type.on_webview_ready = on_webview_ready
        return True
    except Exception as exc:
        print(f"WebView navigation setup unavailable: {type(exc).__name__}", flush=True)
        return False
