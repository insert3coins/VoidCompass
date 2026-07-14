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

from compass_personas import normalize_persona


COGNITION_SCHEMA = 1
MAX_DECISIONS = 40
MAX_TOPICS = 48
MAX_PENDING = 8
MAX_METRIC_SAMPLES = 24
MAX_GOALS = 8


PERSONA_TOPIC_WEIGHTS = {
    "Tactical": {"mission": 1.30, "risk": 1.25, "cargo": 1.10, "route": 1.10, "ambient": 0.70},
    "Guardian": {"risk": 1.35, "fuel": 1.30, "data": 1.20, "cargo": 1.10},
    "Scientific": {"survey": 1.35, "anomaly": 1.30, "valuable": 1.25, "biology": 1.15},
    "Exobiologist": {"biology": 1.45, "survey": 1.20, "valuable": 1.10},
    "Engineer": {"engineering": 1.40, "cargo": 1.20, "fuel": 1.15, "ship": 1.20},
    "Wayfarer": {"route": 1.25, "memory": 1.25, "session": 1.20, "ambient": 1.10},
    "Pathfinder": {"route": 1.40, "mission": 1.20, "survey": 1.05},
    "Veteran": {"memory": 1.25, "pattern": 1.25, "risk": 1.10, "ambient": 0.85},
    "Deadpan": {"anomaly": 1.20, "pattern": 1.15, "ambient": 0.70},
    "Stoic": {"risk": 1.15, "mission": 1.05, "ambient": 0.55, "memory": 0.75},
    "Optimist": {"progress": 1.30, "milestone": 1.30, "recovery": 1.20},
    "Archivist": {"memory": 1.45, "pattern": 1.30, "milestone": 1.20},
    "Companion": {"memory": 1.30, "session": 1.25, "progress": 1.20},
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

    def observe_session_close(self, snapshot, memory):
        """Learn session baselines and return concise debrief insights."""
        if (not self.enabled or memory is None
                or not memory.state.get("current_session")):
            return []
        state = self._state()
        session = (snapshot or {}).get("session") or {}
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
            "fuel_at_jump_pct": ("Typical jump fuel reserve", "percent", 0),
            "cargo_at_sale_pct": ("Typical cargo sale point", "percent", 0),
            "jumps_at_dock": ("Typical docking point", "session jumps", 0),
            "survey_completion_pct": ("Typical survey completion", "percent", 0),
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
        state["predictions"] = predictions[:10]
        new_keys = {row.get("key") for row in predictions} - previous
        return [row for row in predictions if row.get("key") in new_keys]

    @staticmethod
    def _goals(snapshot):
        snapshot = snapshot or {}
        nav = snapshot.get("navigation") or {}
        survey = snapshot.get("survey") or {}
        objectives = snapshot.get("objectives") or {}
        biology = snapshot.get("biology") or {}
        goals = []

        def add(key, label, priority, topic):
            goals.append({"key": key, "label": label, "priority": int(priority), "topic": topic})

        remaining = int(nav.get("remaining_jumps") or 0)
        destination = nav.get("final_destination")
        if remaining and destination:
            add("route", f"Reach {destination} ({remaining} jumps remain)", 75, "route")
        missions = int(objectives.get("active_missions") or 0)
        if missions:
            add("missions", f"Complete {missions} active mission{'s' if missions != 1 else ''}", 70, "mission")
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
        unsold = int(objectives.get("unsold_data_total_cr") or 0)
        if unsold >= 1_000_000:
            add("unsold-data", f"Secure {unsold:,} credits of unsold survey data", 65 if unsold < 10_000_000 else 82, "data")
        engineering = list(objectives.get("pinned_engineering") or [])
        if engineering:
            name = engineering[0].get("name") if isinstance(engineering[0], dict) else str(engineering[0])
            add("engineering", f"Continue pinned engineering work: {name}", 55, "engineering")
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
        if event == "FSSAllBodiesFound":
            self._observe_metric(state, "system_bodies", survey.get("total_bodies"))
            self._observe_metric(state, "system_bio_signals", survey.get("biological_signals"))
            self._observe_metric(state, "system_valuable_bodies", len(survey.get("valuable_bodies") or []))
        elif event in ("FSDJump", "CarrierJump") and flight.get("fuel_percent") is not None:
            self._observe_metric(state, "fuel_at_jump_pct", flight.get("fuel_percent"))
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
    def _candidate(topic, priority, reason, templates, tags, outcome=None, category="objectives"):
        return {
            "topic": topic, "priority": float(priority), "reason": reason,
            "templates": tuple(templates), "tags": tuple(tags),
            "outcome": outcome, "category": category,
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
                    ), ("anomaly", "survey", "pattern"), category="exploration",
                ))
        return rows

    def _candidates(self, event, raw, snapshot, memory, key=None):
        raw = raw if isinstance(raw, dict) else {}
        snapshot = snapshot or {}
        nav = snapshot.get("navigation") or {}
        survey = snapshot.get("survey") or {}
        objectives = snapshot.get("objectives") or {}
        station = snapshot.get("station") or {}
        flight = snapshot.get("flight") or {}
        biology = snapshot.get("biology") or {}
        session = snapshot.get("session") or {}
        current_system = nav.get("current_system")
        candidates = []
        key_text = str(key or "")
        if key_text.startswith("advisor:"):
            return []

        destination = raw.get("DestinationSystem") or raw.get("destination_system")
        destination_station = raw.get("DestinationStation") or raw.get("destination_station")
        if event == "MissionAccepted" and destination:
            templates = [f"Mission logged for {destination}."]
            if destination_station:
                templates.extend((
                    f"Mission logged for {destination}, with the objective at {destination_station}.",
                    f"Objective recorded: {destination_station} in {destination}.",
                ))
            candidates.append(self._candidate(
                "mission-log", 76, "A new mission destination should be retained.",
                templates, ("mission", "progress"), outcome="mission",
            ))

        services = " ".join(str(item).casefold() for item in station.get("services") or [])
        exploration = int(objectives.get("unsold_exploration_cr") or 0)
        bio_value = int(objectives.get("unsold_biology_cr") or 0)
        station_name = station.get("name")
        if event == "Docked" and bio_value and "vista" in services:
            at = f" at {station_name}" if station_name else ""
            candidates.append(self._candidate(
                "sell-biology", 88, "Unsold biological data can be acted on at this station.",
                (
                    f"Vista Genomics is available{at} for our {bio_value:,} credits of biological data.",
                    f"We can secure {bio_value:,} credits of biological data through Vista Genomics{at}.",
                ), ("biology", "data", "goal"), outcome="sell-biology",
            ))
        if event == "Docked" and exploration and "cartograph" in services:
            at = f" at {station_name}" if station_name else ""
            candidates.append(self._candidate(
                "sell-exploration", 86, "Unsold exploration data can be acted on at this station.",
                (
                    f"Universal Cartographics is available{at} for our {exploration:,} credits of exploration data.",
                    f"We can secure {exploration:,} credits of exploration data through Universal Cartographics{at}.",
                ), ("survey", "data", "goal"), outcome="sell-exploration",
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
        if event == "MiningRefined" and cargo_percent is not None and int(cargo_percent) >= 80:
            candidates.append(self._candidate(
                f"mining-cargo-{95 if int(cargo_percent) >= 95 else 80}", 72,
                "The mining hold has crossed a useful capacity threshold.",
                (
                    f"Mining hold is {int(cargo_percent)} percent full at {flight.get('cargo_t')} of {flight.get('cargo_capacity_t')} tonnes.",
                    f"Cargo threshold reached: {int(cargo_percent)} percent of the mining hold is occupied.",
                ), ("cargo", "progress", "mining"), outcome="cargo",
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
                ), ("route", "goal", "progress"), outcome="route", category="navigation",
            ))
        unresolved = max(0, int(survey.get("total_bodies") or 0) - int(survey.get("scanned_bodies") or 0))
        if unresolved and key_text.startswith(("system-arrival:", "first-discovery:", "cockpit-context:")):
            candidates.append(self._candidate(
                "survey-progress", 61,
                "The current system survey still contains unresolved bodies.",
                (
                    f"The survey record still has {unresolved} bod{'ies' if unresolved != 1 else 'y'} unresolved.",
                    f"System survey remains incomplete with {unresolved} bod{'ies' if unresolved != 1 else 'y'} outstanding.",
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
                ), ("biology", "goal", "survey"), outcome="biology", category="exploration",
            ))
        if biology.get("species") and int(biology.get("progress") or 0) and key_text.startswith("cockpit-context:"):
            candidates.append(self._candidate(
                "active-biology", 74,
                "An active biological analysis remains unfinished.",
                (
                    f"The active {biology.get('species')} analysis is at sample {int(biology.get('progress'))} of 3.",
                    f"Sampling remains active for {biology.get('species')}: {int(biology.get('progress'))} of 3 complete.",
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
                ), ("data", "goal", "risk"), category="objectives",
            ))
        if cargo_percent is not None and int(cargo_percent) >= 80 and key_text.startswith(("cockpit-context:", "engineering-ready:", "massacre-complete:")):
            candidates.append(self._candidate(
                "cargo-capacity", 60,
                "Cargo capacity may affect the next planned activity.",
                (
                    f"The cargo hold is {int(cargo_percent)} percent full.",
                    f"Cargo capacity is currently at {int(cargo_percent)} percent.",
                ), ("cargo", "goal"), outcome="cargo",
            ))
        if key_text.startswith("engineering-ready:"):
            candidates.append(self._candidate(
                "engineering-ready", 66,
                "A pinned engineering objective has become actionable.",
                (
                    "This pinned engineering objective is now actionable.",
                    "The current material plan is ready to move into engineering.",
                ), ("engineering", "goal", "progress"), outcome="engineering",
            ))
        if event in ("FSDJump", "Location"):
            memory_row = self._memory_candidate(memory, current_system)
            if memory_row:
                candidates.append(memory_row)
        candidates.extend(self._anomaly_candidates(snapshot, memory, event))
        return candidates

    def _score(self, state, candidate, persona, mood, existing=False, voice_stage=None):
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
        previous = ((state.get("topic_stats") or {}).get(topic) or {}).get("last_template")
        available = [index for index in range(len(templates)) if index != previous] or list(range(len(templates)))
        index = random.choice(available)
        state["topic_stats"][topic]["last_template"] = index
        line = str(templates[index]).strip()
        mood_name = str((mood or {}).get("name") or "calm").casefold()
        tags = set(candidate.get("tags") or ())
        if mood_name == "curious" and tags & {"survey", "biology", "anomaly"}:
            line = f"{line.rstrip('.')} — worth a closer look."
        elif mood_name == "proud" and tags & {"progress", "milestone"}:
            line = f"{line.rstrip('.')} — solid progress."
        return line

    def select(self, event, raw, snapshot, memory=None, key=None, existing=False):
        """Return the highest-utility verified observation, or ``None``."""
        if not self.enabled or not self.config.get("cockpit_advisor_enabled", True):
            return None
        state = self._state()
        candidates = self._candidates(str(event or ""), raw, snapshot, memory, key=key)
        if not candidates:
            return None
        details = memory.status_details() if memory else {}
        mood = details.get("mood") or {}
        voice_stage = details.get("voice_stage") or (
            memory.voice_stage(self.config.get("cockpit_personality_level", "Balanced"))
            if memory else "new"
        )
        persona = self.config.get("cockpit_persona", "Compass")
        for candidate in candidates:
            self._score(
                state, candidate, persona, mood,
                existing=existing, voice_stage=voice_stage,
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
            f"produced utility {selected['score']:.1f}, clearing {threshold}."
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
        }
