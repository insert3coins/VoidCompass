"""The Galaxy Minimap and Postcards (5.5.3.7): feeding them from the app.

The minimap follows the travel history (every arrival), where the ship is
and where a plotted route ends. Postcards answer the journal's Screenshot
event: a card at once, then (on a background thread) the picture found,
shrunk and handed to the card, and with Settings > Caption files, the card's
words saved beside the picture.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
import zlib
from pathlib import Path

from voidcompass.core.platform_support import (
    application_dir,
    default_screenshot_path,
    open_path,
    repaired_screenshot_path,
)
from voidcompass.core import themes
from voidcompass.core.config import get_active_profile
from voidcompass.dashboard.dashboard_postcard_studio_mixin import DashboardPostcardStudioMixin
from voidcompass.overlays import postcard_themes
from voidcompass.overlays.postcard_picture import (
    _themed, card_colours, is_editable, jpeg_thumbnail, keep_card, kept_card, kept_info, needs_picture, open_picture,
    open_picture_small, save_postcard_picture,
)

# Postcard previews render one at a time: the studio asks for one on every
# change, and side by side they starved the app (5.5.5).
_PREVIEW_LOCK = threading.Lock()
from voidcompass.overlays.postcard_restore import saved_at
from voidcompass.exploration.galactic_regions import find_region
from voidcompass.overlays import watcher_mind
from voidcompass.overlays.postcards import (
    STYLES as POSTCARD_STYLES,
    THUMBNAIL_WIDTH,
    body_kind,
    caption_text,
    find_screenshot,
    postcard_card,
    postcard_facts,
    postcard_options,
)
from voidcompass.overlays.postcards import TEXT_PARTS as POSTCARD_TEXT_PARTS, text_size as postcard_text_size


def _whole(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
from voidcompass.overlays.watcher_postcards import postcard_note

# Postcards saved as pictures go in Void Compass's own folder (beside the
# EXE), not among the game's screenshots.
POSTCARD_FOLDER = "postcards"


def postcards_folder(config=None):
    """Settings > Screenshots > Postcard folder, or the postcards folder in
    Void Compass's own folder when none is set (5.5.3.7)."""
    chosen = str((config or {}).get("postcards_path") or "").strip()
    return chosen or str(application_dir() / POSTCARD_FOLDER)

# When to look for the picture after the event: the game writes it first,
# but a large high-resolution one can take a moment, and the screenshot
# converter may turn it into a PNG in between.
_PHOTO_TRIES_S = (0.3, 0.7, 1.5, 3.0, 5.0)


class DashboardKeepsakesMixin(DashboardPostcardStudioMixin):

    # -- The screenshot folder (5.5.3.7) -------------------------------------
    def _repair_screenshot_path(self):
        """Point at the folder Elite really saves to. With OneDrive (or other
        folder backup) Windows keeps Pictures in OneDrive, but Void Compass
        used to assume the user folder's Pictures and saved that guess, so it
        watched an empty or missing folder. A folder chosen in Settings that
        exists is left alone."""
        configured = str(self.config.get("screenshots_path") or "")
        found = repaired_screenshot_path(configured, self.config.get("journal_path"))
        if found and found != configured:
            self.config["screenshots_path"] = found
            if configured:
                logging.info("Screenshot folder moved from %s to %s", configured, found)
                log = getattr(self, "log", None)
                if callable(log):
                    log(f"📸 Screenshot folder found at {found}")
            persist = getattr(self, "_persist_config", None)
            if callable(persist):
                try:
                    persist()
                except Exception:
                    pass
            return True
        return False

    # -- Galaxy Minimap ------------------------------------------------------
    def _galaxy_minimap_position(self):
        """The ship's [x, y, z], when the journal has given one for the
        system it is in (0, 0, 0 is only believed in Sol)."""
        coords = getattr(self, "current_coords", None)
        system = str(getattr(self, "current_sys", "") or "")
        try:
            position = [float(value) for value in coords]
        except (TypeError, ValueError):
            return None
        if len(position) != 3 or not system or system == "---":
            return None
        if not any(position) and system.casefold() != "sol":
            return None
        return position

    def _update_galaxy_minimap(self):
        """This session's trail (from the travel history), where the ship is,
        and the plotted route (NavRoute.json), for the minimap."""
        hud = getattr(self, "galaxy_minimap_hud", None)
        if hud is None:
            return False
        history = getattr(self, "travel_history", None)
        session, rows, revision = [], [], None
        if history is not None:
            session = history.session_rows()
            with history.lock:
                rows, revision = list(history.rows), history.revision
        position = self._galaxy_minimap_position()
        system = getattr(self, "current_sys", "") or ""
        try:
            return hud.update(session, rows, revision, position, system,
                              list(getattr(self, "nav_route_entries", None) or []),
                              self._galaxy_minimap_trip(position, system),
                              self._galaxy_minimap_capsules())
        except Exception as exc:
            logging.debug("Galaxy minimap update skipped: %s", exc)
            return False

    def _galaxy_minimap_trip(self, position, system):
        """The whole trip from Spansh (5.5.3.7): the waypoint route, or this
        commander's latest neutron plot."""
        from voidcompass.overlays.galaxy_minimap_hud import spansh_trip
        manager = getattr(self, "waypoint_manager", None)
        plot = None
        state = getattr(self, "_html_explore_tool_state", None)
        if isinstance(state, dict) and state.get("profile") == get_active_profile(self.config):
            plot = state.get("route") if isinstance(state.get("route"), dict) else None
        try:
            return spansh_trip(list(getattr(manager, "waypoints", None) or []), plot, position, system)
        except Exception as exc:
            logging.debug("Galaxy minimap trip skipped: %s", exc)
            return None

    def _galaxy_minimap_capsules(self):
        """Where your sealed time capsules wait (dashboard_capsules_mixin)."""
        marks = getattr(self, "_capsule_marks", None)
        try:
            return marks() if callable(marks) else []
        except Exception as exc:
            logging.debug("Galaxy minimap capsules skipped: %s", exc)
            return []

    def _update_galaxy_minimap_safely(self):
        """After a route change from the deck (a neutron plot, waypoint
        edits): the minimap's trip again."""
        try:
            self._update_galaxy_minimap()
        except Exception as exc:
            logging.debug("Galaxy minimap refresh skipped: %s", exc)

    def _galaxy_minimap_next_view(self):
        """The minimap's view hotkey: Your route, Around you, Whole galaxy,
        round again (5.5.3.7). Kept like Overlay Studio's View setting."""
        from voidcompass.overlays.galaxy_minimap_hud import minimap_options, next_view
        view = next_view(minimap_options(self.config)["view"])
        self.config["galaxy_minimap_view"] = view
        persist = getattr(self, "_persist_config", None)
        if callable(persist):
            persist()
        hud = getattr(self, "galaxy_minimap_hud", None)
        if hud is not None:
            hud.apply_settings()
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=True)
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            names = {"route": "Your route", "local": "Around you", "galaxy": "Whole galaxy"}
            feed("SYSTEM", f"Galaxy Minimap: {names[view]}", severity="INFO")
        return view

    # -- Postcards ------------------------------------------------------------
    def _postcard_observe(self, event, raw, startup_replay=False):
        """A screenshot taken in game (live only, never from the replay)."""
        if event != "Screenshot" or startup_replay or not isinstance(raw, dict):
            return None
        hud = getattr(self, "postcard_hud", None)
        captions = bool(self.config.get("screenshot_captions", False))
        keep = bool(self.config.get("screenshot_postcards", False))
        if hud is None and not captions and not keep:
            return None
        self._postcard_serial = getattr(self, "_postcard_serial", 0) + 1
        state = str(getattr(self, "hud_flight_state", "") or "")
        station = getattr(self, "current_station_name", None) or ""
        body = str(raw.get("Body") or getattr(self, "current_body_name", "") or "")
        # Where in the galaxy, and what the journal knows of the place.
        position = self._galaxy_minimap_position()
        from_sol = region = None
        if position is not None:
            from_sol = sum(value * value for value in position) ** .5
            found = find_region(*position)
            region = found[1] if found else ""
        item = self._postcard_body(body)
        card = postcard_card(
            raw, state=state, system=getattr(self, "current_sys", "") or "",
            station=station if state in {"DOCKED", "ONFOOT"} else "",
            body_name=getattr(self, "current_body_name", "") or "", serial=self._postcard_serial,
            region=region or "", facts=postcard_facts(item, from_sol), kind=body_kind(item),
        )
        options = postcard_options(self.config)
        # The note reads the facts (a first discovery, a rare world), so it is
        # written before the facts come off the card.
        card["note"] = self._postcard_watcher_note(card, from_sol, state) if options["note"] else ""
        if options["note_mode"] == "own" and options["note_text"]:
            card["note"], card["signed"] = options["note_text"], self._postcard_signature(options)
            mind_note = None
        else:
            # 5.7.1: with its mind awake, its note in its own words, when they're back.
            mind_note = self._postcard_mind_note(card, from_sol)
        # The Watcher keeps every postcard (5.5.3.7).
        mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)
        if mind is not None and hasattr(mind, "keep_postcard"):
            try:
                mind.keep_postcard(card)
            except Exception as exc:
                logging.debug("The Watcher didn't keep the postcard: %s", exc)
        if not options["facts"]:
            card["facts"] = []
        if not options["doing"]:
            card["doing"] = ""
        card["greeting"] = options["greeting"]
        if hud is not None:
            hud.post(card)
        wants_photo = hud is not None and postcard_options(self.config)["photo"]
        folder = str(self.config.get("screenshots_path") or "") or default_screenshot_path(self.config.get("journal_path"))
        if mind_note is not None:
            threading.Thread(target=self._postcard_mind_wait, args=(card, mind_note),
                             name="postcard-note", daemon=True).start()
        threading.Thread(
            target=self._postcard_develop, args=(card, folder, wants_photo, captions, time.time()),
            kwargs={"keep": keep, "palette": dict(themes.ACTIVE_PALETTE or {}), "mind_note": mind_note},
            name="postcard-photo", daemon=True,
        ).start()
        return card

    def _postcard_signature(self, options):
        """How your own words are signed: your choice, or CMDR and your name."""
        if options.get("signature"):
            return options["signature"]
        name = str(getattr(self, "cmdr_name", "") or (self.config or {}).get("active_commander_name") or "").strip()
        return f"CMDR {name}" if name else "me"

    @staticmethod
    def _postcard_background(theme):
        path = postcard_themes.background_path(theme)
        return open_picture_small(str(path), 2400) if path else None

    def _postcard_body(self, name):
        """This system's scan of the body in the picture, if there is one."""
        wanted = str(name or "").casefold()
        if not wanted:
            return None
        for item in list(getattr(self, "scan_items", None) or ()):
            if str(item.get("name") or "").casefold() == wanted:
                found = dict(item)
                # Landable and gravity live with the planet's conditions.
                details = (getattr(self, "body_scan_data", None) or {}).get(item.get("body_id")) or {}
                for key in ("landable", "gravity_g"):
                    if found.get(key) is None and details.get(key) is not None:
                        found[key] = details[key]
                return found
        return None

    def _postcard_watcher_note(self, card, from_sol, state):
        """The Watcher's note for the card, in its nature's voice; none when
        its overlay or its thoughts are off."""
        if not self.config.get("heartbeat_overlay_enabled", True):
            return ""
        if watcher_mind.frequency(self.config) == "off":
            return ""
        recent = getattr(self, "_postcard_recent_notes", None)
        if recent is None:
            recent = self._postcard_recent_notes = []
        note = postcard_note(card, watcher_mind.personality(self.config), from_sol, state, recent=recent)
        if note:
            recent.append(note)
            del recent[:-12]
        return note

    def _postcard_mind_note(self, card, from_sol):
        """5.7.1: the Watcher's note in its own words, asked for now; None
        with its mind asleep (or no note wanted), and the written one stays."""
        mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)
        llm = getattr(mind, "llm", None)
        if not card.get("note") or llm is None or not llm.rewording() or not llm.ready():
            return None
        facts = {"place": card.get("title"), "system": card.get("place"), "kind": str(card.get("kind") or "").lower(),
                 "region": card.get("region"), "doing": card.get("doing"),
                 "distance from Sol": f"{float(from_sol):,.0f} light years" if from_sol is not None else "",
                 "about it": "; ".join(self._postcard_fact_for_mind(fact) for fact in card.get("facts") or ())}
        try:
            return llm.postcard({key: value for key, value in facts.items() if value}, card["note"],
                                watcher_mind.personality(self.config), forbidden=mind._unsayable_names())
        except Exception as exc:
            logging.debug("The Watcher's own postcard note skipped: %s", exc)
            return None

    @staticmethod
    def _postcard_fact_for_mind(fact):
        """A card fact as the model should read it: it can't tell 0.21 g is light."""
        fact = str(fact)
        match = re.fullmatch(r"(\d+(?:\.\d+)?) [gG]", fact.strip())
        if match:
            gravity = float(match.group(1))
            return f"{fact} ({'light' if gravity < .5 else 'heavy' if gravity > 1.5 else 'about Earth'} gravity)"
        return fact

    def _postcard_mind_wait(self, card, job):
        """Its own words for the note, once back (in time): on the card, and
        on the overlay if it's still showing. True when used."""
        if job is None or not job.done.wait(job.wait + 1) or not job.ok:
            return False
        if card.get("note") != job.text:
            card["note"] = job.text
            hud = getattr(self, "postcard_hud", None)
            if hud is not None and hasattr(hud, "set_note"):
                self._ui_post(hud.set_note, card["id"], job.text, key=None)
        return True

    def _postcard_develop(self, card, folder, wants_photo, captions, taken_at, sleep=time.sleep,
                          keep=False, palette=None, mind_note=None):
        """Find the picture (read once): shrink it for the card, write its
        caption, and with Settings > Save postcards as pictures, draw the
        postcard into a PNG in the postcards folder in Void Compass's own
        folder."""
        path, photo, picture = None, None, None
        for delay in _PHOTO_TRIES_S:
            sleep(delay)
            path = find_screenshot(folder, card.get("file"), taken_at)
            if path is None:
                continue
            if not wants_photo and not keep:
                break
            picture = open_picture(path)
            if picture is not None:
                break
        if picture is not None and wants_photo:
            photo = jpeg_thumbnail(picture, THUMBNAIL_WIDTH)
            hud = getattr(self, "postcard_hud", None)
            if hud is not None:
                self._ui_post(hud.attach_photo, card["id"], photo, key=None)
        # The caption and the saved picture carry its own words, once back.
        self._postcard_mind_wait(card, mind_note)
        if captions and path:
            self._postcard_caption(path, card)
        if keep and picture is not None:
            options = postcard_options(self.config)
            saved = save_postcard_picture(card, picture, postcards_folder(self.config), palette,
                                          style=options["style"], theme=options["theme"],
                                          background=self._postcard_background(options["theme"]),
                                          postmark=options["postmark"], sizes=options["sizes"])
            if saved:
                # Kept beside it, so it can be edited later (5.5.4).
                keep_card(saved, card, picture, {"style": options["style"], "theme": options["theme"],
                                                 "palette": dict(palette or {}), "postmark": options["postmark"],
                                                 "sizes": options["sizes"]})
            if saved:
                logging.info("Postcard saved: %s", saved)
                # The album shows it at once.
                publish = getattr(self, "_schedule_html_dashboard_publish", None)
                if callable(publish):
                    self._ui_post(publish, immediate=True, key="postcard-album")
            else:
                logging.warning("Postcard not saved in %s", postcards_folder(self.config))
        return path, photo

    # -- The postcard album (5.5.3.7) ------------------------------------------
    def postcard_album(self):
        album = getattr(self, "_postcard_album_instance", None)
        if album is None:
            from voidcompass.services.postcard_album import PostcardAlbum
            album = PostcardAlbum(lambda: postcards_folder(getattr(self, "config", None)))
            album.preview_source = self._postcard_preview_png
            album.favourites = self.keepsake_favourites()
            self._postcard_album_instance = album
        return album

    def keepsake_favourites(self):
        """The stars on the Postcards and Screenshots pages (5.5.3.7), kept in
        keepsakes.json in Void Compass's own folder."""
        favourites = getattr(self, "_keepsake_favourites", None)
        if favourites is None:
            from voidcompass.services.postcard_album import Favourites
            favourites = Favourites(application_dir() / "keepsakes.json")
            self._keepsake_favourites = favourites
        return favourites

    def _attach_postcard_album(self, runtime):
        server = getattr(runtime, "server", None)
        if server is not None:
            server.postcards = self.postcard_album()
            server.screenshots = self.screenshot_album()
            server.constellations = self.constellation_album()
            server.postcard_saver = self._postcard_design_save
            # Void Wrapped, the book, the recorder and system tunes (5.5.10).
            data = getattr(self, "_html_data", None)
            if callable(data):
                server.data_provider = data

    # -- The Screenshots page (5.5.3.7) ----------------------------------------
    def _screenshot_folder(self):
        config = getattr(self, "config", None) or {}
        return str(config.get("screenshots_path") or "") or default_screenshot_path(config.get("journal_path"))

    def screenshot_album(self):
        album = getattr(self, "_screenshot_album_instance", None)
        if album is None:
            from voidcompass.services.screenshot_album import ScreenshotAlbum
            album = ScreenshotAlbum(self._screenshot_folder)
            album.favourites, album.favourites_kind = self.keepsake_favourites(), "screenshots"
            self._screenshot_album_instance = album
        return album

    def _html_screenshots_workspace(self):
        """The deck's Screenshots page: the screenshot folder, newest first
        (read again at most every few seconds)."""
        cache = getattr(self, "_screenshot_album_cache", None)
        now = time.monotonic()
        folder = self._screenshot_folder()
        album = self.screenshot_album()
        if not cache or cache[0] != folder or now - cache[1] > 4.0:
            cache = (folder, now, album.rows(), album.total)
            self._screenshot_album_cache = cache
        return {
            "folder": folder,
            "found": os.path.isdir(folder),
            "converting": bool(self.config.get("screenshots_enabled", False)),
            "rows": cache[2],
            "total": cache[3],
        }

    def _handle_screenshots_command(self, operation, payload):
        album = self.screenshot_album()
        card_id = str((payload or {}).get("id") or "")[:16]
        self._screenshot_album_cache = None
        if operation == "open_folder":
            opener = getattr(self, "open_screenshots_folder", None)
            if callable(opener):
                opener()
                return True
            return False
        if operation == "show":
            return album.show_in_folder(card_id)
        if operation == "favourite":
            return album.set_favourite(card_id, (payload or {}).get("value") is True)
        if operation == "copy":
            done = album.copy(card_id)
            feed = getattr(self, "add_event_feed_entry", None)
            if callable(feed):
                feed("SYSTEM", "Screenshot copied: paste it anywhere" if done else "The screenshot couldn't be copied",
                     severity="INFO" if done else "WARN")
            return done
        if operation == "postcard":
            return self._postcard_from_screenshot(card_id)
        return False

    def _postcard_from_screenshot(self, shot_id):
        """Any screenshot as a new postcard: the place from its name, the
        day and time from the file; then it opens in the editor."""
        album = self.screenshot_album()
        path = album.path(shot_id)
        picture = open_picture(path) if path else None
        if picture is None:
            return False
        row = next((item for item in album.rows() if item["id"] == shot_id), {})
        taken = os.path.getmtime(path)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(taken))
        system = str(row.get("system") or "")
        card = postcard_card({"System": system, "timestamp": stamp}, system=system, serial=0, now=int(taken * 1000))
        card["greeting"] = postcard_options(self.config)["greeting"]
        options = postcard_options(self.config)
        palette = dict(themes.ACTIVE_PALETTE or {})
        saved = save_postcard_picture(card, picture, postcards_folder(self.config), palette, style=options["style"],
                                      theme=options["theme"], postmark=options["postmark"], sizes=options["sizes"])
        if not saved:
            return False
        keep_card(saved, card, picture, {"style": options["style"], "theme": options["theme"], "palette": palette,
                                         "postmark": options["postmark"], "sizes": options["sizes"]})
        from voidcompass.services.postcard_album import postcard_id
        self._postcard_open_next = postcard_id(os.path.basename(saved))
        self._postcard_album_cache = None
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=True)
        return True

    def _html_postcards_workspace(self):
        """The deck's Postcards page: every postcard saved as a picture,
        newest first (read again at most every few seconds)."""
        cache = getattr(self, "_postcard_album_cache", None)
        now = time.monotonic()
        folder = postcards_folder(self.config)
        if not cache or cache[0] != folder or now - cache[1] > 4.0:
            rows = self.postcard_album().rows()
            for row in rows:
                # Saved from 5.5.4 on (or restored): it can be drawn again.
                row["editable"] = is_editable(os.path.join(folder, row["file"]))
                row["needs_picture"] = row["editable"] and needs_picture(os.path.join(folder, row["file"]))
                row["taken"] = saved_at(row["file"]) or row["at"]
                info = kept_info(os.path.join(folder, row["file"])) if row["editable"] else None
                card = (info or {}).get("card") or {}
                row.update(system=str(card.get("place") or card.get("title") or row["title"]), region=str(card.get("region") or ""),
                           note=str(card.get("note") or "")[:160], designed=bool(((info or {}).get("settings") or {}).get("design")))
            cache = (folder, now, rows)
            self._postcard_album_cache = cache
        options = postcard_options(self.config)
        return {
            "folder": folder,
            "saving": bool(self.config.get("screenshot_postcards", False)),
            "rows": cache[2],
            # Everything about postcards, in one place (the overlay's own
            # options stay in Overlay Studio).
            "settings": {
                "postcard_style": str(self.config.get("postcard_style") or options["style"]),
                "postcard_note_mode": options["note_mode"],
                "postcard_note_text": options["note_text"],
                "postcard_signature": options["signature"],
                "postcard_facts": options["facts"],
                "postcard_note": options["note"],
                "postcard_doing": options["doing"],
                "postcard_postmark": options["postmark"],
                **{f"postcard_size_{part}": round(options["sizes"][part] * 100) for part in options["sizes"]},
                "postcard_greeting": str(self.config.get("postcard_greeting") or "greetings"),
                "postcard_greeting_text": str(self.config.get("postcard_greeting_text") or ""),
                "screenshot_postcards": bool(self.config.get("screenshot_postcards", False)),
                "screenshot_captions": bool(self.config.get("screenshot_captions", False)),
                "postcards_path": str(self.config.get("postcards_path") or ""),
                "default_folder": postcards_folder({}),
            },
            "styles": list(POSTCARD_STYLES),
            "preview": self._postcard_preview_key(),
            # Your own themes (5.5.4), and the postcard being edited.
            "themes": postcard_themes.themes(self.config),
            "theme_choices": {"bases": list(postcard_themes.BASES), "fonts": list(postcard_themes.FONTS),
                              "filters": list(postcard_themes.FILTERS)},
            "editing": dict(getattr(self, "_postcard_editing", None) or {}),
            # Older postcards being given their card back.
            "restore": dict(getattr(self, "_postcard_restore_state", None) or {}),
            # Made from a screenshot on its page: the editor opens on it.
            "open_next": str(getattr(self, "_postcard_open_next", "") or ""),
        }

    def _handle_postcards_command(self, operation, payload):
        album = self.postcard_album()
        card_id = str((payload or {}).get("id") or "")[:16]
        self._postcard_album_cache = None
        if operation == "open_folder":
            return bool(self.open_postcards_folder())
        if operation == "show":
            return album.show_in_folder(card_id)
        if operation == "favourite":
            return album.set_favourite(card_id, (payload or {}).get("value") is True)
        if operation == "copy":
            done = album.copy(card_id)
            feed = getattr(self, "add_event_feed_entry", None)
            if callable(feed):
                feed("SYSTEM", "Postcard copied: paste it anywhere" if done else "The postcard couldn't be copied",
                     severity="INFO" if done else "WARN")
            return done
        if operation == "delete":
            done = album.delete(card_id)
            feed = getattr(self, "add_event_feed_entry", None)
            if callable(feed):
                feed("SYSTEM", "Postcard moved to the Recycle Bin" if done else "The postcard couldn't be deleted",
                     severity="INFO" if done else "WARN")
            return done
        if operation == "set":
            return self._postcard_setting(str(payload.get("key") or ""), payload.get("value"))
        if operation == "save_theme":
            return self._postcard_save_theme(payload)
        if operation == "delete_theme":
            return self._postcard_delete_theme(str(payload.get("name") or ""))
        if operation == "edit":
            return self._postcard_edit_open(card_id)
        if operation == "edit_close":
            self._postcard_editing = self._postcard_edit_draft = None
            return True
        if operation == "edit_save":
            return self._postcard_edit_save(card_id, payload)
        # The studio (5.5.4): previews tried out, pictures swapped, older
        # postcards made editable.
        if operation == "draft":
            return self._postcard_set_draft(payload)
        if operation == "draft_clear":
            self._postcard_draft = None
            return True
        if operation == "edit_draft":
            return self._postcard_set_edit_draft(card_id, payload)
        if operation == "edit_picture":
            return self._postcard_swap_picture(card_id, payload.get("path"))
        if operation == "edit_photo":
            # Another screenshot from the album, or a file you chose (5.6.3).
            shot = str(payload.get("shot") or "")[:16]
            chosen = self.screenshot_album().path(shot) if shot else payload.get("path")
            return bool(chosen) and self._postcard_swap_picture(card_id, chosen)
        if operation == "opened":
            self._postcard_open_next = ""
            return True
        if operation == "restore":
            return self._postcard_restore_start([card_id] if card_id else None)
        return False

    # -- Your own themes (5.5.4) ----------------------------------------------
    def _postcard_save_theme(self, payload):
        name = postcard_themes.clean_name(payload.get("name"))
        if not name:
            return False
        saved = dict(self.config.get("postcard_themes") or {})
        if name not in saved and len(saved) >= postcard_themes.THEMES_MAX:
            return False
        params = postcard_themes.normalize(payload.get("params"))
        picture = str(payload.get("background_data") or "")
        if picture.startswith("data:image/"):
            import base64
            try:
                data = base64.b64decode(picture.split(",", 1)[1], validate=False)
            except (ValueError, IndexError):
                return False
            filename = postcard_themes.save_background(name, data)
            if not filename:
                return False
            params.update(background="image", bg_image=filename)
        elif params["background"] == "image" and not params["bg_image"]:
            params["bg_image"] = (saved.get(name) or {}).get("bg_image", "")
        saved[name] = params
        self.config["postcard_themes"] = saved
        self.config["postcard_style"] = f"theme:{name}"
        return self._postcard_settings_saved()

    def _postcard_delete_theme(self, name):
        name = postcard_themes.clean_name(name)
        saved = dict(self.config.get("postcard_themes") or {})
        if name not in saved:
            return False
        image = postcard_themes.background_path(postcard_themes.normalize(saved.pop(name)))
        if image:
            try:
                image.unlink()
            except OSError:
                pass
        self.config["postcard_themes"] = saved
        if str(self.config.get("postcard_style") or "") == f"theme:{name}":
            self.config["postcard_style"] = postcard_themes.normalize(saved.get(name) or {})["base"]
        return self._postcard_settings_saved()

    def _postcard_settings_saved(self):
        persist = getattr(self, "_persist_config", None)
        if callable(persist):
            persist()
        hud = getattr(self, "postcard_hud", None)
        if hud is not None and hasattr(hud, "apply_settings"):
            hud.apply_settings()
        self._postcard_preview_cache = None
        return True

    # -- Editing a saved postcard (5.5.4) ---------------------------------------
    def _postcard_edit_open(self, card_id):
        path = self.postcard_album().path(card_id)
        kept = kept_card(path) if path else None
        if kept is None:
            return False
        card, settings, picture = kept
        theme = settings.get("theme") or {}
        self._postcard_editing = {
            "id": card_id, "title": card.get("title") or "", "greeting": card.get("greeting", "Greetings from"),
            "note": card.get("note") or "", "signed": card.get("signed") or "",
            "style": f"theme:{theme['name']}" if theme.get("name") else settings.get("style") or "polaroid",
            "base": settings.get("style") or "polaroid", "angle": theme.get("angle"),
            "doing": card.get("doing") or "",
            "postmark": bool(settings.get("postmark")),
            "sizes": {part: round(float((settings.get("sizes") or {}).get(part) or 1.0) * 100) for part in POSTCARD_TEXT_PARTS},
            "photo": picture is not None,
            # The editor (5.6.3) draws the card itself from these.
            "info": {key: card.get(key) for key in ("title", "place", "region", "greeting", "note", "signed", "doing",
                                                    "coordinates", "date", "time", "facts", "kind")}
                    | {"system": card.get("place") or card.get("title") or "", "photo": picture is not None,
                       "postmark": bool(settings.get("postmark")), "base": settings.get("style") or "polaroid",
                       "sizes": {part: round(float((settings.get("sizes") or {}).get(part) or 1.0) * 100) for part in POSTCARD_TEXT_PARTS}},
            "design": settings.get("design") if isinstance(settings.get("design"), dict) else None,
            "looks": self._postcard_looks(settings.get("palette") or None, theme),
            "shots": [{"id": row["id"], "title": row.get("title") or ""} for row in self.screenshot_album().rows()[:48]],
        }
        self._postcard_edit_draft = None
        return True

    @staticmethod
    def _postcard_looks(palette, theme):
        """Each of the four looks' paper, ink and lettering, as hex, with the
        card's own theme over the one it was built on."""
        def hexed(colour):
            return "#%02x%02x%02x" % tuple(colour[:3])
        looks = {}
        for base in ("polaroid", "airmail", "holo", "vintage"):
            colours = card_colours(palette, base)
            if theme and (theme.get("base") or "polaroid") == base:
                colours = _themed(colours, theme)
            looks[base] = {key: hexed(colours[key]) for key in ("paper", "ink", "soft", "greet")}
            if theme and (theme.get("base") or "polaroid") == base:
                looks[base].update({key: theme[key] for key in ("font", "filter", "angle", "background", "bg_colour") if theme.get(key) not in (None, "")})
        return looks

    def _postcard_design_save(self, payload):
        """The editor's drawing, from the deck server's save route: over the
        postcard, or as a new one beside it."""
        import base64
        if payload.get("mode") == "snap":
            # The Hatchling's SNAP (5.6.4): its pod as a new postcard.
            try:
                png = base64.b64decode(str(payload.get("png") or ""), validate=True)
            except ValueError:
                return {"ok": False, "error": "not a picture"}
            saved = self._hatchling_snap(png) if hasattr(self, "_hatchling_snap") else None
            return {"ok": True, "id": saved} if saved else {"ok": False, "error": "not saved"}
        card_id = str(payload.get("id") or "")[:16]
        design = payload.get("design")
        if not isinstance(design, dict) or len(str(design)) > 400_000:
            return {"ok": False, "error": "no design"}
        try:
            png = base64.b64decode(str(payload.get("png") or ""), validate=True)
        except ValueError:
            return {"ok": False, "error": "not a picture"}
        saved = self.postcard_album().save_design(card_id, png, design, as_new=payload.get("mode") == "new")
        if not saved:
            return {"ok": False, "error": "not saved"}
        self._postcard_album_cache = None
        self._postcard_editing = None
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            self._ui_post(publish, immediate=True, key="postcard-album")
        return {"ok": True, "id": saved}

    def _postcard_edit_save(self, card_id, payload):
        edited = self._postcard_edited(card_id, payload)
        if edited is None:
            return False
        path, card, picture, style, theme, postmark, settings = edited
        sizes = settings.get("sizes") or {}
        saved = save_postcard_picture(card, picture, os.path.dirname(path), settings.get("palette") or None,
                                      style=style, theme=theme or None, background=self._postcard_background(theme),
                                      path=path, postmark=postmark, sizes=sizes)
        if not saved:
            return False
        keep_card(saved, card, picture, {"style": style, "theme": theme, "palette": settings.get("palette") or {},
                                         "postmark": postmark, "sizes": sizes})
        self._postcard_editing = self._postcard_edit_draft = None
        album = self.postcard_album()
        forget = getattr(album, "forget_thumb", None)
        if callable(forget):
            forget(card_id)
        return True

    # -- The Postcards page's preview ----------------------------------------
    def _postcard_preview_key(self):
        """Changes whenever the preview would look different."""
        options = postcard_options(self._postcard_preview_config())
        palette = dict(themes.ACTIVE_PALETTE or {})
        return "-".join(str(part) for part in (
            options["style"], int(options["facts"]), int(options["note"]), int(options["doing"]),
            "t" + format(zlib.crc32(repr((options["theme"], options["note_mode"], options["note_text"],
                                          options["signature"])).encode("utf-8")), "08x"),
            "g" + format(zlib.crc32(options["greeting"].encode("utf-8")), "08x"), int(options["postmark"]),
            watcher_mind.personality(self.config), palette.get("accent", ""), palette.get("orange", ""),
            palette.get("text", ""))).replace("#", "")

    def _postcard_preview_picture(self):
        """Your latest screenshot for the preview, or a ship's picture: found
        at most every half minute, read once and kept small."""
        found = getattr(self, "_postcard_preview_found", None)
        if found and time.monotonic() - found[0] < 30:
            picture = open_picture_small(found[1], 1280) if found[1] else None
            if picture is not None:
                return picture
        folder = str(self.config.get("screenshots_path") or "")
        newest = None
        try:
            for name in os.listdir(folder):
                if name.lower().endswith((".png", ".bmp", ".jpg")):
                    path = os.path.join(folder, name)
                    modified = os.path.getmtime(path)
                    if newest is None or modified > newest[0]:
                        newest = (modified, path)
        except OSError:
            newest = None
        candidates = [newest[1]] if newest else []
        for base in (application_dir(), Path(__file__).resolve().parents[3]):
            ships = sorted((Path(base) / "assets" / "images" / "ships").glob("*.png"))
            if ships:
                candidates.append(str(ships[min(3, len(ships) - 1)]))
                break
        for path in candidates:
            picture = open_picture_small(path, 1280)
            if picture is not None:
                self._postcard_preview_found = (time.monotonic(), path)
                return picture
        return None

    def _postcard_preview_png(self):
        """A sample postcard in the current design, small, as a PNG. One
        render at a time; one asked for meanwhile finds it ready."""
        with _PREVIEW_LOCK:
            return self._postcard_preview_render()

    def _postcard_preview_render(self):
        import io
        # Editing a saved postcard: that card, with its changes.
        edited = self._postcard_edit_preview()
        if edited:
            return edited
        key = self._postcard_preview_key()
        cached = getattr(self, "_postcard_preview_cache", None)
        if cached and cached[0] == key:
            return cached[1]
        from voidcompass.overlays.postcard_picture import render_postcard
        options = postcard_options(self._postcard_preview_config())
        sample = {"planet_class": "Water world", "terraformable": True, "landable": True, "gravity_g": 1.02,
                  "was_discovered": False}
        card = postcard_card(
            {"timestamp": "2026-10-11T20:14:00Z", "System": "Hatchooe", "Body": "Hatchooe AB 3",
             "Latitude": 12.3457, "Longitude": -45.678},
            state="LANDED", region="Outer Scutum-Centaurus Arm",
            facts=postcard_facts(sample, 57904) if options["facts"] else [], kind=body_kind(sample))
        if not options["doing"]:
            card["doing"] = ""
        card["greeting"] = options["greeting"]
        if options["note"]:
            import random
            card["note"] = postcard_note(card, watcher_mind.personality(self.config), 57904, "LANDED",
                                         rng=random.Random(7))
        if options["note_mode"] == "own" and options["note_text"]:
            card["note"], card["signed"] = options["note_text"], self._postcard_signature(options)
        image = render_postcard(card, self._postcard_preview_picture(), dict(themes.ACTIVE_PALETTE or {}),
                                width=560, style=options["style"], theme=options["theme"],
                                background=self._postcard_background(options["theme"]), postmark=options["postmark"],
                                sizes=options["sizes"])
        out = io.BytesIO()
        image.save(out, "PNG", optimize=True)
        data = out.getvalue()
        self._postcard_preview_cache = (key, data)
        return data

    _POSTCARD_SWITCHES = ("postcard_facts", "postcard_note", "postcard_doing", "postcard_postmark",
                          "screenshot_postcards", "screenshot_captions")
    _POSTCARD_GREETINGS = ("greetings", "wish", "custom", "none")

    def _postcard_setting(self, key, value):
        """One setting from the Postcards page, checked against its choices."""
        if key == "postcard_style":
            style = str(value or "")
            if style.casefold().startswith("theme:"):
                if postcard_themes.clean_name(style[6:]) not in postcard_themes.themes(self.config):
                    return False
                self.config[key] = f"theme:{postcard_themes.clean_name(style[6:])}"
            elif style.casefold() in POSTCARD_STYLES:
                self.config[key] = style.casefold()
            else:
                return False
        elif key == "postcard_note_mode":
            mode = str(value or "").casefold()
            if mode not in postcard_themes.NOTE_MODES:
                return False
            self.config[key] = mode
            self.config["postcard_note"] = mode == "watcher"
        elif key == "postcard_note_text":
            self.config[key] = " ".join(str(value or "").split())[:160]
        elif key == "postcard_signature":
            self.config[key] = " ".join(str(value or "").split())[:40]
        elif key in self._POSTCARD_SWITCHES:
            self.config[key] = value is True or str(value).casefold() in {"1", "true", "on"}
        elif key == "postcard_greeting":
            greeting = str(value or "").casefold()
            if greeting not in self._POSTCARD_GREETINGS:
                return False
            self.config[key] = greeting
        elif key == "postcard_greeting_text":
            self.config[key] = " ".join(str(value or "").split())[:40]
        elif key in {f"postcard_size_{part}" for part in POSTCARD_TEXT_PARTS}:
            size = postcard_text_size(value)
            if size != _whole(value):
                return False
            self.config[key] = size
        elif key == "postcards_path":
            self.config[key] = str(value or "").strip()[:400]
            self._postcard_album_cache = None
        else:
            return False
        persist = getattr(self, "_persist_config", None)
        if callable(persist):
            persist()
        hud = getattr(self, "postcard_hud", None)
        if hud is not None and hasattr(hud, "apply_settings"):
            hud.apply_settings()
        return True

    def open_postcards_folder(self):
        """Settings > Screenshots > OPEN POSTCARDS (made if need be)."""
        folder = postcards_folder(getattr(self, "config", None))
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            return False
        return bool(open_path(folder))

    def _postcard_caption(self, path, card):
        """The card in words beside the picture. A BMP the converter is about
        to turn into a PNG gets its caption when the PNG is written."""
        text = caption_text(card)
        handler = getattr(self, "screenshots", None)
        try:
            if (path.lower().endswith(".bmp") and self.config.get("screenshots_enabled", False)
                    and hasattr(handler, "add_caption")):
                handler.add_caption(os.path.basename(path), text)
                return
            with open(os.path.splitext(path)[0] + ".txt", "w", encoding="utf-8") as caption:
                caption.write(text)
        except OSError as exc:
            logging.warning("Screenshot caption not written for %s: %s", path, exc)
