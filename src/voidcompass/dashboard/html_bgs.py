"""The BGS tab (5.5.2.4): overview with alerts, factions, systems (and any
system looked up on EDSM), conflicts, your work per tick with a Discord
report, and a guide to the states. The record is dashboard_bgs_mixin's."""

from __future__ import annotations

import time
from urllib.parse import quote
import webbrowser

from voidcompass.bgs import ticks as tick_clock
from voidcompass.bgs import views

_VIEWS = ("overview", "factions", "systems", "conflicts", "activity", "states")


def _text(value, limit=200):
    return str(value if value is not None else "").strip()[:limit]


def _integer(value, default=None):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


class HtmlBgsMixin:
    def _bgs_ui(self):
        return self._html_profile_transient("_html_bgs_state", {
            "view": "overview", "faction": None, "system": None, "faction_query": "", "system_query": "",
            "system_filter": "", "tick": None, "lookup": {"pending": False, "name": "", "error": ""},
            "notice": "", "error": "", "chart_days": 90,
        })

    # -- snapshot --------------------------------------------------------
    def _html_bgs_workspace(self):
        ui = self._bgs_ui()
        store = getattr(self, "bgs_store", None)
        data = {"view": ui["view"], "notice": ui["notice"], "error": ui["error"], "lookup": ui["lookup"],
                "online": self._bgs_online(), "ready": store is not None}
        if store is None:
            return data
        known_ticks = store.ticks()
        last_tick = known_ticks[-1] if known_ticks else None
        tick_start, estimated = tick_clock.tick_for(time.time(), known_ticks)
        tracked = store.tracked("faction")
        state = getattr(self, "_bgs_import_state", {}) or {}
        data.update({
            "import": {"running": bool(state.get("running")), "done": bool(state.get("done"))},
            "tick": {"last": last_tick, "last_label": tick_clock.label(last_tick) if last_tick else "",
                     "current": tick_start, "current_label": tick_clock.label(tick_start), "estimated": estimated},
            "tracked_factions": tracked, "tracked_systems": [str(item) for item in store.tracked("system")],
            "current_system": getattr(self, "current_sys", "") or "",
            "counts": store.query("SELECT (SELECT COUNT(*) FROM systems) systems, "
                                  "(SELECT COUNT(DISTINCT faction) FROM presence) factions, "
                                  "(SELECT COUNT(*) FROM activity) activity")[0],
        })
        alerts = views.alerts(store)
        data["alert_count"] = sum(1 for row in alerts if row["level"] in ("danger", "warn"))
        view = ui["view"]
        if view == "overview":
            address = getattr(self, "current_system_address", None)
            data["current"] = views.system_picture(store, address, tracked) if address is not None else None
            data["alerts"] = alerts[:40]
            data["tracked"] = [self._bgs_faction_brief(store, name, alerts) for name in tracked]
            work = views.activity(store, tick_start, known_ticks)["detail"]
            data["this_tick"] = work
        elif view == "factions":
            rows, total = views.factions_list(store, ui["faction_query"])
            data["factions"] = {"rows": rows, "total": total, "query": ui["faction_query"]}
            if ui["faction"]:
                data["faction"] = views.faction_detail(store, ui["faction"], tick_start)
                if data["faction"]:
                    data["faction"]["alerts"] = [row for row in alerts if row.get("faction") == ui["faction"]]
        elif view == "systems":
            rows, total = views.systems_list(store, ui["system_query"], ui["system_filter"])
            data["systems"] = {"rows": rows, "total": total, "query": ui["system_query"], "filter": ui["system_filter"]}
            if ui["system"] is not None:
                picture = views.system_picture(store, ui["system"], tracked)
                if picture:
                    picture["history"] = views.history(store, ui["system"], days=ui["chart_days"])
                    picture["chart_days"] = ui["chart_days"]
                    picture["activity"] = views._kind_rows(store.query(
                        "SELECT kind, SUM(amount) amount, SUM(count) count FROM activity WHERE system_address = ? GROUP BY kind",
                        (ui["system"],)))
                    picture["visits"] = (store.query("SELECT visits FROM systems WHERE system_address = ?", (ui["system"],)) or [{}])[0].get("visits")
                data["system"] = picture
        elif view == "conflicts":
            data["conflicts"] = views.conflicts(store)
        elif view == "activity":
            data["activity"] = views.activity(store, ui["tick"], known_ticks)
        elif view == "states":
            data["states"] = views.state_catalogue()
        return data

    @staticmethod
    def _bgs_faction_brief(store, name, alerts):
        rows = store.query("SELECT COUNT(*) systems, SUM(controlling) controlled, AVG(influence) average FROM presence WHERE faction = ?", (name,))
        row = rows[0] if rows else {}
        mine = [alert for alert in alerts if alert.get("faction") == name]
        return {"name": name, "systems": row.get("systems") or 0, "controlled": row.get("controlled") or 0,
                "average": row.get("average"), "danger": sum(1 for alert in mine if alert["level"] == "danger"),
                "warn": sum(1 for alert in mine if alert["level"] == "warn")}

    # -- commands --------------------------------------------------------
    def _handle_bgs_command(self, operation, payload):
        ui = self._bgs_ui()
        ui["notice"], ui["error"] = "", ""
        store = getattr(self, "bgs_store", None)
        if store is None:
            return False
        if operation == "view":
            view = _text(payload.get("view"), 20)
            ui["view"] = view if view in _VIEWS else "overview"
            return True
        if operation == "faction":
            ui["faction"] = _text(payload.get("name"), 160) or None
            ui["view"] = "factions"
            return True
        if operation == "system":
            ui["system"] = _integer(payload.get("address"))
            ui["view"] = "systems"
            return True
        if operation == "search_factions":
            ui["faction_query"] = _text(payload.get("query"), 80)
            return True
        if operation == "search_systems":
            ui["system_query"] = _text(payload.get("query"), 80)
            only = _text(payload.get("only"), 20)
            ui["system_filter"] = only if only in ("", "tracked", "conflicts") else ""
            return True
        if operation == "chart_days":
            days = _integer(payload.get("days"), 90)
            ui["chart_days"] = days if days in (1, 7, 30, 90, 365, 3650) else 90
            return True
        if operation == "track_faction":
            name = _text(payload.get("name"), 160)
            if name:
                store.set_tracked("faction", name, bool(payload.get("value")))
            return bool(name)
        if operation == "track_system":
            address = _integer(payload.get("address"))
            if address is not None:
                store.set_tracked("system", str(address), bool(payload.get("value")))
            return address is not None
        if operation == "tick":
            ui["tick"] = float(payload["start"]) if payload.get("start") not in (None, "") else None
            ui["view"] = "activity"
            return True
        if operation == "refresh_tick":
            return self._bgs_refresh_tick(reschedule=False)
        if operation == "copy_report":
            known = store.ticks()
            detail = views.activity(store, ui["tick"], known)["detail"]
            if not detail or not detail["systems"]:
                ui["error"] = "No BGS work in that tick to report."
                return True
            return self._html_copy_text(detail["report"])
        if operation == "lookup":
            return self._bgs_lookup_command(_text(payload.get("system"), 160), ui, store, refresh=bool(payload.get("refresh")))
        if operation == "open":
            kind, name = _text(payload.get("kind"), 20), _text(payload.get("name"), 160)
            urls = {
                "inara_faction": f"https://inara.cz/elite/minorfaction/?search={quote(name)}",
                "inara_system": f"https://inara.cz/elite/starsystem/?search={quote(name)}",
                "edsm_system": f"https://www.edsm.net/en/search/systems/index/name/{quote(name)}",
            }
            if kind in urls and name:
                webbrowser.open_new_tab(urls[kind])
            return True
        return False

    @staticmethod
    def _bgs_lookup_notice(outcome, refresh):
        """Say what the EDSM reply changed, so a refresh never looks dead."""
        if not outcome:
            return ""
        system, edsm_ts = outcome["system"], outcome["edsm_ts"]
        if outcome["status"] == "new":
            return f"Updated {system} from EDSM: its latest report is from {tick_clock.label(edsm_ts)}."
        if outcome["status"] == "older":
            mine = "your own visit" if outcome["record_source"] == "journal" else "what you already have"
            return (f"EDSM's latest report for {system} is from {tick_clock.label(edsm_ts)}, older than {mine} "
                    f"({tick_clock.label(outcome['record_ts'])}), so that stays. Its history was still added to the chart.")
        if refresh:
            return f"EDSM has nothing newer for {system}: its latest report is still {tick_clock.label(edsm_ts)}."
        return ""

    def _bgs_lookup_command(self, name, ui, store, refresh=False):
        if not name:
            ui["error"] = "Type a system name to look up."
            return True
        local = store.find_system(name)
        ui["view"] = "systems"
        if local:
            ui["system"] = local["system_address"]
        ui["lookup"] = {"pending": True, "name": name, "error": ""}

        def done(address, error, outcome=None):
            ui["lookup"] = {"pending": False, "name": name, "error": error or ""}
            if address is not None:
                ui["system"] = address
            elif not local and error:
                ui["error"] = error
            ui["notice"] = self._bgs_lookup_notice(outcome, refresh)
            self._schedule_html_dashboard_publish(immediate=True)
        if not self._bgs_lookup(name, done, refresh=refresh):
            ui["lookup"] = {"pending": False, "name": name, "error": ""}
            if not local:
                ui["error"] = "Not in your journal record. Turn on BGS online in Settings > Integrations to look it up on EDSM."
        return True
