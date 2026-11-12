"""History (5.7.8): the Captain's Log keeps the stories; this keeps the
books. One row a session (jumps, ly, farthest from Sol, first discoveries,
bodies, mapped, footfalls, species, sold, Codex, deaths), the summary rows,
trips from sale to sale, your top 25 finds and records, CSV exports, and an
EDSM flight log import for visits from before your journals (kept apart from
journal data). After ED-Outrider's History (github.com/weslocke/ED-Outrider,
GPLv3).
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone

from voidcompass.dashboard.dashboard_survey_more_mixin import _sale_time
from voidcompass.exploration import system_table

logger = logging.getLogger(__name__)
EDSM_LOG_FILE = "edsm_flight_log.json"


def _epoch(stamp):
    try:
        return datetime.strptime(str(stamp)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def _in(stamp, start, end):
    return bool(stamp) and start <= stamp and (not end or stamp <= end)


class DashboardHistoryMixin:

    def _history_window_rows(self, start, end):
        """Journey rows (travel history) inside a window."""
        history = getattr(self, "travel_history", None)
        if history is None:
            return []
        with history.lock:
            return [row for row in history.rows if _in(str(row[0]), start, end)]

    def _history_sessions(self, period="all"):
        log = getattr(self, "captains_log", None)
        sessions = log.sessions() if log is not None else []
        items = self._survey_all_items() if hasattr(self, "_survey_all_items") else []
        walked = getattr(getattr(self, "walked_bodies", None), "bodies", {}) or {}
        footfall_bodies = {str(item.get("full_name") or item.get("name") or "").casefold()
                           for item in items if item.get("first_footfall")}
        book = (getattr(self, "_cmdr_books", None) or {}).get("book") or {}
        sales = book.get("sales") or []
        rows = []
        for session in sessions:
            start, end = str(session.get("started") or ""), str(session.get("ended") or "")
            if period != "all" and not start.startswith(period):
                continue
            jumps = self._history_window_rows(start, end or "9999")
            far = max((math.hypot(float(r[2]), float(r[3]), float(r[4])) for r in jumps), default=None)
            scanned = [item for item in items if _in(str(item.get("scan_timestamp") or ""), start, end or "9999")]
            firsts = {str(item.get("_system") or "") for item in scanned if item.get("was_discovered") is False}
            species = sum(1 for item in scanned for scan in (item.get("organic_scans") or {}).values()
                          if isinstance(scan, dict) and scan.get("is_complete"))
            footfalls = sum(1 for body, stamp in walked.items() if _in(stamp, start, end or "9999") and body in footfall_bodies)
            sold = sum(sale["amount"] for sale in sales if sale["kind"] in ("exploration", "exobiology") and _in(sale["ts"], start, end or "9999"))
            rows.append({"started": start, "ended": end, "start_system": session.get("start_system"), "end_system": session.get("end_system"),
                         "ship": session.get("ship"), "jumps": int(session.get("jumps") or 0),
                         "ly": round(float(session.get("distance_ly") or 0), 1), "far": round(far) if far is not None else None,
                         "firsts": len(firsts), "bodies": len(scanned), "mapped": int(session.get("dss_maps") or 0),
                         "footfalls": footfalls, "species": species or int(session.get("bio_analyses") or 0),
                         "sold": sold or int(session.get("exploration_sales") or 0) + int(session.get("biology_sales") or 0),
                         "codex": int(session.get("codex") or 0), "deaths": int(session.get("deaths") or 0),
                         "first_systems": sorted(firsts)[:20], "highlights": (session.get("highlights") or [])[-8:]})
        return rows

    def _history_summary(self, rows):
        def total(subset, label):
            return {"label": label, **{key: sum(row[key] or 0 for row in subset)
                                       for key in ("jumps", "ly", "firsts", "bodies", "mapped", "footfalls", "species", "sold", "codex", "deaths")},
                    "far": max((row["far"] or 0 for row in subset), default=None), "sessions": len(subset)}
        companion = getattr(self, "companion_state", None) or {}
        last_sale = max(_sale_time(companion.get("last_exploration_sale")), _sale_time(companion.get("last_bio_sale")))
        since = [row for row in rows if row["started"] >= last_sale] if last_sale else rows
        stats = companion.get("statistics") or {}
        exploration = stats.get("Exploration") or {}
        career = {"label": "Career (the game's statistics)", "jumps": exploration.get("Total_Hyperspace_Jumps"),
                  "ly": exploration.get("Total_Hyperspace_Distance"), "far": exploration.get("Greatest_Distance_From_Start"),
                  "firsts": None, "bodies": exploration.get("Planets_Scanned_To_Level_3"), "mapped": exploration.get("Efficient_Scans"),
                  "footfalls": (stats.get("Exobiology") or {}).get("First_Logged"), "species": (stats.get("Exobiology") or {}).get("Organic_Species_Encountered"),
                  "sold": exploration.get("Exploration_Profits"), "codex": None, "deaths": (stats.get("Combat") or {}).get("Deaths")}
        return [total(rows, "All time (your journals)"), total(since, "Since your last sale"), career]

    def _history_trips(self):
        """Sale to sale: what each trip paid against our estimate, the ×5 on
        biology, credits an hour and a jump, and what any death cost."""
        book = (getattr(self, "_cmdr_books", None) or {}).get("book") or {}
        sales = [sale for sale in book.get("sales") or () if sale["kind"] in ("exploration", "exobiology")]
        items = self._survey_all_items() if hasattr(self, "_survey_all_items") else []
        log = getattr(self, "captains_log", None)
        sessions = log.sessions() if log is not None else []
        stops = []
        for sale in sorted(sales, key=lambda row: row["ts"]):
            # Sales a few minutes apart are one visit to the station.
            if stops and (_epoch(sale["ts"]) or 0) - (_epoch(stops[-1][-1]["ts"]) or 0) < 1800:
                stops[-1].append(sale)
            else:
                stops.append([sale])
        trips = []
        for before, stop in zip(stops, stops[1:]):
            trip = {"start": before[-1]["ts"], "end": stop[-1]["ts"], "paid": 0, "carto": 0, "bio": 0, "bonus_samples": 0, "samples": 0}
            for sale in stop:
                trip["paid"] += sale["amount"]
                trip["carto" if sale["kind"] == "exploration" else "bio"] += sale["amount"]
                for species in sale.get("species") or ():
                    trip["samples"] += 1
                    base = system_table.bio_values.species_value(species["name"]) or 0
                    if base and species["value"] >= base * 4.5:
                        trip["bonus_samples"] += 1
            trips.append(trip)
        for trip in trips:
            scanned = [item for item in items if _in(str(item.get("scan_timestamp") or ""), trip["start"], trip["end"])]
            trip["estimate"] = sum(int(item.get("dss_reward") or 0) if item.get("dss_complete") else int(item.get("reward") or 0)
                                   for item in scanned)
            trip["predicted_bonus"] = sum(1 for item in scanned if item.get("first_footfall")
                                          for scan in (item.get("organic_scans") or {}).values() if isinstance(scan, dict) and scan.get("is_complete"))
            jumps = self._history_window_rows(trip["start"], trip["end"])
            trip["jumps"] = len(jumps)
            trip["ly"] = round(sum(float(row[6] or 0) for row in jumps), 1)
            span = max(1.0, (_epoch(trip["end"]) or 0) - (_epoch(trip["start"]) or 0))
            flown = sum(max(0.0, (_epoch(s.get("ended")) or 0) - (_epoch(s.get("started")) or 0))
                        for s in sessions if _in(str(s.get("started") or ""), trip["start"], trip["end"]))
            hours = (flown or span) / 3600
            trip["cr_h"] = round(trip["paid"] / hours) if hours > 0.05 else None
            trip["cr_jump"] = round(trip["paid"] / trip["jumps"]) if trip["jumps"] else None
            trip["deaths"] = sum(int(s.get("deaths") or 0) for s in sessions if _in(str(s.get("started") or ""), trip["start"], trip["end"]))
        trips.reverse()
        return trips[:200]

    def _history_top(self):
        items = self._survey_all_items() if hasattr(self, "_survey_all_items") else []
        rows = []
        for item in items:
            value = system_table._value_max(item) if not item.get("is_star") else int(item.get("reward") or 0)
            bio = sum(int(system_table.bio_values.species_value(scan.get("species")) or 0)
                      for scan in (item.get("organic_scans") or {}).values() if isinstance(scan, dict) and scan.get("is_complete"))
            rows.append({"system": item.get("_system"), "body": item.get("name"), "class": item.get("planet_class") or item.get("star_type"),
                         "value": value + bio * (5 if item.get("first_footfall") else 1), "first": item.get("was_discovered") is False,
                         "when": str(item.get("scan_timestamp") or "")[:10]})
        rows.sort(key=lambda row: -row["value"])
        return rows[:25]

    def _history_trip_markdown(self, summary):
        since = next((row for row in summary if row["label"] == "Since your last sale"), None)
        if not since:
            return ""
        cmdr = getattr(self, "cmdr_name", "") or "CMDR"
        return "\n".join([f"**CMDR {cmdr}: since my last sale**", "",
                          f"- {since['sessions']} sessions, {since['jumps']:,} jumps, {since['ly']:,.0f} ly",
                          f"- Farthest from Sol: {since['far'] or 0:,} ly",
                          f"- {since['firsts']:,} systems with first discoveries, {since['bodies']:,} bodies scanned, {since['mapped']:,} mapped",
                          f"- {since['species']:,} species analysed, {since['footfalls']:,} first footfalls, {since['codex']:,} Codex entries",
                          f"- Deaths: {since['deaths']}", "", "_Void Compass_"])

    def _history_export(self, kind):
        """Rows for a CSV: firsts, jumps, codex, trips, route, unsold."""
        if kind == "jumps":
            history = getattr(self, "travel_history", None)
            with history.lock:
                rows = list(history.rows)
            return ["Time", "System", "X", "Y", "Z", "Star class", "Jump ly"], [row[:7] for row in rows]
        if kind == "codex":
            codex = getattr(self, "codex_index", None)
            from voidcompass.exploration import bio_reference
            return ["Time", "Entry", "Name", "Region", "System address", "Body id"], [
                [row[0], row[1], bio_reference.english_name(row[1]), row[2], row[3], row[4]] for row in (codex.entries() if codex else [])]
        if kind == "firsts":
            items = self._survey_all_items()
            return ["System", "Body", "Class", "Scanned", "Mapped", "Value"], [
                [item.get("_system"), item.get("name"), item.get("planet_class") or item.get("star_type"),
                 item.get("scan_timestamp"), "yes" if item.get("dss_complete") else "", system_table._value_max(item)]
                for item in items if item.get("was_discovered") is False]
        if kind == "trips":
            return ["Start", "End", "Paid", "Cartography", "Exobiology", "Estimate", "Jumps", "Ly", "Cr/h", "Cr/jump", "Deaths"], [
                [t["start"], t["end"], t["paid"], t["carto"], t["bio"], t["estimate"], t["jumps"], t["ly"], t["cr_h"], t["cr_jump"], t["deaths"]]
                for t in self._history_trips()]
        if kind == "route":
            route = self._route() if hasattr(self, "_route") else None
            return ["Stop", "System", "Jumps", "Ly", "Neutron", "Refuel"], [
                [i, row["system"], row.get("jumps"), row.get("distance"), "yes" if row.get("neutron") else "", "yes" if row.get("refuel") else ""]
                for i, row in enumerate((route or {}).get("rows") or ())]
        if kind == "unsold":
            unsold = self._firsts_payload()["unsold"] if hasattr(self, "_firsts_payload") else []
            return ["System", "First discoveries", "Mapped", "Value", "Found"], [
                [row["system"], row["bodies"], row["mapped"], row["value"], row["first"]] for row in unsold]
        if kind == "edsm":
            data = self._edsm_log()
            return ["Time", "System", "First discovery"], [[row.get("date"), row.get("system"), "yes" if row.get("firstDiscover") else ""]
                                                          for row in data.get("logs") or ()]
        return None

    # -- EDSM's flight log, for visits from before your journals -------------------------------------------
    def _edsm_log(self):
        try:
            with open(self._profile_path(EDSM_LOG_FILE), encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _edsm_import(self):
        state = self._html_profile_transient("_edsm_import_state", {"status": "ready", "detail": ""})
        key = str(self.config.get("edsm_api_key") or "")
        name = str(self.config.get("edsm_cmdr_name") or getattr(self, "cmdr_name", "") or "")
        if not key or not name:
            state.update(status="failed", detail="Set your EDSM commander name and API key in Settings › Integrations first.")
            self._schedule_html_dashboard_publish(immediate=True)
            return False
        if state["status"] == "working":
            return True
        history = getattr(self, "travel_history", None)
        first = str(history.rows[0][0]) if history is not None and history.rows else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state.update(status="working", detail="Asking EDSM for your flight log, a week at a time…")
        self._schedule_html_dashboard_publish(immediate=True)

        def work():
            import requests
            logs, empty, end = [], 0, datetime.strptime(first[:19], "%Y-%m-%dT%H:%M:%S")
            calls = 0
            while empty < 26 and calls < 520:
                start = end - timedelta(days=7)
                try:
                    reply = requests.get("https://www.edsm.net/api-logs-v1/get-logs", timeout=30, params={
                        "commanderName": name, "apiKey": key,
                        "startDateTime": start.strftime("%Y-%m-%d %H:%M:%S"), "endDateTime": end.strftime("%Y-%m-%d %H:%M:%S")})
                    data = reply.json()
                except Exception as exc:
                    return logs, f"EDSM stopped answering: {exc}"
                calls += 1
                if data.get("msgnum") not in (100, None):
                    return logs, f"EDSM: {data.get('msg') or data.get('msgnum')}"
                week = [row for row in data.get("logs") or () if isinstance(row, dict)]
                logs += week
                empty = 0 if week else empty + 1
                end = start
                time.sleep(1.0)
            return logs, ""

        def done(result, error):
            logs, note = result if result else ([], error)
            if logs:
                data = {"imported": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "before": first, "logs": logs}
                path = self._profile_path(EDSM_LOG_FILE)
                try:
                    with open(f"{path}.tmp", "w", encoding="utf-8") as handle:
                        json.dump(data, handle)
                    os.replace(f"{path}.tmp", path)
                except OSError as exc:
                    note = str(exc)
            state.update(status="failed" if note and not logs else "ready",
                         detail=(f"{len(logs):,} visits from before your journals, kept apart from them." if logs else "EDSM had nothing before your journals.")
                         + (f" {note}" if note else ""))
            self._schedule_html_dashboard_publish(immediate=True)

        self._survey_task("edsm-log", lambda: work(), lambda result, error: done(result, error))
        return True

    def _history_payload(self, period):
        rows = self._history_sessions(period or "all")
        summary = self._history_summary(rows if (period or "all") == "all" else self._history_sessions("all"))
        edsm = self._edsm_log()
        imported = self._html_profile_transient("_edsm_import_state", {"status": "ready", "detail": ""})
        return {"sessions": rows, "summary": summary, "trips": self._history_trips(), "top": self._history_top(),
                "records": self._survey_records() if hasattr(self, "_survey_records") else [],
                "trip_markdown": self._history_trip_markdown(summary),
                "periods": ["all", *sorted({row["started"][:4] for row in self._history_sessions("all")}, reverse=True)],
                "edsm": {"count": len(edsm.get("logs") or ()), "imported": edsm.get("imported"), "status": imported["status"],
                         "detail": imported["detail"], "systems": len({row.get("system") for row in edsm.get("logs") or ()})},
                "books_ready": bool((getattr(self, "_cmdr_books", None) or {}).get("book"))}

    def _history_data(self, name, query):
        if name == "history":
            self._cmdr_book()
            return self._history_payload(query.get("period"))
        if name == "history-export":
            result = self._history_export(str(query.get("kind") or ""))
            if result is None:
                return None
            header, rows = result
            return {"header": header, "rows": rows}
        return None

    def _history_command(self, operation, payload):
        if operation == "history_copy_trip":
            summary = self._history_summary(self._history_sessions("all"))
            return self._html_copy_text(self._history_trip_markdown(summary), "trip")
        if operation == "history_edsm_import":
            return self._edsm_import()
        return False
