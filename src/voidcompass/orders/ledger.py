"""Each commander's orders, kept per profile (5.7.7).

One reader for live play and the catch-up after a restart: an event counts
for an order only if it came after the order was accepted, and each event
counts once (events are keyed by time, name and content). The ledger also
keeps each officer's record with you, what you've turned down, and the
ribbons you've earned.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
import uuid
import zlib
from datetime import datetime, timezone

from voidcompass.core.persistence_queue import persistence_queue
from voidcompass.orders import objectives as objective_rules

SCHEMA = 1
OFFER_TTL_S = 20 * 60            # an offer nobody answered is let go
LATER_TTL_S = 24 * 3600          # "later" keeps it on the board this long
FIELD_TTL_S = 14 * 86400         # a field order lapses after two weeks
DECLINE_WINDOW_S = 30 * 86400    # two declines of a kind in this long: stop offering it
REOFFER_REST_S = 30 * 86400      # a declined target isn't offered again for this long
MAX_ACTIVE_FIELD = 3
EVENT_MEMORY = 3000
HISTORY_LIMIT = 400
OPEN = ("offered", "active")
SPEAKERS = ("watcher", "aster", "axiom", "meridian", "lyra")

# How far each officer trusts you, by orders done for them.
STANDINGS = ((0, "New to the watch"), (3, "Trusted"), (8, "Proven"), (15, "Right hand"), (30, "Indispensable"))


def epoch(stamp, default=None):
    """A journal timestamp as seconds."""
    if isinstance(stamp, (int, float)):
        return float(stamp)
    try:
        return datetime.strptime(str(stamp), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return default


def event_key(raw):
    try:
        body = json.dumps(raw, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        body = repr(raw)
    return f"{raw.get('timestamp')}|{raw.get('event')}|{zlib.crc32(body.encode('utf-8')):08x}"


def standing(done):
    label = STANDINGS[0][1]
    for threshold, name in STANDINGS:
        if done >= threshold:
            label = name
    return label


def service_level(done):
    """How many standings past the first: 0 (New to the watch) to 4 (Indispensable)."""
    return sum(1 for threshold, _name in STANDINGS[1:] if done >= threshold)


def objectives_of(order):
    """The objectives in play now: a campaign's current stage, or the order's own."""
    stages = order.get("stages")
    if stages:
        index = int(order.get("stage") or 0)
        if 0 <= index < len(stages):
            return stages[index].setdefault("objectives", [])
        return []
    return order.setdefault("objectives", [])


def progress(order):
    """0..1 over the whole order (a campaign counts its stages)."""
    rows = objectives_of(order)
    here = sum(objective_rules.fraction(row) for row in rows) / len(rows) if rows else 0.0
    stages = order.get("stages")
    if stages:
        return min(1.0, (int(order.get("stage") or 0) + here) / len(stages))
    return here


def current_target(order):
    """Where the order sends you now: the next unfinished objective's own
    place when it has one elsewhere, otherwise the order's target."""
    target = dict(order.get("target") or {})
    for row in objectives_of(order):
        if not objective_rules.done(row):
            place = objective_rules.place_of(row)
            if place and place.get("body") != target.get("body"):
                return place
            break
    return target


def _fresh():
    return {"schema": SCHEMA, "orders": [], "history": [], "record": {}, "declines": {}, "muted": {},
            "keys": {}, "ribbons": {}, "events": [], "offers": {"session": None, "count": 0, "last": 0.0},
            "lines": {}, "files": {}, "after": {}}


class OrderLedger:
    def __init__(self, path, clock=time.time):
        self.path = path
        self.clock = clock
        self.lock = threading.RLock()
        self.data = _fresh()
        self._events = set()
        self.load()

    # -- storage -----------------------------------------------------------
    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except FileNotFoundError:
            return
        except (OSError, ValueError) as exc:
            logging.warning("Crew orders unreadable (%s); starting a fresh ledger", exc)
            return
        if not isinstance(loaded, dict):
            return
        data = _fresh()
        for key, value in loaded.items():
            if key in data and isinstance(value, type(data[key])):
                data[key] = value
        self.data = data
        self._events = set(data["events"])

    def save(self, immediate=False):
        with self.lock:
            snapshot = copy.deepcopy(self.data)
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            persistence_queue().submit_json(self.path, snapshot, indent=None, delay_s=0.0 if immediate else 2.0)
        except Exception:
            logging.debug("Crew orders not saved", exc_info=True)

    def flush(self):
        self.save(immediate=True)
        try:
            persistence_queue().flush(self.path)
        except Exception:
            pass

    # -- lookups -----------------------------------------------------------
    def get(self, order_id):
        with self.lock:
            return next((row for row in self.data["orders"] if row.get("id") == order_id), None)

    def orders(self, *statuses):
        with self.lock:
            return [row for row in self.data["orders"] if not statuses or row.get("status") in statuses]

    def offered(self):
        return self.orders("offered")

    def active(self):
        return self.orders("active")

    def active_field(self):
        return [row for row in self.active() if row.get("size", "field") == "field"]

    def campaign(self):
        return next((row for row in self.active() if row.get("size") == "campaign"), None)

    def long_order(self):
        return next((row for row in self.active() if row.get("size") == "long"), None)

    def history(self, limit=60):
        with self.lock:
            return list(reversed(self.data["history"][-limit:]))

    def record(self, officer):
        with self.lock:
            row = self.data["record"].setdefault(officer, {})
            for key in ("done", "campaigns", "declined", "abandoned", "long"):
                row.setdefault(key, 0)
            row.setdefault("kinds", {})
            return row

    def is_muted(self, officer, kind):
        with self.lock:
            return f"{officer}:{kind}" in self.data["muted"]

    def may_offer_key(self, key, now=None, repeatable=False):
        """False for a target that's open now, done (unless repeatable), or
        turned down in the last month."""
        if not key:
            return True
        now = self.clock() if now is None else now
        with self.lock:
            seen = self.data["keys"].get(key)
        if not seen:
            return True
        status, at = seen.get("status"), float(seen.get("at") or 0)
        if status in OPEN:
            return False
        if status == "done":
            return repeatable and now - at > REOFFER_REST_S
        return now - at > REOFFER_REST_S

    # -- the life of an order ----------------------------------------------
    def _mark_key(self, order, status, now):
        key = order.get("key")
        if key:
            self.data["keys"][key] = {"status": status, "at": now}
            if len(self.data["keys"]) > 2000:
                for old in sorted(self.data["keys"], key=lambda k: self.data["keys"][k].get("at", 0))[:200]:
                    self.data["keys"].pop(old, None)

    def offer(self, draft, now=None, session=None):
        """A draft from a generator becomes an order on the board."""
        now = self.clock() if now is None else now
        order = copy.deepcopy(draft)
        order.setdefault("size", "field")
        order.update(id=f"o-{uuid.uuid4().hex[:10]}", status="offered", offered_at=now, expires_at=now + OFFER_TTL_S)
        if order.get("stages"):
            order["stage"] = 0
        with self.lock:
            self.data["orders"].append(order)
            self._mark_key(order, "offered", now)
            offers = self.data["offers"]
            if session is not None and offers.get("session") != session:
                offers.update(session=session, count=0)
            offers["count"] = int(offers.get("count") or 0) + 1
            offers["last"] = now
        self.save()
        return order

    def accept(self, order_id, now=None):
        now = self.clock() if now is None else now
        with self.lock:
            order = self.get(order_id)
            if order is None or order.get("status") != "offered":
                return None
            if order.get("size", "field") == "field" and len(self.active_field()) >= MAX_ACTIVE_FIELD:
                return {"error": "full", "order": order}
            if order.get("size") in {"campaign", "long"} and any(
                    row.get("size") == order.get("size") for row in self.active()):
                return {"error": "busy", "order": order}
            order.update(status="active", accepted_at=now)
            order.pop("later", None)
            order["expires_at"] = now + FIELD_TTL_S if order.get("size", "field") == "field" else None
            self.data["declines"].pop(f"{order.get('officer')}:{order.get('kind')}", None)
            self._mark_key(order, "active", now)
        self.save()
        return {"order": order}

    def decline(self, order_id, now=None):
        """Turned down. A second refusal of the same kind within a month mutes it."""
        now = self.clock() if now is None else now
        with self.lock:
            order = self.get(order_id)
            if order is None or order.get("status") != "offered":
                return None
            self._close(order, "declined", now)
            officer, kind = order.get("officer"), order.get("kind")
            self.record(officer)["declined"] += 1
            stamps = [at for at in self.data["declines"].get(f"{officer}:{kind}", []) if now - at < DECLINE_WINDOW_S]
            stamps.append(now)
            self.data["declines"][f"{officer}:{kind}"] = stamps[-4:]
            muted = len(stamps) >= 2 and order.get("size", "field") == "field"
            if muted:
                self.data["muted"][f"{officer}:{kind}"] = now
        self.save()
        return {"order": order, "muted": muted}

    def later(self, order_id, now=None):
        now = self.clock() if now is None else now
        with self.lock:
            order = self.get(order_id)
            if order is None or order.get("status") != "offered":
                return None
            order["later"] = True
            order["expires_at"] = now + LATER_TTL_S
        self.save()
        return {"order": order}

    def abandon(self, order_id, now=None):
        now = self.clock() if now is None else now
        with self.lock:
            order = self.get(order_id)
            if order is None or order.get("status") != "active":
                return None
            self._close(order, "abandoned", now)
            self.record(order.get("officer"))["abandoned"] += 1
        self.save()
        return {"order": order}

    def unmute(self, officer=None):
        with self.lock:
            if officer:
                for key in [key for key in self.data["muted"] if key.startswith(f"{officer}:")]:
                    self.data["muted"].pop(key, None)
            else:
                self.data["muted"].clear()
            self.data["declines"].clear()
        self.save()

    def _close(self, order, status, now):
        order.update(status=status, closed_at=now)
        self._mark_key(order, "done" if status == "done" else status, now)
        self.data["orders"] = [row for row in self.data["orders"] if row is not order]
        entry = {key: order.get(key) for key in ("id", "kind", "size", "officer", "title", "brief", "target", "status",
                                                 "offered_at", "accepted_at", "closed_at", "reward", "campaign")}
        entry["objectives"] = [objective_rules.describe(row) for row in objectives_of(order)]
        if order.get("stages"):
            entry["stages"] = [{"title": stage.get("title"), "officer": stage.get("officer"), "done_at": stage.get("done_at")}
                               for stage in order["stages"]]
        self.data["history"].append(entry)
        del self.data["history"][:-HISTORY_LIMIT]

    def _complete(self, order, now):
        self._close(order, "done", now)
        officers = {order.get("officer")}
        for stage in order.get("stages") or ():
            if stage.get("officer"):
                officers.add(stage["officer"])
        for officer in officers:
            if officer not in SPEAKERS:
                continue
            row = self.record(officer)
            row["done"] += 1
            row["kinds"][order.get("kind")] = int(row["kinds"].get(order.get("kind")) or 0) + 1
            row["last_done"] = now
            if order.get("size") == "campaign":
                row["campaigns"] += 1
            if order.get("size") == "long":
                row["long"] += 1

    # -- the journal ---------------------------------------------------------
    def observe(self, raw, ctx=None, now=None):
        """One journal event. Returns what changed, for the crew to talk about."""
        if not isinstance(raw, dict) or not raw.get("event"):
            return []
        now = self.clock() if now is None else now
        ctx = ctx or {}
        at = epoch(raw.get("timestamp"), now)
        key = event_key(raw)
        changes = []
        with self.lock:
            if key in self._events:
                return []
            active = self.active()
            if not active:
                return []
            self._remember_event(key)
            event = str(raw["event"])
            if event == "Died":
                return [{"type": "paused", "order": order} for order in active if progress(order) > 0][:1]
            for order in active:
                if at + 2 < float(order.get("accepted_at") or now):
                    continue
                # 5.7.7: someone else got there first (a first map, by the Scan's own word).
                lost = [row for row in objectives_of(order) if objective_rules.taken(row, event, raw)]
                if lost:
                    self._close(order, "overtaken", now)
                    changes.append({"type": "overtaken", "order": order, "body": raw.get("BodyName")})
                    continue
                changes.extend(self._advance(order, lambda row: objective_rules.advance(row, event, raw, ctx), now))
        if changes:
            self.save()
        return changes

    def _remember_event(self, key):
        self._events.add(key)
        events = self.data["events"]
        events.append(key)
        if len(events) > EVENT_MEMORY:
            for old in events[:-EVENT_MEMORY]:
                self._events.discard(old)
            del events[:-EVENT_MEMORY]

    def _advance(self, order, step, now):
        changes = []
        before = progress(order)
        rows = objectives_of(order)
        for row in rows:
            was_done = objective_rules.done(row)
            gain = step(row)
            if gain:
                changes.append({"type": "progress", "order": order, "objective": row, "gain": gain})
                if objective_rules.done(row) and not was_done and not all(objective_rules.done(other) for other in rows):
                    changes.append({"type": "step", "order": order, "objective": row})
        if rows and all(objective_rules.done(row) for row in rows):
            stages = order.get("stages")
            if stages and int(order.get("stage") or 0) < len(stages) - 1:
                stages[int(order["stage"])]["done_at"] = now
                order["stage"] = int(order["stage"]) + 1
                changes.append({"type": "stage", "order": order, "stage": order["stage"]})
            else:
                if stages:
                    stages[-1]["done_at"] = now
                self._complete(order, now)
                changes.append({"type": "done", "order": order})
                return changes
        after = progress(order)
        if before < .5 <= after < 1 and not order.get("halfway") and order.get("size", "field") != "campaign":
            order["halfway"] = now
            changes.append({"type": "halfway", "order": order})
        return changes

    def tick(self, ctx=None, now=None):
        """Offers that went unanswered, field orders that lapsed, and the
        objectives that need time."""
        now = self.clock() if now is None else now
        ctx = ctx or {}
        changes = []
        with self.lock:
            for order in list(self.data["orders"]):
                expires = order.get("expires_at")
                if expires and now > float(expires):
                    status = "expired" if order.get("status") == "offered" else "lapsed"
                    self._close(order, status, now)
                    changes.append({"type": status, "order": order})
                    continue
                if order.get("status") == "active" and any(row.get("type") == "stay" for row in objectives_of(order)):
                    changes.extend(self._advance(order, lambda row: objective_rules.settle(row, ctx, now), now))
        if changes:
            self.save()
        return changes

    def set_stage_objectives(self, order_id, objectives, extra=None):
        """A campaign's next stage, once its targets are known."""
        with self.lock:
            order = self.get(order_id)
            if order is None or not order.get("stages"):
                return None
            stage = order["stages"][int(order.get("stage") or 0)]
            stage["objectives"] = list(objectives)
            stage["built"] = True
            stage.update(extra or {})
        self.save()
        return order

    def choose(self, order_id, option, objectives):
        """A campaign stage that asks you to pick (The Fork)."""
        with self.lock:
            order = self.get(order_id)
            if order is None or order.get("status") != "active" or not order.get("stages"):
                return None
            stage = order["stages"][int(order.get("stage") or 0)]
            if not stage.get("choice") or stage.get("chosen"):
                return None
            stage.update(objectives=list(objectives), built=True, chosen=option, officer=option)
            order["choice"] = option
            if option in SPEAKERS:
                row = self.record(option)
                row["sided"] = int(row.get("sided") or 0) + 1
        self.save()
        return order

    def last_campaign_ended(self):
        with self.lock:
            ends = [float(row.get("closed_at") or 0) for row in self.data["history"] if row.get("size") == "campaign"]
        return max(ends) if ends else 0.0

    # -- ribbons and remembered wording --------------------------------------
    def award(self, ribbon_id, now=None):
        now = self.clock() if now is None else now
        with self.lock:
            if ribbon_id in self.data["ribbons"]:
                return False
            self.data["ribbons"][ribbon_id] = now
        self.save()
        return True

    def ribbons(self):
        with self.lock:
            return dict(self.data["ribbons"])

    def line_memory(self):
        """Which wordings have been used, so lines don't repeat (order_lines)."""
        with self.lock:
            return self.data["lines"]

    def unlock_file(self, officer, passage, now=None):
        now = self.clock() if now is None else now
        with self.lock:
            told = self.data["files"].setdefault(officer, {})
            if passage in told:
                return False
            told[passage] = now
        self.save()
        return True

    def files_told(self, officer):
        with self.lock:
            return dict(self.data["files"].get(officer) or {})

    # -- after the campaign (an unlock) ----------------------------------------
    def schedule_after(self, campaign, due):
        """A finished campaign's look back, told once a while later."""
        with self.lock:
            if campaign and campaign not in self.data["after"]:
                self.data["after"][campaign] = {"due": float(due), "told": None}
        self.save()

    def after_due(self, now=None):
        now = self.clock() if now is None else now
        with self.lock:
            due = [(row["due"], key) for key, row in self.data["after"].items() if not row.get("told") and now >= row["due"]]
        return min(due)[1] if due else None

    def after_told(self, campaign, now=None):
        now = self.clock() if now is None else now
        with self.lock:
            row = self.data["after"].get(campaign)
            if row is not None:
                row["told"] = now
        self.save()

    def after_scenes(self):
        with self.lock:
            return {key: dict(row) for key, row in self.data["after"].items() if row.get("told")}

    def offers(self):
        with self.lock:
            return dict(self.data["offers"])
