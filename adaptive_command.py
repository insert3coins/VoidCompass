"""Adaptive Command Deck state, objectives and deterministic briefings."""

from __future__ import annotations

import json
import os
import time

from persistence_queue import persistence_queue


MODES = (
    "general", "exploration", "mining", "combat", "ground",
    "engineering", "carrier", "colony", "station",
    "powerplay",
)

AUTOMATIC_MODE_IDLE_S = 1800.0

MODE_LABELS = {
    "general": "GENERAL FLIGHT",
    "exploration": "EXPLORATION",
    "mining": "MINING",
    "combat": "COMBAT",
    "ground": "GROUND OPS",
    "engineering": "ENGINEERING",
    "carrier": "CARRIER OPS",
    "colony": "ARCHITECT",
    "station": "STATION OPS",
    "powerplay": "POWERPLAY",
}

MODE_WORKSPACES = {
    "exploration": "EXPLORE", "mining": "SPECIALISTS",
    "combat": "SPECIALISTS", "engineering": "ENGINEER", "carrier": "CARRIER",
    "colony": "COLONY", "ground": "GROUND", "station": "DASHBOARD",
    "general": "DASHBOARD",
    "powerplay": "GALAXY",
}

# A value of True makes an instantiated overlay available in that activity;
# False suppresses it. Safety surfaces remain available in every scene.
DEFAULT_OVERLAY_SCENES = {
    "general": {"hud": True, "cargo_hud": True, "carrier_hud": True,
                "prospector_hud": True, "system_info_hud": True,
                "station_info_hud": True, "survey_status_hud": True,
                "colony_overlay": True},
    "exploration": {"hud": True, "cargo_hud": False, "carrier_hud": True,
                    "prospector_hud": False, "system_info_hud": True,
                    "station_info_hud": False, "survey_status_hud": True,
                    "colony_overlay": False},
    "mining": {"hud": True, "cargo_hud": True, "carrier_hud": False,
               "prospector_hud": True, "system_info_hud": False,
               "station_info_hud": False, "survey_status_hud": False,
               "colony_overlay": False},
    "combat": {"hud": True, "cargo_hud": False, "carrier_hud": False,
               "prospector_hud": False, "system_info_hud": False,
               "station_info_hud": False, "survey_status_hud": False,
               "colony_overlay": False},
    "ground": {"hud": True, "cargo_hud": False, "carrier_hud": False,
               "prospector_hud": False, "system_info_hud": True,
               "station_info_hud": False, "survey_status_hud": True,
               "colony_overlay": False},
    "engineering": {"hud": True, "cargo_hud": True, "carrier_hud": False,
                    "prospector_hud": False, "system_info_hud": False,
                    "station_info_hud": True, "survey_status_hud": False,
                    "colony_overlay": False},
    "carrier": {"hud": True, "cargo_hud": True, "carrier_hud": True,
                "prospector_hud": False, "system_info_hud": False,
                "station_info_hud": False, "survey_status_hud": False,
                "colony_overlay": False},
    "colony": {"hud": True, "cargo_hud": True, "carrier_hud": False,
               "prospector_hud": False, "system_info_hud": False,
               "station_info_hud": True, "survey_status_hud": False,
               "colony_overlay": True},
    "station": {"hud": True, "cargo_hud": True, "carrier_hud": False,
                "prospector_hud": False, "system_info_hud": False,
                "station_info_hud": True, "survey_status_hud": False,
                "colony_overlay": False},
    "powerplay": {"hud": True, "cargo_hud": True, "carrier_hud": False,
                  "prospector_hud": False, "system_info_hud": True,
                  "station_info_hud": True, "survey_status_hud": False,
                  "colony_overlay": False},
}


def normalize_mode(value, fallback="general"):
    value = str(value or "").strip().casefold().replace(" ", "_")
    aliases = {
        "explore": "exploration", "colonisation": "colony",
        "colonization": "colony", "on_foot": "ground", "onfoot": "ground",
        "auto": "auto", "automatic": "auto",
    }
    value = aliases.get(value, value)
    return value if value in MODES or value == "auto" else fallback


def _defaults():
    return {
        "schema": 1,
        "mode": "general",
        "mode_since": time.time(),
        "session": {},
        "episodes": [],
    }


class AdaptiveCommandDeck:
    def __init__(self, path, config=None):
        self.path = os.fspath(path)
        self.config = config or {}
        self.state = _defaults()
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                self.state.update(loaded)
        except (OSError, ValueError, TypeError):
            pass
        self.state["mode"] = normalize_mode(self.state.get("mode"))

    def _save(self, immediate=False):
        persistence_queue().submit_json(
            self.path, self.state, indent=2, delay_s=1.0, immediate=immediate,
        )

    def flush(self, wait=True):
        self._save(immediate=True)
        if wait:
            persistence_queue().flush(self.path, timeout=5.0)

    def switch(self, path, config=None):
        self.flush()
        self.path = os.fspath(path)
        if config is not None:
            self.config = config
        self.state = _defaults()
        self._load()

    @property
    def locked_mode(self):
        return normalize_mode(self.config.get("adaptive_mode_lock", "auto"), "auto")

    @property
    def current_mode(self):
        locked = self.locked_mode
        if locked != "auto":
            return locked
        mode = normalize_mode(self.state.get("mode"))
        if mode == "general":
            return mode
        session = self.state.get("session") or {}
        last_event_at = float(
            session.get("last_event_at") or self.state.get("mode_since") or 0
        )
        if last_event_at and time.time() - last_event_at > AUTOMATIC_MODE_IDLE_S:
            return "general"
        return mode

    @property
    def automatic(self):
        return self.locked_mode == "auto"

    def set_lock(self, mode):
        mode = normalize_mode(mode, "auto")
        self.config["adaptive_mode_lock"] = mode
        if mode != "auto":
            self.state["mode"] = mode
            self.state["mode_since"] = time.time()
            self._save()
        return self.current_mode

    @staticmethod
    def _new_session(mode, now):
        return {
            "mode": mode, "started_at": now, "last_event_at": now,
            "events": 0, "jumps": 0, "scans": 0, "refined_t": 0,
            "kills": 0, "materials": 0,
        }

    @staticmethod
    def _update_session(session, event, raw, now):
        session["events"] = int(session.get("events") or 0) + 1
        session["last_event_at"] = now
        if event in ("FSDJump", "CarrierJump"):
            session["jumps"] = int(session.get("jumps") or 0) + 1
        if event in ("Scan", "FSSDiscoveryScan", "SAAScanComplete", "ScanOrganic"):
            session["scans"] = int(session.get("scans") or 0) + 1
        if event == "MiningRefined":
            session["refined_t"] = int(session.get("refined_t") or 0) + max(1, int(raw.get("Count") or 1))
        if event in ("Bounty", "FactionKillBond", "CapShipBond"):
            session["kills"] = int(session.get("kills") or 0) + 1
        if event in ("MaterialCollected", "MaterialTrade", "EngineerCraft"):
            session["materials"] = int(session.get("materials") or 0) + 1

    @staticmethod
    def _session_summary(session):
        if not session or int(session.get("events") or 0) < 2:
            return None
        parts = []
        for key, label in (
            ("jumps", "jumps"), ("scans", "survey actions"),
            ("refined_t", "tonnes refined"), ("kills", "claims observed"),
            ("materials", "material actions"),
        ):
            value = int(session.get(key) or 0)
            if value:
                parts.append(f"{value:,} {label}")
        duration = max(0, int((float(session.get("last_event_at") or time.time()) - float(session.get("started_at") or time.time())) / 60))
        label = MODE_LABELS.get(session.get("mode"), "ACTIVITY").title()
        return f"{label} complete: " + (", ".join(parts) if parts else f"{int(session.get('events') or 0):,} journal actions") + f" over {duration} min."

    def observe(self, event, detected_mode, raw=None, *, historical=False):
        raw = raw if isinstance(raw, dict) else {}
        if historical or not self.config.get("adaptive_command_enabled", True):
            return {"changed": False, "mode": self.current_mode}
        now = time.time()
        locked = self.locked_mode
        desired = locked if locked != "auto" else normalize_mode(detected_mode)
        previous = normalize_mode(self.state.get("mode"))
        session = self.state.get("session")
        if not isinstance(session, dict) or session.get("mode") != previous:
            session = self._new_session(previous, now)
            self.state["session"] = session
        changed = desired != previous
        debrief = None
        if changed:
            debrief = self._session_summary(session)
            if debrief:
                episodes = self.state.setdefault("episodes", [])
                episodes.append({
                    "mode": previous, "ended_at": now, "summary": debrief,
                    "metrics": dict(session),
                })
                self.state["episodes"] = episodes[-30:]
            self.state["mode"] = desired
            self.state["mode_since"] = now
            self.state["session"] = self._new_session(desired, now)
            self._update_session(self.state["session"], event, raw, now)
        else:
            self._update_session(session, event, raw, now)
        self._save()
        return {
            "changed": changed, "previous": previous, "mode": desired,
            "debrief": debrief,
            "briefing": self.briefing(desired) if changed else None,
        }

    def close_session(self, reason="Session complete"):
        session = self.state.get("session") or {}
        session["last_event_at"] = time.time()
        summary = self._session_summary(session)
        if summary:
            summary = f"{reason}. {summary}"
        self.state["session"] = {}
        self._save(immediate=True)
        return summary

    @staticmethod
    def briefing(mode):
        lines = {
            "general": "General flight configuration active. Core navigation and safety systems are standing by.",
            "exploration": "Exploration configuration active. Survey progress, route context and biological work have priority.",
            "mining": "Mining configuration active. Prospecting, refinery yield, limpets and cargo movement have priority.",
            "combat": "Combat configuration active. Threat, claims, ammunition and recovery state have priority.",
            "ground": "Ground operations active. Surface position, biological sampling and local hazards have priority.",
            "engineering": "Engineering configuration active. Material shortages and pinned goals have priority.",
            "carrier": "Carrier operations active. Fuel, route, services and logistics have priority.",
            "colony": "Architect configuration active. Construction requirements and matched cargo have priority.",
            "station": "Station operations active. Services, transactions and outstanding objectives have priority.",
            "powerplay": "Powerplay configuration active. Merits, commodities and regional strategy have priority.",
        }
        return lines.get(normalize_mode(mode), lines["general"])

    def scene(self, mode=None):
        mode = normalize_mode(mode or self.current_mode)
        custom = self.config.get("adaptive_overlay_scenes") or {}
        scene = dict(DEFAULT_OVERLAY_SCENES.get(mode, DEFAULT_OVERLAY_SCENES["general"]))
        if isinstance(custom.get(mode), dict):
            scene.update({key: bool(value) for key, value in custom[mode].items()})
        return scene

    def build_queue(self, snapshot, context=None):
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        context = context if isinstance(context, dict) else {}
        mode = self.current_mode
        rows = []

        def add(item_id, label, detail, workspace, priority, copy_text=None, modes=()):
            if mode in modes:
                priority += 25
            rows.append({
                "id": item_id, "label": label, "detail": detail,
                "workspace": workspace, "priority": priority,
                "copy_text": copy_text,
            })

        biology = snapshot.get("biology") or {}
        if biology:
            species = biology.get("species") or biology.get("variant") or biology.get("genus") or "biological sample"
            progress = int(biology.get("progress") or biology.get("sample_idx") or 1)
            add("biology", f"Continue {species} sampling", f"Sample {progress}/3 is active on {biology.get('body') or 'the current body'}.", "GROUND", 100, modes=("exploration", "ground"))

        objectives = snapshot.get("objectives") or {}
        unsold = int(objectives.get("unsold_data_total_cr") or 0)
        if unsold:
            add("survey-data", "Sell recorded survey data", f"{unsold:,} credits of confirmed base-value data remain aboard.", "EXPLORE", 55, modes=("exploration", "station"))

        remaining = int(context.get("survey_remaining") or 0)
        if remaining:
            add("survey", "Complete the current system survey", f"{remaining} bod{'ies' if remaining != 1 else 'y'} remain unresolved in {context.get('current_system') or 'this system'}.", "EXPLORE", 80, modes=("exploration",))

        destination = context.get("next_destination")
        route_text = context.get("route_text")
        if destination:
            add("route", f"Continue to {destination}", route_text or "A navigation objective remains active.", "EXPLORE", 70, copy_text=destination, modes=("exploration", "general"))

        missions = snapshot.get("missions") or {}
        mission_count = int(missions.get("active") or 0)
        if mission_count:
            groups = missions.get("grouped_destinations") or objectives.get("mission_destinations") or []
            first = groups[0] if groups else {}
            system = first.get("system") if isinstance(first, dict) else None
            add("missions", f"Review {mission_count} active mission{'s' if mission_count != 1 else ''}", f"Next recorded destination: {system}." if system else "Mission objectives remain active.", "PROFILE", 60, copy_text=system, modes=("general", "combat"))

        mining = snapshot.get("mining") or {}
        if mining.get("active"):
            add("mining", "Continue the active mining run", f"{int(mining.get('refined_tons') or 0)} tonnes refined this run.", "SPECIALISTS", 75, modes=("mining",))

        powerplay = snapshot.get("powerplay") or {}
        outstanding_units = int(powerplay.get("outstanding_units") or 0)
        if outstanding_units:
            add(
                "powerplay-delivery", "Deliver Powerplay commodities",
                f"{outstanding_units:,} collected units remain outstanding for {powerplay.get('power') or 'the pledged power'}.",
                "GALAXY", 72, modes=("powerplay",),
            )
        elif mode == "powerplay" and powerplay.get("pledged"):
            add(
                "powerplay", f"Review {powerplay.get('power') or 'Powerplay'} operations",
                f"{int(powerplay.get('merits') or 0):,} merits are currently recorded.",
                "GALAXY", 48, modes=("powerplay",),
            )

        pinned = list(context.get("engineering_goals") or [])
        if pinned:
            add("engineering", f"Advance {len(pinned)} engineering goal{'s' if len(pinned) != 1 else ''}", "Material shortages and trader alternatives are ready in Engineering Command.", "ENGINEER", 45, modes=("engineering",))

        strategy = snapshot.get("strategy") or {}
        colonies = strategy.get("colonisation_projects") or []
        if colonies:
            remaining_units = sum(int(row.get("remaining_units") or 0) for row in colonies if isinstance(row, dict))
            add("colony", f"Supply {len(colonies)} construction site{'s' if len(colonies) != 1 else ''}", f"{remaining_units:,} required units remain journal-confirmed.", "COLONY", 50, modes=("colony",))

        carrier = strategy.get("carrier") or {}
        if carrier.get("jump_destination"):
            add("carrier", f"Carrier jump to {carrier['jump_destination']}", f"{carrier.get('name') or 'Fleet Carrier'} has a plotted destination.", "CARRIER", 68, copy_text=carrier.get("jump_destination"), modes=("carrier",))

        rows.sort(key=lambda row: (-int(row["priority"]), row["label"].casefold()))
        return rows[:12]

    def status(self):
        return {
            "mode": self.current_mode,
            "label": MODE_LABELS.get(self.current_mode, "GENERAL FLIGHT"),
            "automatic": self.automatic,
            "workspace": MODE_WORKSPACES.get(self.current_mode, "DASHBOARD"),
            "session": dict(self.state.get("session") or {}),
            "episodes": len(self.state.get("episodes") or []),
        }
