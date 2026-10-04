"""BGS (5.5.2.4): the record behind the BGS tab, kept per commander profile.

Live journal events go through the same reader as the history import
(bgs.journal), so both count your work the same way and each event once. The
whole history is read in the background after startup (later starts only read
new journals). With "BGS online" on (Settings > Integrations), the galaxy tick
is asked for every half hour and systems can be looked up on EDSM.
"""

from __future__ import annotations

import logging
import threading
import time

from voidcompass.bgs import edsm as bgs_edsm
from voidcompass.bgs.importer import import_journals
from voidcompass.bgs.journal import BgsJournal
from voidcompass.bgs.store import BgsStore
from voidcompass.bgs.ticks import fetch_latest_tick
from voidcompass.core.config import get_active_profile, get_profile_file

_TICK_REFRESH_MS = 30 * 60 * 1000


class DashboardBgsMixin:
    def _bgs_init(self, profile_key=None):
        key = profile_key or get_active_profile(self.config)
        self.bgs_store = BgsStore(get_profile_file(key, "bgs.db"))
        self.bgs_journal = BgsJournal(missions=self.bgs_store.missions())
        self._bgs_import_state = {"running": False, "done": False, "files": 0}
        self._bgs_generation = getattr(self, "_bgs_generation", 0) + 1

    def _bgs_switch_profile(self, profile_key):
        old = getattr(self, "bgs_store", None)
        self._bgs_init(profile_key)
        if old is not None:
            old.close()
        self._bgs_start_import()

    def _bgs_close(self):
        self._bgs_generation = getattr(self, "_bgs_generation", 0) + 1
        store = getattr(self, "bgs_store", None)
        if store is not None:
            store.close()

    def _bgs_online(self):
        return bool(self.config.get("bgs_online_enabled", True))

    # -- the journal -----------------------------------------------------
    def _bgs_observe(self, raw, startup_replay=False):
        reader = getattr(self, "bgs_journal", None)
        store = getattr(self, "bgs_store", None)
        if reader is None or store is None or not isinstance(raw, dict):
            return False
        try:
            changed = store.apply(reader.observe(raw))
        except Exception as exc:
            logging.debug("BGS event skipped [%s]: %s", raw.get("event"), exc)
            return False
        if changed and not startup_replay and getattr(self, "_html_dashboard_active_page", "") == "bgs":
            self._schedule_html_dashboard_publish()
        return changed

    # -- history ---------------------------------------------------------
    def _bgs_start_import(self):
        store = getattr(self, "bgs_store", None)
        state = getattr(self, "_bgs_import_state", None)
        if store is None or state is None or state.get("running"):
            return False
        journal_path = self.config.get("journal_path") or getattr(getattr(self, "watcher", None), "journal_path", None)
        commander, fid = getattr(self, "cmdr_name", None), getattr(self, "cmdr_fid", None)
        generation = self._bgs_generation
        state["running"] = True

        def run():
            files = 0
            try:
                files = import_journals(store, journal_path, commander, fid,
                                        should_stop=lambda: generation != self._bgs_generation)
            except Exception as exc:
                logging.warning("BGS history import skipped: %s", exc)
            if generation != self._bgs_generation:
                return

            def done():
                state.update(running=False, done=True, files=files)
                if files:
                    self.log(f"BGS record read {files:,} journals")
                self._schedule_html_dashboard_publish()
            self._ui_post(done, key=None)
        threading.Thread(target=run, name="bgs-history", daemon=True).start()
        return True

    # -- the tick --------------------------------------------------------
    def _bgs_refresh_tick(self, reschedule=True):
        if reschedule:
            try:
                self.root.call_later(_TICK_REFRESH_MS, self._bgs_refresh_tick)
            except Exception:
                pass
        if not self._bgs_online():
            return False
        store, generation = getattr(self, "bgs_store", None), getattr(self, "_bgs_generation", 0)
        if store is None:
            return False

        def run():
            ts = fetch_latest_tick()
            if ts and generation == self._bgs_generation and store.add_tick(ts):
                self._ui_post(self._schedule_html_dashboard_publish, key="bgs-tick")
        threading.Thread(target=run, name="bgs-tick", daemon=True).start()
        return True

    # -- EDSM lookups ----------------------------------------------------
    def _bgs_lookup(self, system_name, on_done, refresh=False):
        """Ask EDSM for a system's factions and their history. ``on_done`` gets
        ``(address, error, outcome)``; outcome says whether EDSM had anything
        newer than the record ("new", "same", or "older" than our own visit).

        A refresh adds a parameter EDSM ignores: its CDN keeps each reply a
        day per URL, so asking the same URL again would only repeat it."""
        if not self._bgs_online():
            on_done(None, "Turn on BGS online in Settings > Integrations to look systems up on EDSM.", None)
            return False
        edsm, store, generation = getattr(self, "edsm", None), self.bgs_store, self._bgs_generation
        name = str(system_name or "").strip()
        params = {"systemName": name, "showHistory": 1}
        if refresh:
            params["recheck"] = int(time.time())

        def run():
            error, address, outcome = "", None, None
            try:
                reply = edsm._limited_get(bgs_edsm.URL, params=params, timeout=15, retries=1)
                data = reply.json() if reply is not None else None
                snapshot, points = bgs_edsm.from_edsm(data)
                if snapshot is None:
                    error = f"EDSM has no faction data for {name}."
                    if isinstance(data, dict) and data.get("id64") and not data.get("factions"):
                        error = f"{data.get('name') or name} has no factions (unpopulated)."
                elif generation == self._bgs_generation:
                    added = store.add_snapshot(snapshot)
                    store.add_edsm_points(snapshot["system_address"], points)
                    address = snapshot["system_address"]
                    rows = store.query("SELECT ts, source FROM systems WHERE system_address = ?", (address,))
                    current = rows[0] if rows else {}
                    status = "same"
                    if current.get("ts") is not None and current["ts"] > snapshot["ts"]:
                        status = "older"
                    elif added:
                        status = "new"
                    outcome = {"status": status, "edsm_ts": snapshot["ts"], "system": snapshot["system"] or name,
                               "record_ts": current.get("ts"), "record_source": current.get("source") or ""}
            except Exception as exc:
                error = f"EDSM lookup failed: {exc}"
            if generation == self._bgs_generation:
                self._ui_post(lambda: on_done(address, error, outcome), key=None)
        threading.Thread(target=run, name="bgs-lookup", daemon=True).start()
        return True
