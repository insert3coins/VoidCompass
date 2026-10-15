"""Your home system (5.5.4), for MainDashboard: set in Settings, its
coordinates found from your travel history or EDSM."""
from __future__ import annotations

import logging

from voidcompass.core import home_anchor


class DashboardHomeMixin:
    def _home_resolve(self):
        """The home system just changed: find where it is."""
        name = str(self.config.get("home_system") or "").strip()
        self._home_status = "sol"
        if not name or name.casefold() == home_anchor.SOL.casefold():
            self.config["home_system"] = ""
            self.config["home_system_pos"] = None
            self._home_changed()
            return
        history = getattr(self, "travel_history", None)
        rows = []
        if history is not None:
            with history.lock:
                rows = list(history.rows)
        position = home_anchor.from_history(rows, name)
        if position is not None:
            self.config["home_system_pos"] = position
            self._home_status = "found"
            self._home_changed()
            return
        self.config["home_system_pos"] = None
        edsm = getattr(self, "edsm", None)
        if edsm is None or not hasattr(edsm, "fetch_system_coords"):
            self._home_status = "unknown"
            self._home_changed()
            return
        self._home_status = "looking"
        asked = name

        def answer(found_name, coords):
            def apply():
                if str(self.config.get("home_system") or "").strip() != asked:
                    return  # changed again while EDSM answered
                if isinstance(coords, dict) and all(axis in coords for axis in "xyz"):
                    self.config["home_system"] = str(found_name or asked)
                    self.config["home_system_pos"] = [float(coords["x"]), float(coords["y"]), float(coords["z"])]
                    self._home_status = "found"
                else:
                    self._home_status = "unknown"
                self._home_changed()
            post = getattr(self, "_ui_post", None)
            if callable(post):
                post(apply, key="home-system")
            else:
                apply()
        try:
            edsm.fetch_system_coords(name, answer)
        except Exception as exc:
            logging.warning("Home system lookup failed: %s", exc)
            self._home_status = "unknown"
        self._home_changed()

    def _home_changed(self):
        try:
            self._persist_config()
        except Exception:
            logging.debug("Home system save skipped", exc_info=True)
        for attr in ("galaxy_minimap_hud",):
            overlay = getattr(self, attr, None)
            if overlay is not None and hasattr(overlay, "apply_settings"):
                overlay.apply_settings()
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=True)

    def _home_settings(self):
        """For the Settings page: the home in use and how its lookup went."""
        anchor = home_anchor.home(self.config)
        asked = str(self.config.get("home_system") or "").strip()
        status = getattr(self, "_home_status", None) or ("found" if anchor["custom"] else ("unknown" if asked else "sol"))
        return {"name": anchor["name"], "asked": asked, "custom": anchor["custom"], "status": status,
                "pos": [round(value, 2) for value in anchor["pos"]]}
