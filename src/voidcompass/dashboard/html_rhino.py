"""The Rhino page: surface mining in one place. A big map of the ground round
you (the Rhino Map overlay's, drawn larger), the keys as buttons, your marked
deposits with their details to set, the rigs and holds, the survey, the rig
plan and the planning circle; every deposit you've marked anywhere; and
where in this system the Rhino is worth landing."""
from __future__ import annotations

import logging
import webbrowser

from voidcompass.mining.planet_materials import PlanetMaterialsStore, rhino_commodity_choices
from voidcompass.dashboard.dashboard_rigs_mixin import runs_summary
from voidcompass.mining import regrowth, rhino_report
from voidcompass.mining.rhino_intelligence import AMOUNTS, DENSITIES

# The keys the page shows beside its buttons, by action.
RHINO_KEYS = ("rhino_survey_centre", "rhino_survey_edge", "rhino_deposit_mark", "rhino_deposit_mined_out",
              "rhino_trace", "rhino_circle", "rhino_site_save", "rig_clear", *(f"rig_{slot}" for slot in range(1, 7)))
EDITABLE = ("materials", "rigs", "amount", "density", "notes", "name")
# A target the Rhino page set clears itself once you're this close to it.
ARRIVED_DEPOSIT_M = 40.0
ARRIVED_SITE_M = 200.0


def _int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


class HtmlRhinoMixin:
    def _rhino_keys(self):
        config = getattr(self, "config", None) or {}
        return {action: str(config.get(f"overlay_hotkey_{action}") or "") for action in RHINO_KEYS}

    def _rhino_run(self):
        """The Rhino run the mining engine is keeping, if it's a surface one."""
        engine = getattr(self, "specialist_engine", None)
        try:
            snapshot = engine.mining_snapshot() if engine is not None else {}
        except Exception:
            return None
        session = snapshot.get("session") or {}
        if str(session.get("mode") or "") != "surface":
            return None
        return {key: session.get(key) for key in ("refined_t", "tons_per_hour", "cargo_removed_t", "started", "ended",
                                                    "duration_s", "yield")} | {"active": bool(snapshot.get("active"))}

    def _rhino_found(self):
        """The commodities you've found with the Rhino (your deposits and what
        your rigs gave), most found first."""
        counts = {}
        try:
            rows = self._planet_materials_store().rows()
        except Exception:
            rows = []
        names = [str(row.get("materials") or "").replace(";", ",").split(",")[0].strip()
                 for row in rows if str(row.get("site_type") or "site") == "site"]
        names += [str(row.get("commodity") or "") for row in getattr(self.rig_store(), "yields", None) or ()]
        for name in names:
            if name and name.casefold() != "unknown":
                counts[name] = counts.get(name, 0) + 1
        return sorted(counts, key=lambda name: (-counts[name], name))

    def _rhino_sites_everywhere(self):
        """Every deposit you've marked, on any planet."""
        try:
            rows = self._planet_materials_store().rows()
        except Exception:
            logging.debug("Rhino page: sites skipped", exc_info=True)
            return []
        out = []
        for row in rows:
            if str(row.get("site_type") or "site") != "site":
                continue
            out.append({"id": row.get("id"), "system": row.get("system"), "body": row.get("body"), "name": row.get("name"),
                        "materials": row.get("materials"), "rigs": _int(row.get("rigs")), "amount": row.get("amount") or "",
                        "density": row.get("density") or "", "depleted": bool(row.get("depleted")),
                        "regrowth": regrowth.standing(row), "latitude": row.get("latitude"), "longitude": row.get("longitude"),
                        "signal": row.get("location_index"), "updated": row.get("updated_at"),
                        "estimate": row.get("tons_left") or "", "notes": row.get("notes") or ""})
        return out

    def _html_rhino_workspace(self):
        from voidcompass.overlays.rig_tracker import rig_drop_m, rig_spacing_m, rig_warn_m
        from voidcompass.overlays.surface_map import rig_words
        where = self._mining_where() if callable(getattr(self, "_mining_where", None)) else {}
        place = self._rig_place()
        surface = facts = rigs = None
        if place:
            for name, build in (("map", self._rhino_surface_fresh), ("facts", self._survey_facts),
                                ("rigs", self.api_rigs)):
                try:
                    value = build()
                except Exception:
                    logging.debug("Rhino page %s skipped", name, exc_info=True)
                    value = None
                if name == "map":
                    surface = value
                elif name == "facts":
                    facts = value
                else:
                    rigs = value
        here = []
        if place:
            by_id = {item.get("id"): item for item in (surface or {}).get("deposits") or ()}
            for row in self._deposit_rows(place[0], place[1], near=(place[2], place[3], place[4])):
                drawn = by_id.get(row.get("id")) or {}
                here.append({"id": row.get("id"), "name": row.get("name"), "materials": row.get("materials"),
                             "rigs": _int(row.get("rigs")), "amount": row.get("amount") or "", "density": row.get("density") or "",
                             "depleted": bool(row.get("depleted")), "notes": row.get("notes") or "",
                             "regrowth": regrowth.standing(row),
                             "signal": row.get("location_index"), "estimate": row.get("tons_left") or "",
                             "distance": drawn.get("distance"), "bearing": drawn.get("bearing"), "n": drawn.get("n")})
            here.sort(key=lambda row: (row["distance"] is None, row["distance"] or 0))
        config = getattr(self, "config", None) or {}
        words = rig_words(surface)
        return {
            "where": where, "on_surface": place is not None, "body": place[1] if place else where.get("body") or "",
            "system": place[0] if place else where.get("system") or "",
            "in_rhino": self._rig_in_rhino(), "map": surface, "facts": facts or {}, "rigs": rigs or {},
            "holds": self._rig_holds(), "run": self._rhino_run(), "rig_words": {"text": words[0], "tone": words[1]} if words else None,
            "deposits": here, "sites": self._rhino_sites_everywhere(), "catalogue": rhino_commodity_choices(config, self._rhino_found()),
            "saved_sites": self._rhino_saved_sites(), "site_here": self._rhino_site_here_brief(), "report": self._rhino_report_brief(),
            "amounts": list(AMOUNTS), "densities": list(DENSITIES),
            "prospects": self._mining_system_grounds() if callable(getattr(self, "_mining_system_grounds", None)) else [],
            "ground": self._mining_ground_here(where) if callable(getattr(self, "_mining_ground_here", None)) and where else None,
            "signals": self._surface_mining_signals(place[1]) if place else 0,
            "signal": self._rhino_signal_here(), "tracing": bool(getattr(self, "_rig_trace", None)),
            "keys": self._rhino_keys(), "target": self._rhino_target_brief(place),
            "aboard": (rigs or {}).get("aboard") or (self._rhino_aboard_summary() if place else None),
            "settings": {"spacing_m": rig_spacing_m(config), "warn_m": rig_warn_m(config), "drop_m": rig_drop_m(config)},
        }

    def _rhino_target_brief(self, place):
        """The planet compass's target, for the page to show and clear: its
        name, and how far and which way when it's on the planet you're on."""
        if not getattr(self, "target_latlon_active", False) or getattr(self, "target_lat", None) is None:
            return None
        from voidcompass.overlays.rig_tracker import bearing_deg, surface_distance_m
        brief = {"label": str(getattr(self, "ground_target_label", "") or "Target"),
                 "body": str(getattr(self, "ground_target_body", "") or "")}
        if place and (not brief["body"] or brief["body"].casefold() == place[1].casefold()):
            brief["distance"] = round(surface_distance_m(place[2], place[3], self.target_lat, self.target_lon, place[4]))
            brief["bearing"] = round(bearing_deg(place[2], place[3], self.target_lat, self.target_lon))
        return brief

    def _rhino_set_target(self, lat, lon, reach, **target):
        self.set_ground_target(lat, lon, **target)
        self._rhino_target = {"at": (getattr(self, "target_lat", None), getattr(self, "target_lon", None)), "reach": reach, "label": target.get("label") or "Target"}
        return True

    def _rhino_target_watch(self):
        """A target the Rhino page set goes once you get there. One set
        anywhere else (the Planetary page's waypoints) is left alone."""
        mine = getattr(self, "_rhino_target", None)
        if not mine:
            return False
        here = (getattr(self, "target_lat", None), getattr(self, "target_lon", None))
        if not getattr(self, "target_latlon_active", False) or here != mine["at"]:
            self._rhino_target = None
            return False
        place = self._rig_place()
        if place is None:
            return False
        from voidcompass.overlays.rig_tracker import surface_distance_m
        if surface_distance_m(place[2], place[3], self.target_lat, self.target_lon, place[4]) > mine["reach"]:
            return False
        self._rhino_target = None
        self.clear_ground_target()
        self._rig_say("ARRIVED", mine["label"], severity="success")
        self._rhino_after_change()
        return True

    def _rhino_saved_sites(self):
        """Every mining location you've saved, for SITES: no coverage grid (it's
        big and the page doesn't draw it), with what its runs took and are worth."""
        here = (str(getattr(self, "current_sys", "") or "").casefold(), str(getattr(self, "current_body_name", "") or "").casefold())
        try:
            prices = self._rhino_prices()
        except Exception:
            prices = {}
        out = []
        for site in self.survey_store().all_sites():
            survey = site.get("survey") or {}
            earned, total = rhino_report.earnings(site, prices)
            out.append({key: site.get(key) for key in ("id", "name", "note", "signal", "system", "body", "deposits", "tonnes",
                                                       "saved", "updated", "centre")}
                       | {"runs": runs_summary(site.get("runs")), "earned": earned, "earned_total": total,
                          "swept": survey.get("percent"), "edge": bool(survey.get("edge")), "radius_m": survey.get("radius_m"),
                          "plans": len(site.get("plans") or ()),
                          "here": (str(site.get("system") or "").casefold(), str(site.get("body") or "").casefold()) == here})
        return out

    # -- a saved site written up (5.8.3) ------------------------------------------------------
    def _rhino_find_site(self, site_id, system=None, body=None):
        site_id = str(site_id or "")
        for site in self.survey_store().all_sites():
            if str(site.get("id")) == site_id and (system is None or str(site.get("system") or "").casefold() == str(system).casefold()) \
                    and (body is None or str(site.get("body") or "").casefold() == str(body).casefold()):
                return site
        return None

    def _rhino_site_report(self, site_id, system=None, body=None):
        """The site as text for Discord or a file, or None."""
        from voidcompass.dashboard.dashboard_rigs_mixin import rhino_surface_commodity
        site = self._rhino_find_site(site_id, system, body)
        if site is None:
            return None
        ids = {item for item in (site.get("deposits") or {}).get("ids") or () if item is not None}
        try:
            deposits = [row for row in self._planet_materials_store().rows() if row.get("id") in ids]
        except Exception:
            deposits = []
        try:
            prices = self._rhino_prices()
        except Exception:
            prices = {}
        return rhino_report.site_report(site, deposits, prices, runs_summary(site.get("runs")), commodity_of=rhino_surface_commodity)

    def _rhino_report_brief(self):
        """The report the page has open, if any: {"id", "text"}."""
        open_ = getattr(self, "_rhino_report_open", None)
        if not open_:
            return None
        text = self._rhino_site_report(*open_)
        if text is None:
            self._rhino_report_open = None
            return None
        return {"id": open_[0], "text": text}

    def _rhino_report_save(self, site_id, system, body, folder):
        """REPORT › SAVE: the report as a text file in ``folder``; the file, or None."""
        import re
        from pathlib import Path
        text = self._rhino_site_report(site_id, system, body)
        target = Path(str(folder or "")).expanduser()
        if text is None or not str(folder or "").strip() or not target.is_dir():
            return None
        site = self._rhino_find_site(site_id, system, body) or {}
        stem = re.sub(r"[^A-Za-z0-9]+", "_", str(site.get("name") or "rhino_site")).strip("_")[:60] or "rhino_site"
        path = target / f"{stem}_report.md"
        path.write_text(text + "\n", encoding="utf-8")
        return path

    def api_rhino_site_report(self, site_id):
        """The Local API: a saved site's report."""
        from voidcompass.services.local_api import ApiError
        site = self._rhino_find_site(site_id)
        if site is None:
            raise ApiError(404, "No saved Rhino site with that id: GET /api/v1/rhino lists the one you're at")
        return {"id": site.get("id"), "name": site.get("name"), "system": site.get("system"), "body": site.get("body"),
                "text": self._rhino_site_report(site_id)}

    def _rhino_site_here_brief(self):
        site = self._rhino_site_here() if self._rig_place() else None
        return {"id": site.get("id"), "name": site.get("name"), "updated": site.get("updated")} if site else None

    def _rhino_site_operation(self, operation, payload):
        system, body, site_id = str(payload.get("system") or ""), str(payload.get("body") or ""), str(payload.get("id") or "")
        store = self.survey_store()
        if operation == "site_save":
            site = self._rhino_site_save()
            name = str(payload.get("name") or "").strip()
            place = self._rig_place()
            if site and name and place and name != site.get("name"):
                store.change_site(place[0], place[1], site["id"], name=name)
            return bool(site)
        if operation == "site_forget":
            return bool(payload.get("confirmed")) and store.forget_site(system, body, site_id)
        if operation == "site_rename":
            return store.change_site(system, body, site_id, name=payload.get("name"), note=payload.get("note"))
        if operation == "site_report":
            # REPORT opens the write-up on the page (again: closes it).
            wanted = (site_id, system, body)
            self._rhino_report_open = None if getattr(self, "_rhino_report_open", None) == wanted else wanted
            return True
        if operation == "site_report_copy":
            text = self._rhino_site_report(site_id, system, body)
            return bool(text) and self._html_copy_text(text, "site report")
        if operation == "site_report_save":
            written = self._rhino_report_save(site_id, system, body, payload.get("path"))
            feed = getattr(self, "add_event_feed_entry", None)
            if written is not None and callable(feed):
                feed("MINING", f"Site report saved: {written}", severity="INFO")
            return written is not None
        site = next((row for row in store.sites(system, body) if row.get("id") == site_id), None)
        if site is None:
            return False
        if operation == "site_target":
            centre = site.get("centre") or ()
            if len(centre) != 2:
                return False
            return self._rhino_set_target(centre[0], centre[1], ARRIVED_SITE_M, system=system, body=body,
                                          label=site.get("name") or "Mining location")
        if operation == "site_resume":
            place = self._rig_place()
            if place is None or (place[0].casefold(), place[1].casefold()) != (system.casefold(), body.casefold()):
                self._rig_say("RHINO SITE", "Resume a site's survey on its own planet", severity="warn")
                return False
            done = store.resume_site(system, body, site_id)
            if done:
                self._rig_say("SURVEY RESUMED", f"{site.get('name')} · {int((site.get('survey') or {}).get('percent') or 0)}% swept so far",
                              severity="success")
            return done
        return False

    def _rhino_site(self, site_id):
        try:
            wanted = int(site_id)
        except (TypeError, ValueError):
            return None
        return next((row for row in self._planet_materials_store().rows() if int(row.get("id") or -1) == wanted), None)

    def _html_rhino_operation(self, operation, payload):
        """The Rhino page's buttons. True when something changed."""
        payload = payload or {}
        keys = {"deposit_mark": self._deposit_mark_key, "trace": self._rig_trace_key, "trace_forget": self._rig_forget_plan,
                "circle": self._rig_circle_key, "forget_rigs": self._rig_clear_here}
        if operation in ("survey_centre", "survey_edge", "survey_clear"):
            done = self._survey_mark(operation.split("_", 1)[1])
        elif operation in keys:
            done = keys[operation]()
        elif operation == "rig":
            slot = _int(payload.get("slot"))
            done = self._rig_mark(slot) if 1 <= slot <= 6 else None
        elif operation in ("site_save", "site_forget", "site_rename", "site_target", "site_resume", "site_report",
                           "site_report_copy", "site_report_save"):
            done = self._rhino_site_operation(operation, payload)
        elif operation in ("deposit_save", "deposit_mined_out", "deposit_delete", "deposit_navigate", "deposit_regrown"):
            done = self._rhino_deposit_operation(operation, payload)
            if done and operation != "deposit_navigate":
                self._rhino_site_keep()
        elif operation == "target_clear":
            done = bool(getattr(self, "target_latlon_active", False))
            self._rhino_target = None
            self.clear_ground_target()
        elif operation == "copy_system":
            done = self._html_copy_text(str(payload.get("system") or "")[:140])
        elif operation == "open_spansh":
            webbrowser.open_new_tab("https://spansh.co.uk/bodies")
            done = True
        else:
            return False
        self._rhino_after_change()
        return bool(done)

    def _rhino_deposit_operation(self, operation, payload):
        row = self._rhino_site(payload.get("id"))
        if row is None:
            return False
        store = self._planet_materials_store()
        if operation == "deposit_delete":
            if not payload.get("confirmed"):
                return False
            if str(getattr(self, "ground_target_site_id", "")) == str(row["id"]):
                self.clear_ground_target()
            return store.delete(row["id"])
        if operation == "deposit_navigate":
            return self._rhino_set_target(row["latitude"], row["longitude"], ARRIVED_DEPOSIT_M, system=row["system"],
                                          body=row["body"], label=row.get("name") or "Deposit", site_id=row["id"])
        if operation == "deposit_mined_out":
            return bool(self._deposit_worked_out(dict(row)))
        if operation == "deposit_regrown":
            return self._deposit_grown_back(dict(row))
        changes = {}
        for key in EDITABLE:
            if key in payload:
                changes[key] = str(payload.get(key) or "").strip()
        if "materials" in changes and not changes["materials"]:
            changes["materials"] = "Unknown"
        if "name" in changes and not changes["name"]:
            changes["name"] = (changes.get("materials") or row.get("materials") or "Deposit").split(",", 1)[0]
        if "rigs" in changes:
            changes["rigs"] = max(0, min(12, _int(changes["rigs"])))
        if changes.get("amount") and changes["amount"] not in AMOUNTS:
            changes.pop("amount")
        if changes.get("density") and changes["density"] not in DENSITIES:
            changes.pop("density")
        changes["depleted"] = 1 if (changes.get("amount", row.get("amount")) == "Depleted") else 0
        try:
            store.save({**row, **changes})
        except ValueError as exc:
            logging.info("Deposit not saved: %s", exc)
            return False
        return True


__all__ = ["HtmlRhinoMixin", "PlanetMaterialsStore"]
