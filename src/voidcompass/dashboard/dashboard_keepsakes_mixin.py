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
import threading
import time
from pathlib import Path

from voidcompass.core.platform_support import (
    application_dir,
    default_screenshot_path,
    open_path,
    repaired_screenshot_path,
)
from voidcompass.core import themes
from voidcompass.core.config import get_active_profile
from voidcompass.overlays.postcard_picture import jpeg_thumbnail, open_picture, save_postcard_picture
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


class DashboardKeepsakesMixin:

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
        if hud is not None:
            hud.post(card)
        wants_photo = hud is not None and postcard_options(self.config)["photo"]
        folder = str(self.config.get("screenshots_path") or "") or default_screenshot_path(self.config.get("journal_path"))
        threading.Thread(
            target=self._postcard_develop, args=(card, folder, wants_photo, captions, time.time()),
            kwargs={"keep": keep, "palette": dict(themes.ACTIVE_PALETTE or {})},
            name="postcard-photo", daemon=True,
        ).start()
        return card

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

    def _postcard_develop(self, card, folder, wants_photo, captions, taken_at, sleep=time.sleep,
                          keep=False, palette=None):
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
        if captions and path:
            self._postcard_caption(path, card)
        if keep and picture is not None:
            saved = save_postcard_picture(card, picture, postcards_folder(self.config), palette,
                                          style=postcard_options(self.config)["style"])
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
        return False

    def _html_postcards_workspace(self):
        """The deck's Postcards page: every postcard saved as a picture,
        newest first (read again at most every few seconds)."""
        cache = getattr(self, "_postcard_album_cache", None)
        now = time.monotonic()
        folder = postcards_folder(self.config)
        if not cache or cache[0] != folder or now - cache[1] > 4.0:
            cache = (folder, now, self.postcard_album().rows())
            self._postcard_album_cache = cache
        options = postcard_options(self.config)
        return {
            "folder": folder,
            "saving": bool(self.config.get("screenshot_postcards", False)),
            "rows": cache[2],
            # Everything about postcards, in one place (the overlay's own
            # options stay in Overlay Studio).
            "settings": {
                "postcard_style": options["style"],
                "postcard_facts": options["facts"],
                "postcard_note": options["note"],
                "postcard_doing": options["doing"],
                "screenshot_postcards": bool(self.config.get("screenshot_postcards", False)),
                "screenshot_captions": bool(self.config.get("screenshot_captions", False)),
                "postcards_path": str(self.config.get("postcards_path") or ""),
                "default_folder": postcards_folder({}),
            },
            "styles": list(POSTCARD_STYLES),
            "preview": self._postcard_preview_key(),
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
        if operation == "set":
            return self._postcard_setting(str(payload.get("key") or ""), payload.get("value"))
        return False

    # -- The Postcards page's preview ----------------------------------------
    def _postcard_preview_key(self):
        """Changes whenever the preview would look different."""
        options = postcard_options(self.config)
        palette = dict(themes.ACTIVE_PALETTE or {})
        return "-".join(str(part) for part in (
            options["style"], int(options["facts"]), int(options["note"]), int(options["doing"]),
            watcher_mind.personality(self.config), palette.get("accent", ""), palette.get("orange", ""),
            palette.get("text", ""))).replace("#", "")

    def _postcard_preview_picture(self):
        """Your latest screenshot for the preview, or a ship's picture."""
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
            picture = open_picture(path)
            if picture is not None:
                return picture
        return None

    def _postcard_preview_png(self):
        """A sample postcard in the current design, small, as a PNG."""
        import io
        key = self._postcard_preview_key()
        cached = getattr(self, "_postcard_preview_cache", None)
        if cached and cached[0] == key:
            return cached[1]
        from voidcompass.overlays.postcard_picture import render_postcard
        options = postcard_options(self.config)
        sample = {"planet_class": "Water world", "terraformable": True, "landable": True, "gravity_g": 1.02,
                  "was_discovered": False}
        card = postcard_card(
            {"timestamp": "2026-10-11T20:14:00Z", "System": "Hatchooe", "Body": "Hatchooe AB 3",
             "Latitude": 12.3457, "Longitude": -45.678},
            state="LANDED", region="Outer Scutum-Centaurus Arm",
            facts=postcard_facts(sample, 57904) if options["facts"] else [], kind=body_kind(sample))
        if not options["doing"]:
            card["doing"] = ""
        if options["note"]:
            import random
            card["note"] = postcard_note(card, watcher_mind.personality(self.config), 57904, "LANDED",
                                         rng=random.Random(7))
        image = render_postcard(card, self._postcard_preview_picture(), dict(themes.ACTIVE_PALETTE or {}),
                                width=560, style=options["style"])
        out = io.BytesIO()
        image.save(out, "PNG", optimize=True)
        data = out.getvalue()
        self._postcard_preview_cache = (key, data)
        return data

    _POSTCARD_SWITCHES = ("postcard_facts", "postcard_note", "postcard_doing", "screenshot_postcards", "screenshot_captions")

    def _postcard_setting(self, key, value):
        """One setting from the Postcards page, checked against its choices."""
        if key == "postcard_style":
            style = str(value or "").casefold()
            if style not in POSTCARD_STYLES:
                return False
            self.config[key] = style
        elif key in self._POSTCARD_SWITCHES:
            self.config[key] = value is True or str(value).casefold() in {"1", "true", "on"}
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
