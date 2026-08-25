"""Small, cached Galnet RSS relay for the HTML command deck.

Galnet is atmosphere rather than flight-critical telemetry.  The service is
therefore deliberately independent of Tk and the journal pipeline: callers
receive a JSON-safe cached snapshot immediately while a bounded daemon worker
refreshes Frontier's public RSS feed in the background.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

import requests


GALNET_RSS_URL = "https://community.elitedangerous.com/galnet-rss"
DEFAULT_REFRESH_SECONDS = 30 * 60
MAX_ARTICLES = 24
MAX_RESPONSE_BYTES = 5 * 1024 * 1024


class _DescriptionParser(HTMLParser):
    """Turn the deliberately small HTML subset in RSS descriptions into text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.casefold() == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag.casefold() in {"p", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)

    def text(self):
        value = "".join(self.parts).replace("\r\n", "\n").replace("\r", "\n")
        value = "\n".join(line.rstrip() for line in value.split("\n"))
        return re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", value).strip()


def _plain_description(value):
    parser = _DescriptionParser()
    try:
        parser.feed(str(value or ""))
        parser.close()
        return parser.text()
    except Exception:
        return str(value or "").strip()


def _published(value):
    raw = str(value or "").strip()
    if not raw:
        return "", ""
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(timezone.utc)
        return parsed.isoformat().replace("+00:00", "Z"), parsed.strftime("%d %b %Y")
    except (TypeError, ValueError, OverflowError):
        return raw[:80], raw[:30]


def parse_galnet_rss(payload, limit=MAX_ARTICLES):
    """Parse Frontier's RSS document while preserving its editorial ordering."""
    root = ElementTree.fromstring(payload)
    articles = []
    for item in root.findall(".//item"):
        title = _plain_description(item.findtext("title"))[:300]
        if not title:
            continue
        body = _plain_description(item.findtext("description"))[:20_000]
        identifier = str(item.findtext("guid") or title).strip()[:300]
        published, stamp = _published(item.findtext("pubDate"))
        articles.append({
            "id": identifier,
            "title": title,
            "body": body,
            "published": published,
            "stamp": stamp,
        })
        if len(articles) >= max(1, int(limit or MAX_ARTICLES)):
            break
    return articles


class GalnetFeedService:
    """Thread-safe cache and non-blocking Frontier RSS refresh."""

    def __init__(self, cache_path, app_version, refresh_seconds=DEFAULT_REFRESH_SECONDS):
        self.cache_path = Path(cache_path)
        self.app_version = str(app_version or "unknown")
        self.refresh_seconds = max(300, int(refresh_seconds or DEFAULT_REFRESH_SECONDS))
        self._lock = threading.Lock()
        self._busy = False
        self._stopped = threading.Event()
        self._articles = []
        self._updated_at = ""
        self._fetched_epoch = 0.0
        self._status = "waiting"
        self._detail = "Awaiting Galnet relay"
        self._load_cache()

    def _load_cache(self):
        try:
            cached = json.loads(self.cache_path.read_text(encoding="utf-8"))
            articles = cached.get("articles") if isinstance(cached, dict) else None
            if not isinstance(articles, list):
                return
            clean = [row for row in articles[:MAX_ARTICLES] if isinstance(row, dict)]
            if not clean:
                return
            self._articles = clean
            self._updated_at = str(cached.get("updated_at") or "")[:80]
            self._fetched_epoch = float(cached.get("fetched_epoch") or 0.0)
            self._status = "cached"
            self._detail = "Cached Galnet dispatches"
        except FileNotFoundError:
            pass
        except Exception as exc:
            logging.debug("Galnet cache ignored: %s", exc)

    def _save_cache(self, articles, updated_at, fetched_epoch):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        payload = {
            "updated_at": updated_at,
            "fetched_epoch": fetched_epoch,
            "articles": articles,
        }
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, self.cache_path)

    def snapshot(self):
        with self._lock:
            return {
                "status": self._status,
                "detail": self._detail,
                "busy": self._busy,
                "source": "Frontier Galnet",
                "updated_at": self._updated_at,
                "articles": [dict(row) for row in self._articles],
            }

    def refresh_async(self, callback=None, force=False):
        now = time.time()
        with self._lock:
            if self._busy or self._stopped.is_set():
                return False
            if (
                not force and self._articles and self._fetched_epoch
                and now - self._fetched_epoch < self.refresh_seconds
            ):
                return False
            self._busy = True
            self._status = "refreshing"
            self._detail = "Receiving Galnet dispatches"
        threading.Thread(
            target=self._refresh_worker,
            args=(callback,),
            name="galnet-rss",
            daemon=True,
        ).start()
        return True

    def _refresh_worker(self, callback):
        try:
            response = requests.get(
                GALNET_RSS_URL,
                headers={
                    "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.5",
                    "User-Agent": f"VoidCompass/{self.app_version}",
                },
                timeout=(4.0, 10.0),
            )
            response.raise_for_status()
            if len(response.content) > MAX_RESPONSE_BYTES:
                raise ValueError("Galnet response exceeded the safety limit")
            articles = parse_galnet_rss(response.content)
            if not articles:
                raise ValueError("Galnet returned no readable dispatches")
            fetched_epoch = time.time()
            updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(fetched_epoch))
            try:
                self._save_cache(articles, updated_at, fetched_epoch)
            except Exception as exc:
                logging.debug("Galnet cache write skipped: %s", exc)
            with self._lock:
                self._articles = articles
                self._updated_at = updated_at
                self._fetched_epoch = fetched_epoch
                self._status = "live"
                self._detail = f"{len(articles)} Galnet dispatches received"
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__
            with self._lock:
                self._status = "cached" if self._articles else "error"
                self._detail = (
                    "Galnet offline — showing cached dispatches"
                    if self._articles else f"Galnet unavailable: {message[:140]}"
                )
            logging.info("Galnet refresh unavailable: %s", message)
        finally:
            with self._lock:
                self._busy = False
            if callable(callback) and not self._stopped.is_set():
                try:
                    callback()
                except Exception:
                    logging.debug("Galnet completion callback failed", exc_info=True)

    def request_stop(self):
        self._stopped.set()
