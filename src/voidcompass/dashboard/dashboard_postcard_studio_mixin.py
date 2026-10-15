"""The Postcards page's studio (5.5.4), for MainDashboard: the preview that
follows the controls before anything is saved, a saved postcard edited with
its own preview, its picture swapped, and older postcards (saved before they
could be edited) given their card back from the journal.
"""
from __future__ import annotations

import datetime as _datetime
import logging
import os
import threading
import time

from voidcompass.core import themes
from voidcompass.core.platform_support import default_screenshot_path
from voidcompass.exploration.galactic_regions import find_region
from voidcompass.overlays import postcard_themes
from voidcompass.overlays.postcard_picture import is_editable, keep_card, kept_card, open_picture
from voidcompass.overlays.postcard_restore import ScreenshotIndex, find_picture, saved_at
from voidcompass.overlays.postcards import STYLES as POSTCARD_STYLES, postcard_card, postcard_facts, postcard_options
from voidcompass.overlays.postcards import TEXT_PARTS as POSTCARD_TEXT_PARTS, text_size as postcard_text_size

DRAFT_THEME = "Studio draft"
# What the studio may try out before it's saved.
DRAFT_KEYS = {
    "postcard_style": 60, "postcard_greeting": 12, "postcard_greeting_text": 40, "postcard_note_mode": 10,
    "postcard_note_text": 160, "postcard_signature": 40, "postcard_facts": None, "postcard_doing": None,
    "postcard_postmark": None,
    "postcard_size_lettering": 3, "postcard_size_note": 3, "postcard_size_details": 3,
}


class DashboardPostcardStudioMixin:
    # -- The studio's preview: the controls tried out, nothing saved -----------
    def _postcard_set_draft(self, payload):
        values = (payload or {}).get("values")
        values = values if isinstance(values, dict) else {}
        config = {}
        for key, limit in DRAFT_KEYS.items():
            if key not in values:
                continue
            value = values[key]
            config[key] = bool(value) if limit is None else " ".join(str(value or "").split())[:limit]
        theme = (payload or {}).get("theme")
        self._postcard_draft = {"config": config,
                                "theme": postcard_themes.normalize(theme) if isinstance(theme, dict) else None}
        return True

    def _postcard_preview_config(self):
        """The settings the preview draws with: the saved ones, with the
        studio's draft over them."""
        draft = getattr(self, "_postcard_draft", None) or {}
        config = dict(self.config or {})
        config.update(draft.get("config") or {})
        if draft.get("theme"):
            config["postcard_themes"] = {**dict(config.get("postcard_themes") or {}), DRAFT_THEME: draft["theme"]}
            config["postcard_style"] = f"theme:{DRAFT_THEME}"
        return config

    # -- A saved postcard, edited ---------------------------------------------
    def _postcard_edited(self, card_id, payload):
        """(path, card, picture, style, theme, postmark, settings) with the
        editor's changes, or None."""
        path = self.postcard_album().path(card_id)
        kept = kept_card(path) if path else None
        if kept is None:
            return None
        card, settings, picture = kept
        payload = payload or {}
        clean = lambda key, limit: " ".join(str(payload.get(key) or "").split())[:limit]
        if "title" in payload:
            card.update(title=clean("title", 80) or card.get("title"), greeting=clean("greeting", 40),
                        note=clean("note", 160), doing=clean("doing", 120))
            signed = clean("signed", 40)
            if signed:
                card["signed"] = signed
            else:
                card.pop("signed", None)
        style, theme = settings.get("style") or "polaroid", dict(settings.get("theme") or {})
        chosen_style = str(payload.get("style") or "")
        if chosen_style.casefold().startswith("theme:"):
            found = postcard_themes.themes(self.config).get(postcard_themes.clean_name(chosen_style[6:]))
            if found:
                style, theme = found["base"], dict(found)
        elif chosen_style.casefold() in POSTCARD_STYLES:
            style, theme = chosen_style.casefold(), {}
        if payload.get("angle") not in (None, ""):
            theme["angle"] = postcard_themes.normalize({"angle": payload.get("angle")})["angle"]
        postmark = bool(settings.get("postmark"))
        if "postmark" in payload:
            postmark = payload.get("postmark") in (True, "1", "on", "true")
        sizes = dict(settings.get("sizes") or {})
        for part in POSTCARD_TEXT_PARTS:
            if f"size_{part}" in payload:
                sizes[part] = postcard_text_size(payload.get(f"size_{part}")) / 100.0
        settings = {**settings, "sizes": sizes}
        return path, card, picture, style, theme, postmark, settings

    def _postcard_set_edit_draft(self, card_id, payload):
        if not card_id or self.postcard_album().path(card_id) is None:
            return False
        self._postcard_edit_draft = {"id": card_id, "values": dict(payload or {})}
        return True

    def _postcard_edit_preview(self):
        """The postcard being edited, with its changes, small, as a PNG."""
        draft = getattr(self, "_postcard_edit_draft", None)
        if not draft:
            return None
        key = repr(draft)
        cached = getattr(self, "_postcard_edit_preview_cache", None)
        if cached and cached[0] == key:
            return cached[1]
        edited = self._postcard_edited(draft["id"], draft["values"])
        if edited is None:
            return None
        import io

        from voidcompass.overlays.postcard_picture import render_postcard
        _path, card, picture, style, theme, postmark, settings = edited
        image = render_postcard(card, picture, settings.get("palette") or None, width=560, style=style,
                                theme=theme or None, background=self._postcard_background(theme), postmark=postmark,
                                sizes=settings.get("sizes"))
        out = io.BytesIO()
        image.save(out, "PNG")
        self._postcard_edit_preview_cache = (key, out.getvalue())
        return out.getvalue()

    def _postcard_swap_picture(self, card_id, chosen):
        """Give a saved postcard a different picture (or its first one)."""
        path = self.postcard_album().path(card_id)
        kept = kept_card(path) if path else None
        picture = open_picture(str(chosen or ""))
        if kept is None or picture is None:
            return False
        card, settings, _old = kept
        return keep_card(path, card, picture, settings)

    # -- Older postcards, made editable -----------------------------------------
    def _postcard_restore_start(self, card_ids=None):
        state = getattr(self, "_postcard_restore_state", None) or {}
        if state.get("running"):
            return False
        folder = self.postcard_album().folder()
        rows = [row for row in self.postcard_album().rows()
                if not is_editable(os.path.join(folder, row["file"])) and row["file"].lower().startswith("postcard - ")]
        if card_ids:
            rows = [row for row in rows if row["id"] in set(card_ids)]
        if not rows:
            return False
        self._postcard_restore_state = {"running": True, "done": 0, "total": len(rows), "pictures": 0, "found": 0}
        threading.Thread(target=self._postcard_restore_run, args=(folder, rows), name="postcard-restore", daemon=True).start()
        return True

    def _postcard_restore_run(self, folder, rows):
        state = self._postcard_restore_state
        config = self.config
        shots = str(config.get("screenshots_path") or "") or default_screenshot_path(config.get("journal_path"))
        moments = {row["id"]: saved_at(row["file"]) for row in rows}
        index = ScreenshotIndex(config.get("journal_path"), moments.values())
        options = postcard_options(config)
        palette = dict(themes.ACTIVE_PALETTE or {})
        try:
            for row in rows:
                moment = moments[row["id"]] or row.get("at") or time.time()
                found = index.near(moment, row["title"])
                picture = None
                if found:
                    at, raw, position = found
                    region, from_sol = "", None
                    if position is not None:
                        from_sol = sum(value * value for value in position) ** .5
                        named = find_region(*position)
                        region = named[1] if named else ""
                    card = postcard_card(raw, region=region, facts=postcard_facts(None, from_sol) if options["facts"] else [],
                                         now=at * 1000)
                    picture = open_picture(find_picture(shots, raw, at) or "")
                    state["found"] += 1
                else:
                    # Only its file name to go on: the place and when it was saved.
                    stamp = _datetime.datetime.fromtimestamp(moment, _datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    card = postcard_card({"timestamp": stamp}, body_name=row["title"], now=moment * 1000)
                # What you were doing then isn't in the journal's Screenshot.
                card.update(greeting=options["greeting"], note="", doing="")
                if picture is not None:
                    state["pictures"] += 1
                keep_card(os.path.join(folder, row["file"]), card, picture,
                          {"style": options["style"], "theme": options["theme"], "palette": palette,
                           "postmark": False, "restored": True})
                state["done"] += 1
        except Exception:
            logging.exception("Restoring older postcards stopped")
        finally:
            state["running"] = False
            self._postcard_album_cache = None
            publish = getattr(self, "_schedule_html_dashboard_publish", None)
            if callable(publish):
                self._ui_post(publish, immediate=True, key="postcard-album")
