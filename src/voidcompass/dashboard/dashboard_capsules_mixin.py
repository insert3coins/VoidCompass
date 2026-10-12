"""Time capsules, On this day and your constellation (5.5.3.7), for
MainDashboard.

Leave a note for a system on the deck's Time Capsules page; it is handed
back when you next jump in there (by the Watcher, or as a notice), or told
"not yet" when you sealed it for later. On this day: where you were on this
date in years gone by, with the postcards you took that day. Your
constellation: a star per session, named by the Watcher when one is done.
Each page keeps its own settings (per commander).
"""
from __future__ import annotations

import base64
from datetime import datetime
import io
import logging
import math
import os
import re
import time

from voidcompass.core.config import get_active_profile, get_profile_dir
from voidcompass.exploration.constellation import (
    DWELL_CAP_S, SHAPES, SOURCES, constellation_options, constellations,
)
from voidcompass.exploration.time_capsules import WAITS, CapsuleStore, on_this_day, span_text, years_text
from voidcompass.overlays import watcher_mind

# A constellation saved as a picture: the page's drawing (a JPEG or PNG, at
# most this big on the way), kept as a PNG.
CONSTELLATION_PICTURE_MAX = 1536 * 1024

# Arrivals by travel: a capsule waits for you to come back. Logging in where
# it was left opens it only with "Open when I log in there" on.
CAPSULE_ARRIVALS = ("FSDJump", "CarrierJump")

# Each page's settings: key -> (kind, choices or (low, high), default).
CAPSULE_SETTINGS = {
    "capsule_delivery": ("choice", ("both", "notice", "watcher"), "both"),
    "capsule_open_on_login": ("bool", None, False),
    "capsule_notice_s": ("choice", (10, 25, 45, 60), 25),
    "capsule_blur_sealed": ("bool", None, True),
    "on_this_day_watcher": ("bool", None, True),
}
CONSTELLATION_SETTINGS = {
    "constellation_stars": ("range", (5, 12), 9),
    "constellation_linger_min": ("choice", (5, 10, 20, 30, 60), 10),
    "constellation_source": ("choice", SOURCES, "session"),
    "constellation_shape": ("choice", SHAPES, "branching"),
    "constellation_names": ("bool", None, True),
    "constellation_lines": ("choice", ("accent", "white", "gold"), "accent"),
    "constellation_picture": ("choice", (1600, 2560, 3840), 1600),
    "constellation_picture_legend": ("bool", None, True),
    "constellation_watcher": ("bool", None, True),
}


def setting_value(config, key, spec):
    """A page setting from the config, kept to its choices."""
    kind, choices, default = spec
    value = (config or {}).get(key, default)
    if kind == "bool":
        return value is True or str(value).casefold() in {"1", "true", "on"}
    if kind == "range":
        try:
            return max(choices[0], min(choices[1], int(float(value))))
        except (TypeError, ValueError):
            return default
    if isinstance(default, int):
        try:
            value = int(float(value))
        except (TypeError, ValueError):
            return default
    else:
        value = str(value or "").casefold()
    return value if value in choices else default


def wait_text(seconds):
    """How long until a capsule opens, always with a number ("1 day",
    "3 weeks"): the Watcher may start a sentence with it."""
    days = max(0.0, float(seconds)) / 86400
    if days < 1:
        hours = max(1, math.ceil(days * 24))
        return f"{hours} hour{'' if hours == 1 else 's'}"
    if days < 14:
        whole = math.ceil(days)
        return f"{whole} day{'' if whole == 1 else 's'}"
    if days < 60:
        return f"{math.ceil(days / 7)} weeks"
    if days < 365:
        return f"{math.ceil(days / 30.44)} months"
    years = round(days / 365.25, 1)
    return "1 year" if years <= 1.05 else f"{years:g} years"


class DashboardCapsulesMixin:
    def capsule_store(self):
        store = getattr(self, "_capsule_store", None)
        if store is None:
            store = CapsuleStore(lambda: get_profile_dir(get_active_profile(getattr(self, "config", None) or {})))
            self._capsule_store = store
        return store

    def _keepsake_setting(self, key):
        spec = CAPSULE_SETTINGS.get(key) or CONSTELLATION_SETTINGS[key]
        return setting_value(getattr(self, "config", None), key, spec)

    def _set_keepsake_setting(self, settings, key, value):
        """One setting from the Time Capsules or Constellation page, kept to
        its choices and saved."""
        spec = settings.get(str(key or ""))
        if spec is None:
            return False
        kind, choices, default = spec
        if kind == "bool":
            checked = value is True or str(value).casefold() in {"1", "true", "on"}
        else:
            try:
                checked = int(float(value)) if isinstance(default, int) else str(value or "").casefold()
            except (TypeError, ValueError):
                return False
            if kind == "range" and not choices[0] <= checked <= choices[1]:
                return False
            if kind == "choice" and checked not in choices:
                return False
        self.config[key] = checked
        persist = getattr(self, "_persist_config", None)
        if callable(persist):
            persist()
        if settings is CONSTELLATION_SETTINGS:
            self._constellation_cache = None
        return True

    # -- Arriving ---------------------------------------------------------------
    def _capsule_arrival(self, event, raw, startup_replay=False):
        """A live arrival: open the capsules left for this system, or say
        "not yet" for the ones sealed for later."""
        arrivals = CAPSULE_ARRIVALS + (("Location",) if self._keepsake_setting("capsule_open_on_login") else ())
        if startup_replay or event not in arrivals or not isinstance(raw, dict):
            return []
        system = str(raw.get("StarSystem") or "")
        try:
            arrived = datetime.fromisoformat(str(raw.get("timestamp")).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            arrived = time.time()
        store = self.capsule_store()
        try:
            position = raw.get("StarPos")
            if isinstance(position, (list, tuple)) and len(position) >= 3:
                store.set_coords(system, position)  # for the minimap's marks
            opened = store.deliver(system, arrived)
            early = store.early(system, arrived) if not opened else []
        except Exception as exc:
            logging.debug("Time capsules skipped: %s", exc)
            return []
        for index, capsule in enumerate(opened):
            self._hand_back_capsule(capsule, watcher=index == 0)
        if early:
            soonest = min(float(capsule["not_before"]) for capsule in early)
            self._capsule_not_yet(system, soonest - arrived)
        if opened:
            publish = getattr(self, "_schedule_html_dashboard_publish", None)
            if callable(publish):
                publish(immediate=True)
            update_minimap = getattr(self, "_update_galaxy_minimap_safely", None)
            if callable(update_minimap):
                update_minimap()
        return opened

    def _watcher_says(self, kind, fields):
        heartbeat = getattr(self, "heartbeat_hud", None)
        if heartbeat is None or not hasattr(heartbeat, "note"):
            return None
        try:
            return heartbeat.note(kind, fields)
        except Exception as exc:
            logging.debug("Watcher %s skipped: %s", kind, exc)
            return None

    def _notice(self, title, message):
        toast = getattr(self, "toast_hud", None)
        if toast is not None and hasattr(toast, "push"):
            toast.push(title, message, severity="info", duration_s=float(self._keepsake_setting("capsule_notice_s")))
            return True
        return False

    def _hand_back_capsule(self, capsule, watcher=True):
        """As "Hand capsules back" says: by the Watcher (with a notice when it
        stays quiet), by a notice only, or by the Watcher only. Always in the
        event feed."""
        span = span_text(time.time() - float(capsule.get("left_at") or 0))
        fields = {"note": capsule["note"], "span": span, "system": capsule["system"]}
        delivery = self._keepsake_setting("capsule_delivery")
        said = self._watcher_says("capsule", fields) if watcher and delivery != "notice" else None
        if not said and delivery != "watcher":
            self._notice(f"TIME CAPSULE · {capsule['system'].upper()}", f"Left {span} ago: {capsule['note']}")
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            feed("CAPSULE", f"{capsule['system']}, left {span} ago: {capsule['note']}", severity="INFO")

    def _capsule_not_yet(self, system, seconds):
        """Back before a capsule's "Not before…": it's there, not yet."""
        wait = wait_text(seconds)
        delivery = self._keepsake_setting("capsule_delivery")
        said = self._watcher_says("capsule_early", {"system": system, "wait": wait}) if delivery != "notice" else None
        if not said and delivery != "watcher":
            self._notice(f"TIME CAPSULE · {system.upper()}", f"Sealed for later: it opens in {wait}.")

    # -- On this day --------------------------------------------------------------
    def _on_this_day(self):
        """This date in years gone by, worked out once a day."""
        today = datetime.now().astimezone()
        key = (today.strftime("%Y-%m-%d"), get_active_profile(getattr(self, "config", None) or {}))
        cached = getattr(self, "_on_this_day_cache", None)
        if cached and cached[0] == key:
            return cached[1]
        days = on_this_day(self._history_rows(), today)
        self._on_this_day_cache = (key, days)
        return days

    def _history_rows(self):
        history = getattr(self, "travel_history", None)
        if history is None:
            return []
        with history.lock:
            return list(history.rows)

    def _on_this_day_watcher(self, startup_replay=False):
        """The first live jump of the day: the Watcher may look back."""
        if startup_replay or not self._keepsake_setting("on_this_day_watcher"):
            return None
        try:
            days = self._on_this_day()
        except Exception as exc:
            logging.debug("On this day skipped: %s", exc)
            return None
        if not days:
            return None
        return self._watcher_says("on_this_day", {"ago": years_text(days[0]["years"]).capitalize(), "system": days[0]["first"]})

    # -- The Galaxy Minimap's marks ---------------------------------------------
    def _capsule_marks(self):
        """Where the sealed capsules are, as [x, z], for the minimap: their
        own coordinates, or the travel history's last visit there."""
        try:
            sealed = [row for row in self.capsule_store().rows() if not row.get("opened_at")]
        except Exception:
            return []
        if not sealed:
            return []
        wanted = {str(row["system"]).casefold() for row in sealed if not row.get("coords")}
        found = {}
        if wanted:
            for row in reversed(self._history_rows()):
                key = str(row[1]).casefold()
                if key in wanted and key not in found:
                    found[key] = [row[2], row[3], row[4]]
                    if len(found) == len(wanted):
                        break
        marks = []
        for row in sealed:
            coords = row.get("coords") or found.get(str(row["system"]).casefold())
            if coords:
                marks.append([round(float(coords[0]), 1), round(float(coords[2]), 1)])
        return marks

    # -- The deck's Time Capsules page ----------------------------------------
    def _html_capsules_workspace(self):
        now = time.time()
        rows = self.capsule_store().rows()
        sealed, opened = [], []
        for row in rows:
            entry = {"id": row["id"], "system": row["system"], "note": row["note"], "left_from": row.get("left_from") or "",
                     "left_at": row.get("left_at"), "left_ago": span_text(now - float(row.get("left_at") or now))}
            if row.get("opened_at"):
                entry.update(opened_at=row["opened_at"], waited=span_text(float(row["opened_at"]) - float(row.get("left_at") or 0)))
                opened.append(entry)
            else:
                if row.get("not_before") and float(row["not_before"]) > now:
                    entry["opens_in"] = wait_text(float(row["not_before"]) - now)
                sealed.append(entry)
        days = [dict(day, ago=years_text(day["years"])) for day in self._on_this_day()]
        # The postcards you took on this date, by year.
        cards = {}
        album = getattr(self, "postcard_album", None)
        if callable(album) and days:
            today = datetime.now()
            years = {day["date"][:4] for day in days}
            try:
                for card in album().rows():
                    taken = datetime.fromtimestamp(float(card["at"]))
                    if (taken.month, taken.day) == (today.month, today.day) and str(taken.year) in years:
                        cards.setdefault(str(taken.year), []).append({"id": card["id"], "title": card["title"]})
            except Exception as exc:
                logging.debug("On this day postcards skipped: %s", exc)
        for day in days:
            day["postcards"] = cards.get(day["date"][:4], [])[:6]
        return {
            "here": str(getattr(self, "current_sys", "") or ""),
            "sealed": sealed,
            "opened": opened,
            "on_this_day": days,
            "today": datetime.now().strftime("%d %B").lstrip("0"),
            "waits": list(WAITS),
            "settings": {key: self._keepsake_setting(key) for key in CAPSULE_SETTINGS},
            "minimap": bool(setting_value(self.config, "galaxy_minimap_capsules", ("bool", None, True))),
        }

    def _handle_capsules_command(self, operation, payload):
        payload = payload or {}
        store = self.capsule_store()
        if operation == "leave":
            here = str(getattr(self, "current_sys", "") or "")
            system = str(payload.get("system") or "").strip() or here
            coords = getattr(self, "current_coords", None) if system.casefold() == here.casefold() else None
            wait = str(payload.get("wait") or "none")
            capsule = store.leave(system, payload.get("note"), here=here, wait=wait if wait in WAITS else "none",
                                  coords=coords)
            if capsule:
                feed = getattr(self, "add_event_feed_entry", None)
                if callable(feed):
                    feed("CAPSULE", f"Time capsule sealed for {capsule['system']}", severity="INFO")
                update_minimap = getattr(self, "_update_galaxy_minimap_safely", None)
                if callable(update_minimap):
                    update_minimap()
            return bool(capsule)
        if operation == "remove":
            done = store.remove(str(payload.get("id") or ""))
            update_minimap = getattr(self, "_update_galaxy_minimap_safely", None)
            if done and callable(update_minimap):
                update_minimap()
            return done
        if operation == "set":
            return self._set_keepsake_setting(CAPSULE_SETTINGS, payload.get("key"), payload.get("value"))
        return False

    # -- The deck's Constellation page -----------------------------------------
    def _constellation_sky(self):
        """Every constellation, worked out again only when the travel
        history, the Watcher's nature or the page's settings change."""
        history = getattr(self, "travel_history", None)
        config = getattr(self, "config", None) or {}
        nature = watcher_mind.personality(config)
        options = constellation_options(config)
        key = (getattr(history, "revision", None), nature, get_active_profile(config), tuple(sorted(options.items())))
        cached = getattr(self, "_constellation_cache", None)
        if not cached or cached[0] != key:
            cached = (key, constellations(self._history_rows(), nature, options))
            self._constellation_cache = cached
        return cached[1], options

    def _tonight(self, linger_s):
        """This session's star so far: where you've stayed longest ("this
        morning", "tonight": as the session's start says)."""
        history = getattr(self, "travel_history", None)
        if history is None or not hasattr(history, "session_rows"):
            return None
        rows = history.session_rows()
        best = None
        for index, row in enumerate(rows):
            try:
                arrived = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00")).timestamp()
                left = (datetime.fromisoformat(str(rows[index + 1][0]).replace("Z", "+00:00")).timestamp()
                        if index + 1 < len(rows) else time.time())
            except (TypeError, ValueError, IndexError):
                continue
            stay = max(0.0, min(DWELL_CAP_S, left - arrived))
            if best is None or stay > best[0]:
                best = (stay, str(row[1]), index + 1 == len(rows))
        if best is None:
            return None
        from voidcompass.exploration.flight_log import part_of_day
        try:
            began = datetime.fromisoformat(str(rows[0][0]).replace("Z", "+00:00")).astimezone()
        except (TypeError, ValueError, IndexError):
            began = datetime.now().astimezone()
        return {"system": best[1], "minutes": round(best[0] / 60), "here": best[2], "lingering": best[0] >= linger_s,
                "when": part_of_day(began)["When"]}

    def _html_constellation_workspace(self):
        sky, options = self._constellation_sky()
        latest = sky[-1] if sky else None
        return {
            "sky": sky,
            "per": options["per"],
            "to_go": 0 if not latest or latest["complete"] else options["per"] - len(latest["stars"]),
            "tonight": self._tonight(options["linger_min"] * 60),
            "settings": {key: self._keepsake_setting(key) for key in CONSTELLATION_SETTINGS},
        }

    def _constellation_watch(self, startup_replay=False):
        """A new session's first live jump: the Watcher names any
        constellation finished since it last looked (never the ones from
        before it started looking)."""
        if startup_replay:
            return None
        history = getattr(self, "travel_history", None)
        session = getattr(history, "session_start", None)
        if getattr(self, "_constellation_watched", None) == (session, get_active_profile(self.config)):
            return None
        self._constellation_watched = (session, get_active_profile(self.config))
        heartbeat = getattr(self, "heartbeat_hud", None)
        mind = getattr(heartbeat, "mind", None)
        if mind is None or not hasattr(mind, "memory"):
            return None
        try:
            sky, _options = self._constellation_sky()
        except Exception as exc:
            logging.debug("Constellation watch skipped: %s", exc)
            return None
        done = [item for item in sky if item["complete"]]
        with mind.lock:
            named = mind.memory.get("constellations_named")
            mind.memory["constellations_named"] = len(done)
        if named is None or len(done) <= int(named) or not self._keepsake_setting("constellation_watcher"):
            return None
        newest = done[-1]
        return self._watcher_says("constellation_named", {"name": newest["name"], "count": len(newest["stars"])})

    def _save_constellation(self, payload):
        """SAVE AS PICTURE: the page's drawing, kept with your postcards."""
        from voidcompass.dashboard.dashboard_keepsakes_mixin import postcards_folder
        try:
            data = base64.b64decode(str(payload.get("picture") or "").split(",", 1)[-1], validate=True)
        except (ValueError, TypeError):
            return False
        if not data.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")) or len(data) > CONSTELLATION_PICTURE_MAX:
            return False
        try:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as image:
                if image.width > 4000 or image.height > 4000:
                    return False
                out = io.BytesIO()
                image.convert("RGB").save(out, "PNG", optimize=True)
            data = out.getvalue()
        except (ImportError, OSError, ValueError):
            return False
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(payload.get("name") or "Constellation")).strip()[:60] or "Constellation"
        folder = postcards_folder(getattr(self, "config", None))
        stamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        path = os.path.join(folder, f"Constellation - {name} - {stamp}.png")
        try:
            os.makedirs(folder, exist_ok=True)
            with open(path + ".part", "wb") as handle:
                handle.write(data)
            os.replace(path + ".part", path)
        except OSError as exc:
            logging.warning("Constellation not saved: %s", exc)
            return False
        self._postcard_album_cache = None
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            feed("SYSTEM", f"{name} saved with your postcards", severity="INFO")
        return True

    def _handle_constellation_command(self, operation, payload):
        payload = payload or {}
        if operation == "save":
            return self._save_constellation(payload)
        if operation == "set":
            return self._set_keepsake_setting(CONSTELLATION_SETTINGS, payload.get("key"), payload.get("value"))
        return False
