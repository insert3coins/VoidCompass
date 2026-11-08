"""When the crew may offer an order (5.7.7). Never a nag: a new commander
gets one offer a session; "Often" allows one an hour. Never in a fight, a
menu or the seconds around a jump, and never in the first minutes of a
session."""

from __future__ import annotations

FREQUENCIES = {
    "off": None,
    "session": {"per_session": 1, "gap": 1800.0, "label": "Once a session"},
    "sometimes": {"per_session": 3, "gap": 2 * 3600.0, "label": "Now and then (every two hours at most)"},
    "often": {"per_session": 8, "gap": 3600.0, "label": "Often (every hour at most)"},
}
DEFAULT_FREQUENCY = "session"
SETTLE_S = 5 * 60.0          # into a session before the first offer
AFTER_JUMP_S = 25.0          # after arriving somewhere
AFTER_THOUGHT_S = 20.0       # after the companion last spoke
CAMPAIGN_GAP_S = 3 * 3600.0  # a new campaign isn't offered within this long of the last one ending


def frequency(config):
    value = str((config or {}).get("orders_frequency") or DEFAULT_FREQUENCY).casefold()
    return value if value in FREQUENCIES else DEFAULT_FREQUENCY


def may_offer(facts, offers, now, config, session):
    """(True, "") or (False, why not). facts: session_start, in_danger,
    jumping, gui_focus, arrived_at, last_spoke, offered_open (orders on the
    board right now)."""
    if not (config or {}).get("orders_enabled", True):
        return False, "Crew orders are off"
    setting = FREQUENCIES.get(frequency(config))
    if setting is None:
        return False, "Offers are off"
    started = facts.get("session_start")
    if not started:
        return False, "Waiting for the game"
    if now - float(started) < SETTLE_S:
        return False, "Settling in"
    if facts.get("in_danger"):
        return False, "Not in a fight"
    if facts.get("jumping"):
        return False, "Not mid-jump"
    if facts.get("gui_focus"):
        return False, "Not while a panel or map is open"
    if now - float(facts.get("arrived_at") or 0) < AFTER_JUMP_S:
        return False, "Just arrived"
    if now - float(facts.get("last_spoke") or 0) < AFTER_THOUGHT_S:
        return False, "Someone's talking"
    if facts.get("offered_open"):
        return False, "An offer is waiting for your answer"
    same_session = offers.get("session") == session
    if same_session and int(offers.get("count") or 0) >= setting["per_session"]:
        return False, "That's this session's offer"
    last = float(offers.get("last") or 0)
    if now - last < setting["gap"]:
        return False, f"Next offer after {int((setting['gap'] - (now - last)) // 60) + 1} min"
    return True, ""
