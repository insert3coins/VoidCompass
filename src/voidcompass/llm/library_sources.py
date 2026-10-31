"""Your own sources for the Watcher's LIBRARY (5.7.1): web pages about Elite
Dangerous (a wiki, a guide), fetched on this PC when you add them and split
into cards its mind reads when you talk to it. Not training: the model never
changes; it reads the best few cards for what you asked, and its rules check
every word it says, as with the rest of the LIBRARY.

Fetching is polite: each site's robots.txt is obeyed, one page at a time with
a pause between, a page limit per source, and it can be cancelled. Only the
pages you add (and, if you choose, pages they link to on the same site) are
read. A card that names something the Watcher never speaks of is never kept.
Everything stays in Void Compass's folder on this PC, never in the build.
"""
from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
import json
import logging
import math
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.request
import urllib.robotparser
from urllib.parse import parse_qs, quote, unquote, urldefrag, urlencode, urljoin, urlparse
import zlib

from voidcompass.core.version import APP_VERSION
from voidcompass.llm.llm_embed import similarity, unpack

SOURCES_KEPT = 40
# Search by meaning (bge-small): a card this alike (or sharing words) is kept,
# and shared words add a little on top. Measured on the Elite wiki's cards:
# the right card for a question scored 0.67 to 0.86.
MEANING_FLOOR = 0.6
MEANING_SPREAD = 0.1
WORDS_WEIGHT = 0.15
PAGE_CHOICES = (1, 10, 25, 50, 100, 200)
CARD_TEXT = 700
CARDS_KEPT = 8000
PAGE_BYTES = 3 * 1024 * 1024
FETCH_GAP_S = 1.0
FETCH_TIMEOUT_S = 15
USER_AGENT = f"VoidCompass/{APP_VERSION} (the Watcher's library; personal use)"
# Never parts of a page's text: furniture, scripts, and a wiki's edit links,
# references, navigation boxes and contents.
_SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "header", "footer", "aside", "form", "button", "select",
              "template", "iframe", "figure", "sup"}
_SKIP_CLASSES = re.compile(r"\b(mw-editsection|reference|references|reflist|navbox|toc|noprint|mw-jump-link|catlinks|"
                           r"printfooter|mw-cite-backlink|sidebar|global-navigation|page-footer|wds-|comment|advert|"
                           r"cookie|share|breadcrumb)", re.I)
_CONTENT = re.compile(r"\b(mw-parser-output|mw-content-text|page-content|entry-content|post-content|article-body)\b", re.I)
_BLOCKS = {"p", "li", "dd", "dt", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "blockquote", "pre", "caption", "td", "th"}
_VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr", "area", "col", "embed", "param", "track"}
# Links not worth following: a wiki's own pages, files, edits, feeds.
_SKIP_LINKS = re.compile(r"(\b(Special|File|Image|Category|Talk|User|User_talk|Template|Help|MediaWiki|Module|"
                         r"Forum|Message_Wall|Blog|Board)(_talk)?:|[?&](action|oldid|diff|printable|veaction)=|"
                         r"\.(png|jpe?g|gif|webp|svg|pdf|zip|mp4|webm|ogg|mp3)$|/feed/?$|/(login|signin|register)\b)",
                         re.I)
# Sections that are lists, not text.
_NOT_TEXT = re.compile(r"^\s*(videos?|gallery|images?|media|references?|notes|sources?|see also|external links?|"
                       r"further reading|navigation|footnotes|citations)\s*$", re.I)
_WORD = re.compile(r"[a-z][a-z0-9'-]{2,}")
_STOP = set("""the and for are but not you all any can had her was one our out day get has him his how man new now old
see two way who boy did its let put say she too use that this with from they will would there their what about which
when make like time just know take into year your good some could them than then look only come over think also back
after work first well even want because these give most very been were said each does such many more other where while
being here those through during before should still between both same into upon""".split())


# -- reading a page ---------------------------------------------------------------
class PageText(HTMLParser):
    """A page's title, readable blocks (with the heading they sit under) and
    links. Blocks inside the page's main content are preferred when there are
    enough of them; the rest of the page is a fallback."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.links = []
        self._in_title = False
        self._stack = []          # (tag, skipped, content)
        self._text = []
        self._heading = ""
        self.blocks = []          # (heading, text, in content)

    def _skipping(self):
        return any(skipped for _tag, skipped, _content in self._stack)

    def _in_content(self):
        return any(content for _tag, _skipped, content in self._stack)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "a" and attrs.get("href") and not self._skipping():
            self.links.append((attrs["href"], self._in_content()))
        if tag in _VOID:
            if tag == "br":
                self._text.append(" ")
            return
        if tag in _BLOCKS:
            self._flush()
        names = f"{attrs.get('class') or ''} {attrs.get('id') or ''}"
        skipped = tag in _SKIP_TAGS or bool(_SKIP_CLASSES.search(names)) or attrs.get("role") == "navigation"
        content = tag in {"main", "article"} or attrs.get("role") == "main" or bool(_CONTENT.search(names))
        self._stack.append((tag, skipped, content))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in _VOID:
            return
        if tag in _BLOCKS:
            self._flush(heading=tag in {"h1", "h2", "h3", "h4", "h5", "h6"})
        # Close back to the matching tag (pages don't always close what they open).
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                break

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if not self._skipping():
            self._text.append(data)

    def _flush(self, heading=False):
        text = " ".join("".join(self._text).split())
        self._text = []
        if not text:
            return
        if heading:
            self._heading = text[:120]
        elif len(text) >= 3:
            self.blocks.append((self._heading, text, self._in_content()))

    def close(self):
        super().close()
        self._flush()


def read_page(html, url=""):
    """(title, [(section, text)], links) of a page's readable text."""
    parser = PageText()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        logging.debug("A library page didn't parse cleanly: %s", url, exc_info=True)
    content = [(heading, text) for heading, text, inside in parser.blocks if inside]
    in_content = sum(len(text) for _heading, text in content) >= 400
    rows = content if in_content else [(heading, text) for heading, text, _inside in parser.blocks]
    title = " ".join(parser.title.split())
    # "Fleet Carrier | Elite Dangerous Wiki | Fandom": the page's own name.
    title = re.split(r"\s+[|–—-]\s+", title)[0] if title else urlparse(url).path.rsplit("/", 1)[-1]
    # The links in the page's own text (not its menus), when it has one.
    links = [urldefrag(urljoin(url, link))[0] for link, inside in parser.links if inside or not in_content]
    return title.replace("_", " ")[:160], rows, links


def cards_from(title, rows, url, refused=None):
    """The page's text as cards of at most CARD_TEXT characters, by section:
    {"title", "text", "url"}. A card naming what it never speaks of
    (``refused``, a pattern) isn't kept. Short scraps (menus, captions) go."""
    sections = []
    for heading, text in rows:
        if len(text) < 40 and not text.endswith((".", "!", "?", ":")):
            continue  # a menu item or a caption
        if _NOT_TEXT.match(heading or ""):
            continue  # video titles, picture captions, references
        if sections and sections[-1][0] == heading:
            sections[-1][1].append(text)
        else:
            sections.append((heading, [text]))
    cards = []
    for heading, texts in sections:
        name = f"{title} · {heading}" if heading and heading.casefold() != title.casefold() else title
        chunk = ""
        for text in texts:
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                if refused is not None and refused.search(sentence):
                    continue  # just that sentence: the rest of what it says is kept
                if len(chunk) + len(sentence) + 1 > CARD_TEXT and chunk:
                    cards.append({"title": name, "text": chunk.strip(), "url": url})
                    chunk = ""
                chunk += " " + sentence[:CARD_TEXT]
        if chunk.strip():
            cards.append({"title": name, "text": chunk.strip(), "url": url})
    if refused is not None:
        cards = [card for card in cards if not refused.search(f"{card['title']} {card['text']}")]
    return [card for card in cards if len(card["text"]) >= 60]


def same_site_links(links, start, limit):
    """Links on the start page's own site worth following, each once."""
    host = urlparse(start).netloc.casefold()
    seen, out = set(), []
    for link in links:
        parts = urlparse(link)
        if parts.scheme not in ("http", "https") or parts.netloc.casefold() != host or _SKIP_LINKS.search(link):
            continue
        if link not in seen:
            seen.add(link)
            out.append(link)
        if len(out) >= limit:
            break
    return out


def terms(text):
    return [word for word in _WORD.findall(str(text or "").casefold()) if word not in _STOP]


# -- the library ------------------------------------------------------------------
class SourceLibrary:
    """Your sources and their cards, kept in ``folder``: fetched one at a time
    in the background, searched when it talks to you."""

    def __init__(self, folder, on_change=None, refused=None, opener=None, sleep=time.sleep, embedder=None,
                 builtin=None):
        self.folder = Path(folder)
        self.on_change = on_change
        # What it never speaks of: a card naming it isn't kept.
        self.refused = refused
        # Search by meaning (llm_embed.Embedder), or None for words only; and
        # its own LIBRARY's cards, searched with yours ({"title", "text", "subject"}).
        self.embedder = embedder
        self.builtin = builtin
        self._builtin_vectors = {}
        self._vector_thread = None
        self.indexing = {"done": 0, "total": 0}
        self._open = opener or self._fetch
        self._sleep = sleep
        self._lock = threading.Lock()
        self._sources = []
        self._cards = {}
        self._index = None
        self._thread = None
        self._cancel = threading.Event()
        self.state = {"stage": "idle", "source": "", "done": 0, "total": 0, "url": "", "skipped": 0, "error": ""}
        self._load()

    # -- keeping ---------------------------------------------------------------
    def _path(self, name):
        return self.folder / name

    def _load(self):
        try:
            self._builtin_vectors = json.loads(self._path("builtin-vectors.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._builtin_vectors = {}
        try:
            data = json.loads(self._path("sources.json").read_text(encoding="utf-8"))
            self._sources = [row for row in data.get("sources") or [] if isinstance(row, dict) and row.get("id")]
        except (OSError, ValueError):
            self._sources = []
        for row in self._sources:
            try:
                cards = json.loads(self._path(f"cards-{row['id']}.json").read_text(encoding="utf-8"))
                self._cards[row["id"]] = [card for card in cards if isinstance(card, dict) and card.get("text")]
            except (OSError, ValueError):
                self._cards[row["id"]] = []

    def _save(self, source_id=None):
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            if source_id is not None:
                self._path(f"cards-{source_id}.json").write_text(
                    json.dumps(self._cards.get(source_id, []), ensure_ascii=False), encoding="utf-8")
            self._path("sources.json").write_text(json.dumps({"sources": self._sources}, indent=1), encoding="utf-8")
        except OSError:
            logging.warning("The Watcher's library sources couldn't be saved in %s", self.folder, exc_info=True)

    def _changed(self):
        self._index = None
        if callable(self.on_change):
            try:
                self.on_change()
            except Exception:
                logging.debug("Library change listener failed", exc_info=True)

    # -- what's there ------------------------------------------------------------
    def sources(self):
        with self._lock:
            return [{**row, "cards": len(self._cards.get(row["id"], []))} for row in self._sources]

    def card_count(self):
        with self._lock:
            return sum(len(cards) for cards in self._cards.values())

    def running(self):
        return self._thread is not None and self._thread.is_alive()

    # -- adding, refreshing, removing -------------------------------------------------
    def add(self, url, follow=False, pages=25):
        """Add a source and start fetching it. "" when started, else why not."""
        url = str(url or "").strip()
        parts = urlparse(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            return "That isn't a web address (it starts with https://)."
        if self.running():
            return "It's still reading another source: wait, or cancel it."
        pages = max(1, min(int(pages or 1), PAGE_CHOICES[-1])) if follow else 1
        with self._lock:
            if any(row["url"] == url for row in self._sources):
                return "That source is already in its library: refresh it instead."
            if len(self._sources) >= SOURCES_KEPT:
                return f"It keeps at most {SOURCES_KEPT} sources: remove one first."
            source = {"id": f"{zlib.crc32(url.encode('utf-8')):08x}", "url": url, "host": parts.netloc,
                      "title": parts.netloc, "follow": bool(follow), "pages_wanted": pages,
                      "added": round(time.time()), "fetched": None, "pages": 0, "skipped": 0, "error": ""}
            self._sources.append(source)
            self._cards[source["id"]] = []
        self._save()
        self._start(source)
        return ""

    def refresh(self, source_id):
        if self.running():
            return "It's still reading another source."
        with self._lock:
            source = next((row for row in self._sources if row["id"] == source_id), None)
        if source is None:
            return "No such source."
        self._start(source)
        return ""

    def remove(self, source_id):
        if self.running() and self.state.get("source") == source_id:
            self.cancel()
            self._thread.join(5)
        with self._lock:
            before = len(self._sources)
            self._sources = [row for row in self._sources if row["id"] != source_id]
            self._cards.pop(source_id, None)
            gone = len(self._sources) < before
        if gone:
            try:
                self._path(f"cards-{source_id}.json").unlink(missing_ok=True)
            except OSError:
                pass
            self._save()
            self._changed()
        return gone

    def cancel(self):
        self._cancel.set()

    def _start(self, source):
        self._cancel.clear()
        self.state = {"stage": "fetching", "source": source["id"], "done": 0, "total": source["pages_wanted"],
                      "url": source["url"], "skipped": 0, "error": ""}
        self._thread = threading.Thread(target=self._crawl, args=(source,), name="watcher-library", daemon=True)
        self._thread.start()
        self._changed()

    # -- fetching -----------------------------------------------------------------
    @staticmethod
    def _fetch(url, html=True):
        """(text, final url) or raises: web pages only (unless ``html`` is
        False, for robots.txt), at most PAGE_BYTES."""
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                       "Accept": "text/html" if html else "text/plain"})
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_S) as reply:
            kind = reply.headers.get("Content-Type", "")
            if html and "html" not in kind.casefold():
                raise ValueError(f"not a web page ({kind or 'unknown'})")
            data = reply.read(PAGE_BYTES + 1)[:PAGE_BYTES]
            charset = reply.headers.get_content_charset() or "utf-8"
            return data.decode(charset, errors="replace"), reply.geturl()

    def _robots(self, url):
        """The site's robots.txt, as the robots standard (RFC 9309) reads it:
        none there (4xx), everything may be read; the site failing (5xx or
        no answer), nothing may. (rules, why nothing may be read or "")."""
        parts = urlparse(url)
        robots = urllib.robotparser.RobotFileParser()
        why = ""
        try:
            text, _final = self._open(f"{parts.scheme}://{parts.netloc}/robots.txt", html=False)
            robots.parse(text.splitlines())
        except urllib.error.HTTPError as exc:
            robots.parse([] if 400 <= exc.code < 500 else ["User-agent: *", "Disallow: /"])
            why = "" if 400 <= exc.code < 500 else f"Its site isn't answering properly ({exc.code})."
        except Exception as exc:
            robots.parse(["User-agent: *", "Disallow: /"])
            why = f"Its site didn't answer ({exc})."[:200]
        return robots, why

    @staticmethod
    def wiki_title(url):
        """A wiki page's title from its address (/wiki/Title or ?title=), or None."""
        parts = urlparse(url)
        if "/wiki/" in parts.path:
            title = unquote(parts.path.split("/wiki/", 1)[1])
        else:
            title = (parse_qs(parts.query).get("title") or [""])[0]
        return title.replace("_", " ").strip() or None

    def _wiki_page(self, url, title, apis):
        """(title, html, linked page addresses) through the wiki's own API, the
        way it asks programs to read it (Fandom refuses programs its pages).
        ``apis`` is the API paths to try; the one that answers goes first."""
        parts = urlparse(url)
        for api in list(apis):
            query = urlencode({"action": "parse", "page": title, "prop": "text|links", "format": "json",
                               "formatversion": 2, "redirects": 1})
            try:
                text, _final = self._open(f"{parts.scheme}://{parts.netloc}{api}?{query}", html=False)
                page = json.loads(text).get("parse")
            except (ValueError, OSError, urllib.error.URLError):
                continue
            if not isinstance(page, dict) or "text" not in page:
                continue
            apis.remove(api)
            apis.insert(0, api)
            links = [f"{parts.scheme}://{parts.netloc}/wiki/{quote(str(row.get('title') or '').replace(' ', '_'))}"
                     for row in page.get("links") or [] if isinstance(row, dict) and row.get("ns") == 0
                     and row.get("exists", True) and row.get("title")]
            return str(page.get("title") or title), str(page.get("text") or ""), links
        return None

    def _crawl(self, source):
        robots, unreachable = self._robots(source["url"])
        apis = ["/api.php", "/w/api.php"]
        delay = max(FETCH_GAP_S, min(10.0, float(robots.crawl_delay(USER_AGENT) or 0)))
        queue, seen, cards, pages, skipped = [source["url"]], set(), [], 0, 0
        title = source["title"]
        error = ""
        while queue and pages < source["pages_wanted"] and not self._cancel.is_set():
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            if not robots.can_fetch(USER_AGENT, url):
                skipped += 1
                if url == source["url"]:
                    error = unreachable or "Its site asks not to be read by programs (robots.txt)."
                continue
            self.state.update(url=url, done=pages, skipped=skipped)
            self._changed()
            try:
                wiki = self._wiki_page(url, self.wiki_title(url), apis) if self.wiki_title(url) else None
                if wiki is not None:
                    page_title, html, wiki_links = wiki
                    final = url
                    page_title, rows, _links = read_page(f"<title>{page_title}</title><main>{html}</main>", url)
                    links = wiki_links
                else:
                    html, final = self._open(url)
                    page_title, rows, links = read_page(html, final)
                found = cards_from(page_title, rows, final, self.refused)
                cards.extend(found)
                pages += 1
                if url == source["url"]:
                    title = page_title or title
                if source["follow"]:
                    queue.extend(same_site_links(links, source["url"], source["pages_wanted"] * 3))
            except Exception as exc:
                skipped += 1
                if url == source["url"]:
                    error = f"It couldn't read that page ({exc})."[:200]
                logging.info("Watcher library skipped %s: %s", url, exc)
            if queue and pages < source["pages_wanted"]:
                self._sleep(delay)
        cancelled = self._cancel.is_set()
        with self._lock:
            if not cancelled or cards:
                others = sum(len(rows) for key, rows in self._cards.items() if key != source["id"])
                self._cards[source["id"]] = cards[:max(0, CARDS_KEPT - others)]
            source.update(title=title, pages=pages, skipped=skipped, error=error,
                          fetched=round(time.time()) if pages else source.get("fetched"))
        self._save(source["id"])
        self.state = {"stage": "cancelled" if cancelled else "done", "source": source["id"], "done": pages,
                      "total": source["pages_wanted"], "url": "", "skipped": skipped, "error": error}
        self._changed()
        self.fill_vectors()

    # -- reading for meaning (llm_embed) ------------------------------------------------
    def vectors_running(self):
        return self._vector_thread is not None and self._vector_thread.is_alive()

    def fill_vectors(self):
        """Read every card without one for its meaning, in the background:
        yours after each fetch, its own LIBRARY's once (kept)."""
        if self.embedder is None or not self.embedder.available() or self.vectors_running():
            return False
        self._vector_thread = threading.Thread(target=self._fill_vectors, name="watcher-library-vectors", daemon=True)
        self._vector_thread.start()
        return True

    def _fill_vectors(self):
        todo = []
        for card in (self.builtin() if callable(self.builtin) else None) or ():
            key = _card_key(card)
            if key not in self._builtin_vectors:
                todo.append((None, key, card))
        with self._lock:
            for row in self._sources:
                todo += [(row["id"], None, card) for card in self._cards.get(row["id"], []) if not card.get("vec")]
        if not todo:
            return
        self.indexing = {"done": 0, "total": len(todo)}
        self._changed()
        changed = set()
        for start in range(0, len(todo), 32):
            if getattr(self, "_closing", False):
                break
            chunk = todo[start:start + 32]
            vectors = self.embedder.vectors([f"{card['title']}: {card['text']}" for _id, _key, card in chunk])
            if vectors is None:
                break
            with self._lock:
                for (source_id, key, card), vector in zip(chunk, vectors):
                    if source_id is None:
                        self._builtin_vectors[key] = vector
                    else:
                        card["vec"] = vector
                    changed.add(source_id)
            self.indexing = {"done": min(len(todo), start + len(chunk)), "total": len(todo)}
            self._index = None
            self._changed()
        for source_id in changed:
            if source_id is None:
                try:
                    self.folder.mkdir(parents=True, exist_ok=True)
                    self._path("builtin-vectors.json").write_text(json.dumps(self._builtin_vectors), encoding="utf-8")
                except OSError:
                    logging.warning("The Watcher's library search index couldn't be saved", exc_info=True)
            else:
                self._save(source_id)
        self.indexing = {"done": 0, "total": 0}
        self._index = None
        self._changed()

    # -- searching ---------------------------------------------------------------
    def _build_index(self):
        cards = []
        for card in (self.builtin() if callable(self.builtin) else None) or ():
            cards.append({**card, "host": "", "own": True, "vec": self._builtin_vectors.get(_card_key(card))})
        with self._lock:
            for row in self._sources:
                for card in self._cards.get(row["id"], []):
                    cards.append({**card, "host": row["host"]})
        postings = {}
        for number, card in enumerate(cards):
            counts = Counter(terms(card["text"]))
            for term in terms(card["title"]):
                counts[term] += 3  # the page and section name count most
            for term, count in counts.items():
                postings.setdefault(term, []).append((number, count))
        vectors = [unpack(card["vec"]) if card.get("vec") else None for card in cards]
        self._index = (cards, postings, vectors)
        return self._index

    def search(self, text, limit=5):
        """Cards about what you asked, best first: by meaning when its search
        model is here (a little extra for the same words), else by words."""
        cards, postings, vectors = self._index or self._build_index()
        if not cards:
            return []
        words = Counter()
        for term in set(terms(text)):
            rows = postings.get(term)
            if not rows:
                continue
            weight = math.log(1 + len(cards) / len(rows))
            for number, count in rows:
                words[number] += weight * (1 + math.log(count))
        asked = None
        if self.embedder is not None and self.embedder.available() and any(vector is not None for vector in vectors):
            packed = self.embedder.question(text)
            asked = unpack(packed) if packed else None
        if any(vector is None for vector in vectors):
            self.fill_vectors()  # some not yet read for meaning: in the background
        if asked is None:
            best = [number for number, score in words.most_common(limit * 3) if score > 1.0]
            return [_shown(cards[number]) for number in best[:limit]]
        most = max(words.values(), default=0.0) or 1.0
        meanings = [similarity(asked, vector) if vector is not None else None for vector in vectors]
        # Near the best match, not just over the floor: the weak ones padded the list.
        cut = max(MEANING_FLOOR, max((value for value in meanings if value is not None), default=0.0) - MEANING_SPREAD)
        scored = []
        for number, meaning in enumerate(meanings):
            if (meaning is not None and meaning >= cut) or (meaning is None and words.get(number, 0.0) > 1.0):
                scored.append(((meaning or MEANING_FLOOR) + WORDS_WEIGHT * words.get(number, 0.0) / most, number))
        scored.sort(reverse=True)
        return [_shown(cards[number]) for _score, number in scored[:limit]]

    def for_prompt(self, text, limit=3, length=500):
        """The best few cards as lines for its mind: what the card says, and where from."""
        return [f"{card['title']}: {card['text'][:length]}" for card in self.search(text, limit)]


def _card_key(card):
    words = f"{card.get('title', '')}|{card.get('text', '')}"
    return f"{zlib.crc32(words.encode('utf-8')):08x}"


def _shown(card):
    """A card as searched for: without its vector."""
    return {key: value for key, value in card.items() if key != "vec"}
