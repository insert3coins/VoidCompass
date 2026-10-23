"""Points of interest from EDAstro's Galactic Exploration Catalog (5.6.1).

The catalogue is curated by explorers: sights, nebulae, green gas giants,
planetary features and the like, each with its coordinates and a summary.
Its content is CC BY-NC-SA 3.0 (edastro.com), so it is fetched at runtime
and cached here, never shipped with the app, refreshed at most once a day,
and credited wherever it shows, with each point linked to its own page.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time

import requests

from voidcompass.core.version import APP_VERSION

FEED_URL = "https://edastro.com/gec/json/all"
CREDIT = "Points of interest: EDAstro Galactic Exploration Catalog (CC BY-NC-SA 3.0)"
CREDIT_URL = "https://edastro.com/gec/"
HEADERS = {"User-Agent": f"VoidCompass/{APP_VERSION} (Elite Dangerous companion; insert3coins/VoidCompass)",
           "Accept": "application/json"}
REFRESH_S = 24 * 3600
# After a failed fetch, wait this long before trying again.
RETRY_S = 30 * 60
TIMEOUT_S = 30


def compact(row):
    """The parts of a catalogue entry the app shows."""
    coords = row.get("coordinates")
    try:
        coords = [float(coords[index]) for index in range(3)]
    except (TypeError, ValueError, IndexError):
        return None
    system = str(row.get("galMapSearch") or "").strip()
    if not system:
        return None
    try:
        rating = round(float(row.get("rating")), 1)
    except (TypeError, ValueError):
        rating = None
    url = str(row.get("poiUrl") or "")
    if not url.startswith("https://"):
        url = f"https://edastro.com/gec/view/{int(row.get('id') or 0)}" if row.get("id") else CREDIT_URL
    return {
        "id": int(row.get("id") or 0),
        "name": str(row.get("name") or system)[:160],
        "type": str(row.get("type") or "Point of interest")[:60],
        "region": str(row.get("region") or "")[:80],
        "system": system[:120],
        "coords": coords,
        "summary": str(row.get("summary") or "")[:400],
        "rating": rating,
        "url": url[:300],
    }


class GecCatalog:
    """The cached catalogue, refreshed in the background when it's a day old."""

    def __init__(self, cache_path, fetch=None, clock=time.time, on_change=None):
        self.cache_path = str(cache_path)
        self.lock = threading.Lock()
        self.clock = clock
        self.on_change = on_change
        self._fetch = fetch or self._download
        self._rows = None
        self._fetched = 0.0
        self._tried = 0.0
        self._busy = False
        self.error = ""

    def _download(self):
        response = requests.get(FEED_URL, headers=HEADERS, timeout=TIMEOUT_S)
        response.raise_for_status()
        return response.json()

    def _load(self):
        if self._rows is not None:
            return
        self._rows = []
        try:
            with open(self.cache_path, "r", encoding="utf-8") as handle:
                saved = json.load(handle)
            self._rows = [row for row in saved.get("rows") or () if isinstance(row, dict)]
            self._fetched = float(saved.get("fetched") or 0)
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def rows(self, refresh=True):
        """What's cached; a refresh starts in the background if it's stale."""
        with self.lock:
            self._load()
            rows = list(self._rows)
            now = self.clock()
            stale = now - self._fetched >= REFRESH_S and now - self._tried >= RETRY_S
            start = refresh and stale and not self._busy
            if start:
                self._busy, self._tried = True, now
        if start:
            threading.Thread(target=self._refresh, name="GEC-catalog", daemon=True).start()
        return rows

    def _refresh(self):
        try:
            feed = self._fetch()
            rows = [row for row in (compact(item) for item in feed or () if isinstance(item, dict)) if row]
            if not rows:
                raise ValueError("the catalogue came back empty")
            os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
            temporary = f"{self.cache_path}.tmp"
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump({"fetched": self.clock(), "rows": rows}, handle, ensure_ascii=False)
            os.replace(temporary, self.cache_path)
            with self.lock:
                self._rows, self._fetched, self.error = rows, self.clock(), ""
            if callable(self.on_change):
                self.on_change()
        except Exception as exc:
            logging.info("EDAstro catalogue not refreshed: %s", exc)
            with self.lock:
                self.error = str(exc)[:200]
        finally:
            with self.lock:
                self._busy = False
