"""Compact persisted working state for the Compass cockpit intelligence.

The autobiographical memory remains the source of truth. This module keeps a
small current view for the deterministic adviser, persona and settings UI.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import threading

from compass_personas import DEFAULT_PERSONA, persona_profile


BRAIN_SCHEMA_VERSION = 3
MAX_RELEVANT_MEMORIES = 8


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compact_memory(row):
    return {
        "id": row.get("id"),
        "type": row.get("type"),
        "text": row.get("text"),
        "system": row.get("system"),
        "salience": int(row.get("salience") or 0),
        "timestamp": row.get("timestamp"),
        "pinned": bool(row.get("pinned")),
    }


class CockpitBrain:
    """Atomic, per-commander working-brain snapshot and decision history."""

    def __init__(self, path):
        self.path = str(path)
        self._lock = threading.RLock()
        self.state = self._load()

    def _empty(self):
        return {
            "schema": BRAIN_SCHEMA_VERSION,
            "updated_at": _now(),
            "identity": {
                "name": "Compass",
                "role": "local Elite Dangerous cockpit intelligence",
                "principles": [
                    "Use only verified journal, application, and memory facts",
                    "Prefer useful quiet over repetitive chatter",
                    "Never ask questions and never address the pilot as commander",
                    "Urgent safety speech is owned by deterministic systems",
                ],
            },
            "pilot_model": {},
            "experience": {},
            "working_memory": {},
            "cognition": {},
        }

    def _load(self):
        state = self._empty()
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                saved = json.load(handle)
            if isinstance(saved, dict):
                for key in ("identity", "pilot_model", "experience", "working_memory", "cognition"):
                    if isinstance(saved.get(key), dict):
                        state[key] = saved[key]
                state["updated_at"] = saved.get("updated_at") or state["updated_at"]
        except (OSError, TypeError, ValueError):
            pass
        return state

    def switch(self, path):
        with self._lock:
            self.path = str(path)
            self.state = self._load()

    def _save(self):
        folder = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(folder, exist_ok=True)
        temporary = self.path + ".tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(self.state, handle, indent=2, ensure_ascii=False)
            os.replace(temporary, self.path)
        except OSError:
            try:
                os.remove(temporary)
            except OSError:
                pass

    @staticmethod
    def _session_view(memory):
        session = memory.state.get("current_session")
        if not isinstance(session, dict):
            return None
        baseline = session.get("baseline") if isinstance(session.get("baseline"), dict) else {}
        delta = {}
        for key, value in memory.state.get("counters", {}).items():
            try:
                change = int(value or 0) - int(baseline.get(key) or 0)
            except (TypeError, ValueError):
                continue
            if change:
                delta[str(key)] = change
        return {
            "id": session.get("id"),
            "started_at": session.get("started_at"),
            "start_system": session.get("start_system"),
            "ship": session.get("ship"),
            "distance_ly": session.get("distance_ly"),
            "recent_systems": list(session.get("recent_systems") or [])[-8:],
            "activity_delta": delta,
        }

    @staticmethod
    def _relevant_memories(memory, current_system=None):
        selected = []
        seen = set()

        def add(row):
            memory_id = row.get("id")
            marker = memory_id or (row.get("timestamp"), row.get("text"))
            if marker in seen or not row.get("text"):
                return
            seen.add(marker)
            selected.append(_compact_memory(row))

        rows = memory.memory_rows()
        if current_system:
            for row in memory.memories_for_system(current_system, limit=3):
                add(row)
            # System-neutral pinned memories may express a user-curated ongoing
            # relationship fact.  Memories tied to somewhere else are not
            # relevant to the current callout and stay in the long-term file.
            for row in rows:
                if row.get("pinned") and not row.get("system"):
                    add(row)
        else:
            for row in rows:
                if row.get("pinned"):
                    add(row)
            for row in rows:
                add(row)
                if len(selected) >= MAX_RELEVANT_MEMORIES:
                    break
        return selected[:MAX_RELEVANT_MEMORIES]

    def update(self, memory, gameplay=None, purpose=None, event=None,
               personality_level="Balanced", persona_name=DEFAULT_PERSONA):
        """Rebuild and persist the compact working state from verified inputs."""
        if memory is None:
            return {}
        gameplay = gameplay if isinstance(gameplay, dict) else {}
        details = memory.status_details()
        mood = details.get("mood") or {}
        current_system = (
            (gameplay.get("navigation") or {}).get("current_system")
            or memory.state.get("current_system")
        )
        with self._lock:
            self.state.update({
                "schema": BRAIN_SCHEMA_VERSION,
                "updated_at": _now(),
                "pilot_model": {
                    "persona": persona_profile(persona_name),
                    "relationship": details.get("relationship"),
                    "relationship_score": memory.relationship_score(),
                    "voice_stage": memory.voice_stage(personality_level),
                    "traits": list(details.get("traits") or []),
                    "habits": list(details.get("habits") or []),
                    "intentions": dict(details.get("intentions") or {}),
                    "mood": {
                        "name": mood.get("name", "calm"),
                        "intensity": mood.get("intensity", 0.2),
                        "reason": mood.get("reason", "systems nominal"),
                    },
                },
                "experience": {
                    "summary": memory.summary(),
                    "gameplay_awareness": memory.gameplay_awareness(),
                    "biology_awareness": memory.biology_awareness(),
                    "favorite_ship": details.get("favorite_ship"),
                    "most_visited_system": details.get("most_visited_system"),
                    "completed_sessions": int(details.get("sessions") or 0),
                    "completed_expeditions": int(details.get("completed_expeditions") or 0),
                },
                "working_memory": {
                    "purpose": purpose,
                    "last_event": event,
                    "current_system": current_system,
                    "session": self._session_view(memory),
                    "active_expedition": details.get("active_expedition"),
                    "relevant_memories": self._relevant_memories(memory, current_system),
                    "verified_gameplay": gameplay,
                },
            })
            self._save()
            return json.loads(json.dumps(self.state, ensure_ascii=False, default=str))

    def cognition_state(self):
        """Return an isolated copy of the bounded adaptive cognition state."""
        with self._lock:
            value = self.state.get("cognition")
            return json.loads(json.dumps(value if isinstance(value, dict) else {}))

    def set_cognition_state(self, value, save=False):
        """Replace cognition state without exposing the brain's internal lock."""
        with self._lock:
            self.state["cognition"] = json.loads(json.dumps(
                value if isinstance(value, dict) else {},
                ensure_ascii=False,
                default=str,
            ))
            self.state["updated_at"] = _now()
            if save:
                self._save()
            return self.cognition_state()

    def status(self):
        with self._lock:
            return {
                "path": self.path,
                "updated_at": self.state.get("updated_at"),
                "persona": (
                    (self.state.get("pilot_model") or {}).get("persona") or {}
                ).get("name", DEFAULT_PERSONA),
            }
