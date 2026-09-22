"""Keep transient WebView2 navigation failures out of application windows."""

from urllib.parse import urlparse


def configure_embedded_navigation(edge_module=None):
    """Configure before creating any WebViews, while keeping pywebview hooks.

    pywebview enables Edge's full built-in error document during initialization.
    Turn it off on the UI thread before each navigation; the owning host retains
    responsibility for readiness, retrying and presenting its actual content.
    """
    try:
        if edge_module is None:
            from webview.platforms import edgechromium as edge_module
        browser_type = edge_module.EdgeChrome
        original_start = browser_type.on_navigation_start
        if getattr(original_start, "_voidcompass_navigation", False) is True:
            return True
        original_completed = browser_type.on_navigation_completed

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
            if not getattr(args, "IsSuccess", True):
                # Never put the loopback authentication token in diagnostics.
                path = urlparse(str(getattr(browser, "url", "") or "")).path
                status = str(getattr(args, "WebErrorStatus", "unknown"))
                print(f"WebView navigation failed: {path} ({status})", flush=True)
            return original_completed(browser, sender, args)

        on_navigation_start._voidcompass_navigation = True
        browser_type.on_navigation_start = on_navigation_start
        browser_type.on_navigation_completed = on_navigation_completed
        return True
    except Exception as exc:
        print(f"WebView navigation setup unavailable: {type(exc).__name__}", flush=True)
        return False
