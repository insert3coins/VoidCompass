"""Commander Record's books (5.7.8): the whole fleet with EDSY and Coriolis
links, stored modules, missions with their kills, Community Goals, vouchers
held, sessions of fighting and mining, ring hotspots and earnings, and History's
sessions table. Built from one pass over the journal (commander_book), off the
UI thread, kept until a journal file changes. The page asks for them by name
(/api/data/cmdr-book, cmdr-earnings, history-*).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time

from voidcompass.exploration import commander_book, journal_events
from voidcompass.outrider import commander as cmdr

logger = logging.getLogger(__name__)
HOTSPOTS_FILE = "hotspot_names.json"


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class DashboardCmdrMixin:

    def _cmdr_signature(self):
        path = str(self.config.get("journal_path") or "")
        files = journal_events.journal_files(path) if path else []
        if not files:
            return None
        newest = files[-1]
        try:
            return (len(files), newest, os.path.getsize(newest))
        except OSError:
            return (len(files), newest, 0)

    def _cmdr_book(self):
        """The folded books, or None while they're first being read."""
        state = self._html_profile_transient("_cmdr_books", {"signature": None, "book": None, "working": False})
        signature = self._cmdr_signature()
        if signature is None:
            return {"folds": {}, "loadouts": [], "sessions": [], "sales": [], "stats": None, "hotspots": []}
        if state["signature"] != signature and not state["working"]:
            state["working"] = True
            path = str(self.config.get("journal_path") or "")
            commander, fid = getattr(self, "cmdr_name", None), getattr(self, "cmdr_fid", None)
            names = self._hotspot_names()

            def work():
                try:
                    events = journal_events.read(path, commander_book.EVENTS, commander=commander, fid=fid)
                    book = commander_book.read(events, names)
                except Exception:
                    logger.exception("Commander books couldn't be read")
                    book = None
                state.update(book=book, signature=signature, working=False)
                publish = getattr(self, "_schedule_html_dashboard_publish", None)
                if callable(publish):
                    try:
                        self._ui_post(lambda: publish(immediate=True), key="cmdr-books")
                    except Exception:
                        pass

            threading.Thread(target=work, name="CommanderBooks", daemon=True).start()
        return state["book"]

    def _hotspot_names(self):
        try:
            with open(self._profile_path(HOTSPOTS_FILE), encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _hotspot_observe(self, raw, startup_replay=False):
        """A live drop into a ring: the hotspot's name, when Status.json's
        destination says it (the journal never names one), and a crew line
        with your record there."""
        if startup_replay or raw.get("BodyType") != "PlanetaryRing":
            return
        ring = str(raw.get("Body") or "")
        details = getattr(self, "current_destination_details", None) or {}
        label = str(details.get("Name_Localised") or details.get("Name") or "")
        names = self._hotspot_names()
        if "hotspot" in label.casefold() and ring and names.get(ring) != label:
            names[ring] = label
            try:
                path = self._profile_path(HOTSPOTS_FILE)
                with open(f"{path}.tmp", "w", encoding="utf-8") as handle:
                    json.dump(names, handle, indent=1)
                os.replace(f"{path}.tmp", path)
            except OSError:
                pass
        book = (getattr(self, "_cmdr_books", None) or {}).get("book")
        record = next((row for row in (book or {}).get("hotspots") or () if row["ring"] == ring), None)
        if not record or not record.get("stints"):
            return
        what = names.get(ring) or "This ring"
        rate = f", {record['best_tph']:.0f} t/h at best" if record.get("best_tph") else ""
        text = f"{what}: {record['stints']} stint{'s' if record['stints'] != 1 else ''} before{rate}."
        mind = getattr(self, "_orders_mind", lambda: None)()
        if mind is not None and hasattr(mind, "crew_say"):
            try:
                from voidcompass.core import companions
                mind.crew_say(companions.identity(self.config), text, heading="MINING", topic="hotspot_record", converse=False)
            except Exception:
                logger.debug("Hotspot line not said", exc_info=True)

    def _cmdr_ranks(self, stats):
        """Each rank with the next one, and roughly the credits to the next exobiology rank."""
        ranks = dict(getattr(self, "cmdr_ranks", None) or {})
        progress = dict(getattr(self, "cmdr_rank_progress", None) or {})
        rows = []
        from voidcompass.core import ranks as rank_names
        for kind in ("Combat", "Trade", "Explore", "Exobiologist", "Soldier", "CQC", "Federation", "Empire"):
            number = ranks.get(kind)
            if number is None:
                continue
            row = {"kind": kind, "name": rank_names.name(kind, number), "next": rank_names.name(kind, int(number) + 1),
                   "percent": _num(progress.get(kind))}
            thresholds = cmdr.RANK_CREDITS.get(kind)
            if thresholds and stats:
                earned = _num(((stats.get("Exobiology") or {}).get("Organic_Data_Profits")))
                index = int(number) + 1
                if earned is not None and index < len(thresholds):
                    row["credits_left"] = max(0, int(thresholds[index] - earned))
                    row["estimate"] = True
            rows.append(row)
        return rows

    def _cmdr_book_payload(self):
        book = self._cmdr_book()
        if book is None:
            return {"working": True}
        folds = book.get("folds") or {}
        try:
            fleet = cmdr.ships(folds.get("stored_ships"), book.get("loadouts") or [])
        except Exception:
            fleet = {"ships": []}
        try:
            modules = cmdr.stored_modules(folds.get("stored_modules"))
        except Exception:
            modules = {"modules": []}
        try:
            missions = cmdr.missions(folds.get("missions"))
        except Exception:
            missions = []
        try:
            goals = cmdr.community_goals(folds.get("community_goals"))
        except Exception:
            goals = []
        vouchers = cmdr.vouchers(folds.get("vouchers")) if folds.get("vouchers") else None
        stats = book.get("stats") or ((getattr(self, "companion_state", None) or {}).get("statistics")) or {}
        ships = fleet.get("ships") or []
        carrier = getattr(getattr(self, "carrier_tracker", None), "carrier_data", None) or {}
        money = {"credits": getattr(self, "cmdr_balance", None),
                 "net_worth": (stats.get("Bank_Account") or {}).get("Current_Wealth"),
                 "fleet_value": sum(int(ship.get("value") or 0) for ship in ships), "ships": len(ships),
                 "modules_value": sum(int(row.get("value") or 0) for row in modules.get("modules") or ()),
                 "modules": len(modules.get("modules") or ()), "carrier_balance": carrier.get("balance"),
                 "vouchers": vouchers}
        return {"working": False, "money": money, "ranks": self._cmdr_ranks(stats), "fleet": ships,
                "modules": modules.get("modules") or [], "modules_ts": modules.get("ts"),
                "missions": missions, "goals": goals, "vouchers": vouchers,
                "sessions": (book.get("sessions") or [])[:80], "hotspots": book.get("hotspots") or []}

    def _cmdr_earnings_payload(self, period):
        book = self._cmdr_book()
        if book is None:
            return {"working": True}
        return {"working": False, **commander_book.earnings(book.get("sales") or [], period or "all")}

    def _cmdr_vouchers_where(self):
        """5.7.8, after ED-Outrider: where to cash the vouchers you hold. A
        faction's own stations take its vouchers at Contacts; Interstellar
        Factors takes any, less its cut. Asked of Spansh when the page asks."""
        vouchers = (self._cmdr_book_payload() or {}).get("vouchers") or {}
        factions = [str(row.get("name") or "") for row in vouchers.get("factions") or () if row.get("name")][:4]
        system = str(getattr(self, "current_sys", "") or "")
        coords = getattr(self, "current_coords", None)
        if not factions or not system or not coords:
            return {"status": "ready", "factors": None, "factions": {}}
        key = (system, tuple(factions))
        state = self.__dict__.setdefault("_vouchers_where", {"key": None, "status": "ready", "answer": None})
        if state["key"] == key:
            return {"status": state["status"], **(state["answer"] or {"factors": None, "factions": {}})}
        state.update(key=key, status="working", answer=None)
        here = [float(v) for v in coords[:3]]

        def work():
            from voidcompass.services import spansh

            def nearest(filters):
                body = {"filters": filters, "reference_coords": {"x": here[0], "y": here[1], "z": here[2]},
                        "sort": [{"distance": {"direction": "asc"}}], "size": 1, "page": 0}
                rows = spansh._call("POST", "stations/search", body=body, ttl=3600).get("results") or []
                row = rows[0] if rows else None
                return {"name": row.get("name"), "system": row.get("system_name"), "distance": row.get("distance")} if row else None
            answer = {"factors": nearest({"services": [{"name": "Interstellar Factors Contact"}]}), "factions": {}}
            for faction in factions:
                answer["factions"][faction] = nearest({"controlling_minor_faction": {"value": [faction]}})
            return answer

        def done(result, error):
            if state.get("key") != key:
                return
            state.update(status="failed" if error else "ready", answer=result or None)

        self._survey_task("vouchers", work, done)
        return {"status": "working", "factors": None, "factions": {}}

    def _records_data(self, name, query):
        if name == "cmdr-vouchers":
            return self._cmdr_vouchers_where()
        if name == "cmdr-book":
            return self._cmdr_book_payload()
        if name == "cmdr-earnings":
            return self._cmdr_earnings_payload(query.get("period"))
        history = getattr(self, "_history_data", None)
        return history(name, query) if callable(history) else None
