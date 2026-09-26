"""Deliver bundled web assets reliably to the local WebView2 servers.

A page whose app.js or one of its modules fails to load starts no client at
all: the boot screen stays frozen and overlays never report ready. Two
Windows traps can cause that without any real missing file.
"""

from __future__ import annotations

import mimetypes
import time

# ``mimetypes`` reads the Windows registry, where some installs map .js to
# text/plain. With nosniff on, a browser then refuses every script, so the
# types our pages depend on are pinned here.
_ASSET_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".cur": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".txt": "text/plain; charset=utf-8",
}

# The packaged build serves files it has just extracted to a temp folder,
# and real-time antivirus can hold one briefly while it scans. A short retry
# rides that out instead of turning it into a 404 that kills the page.
READ_ATTEMPTS = 6
READ_RETRY_S = 0.15


def asset_type(path):
    """Return the Content-Type for one bundled asset path."""
    suffix = str(getattr(path, "suffix", "") or "").casefold()
    return _ASSET_TYPES.get(suffix) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def read_asset(path, attempts=READ_ATTEMPTS, delay=READ_RETRY_S, sleep=time.sleep):
    """Read one asset, retrying transient OS errors; re-raise the last one."""
    last_error = None
    for attempt in range(max(1, int(attempts))):
        try:
            return path.read_bytes()
        except FileNotFoundError:
            raise
        except OSError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                sleep(delay)
    raise last_error
