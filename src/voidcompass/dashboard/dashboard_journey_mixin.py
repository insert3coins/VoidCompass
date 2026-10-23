"""Your journey, told back (5.5.10), for MainDashboard: Void Wrapped and the
Flight Recorder, with the music diary they share.

The heavy reading (a year of scanned bodies and journal events) happens off
the app's loop, and the answers are kept until something they're made from
changes. The deck asks for the big pieces by name through the dashboard
server's /api/data/ route; its snapshot carries only what each page shows
at rest.
"""
from __future__ import annotations

import base64
from datetime import datetime
import io
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import threading
import time

from voidcompass.core.config import get_active_profile, get_profile_file
from voidcompass.core.platform_support import application_dir, open_path
from voidcompass.exploration import galactic_regions
from voidcompass.exploration.flight_log import ELITE_YEARS
from voidcompass.exploration.flight_recorder import recorder_sessions, tape
from voidcompass.exploration.void_wrapped import year_bounds, year_story, years_available
from voidcompass.exploration.year_record import YearRecord
from voidcompass.overlays import watcher_mind
from voidcompass.services.music_diary import MusicDiary

WRAPPED_FOLDER = "wrapped"
CARD_PICTURE_MAX = 1800 * 1024
# A year's scanned bodies are read at most this many rows deep.
YEAR_BODY_ROWS = 400_000
# The current year's story is told again at most this often while you fly.
WRAPPED_STALE_S = 600


def _picture_bytes(payload):
    """A card or page drawn by the deck: PNG or JPEG bytes, or None."""
    try:
        data = base64.b64decode(str(payload or "").split(",", 1)[-1], validate=True)
    except (ValueError, TypeError):
        return None
    if not data.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")) or len(data) > CARD_PICTURE_MAX:
        return None
    return data


def _safe_name(text, fallback):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(text or "")).strip()[:70] or fallback


class DashboardJourneyMixin:
    # -- the music diary ---------------------------------------------------------
    def music_diary(self):
        key = get_active_profile(getattr(self, "config", None) or {})
        diary = getattr(self, "_music_diary_instance", None)
        if diary is None or getattr(self, "_music_diary_key", None) != key:
            diary = MusicDiary(get_profile_file(key, "music_diary.json"))
            self._music_diary_instance, self._music_diary_key = diary, key
        return diary

    def _music_diary_note(self, track_id, track):
        try:
            self.music_diary().note(time.time(), track_id, track.get("title") or "", track.get("artist") or "",
                                    track.get("album") or "")
        except Exception as exc:
            logging.debug("Music diary skipped: %s", exc)

    # -- shared readers ------------------------------------------------------------
    def _journey_rows(self):
        history = getattr(self, "travel_history", None)
        if history is None:
            return []
        with history.lock:
            return list(history.rows)

    def _journey_sessions(self):
        log = getattr(self, "captains_log", None)
        try:
            return list(log.sessions()) if log is not None else []
        except Exception:
            return []

    def _journey_postcards(self):
        album = getattr(self, "postcard_album", None)
        try:
            return album().rows() if callable(album) else []
        except Exception:
            return []

    def _journey_bodies(self, start, end, firsts_only=False, limit=YEAR_BODY_ROWS):
        """Bodies scanned from ``start`` to ``end`` (unix times), from the scan
        record: when each was scanned is its journal time where it has one."""
        conn = getattr(self, "conn", None)
        lock = getattr(self, "db_lock", None)
        if conn is None or lock is None:
            return []
        out = []
        with lock:
            try:
                cursor = conn.execute("SELECT system_name, data_json, ts FROM scan_hud_items WHERE ts >= ? LIMIT ?",
                                      (int(start) - 86400, int(limit)))
                rows = cursor.fetchall()
            except sqlite3.Error as exc:
                logging.debug("Scanned bodies not read: %s", exc)
                return []
        for system, payload, saved in rows:
            try:
                item = json.loads(payload)
            except ValueError:
                continue
            when = None
            stamp = item.get("scan_timestamp")
            if stamp:
                try:
                    when = datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
                except ValueError:
                    when = None
            when = when if when is not None else float(saved or 0)
            if not start <= when < end:
                continue
            if firsts_only and item.get("was_discovered") is not False and not item.get("first_footfall"):
                continue
            out.append({
                "system": system, "name": item.get("name") or "", "full_name": item.get("full_name") or item.get("name") or "",
                "class": item.get("class") or "", "planet_class": item.get("planet_class") or "",
                "star_type": item.get("star_type") or "", "is_star": bool(item.get("is_star")),
                "was_discovered": item.get("was_discovered"), "dss_complete": bool(item.get("dss_complete")),
                "first_footfall": bool(item.get("first_footfall")), "terraformable": bool(item.get("terraformable")),
                "green_giant": bool(item.get("green_giant")), "reward": int(item.get("reward") or 0),
                "dss_reward": int(item.get("dss_reward") or 0), "when": when,
            })
        return out

    # -- Void Wrapped ---------------------------------------------------------------------
    def _wrapped_years(self):
        rows, sessions = self._journey_rows(), self._journey_sessions()
        key = (getattr(getattr(self, "travel_history", None), "revision", None), len(sessions),
               str((sessions[0] if sessions else {}).get("started")))
        cached = getattr(self, "_wrapped_years_cache", None)
        if cached and cached[0] == key:
            return cached[1]
        years = years_available(rows, sessions)
        self._wrapped_years_cache = (key, years)
        return years

    def _html_wrapped_workspace(self):
        config = getattr(self, "config", None) or {}
        return {
            "years": self._wrapped_years(),
            "commander": str(config.get("active_commander_name") or getattr(self, "cmdr_name", "") or ""),
            "this_year": datetime.now().year,
            "elite_offset": ELITE_YEARS,
            "folder": self.wrapped_folder(),
            "saved": self._wrapped_saved(),
            # 5.6.1: an expedition's own story, from the Expeditions page.
            "trips": self._wrapped_trips(),
            "trip_request": dict(getattr(self, "_wrapped_trip_request", None) or {}),
        }

    def _wrapped_trips(self):
        manager = getattr(self, "expedition_manager", None)
        rows = manager.expeditions() if manager is not None else []
        return [{"id": row.get("id"), "name": row.get("name") or "Expedition", "status": row.get("status"),
                 "started": row.get("started"), "ended": row.get("ended"),
                 "jumps": int((row.get("stats") or {}).get("jumps") or 0)}
                for row in rows if int((row.get("stats") or {}).get("jumps") or 0)][:40]

    def _expedition_story(self, expedition_id):
        """An expedition told as Void Wrapped's cards, cut to its dates."""
        from voidcompass.exploration.flight_recorder import epoch
        manager = getattr(self, "expedition_manager", None)
        expedition = manager.get(expedition_id) if manager is not None else None
        if not expedition:
            return None
        start = epoch(expedition.get("started")) or time.time()
        end = epoch(expedition.get("ended")) or time.time()
        trip = {"id": expedition["id"], "name": expedition.get("name") or "Expedition", "start": start, "end": end + 60}
        places = manager.bookmarks(expedition_id)
        key = (expedition.get("ended"), int((expedition.get("stats") or {}).get("jumps") or 0), self._wrapped_key(0)[1:],
               len(places), sum(1 for row in places if row.get("status") == "visited"))
        cache = getattr(self, "_trip_story_cache", None)
        if cache is None:
            cache = self._trip_story_cache = {}
        held = cache.get(expedition_id)
        if held and held[0] == key:
            return held[1]
        if expedition_id in getattr(self, "_trip_story_working", set()):
            return held[1] if held else {"working": True, "trip": trip}
        self._trip_story_working = getattr(self, "_trip_story_working", set()) | {expedition_id}

        def work():
            try:
                story = self._tell_year(datetime.fromtimestamp(start).year, trip=trip)
                # 5.6.1, Part 5: the places you kept, just before the verdict.
                cards = story.get("cards") or []
                if places and cards:
                    at = next((index for index, card in enumerate(cards) if card.get("kind") == "verdict"), len(cards))
                    cards.insert(at, {"kind": "places", "count": len(places),
                                      "visited": sum(1 for row in places if row.get("status") == "visited"),
                                      "names": [str(row.get("title") or row.get("body") or row.get("system") or "")[:80] for row in places][:6]})
            except Exception:
                logging.exception("Expedition story couldn't be told")
                story = {"trip": trip, "error": True, "cards": []}
            cache[expedition_id] = (key, story)
            self._trip_story_working = getattr(self, "_trip_story_working", set()) - {expedition_id}

        threading.Thread(target=work, name="expedition-story", daemon=True).start()
        return held[1] if held else {"working": True, "trip": trip}

    def _wrapped_key(self, year):
        history = getattr(self, "travel_history", None)
        sessions = self._journey_sessions()
        newest = sessions[0] if sessions else {}
        config = getattr(self, "config", None) or {}
        return (year, get_active_profile(config), watcher_mind.personality(config), getattr(history, "revision", None),
                len(sessions), str(newest.get("ended")), int(newest.get("jumps") or 0),
                getattr(self.music_diary(), "revision", 0))

    def _wrapped_story(self, year):
        """The year's story, or {"working": True} while it's being told."""
        key = self._wrapped_key(year)
        cache = getattr(self, "_wrapped_cache", None)
        if cache is None:
            cache = self._wrapped_cache = {}
        lock = getattr(self, "_wrapped_lock", None)
        if lock is None:
            lock = self._wrapped_lock = threading.Lock()
        with lock:
            held = cache.get(year)
            fresh = held and (held["key"] == key or (year == datetime.now().year
                                                      and time.monotonic() - held["at"] < WRAPPED_STALE_S
                                                      and held["key"][:3] == key[:3]))
            if held and fresh:
                return held["story"]
            if year in getattr(self, "_wrapped_working", set()):
                return held["story"] if held else {"working": True, "year": year}
            self._wrapped_working = getattr(self, "_wrapped_working", set()) | {year}

        def work():
            try:
                story = self._tell_year(year)
            except Exception:
                logging.exception("Void Wrapped %s couldn't be told", year)
                story = {"year": year, "error": True, "cards": []}
            with lock:
                cache[year] = {"key": key, "story": story, "at": time.monotonic()}
                self._wrapped_working = getattr(self, "_wrapped_working", set()) - {year}

        threading.Thread(target=work, name=f"void-wrapped-{year}", daemon=True).start()
        return held["story"] if held else {"working": True, "year": year}

    def _tell_year(self, year, trip=None):
        start, end = (trip["start"], trip["end"]) if trip else year_bounds(year)
        config = getattr(self, "config", None) or {}
        sources = {
            "rows": self._journey_rows(),
            "sessions": self._journey_sessions(),
            "bodies": self._journey_bodies(start, end),
            "postcards": self._journey_postcards(),
            "music": self.music_diary().between(start, end),
            "region_of": galactic_regions.find_region,
        }
        store = getattr(self, "trading_store", None)
        if store is not None:
            try:
                sources["trades"] = store.query("SELECT * FROM trades WHERE ts >= ? AND ts < ?", (start, end))
            except Exception as exc:
                logging.debug("Wrapped trades skipped: %s", exc)
        bgs = getattr(self, "bgs_store", None)
        if bgs is not None:
            try:
                with bgs.lock:
                    sources["bgs"] = [dict(row) for row in bgs.conn.execute(
                        "SELECT ts, kind, faction, system, amount, count FROM activity WHERE ts >= ? AND ts < ?",
                        (start, end)).fetchall()]
            except Exception as exc:
                logging.debug("Wrapped BGS skipped: %s", exc)
        index = getattr(self, "codex_index", None)
        if index is not None:
            first, last = datetime.fromtimestamp(start).strftime("%Y-%m-%d"), datetime.fromtimestamp(end).strftime("%Y-%m-%d")
            with index.lock:
                sources["codex_bio"] = sum(1 for row in index.rows if first <= str(row[0])[:10] < last)
        engine = getattr(self, "achievement_engine", None)
        if engine is not None:
            try:
                sources["achievements"] = engine.snapshot().get("achievements") or []
            except Exception as exc:
                logging.debug("Wrapped achievements skipped: %s", exc)
        sky = getattr(self, "_constellation_sky", None)
        if callable(sky):
            try:
                sources["sky"] = sky()[0]
            except Exception as exc:
                logging.debug("Wrapped constellations skipped: %s", exc)
        commander = str(config.get("active_commander_name") or getattr(self, "cmdr_name", "") or "")
        record = getattr(self, "_year_record", None)
        if record is None:
            record = self._year_record = YearRecord()
        try:
            sources["events"] = record.events(str(config.get("journal_path") or ""), start, end, commander or None,
                                              str(config.get("active_commander_fid") or "") or None)
        except Exception as exc:
            logging.debug("Wrapped journal events skipped: %s", exc)
        return year_story(year, sources, watcher_mind.personality(config), commander, trip=trip)

    def wrapped_folder(self):
        return str(application_dir() / WRAPPED_FOLDER)

    def _wrapped_saved(self):
        folder = self.wrapped_folder()
        try:
            names = sorted((name for name in os.listdir(folder) if name.lower().endswith((".png", ".jpg"))),
                           key=lambda name: os.path.getmtime(os.path.join(folder, name)), reverse=True)
        except OSError:
            return {"count": 0}
        return {"count": len(names), "latest": names[0] if names else ""}

    def _save_wrapped_card(self, payload, copy=False):
        data = _picture_bytes(payload.get("picture"))
        if data is None:
            return False
        try:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as image:
                if image.width > 4096 or image.height > 4096:
                    return False
                picture = image.convert("RGB")
                if copy:
                    from voidcompass.services.postcard_album import copy_dib
                    out = io.BytesIO()
                    picture.save(out, "BMP")
                    return copy_dib(out.getvalue()[14:])
                out = io.BytesIO()
                picture.save(out, "PNG", optimize=True)
        except (ImportError, OSError, ValueError):
            return False
        year = int(payload.get("year") or 0) or datetime.now().year
        card = _safe_name(payload.get("card"), "Card")
        folder = Path(self.wrapped_folder())
        path = folder / f"Void Wrapped {year + ELITE_YEARS} - {int(payload.get('index') or 0):02d} {card}.png"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            with open(str(path) + ".part", "wb") as handle:
                handle.write(out.getvalue())
            os.replace(str(path) + ".part", path)
        except OSError as exc:
            logging.warning("Void Wrapped card not saved: %s", exc)
            return False
        return True

    def _handle_wrapped_command(self, operation, payload):
        payload = payload or {}
        if operation == "save":
            done = self._save_wrapped_card(payload)
            if done and payload.get("last"):
                feed = getattr(self, "add_event_feed_entry", None)
                if callable(feed):
                    feed("SYSTEM", "Void Wrapped saved as pictures in the wrapped folder", severity="INFO")
            return done
        if operation == "copy":
            return self._save_wrapped_card(payload, copy=True)
        if operation == "open_folder":
            folder = self.wrapped_folder()
            try:
                os.makedirs(folder, exist_ok=True)
            except OSError:
                return False
            return bool(open_path(folder))
        if operation == "retell":
            year = int(payload.get("year") or 0)
            lock = getattr(self, "_wrapped_lock", None)
            if lock is None:
                lock = self._wrapped_lock = threading.Lock()
            with lock:
                (getattr(self, "_wrapped_cache", None) or {}).pop(year, None)
            return True
        return False

    def _wrapped_watch(self, startup_replay=False):
        """In December (and January, for the year just gone): once, a notice
        that the year is wrapped."""
        if startup_replay:
            return False
        now = datetime.now()
        year = now.year if now.month == 12 else now.year - 1 if now.month == 1 else None
        config = getattr(self, "config", None) or {}
        if year is None or int(config.get("wrapped_noticed_year") or 0) >= year:
            return False
        if not any(row["year"] == year and row["jumps"] >= 20 for row in self._wrapped_years()):
            return False
        self.config["wrapped_noticed_year"] = year
        persist = getattr(self, "_persist_config", None)
        if callable(persist):
            persist()
        toast = getattr(self, "toast_hud", None)
        if toast is not None and hasattr(toast, "push"):
            toast.push(f"YOUR {year + ELITE_YEARS} IS WRAPPED", "Your year in the black, told as a story: Void Wrapped on the deck.",
                       severity="info", duration_s=14.0)
            return True
        return False

    # -- The Flight Recorder ------------------------------------------------------------------
    def _recorder_data(self, query):
        """For the Galactic Atlas: the sessions it can play, or one's tape."""
        wanted = str((query or {}).get("id") or "")
        sessions = self._journey_sessions()
        if not wanted:
            return {"sessions": recorder_sessions(sessions, rows=self._journey_rows())}
        if wanted.startswith("expedition:"):
            # 5.6.1: a whole expedition, played as one long session.
            manager = getattr(self, "expedition_manager", None)
            expedition = manager.get(wanted.split(":", 1)[1]) if manager is not None else None
            session = {"started": expedition.get("started"), "ended": expedition.get("ended"),
                       "jumps": int((expedition.get("stats") or {}).get("jumps") or 0),
                       "highlights": [{"kind": row.get("kind"), "title": row.get("title"), "detail": row.get("detail"),
                                       "timestamp": row.get("timestamp")} for row in expedition.get("events") or ()
                                      if row.get("kind") not in {"JUMP", "SESSION"}]} if expedition else None
        else:
            session = next((row for row in sessions if str(row.get("started") or "") == wanted), None)
        if session is None:
            return None
        cached = getattr(self, "_recorder_cache", None)
        key = (wanted, str(session.get("ended")), int(session.get("jumps") or 0), len(session.get("highlights") or ()))
        if cached and cached[0] == key:
            return cached[1]
        from voidcompass.exploration.flight_recorder import epoch
        start = epoch(session.get("started")) or 0.0
        end = epoch(session.get("ended")) or time.time()
        finds = []
        deep = getattr(self, "deep_survey", None)
        if deep is not None and hasattr(deep, "discovery_state"):
            try:
                finds = deep.discovery_state(1200)
            except Exception:
                finds = []
        bodies = []
        for body in self._journey_bodies(start, end + 60, firsts_only=True, limit=60_000):
            kind = "footfall" if body["first_footfall"] and body["was_discovered"] is not False else "first"
            bodies.append({"name": body["full_name"] or body["name"], "when": body["when"], "kind": kind,
                           "value": body["dss_reward"] or body["reward"]})
        music = self.music_diary().between(start - 1800, end)
        playing = self.music_diary().playing_at(start)
        if playing and (not music or music[0] != playing) and start - float(playing[0]) < 1800:
            music = [playing] + [row for row in music if row != playing]
        config = getattr(self, "config", None) or {}
        recorded = tape(session, self._journey_rows(), finds, self._journey_postcards(), music, bodies,
                        watcher_mind.personality(config))
        self._recorder_cache = (key, recorded)
        return recorded

    def _recorder_open(self, session_id):
        """WATCH AGAIN on a flight log: the Atlas opens the recorder on it."""
        previous = getattr(self, "_recorder_request", None) or {"seq": 0}
        self._recorder_request = {"seq": int(previous.get("seq") or 0) + 1, "id": str(session_id or "")[:40],
                                  "at": time.time()}
        refresh = getattr(getattr(self, "atlas", None), "refresh", None)
        if callable(refresh):
            refresh()
        request = getattr(self, "_request_html_dashboard_page", None)
        return bool(request("map")) if callable(request) else True

    def _recorder_music(self, payload):
        """The night's music, played again while the recorder plays."""
        operation = str((payload or {}).get("op") or "")
        if operation == "queue":
            tracks = [str(track)[:16] for track in list((payload or {}).get("tracks") or [])[:200] if track]
            library = self.music_library()
            tracks = [track for track in tracks if library.track(track)]
            if not tracks:
                return False
            previous = getattr(self, "_music_remote", None) or {"seq": 0}
            self._music_remote = {"seq": int(previous["seq"]) + 1, "op": "queue", "tracks": tracks}
        elif operation == "pause":
            previous = getattr(self, "_music_remote", None) or {"seq": 0}
            self._music_remote = {"seq": int(previous["seq"]) + 1, "op": "pause"}
        else:
            return False
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    # -- the deck's /api/data/ route ------------------------------------------------------------------
    def _html_data(self, name, query):
        """Answers the deck asks for by name (on the dashboard server's
        thread): (content type, bytes) or None."""
        query = query or {}
        if name == "wrapped" and query.get("expedition"):
            story = self._expedition_story(str(query.get("expedition"))[:20])
            return self._json_answer(story) if story is not None else None
        if name == "wrapped":
            try:
                year = int(query.get("year") or datetime.now().year)
            except (TypeError, ValueError):
                return None
            return self._json_answer(self._wrapped_story(year))
        if name == "recorder":
            answer = self._recorder_data(query)
            return self._json_answer(answer) if answer is not None else None
        return None

    # -- the Local API (5.5.10) -------------------------------------------------------------------------
    def api_wrapped_years(self):
        return {"years": self._wrapped_years()}

    def api_wrapped(self, year):
        from voidcompass.services.local_api import ApiError
        if not 1900 <= int(year) <= 9999:
            raise ApiError(404, "No such year")
        story = self._wrapped_story(int(year))
        if story.get("working"):
            return {"working": True, "year": int(year), "retry_after_s": 2}
        return story

    def api_recorder_sessions(self):
        return {"sessions": recorder_sessions(self._journey_sessions(), rows=self._journey_rows())}

    def api_recorder_tape(self, session):
        from voidcompass.services.local_api import ApiError
        if not session:
            raise ApiError(400, "Say which session: ?session=<its start time>, from /api/v1/recorder")
        recorded = self._recorder_data({"id": session})
        if recorded is None:
            raise ApiError(404, f"No session started at {session}")
        return recorded

    @staticmethod
    def _json_answer(value):
        return "application/json; charset=utf-8", json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
