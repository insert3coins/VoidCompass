"""Lightweight, panel-independent PvE encounter state for Compass."""

from __future__ import annotations

import time


COMBAT_VOUCHER_TYPES = {"bounty", "combatbond", "combat bond"}


def _number(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _percent(value):
    if value is None:
        return None
    result = _number(value, 0)
    if result <= 1:
        result *= 100
    return round(max(0.0, min(100.0, result)), 1)


def _display_name(value, fallback="Unknown contact"):
    text = str(value or "").strip().strip("$;")
    if text.casefold().endswith("_name"):
        text = text[:-5]
    return text.replace("_", " ").strip().title() or fallback


class CombatAwareness:
    """Retain verified facts for the current PvE sortie and latest target."""

    def __init__(self):
        self.state = self._empty_state()

    @staticmethod
    def _empty_state(previous=None):
        previous = previous or {}
        return {
            "active": False,
            "started_at": None,
            "system": None,
            "trigger": None,
            "attacks": 0,
            "victories": 0,
            "bounties": 0,
            "combat_bonds": 0,
            "reward_cr": 0,
            "unclaimed_reward_cr": 0,
            "redeemed_reward_cr": 0,
            "shield_failures": 0,
            "shields_up": None,
            "last_shield_event_up": None,
            "hull_percent": None,
            "minimum_hull_percent": None,
            "cockpit_breached": False,
            "fighter_losses": 0,
            "srv_losses": 0,
            "interdictions": 0,
            "interdictions_escaped": 0,
            "current_target": None,
            "last_victory": None,
            "last_interdiction": None,
            "last_summary": previous.get("last_summary"),
            "last_summary_pending": False,
            "status_hardpoints": False,
            "status_in_danger": False,
        }

    def reset(self):
        self.state = self._empty_state()

    def _start(self, system=None, trigger=None):
        if self.state.get("active"):
            return self.state
        previous = self.state
        self.state = self._empty_state(previous)
        self.state.update({
            "active": True,
            "started_at": time.time(),
            "system": system,
            "trigger": trigger,
            "shields_up": previous.get("shields_up"),
            "hull_percent": previous.get("hull_percent"),
            "minimum_hull_percent": previous.get("hull_percent"),
            "status_hardpoints": bool(previous.get("status_hardpoints")),
            "status_in_danger": bool(previous.get("status_in_danger")),
            "current_target": previous.get("current_target"),
            "unclaimed_reward_cr": int(previous.get("unclaimed_reward_cr") or 0),
            "redeemed_reward_cr": int(previous.get("redeemed_reward_cr") or 0),
        })
        return self.state

    def _finish(self, reason):
        state = self.state
        if not state.get("active"):
            return
        duration = max(0.0, time.time() - float(state.get("started_at") or time.time()))
        state["last_summary"] = {
            "reason": str(reason or "complete"),
            "system": state.get("system"),
            "duration_minutes": round(duration / 60.0, 1),
            "attacks": int(state.get("attacks") or 0),
            "victories": int(state.get("victories") or 0),
            "bounties": int(state.get("bounties") or 0),
            "combat_bonds": int(state.get("combat_bonds") or 0),
            "capital_ship_bonds": int(state.get("capital_ship_bonds") or 0),
            "reward_cr": int(state.get("reward_cr") or 0),
            "shield_failures": int(state.get("shield_failures") or 0),
            "minimum_hull_percent": state.get("minimum_hull_percent"),
            "cockpit_breached": bool(state.get("cockpit_breached")),
            "fighter_losses": int(state.get("fighter_losses") or 0),
            "srv_losses": int(state.get("srv_losses") or 0),
            "interdictions": int(state.get("interdictions") or 0),
            "interdictions_escaped": int(state.get("interdictions_escaped") or 0),
            "interdictions_attempted": int(state.get("interdictions_attempted") or 0),
            "interdictions_succeeded": int(state.get("interdictions_succeeded") or 0),
            "destroyed": bool(state.get("destroyed")),
            "last_loss": dict(state.get("last_loss") or {}) or None,
        }
        state["last_summary_pending"] = True
        state["active"] = False

    def update_status(self, flags):
        if not isinstance(flags, int):
            return
        self.state["shields_up"] = bool(flags & 0x00000008)
        self.state["status_hardpoints"] = bool(flags & 0x00000040)
        self.state["status_in_danger"] = bool(flags & 0x00400000)

    def observe(self, event, raw=None, system=None, startup_replay=False):
        if startup_replay:
            return
        raw = raw if isinstance(raw, dict) else {}
        event = str(event or "")
        if event == "LoadGame":
            self.reset()
            return

        state = self.state
        if event == "ShipTargeted":
            if not raw.get("TargetLocked", False):
                state["current_target"] = None
                return
            target = dict(state.get("current_target") or {})
            pilot = raw.get("PilotName_Localised") or raw.get("PilotName")
            pilot_text = str(pilot or "").strip()
            target.update({
                "ship": _display_name(raw.get("Ship_Localised") or raw.get("Ship"), "Ship"),
                "scan_stage": int(raw.get("ScanStage") or 0),
                "pilot": pilot,
                "rank": raw.get("PilotRank"),
                "faction": raw.get("Faction"),
                "legal_status": raw.get("LegalStatus"),
                "bounty_cr": int(raw.get("Bounty") or 0),
                "shield_percent": _percent(raw.get("ShieldHealth")),
                "hull_percent": _percent(raw.get("HullHealth")),
                "subsystem": _display_name(raw.get("Subsystem_Localised") or raw.get("Subsystem"), "") or None,
                "subsystem_percent": _percent(raw.get("SubsystemHealth")),
                "power": raw.get("Power"),
                "is_player": bool(
                    raw.get("IsPlayer", False)
                    or pilot_text.casefold().startswith("cmdr ")
                    or pilot_text.casefold().startswith("$cmdr")
                ),
            })
            state["current_target"] = target
            return

        combat_start_events = {
            "UnderAttack", "ShieldState", "HullDamage", "CockpitBreached",
            "Bounty", "FactionKillBond", "CapShipBond", "FighterDestroyed", "SRVDestroyed",
        }
        if event in combat_start_events and not state.get("active"):
            state = self._start(system, event)

        if event == "UnderAttack":
            state["attacks"] = int(state.get("attacks") or 0) + 1
        elif event == "ShieldState":
            shields_up = bool(raw.get("ShieldsUp"))
            if not shields_up and state.get("last_shield_event_up") is not False:
                state["shield_failures"] = int(state.get("shield_failures") or 0) + 1
            state["shields_up"] = shields_up
            state["last_shield_event_up"] = shields_up
        elif event == "HullDamage":
            health = _percent(raw.get("Health"))
            if health is not None:
                state["hull_percent"] = health
                state["hull_context"] = "fighter" if raw.get("Fighter") else "ship"
                previous = state.get("minimum_hull_percent")
                state["minimum_hull_percent"] = health if previous is None else min(float(previous), health)
        elif event == "CockpitBreached":
            state["cockpit_breached"] = True
        elif event in ("Bounty", "FactionKillBond", "CapShipBond"):
            reward = int(raw.get("TotalReward") or raw.get("Reward") or 0)
            state["victories"] = int(state.get("victories") or 0) + 1
            state["reward_cr"] = int(state.get("reward_cr") or 0) + reward
            state["unclaimed_reward_cr"] = int(state.get("unclaimed_reward_cr") or 0) + reward
            if event == "Bounty":
                state["bounties"] = int(state.get("bounties") or 0) + 1
            else:
                state["combat_bonds"] = int(state.get("combat_bonds") or 0) + 1
                if event == "CapShipBond":
                    state["capital_ship_bonds"] = int(state.get("capital_ship_bonds") or 0) + 1
            state["last_victory"] = {
                "kind": (
                    "bounty" if event == "Bounty"
                    else "capital ship bond" if event == "CapShipBond"
                    else "combat bond"
                ),
                "target": _display_name(raw.get("Target_Localised") or raw.get("Target"), "Hostile contact"),
                "victim_faction": raw.get("VictimFaction"),
                "awarding_faction": raw.get("AwardingFaction") or raw.get("Faction"),
                "reward_cr": reward,
                "shared_with": int(raw.get("SharedWithOthers") or 0),
            }
        elif event == "FighterDestroyed":
            state["fighter_losses"] = int(state.get("fighter_losses") or 0) + 1
        elif event == "SRVDestroyed":
            state["srv_losses"] = int(state.get("srv_losses") or 0) + 1
        elif event == "Interdicted":
            if not state.get("active"):
                state = self._start(system, event)
            state["interdictions"] = int(state.get("interdictions") or 0) + 1
            state["last_interdiction"] = {
                "pilot": raw.get("Interdictor_Localised") or raw.get("Interdictor") or "Unknown contact",
                "is_player": bool(raw.get("IsPlayer", False)),
                "is_thargoid": bool(raw.get("IsThargoid", False)),
                "faction": raw.get("Faction"),
                "submitted": bool(raw.get("Submitted", False)),
            }
        elif event == "Interdiction":
            if not raw.get("IsPlayer") and bool(raw.get("Success")) and not state.get("active"):
                state = self._start(system, event)
            state["interdictions_attempted"] = int(state.get("interdictions_attempted") or 0) + 1
            if bool(raw.get("Success")):
                state["interdictions_succeeded"] = int(state.get("interdictions_succeeded") or 0) + 1
            state["last_interdiction"] = {
                "pilot": raw.get("Interdicted_Localised") or raw.get("Interdicted") or "Unknown contact",
                "is_player": bool(raw.get("IsPlayer", False)),
                "faction": raw.get("Faction"),
                "success": bool(raw.get("Success", False)),
                "outbound": True,
            }
        elif event == "EscapeInterdiction":
            if not state.get("active"):
                state = self._start(system, event)
            state["interdictions_escaped"] = int(state.get("interdictions_escaped") or 0) + 1
            state["last_interdiction"] = {
                "pilot": raw.get("Interdictor_Localised") or raw.get("Interdictor") or "Unknown contact",
                "is_player": bool(raw.get("IsPlayer", False)),
                "is_thargoid": bool(raw.get("IsThargoid", False)),
                "escaped": True,
            }
            self._finish(event)
        elif event == "RedeemVoucher":
            voucher_type = str(raw.get("Type") or "").replace("_", " ").casefold()
            if voucher_type in COMBAT_VOUCHER_TYPES:
                amount = int(raw.get("Amount") or 0)
                state["redeemed_reward_cr"] = int(state.get("redeemed_reward_cr") or 0) + amount
                state["unclaimed_reward_cr"] = max(0, int(state.get("unclaimed_reward_cr") or 0) - amount)
                state["last_redemption"] = {"type": voucher_type, "amount_cr": amount}
        elif event == "Died":
            if not state.get("active"):
                state = self._start(system, event)
            state["destroyed"] = True
            killers = raw.get("Killers") if isinstance(raw.get("Killers"), list) else []
            state["last_loss"] = {
                "killer": raw.get("KillerName_Localised") or raw.get("KillerName")
                          or (killers[0].get("Name") if killers and isinstance(killers[0], dict) else None),
                "ship": raw.get("KillerShip")
                        or (killers[0].get("Ship") if killers and isinstance(killers[0], dict) else None),
                "rank": raw.get("KillerRank")
                        or (killers[0].get("Rank") if killers and isinstance(killers[0], dict) else None),
            }
            self._finish(event)
        elif event in ("StartJump", "FSDJump", "CarrierJump", "Docked", "Shutdown"):
            self._finish(event)

    def snapshot(self, massacre_stacks=None, lifetime=None):
        state = self.state
        started = state.get("started_at")
        duration = max(0.0, time.time() - float(started or time.time())) / 60.0
        return {
            "active": bool(state.get("active")),
            "system": state.get("system"),
            "duration_minutes": round(duration, 1) if state.get("active") else 0.0,
            "attacks": int(state.get("attacks") or 0),
            "victories": int(state.get("victories") or 0),
            "bounties": int(state.get("bounties") or 0),
            "combat_bonds": int(state.get("combat_bonds") or 0),
            "capital_ship_bonds": int(state.get("capital_ship_bonds") or 0),
            "reward_cr": int(state.get("reward_cr") or 0),
            "unclaimed_reward_cr": int(state.get("unclaimed_reward_cr") or 0),
            "redeemed_reward_cr": int(state.get("redeemed_reward_cr") or 0),
            "shield_failures": int(state.get("shield_failures") or 0),
            "shields_up": state.get("shields_up"),
            "hull_percent": state.get("hull_percent"),
            "minimum_hull_percent": state.get("minimum_hull_percent"),
            "cockpit_breached": bool(state.get("cockpit_breached")),
            "fighter_losses": int(state.get("fighter_losses") or 0),
            "srv_losses": int(state.get("srv_losses") or 0),
            "interdictions": int(state.get("interdictions") or 0),
            "interdictions_escaped": int(state.get("interdictions_escaped") or 0),
            "interdictions_attempted": int(state.get("interdictions_attempted") or 0),
            "interdictions_succeeded": int(state.get("interdictions_succeeded") or 0),
            "hardpoints_deployed": bool(state.get("status_hardpoints")),
            "in_danger": bool(state.get("status_in_danger")),
            "current_target": dict(state.get("current_target") or {}) or None,
            "last_victory": dict(state.get("last_victory") or {}) or None,
            "last_interdiction": dict(state.get("last_interdiction") or {}) or None,
            "last_redemption": dict(state.get("last_redemption") or {}) or None,
            "last_loss": dict(state.get("last_loss") or {}) or None,
            "massacre_stacks": list(massacre_stacks or [])[:6],
            "lifetime": dict(lifetime or {}),
            "last_summary": state.get("last_summary") if state.get("last_summary_pending") else None,
        }

    def consume_summary(self):
        self.state["last_summary_pending"] = False
