"""Bounded, GPU-free decision and learning engine for Compass.

The engine never invents game facts. It ranks verified observations, renders
them through curated templates, learns whether advice was acted upon, and keeps
small rolling baselines inside the per-commander cockpit brain.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
import random
import re
import statistics
import time

import compass_operations
from compass_personas import normalize_persona


COGNITION_SCHEMA = 2
MAX_DECISIONS = 40
MAX_TOPICS = 48
MAX_PENDING = 8
MAX_METRIC_SAMPLES = 24
MAX_GOALS = 8
MAX_PREDICTIONS = 18

MOOD_CLAUSES = {
    "curious": (
        "worth a closer look", "the pattern merits attention",
        "there may be more here", "I would keep the sensors on this",
        "that stands out in the data", "an interesting result",
    ),
    "proud": (
        "solid progress", "another good result", "nicely handled",
        "the record is improving", "that moved us forward", "a worthwhile gain",
    ),
}


PERSONA_TOPIC_WEIGHTS = {
    "Tactical": {"mission": 1.30, "risk": 1.25, "combat": 1.35, "powerplay": 1.30, "cargo": 1.10, "route": 1.10, "signals": 1.20, "legal": 1.15, "ambient": 0.70},
    "Guardian": {"risk": 1.35, "combat": 1.15, "fuel": 1.30, "data": 1.20, "cargo": 1.10, "rescue": 1.35, "ground": 1.15},
    "Scientific": {"survey": 1.35, "anomaly": 1.30, "valuable": 1.25, "biology": 1.15, "mining": 1.10, "signals": 1.25},
    "Exobiologist": {"biology": 1.45, "survey": 1.20, "valuable": 1.10},
    "Engineer": {"engineering": 1.40, "cargo": 1.20, "fuel": 1.15, "ship": 1.20, "mining": 1.25, "logistics": 1.30},
    "Wayfarer": {"route": 1.25, "memory": 1.25, "session": 1.20, "ambient": 1.10},
    "Pathfinder": {"route": 1.40, "mission": 1.20, "survey": 1.05},
    "Veteran": {"memory": 1.25, "pattern": 1.25, "risk": 1.10, "combat": 1.20, "trade": 1.10, "powerplay": 1.15, "ambient": 0.85},
    "Deadpan": {"anomaly": 1.20, "pattern": 1.15, "ambient": 0.70},
    "Stoic": {"risk": 1.15, "mission": 1.05, "ambient": 0.55, "memory": 0.75},
    "Optimist": {"progress": 1.30, "milestone": 1.30, "recovery": 1.20, "trade": 1.10},
    "Archivist": {"memory": 1.45, "pattern": 1.30, "milestone": 1.20, "powerplay": 1.15, "strategy": 1.20},
    "Companion": {"memory": 1.30, "session": 1.25, "progress": 1.20, "powerplay": 1.10},
    "Emergent": {"learning": 1.45, "pattern": 1.30, "memory": 1.20, "anomaly": 1.15},
}


OUTCOME_EVENTS = {
    "sell-biology": {"SellOrganicData"},
    "sell-exploration": {"SellExplorationData", "MultiSellExplorationData"},
    "survey": {"Scan", "FSSAllBodiesFound", "SAAScanComplete"},
    "biology": {"ScanOrganic"},
    "mission": {"MissionCompleted", "MissionRedirected"},
    "cargo": {"MarketSell", "EjectCargo"},
    "route": {"FSDJump", "CarrierJump"},
    "engineering": {"EngineerCraft", "Synthesis", "TechnologyBroker"},
    "signal": {"DataScanned", "Scanned", "SupercruiseDestinationDrop"},
    "rescue": {"SearchAndRescue", "MarketSell"},
    "mission-route": {"FSDJump", "CarrierJump", "Docked", "MissionCompleted"},
    "colonisation": {"ColonisationContribution"},
}

OUTCOME_ABANDON_EVENTS = {
    "sell-biology": {"Undocked"},
    "sell-exploration": {"Undocked"},
    "survey": {"StartJump", "FSDJump"},
    "biology": {"StartJump", "FSDJump"},
    "cargo": {"StartJump", "FSDJump"},
}


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp(value=None):
    if value is None:
        return time.time()
    try:
        return float(value)
    except (TypeError, ValueError):
        return time.time()


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None if default is None else float(default)


def _words(value):
    return {
        word for word in re.findall(r"[a-z0-9]+", str(value or "").casefold())
        if len(word) >= 3
    }


def _median(values):
    clean = [_number(value) for value in values]
    return statistics.median(clean) if clean else None


class CompassCognition:
    """Adaptive observation scorer backed by the existing cockpit brain file."""

    def __init__(self, brain, config):
        self.brain = brain
        self.config = config

    @property
    def enabled(self):
        return bool(self.config.get("cockpit_cognition_enabled", True))

    @staticmethod
    def _empty_state():
        return {
            "schema": COGNITION_SCHEMA,
            "topic_stats": {},
            "metrics": {},
            "predictions": [],
            "goals": [],
            "pending_outcomes": [],
            "recent_decisions": [],
            "last_decision": None,
            "last_anomalies": [],
            "learning_notices": [],
            "preparation": {},
        }

    def _state(self):
        saved = self.brain.cognition_state() if self.brain is not None else {}
        state = self._empty_state()
        if isinstance(saved, dict):
            for key in state:
                if key in saved and (
                    key == "last_decision"
                    or isinstance(saved[key], type(state[key]))
                ):
                    state[key] = saved[key]
        state["schema"] = COGNITION_SCHEMA
        return state

    def _commit(self, state, save=False):
        if self.brain is None:
            return
        topics = state.setdefault("topic_stats", {})
        if len(topics) > MAX_TOPICS:
            ordered = sorted(
                topics.items(),
                key=lambda pair: _number((pair[1] or {}).get("last_offered_at")),
                reverse=True,
            )[:MAX_TOPICS]
            state["topic_stats"] = dict(ordered)
        state["pending_outcomes"] = list(state.get("pending_outcomes") or [])[-MAX_PENDING:]
        state["recent_decisions"] = list(state.get("recent_decisions") or [])[-MAX_DECISIONS:]
        state["goals"] = list(state.get("goals") or [])[:MAX_GOALS]
        state["learning_notices"] = list(state.get("learning_notices") or [])[-8:]
        preparation = state.get("preparation") or {}
        state["preparation"] = dict(sorted(
            preparation.items(),
            key=lambda pair: _number((pair[1] or {}).get("last_observed_at"), 0),
            reverse=True,
        )[:12])
        self.brain.set_cognition_state(state, save=save)

    def reset(self, save=True):
        self._commit(self._empty_state(), save=save)

    @staticmethod
    def _topic_stat(state, topic):
        stats = state.setdefault("topic_stats", {})
        row = stats.setdefault(str(topic), {
            "offered": 0, "acted": 0, "ignored": 0,
            "last_offered_at": None, "last_result_at": None,
        })
        return row

    @staticmethod
    def _confidence(row):
        acted = int(row.get("acted") or 0)
        ignored = int(row.get("ignored") or 0)
        resolved = acted + ignored
        return round((acted + 1) / (resolved + 2), 2), resolved

    def _observe_metric(self, state, name, value):
        value = _number(value, None) if value is not None else None
        if value is None or not math.isfinite(value):
            return False
        metrics = state.setdefault("metrics", {})
        row = metrics.setdefault(str(name), {"samples": []})
        samples = list(row.get("samples") or [])
        samples.append(round(value, 2))
        row["samples"] = samples[-MAX_METRIC_SAMPLES:]
        row["count"] = len(row["samples"])
        row["median"] = round(float(_median(row["samples"])), 2)
        row["mean"] = round(sum(row["samples"]) / len(row["samples"]), 2)
        row["minimum"] = min(row["samples"])
        row["maximum"] = max(row["samples"])
        return True

    @staticmethod
    def _session_duration_minutes(memory):
        session = (memory.state.get("current_session") if memory else None) or {}
        started = session.get("started_at")
        if not started:
            return None
        try:
            start = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
            return max(0.0, (datetime.now(timezone.utc) - start).total_seconds() / 60.0)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _learn_preparation(state, key, label, memory=None):
        """Learn a recurring preparation need at most once per game session."""
        session = (memory.state.get("current_session") if memory else None) or {}
        session_key = str(session.get("started_at") or datetime.now(timezone.utc).date())
        rows = state.setdefault("preparation", {})
        row = rows.setdefault(str(key), {
            "label": str(label), "occurrences": 0, "last_session": None,
            "last_observed_at": None,
        })
        if row.get("last_session") == session_key:
            return False
        row["label"] = str(label)
        row["occurrences"] = int(row.get("occurrences") or 0) + 1
        row["last_session"] = session_key
        row["last_observed_at"] = time.time()
        return True

    def observe_session_close(self, snapshot, memory):
        """Learn session baselines and return concise debrief insights."""
        if (not self.enabled or memory is None
                or not memory.state.get("current_session")):
            return []
        state = self._state()
        session = (snapshot or {}).get("session") or {}
        mining = (snapshot or {}).get("mining") or {}
        trade = (snapshot or {}).get("trade") or {}
        combat = (snapshot or {}).get("combat") or {}
        powerplay = (snapshot or {}).get("powerplay") or {}
        ship_operations = (snapshot or {}).get("ship_operations") or {}
        signals = (snapshot or {}).get("signals") or {}
        ground = (snapshot or {}).get("ground_operations") or {}
        missions = (snapshot or {}).get("missions") or {}
        duration = self._session_duration_minutes(memory)
        previous_jumps = ((state.get("metrics") or {}).get("session_jumps") or {}).get("median")
        previous_duration = ((state.get("metrics") or {}).get("session_minutes") or {}).get("median")
        jumps = int(session.get("jumps") or 0)
        distance = _number(session.get("distance_ly"))
        if jumps:
            self._observe_metric(state, "session_jumps", jumps)
        if distance:
            self._observe_metric(state, "session_distance_ly", distance)
        if duration and duration >= 2:
            self._observe_metric(state, "session_minutes", duration)
        profit = int(session.get("trade_profit_cr") or 0)
        if profit > 0:
            self._observe_metric(state, "session_trade_profit_cr", profit)
        refined = int(mining.get("refined_tons") or 0)
        if refined > 0:
            self._observe_metric(state, "mining_session_refined_tons", refined)
        transactions = int(trade.get("transactions") or 0)
        if transactions > 0:
            self._observe_metric(state, "trade_session_transactions", transactions)
        combat_summary = combat.get("last_summary") or {}
        if int(combat_summary.get("victories") or 0):
            self._observe_metric(state, "combat_sortie_victories", combat_summary.get("victories"))
        if int(combat_summary.get("reward_cr") or 0):
            self._observe_metric(state, "combat_sortie_reward_cr", combat_summary.get("reward_cr"))
        if combat_summary.get("minimum_hull_percent") is not None:
            self._observe_metric(state, "combat_sortie_minimum_hull_pct", combat_summary.get("minimum_hull_percent"))
        session_merits = int(powerplay.get("session_merits") or 0)
        session_delivered = int(powerplay.get("session_delivered") or 0)
        if session_merits:
            self._observe_metric(state, "powerplay_session_merits", session_merits)
        if session_delivered:
            self._observe_metric(state, "powerplay_session_delivered", session_delivered)
        logistics = ship_operations.get("session_logistics") or {}
        if float(logistics.get("fuel_scooped_t") or 0) > 0:
            self._observe_metric(state, "session_fuel_scooped_t", logistics.get("fuel_scooped_t"))
        mission_session = missions.get("session") or {}
        if int(mission_session.get("completed") or 0):
            self._observe_metric(state, "session_missions_completed", mission_session.get("completed"))
        if int(mission_session.get("rewards_cr") or 0):
            self._observe_metric(state, "session_mission_rewards_cr", mission_session.get("rewards_cr"))
        if int(ground.get("items_collected") or 0):
            self._observe_metric(state, "session_ground_items", ground.get("items_collected"))
        signal_summary = signals.get("last_summary") or signals
        if int(signal_summary.get("total") or 0):
            self._observe_metric(state, "system_signals", signal_summary.get("total"))
        self._refresh_predictions(state, memory)
        self._commit(state, save=True)

        insights = []
        if previous_jumps and jumps >= max(5, float(previous_jumps) * 1.5):
            insights.append(
                f"This was a longer flight than usual: {jumps} jumps against a typical {round(float(previous_jumps))}."
            )
        elif previous_jumps and jumps and jumps <= max(1, float(previous_jumps) * 0.5):
            insights.append(
                f"This was a shorter flight than usual: {jumps} jumps against a typical {round(float(previous_jumps))}."
            )
        if previous_duration and duration and duration >= float(previous_duration) * 1.5:
            insights.append(
                f"The session ran for {round(duration)} minutes, longer than the usual {round(float(previous_duration))}."
            )
        if refined:
            insights.append(f"Mining contributed {refined} refined tonnes to this session.")
        if transactions and profit:
            insights.append(f"Trade closed at {profit:,} credits across {transactions} market transactions.")
        if int(combat_summary.get("victories") or 0):
            insights.append(
                f"PvE combat closed with {int(combat_summary.get('victories') or 0)} victories "
                f"and {int(combat_summary.get('reward_cr') or 0):,} credits recorded."
            )
        if session_merits or session_delivered:
            insights.append(
                f"Powerplay closed with {session_merits:,} merits and {session_delivered:,} delivered units recorded."
            )
        goals = list(state.get("goals") or [])
        if goals:
            insights.append(f"Highest remaining priority: {goals[0].get('label')}.")
        return insights[:2]

    def _resolve_outcomes(self, state, event):
        now = time.time()
        remaining = []
        notices = []
        for pending in state.get("pending_outcomes") or []:
            outcome = str(pending.get("outcome") or "")
            topic = str(pending.get("topic") or "general")
            offered_at = _number(pending.get("offered_at"), now)
            result = None
            # A contextual callout can be recorded earlier in the same journal
            # event that triggered it. Do not treat that event as an immediate
            # response or abandonment by the pilot.
            if now - offered_at < 5.0:
                remaining.append(pending)
                continue
            if event in OUTCOME_EVENTS.get(outcome, set()):
                result = "acted"
            elif event in OUTCOME_ABANDON_EVENTS.get(outcome, set()):
                result = "ignored"
            elif now - offered_at >= 2700:
                result = "ignored"
            if result is None:
                remaining.append(pending)
                continue
            row = self._topic_stat(state, topic)
            row[result] = int(row.get(result) or 0) + 1
            row["last_result_at"] = now
            confidence, resolved = self._confidence(row)
            row["confidence"] = confidence
            if resolved in (3, 8, 20):
                label = "useful" if confidence >= 0.6 else "usually unnecessary"
                notices.append(f"Learned advice pattern: {topic.replace('-', ' ')} is {label} ({confidence:.0%} confidence)")
        state["pending_outcomes"] = remaining[-MAX_PENDING:]
        return notices

    def _refresh_predictions(self, state, memory=None):
        previous = {row.get("key") for row in state.get("predictions") or []}
        predictions = []
        labels = {
            "session_jumps": ("Typical session", "jumps", 0),
            "session_minutes": ("Typical session length", "minutes", 0),
            "session_distance_ly": ("Typical session distance", "light years", 0),
            "system_bodies": ("Typical surveyed system", "bodies", 0),
            "system_bio_signals": ("Typical biological yield", "signals", 1),
            "session_trade_profit_cr": ("Typical profitable trade session", "credits", 0),
            "trade_sale_profit_cr": ("Typical trade sale profit", "credits", 0),
            "trade_profit_per_ton_cr": ("Typical trade margin", "credits per tonne", 0),
            "prospector_best_pct": ("Typical best prospector result", "percent", 1),
            "mining_session_prospected": ("Typical mining search", "asteroids", 0),
            "mining_session_refined_tons": ("Typical mining yield", "tonnes", 0),
            "trade_session_transactions": ("Typical trade session", "transactions", 0),
            "combat_kill_reward_cr": ("Typical PvE reward", "credits", 0),
            "combat_sortie_victories": ("Typical PvE sortie", "victories", 0),
            "combat_sortie_reward_cr": ("Typical PvE sortie reward", "credits", 0),
            "combat_sortie_minimum_hull_pct": ("Typical post-combat hull floor", "percent", 0),
            "powerplay_merit_gain": ("Typical Powerplay merit gain", "merits", 0),
            "powerplay_delivery_batch": ("Typical Powerplay delivery", "units", 0),
            "powerplay_collection_batch": ("Typical Powerplay collection", "units", 0),
            "powerplay_session_merits": ("Typical Powerplay session", "merits", 0),
            "powerplay_session_delivered": ("Typical Powerplay session delivery", "units", 0),
            "fuel_at_jump_pct": ("Typical jump fuel reserve", "percent", 0),
            "cargo_at_sale_pct": ("Typical cargo sale point", "percent", 0),
            "jumps_at_dock": ("Typical docking point", "session jumps", 0),
            "survey_completion_pct": ("Typical survey completion", "percent", 0),
            "system_signals": ("Typical system signal count", "signals", 0),
            "session_fuel_scooped_t": ("Typical session fuel scooped", "tonnes", 1),
            "session_missions_completed": ("Typical mission session", "missions completed", 0),
            "session_mission_rewards_cr": ("Typical mission session reward", "credits", 0),
            "session_ground_items": ("Typical ground collection", "items", 0),
        }
        for key, (label, unit, digits) in labels.items():
            metric = (state.get("metrics") or {}).get(key) or {}
            count = int(metric.get("count") or 0)
            if count < 3:
                continue
            value = round(_number(metric.get("median")), digits)
            predictions.append({
                "key": key, "label": label, "value": value, "unit": unit,
                "confidence": min(0.95, round(0.35 + count * 0.05, 2)),
                "samples": count,
            })
        if memory is not None:
            bio_baseline = memory.bio_sell_baseline()
            if bio_baseline:
                predictions.append({
                    "key": "bio_sell_samples", "label": "Expected biology sale",
                    "value": int(bio_baseline), "unit": "samples",
                    "confidence": min(0.95, 0.55 + len(
                        (memory.state.get("habits_data") or {}).get("bio_sell_counts") or []
                    ) * 0.03),
                    "samples": len((memory.state.get("habits_data") or {}).get("bio_sell_counts") or []),
                })
        state["predictions"] = predictions[:MAX_PREDICTIONS]
        new_keys = {row.get("key") for row in predictions} - previous
        return [row for row in predictions if row.get("key") in new_keys]

    @staticmethod
    def _goals(snapshot):
        snapshot = snapshot or {}
        nav = snapshot.get("navigation") or {}
        survey = snapshot.get("survey") or {}
        objectives = snapshot.get("objectives") or {}
        biology = snapshot.get("biology") or {}
        mining = snapshot.get("mining") or {}
        trade = snapshot.get("trade") or {}
        combat = snapshot.get("combat") or {}
        powerplay = snapshot.get("powerplay") or {}
        flight = snapshot.get("flight") or {}
        mission_context = snapshot.get("missions") or {}
        signals = snapshot.get("signals") or {}
        ground = snapshot.get("ground_operations") or {}
        strategy = snapshot.get("strategy") or {}
        rescue_legal = snapshot.get("rescue_legal") or {}
        exploration = snapshot.get("exploration_intelligence") or {}
        goals = []

        def add(key, label, priority, topic):
            if any(row.get("key") == key for row in goals):
                return
            goals.append({"key": key, "label": label, "priority": int(priority), "topic": topic})

        action_keys = {
            "biology": "sample", "survey": "survey", "route": "route",
            "expedition": "expedition",
        }
        for action in list(exploration.get("actions") or [])[:3]:
            kind = str(action.get("kind") or "exploration")
            key = action_keys.get(kind, str(action.get("id") or f"exploration-{kind}"))
            add(
                key, str(action.get("title") or "Continue exploration work"),
                max(45, min(88, int(action.get("priority") or 55))), kind,
            )

        remaining = int(nav.get("remaining_jumps") or 0)
        destination = nav.get("final_destination")
        if remaining and destination:
            add("route", f"Reach {destination} ({remaining} jumps remain)", 75, "route")
        urgent = [row for row in mission_context.get("urgent") or [] if not row.get("expired")]
        if urgent:
            mission = urgent[0]
            minutes = int(mission.get("expiry_minutes") or 0)
            destination = mission.get("system") or mission.get("settlement") or "its destination"
            add("urgent-mission", f"Complete {mission.get('name') or 'mission'} at {destination} ({minutes} min remain)", 94, "mission")
        active_missions = int(mission_context.get("active") or objectives.get("active_missions") or 0)
        if active_missions and not urgent:
            add("missions", f"Complete {active_missions} active mission{'s' if active_missions != 1 else ''}", 70, "mission")
        grouped = list(mission_context.get("grouped_destinations") or [])
        if grouped:
            add("mission-route", f"Combine {grouped[0].get('missions')} missions in {grouped[0].get('system')}", 77, "mission-route")
        if int(mission_context.get("ground") or 0) and ground.get("settlement"):
            add("ground-missions", f"Review ground objectives near {(ground.get('settlement') or {}).get('name') or 'the settlement'}", 79, "ground")
        unresolved = max(0, int(survey.get("total_bodies") or 0) - int(survey.get("scanned_bodies") or 0))
        if unresolved:
            add("survey", f"Resolve {unresolved} remaining system bod{'ies' if unresolved != 1 else 'y'}", 62, "survey")
        bio_remaining = max(
            0, int(survey.get("biological_signals") or 0)
            - int(survey.get("completed_biological_analyses") or 0),
        )
        if bio_remaining:
            add("biology", f"Investigate {bio_remaining} unresolved biological signal{'s' if bio_remaining != 1 else ''}", 68, "biology")
        if biology.get("species") and int(biology.get("progress") or 0):
            add("sample", f"Complete {biology.get('species')} sampling", 82, "biology")
        mining_missions = list(mining.get("missions") or [])
        mining_remaining = sum(
            int(row.get("remaining") or 0) for row in mining_missions if isinstance(row, dict)
        )
        if mining_remaining:
            add("mining-contracts", f"Collect {mining_remaining} t for active mining contracts", 76, "mining")
        elif mining.get("active"):
            add("mining-session", f"Continue mining session ({int(mining.get('refined_tons') or 0)} t refined)", 54, "mining")
        bought_by_commodity = trade.get("commodities_bought") or {}
        sold_by_commodity = trade.get("commodities_sold") or {}
        trade_open_units = sum(
            max(0, int(count or 0) - int(sold_by_commodity.get(name) or 0))
            for name, count in bought_by_commodity.items()
        )
        if trade_open_units and int(flight.get("cargo_t") or 0):
            add("trade-cargo", f"Sell or route {trade_open_units} t of session trade cargo", 64, "trade")
        trade_plan = trade.get("plan") or {}
        if trade_plan.get("to_station"):
            add(
                "trade-plan",
                f"Run {trade_plan.get('kind') or 'trade'} plan to {trade_plan.get('to_station')}",
                73, "trade",
            )
        hull = combat.get("hull_percent")
        if combat.get("active") and hull is not None and float(hull) <= 35:
            add("combat-survival", f"Break contact or finish the encounter at {float(hull):.0f}% hull", 96, "combat")
        elif combat.get("active"):
            target = (combat.get("current_target") or {}).get("pilot") or (combat.get("current_target") or {}).get("ship")
            add("combat-encounter", f"Resolve active hostile encounter{f' with {target}' if target else ''}", 78, "combat")
        incomplete_stacks = [
            row for row in combat.get("massacre_stacks") or []
            if isinstance(row, dict) and not row.get("complete")
        ]
        if incomplete_stacks:
            stack = incomplete_stacks[0]
            remaining_kills = max(0, int(stack.get("kills_needed") or 0) - int(stack.get("kills_done") or 0))
            add("massacre-stack", f"Defeat {remaining_kills} more {stack.get('faction') or 'mission'} targets", 74, "combat")
        if int(combat.get("unclaimed_reward_cr") or 0) >= 1_000_000:
            add("combat-vouchers", f"Redeem {int(combat.get('unclaimed_reward_cr') or 0):,} credits in combat vouchers", 67, "combat")
        powerplay_outstanding = int(powerplay.get("outstanding_units") or 0)
        if powerplay.get("pledged") and powerplay_outstanding:
            add(
                "powerplay-delivery",
                f"Deliver {powerplay_outstanding:,} outstanding Powerplay unit{'s' if powerplay_outstanding != 1 else ''}",
                78, "powerplay",
            )
        pp_system = powerplay.get("system") or {}
        if powerplay.get("pledged") and pp_system.get("contested"):
            add(
                "powerplay-system",
                f"Review contested Powerplay conditions in {pp_system.get('name') or 'the current system'}",
                72, "powerplay",
            )
        unsold = int(objectives.get("unsold_data_total_cr") or 0)
        if unsold >= 1_000_000:
            add("unsold-data", f"Secure {unsold:,} credits of unsold survey data", 65 if unsold < 10_000_000 else 82, "data")
        engineering = list(objectives.get("pinned_engineering") or [])
        if engineering:
            name = engineering[0].get("name") if isinstance(engineering[0], dict) else str(engineering[0])
            add("engineering", f"Continue pinned engineering work: {name}", 55, "engineering")
        if int(rescue_legal.get("rescue_units") or 0):
            add("rescue-cargo", f"Deliver {int(rescue_legal.get('rescue_units') or 0)} rescued item{'s' if int(rescue_legal.get('rescue_units') or 0) != 1 else ''}", 76, "rescue")
        if int(rescue_legal.get("stolen_units") or 0) or int(mission_context.get("illegal") or 0):
            add("legal-cargo", "Manage illicit cargo and legal exposure", 86, "legal")
        notable_signals = list(signals.get("notable") or [])
        if notable_signals:
            signal = max(notable_signals, key=lambda row: int(row.get("threat") or 0))
            add("signal", f"Assess {signal.get('name') or signal.get('type')} (threat {int(signal.get('threat') or 0)})", 80 if int(signal.get("threat") or 0) >= 3 else 65, "signals")
        carrier = strategy.get("carrier") or {}
        if carrier.get("jump_destination"):
            add("carrier-jump", f"Monitor carrier jump to {carrier.get('jump_destination')}", 69, "strategy")
        try:
            carrier_fuel = float(carrier.get("fuel_level"))
            carrier_capacity = float(carrier.get("fuel_capacity") or 0)
            if carrier_capacity and carrier_fuel / carrier_capacity <= 0.15:
                add("carrier-fuel", f"Replenish carrier fuel ({carrier_fuel:.0f} of {carrier_capacity:.0f})", 84, "logistics")
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        matching = list(strategy.get("colonisation_matching_cargo") or [])
        if matching:
            add("colonisation-cargo", f"Deliver {sum(int(row.get('aboard') or 0) for row in matching)} t of matched construction cargo", 78, "colonisation")
        conflicts = list(strategy.get("conflicts") or [])
        if strategy.get("watched_factions_here") and conflicts:
            add("watched-faction", "Review the watched faction's local conflict", 74, "strategy")
        community_goals = []
        for row in strategy.get("community_goals") or []:
            if not isinstance(row, dict) or row.get("complete"):
                continue
            try:
                expiry = datetime.fromisoformat(str(row.get("expiry")).replace("Z", "+00:00"))
                if expiry <= datetime.now(timezone.utc):
                    continue
            except (TypeError, ValueError):
                pass
            community_goals.append(row)
        if community_goals:
            goal = community_goals[0]
            priority = 62
            expiry_note = ""
            try:
                expiry = datetime.fromisoformat(str(goal.get("expiry")).replace("Z", "+00:00"))
                hours = max(0, round((expiry - datetime.now(timezone.utc)).total_seconds() / 3600))
                expiry_note = f", {hours} h remain"
                if hours <= 6:
                    priority = 88
            except (TypeError, ValueError):
                pass
            add("community-goal", f"Continue {goal.get('title') or 'Community Goal'} ({int(goal.get('contribution') or 0):,} contributed{expiry_note})", priority, "strategy")
        if ground.get("on_foot") and (int(ground.get("medkits") or 0) == 0 or int(ground.get("energy_cells") or 0) == 0):
            missing = "medkits" if int(ground.get("medkits") or 0) == 0 else "energy cells"
            add("ground-supplies", f"Restock {missing} for ground operations", 73, "ground")
        return sorted(goals, key=lambda row: row["priority"], reverse=True)[:MAX_GOALS]

    def observe(self, event, snapshot, memory=None, raw=None, startup_replay=False):
        """Update learned outcomes, goals, baselines and predictions."""
        if not self.enabled or startup_replay:
            return []
        event = str(event or "")
        state = self._state()
        notices = self._resolve_outcomes(state, event)
        survey = (snapshot or {}).get("survey") or {}
        flight = (snapshot or {}).get("flight") or {}
        session = (snapshot or {}).get("session") or {}
        mining = (snapshot or {}).get("mining") or {}
        trade = (snapshot or {}).get("trade") or {}
        combat = (snapshot or {}).get("combat") or {}
        powerplay = (snapshot or {}).get("powerplay") or {}
        signals = (snapshot or {}).get("signals") or {}
        ground = (snapshot or {}).get("ground_operations") or {}
        if self.config.get("cockpit_cognition_learning_enabled", True):
            if (mining.get("active") and int(mining.get("prospected") or 0) >= 2
                    and mining.get("limpets") is not None
                    and int(mining.get("limpets") or 0) <= 5):
                self._learn_preparation(
                    state, "mining-limpets", "Carry a healthier limpet reserve for mining", memory,
                )
            if (ground.get("on_foot") and (
                    int(ground.get("medkits") or 0) == 0
                    or int(ground.get("energy_cells") or 0) == 0)):
                self._learn_preparation(
                    state, "ground-supplies", "Check medkits and energy cells before ground work", memory,
                )
            if event in ("Repair", "RepairAll"):
                self._learn_preparation(
                    state, "repair-visits", "Review repair capability before extended operations", memory,
                )
            elif event == "Synthesis":
                self._learn_preparation(
                    state, "synthesis-use", "Review synthesis materials before departure", memory,
                )
        if event == "FSSAllBodiesFound":
            self._observe_metric(state, "system_bodies", survey.get("total_bodies"))
            self._observe_metric(state, "system_bio_signals", survey.get("biological_signals"))
            self._observe_metric(state, "system_valuable_bodies", len(survey.get("valuable_bodies") or []))
        elif event in ("FSDJump", "CarrierJump") and flight.get("fuel_percent") is not None:
            self._observe_metric(state, "fuel_at_jump_pct", flight.get("fuel_percent"))
            previous_signals = signals.get("last_summary") or {}
            if int(previous_signals.get("total") or 0):
                self._observe_metric(state, "system_signals", previous_signals.get("total"))
        elif event == "MarketSell" and int(session.get("trade_profit_cr") or 0) > 0:
            self._observe_metric(state, "session_trade_profit_cr", session.get("trade_profit_cr"))
            if flight.get("cargo_percent") is not None:
                self._observe_metric(state, "cargo_at_sale_pct", flight.get("cargo_percent"))
        elif event == "Docked" and int(session.get("jumps") or 0) > 0:
            self._observe_metric(state, "jumps_at_dock", session.get("jumps"))
        elif event == "StartJump" and int(survey.get("total_bodies") or 0) > 0:
            completion = (
                int(survey.get("scanned_bodies") or 0) * 100
                / int(survey.get("total_bodies") or 1)
            )
            self._observe_metric(state, "survey_completion_pct", completion)
        if event == "ProspectedAsteroid" and mining.get("last_materials"):
            best = max(
                (_number(row.get("percent"), 0) for row in mining.get("last_materials") if isinstance(row, dict)),
                default=0,
            )
            if best:
                self._observe_metric(state, "prospector_best_pct", best)
        if event == "MarketSell" and trade.get("last_transaction"):
            sale = trade.get("last_transaction") or {}
            self._observe_metric(state, "trade_sale_profit_cr", sale.get("profit"))
            self._observe_metric(state, "trade_profit_per_ton_cr", sale.get("profit_per_ton"))
        if event in ("FSDJump", "CarrierJump") and mining.get("last_summary"):
            summary = mining.get("last_summary") or {}
            if int(summary.get("prospected") or 0):
                self._observe_metric(state, "mining_session_prospected", summary.get("prospected"))
            if int(summary.get("refined_tons") or 0):
                self._observe_metric(state, "mining_session_refined_tons", summary.get("refined_tons"))
        if event in ("Bounty", "FactionKillBond", "CapShipBond") and combat.get("last_victory"):
            self._observe_metric(state, "combat_kill_reward_cr", (combat.get("last_victory") or {}).get("reward_cr"))
        if event in ("EscapeInterdiction", "StartJump", "FSDJump", "CarrierJump", "Docked", "Died") and combat.get("last_summary"):
            summary = combat.get("last_summary") or {}
            if int(summary.get("victories") or 0):
                self._observe_metric(state, "combat_sortie_victories", summary.get("victories"))
            if int(summary.get("reward_cr") or 0):
                self._observe_metric(state, "combat_sortie_reward_cr", summary.get("reward_cr"))
            if summary.get("minimum_hull_percent") is not None:
                self._observe_metric(state, "combat_sortie_minimum_hull_pct", summary.get("minimum_hull_percent"))
        if event == "PowerplayMerits":
            self._observe_metric(state, "powerplay_merit_gain", (raw or {}).get("MeritsGained"))
        elif event == "PowerplayCollect":
            self._observe_metric(state, "powerplay_collection_batch", (raw or {}).get("Count"))
        elif event == "PowerplayDeliver":
            self._observe_metric(state, "powerplay_delivery_batch", (raw or {}).get("Count"))
        state["goals"] = self._goals(snapshot)
        new_predictions = self._refresh_predictions(state, memory)
        for prediction in new_predictions:
            notices.append(
                f"New pilot prediction: {prediction['label'].lower()} is about "
                f"{prediction['value']:,} {prediction['unit']}"
            )
        if notices:
            state["learning_notices"].extend({"at": _utc_now(), "text": text} for text in notices)
        self._commit(state)
        return notices[:2]

    @staticmethod
    def _candidate(topic, priority, reason, templates, tags, outcome=None,
                   category="objectives", sources=()):
        return {
            "topic": topic, "priority": float(priority), "reason": reason,
            "templates": tuple(templates), "tags": tuple(tags),
            "outcome": outcome, "category": category,
            "sources": tuple(sources),
        }

    def _memory_candidate(self, memory, system_name):
        if not memory or not system_name or memory.system_visits(system_name) < 2:
            return None
        rows = memory.memories_for_system(system_name, limit=4)
        if not rows:
            return None
        query = _words(system_name) | {"arrival", "system", "return"}
        ranked = []
        for index, row in enumerate(rows):
            overlap = len(query & _words(row.get("text")))
            score = int(row.get("salience") or 0) * 2 + overlap * 3 - index
            ranked.append((score, row))
        row = max(ranked, key=lambda item: item[0])[1]
        text = str(row.get("text") or "").strip().rstrip(".!?")
        if not text:
            return None
        return self._candidate(
            f"memory-return:{row.get('id') or system_name}", 58,
            "A relevant episode is attached to this familiar system.",
            (
                f"This system connects with an earlier flight entry: {text}.",
                f"I remember this system from our archive: {text}.",
                f"Returning here brings one relevant record forward: {text}.",
                f"A previous visit matters here. The record says: {text}.",
                f"This system is familiar for a reason: {text}.",
            ), ("memory", "pattern"), category="navigation",
        )

    def _anomaly_candidates(self, snapshot, memory, event):
        state = self._state()
        metrics = state.get("metrics") or {}
        survey = (snapshot or {}).get("survey") or {}
        session = (snapshot or {}).get("session") or {}
        traffic = (snapshot or {}).get("traffic") or {}
        rows = []
        if event == "FSSAllBodiesFound":
            bodies = int(survey.get("total_bodies") or 0)
            baseline = (metrics.get("system_bodies") or {}).get("median")
            count = int((metrics.get("system_bodies") or {}).get("count") or 0)
            if baseline and count >= 4 and bodies >= max(float(baseline) + 8, float(baseline) * 1.7):
                rows.append(self._candidate(
                    "anomaly-system-size", 76,
                    f"{bodies} bodies is well above the learned median of {round(float(baseline))}.",
                    (
                        f"This is an unusually large system for our survey history: {bodies} bodies against a typical {round(float(baseline))}.",
                        f"Survey anomaly noted. {bodies} bodies is well above our usual {round(float(baseline))}.",
                        f"System scale stands out: {bodies} bodies compared with our median of {round(float(baseline))}.",
                        f"Our normal survey contains about {round(float(baseline))} bodies; this one contains {bodies}.",
                    ), ("anomaly", "survey", "learning"), category="exploration",
                ))
            signals = int(survey.get("biological_signals") or 0)
            bio_base = (metrics.get("system_bio_signals") or {}).get("median")
            bio_count = int((metrics.get("system_bio_signals") or {}).get("count") or 0)
            if bio_base is not None and bio_count >= 4 and signals >= max(float(bio_base) + 3, 4):
                rows.append(self._candidate(
                    "anomaly-biology-yield", 79,
                    f"{signals} signals exceeds the learned biological baseline.",
                    (
                        f"Biological yield is unusually high here: {signals} signals against a typical {round(float(bio_base), 1)}.",
                        f"This system stands above our biological baseline with {signals} signals.",
                        f"The biology count is exceptional for us: {signals} signals against a norm of {round(float(bio_base), 1)}.",
                        f"Our learned baseline is {round(float(bio_base), 1)} biological signals; this system has {signals}.",
                    ), ("anomaly", "biology", "learning"), outcome="biology", category="exploration",
                ))
        if event in ("FSDJump", "Location", "TrafficUpdate") and memory:
            day = int(traffic.get("day") or 0)
            known = [
                int(((row or {}).get("traffic") or {}).get("day") or 0)
                for row in (memory.state.get("systems") or {}).values()
                if isinstance((row or {}).get("traffic"), dict)
            ]
            typical = _median([value for value in known if value > 0])
            if typical and len(known) >= 8 and day >= max(20, float(typical) * 3):
                rows.append(self._candidate(
                    "anomaly-traffic", 72,
                    f"Daily traffic {day} is above the learned travelled-system baseline.",
                    (
                        f"Traffic is unusually active here: {day} movements today against a typical {round(float(typical))}.",
                        f"This system is busier than our normal route history, with {day} movements today.",
                        f"Local traffic stands well above our travelled-system norm: {day} movements today.",
                        f"We usually see about {round(float(typical))} daily movements; this system is reporting {day}.",
                    ), ("anomaly", "route", "pattern"), category="navigation",
                ))
        typical_jumps = (metrics.get("session_jumps") or {}).get("median")
        jumps = int(session.get("jumps") or 0)
        if event in ("FSDJump", "CarrierJump") and typical_jumps and jumps >= max(10, float(typical_jumps) * 1.5):
            rows.append(self._candidate(
                "anomaly-long-session", 52,
                "The active session has passed the learned jump baseline.",
                (
                    f"This flight has reached {jumps} jumps, beyond our usual session of {round(float(typical_jumps))}.",
                    f"We are running longer than usual: {jumps} jumps against a typical {round(float(typical_jumps))}.",
                    f"Session distance is stretching past our normal pattern at {jumps} jumps.",
                    f"Our typical session is {round(float(typical_jumps))} jumps; this one has reached {jumps}.",
                ), ("anomaly", "session", "pattern"), category="ambient",
            ))
        if event == "StartJump" and int(survey.get("total_bodies") or 0) > 0:
            survey_metric = metrics.get("survey_completion_pct") or {}
            typical_completion = survey_metric.get("median")
            sample_count = int(survey_metric.get("count") or 0)
            current_completion = (
                int(survey.get("scanned_bodies") or 0) * 100
                / int(survey.get("total_bodies") or 1)
            )
            if (typical_completion and sample_count >= 4
                    and current_completion + 25 < float(typical_completion)):
                rows.append(self._candidate(
                    "anomaly-survey-depth", 54,
                    "The completed survey fraction is below the pilot's learned norm.",
                    (
                        f"We are leaving this system at {round(current_completion)} percent surveyed; your usual completion is {round(float(typical_completion))} percent.",
                        f"This survey ended earlier than your normal pattern: {round(current_completion)} percent against a typical {round(float(typical_completion))}.",
                        f"Departure survey depth is {round(current_completion)} percent, below your usual {round(float(typical_completion))} percent.",
                        f"This system closes at {round(current_completion)} percent surveyed; your learned norm is {round(float(typical_completion))} percent.",
                    ), ("anomaly", "survey", "pattern"), category="exploration",
                ))
        return rows

    def _candidates(self, event, raw, snapshot, memory, key=None, state=None):
        raw = raw if isinstance(raw, dict) else {}
        snapshot = snapshot or {}
        nav = snapshot.get("navigation") or {}
        survey = snapshot.get("survey") or {}
        objectives = snapshot.get("objectives") or {}
        station = snapshot.get("station") or {}
        flight = snapshot.get("flight") or {}
        biology = snapshot.get("biology") or {}
        session = snapshot.get("session") or {}
        mining = snapshot.get("mining") or {}
        trade = snapshot.get("trade") or {}
        combat = snapshot.get("combat") or {}
        powerplay = snapshot.get("powerplay") or {}
        mission_context = snapshot.get("missions") or {}
        signals = snapshot.get("signals") or {}
        ship_operations = snapshot.get("ship_operations") or {}
        ground = snapshot.get("ground_operations") or {}
        strategy = snapshot.get("strategy") or {}
        rescue_legal = snapshot.get("rescue_legal") or {}
        exploration = snapshot.get("exploration_intelligence") or {}
        current_system = nav.get("current_system")
        candidates = []
        key_text = str(key or "")
        if key_text.startswith("advisor:"):
            return []

        route_intel = exploration.get("route") or {}
        completion_intel = exploration.get("completion") or {}
        if event in ("FSDJump", "CarrierJump", "Location") and route_intel.get("off_route"):
            distance = route_intel.get("nearest_distance_ly")
            nearest = route_intel.get("nearest_system") or "the plotted route"
            distance_text = f"{float(distance):.1f} light-years" if distance is not None else "an unresolved distance"
            candidates.append(self._candidate(
                "exploration-off-route", 74,
                "The verified live position is outside the active plotted route.",
                (
                    f"Arrival check: we are off the plotted route, {distance_text} from {nearest}.",
                    f"Route comparison places us {distance_text} from the nearest plotted point, {nearest}.",
                    f"This arrival sits outside the active route; {nearest} is the nearest plotted reference at {distance_text}.",
                ), ("route", "survey", "navigation"), category="exploration",
                sources=("journal", "navigation"),
            ))
        if event == "FSSAllBodiesFound" and completion_intel:
            actions = list(exploration.get("actions") or [])
            next_action = actions[0].get("title") if actions else None
            if next_action:
                candidates.append(self._candidate(
                    "survey-next-action", 70,
                    "The factual completion matrix has a highest-ranked remaining action.",
                    (
                        f"FSS is resolved. The next survey priority is {next_action}.",
                        f"System matrix updated; highest remaining priority is {next_action}.",
                        f"Survey pass complete. I have {next_action} at the top of the action queue.",
                    ), ("survey", "goal", "progress"), category="exploration",
                    sources=("journal",),
                ))
        if event == "StartJump":
            departure = exploration.get("last_departure") or {}
            departure_completion = departure.get("completion") or completion_intel
            reasons = list(departure_completion.get("reasons") or [])
            if reasons and int(departure_completion.get("percent") or 0) < 100:
                candidates.append(self._candidate(
                    "departure-survey-state", 52,
                    "The saved departure checkpoint has verified unfinished survey work.",
                    (
                        f"Departure checkpoint saved at {int(departure_completion.get('percent') or 0)} percent; {reasons[0]}.",
                        f"I have retained the unfinished survey state: {reasons[0]}.",
                        f"System departure logged with work remaining: {reasons[0]}.",
                    ), ("survey", "memory", "progress"), category="ambient",
                    sources=("journal",),
                ))

        preparation = ((state or self._state()).get("preparation") or {})
        limpet_lesson = preparation.get("mining-limpets") or {}
        if (event in ("Undocked", "Loadout")
                and int(limpet_lesson.get("occurrences") or 0) >= 2
                and ship_operations.get("role") == "Mining"
                and ship_operations.get("limpets") is not None
                and int(ship_operations.get("limpets") or 0) < 10):
            limpets = int(ship_operations.get("limpets") or 0)
            candidates.append(self._candidate(
                "prepare-mining-limpets", 78,
                "Repeated mining sessions have reached a low limpet reserve.",
                (
                    f"Learned preparation check: this mining loadout has {limpets} limpets aboard.",
                    f"Before the next mining run, note the limpet reserve is only {limpets}.",
                    f"Our mining history says limpet reserves run short; the current count is {limpets}.",
                    f"Mining preparation flag: {limpets} limpets aboard, below our learned working reserve.",
                ), ("mining", "logistics", "learning"), category="objectives",
                sources=("cargo", "journal"),
            ))
        ground_lesson = preparation.get("ground-supplies") or {}
        if (event in ("Disembark", "SuitLoadout")
                and int(ground_lesson.get("occurrences") or 0) >= 2
                and (int(ground.get("medkits") or 0) == 0
                     or int(ground.get("energy_cells") or 0) == 0)):
            missing = []
            if int(ground.get("medkits") or 0) == 0:
                missing.append("medkits")
            if int(ground.get("energy_cells") or 0) == 0:
                missing.append("energy cells")
            label = " and ".join(missing)
            candidates.append(self._candidate(
                "prepare-ground-supplies", 80,
                "Repeated ground deployments have started without essential supplies.",
                (
                    f"Learned ground check: no {label} are recorded in the current kit.",
                    f"Before moving farther from the ship, the kit still needs {label}.",
                    f"Our ground history flags a recurring shortage: {label} are missing.",
                    f"Ground preparation warning: current supplies show no {label}.",
                ), ("ground", "logistics", "learning", "risk"), category="objectives",
                sources=("status", "cargo"),
            ))

        if event == "ReceiveText":
            message = compass_operations.classify_important_message(raw)
            if message:
                sender = message.get("sender") or "game operations"
                content = message.get("message") or "an actionable communication arrived"
                candidates.append(self._candidate(
                    f"important-message:{message.get('kind')}", message.get("priority") or 82,
                    "An actionable game or NPC communication passed the selective message filter.",
                    (
                        f"Priority communication from {sender}: {content}",
                        f"Actionable message received from {sender}: {content}",
                        f"Operational channel, {sender}: {content}",
                        f"I have flagged this message from {sender}: {content}",
                    ), ("mission", "risk", "communications"), category="objectives",
                    sources=("journal",),
                ))

        destination = raw.get("DestinationSystem") or raw.get("destination_system")
        destination_station = raw.get("DestinationStation") or raw.get("destination_station")
        destination_settlement = raw.get("DestinationSettlement") or raw.get("destination_settlement")
        if event == "MissionAccepted" and destination:
            templates = [f"Mission logged for {destination}."]
            mission_row = next(
                (row for row in mission_context.get("rows") or []
                 if str(row.get("id")) == str(raw.get("MissionID"))),
                {},
            )
            minutes = mission_row.get("expiry_minutes")
            deadline = f" The deadline is in {int(minutes)} minutes." if minutes is not None and int(minutes) > 0 else ""
            if destination_settlement:
                templates.extend((
                    f"Ground objective logged for {destination_settlement} in {destination}.{deadline}",
                    f"Settlement mission recorded: {destination_settlement}, {destination}.{deadline}",
                ))
            elif destination_station:
                templates.extend((
                    f"Mission logged for {destination}, with the objective at {destination_station}.{deadline}",
                    f"Objective recorded: {destination_station} in {destination}.{deadline}",
                ))
            candidates.append(self._candidate(
                "mission-log", 76, "A new mission destination should be retained.",
                templates, ("mission", "progress"), outcome="mission",
                sources=("journal",),
            ))

        if event == "Loadout" and ship_operations.get("role") not in (None, "General"):
            role = ship_operations.get("role")
            capabilities = [name.replace("_", " ") for name, enabled in
                            (ship_operations.get("capabilities") or {}).items() if enabled]
            detail = ", ".join(capabilities[:4]) or "verified modules"
            candidates.append(self._candidate(
                "ship-role", 58,
                "The current modules support a verified broad operating role.",
                (
                    f"Loadout assessment: {role}, supported by {detail}.",
                    f"The current ship configuration reads as {role}; key capability is {detail}.",
                    f"Ship role indexed as {role}, with {detail} available.",
                    f"Operational profile resolved: {role}. I have {detail} in the capability list.",
                ), ("ship", "logistics", "pattern"), category="ambient",
            ))

        if event == "FSSSignalDiscovered":
            raw_name = str(raw.get("SignalName_Localised") or raw.get("SignalName") or "").strip("$;")
            raw_type = str(raw.get("SignalType") or "").strip("$;")
            threat = int(raw.get("ThreatLevel") or 0)
            notable = next(
                (row for row in reversed(signals.get("notable") or [])
                 if int(row.get("threat") or 0) == threat
                 and (not raw_name or raw_name.casefold() in str(row.get("name") or "").casefold()
                      or raw_type.casefold() == str(row.get("type") or "").casefold())),
                None,
            )
            if notable and (threat >= 3 or any(marker in f"{raw_name} {raw_type}".casefold()
                                               for marker in ("distress", "nonhuman", "non human", "salvage", "highgrade", "high grade"))):
                name = notable.get("name") or notable.get("type") or "notable signal"
                candidates.append(self._candidate(
                    "notable-signal", 82 if threat >= 4 else 70,
                    "A non-routine signal has verified risk or salvage value.",
                    (
                        f"Notable signal resolved: {name}, threat level {threat}.",
                        f"Signal analysis flags {name}; verified threat is {threat}.",
                        f"Sensors have a non-routine contact: {name}, threat {threat}.",
                        f"Operational signal marked: {name}. Threat rating is {threat}.",
                    ), ("signals", "risk", "valuable"), outcome="signal", category="objectives",
                    sources=("journal",),
                ))

        if event == "ApproachSettlement":
            settlement = (ground.get("settlement") or {}).get("name") or raw.get("Name") or "the settlement"
            matching = [row for row in mission_context.get("rows") or []
                        if row.get("settlement") and str(row.get("settlement")).casefold() == str(settlement).casefold()]
            if matching:
                candidates.append(self._candidate(
                    "ground-objective-arrival", 81,
                    "The approached settlement matches a verified active mission.",
                    (
                        f"Settlement confirmed: {settlement}. {len(matching)} active objective{'s' if len(matching) != 1 else ''} match this location.",
                        f"We have reached {settlement}; the mission ledger has {len(matching)} matching objective{'s' if len(matching) != 1 else ''}.",
                        f"Ground objective location verified at {settlement}.",
                        f"Approach complete. {settlement} matches the active mission record.",
                    ), ("ground", "mission", "progress"), outcome="mission", category="objectives",
                ))

        if event in ("FSDJump", "CarrierJump", "Location"):
            grouped = [row for row in mission_context.get("grouped_destinations") or []
                       if str(row.get("system") or "").casefold() == str(current_system or "").casefold()]
            if grouped:
                count = int(grouped[0].get("missions") or 0)
                candidates.append(self._candidate(
                    "mission-route-combination", 74,
                    "Several active missions share the verified current system.",
                    (
                        f"Route efficiency note: {count} active missions share {current_system}.",
                        f"This arrival combines {count} mission objectives in {current_system}.",
                        f"Mission routing aligns here; {count} objectives use {current_system}.",
                        f"We can service {count} active missions during this visit to {current_system}.",
                    ), ("mission", "route", "strategy"), outcome="mission-route", category="objectives",
                    sources=("journal", "navigation"),
                ))
            if strategy.get("watched_factions_here") and strategy.get("conflicts"):
                faction = (strategy.get("watched_factions_here") or [{}])[0].get("name") or "the watched faction"
                candidates.append(self._candidate(
                    "watched-faction-conflict", 72,
                    "A watched faction is present alongside a verified local conflict.",
                    (
                        f"Strategic watch: {faction} is involved in local conflict conditions.",
                        f"The watched-faction board is active here; {faction} has a conflict to review.",
                        f"Local BGS conditions matter to {faction}; I have flagged the conflict.",
                        f"Faction watch matched this system. {faction} has active strategic context here.",
                    ), ("strategy", "mission", "pattern"), category="objectives",
                ))

        if event in ("ColonisationConstructionDepot", "ColonisationContribution"):
            matched = list(strategy.get("colonisation_matching_cargo") or [])
            if matched:
                total = sum(int(row.get("aboard") or 0) for row in matched)
                candidates.append(self._candidate(
                    "colonisation-matched-cargo", 79,
                    "Onboard cargo matches verified outstanding construction requirements.",
                    (
                        f"Construction match confirmed: {total} tonnes aboard can be contributed here.",
                        f"The colony ledger matches {total} tonnes in our hold to outstanding resources.",
                        f"We are carrying {total} tonnes required by this construction project.",
                        f"Colonisation cargo check complete: {total} usable tonnes are aboard.",
                    ), ("colonisation", "cargo", "strategy"), outcome="colonisation", category="objectives",
                    sources=("journal", "cargo"),
                ))

        if event == "CommunityGoal":
            active_goals = [row for row in strategy.get("community_goals") or [] if isinstance(row, dict)]
            important = next((row for row in active_goals if row.get("complete") or row.get("top_rank")), None)
            if important:
                title = important.get("title") or "Community Goal"
                contribution = int(important.get("contribution") or 0)
                status = "complete" if important.get("complete") else "in the top rank"
                candidates.append(self._candidate(
                    "community-goal-status", 78,
                    "A joined Community Goal reached a meaningful verified status.",
                    (
                        f"Community Goal update: {title} is {status}, with {contribution:,} contributed.",
                        f"Strategic goal status changed. {title} is {status}; our contribution is {contribution:,}.",
                        f"{title} now reports {status}. The contribution ledger holds {contribution:,}.",
                        f"Community operation update: {title}, {status}, {contribution:,} contributed.",
                    ), ("strategy", "progress", "milestone"), category="objectives",
                ))

        if event in ("SquadronCreated", "JoinedSquadron", "SquadronPromotion",
                     "SquadronDemotion", "LeftSquadron", "KickedFromSquadron",
                     "DisbandedSquadron", "WonATrophyForSquadron"):
            squadron = strategy.get("squadron") or {}
            name = raw.get("SquadronName") or squadron.get("name") or "the squadron"
            detail = {
                "SquadronCreated": f"Squadron record created for {name}.",
                "JoinedSquadron": f"Squadron membership confirmed with {name}.",
                "SquadronPromotion": f"Squadron promotion recorded in {name}.",
                "SquadronDemotion": f"Squadron rank change recorded in {name}.",
                "LeftSquadron": f"Squadron membership with {name} has ended.",
                "KickedFromSquadron": f"Removal from {name} has been recorded.",
                "DisbandedSquadron": f"Squadron {name} has been disbanded.",
                "WonATrophyForSquadron": f"A squadron trophy has been recorded for {name}.",
            }[event]
            candidates.append(self._candidate(
                "squadron-status", 74 if event not in ("KickedFromSquadron", "DisbandedSquadron") else 84,
                "A meaningful squadron membership or achievement event was verified.",
                (detail,), ("strategy", "milestone", "social"), category="objectives",
            ))

        services = " ".join(str(item).casefold() for item in station.get("services") or [])
        exploration = int(objectives.get("unsold_exploration_cr") or 0)
        bio_value = int(objectives.get("unsold_biology_cr") or 0)
        bio_potential = int(objectives.get("unsold_biology_bonus_potential_cr") or 0)
        bio_value_text = (
            f"{bio_value:,} to {bio_value + bio_potential:,} estimated credits"
            if bio_potential else f"{bio_value:,} credits"
        )
        station_name = station.get("name")
        if event == "Docked" and bio_value and "vista" in services:
            at = f" at {station_name}" if station_name else ""
            candidates.append(self._candidate(
                "sell-biology", 88, "Unsold biological data can be acted on at this station.",
                (
                    f"Vista Genomics is available{at} for our biological archive, estimated at {bio_value_text}.",
                    f"We can secure at least {bio_value:,} credits of biological data through Vista Genomics{at}.",
                    f"Our biological archive is estimated at {bio_value_text}, and Vista Genomics is available{at}.",
                    f"Vista Genomics can receive the current biology record{at}; base value is {bio_value:,} credits.",
                ), ("biology", "data", "goal"), outcome="sell-biology",
            ))
        if event == "Docked" and exploration and "cartograph" in services:
            at = f" at {station_name}" if station_name else ""
            candidates.append(self._candidate(
                "sell-exploration", 86, "Unsold exploration data can be acted on at this station.",
                (
                    f"Universal Cartographics is available{at} for our {exploration:,} credits of exploration data.",
                    f"We can secure {exploration:,} credits of exploration data through Universal Cartographics{at}.",
                    f"Our {exploration:,}-credit survey archive can be sold through Universal Cartographics{at}.",
                    f"Universal Cartographics can receive the current exploration record worth approximately {exploration:,} credits{at}.",
                ), ("survey", "data", "goal"), outcome="sell-exploration",
            ))
        if event == "Docked" and int(rescue_legal.get("rescue_units") or 0) and (
                "searchandrescue" in services or "search and rescue" in services):
            units = int(rescue_legal.get("rescue_units") or 0)
            candidates.append(self._candidate(
                "rescue-delivery", 80,
                "Rescue cargo is aboard and this station exposes Search and Rescue.",
                (
                    f"Search and Rescue is available for the {units} recovered item{'s' if units != 1 else ''} aboard.",
                    f"We can hand over {units} rescue item{'s' if units != 1 else ''} at this station.",
                    f"Rescue cargo destination confirmed; {units} recovered item{'s are' if units != 1 else ' is'} ready for transfer.",
                    f"This station can receive our {units} recovered item{'s' if units != 1 else ''}.",
                ), ("rescue", "cargo", "progress"), outcome="rescue", category="objectives",
                sources=("journal", "cargo"),
            ))

        if event == "FSSAllBodiesFound":
            total = int(survey.get("total_bodies") or 0)
            valuable = list(survey.get("valuable_bodies") or [])
            signals = int(survey.get("biological_signals") or 0)
            if valuable or signals:
                details = []
                if valuable:
                    details.append(f"{len(valuable)} high-value mapping target{'s' if len(valuable) != 1 else ''}")
                if signals:
                    details.append(f"{signals} biological signal{'s' if signals != 1 else ''}")
                joined = " and ".join(details)
                candidates.append(self._candidate(
                    "survey-briefing", 82,
                    "The completed FSS contains actionable mapping or biology priorities.",
                    (
                        f"Full spectrum survey complete: {total} bodies, including {joined}.",
                        f"System survey resolved {total} bodies and identified {joined}.",
                        f"FSS analysis is complete with {joined} among {total} bodies.",
                    ), ("survey", "biology", "valuable", "progress"), outcome="survey", category="exploration",
                ))

        cargo_percent = flight.get("cargo_percent")
        if event == "ProspectedAsteroid":
            core = mining.get("last_core")
            current_materials = [
                row for row in mining.get("last_materials") or [] if isinstance(row, dict)
            ]
            current_best = max(current_materials, key=lambda row: float(row.get("percent") or 0), default={})
            best_material = current_best.get("name")
            best_percent = float(current_best.get("percent") or 0)
            if core:
                candidates.append(self._candidate(
                    "mining-core-found", 88,
                    "The prospector identified a motherlode material.",
                    (
                        f"Core deposit confirmed: {core}.",
                        f"The prospector has identified a {core} core.",
                        f"Motherlode signature resolved as {core}.",
                        f"Core asteroid located. Primary material is {core}.",
                    ), ("mining", "valuable", "progress"), category="objectives",
                ))
            elif best_material and best_percent >= 20:
                candidates.append(self._candidate(
                    "mining-rich-prospect", 72,
                    "The strongest prospector result crossed a useful generic concentration threshold.",
                    (
                        f"Strong prospector result: {best_material} at {best_percent:.1f} percent.",
                        f"This rock is carrying {best_percent:.1f} percent {best_material}.",
                        f"Prospector quality is favourable: {best_material}, {best_percent:.1f} percent.",
                        f"Useful concentration detected. {best_percent:.1f} percent {best_material}.",
                    ), ("mining", "valuable", "pattern"), category="objectives",
                ))
        if event == "AsteroidCracked":
            cracked = int(mining.get("cores_cracked") or 0)
            candidates.append(self._candidate(
                "mining-core-cracked", 78,
                "A core asteroid has been opened and the session count is verified.",
                (
                    f"Core fracture confirmed. That is {cracked} opened this session.",
                    f"Asteroid core successfully cracked; session count is now {cracked}.",
                    f"Charge pattern complete. Core number {cracked} is open.",
                    f"Core breach recorded. We have cracked {cracked} this session.",
                ), ("mining", "progress"), category="objectives",
            ))
        if event == "MiningRefined" and cargo_percent is not None and int(cargo_percent) >= 80:
            candidates.append(self._candidate(
                f"mining-cargo-{95 if int(cargo_percent) >= 95 else 80}", 72,
                "The mining hold has crossed a useful capacity threshold.",
                (
                    f"Mining hold is {int(cargo_percent)} percent full at {flight.get('cargo_t')} of {flight.get('cargo_capacity_t')} tonnes.",
                    f"Cargo threshold reached: {int(cargo_percent)} percent of the mining hold is occupied.",
                    f"The refined load now occupies {int(cargo_percent)} percent of available cargo capacity.",
                    f"Mining capacity update: {flight.get('cargo_t')} of {flight.get('cargo_capacity_t')} tonnes loaded, or {int(cargo_percent)} percent.",
                ), ("cargo", "progress", "mining"), outcome="cargo",
            ))
        if (event in ("MiningRefined", "ProspectedAsteroid") and mining.get("active")
                and mining.get("limpets") is not None and int(mining.get("limpets")) <= 5
                and int(mining.get("prospected") or 0) >= 2):
            limpets = int(mining.get("limpets") or 0)
            candidates.append(self._candidate(
                "mining-low-limpets", 80 if limpets <= 2 else 72,
                "The active mining session has a low verified limpet reserve.",
                (
                    f"Limpet reserve is down to {limpets}.",
                    f"Mining consumables are running low: {limpets} limpets remain.",
                    f"We have {limpets} limpets left for prospecting and collection.",
                    f"Limpet count is {limpets}; plan the remaining rocks accordingly.",
                ), ("mining", "cargo", "risk"), category="objectives",
                sources=("journal", "cargo"),
            ))
        if event in ("FSDJump", "CarrierJump") and mining.get("last_summary"):
            summary = mining.get("last_summary") or {}
            prospected = int(summary.get("prospected") or 0)
            refined = int(summary.get("refined_tons") or 0)
            cores = int(summary.get("cores_cracked") or 0)
            if prospected or refined or cores:
                candidates.append(self._candidate(
                    "mining-session-summary", 66,
                    "Leaving the system closed an active mining session with verified totals.",
                    (
                        f"Mining session closed: {prospected} asteroids checked, {refined} tonnes refined and {cores} cores cracked.",
                        f"Final mining ledger: {refined} tonnes from {prospected} prospects, with {cores} opened cores.",
                        f"Departure closes the mining run at {prospected} prospects, {refined} refined tonnes and {cores} cracked cores.",
                        f"Mining record secured. {refined} tonnes refined after checking {prospected} asteroids; {cores} cores opened.",
                    ), ("mining", "session", "progress"), category="objectives",
                ))
        if event == "CargoDepot":
            completed_contracts = [
                row for row in mining.get("missions") or []
                if isinstance(row, dict) and int(row.get("required") or 0) > 0
                and int(row.get("remaining") or 0) == 0
            ]
            if completed_contracts:
                commodity = completed_contracts[0].get("commodity") or "mining cargo"
                candidates.append(self._candidate(
                    "mining-contract-ready", 82,
                    "A tracked mining contract has reached its verified delivery requirement.",
                    (
                        f"Mining contract cargo is complete for {commodity}.",
                        f"The {commodity} delivery requirement is now satisfied.",
                        f"Contract ledger complete: required {commodity} has been delivered.",
                        f"Mining objective fulfilled for {commodity}; the contract is ready to close.",
                    ), ("mining", "mission", "progress"), outcome="mission", category="objectives",
                ))
        profit = int(session.get("trade_profit_cr") or 0)
        milestones = (1_000_000, 5_000_000, 10_000_000, 50_000_000, 100_000_000)
        milestone = max((mark for mark in milestones if profit >= mark), default=0)
        if event == "MarketSell" and milestone:
            candidates.append(self._candidate(
                f"trade-profit-{milestone}", 68,
                "Session trade profit crossed a meaningful milestone.",
                (
                    f"The trade ledger has reached {profit:,} credits of session profit.",
                    f"Session trading profit now stands at {profit:,} credits.",
                    f"Trade milestone recorded: {profit:,} credits of session profit.",
                ), ("trade", "progress", "milestone"), category="objectives",
            ))
        if event == "MarketBuy" and trade.get("last_transaction"):
            purchase = trade.get("last_transaction") or {}
            investment = abs(int(purchase.get("profit") or 0))
            if investment >= 5_000_000:
                commodity = purchase.get("commodity") or "commodity cargo"
                candidates.append(self._candidate(
                    "trade-large-investment", 67,
                    "A large verified purchase materially increased cargo exposure.",
                    (
                        f"Trade position opened: {int(purchase.get('count') or 0)} tonnes of {commodity} for {investment:,} credits.",
                        f"Cargo investment is {investment:,} credits in {commodity}.",
                        f"Large purchase logged: {commodity}, {investment:,} credits committed.",
                        f"The new {commodity} position puts {investment:,} credits into the hold.",
                    ), ("trade", "cargo", "risk"), category="objectives",
                ))
        if event == "MarketSell" and trade.get("last_transaction"):
            sale = trade.get("last_transaction") or {}
            sale_profit = int(sale.get("profit") or 0)
            per_ton = int(sale.get("profit_per_ton") or 0)
            commodity = sale.get("commodity") or "commodity cargo"
            count = int(sale.get("count") or 0)
            if sale_profit < 0:
                candidates.append(self._candidate(
                    "trade-loss-sale", 86,
                    "The completed sale realised a verified loss.",
                    (
                        f"Trade loss recorded: {abs(sale_profit):,} credits on {count} tonnes of {commodity}.",
                        f"That {commodity} sale closed {abs(sale_profit):,} credits below cost.",
                        f"Negative margin confirmed: {abs(per_ton):,} credits per tonne on {commodity}.",
                        f"The ledger shows a {abs(sale_profit):,}-credit loss on this {commodity} sale.",
                    ), ("trade", "risk", "pattern"), category="objectives",
                ))
            elif sale_profit >= 1_000_000 or per_ton >= 20_000:
                candidates.append(self._candidate(
                    "trade-strong-sale", 74,
                    "The completed sale produced a strong verified total or per-tonne margin.",
                    (
                        f"Strong sale: {sale_profit:,} credits profit on {commodity}, or {per_ton:,} per tonne.",
                        f"The {commodity} position closed {sale_profit:,} credits ahead.",
                        f"Trade result confirmed: {sale_profit:,} credits profit from {count} tonnes of {commodity}.",
                        f"That cargo leg returned {per_ton:,} credits per tonne on {commodity}.",
                    ), ("trade", "progress", "valuable"), category="objectives",
                ))

        target = combat.get("current_target") or {}
        if event == "Interdicted" and bool(raw.get("IsThargoid")):
            candidates.append(self._candidate(
                "residual-thargoid-interdiction", 96,
                "The journal identifies the interdiction source as Thargoid; this is immediate encounter safety, not war-campaign tracking.",
                (
                    "Thargoid interdiction confirmed. Prioritise escape vector, heat control and distance.",
                    "Non-human interdiction. Keep the ship cold, boost clear and prepare defensive systems.",
                    "Thargoid contact verified. Break mass lock and avoid committing unless this encounter was intentional.",
                    "Residual Thargoid encounter. Defensive flight profile recommended until the contact is clear.",
                ), ("combat", "risk", "signals"), category="objectives",
            ))
        if (event == "ShipTargeted" and int(target.get("scan_stage") or 0) >= 3
                and not target.get("is_player")):
            legal = str(target.get("legal_status") or "").casefold()
            rank = str(target.get("rank") or "").casefold()
            bounty = int(target.get("bounty_cr") or 0)
            if legal in ("wanted", "enemy", "lawless") and (
                    rank in ("master", "dangerous", "deadly", "elite") or bounty >= 500_000):
                pilot = target.get("pilot") or target.get("ship") or "hostile contact"
                ship = target.get("ship") or "ship"
                details = f", bounty {bounty:,} credits" if bounty else ""
                candidates.append(self._candidate(
                    "combat-threat-scan", 72,
                    "A fully scanned NPC target has a verified high rank or substantial bounty.",
                    (
                        f"Threat scan complete: {pilot}, {rank or 'rank unknown'} {ship}{details}.",
                        f"Hostile profile resolved. {pilot} is flying a {ship}{details}.",
                        f"Target assessment: {pilot}, combat rank {rank or 'unknown'}{details}.",
                        f"PvE contact verified: {ship} piloted by {pilot}{details}.",
                    ), ("combat", "risk", "valuable"), category="objectives",
                ))

        if event in ("Bounty", "FactionKillBond", "CapShipBond") and combat.get("last_victory"):
            victory = combat.get("last_victory") or {}
            reward = int(victory.get("reward_cr") or 0)
            victim_faction = victory.get("victim_faction")
            stacks = [row for row in combat.get("massacre_stacks") or [] if isinstance(row, dict)]
            matching_stack = next(
                (row for row in stacks if victim_faction and str(row.get("faction")).casefold() == str(victim_faction).casefold()),
                None,
            )
            # The companion path already announces a newly completed stack.
            if not (matching_stack and matching_stack.get("complete")):
                progress = ""
                if matching_stack:
                    progress = (
                        f" Massacre progress is {int(matching_stack.get('kills_done') or 0)} "
                        f"of {int(matching_stack.get('kills_needed') or 0)}."
                    )
                target_name = victory.get("target") or "hostile contact"
                candidates.append(self._candidate(
                    "combat-victory", 71 if reward >= 250_000 else 64,
                    "A PvE victory produced a verified bounty or combat bond.",
                    (
                        f"PvE victory confirmed: {target_name}, reward {reward:,} credits.{progress}",
                        f"Combat ledger updated by {reward:,} credits after the {target_name} kill.{progress}",
                        f"Hostile contact resolved. {reward:,} credits recorded.{progress}",
                        f"Kill verified and voucher logged for {reward:,} credits.{progress}",
                    ), ("combat", "progress", "mission"), category="objectives",
                ))

        if event in ("FighterDestroyed", "SRVDestroyed"):
            vehicle = "ship-launched fighter" if event == "FighterDestroyed" else "surface vehicle"
            candidates.append(self._candidate(
                f"combat-{event.casefold()}", 82,
                "A deployed combat vehicle was destroyed.",
                (
                    f"We have lost the {vehicle}.",
                    f"{vehicle.title()} telemetry is gone; destruction confirmed.",
                    f"Combat asset lost: {vehicle}.",
                    f"The {vehicle} has been destroyed. I have updated the sortie record.",
                ), ("combat", "risk", "loss"), category="objectives",
            ))

        if event == "RedeemVoucher" and combat.get("last_redemption"):
            redemption = combat.get("last_redemption") or {}
            amount = int(redemption.get("amount_cr") or 0)
            if amount >= 250_000:
                candidates.append(self._candidate(
                    "combat-vouchers-redeemed", 64,
                    "Combat vouchers were converted into verified credits.",
                    (
                        f"Combat vouchers secured: {amount:,} credits redeemed.",
                        f"The combat ledger is banked for {amount:,} credits.",
                        f"Voucher redemption complete. {amount:,} credits are now secure.",
                        f"PvE earnings transferred: {amount:,} credits.",
                    ), ("combat", "data", "progress"), category="objectives",
                ))

        if event == "EscapeInterdiction" and combat.get("last_summary"):
            candidates.append(self._candidate(
                "combat-interdiction-escaped", 68,
                "The interdiction encounter ended in a verified escape.",
                (
                    "Interdiction escaped. The tether is broken and the route is ours again.",
                    "Escape vector held. We are clear of the interdiction.",
                    "Interdiction defeated; frame-shift control is stable.",
                    "Tether broken cleanly. Navigation is back under our control.",
                ), ("combat", "recovery", "progress"), category="navigation",
            ))

        if event in ("StartJump", "FSDJump", "CarrierJump", "Docked") and combat.get("last_summary"):
            summary = combat.get("last_summary") or {}
            victories = int(summary.get("victories") or 0)
            rewards = int(summary.get("reward_cr") or 0)
            minimum_hull = summary.get("minimum_hull_percent")
            if victories or rewards:
                hull_note = f" Minimum hull was {float(minimum_hull):.0f} percent." if minimum_hull is not None else ""
                candidates.append(self._candidate(
                    "combat-sortie-summary", 67,
                    "The PvE encounter has ended with verified combat totals.",
                    (
                        f"Combat sortie closed: {victories} victories and {rewards:,} credits logged.{hull_note}",
                        f"Post-combat record: {victories} hostiles resolved for {rewards:,} credits.{hull_note}",
                        f"Encounter complete. The ledger holds {victories} victories and {rewards:,} credits.{hull_note}",
                        f"PvE summary secured: {victories} victories, {rewards:,} credits.{hull_note}",
                    ), ("combat", "session", "progress"), category="objectives",
                ))

        if event in ("PowerplayJoin", "PowerplayDefect", "PowerplayLeave"):
            from_power = raw.get("FromPower")
            to_power = raw.get("ToPower") or raw.get("Power")
            if event == "PowerplayJoin":
                detail = f"Pledge registered with {to_power or 'the selected power'}."
                templates = (
                    detail,
                    f"Powerplay allegiance established with {to_power or 'the selected power'}.",
                    f"Strategic record opened for {to_power or 'the new pledge'}.",
                    f"Pledge confirmed. I will track our work for {to_power or 'this power'}.",
                )
            elif event == "PowerplayDefect":
                detail = f"Defection recorded from {from_power or 'the former power'} to {to_power or 'the new power'}."
                templates = (
                    detail,
                    f"Powerplay allegiance changed: {from_power or 'former power'} to {to_power or 'new power'}.",
                    f"Strategic record transferred from {from_power or 'the previous power'} to {to_power or 'the new power'}.",
                    f"Defection confirmed. I am now tracking activity for {to_power or 'the new pledge'}.",
                )
            else:
                detail = f"Powerplay pledge to {raw.get('Power') or from_power or 'the current power'} has ended."
                templates = (
                    detail,
                    "Powerplay allegiance cleared; the active pledge record is now closed.",
                    "Pledge departure confirmed. I have closed the current Powerplay operation.",
                    "Strategic affiliation removed from the active flight record.",
                )
            candidates.append(self._candidate(
                "powerplay-pledge", 84, "The commander's Powerplay allegiance changed.",
                templates, ("powerplay", "milestone", "progress"), category="objectives",
            ))

        if event == "PowerplayRank":
            rank = raw.get("Rank") if raw.get("Rank") is not None else powerplay.get("rank")
            power = raw.get("Power") or powerplay.get("power") or "the pledged power"
            candidates.append(self._candidate(
                "powerplay-rank", 82, "A verified Powerplay rank change was recorded.",
                (
                    f"Powerplay rank updated to {rank} with {power}.",
                    f"Strategic progression confirmed: rank {rank} for {power}.",
                    f"The pledge ledger now records Powerplay rank {rank} with {power}.",
                    f"Rank change secured. Our standing with {power} is now {rank}.",
                ), ("powerplay", "milestone", "progress"), category="objectives",
            ))

        if event == "PowerplayMerits":
            gained = int(raw.get("MeritsGained") or 0)
            total = int(raw.get("TotalMerits") or powerplay.get("merits") or 0)
            if gained >= 100:
                candidates.append(self._candidate(
                    "powerplay-merits", 70 if gained < 1_000 else 80,
                    "A meaningful verified merit gain changed Powerplay progression.",
                    (
                        f"Powerplay progress: {gained:,} merits gained, bringing the total to {total:,}.",
                        f"Merit ledger updated by {gained:,}; current standing is {total:,} merits.",
                        f"Strategic work credited: {gained:,} new merits and {total:,} held in total.",
                        f"The pledge has recognised {gained:,} merits from this action; total merits are {total:,}.",
                    ), ("powerplay", "progress", "milestone"), category="objectives",
                ))

        if event in ("PowerplayCollect", "PowerplayDeliver"):
            action = powerplay.get("last_action") or {}
            count = int(raw.get("Count") or action.get("count") or 0)
            commodity = action.get("commodity") or "Powerplay units"
            outstanding = int(powerplay.get("outstanding_units") or 0)
            if event == "PowerplayCollect" and count >= 10:
                candidates.append(self._candidate(
                    "powerplay-collection", 64,
                    "A useful Powerplay collection batch was recorded for the active operation.",
                    (
                        f"Collected {count:,} {commodity}; {outstanding:,} session units now remain for delivery.",
                        f"Powerplay allocation received: {count:,} {commodity}. Outstanding session cargo is {outstanding:,} units.",
                        f"Strategic cargo logged: {count:,} {commodity} collected, with {outstanding:,} units awaiting delivery.",
                        f"Collection complete for {count:,} {commodity}. I am tracking {outstanding:,} outstanding units.",
                    ), ("powerplay", "cargo", "progress"), category="objectives",
                ))
            elif event == "PowerplayDeliver" and count >= 10:
                completed = outstanding == 0
                candidates.append(self._candidate(
                    "powerplay-delivery-complete" if completed else "powerplay-delivery", 78 if completed else 70,
                    "A Powerplay delivery changed the verified outstanding session allocation.",
                    (
                        f"Delivered {count:,} {commodity}. {'The tracked allocation is complete' if completed else f'{outstanding:,} session units remain'}.",
                        f"Powerplay delivery accepted: {count:,} {commodity}. {'No tracked units remain' if completed else f'{outstanding:,} remain outstanding'}.",
                        f"Strategic cargo transferred: {count:,} {commodity}. {'Session allocation cleared' if completed else f'{outstanding:,} units are still tracked'}.",
                        f"Delivery ledger updated by {count:,} {commodity}. {'The current allocation is closed' if completed else f'{outstanding:,} units remain'}.",
                    ), ("powerplay", "cargo", "progress", "milestone"), category="objectives",
                ))

        if event == "PowerplayFastTrack":
            cost = int(raw.get("Cost") or 0)
            if cost >= 250_000:
                candidates.append(self._candidate(
                    "powerplay-fast-track", 66,
                    "A substantial verified credit cost was spent on Powerplay fast tracking.",
                    (
                        f"Powerplay allocation fast-tracked for {cost:,} credits.",
                        f"Strategic fast track confirmed; cost was {cost:,} credits.",
                        f"The allocation timer was bypassed for {cost:,} credits.",
                        f"Fast-track expenditure recorded at {cost:,} credits.",
                    ), ("powerplay", "trade", "progress"), category="objectives",
                ))

        if event == "PowerplaySalary":
            amount = int(raw.get("Amount") or 0)
            if amount:
                candidates.append(self._candidate(
                    "powerplay-salary", 62,
                    "The pledged power paid a verified salary.",
                    (
                        f"Powerplay salary received: {amount:,} credits.",
                        f"The pledge ledger has paid {amount:,} credits in salary.",
                        f"Strategic salary transfer confirmed at {amount:,} credits.",
                        f"Powerplay service payment secured: {amount:,} credits.",
                    ), ("powerplay", "progress"), category="objectives",
                ))

        pp_system = powerplay.get("system") or {}
        if (event in ("FSDJump", "Location") and powerplay.get("pledged") and pp_system
                and (pp_system.get("contested") or pp_system.get("state"))):
            system_name = pp_system.get("name") or current_system or "this system"
            controller = pp_system.get("controlling") or "no recorded controlling power"
            state_name = pp_system.get("state") or "unclassified"
            pledged = powerplay.get("power") or "our pledged power"
            presence = "present" if pp_system.get("pledged_power_present") else "not listed among the active powers"
            candidates.append(self._candidate(
                "powerplay-system-context", 69 if pp_system.get("contested") else 61,
                "The arrival has verified Powerplay control and presence context.",
                (
                    f"Powerplay briefing for {system_name}: {controller} controls the system, state {state_name}; {pledged} is {presence}.",
                    f"Strategic context: {system_name} is controlled by {controller} with state {state_name}. Our pledge, {pledged}, is {presence}.",
                    f"Local Powerplay record for {system_name} shows {controller} in control and state {state_name}; {pledged} is {presence}.",
                    f"Arrival cross-check for {system_name}: controller {controller}, Powerplay state {state_name}, and {pledged} is {presence}.",
                ), ("powerplay", "route", "progress"), category="navigation",
            ))

        matching = [
            row for row in objectives.get("mission_destinations") or []
            if current_system and str(row.get("system")).casefold() == str(current_system).casefold()
        ]
        if matching and key_text.startswith(("system-arrival:", "route-arrival:", "route-waypoint:")):
            count = len(matching)
            candidates.append(self._candidate(
                "mission-destination", 84,
                "The current system matches an active mission destination.",
                (
                    f"{count} active mission objective{'s' if count != 1 else ''} reference this system.",
                    f"This system matches {count} active mission objective{'s' if count != 1 else ''}.",
                    f"Mission cross-check complete: this system is referenced by {count} active objective{'s' if count != 1 else ''}.",
                    f"We have arrived in a system tied to {count} current mission objective{'s' if count != 1 else ''}.",
                ), ("mission", "goal", "route"), outcome="mission",
            ))
        remaining_jumps = int(nav.get("remaining_jumps") or 0)
        final_destination = nav.get("final_destination")
        if (remaining_jumps and final_destination
                and key_text.startswith(("route-waypoint:", "system-arrival:"))):
            candidates.append(self._candidate(
                "route-progress", 58,
                "The active route has a verified remaining distance in jumps.",
                (
                    f"{remaining_jumps} jump{'s' if remaining_jumps != 1 else ''} remain to {final_destination}.",
                    f"Route progress leaves {remaining_jumps} jump{'s' if remaining_jumps != 1 else ''} before {final_destination}.",
                    f"The plotted course to {final_destination} now has {remaining_jumps} jump{'s' if remaining_jumps != 1 else ''} remaining.",
                    f"Navigation count: {remaining_jumps} more jump{'s' if remaining_jumps != 1 else ''} to reach {final_destination}.",
                ), ("route", "goal", "progress"), outcome="route", category="navigation",
                sources=("navigation", "journal"),
            ))
        unresolved = max(0, int(survey.get("total_bodies") or 0) - int(survey.get("scanned_bodies") or 0))
        if unresolved and key_text.startswith(("system-arrival:", "first-discovery:", "cockpit-context:")):
            candidates.append(self._candidate(
                "survey-progress", 61,
                "The current system survey still contains unresolved bodies.",
                (
                    f"The survey record still has {unresolved} bod{'ies' if unresolved != 1 else 'y'} unresolved.",
                    f"System survey remains incomplete with {unresolved} bod{'ies' if unresolved != 1 else 'y'} outstanding.",
                    f"There {'are' if unresolved != 1 else 'is'} still {unresolved} unresolved bod{'ies' if unresolved != 1 else 'y'} in the system record.",
                    f"Survey sensors have {unresolved} bod{'ies' if unresolved != 1 else 'y'} left to resolve here.",
                ), ("survey", "goal"), outcome="survey", category="exploration",
            ))
        bio_remaining = max(
            0, int(survey.get("biological_signals") or 0)
            - int(survey.get("completed_biological_analyses") or 0),
        )
        if bio_remaining and key_text.startswith(("system-arrival:", "valuable-world:", "cockpit-context:")):
            candidates.append(self._candidate(
                "biology-progress", 69,
                "Biological opportunities remain unresolved in the current system.",
                (
                    f"{bio_remaining} biological signal{'s remain' if bio_remaining != 1 else ' remains'} unresolved here.",
                    f"Biological work remains: {bio_remaining} unresolved signal{'s' if bio_remaining != 1 else ''}.",
                    f"The current system still holds {bio_remaining} unresolved biological signal{'s' if bio_remaining != 1 else ''}.",
                    f"Biology ledger: {bio_remaining} signal{'s are' if bio_remaining != 1 else ' is'} not yet complete.",
                ), ("biology", "goal", "survey"), outcome="biology", category="exploration",
            ))
        if biology.get("species") and int(biology.get("progress") or 0) and key_text.startswith("cockpit-context:"):
            candidates.append(self._candidate(
                "active-biology", 74,
                "An active biological analysis remains unfinished.",
                (
                    f"The active {biology.get('species')} analysis is at sample {int(biology.get('progress'))} of 3.",
                    f"Sampling remains active for {biology.get('species')}: {int(biology.get('progress'))} of 3 complete.",
                    f"{biology.get('species')} fieldwork is still open at {int(biology.get('progress'))} of 3 samples.",
                    f"The genetic sampler has {int(biology.get('progress'))} of 3 required {biology.get('species')} samples.",
                ), ("biology", "goal", "progress"), outcome="biology", category="exploration",
            ))
        unsold = int(objectives.get("unsold_data_total_cr") or 0)
        if unsold >= 5_000_000 and key_text.startswith(("cockpit-context:", "cockpit-shutdown", "route-arrival:", "bio-complete:")):
            candidates.append(self._candidate(
                "unsold-data", 70 if unsold < 20_000_000 else 86,
                "A substantial unsold survey archive is currently at risk.",
                (
                    f"Our unsold survey archive is estimated at {unsold:,} credits.",
                    f"Survey data currently at risk totals approximately {unsold:,} credits.",
                    f"The exploration ledger still holds about {unsold:,} credits in unsold data.",
                    f"We are carrying a survey archive valued near {unsold:,} credits without a completed sale.",
                ), ("data", "goal", "risk"), category="objectives",
                sources=("journal",),
            ))
        if cargo_percent is not None and int(cargo_percent) >= 80 and key_text.startswith(("cockpit-context:", "engineering-ready:", "massacre-complete:")):
            candidates.append(self._candidate(
                "cargo-capacity", 60,
                "Cargo capacity may affect the next planned activity.",
                (
                    f"The cargo hold is {int(cargo_percent)} percent full.",
                    f"Cargo capacity is currently at {int(cargo_percent)} percent.",
                    f"Available hold space has fallen to {100 - int(cargo_percent)} percent.",
                    f"Current cargo load occupies {int(cargo_percent)} percent of the ship's capacity.",
                ), ("cargo", "goal"), outcome="cargo",
                sources=("cargo",),
            ))
        if key_text.startswith("engineering-ready:"):
            candidates.append(self._candidate(
                "engineering-ready", 66,
                "A pinned engineering objective has become actionable.",
                (
                    "This pinned engineering objective is now actionable.",
                    "The current material plan is ready to move into engineering.",
                    "The pinned blueprint now has the materials required for its next step.",
                    "Engineering inventory reconciled; the selected upgrade can proceed.",
                ), ("engineering", "goal", "progress"), outcome="engineering",
            ))
        if event in ("FSDJump", "Location"):
            memory_row = self._memory_candidate(memory, current_system)
            if memory_row:
                candidates.append(memory_row)
        candidates.extend(self._anomaly_candidates(snapshot, memory, event))
        return candidates

    def _score(self, state, candidate, persona, mood, existing=False, voice_stage=None,
               activity_mode=None, fact_quality=None):
        score = float(candidate.get("priority") or 0)
        tags = set(candidate.get("tags") or ())
        weights = PERSONA_TOPIC_WEIGHTS.get(normalize_persona(persona), {})
        multipliers = [float(weights[tag]) for tag in tags if tag in weights]
        if multipliers:
            score *= max(multipliers)
        if normalize_persona(persona) == "Stoic":
            score *= 0.88
        elif normalize_persona(persona) == "Deadpan":
            score *= 0.93
        mood_name = str((mood or {}).get("name") or "calm").casefold()
        if mood_name in ("alert", "shaken"):
            score *= 1.12 if "risk" in tags else 0.82
        elif mood_name in ("curious", "proud") and tags & {"survey", "biology", "learning", "milestone"}:
            score *= 1.08
        stage = str(voice_stage or "new").casefold()
        if tags & {"memory", "learning", "pattern"}:
            if stage in ("trusted", "veteran"):
                score *= 1.12
            elif stage in ("new", "developing"):
                score *= 0.88
        mode = str(activity_mode or "general").casefold()
        mode_tags = {
            "exploration": {"survey", "biology", "signals", "valuable", "route", "data"},
            "mining": {"mining", "cargo", "logistics", "ship"},
            "trade": {"trade", "cargo", "route", "mission", "logistics"},
            "combat": {"combat", "risk", "legal", "mission", "ship"},
            "ground": {"ground", "risk", "mission", "legal"},
            "engineering": {"engineering", "cargo", "logistics", "ship"},
            "powerplay": {"powerplay", "strategy", "combat", "cargo", "route"},
            "carrier": {"strategy", "logistics", "cargo", "route"},
            "colonisation": {"colonisation", "cargo", "logistics", "route"},
            "station": {"data", "trade", "engineering", "mission", "rescue", "legal", "cargo"},
        }
        operational_tags = set().union(*mode_tags.values())
        if mode in mode_tags:
            if tags & mode_tags[mode]:
                score *= 1.15
            elif tags & operational_tags and "risk" not in tags:
                score *= 0.70
        quality = fact_quality if isinstance(fact_quality, dict) else {}
        source_rows = quality.get("sources") or {}
        confidences = [
            _number((source_rows.get(source) or {}).get("confidence"), 0)
            for source in candidate.get("sources") or ()
        ] if source_rows else []
        if confidences:
            fact_confidence = min(confidences)
            score *= max(0.35, fact_confidence)
            candidate["fact_confidence"] = round(fact_confidence, 2)
        else:
            candidate["fact_confidence"] = None
        if quality.get("conflicts") and "risk" not in tags:
            score *= 0.65
        row = self._topic_stat(state, candidate["topic"])
        confidence, resolved = self._confidence(row)
        if resolved >= 3:
            score *= 0.65 + confidence * 0.7
        offered_at = _number(row.get("last_offered_at"), 0)
        if offered_at:
            age = max(0, time.time() - offered_at)
            if age < 300:
                score *= 0.25
            elif age < 900:
                score *= 0.70
        recent_topics = [row.get("topic") for row in (state.get("recent_decisions") or [])[-6:]]
        repeats = recent_topics.count(candidate["topic"])
        score *= 0.7 ** repeats
        if existing:
            score += 8
        candidate["confidence"] = confidence
        candidate["activity_mode"] = mode
        candidate["score"] = round(score, 1)
        return candidate["score"]

    @staticmethod
    def _threshold(level, existing=False):
        base = {"quiet": 78, "proactive": 48}.get(str(level or "Balanced").casefold(), 62)
        return base - (8 if existing else 0)

    @staticmethod
    def _render(state, candidate, mood=None):
        templates = tuple(candidate.get("templates") or ())
        if not templates:
            return ""
        topic = candidate["topic"]
        topic_state = (state.get("topic_stats") or {}).get(topic) or {}
        history = list(topic_state.get("recent_templates") or ())
        history_limit = min(4, len(templates) - 1)
        recent = set(history[-history_limit:]) if history_limit else set()
        available = [index for index in range(len(templates)) if index not in recent] or list(range(len(templates)))
        index = random.choice(available)
        history.append(index)
        state["topic_stats"][topic]["recent_templates"] = history[-4:]
        state["topic_stats"][topic]["last_template"] = index
        line = str(templates[index]).strip()
        mood_name = str((mood or {}).get("name") or "calm").casefold()
        tags = set(candidate.get("tags") or ())
        if mood_name == "curious" and tags & {"survey", "biology", "anomaly"}:
            clauses = MOOD_CLAUSES["curious"]
            previous_clause = topic_state.get("last_mood_clause")
            available_clauses = [item for item in clauses if item != previous_clause] or list(clauses)
            clause = random.choice(available_clauses)
            state["topic_stats"][topic]["last_mood_clause"] = clause
            line = f"{line.rstrip('.')} — {clause}."
        elif mood_name == "proud" and tags & {"progress", "milestone"}:
            clauses = MOOD_CLAUSES["proud"]
            previous_clause = topic_state.get("last_mood_clause")
            available_clauses = [item for item in clauses if item != previous_clause] or list(clauses)
            clause = random.choice(available_clauses)
            state["topic_stats"][topic]["last_mood_clause"] = clause
            line = f"{line.rstrip('.')} — {clause}."
        return line

    def select(self, event, raw, snapshot, memory=None, key=None, existing=False):
        """Return the highest-utility verified observation, or ``None``."""
        if not self.enabled or not self.config.get("cockpit_advisor_enabled", True):
            return None
        state = self._state()
        candidates = self._candidates(
            str(event or ""), raw, snapshot, memory, key=key, state=state,
        )
        if not candidates:
            return None
        details = memory.status_details() if memory else {}
        mood = details.get("mood") or {}
        voice_stage = details.get("voice_stage") or (
            memory.voice_stage(self.config.get("cockpit_personality_level", "Balanced"))
            if memory else "new"
        )
        persona = self.config.get("cockpit_persona", "Compass")
        activity_mode = ((snapshot or {}).get("activity") or {}).get("mode") or "general"
        fact_quality = (snapshot or {}).get("fact_quality") or {}
        for candidate in candidates:
            self._score(
                state, candidate, persona, mood,
                existing=existing, voice_stage=voice_stage,
                activity_mode=activity_mode, fact_quality=fact_quality,
            )
        selected = max(candidates, key=lambda row: row.get("score") or 0)
        threshold = self._threshold(self.config.get("cockpit_advisor_level"), existing=existing)
        if float(selected.get("score") or 0) < threshold:
            self.record_silence(
                selected.get("topic"),
                f"Highest candidate scored {selected.get('score')}; threshold is {threshold}.",
                state=state,
            )
            return None
        selected["line"] = self._render(state, selected, mood=mood)
        selected["decision_reason"] = (
            f"{selected['reason']} Persona {normalize_persona(persona)} and learned usefulness "
            f"produced utility {selected['score']:.1f} in {activity_mode} mode, clearing {threshold}."
        )
        self._commit(state)
        return selected

    def record_silence(self, topic, reason, state=None):
        state = state or self._state()
        decision = {
            "at": _utc_now(), "action": "silence", "topic": str(topic or "none"),
            "score": None, "line": None, "reason": str(reason or "No useful observation."),
        }
        state["last_decision"] = decision
        state["recent_decisions"].append(decision)
        self._commit(state)

    def record_spoken(self, candidate, line=None, save=False):
        if not candidate:
            return
        state = self._state()
        topic = str(candidate.get("topic") or "general")
        row = self._topic_stat(state, topic)
        row["offered"] = int(row.get("offered") or 0) + 1
        row["last_offered_at"] = time.time()
        decision = {
            "at": _utc_now(), "action": "speak", "topic": topic,
            "score": candidate.get("score"),
            "line": str(line or candidate.get("line") or "")[:280],
            "reason": str(candidate.get("decision_reason") or candidate.get("reason") or "")[:320],
        }
        state["last_decision"] = decision
        state["recent_decisions"].append(decision)
        if "anomaly" in set(candidate.get("tags") or ()):
            state["last_anomalies"].append({
                "at": decision["at"], "topic": topic,
                "reason": decision["reason"],
            })
            state["last_anomalies"] = state["last_anomalies"][-8:]
        outcome = candidate.get("outcome")
        if outcome and self.config.get("cockpit_cognition_learning_enabled", True):
            state["pending_outcomes"] = [
                pending for pending in state.get("pending_outcomes") or []
                if pending.get("topic") != topic
            ]
            state["pending_outcomes"].append({
                "topic": topic, "outcome": outcome, "offered_at": time.time(),
            })
        self._commit(state, save=save)

    def status(self):
        state = self._state()
        useful = []
        for topic, row in (state.get("topic_stats") or {}).items():
            confidence, resolved = self._confidence(row)
            if resolved:
                useful.append({
                    "topic": topic, "confidence": confidence, "resolved": resolved,
                    "offered": int(row.get("offered") or 0),
                })
        useful.sort(key=lambda row: (row["resolved"], abs(row["confidence"] - 0.5)), reverse=True)
        return {
            "enabled": self.enabled,
            "last_decision": state.get("last_decision"),
            "decisions": len(state.get("recent_decisions") or []),
            "predictions": list(state.get("predictions") or []),
            "goals": list(state.get("goals") or []),
            "learned_topics": useful[:8],
            "pending_outcomes": len(state.get("pending_outcomes") or []),
            "metrics": {
                key: {name: value for name, value in row.items() if name != "samples"}
                for key, row in (state.get("metrics") or {}).items()
            },
            "anomalies": list(state.get("last_anomalies") or [])[-4:],
            "learning_notices": list(state.get("learning_notices") or [])[-4:],
            "preparation": [
                {"key": key, **dict(row)}
                for key, row in (state.get("preparation") or {}).items()
            ],
        }
