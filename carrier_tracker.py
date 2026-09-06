"""
carrier_tracker.py — Personal and squadron carrier state from Elite Dangerous journal events.
Implements the EDCM status state machine.
Discord webhooks use requests only — no discord.py dependency.
State is persisted to carrier_state.json so it survives app restarts.
"""
import json
import logging
import math
import os
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import quote_plus

from persistence_queue import persistence_queue
import themes

CARRIER_STATE_FILE = "carrier_state.json"

# Fields that are safe to persist (skip runtime callbacks etc.)
_PERSIST_KEYS = {
    "carrier_id", "carrier_type", "callsign", "name",
    "squadron_id", "squadron_name", "squadron_rank", "squadron_rank_name",
    "carrier_purchased_at", "carrier_spawn_system",
    "system", "system_address", "body",
    "fuel_level", "fuel_capacity", "fuel_level_estimated",
    "fuel_level_source", "fuel_level_updated_at",
    "jump_range_curr", "jump_range_max",
    "jump_destination", "jump_destination_address", "jump_body", "jump_departure_time",
    "previous_system", "previous_body",
    "docking_access", "allow_notorious", "pending_decom",
    "balance", "available_balance", "reserve_balance", "reserve_percent",
    "tax_rearm", "tax_refuel", "tax_repair",
    "space_total", "space_cargo", "space_crew", "space_free",
    "space_reserved", "space_ship_packs", "space_module_packs",
    "crew", "trade_orders", "jump_history", "stats_updated_at",
    "cargo_updated_at", "cargo_total_source",
    "expedition_name", "expedition_route", "expedition_reserve_fuel",
    "expedition_requested_destinations",
    "expedition_route_source", "expedition_spansh_job", "expedition_spansh_url",
    "expedition_plotted_at", "expedition_total_distance_ly",
    "expedition_used_capacity_t", "expedition_fuel_required_t",
    "expedition_starting_tank_t", "expedition_starting_market_tritium_t",
    "expedition_starting_load_t",
    "notes", "destination_note", "last_updated",
}

_COOLDOWN_SECS = 290  # 4m50s post-departure cooldown window

_DISCORD_EVENT_STYLES = {
    "jump_plotted":      ("JUMP PLOTTED", "accent"),
    "jump_completed":    ("JUMP COMPLETE", "green"),
    "jump_cancelled":    ("JUMP CANCELLED", "red"),
    "cooldown_finished": ("COOLDOWN COMPLETE", "yellow"),
    "status_update":     ("CARRIER STATUS", "orange"),
    "test":              ("WEBHOOK TEST", "accent"),
}

_DISCORD_SERVICE_NAMES = {
    "Commodities": "Commodity Market",
    "VoucherRedemption": "Redemption Office",
    "Exploration": "Universal Cartographics",
    "VistaGenomics": "Vista Genomics",
    "BlackMarket": "Secure Warehouse",
    "CarrierFuel": "Tritium Depot",
    "PioneerSupplies": "Pioneer Supplies",
}

CREW_ROLES = [
    "Captain", "Commodities", "Refuel", "Repair", "Rearm",
    "VoucherRedemption", "Exploration", "VistaGenomics",
    "Outfitting", "Shipyard", "BlackMarket", "CarrierFuel",
    "PioneerSupplies", "Bartender",
]


def _parse_dt(ts_str):
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


def _discord_time(ts_value):
    """Return full and relative Discord timestamp tokens."""
    try:
        if isinstance(ts_value, (int, float)):
            epoch = int(ts_value)
        else:
            dt = _parse_dt(ts_value)
            if not dt:
                return ""
            epoch = int(dt.timestamp())
        return f"<t:{epoch}:F> · <t:{epoch}:R>"
    except (TypeError, ValueError, OverflowError):
        return ""


def _discord_escape(value):
    """Escape Discord markdown in journal/user text; links are built separately."""
    text = str(value or "").replace("\r", "").replace("\x00", "").strip()
    for char in ("\\", "*", "_", "~", "`", "|", "[", "]", ">"):
        text = text.replace(char, f"\\{char}")
    return text


def _discord_clip(value, limit=1024):
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:max(0, limit - 1)].rstrip() + "…"


def _discord_error_detail(exc):
    """Describe a webhook failure without leaking its credential-bearing URL."""
    if isinstance(exc, RuntimeError):
        return str(exc)
    error_name = type(exc).__name__
    if "timeout" in error_name.casefold():
        return "Discord request timed out."
    if "connection" in error_name.casefold():
        return "Could not connect to Discord."
    return f"Discord webhook request failed ({error_name})."


def _edsm_system_url(system):
    system = " ".join(str(system or "").split())
    if not system or system.casefold() in {"unknown", "tbd"}:
        return ""
    return f"https://www.edsm.net/show-system?systemName={quote_plus(system)}"


def _discord_location(system, body=None, *, link=True):
    """Format an Elite system/body with a safe EDSM system link."""
    system = " ".join(str(system or "").split()) or "Unknown"
    body = " ".join(str(body or "").split())
    escaped_system = _discord_escape(system)
    url = _edsm_system_url(system)
    system_text = f"[{escaped_system}]({url})" if link and url else escaped_system
    if not body:
        return system_text
    suffix = body
    if body.casefold().startswith(system.casefold()):
        suffix = body[len(system):].strip()
    return system_text + (f" · {_discord_escape(suffix)}" if suffix else "")


def _discord_number(value, decimals=0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if decimals:
        return f"{number:,.{decimals}f}"
    return f"{int(round(number)):,}"


def _next_pending_route(cd):
    current = " ".join(str(cd.get("system") or "").split()).casefold()
    current_address = cd.get("system_address")
    for row in cd.get("expedition_route") or []:
        if not isinstance(row, dict) or row.get("visited"):
            continue
        system = " ".join(str(row.get("system") or "").split())
        if not system:
            continue
        same_address = (
            current_address is not None and row.get("id64") is not None
            and str(row.get("id64")) == str(current_address)
        )
        if same_address or (current and system.casefold() == current):
            continue
        return row
    return None


def _utc_stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class CarrierTracker:
    @staticmethod
    def _empty_carrier_data():
        return {
            "carrier_id": None,
            "carrier_type": None,
            "callsign": None,
            "name": None,
            "squadron_id": None,
            "squadron_name": None,
            "squadron_rank": None,
            "squadron_rank_name": None,
            "carrier_purchased_at": None,
            "carrier_spawn_system": None,
            "system": None,
            "system_address": None,
            "body": None,
            "status": "idle",          # idle | jumping | cooldown | cooldown_cancel
            "fuel_level": None,
            "fuel_capacity": 1000,
            "fuel_level_estimated": False,
            "fuel_level_source": None,
            "fuel_level_updated_at": None,
            "jump_range_curr": None,
            "jump_range_max": None,
            "jump_destination": None,
            "jump_destination_address": None,
            "jump_body": None,
            "jump_departure_time": None,
            "previous_system": None,
            "previous_body": None,
            "docking_access": "all",
            "allow_notorious": False,
            "pending_decom": False,
            "balance": None,
            "available_balance": None,
            "reserve_balance": None,
            "reserve_percent": None,
            "tax_rearm": None,
            "tax_refuel": None,
            "tax_repair": None,
            "space_total": None,
            "space_cargo": None,
            "space_crew": None,
            "space_free": None,
            "space_reserved": None,
            "space_ship_packs": None,
            "space_module_packs": None,
            "crew": [],
            "trade_orders": [],
            "jump_history": [],
            "stats_updated_at": None,
            "cargo_updated_at": None,
            "cargo_total_source": None,
            "expedition_name": "",
            "expedition_route": [],
            "expedition_reserve_fuel": 200,
            "expedition_requested_destinations": [],
            "expedition_route_source": "manual",
            "expedition_spansh_job": None,
            "expedition_spansh_url": None,
            "expedition_plotted_at": None,
            "expedition_total_distance_ly": None,
            "expedition_used_capacity_t": None,
            "expedition_fuel_required_t": None,
            "expedition_starting_tank_t": None,
            "expedition_starting_market_tritium_t": None,
            "expedition_starting_load_t": None,
            "notes": "",
            "destination_note": "",
            "last_updated": None,
        }

    def __init__(self):
        self.carrier_data = self._empty_carrier_data()
        self._carriers = {}
        self._active_carrier_key = None
        self._squadron_context = {}
        self._replaying_history = False
        self._profile_generation = 0
        self._profile_lock = threading.RLock()
        self._diagnostic_last = {}
        self._config = {}
        self.on_updated = None          # callback(carrier_data) — grabbed by CarrierWindow
        self.on_panel_updated = None    # callback(carrier_data) — persistent, used by dashboard panel
        self.on_status_changed = None   # callback(old, new, carrier_data)

    def set_config(self, config):
        with self._profile_lock:
            self._profile_generation += 1
            ticker = getattr(self, "_status_ticker", None)
            if ticker and ticker.is_alive():
                ticker.cancel()
            self._status_ticker = None
            self.carrier_data = self._empty_carrier_data()
            self._carriers = {}
            self._active_carrier_key = None
            self._squadron_context = {}
            self._config = config
            self.load_state()

    @staticmethod
    def _normalise_carrier_type(value):
        text = str(value or "").strip().casefold().replace("_", "")
        if "squadron" in text:
            return "SquadronCarrier"
        if text in {"fleet", "fleetcarrier", "drakeclasscarrier"}:
            return "FleetCarrier"
        return str(value or "").strip() or None

    @classmethod
    def _carrier_key(cls, carrier_id=None, carrier_type=None):
        if carrier_id is not None and str(carrier_id).strip():
            return f"id:{carrier_id}"
        normalised = cls._normalise_carrier_type(carrier_type)
        return f"type:{normalised}" if normalised else None

    def _register_carrier(self, data, *, make_active=False):
        """Add/merge one managed carrier and return its canonical record."""
        if not isinstance(data, dict):
            data = {}
        carrier_type = self._normalise_carrier_type(data.get("carrier_type"))
        carrier_id = data.get("carrier_id")
        key = self._carrier_key(carrier_id, carrier_type)
        if not key:
            return data

        existing = self._carriers.get(key)
        if existing is None and carrier_type:
            # CarrierLocation can establish a typed placeholder before the
            # later CarrierStats event supplies the permanent numeric ID.
            type_key = self._carrier_key(None, carrier_type)
            placeholder = self._carriers.get(type_key)
            if placeholder is not None:
                existing = placeholder
                if type_key != key:
                    self._carriers.pop(type_key, None)
                    if self._active_carrier_key == type_key:
                        self._active_carrier_key = key
        if existing is None:
            existing = self._empty_carrier_data()
        for field, value in data.items():
            if value is not None or field not in existing:
                existing[field] = deepcopy(value)
        existing["carrier_type"] = carrier_type or existing.get("carrier_type")
        existing.setdefault("_runtime_prev_status", existing.get("status", "idle"))
        existing.setdefault("_runtime_cancel_ts", None)
        for field, value in self._squadron_context.items():
            if value is not None and existing.get(field) is None:
                existing[field] = value
        self._carriers[key] = existing
        if make_active or self._active_carrier_key not in self._carriers:
            self._active_carrier_key = key
        self._restore_active_carrier()
        return existing

    def _restore_active_carrier(self):
        record = self._carriers.get(self._active_carrier_key)
        if record is None and self._carriers:
            # A personal carrier remains the least surprising default when
            # both personal and Squadron carriers have been observed.
            choice = next((
                (key, row) for key, row in self._carriers.items()
                if row.get("carrier_type") == "FleetCarrier"
            ), next(iter(self._carriers.items())))
            self._active_carrier_key, record = choice
        self.carrier_data = record if record is not None else self._empty_carrier_data()
        return self.carrier_data

    def carriers(self):
        """Return independent managed-carrier snapshots in stable UI order."""
        with self._profile_lock:
            rows = [deepcopy(row) for row in self._carriers.values()]
        return sorted(rows, key=lambda row: (
            row.get("carrier_type") == "SquadronCarrier",
            str(row.get("name") or row.get("callsign") or "").casefold(),
        ))

    def carrier_for_id(self, carrier_id):
        key = self._carrier_key(carrier_id)
        with self._profile_lock:
            return self._carriers.get(key)

    def display_carrier(self):
        """Return the carrier whose live operation deserves overlay priority."""
        with self._profile_lock:
            priority = {"jumping": 0, "cooldown_cancel": 1, "cooldown": 2}
            active = [
                row for row in self._carriers.values()
                if row.get("status") in priority
            ]
            if active:
                active.sort(key=lambda row: (
                    priority.get(row.get("status"), 9),
                    str(row.get("jump_departure_time") or row.get("last_updated") or ""),
                ))
                return active[0]
            return self.carrier_data

    def set_active_carrier(self, carrier_id):
        key = self._carrier_key(carrier_id)
        with self._profile_lock:
            if key not in self._carriers:
                return False
            if key == self._active_carrier_key and self.carrier_data is self._carriers[key]:
                return True
            self._active_carrier_key = key
            self.carrier_data = self._carriers[key]
            self.save_state()
            snapshot = self.carrier_data
        if callable(self.on_updated):
            self.on_updated(snapshot)
        if callable(self.on_panel_updated):
            self.on_panel_updated(snapshot)
        return True

    def _event_carrier(self, raw, *, create=False):
        # Preserve the original public ``carrier_data`` contract for callers
        # and older state/tests that seed that dictionary directly.
        if not self._carriers and (
            self.carrier_data.get("carrier_id") is not None
            or self.carrier_data.get("carrier_type")
        ):
            self._register_carrier(self.carrier_data, make_active=True)
        carrier_id = raw.get("CarrierID")
        if carrier_id is None and raw.get("event") == "CarrierJump":
            carrier_id = raw.get("MarketID")
        carrier_type = self._normalise_carrier_type(raw.get("CarrierType"))
        key = self._carrier_key(carrier_id, carrier_type)
        record = self._carriers.get(key) if key else None
        if record is None and carrier_id is not None:
            record = next((
                row for row in self._carriers.values()
                if row.get("carrier_id") is not None
                and str(row.get("carrier_id")) == str(carrier_id)
            ), None)
        if record is None and carrier_type:
            record = next((
                row for row in self._carriers.values()
                if row.get("carrier_type") == carrier_type
                and (carrier_id is None or row.get("carrier_id") is None)
            ), None)
        if record is None and not create:
            return None
        if record is None:
            record = self._empty_carrier_data()
        if carrier_id is not None:
            record["carrier_id"] = carrier_id
        if carrier_type:
            record["carrier_type"] = carrier_type
        return self._register_carrier(record)

    def scan_journal_history(self, journal_path, max_files=10, commander=None, fid=None):
        """
        Catch up every managed carrier independently from recent journals.

        The game can emit personal Fleet Carrier and Squadron Carrier records
        in the same session. Replaying them chronologically preserves both
        identities, while each record's last-updated watermark prevents an
        older startup event from rewinding persisted state.
        """
        generation = self._profile_generation
        if not journal_path or not os.path.exists(journal_path):
            return
        try:
            files = sorted([
                os.path.join(journal_path, f)
                for f in os.listdir(journal_path)
                if f.startswith("Journal.") and f.endswith(".log")
            ])
        except Exception:
            return

        recent = files[-max_files:]
        replay = []
        expected_name = str(commander or "").strip().casefold()
        expected_fid = str(fid or "").strip().casefold()

        for filepath in recent:
            active_commander = not bool(expected_name or expected_fid)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            raw = json.loads(line)
                        except Exception:
                            continue
                        ev = raw.get("event")
                        if not ev:
                            continue
                        if ev in ("Commander", "LoadGame"):
                            actual_name = str(
                                raw.get("Commander") or raw.get("Name") or ""
                            ).strip().casefold()
                            actual_fid = str(raw.get("FID") or "").strip().casefold()
                            active_commander = (
                                (not expected_name or actual_name == expected_name)
                                and (not expected_fid or not actual_fid or actual_fid == expected_fid)
                                and bool(actual_name or actual_fid)
                            )
                        if not active_commander:
                            continue
                        if ev.startswith("Carrier") or ev in {
                            "SquadronStartup", "SquadronCreated", "JoinedSquadron",
                            "SquadronPromotion", "SquadronDemotion", "LeftSquadron",
                            "KickedFromSquadron", "DisbandedSquadron",
                        }:
                            replay.append(raw)
            except Exception:
                continue

        if generation != self._profile_generation:
            return
        if not replay:
            return

        with self._profile_lock:
            if generation != self._profile_generation:
                return
            callbacks = (
                self.on_updated, self.on_panel_updated, self.on_status_changed,
            )
            self.on_updated = None
            self.on_panel_updated = None
            self.on_status_changed = None
            self._replaying_history = True
            try:
                for raw in replay:
                    self._process_event_unlocked(raw)
            finally:
                self._replaying_history = False
                self.on_updated, self.on_panel_updated, self.on_status_changed = callbacks

            self._restore_active_carrier()
            self.save_state()
        logging.info(
            "CarrierTracker: history scan complete — %d managed carrier(s)",
            len(self._carriers),
        )
        self._ensure_status_ticker()
        if callable(self.on_updated):
            self.on_updated(self.carrier_data)
        if callable(self.on_panel_updated):
            self.on_panel_updated(self.carrier_data)

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _state_path(self):
        return os.path.abspath(
            self._config.get("carrier_state_file", CARRIER_STATE_FILE)
        )

    def save_state(self, immediate=False):
        # Journal events arrive on the Tk thread, so writing the file here
        # blocked the interface; the shared queue coalesces repeat saves.
        try:
            carriers = [
                {k: deepcopy(v) for k, v in row.items() if k in _PERSIST_KEYS}
                for row in self._carriers.values()
                if row.get("carrier_id") is not None or row.get("carrier_type")
            ]
            data = {
                "schema_version": 2,
                "active_carrier_key": self._active_carrier_key,
                "carriers": carriers,
            }
            persistence_queue().submit_json(
                self._state_path(), data, indent=2,
                delay_s=1.0, immediate=immediate,
            )
        except Exception as exc:
            logging.warning(f"CarrierTracker: could not save state: {exc}")

    def load_state(self):
        path = self._state_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            records = saved.get("carriers") if isinstance(saved, dict) else None
            if not isinstance(records, list):
                # Seamless migration from the original single-carrier file.
                records = [saved] if isinstance(saved, dict) else []
            route_repaired = False
            for saved_row in records:
                if not isinstance(saved_row, dict):
                    continue
                row = self._empty_carrier_data()
                for key in _PERSIST_KEYS:
                    if key in saved_row:
                        row[key] = deepcopy(saved_row[key])
                if not row.get("carrier_id") and not row.get("carrier_type"):
                    continue
                row = self._register_carrier(row)
                self.carrier_data = row
                route_repaired = bool(self._repair_current_expedition_stop(
                    row.get("system"), row.get("last_updated"),
                    row.get("system_address"),
                )) or route_repaired
                self._update_status()
                row["_runtime_prev_status"] = row["status"]
            requested_active = saved.get("active_carrier_key") if isinstance(saved, dict) else None
            if requested_active in self._carriers:
                self._active_carrier_key = requested_active
            self._restore_active_carrier()
            logging.info(
                "CarrierTracker: loaded %d managed carrier(s); active %s @ %s",
                len(self._carriers),
                self.carrier_data.get("name") or "unknown carrier",
                self.carrier_data.get("system") or "?",
            )
            self._ensure_status_ticker()
            if route_repaired:
                self.save_state()
        except Exception as exc:
            logging.warning(f"CarrierTracker: could not load state: {exc}")

    def process_event(self, raw):
        with self._profile_lock:
            return self._process_event_unlocked(raw)

    def _process_event_unlocked(self, raw):
        ev = raw.get("event") if isinstance(raw, dict) else None
        if not ev:
            return

        squadron_events = {
            "SquadronStartup", "SquadronCreated", "JoinedSquadron",
            "SquadronPromotion", "SquadronDemotion", "LeftSquadron",
            "KickedFromSquadron", "DisbandedSquadron",
        }
        if ev in squadron_events:
            changed = self._apply_squadron_event(raw)
            if changed:
                self.save_state()
                if callable(self.on_panel_updated):
                    self.on_panel_updated(self.carrier_data)
            return

        if not ev.startswith("Carrier"):
            return

        # CarrierJump can describe a carrier merely carrying the commander,
        # and CarrierDepositFuel can be a donation to somebody else's carrier.
        # Only identity-bearing owner events may create a managed record.
        create = ev in {"CarrierStats", "CarrierBuy", "CarrierLocation"}
        record = self._event_carrier(raw, create=create)
        if record is None:
            return

        event_ts = _parse_dt(raw.get("timestamp"))
        known_ts = _parse_dt(record.get("last_updated"))
        if self._replaying_history and event_ts and known_ts and event_ts < known_ts:
            return
        selected_key = self._active_carrier_key
        self.carrier_data = record

        changed = False

        if ev == "CarrierStats":
            changed = self._handle_stats(raw)
        elif ev == "CarrierJumpRequest":
            changed = self._handle_jump_request(raw)
        elif ev == "CarrierJumpCancelled":
            changed = self._handle_jump_cancelled(raw)
        elif ev in ("CarrierLocation", "CarrierJump"):
            changed = self._handle_location(raw)
        elif ev == "CarrierTradeOrder":
            changed = self._handle_trade_order(raw)
        elif ev == "CarrierDepositFuel":
            total = raw.get("Total")
            if total is not None:
                changed = self._set_authoritative_fuel(
                    total, raw, "CarrierDepositFuel",
                )
        elif ev == "CarrierDockingPermission":
            self.carrier_data["docking_access"] = raw.get("DockingAccess", "all")
            self.carrier_data["allow_notorious"] = bool(raw.get("AllowNotorious", False))
            changed = True
        elif ev == "CarrierNameChange":
            changed = self._handle_name_change(raw)
        elif ev == "CarrierFinance":
            changed = self._handle_finance(raw)
        elif ev == "CarrierBankTransfer":
            changed = self._handle_bank_transfer(raw)
        elif ev == "CarrierBuy":
            changed = self._handle_carrier_buy(raw)

        if changed:
            self.carrier_data["last_updated"] = raw.get("timestamp") or _utc_stamp()
            old_status = self.carrier_data.get("_runtime_prev_status", "idle")
            self._update_status()
            new_status = self.carrier_data["status"]
            fresh = self._event_is_fresh(raw) and not self._replaying_history
            if new_status != old_status:
                self.carrier_data["_runtime_prev_status"] = new_status
                self._fire_status_changed(
                    old_status, new_status, self.carrier_data, discord=fresh,
                )
            self._ensure_status_ticker()
            self.save_state()
            changed_record = self.carrier_data
            if callable(self.on_updated):
                self.on_updated(changed_record)
            if callable(self.on_panel_updated):
                self.on_panel_updated(changed_record)
        if selected_key in self._carriers:
            self._active_carrier_key = selected_key
        self._restore_active_carrier()

    def _apply_squadron_event(self, raw):
        ev = raw.get("event")
        clear = ev in {"LeftSquadron", "KickedFromSquadron", "DisbandedSquadron"}
        if clear:
            updates = {
                "squadron_id": None, "squadron_name": None,
                "squadron_rank": None, "squadron_rank_name": None,
            }
        else:
            updates = {
                "squadron_id": raw.get("SquadronID"),
                "squadron_name": raw.get("SquadronName"),
                "squadron_rank": raw.get("NewRank", raw.get("CurrentRank")),
                "squadron_rank_name": raw.get(
                    "NewRankName", raw.get("CurrentRankName"),
                ),
            }
            updates = {key: value for key, value in updates.items() if value is not None}
        if not updates:
            return False
        self._squadron_context.update(updates)
        for row in self._carriers.values():
            row.update(updates)
            row["last_updated"] = raw.get("timestamp") or _utc_stamp()
        return True

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_stats(self, raw):
        cd = self.carrier_data
        cd["carrier_id"] = raw.get("CarrierID")
        cd["carrier_type"] = raw.get("CarrierType") or cd.get("carrier_type") or "FleetCarrier"
        cd["callsign"] = raw.get("Callsign")
        cd["name"] = raw.get("Name")
        cd["docking_access"] = (raw.get("DockingAccess") or "all").lower()
        cd["allow_notorious"] = bool(raw.get("AllowNotorious", False))
        cd["pending_decom"] = bool(raw.get("PendingDecommission", False))

        fuel = raw.get("FuelLevel")
        if fuel is not None:
            self._set_authoritative_fuel(fuel, raw, "CarrierStats")
        cd["jump_range_curr"] = raw.get("JumpRangeCurr")
        cd["jump_range_max"] = raw.get("JumpRangeMax")
        cd["stats_updated_at"] = raw.get("timestamp") or _utc_stamp()

        finance = raw.get("Finance") or {}
        cd["balance"] = finance.get("CarrierBalance")
        cd["available_balance"] = finance.get("AvailableBalance")
        cd["reserve_balance"] = finance.get("ReserveBalance")
        cd["reserve_percent"] = finance.get("ReservePercent")
        cd["tax_rearm"] = finance.get("TaxRate_rearm", finance.get("TaxRate_Rearm"))
        cd["tax_refuel"] = finance.get("TaxRate_refuel", finance.get("TaxRate_Refuel"))
        cd["tax_repair"] = finance.get("TaxRate_repair", finance.get("TaxRate_Repair"))

        space = raw.get("SpaceUsage") or {}
        cd["space_total"] = space.get("TotalCapacity")
        cd["space_cargo"] = space.get("Cargo")
        cd["space_crew"] = space.get("Crew")
        cd["space_free"] = space.get("FreeSpace")
        cd["space_reserved"] = space.get("CargoSpaceReserved", space.get("ReservedSpace"))
        cd["space_ship_packs"] = space.get("ShipPacks")
        cd["space_module_packs"] = space.get("ModulePacks")
        cd["cargo_updated_at"] = cd["stats_updated_at"]
        cd["cargo_total_source"] = "CarrierStats"

        crew_raw = raw.get("Crew") or []
        cd["crew"] = [
            {
                "CrewRole": c.get("CrewRole"),
                "Activated": bool(c.get("Activated", False)),
                "Enabled": bool(c.get("Enabled", False)),
            }
            for c in crew_raw
        ]
        return True

    def _handle_finance(self, raw):
        cd = self.carrier_data
        cd["balance"] = raw.get("CarrierBalance", cd["balance"])
        cd["available_balance"] = raw.get("AvailableBalance", cd["available_balance"])
        cd["reserve_balance"] = raw.get("ReserveBalance", cd["reserve_balance"])
        cd["reserve_percent"] = raw.get("ReservePercent", cd["reserve_percent"])
        return True

    def _handle_bank_transfer(self, raw):
        cd = self.carrier_data
        cd["balance"] = raw.get("CarrierBalance", cd.get("balance"))
        return True

    def apply_observed_cargo_transfer(self, raw, carrier_id=None):
        """Advance an exact owner snapshot with a confirmed own-carrier transfer."""
        if not isinstance(raw, dict):
            return False
        delta = 0
        for row in raw.get("Transfers") or []:
            if not isinstance(row, dict):
                continue
            try:
                count = max(0, int(row.get("Count") or 0))
            except (TypeError, ValueError):
                continue
            direction = str(row.get("Direction") or "").casefold()
            if direction == "tocarrier":
                delta += count
            elif direction == "toship":
                delta -= count
        if not delta:
            return False
        with self._profile_lock:
            carrier_id = carrier_id or raw.get("CarrierID") or raw.get("MarketID")
            cd = self.carrier_for_id(carrier_id) if carrier_id is not None else self.carrier_data
            if cd is None:
                return False
            if cd.get("space_cargo") is None:
                return False
            cd["space_cargo"] = max(0, int(cd["space_cargo"]) + delta)
            if cd.get("space_free") is not None:
                cd["space_free"] = max(0, int(cd["space_free"]) - delta)
            cd["cargo_updated_at"] = raw.get("timestamp") or _utc_stamp()
            cd["cargo_total_source"] = "CarrierStats + own-carrier CargoTransfer"
            cd["last_updated"] = _utc_stamp()
            self.save_state()
        if callable(self.on_updated):
            self.on_updated(cd)
        if callable(self.on_panel_updated):
            self.on_panel_updated(cd)
        return True

    def _handle_carrier_buy(self, raw):
        cd = self.carrier_data
        cd["carrier_id"] = raw.get("CarrierID") or cd.get("carrier_id")
        cd["carrier_type"] = (
            self._normalise_carrier_type(raw.get("CarrierType"))
            or cd.get("carrier_type") or "FleetCarrier"
        )
        cd["callsign"] = raw.get("Callsign") or cd.get("callsign")
        cd["carrier_purchased_at"] = raw.get("timestamp")
        cd["carrier_spawn_system"] = raw.get("Location")
        return True

    def _handle_jump_request(self, raw):
        cd = self.carrier_data
        cd["jump_destination"] = raw.get("SystemName")
        cd["jump_destination_address"] = raw.get("SystemAddress")
        cd["jump_body"] = raw.get("Body")
        cd["jump_departure_time"] = raw.get("DepartureTime")
        cd["_runtime_cancel_ts"] = None
        return True

    def _handle_jump_cancelled(self, raw):
        cd = self.carrier_data
        cd["jump_destination"] = None
        cd["jump_destination_address"] = None
        cd["jump_body"] = None
        cd["jump_departure_time"] = None
        ts = _parse_dt(raw.get("timestamp"))
        cd["_runtime_cancel_ts"] = ts if ts else datetime.now(timezone.utc)
        return True

    def _handle_location(self, raw):
        cd = self.carrier_data
        system = raw.get("StarSystem") or raw.get("SystemName")
        system_address = raw.get("SystemAddress")
        body = raw.get("Body")
        system_changed = bool(system and system != cd.get("system"))

        if system_changed:
            if cd.get("system"):
                cd["previous_system"] = cd["system"]
                cd["previous_body"] = cd.get("body")
                hist = cd.setdefault("jump_history", [])
                hist.insert(0, {
                    "system": cd["system"],
                    "body": cd.get("body"),
                    "timestamp": raw.get("timestamp"),
                })
                cd["jump_history"] = hist[:10]
            cd["system"] = system
            cd["system_address"] = system_address
            cd["body"] = body
            cd["jump_destination"] = None
            cd["jump_destination_address"] = None
            cd["jump_body"] = None
            # Keep jump_departure_time so _update_status() can compute the
            # post-jump cooldown window; it expires naturally after _COOLDOWN_SECS.
        elif body and body != cd.get("body"):
            cd["body"] = body
        if system_address is not None:
            cd["system_address"] = system_address
        completed_stop = None
        if system_changed:
            completed_stop = self._advance_expedition(
                system, raw.get("timestamp"), system_address,
            )
        else:
            # CarrierLocation commonly precedes CarrierJump for one arrival.
            # Repair an entirely unmarked current stop, but do not let the
            # second notification consume a later repeated-system waypoint.
            completed_stop = self._repair_current_expedition_stop(
                system, raw.get("timestamp"), system_address,
            )
        if completed_stop is None:
            completed_stop = self._find_unaccounted_arrival_stop(
                system, raw.get("timestamp"), system_address,
            )
        self._apply_carrier_jump_fuel(completed_stop, raw)
        return True

    def _set_authoritative_fuel(self, value, raw, source):
        """Record an exact journal fuel observation without rewinding newer evidence."""
        cd = self.carrier_data
        incoming_at = (raw or {}).get("timestamp") or _utc_stamp()
        current_at = cd.get("fuel_level_updated_at") or cd.get("stats_updated_at")
        incoming_dt = _parse_dt(incoming_at)
        current_dt = _parse_dt(current_at)
        if incoming_dt and current_dt and incoming_dt < current_dt:
            return False
        try:
            fuel = max(0, min(int(cd.get("fuel_capacity") or 1000), int(value)))
        except (TypeError, ValueError):
            return False
        cd["fuel_level"] = fuel
        cd["fuel_level_estimated"] = False
        cd["fuel_level_source"] = source
        cd["fuel_level_updated_at"] = incoming_at
        return True

    def _find_unaccounted_arrival_stop(self, system, timestamp=None, system_address=None):
        """Find a pre-5.2.9.6 visited stop belonging to this arrival pair."""
        event_dt = _parse_dt(timestamp)
        if event_dt is None:
            return None
        target = " ".join(str(system or "").split()).casefold()
        target_address = str(system_address) if system_address is not None else None
        candidates = []
        for row in self.carrier_data.get("expedition_route") or []:
            if not isinstance(row, dict) or not row.get("visited") or row.get("fuel_accounted_at"):
                continue
            row_target = " ".join(str(row.get("system") or "").split()).casefold()
            row_address = row.get("id64")
            address_match = (
                target_address is not None and row_address is not None
                and str(row_address) == target_address
            )
            if not address_match and (not target or row_target != target):
                continue
            visited_dt = _parse_dt(row.get("visited_at"))
            if visited_dt is None:
                continue
            delta = abs((event_dt - visited_dt).total_seconds())
            if delta <= 180:
                candidates.append((delta, row))
        return min(candidates, key=lambda item: item[0])[1] if candidates else None

    def _apply_carrier_jump_fuel(self, route_row, raw):
        """Project depot fuel after an arrival until CarrierStats confirms it."""
        if not isinstance(route_row, dict) or route_row.get("fuel_accounted_at"):
            return False
        cd = self.carrier_data
        timestamp = (raw or {}).get("timestamp") or _utc_stamp()
        event_dt = _parse_dt(timestamp)
        fuel_at = cd.get("fuel_level_updated_at") or cd.get("stats_updated_at")
        fuel_dt = _parse_dt(fuel_at)
        if event_dt and fuel_dt and event_dt <= fuel_dt:
            return False
        try:
            fuel = int(cd.get("fuel_level"))
            distance = float(route_row.get("distance_ly"))
            total = int(cd.get("space_total"))
            free = int(cd.get("space_free"))
        except (TypeError, ValueError):
            return False
        used_capacity = max(0, total - free)
        # Current Fleet Carrier formula: the 25,000 T hull, used carrier
        # capacity and depot fuel all contribute to the burn for this leg.
        burn = int(math.floor(
            5.0 + (distance / 8.0) * (1.0 + (used_capacity + fuel) / 25000.0) + 0.5
        ))
        burn = max(0, min(fuel, burn))
        cd["fuel_level"] = fuel - burn
        cd["fuel_level_estimated"] = True
        cd["fuel_level_source"] = "CarrierJump calculation"
        cd["fuel_level_updated_at"] = timestamp
        route_row["fuel_accounted_at"] = timestamp
        route_row["fuel_actual_used_t"] = burn
        return True

    def _handle_name_change(self, raw):
        # Name is the documented field.  At least one live journal build
        # emitted the carrier name under an empty key, so retain that
        # compatibility fallback instead of silently losing a rename.
        name = raw.get("Name") or raw.get("CarrierName") or raw.get("")
        if not name:
            return False
        self.carrier_data["name"] = name
        if raw.get("Callsign"):
            self.carrier_data["callsign"] = raw.get("Callsign")
        return True

    def _advance_expedition(self, system, timestamp=None, system_address=None):
        target = " ".join(str(system or "").split()).casefold()
        target_address = str(system_address) if system_address is not None else None
        if not target and target_address is None:
            return None
        route = self.carrier_data.get("expedition_route") or []
        for row in route:
            if not isinstance(row, dict) or row.get("visited"):
                continue
            row_target = " ".join(str(row.get("system") or "").split()).casefold()
            row_address = row.get("id64")
            address_match = (
                target_address is not None and row_address is not None
                and str(row_address) == target_address
            )
            if address_match or (target and row_target == target):
                row["visited"] = True
                row["visited_at"] = timestamp or _utc_stamp()
                return row
        return None

    def next_expedition_stop(self):
        """Return the next pending row, never a stale copy of our current stop."""
        current = " ".join(str(self.carrier_data.get("system") or "").split()).casefold()
        current_address = self.carrier_data.get("system_address")
        for row in self.carrier_data.get("expedition_route") or []:
            if not isinstance(row, dict) or row.get("visited"):
                continue
            system = " ".join(str(row.get("system") or "").split())
            if not system:
                continue
            same_address = (
                current_address is not None and row.get("id64") is not None
                and str(row.get("id64")) == str(current_address)
            )
            if same_address or (current and system.casefold() == current):
                # An interrupted/manual route can leave the arrival row
                # pending.  Copy Next must still move the commander forward.
                continue
            return row
        return None

    def _publish_expedition_change(self):
        self.save_state()
        if callable(self.on_updated):
            self.on_updated(self.carrier_data)
        if callable(self.on_panel_updated):
            self.on_panel_updated(self.carrier_data)

    def set_expedition_stop_visited(self, index, visited=True):
        """Manually correct one route row without discarding its fuel plan."""
        route = self.carrier_data.get("expedition_route") or []
        try:
            row = route[int(index)]
        except (IndexError, TypeError, ValueError):
            return False
        if not isinstance(row, dict):
            return False
        visited = bool(visited)
        row["visited"] = visited
        row["visited_at"] = _utc_stamp() if visited else None
        row["manual_progress"] = visited
        if not visited:
            # A later real arrival must be allowed to account for this leg.
            row["fuel_accounted_at"] = None
            row["fuel_actual_used_t"] = None
        self._publish_expedition_change()
        return True

    def _invalidate_edited_expedition_plan(self):
        """Turn a structurally edited calculated route into a truthful manual one."""
        cd = self.carrier_data
        leg_fields = (
            "distance_ly", "distance_to_destination_ly", "fuel_remaining_t",
            "fuel_used_t", "tritium_market_t", "restock_t", "must_restock",
            "icy_ring", "pristine", "desired_destination",
        )
        for row in cd.get("expedition_route") or []:
            if isinstance(row, dict):
                for key in leg_fields:
                    row.pop(key, None)
        cd["expedition_requested_destinations"] = [
            str(row.get("system") or "").strip()
            for row in cd.get("expedition_route") or []
            if isinstance(row, dict) and str(row.get("system") or "").strip()
        ]
        cd["expedition_route_source"] = "manual"
        cd["expedition_spansh_job"] = None
        cd["expedition_spansh_url"] = None
        cd["expedition_plotted_at"] = None
        for key in (
            "expedition_total_distance_ly", "expedition_used_capacity_t",
            "expedition_fuel_required_t", "expedition_starting_tank_t",
            "expedition_starting_market_tritium_t", "expedition_starting_load_t",
        ):
            cd[key] = None

    def add_expedition_stop(self, system, after_index=None):
        system = " ".join(str(system or "").split())
        if not system:
            return False
        route = self.carrier_data.setdefault("expedition_route", [])
        row = {"system": system, "visited": False, "visited_at": None}
        try:
            index = int(after_index) + 1
        except (TypeError, ValueError):
            index = len(route)
        route.insert(max(0, min(index, len(route))), row)
        self._invalidate_edited_expedition_plan()
        self._publish_expedition_change()
        return True

    def delete_expedition_stop(self, index):
        route = self.carrier_data.get("expedition_route") or []
        try:
            route.pop(int(index))
        except (IndexError, TypeError, ValueError):
            return False
        self._invalidate_edited_expedition_plan()
        self._publish_expedition_change()
        return True

    def move_expedition_stop(self, index, offset):
        route = self.carrier_data.get("expedition_route") or []
        try:
            old = int(index)
            new = old + int(offset)
        except (TypeError, ValueError):
            return False
        if old < 0 or old >= len(route) or new < 0 or new >= len(route):
            return False
        route[old], route[new] = route[new], route[old]
        self._invalidate_edited_expedition_plan()
        self._publish_expedition_change()
        return True

    def _repair_current_expedition_stop(self, system, timestamp=None, system_address=None):
        """Mark current stop only when this arrival has no completed match."""
        target = " ".join(str(system or "").split()).casefold()
        target_address = str(system_address) if system_address is not None else None
        for row in self.carrier_data.get("expedition_route") or []:
            if not isinstance(row, dict) or not row.get("visited"):
                continue
            row_target = " ".join(str(row.get("system") or "").split()).casefold()
            row_address = row.get("id64")
            if (
                target_address is not None and row_address is not None
                and str(row_address) == target_address
            ) or (target and row_target == target):
                return None
        return self._advance_expedition(system, timestamp, system_address)

    def set_expedition(self, name, systems, reserve_fuel=200):
        """Persist a manually pasted carrier route."""
        existing = {
            str(row.get("system") or "").strip().lower(): row
            for row in (self.carrier_data.get("expedition_route") or []) if isinstance(row, dict)
        }
        route = []
        seen = set()
        for value in systems or []:
            supplied = value if isinstance(value, dict) else {}
            system = str(supplied.get("system") if supplied else value or "").strip()
            key = system.lower()
            if not system or key in seen:
                continue
            seen.add(key)
            old = existing.get(key, {})
            row = dict(supplied)
            row.update({
                "system": system,
                "visited": bool(old.get("visited")),
                "visited_at": old.get("visited_at"),
                "fuel_accounted_at": old.get("fuel_accounted_at"),
                "fuel_actual_used_t": old.get("fuel_actual_used_t"),
            })
            route.append(row)
        self.carrier_data["expedition_name"] = (name or "").strip()
        self.carrier_data["expedition_route"] = route
        self.carrier_data["expedition_requested_destinations"] = [row["system"] for row in route]
        self.carrier_data["expedition_route_source"] = "manual"
        self.carrier_data["expedition_spansh_job"] = None
        self.carrier_data["expedition_spansh_url"] = None
        self.carrier_data["expedition_plotted_at"] = None
        for key in (
            "expedition_total_distance_ly", "expedition_used_capacity_t",
            "expedition_fuel_required_t", "expedition_starting_tank_t",
            "expedition_starting_market_tritium_t", "expedition_starting_load_t",
        ):
            self.carrier_data[key] = None
        try:
            self.carrier_data["expedition_reserve_fuel"] = max(0, int(reserve_fuel))
        except Exception:
            self.carrier_data["expedition_reserve_fuel"] = 200
        self._repair_current_expedition_stop(
            self.carrier_data.get("system"),
            system_address=self.carrier_data.get("system_address"),
        )
        self.save_state()
        if callable(self.on_updated):
            self.on_updated(self.carrier_data)
        if callable(self.on_panel_updated):
            self.on_panel_updated(self.carrier_data)

    def clear_expedition(self):
        """Delete route-planning state without disturbing carrier evidence."""
        reserve_fuel = self.carrier_data.get("expedition_reserve_fuel")
        if reserve_fuel is None:
            reserve_fuel = 200
        self.set_expedition("", [], reserve_fuel)

    def set_spansh_expedition(self, name, route_result, reserve_fuel=200):
        """Persist a normalized Spansh route and its per-jump fuel evidence."""
        result = route_result if isinstance(route_result, dict) else {}
        jumps = result.get("jumps") or []
        existing = {
            str(row.get("system") or "").strip().lower(): row
            for row in (self.carrier_data.get("expedition_route") or []) if isinstance(row, dict)
        }
        rows = []
        # Spansh includes the source as row zero. The expedition list contains
        # only jumps still to make from the carrier's current location.
        for jump in jumps[1:]:
            if not isinstance(jump, dict) or not jump.get("system"):
                continue
            system = str(jump.get("system") or "").strip()
            old = existing.get(system.lower(), {})
            rows.append({
                key: jump.get(key)
                for key in (
                    "system", "id64", "distance_ly", "distance_to_destination_ly",
                    "fuel_remaining_t", "fuel_used_t", "tritium_market_t", "restock_t",
                    "must_restock", "icy_ring", "pristine", "desired_destination",
                )
            } | {
                "system": system,
                "visited": bool(old.get("visited")),
                "visited_at": old.get("visited_at"),
                "fuel_accounted_at": old.get("fuel_accounted_at"),
                "fuel_actual_used_t": old.get("fuel_actual_used_t"),
            })
        cd = self.carrier_data
        cd["expedition_name"] = (name or "").strip()
        cd["expedition_route"] = rows
        cd["expedition_requested_destinations"] = [
            str(row.get("name") or row.get("system") or "").strip()
            for row in (result.get("destinations") or [])
            if isinstance(row, dict) and (row.get("name") or row.get("system"))
        ]
        try:
            cd["expedition_reserve_fuel"] = max(0, int(reserve_fuel))
        except Exception:
            cd["expedition_reserve_fuel"] = 200
        cd["expedition_route_source"] = "spansh"
        cd["expedition_spansh_job"] = result.get("job")
        cd["expedition_spansh_url"] = result.get("url")
        cd["expedition_plotted_at"] = _utc_stamp()
        cd["expedition_total_distance_ly"] = result.get("total_distance_ly")
        cd["expedition_used_capacity_t"] = result.get("used_capacity_t")
        cd["expedition_fuel_required_t"] = result.get("fuel_required_t")
        cd["expedition_starting_tank_t"] = result.get("starting_tank_t")
        cd["expedition_starting_market_tritium_t"] = result.get("starting_market_tritium_t")
        cd["expedition_starting_load_t"] = result.get("starting_load_t")
        self._repair_current_expedition_stop(
            cd.get("system"), system_address=cd.get("system_address"),
        )
        self.save_state()
        if callable(self.on_updated):
            self.on_updated(self.carrier_data)
        if callable(self.on_panel_updated):
            self.on_panel_updated(self.carrier_data)

    def update_expedition_details(self, name, reserve_fuel=200):
        """Update route metadata without replacing calculated Spansh jumps."""
        self.carrier_data["expedition_name"] = (name or "").strip()
        try:
            self.carrier_data["expedition_reserve_fuel"] = max(0, int(reserve_fuel))
        except Exception:
            self.carrier_data["expedition_reserve_fuel"] = 200
        self.save_state()
        if callable(self.on_updated):
            self.on_updated(self.carrier_data)
        if callable(self.on_panel_updated):
            self.on_panel_updated(self.carrier_data)

    def _handle_trade_order(self, raw):
        cd = self.carrier_data
        commodity = (
            raw.get("Commodity_Localised") or raw.get("Commodity") or ""
        ).title()

        orders = [
            o for o in cd.get("trade_orders", [])
            if o.get("commodity", "").lower() != commodity.lower()
        ]

        if not raw.get("CancelTrade", False):
            purchase = raw.get("PurchaseOrder")
            sale = raw.get("SaleOrder")
            if purchase is not None or sale is not None:
                orders.insert(0, {
                    "commodity": commodity,
                    "type": "Buy" if purchase is not None else "Sell",
                    "amount": purchase if purchase is not None else sale,
                    "price": raw.get("Price"),
                    "black_market": bool(raw.get("BlackMarket", False)),
                    "timestamp": raw.get("timestamp"),
                })
        cd["trade_orders"] = orders[:50]
        return True

    # ------------------------------------------------------------------
    # Status state machine (EDCM algorithm)
    # ------------------------------------------------------------------

    def _update_status(self):
        cd = self.carrier_data
        dep_str = cd.get("jump_departure_time")
        now = datetime.now(timezone.utc)

        if dep_str:
            dep_dt = _parse_dt(dep_str)
            if dep_dt:
                delta = (dep_dt - now).total_seconds()
                if delta > 0:
                    cd["status"] = "jumping"
                    return
                elif delta > -_COOLDOWN_SECS:
                    cd["status"] = "cooldown"
                    return

        last_cancel = cd.get("_runtime_cancel_ts")
        if last_cancel:
            if (now - last_cancel).total_seconds() < 60:
                cd["status"] = "cooldown_cancel"
                return

        cd["status"] = "idle"

    # ------------------------------------------------------------------
    # Background status ticker
    # ------------------------------------------------------------------

    def _ensure_status_ticker(self):
        active = [
            row for row in self._carriers.values()
            if row.get("status") in ("jumping", "cooldown", "cooldown_cancel")
        ]
        if not active:
            return
        existing = getattr(self, "_status_ticker", None)
        if existing and existing.is_alive():
            return
        departures = [
            _parse_dt(row.get("jump_departure_time")) for row in active
            if row.get("status") == "jumping"
        ]
        departures = [value for value in departures if value is not None]
        if departures:
            secs_until = min(
                (value - datetime.now(timezone.utc)).total_seconds()
                for value in departures
            )
            delay = max(5.0, min(30.0, secs_until + 2.0))
        else:
            delay = 30.0
        self._schedule_status_check(delay)

    def _schedule_status_check(self, delay: float = 30.0):
        old = getattr(self, "_status_ticker", None)
        if old and old.is_alive():
            old.cancel()
        t = threading.Timer(delay, self._status_check_tick)
        t.daemon = True
        t.start()
        self._status_ticker = t

    def _status_check_tick(self):
        changed = []
        selected_key = self._active_carrier_key
        for row in list(self._carriers.values()):
            self.carrier_data = row
            old = row.get("_runtime_prev_status", row.get("status", "idle"))
            self._update_status()
            new = row["status"]
            if new != old:
                row["_runtime_prev_status"] = new
                row["last_updated"] = _utc_stamp()
                self._fire_status_changed(old, new, row)
                changed.append(row)
        if selected_key in self._carriers:
            self._active_carrier_key = selected_key
        self._restore_active_carrier()
        if changed:
            self.save_state()
            for row in changed:
                if callable(self.on_updated):
                    self.on_updated(row)
                if callable(self.on_panel_updated):
                    self.on_panel_updated(row)
        active = any(
            row.get("status") in ("jumping", "cooldown", "cooldown_cancel")
            for row in self._carriers.values()
        )
        if active:
            self._schedule_status_check(30.0)
        else:
            self._status_ticker = None

    # ------------------------------------------------------------------
    # Discord webhook
    # ------------------------------------------------------------------

    @staticmethod
    def _event_is_fresh(raw, max_age_secs=120):
        ts = (raw or {}).get("timestamp")
        if not ts:
            return True
        try:
            dt = _parse_dt(ts)
            if dt is None:
                return True
            return (datetime.now(timezone.utc) - dt).total_seconds() < max_age_secs
        except Exception:
            return True

    def _fire_status_changed(self, old_status, new_status, carrier_data=None, discord=True):
        carrier_data = carrier_data if isinstance(carrier_data, dict) else self.carrier_data
        if callable(self.on_status_changed):
            try:
                self.on_status_changed(old_status, new_status, carrier_data)
            except Exception as exc:
                self._warn_throttled(
                    "status-callback",
                    "Carrier status callback failed: %s",
                    exc,
                )
        if discord:
            self._maybe_discord(old_status, new_status, carrier_data)

    def _warn_throttled(self, key, message, *args, interval_s=120.0):
        """Retain useful carrier diagnostics without flooding normal logs."""
        now = time.monotonic()
        if now - float(self._diagnostic_last.get(key) or 0.0) < interval_s:
            return
        self._diagnostic_last[key] = now
        logging.warning(message, *args)

    def _maybe_discord(self, old_status, new_status, carrier_data=None):
        url = (self._config.get("carrier_discord_webhook_url") or "").strip()
        if not url:
            return

        event_type = None
        if new_status == "jumping" and old_status == "idle":
            event_type = "jump_plotted"
        elif new_status == "cooldown" and old_status == "jumping":
            event_type = "jump_completed"
        elif new_status == "cooldown_cancel":
            event_type = "jump_cancelled"
        elif old_status in ("cooldown", "cooldown_cancel") and new_status == "idle":
            event_type = "cooldown_finished"

        if not event_type:
            return
        if not self._config.get(f"carrier_discord_{event_type}", True):
            return

        with self._profile_lock:
            snapshot = deepcopy(
                carrier_data if isinstance(carrier_data, dict) else self.carrier_data
            )
        threading.Thread(
            target=self._send_discord,
            args=(url, event_type, snapshot),
            daemon=True,
        ).start()

    def _discord_color(self, event_type):
        """Resolve webhook colour from the active commander's UI theme."""
        _name, palette = themes.resolve_theme(
            self._config.get("ui_theme_name"),
            self._config.get("ui_custom_themes"),
        )
        slot = _DISCORD_EVENT_STYLES.get(event_type, ("CARRIER EVENT", "accent"))[1]
        value = palette.get(slot) or palette.get("accent") or "#00d1ff"
        try:
            return int(value.lstrip("#"), 16)
        except (TypeError, ValueError):
            return 0x00D1FF

    def _build_discord_payload(self, event_type, cd):
        """Build one bounded, themed carrier operations embed."""
        carrier_type = cd.get("carrier_type")
        is_squadron = carrier_type == "SquadronCarrier"
        carrier_label = "Squadron Carrier" if is_squadron else "Fleet Carrier"
        event_label = _DISCORD_EVENT_STYLES.get(
            event_type, (str(event_type or "Carrier Event").replace("_", " ").upper(), "accent")
        )[0]
        name = _discord_escape(cd.get("name") or carrier_label)
        callsign = _discord_escape(cd.get("callsign") or "???-???")
        description = f"**{name}** · `{callsign}`"
        if event_type == "test":
            description += "\nThe webhook is connected. This preview uses the active carrier state."
        if cd.get("pending_decom"):
            description += "\n**DECOMMISSIONING IS PENDING**"
        detailed_status = event_type == "status_update"

        fields = []

        def add_field(field_name, value, inline=False):
            value = _discord_clip(value)
            if value:
                fields.append({
                    "name": _discord_clip(field_name, 256),
                    "value": value,
                    "inline": bool(inline),
                })

        location_links = event_type != "jump_plotted"
        current = _discord_location(
            cd.get("system"), cd.get("body"), link=location_links,
        )
        target = _discord_location(
            cd.get("jump_destination"), cd.get("jump_body"), link=location_links,
        )
        previous = _discord_location(
            cd.get("previous_system"), cd.get("previous_body"), link=location_links,
        )
        if event_type == "jump_plotted":
            add_field("CURRENT SYSTEM", current, True)
            add_field("JUMP TARGET", target, True)
            add_field("DEPARTURE", _discord_time(cd.get("jump_departure_time")))
        elif event_type == "jump_completed":
            add_field("ARRIVED", current, True)
            add_field("DEPARTED FROM", previous, True)
        elif event_type == "jump_cancelled":
            add_field("REMAINING AT", current, True)
            if cd.get("jump_destination"):
                add_field("CANCELLED TARGET", target, True)
        else:
            add_field("CURRENT SYSTEM", current, True)
            if (
                event_type in {"status_update", "test"}
                and cd.get("jump_destination")
                and cd.get("status") == "jumping"
            ):
                add_field("JUMP TARGET", target, True)
                add_field("DEPARTURE", _discord_time(cd.get("jump_departure_time")))

        manual_departure = _discord_time(cd.get("_manual_departure_ts"))
        if event_type == "status_update" and manual_departure:
            add_field("PLANNED DEPARTURE", manual_departure)

        if is_squadron:
            squadron = _discord_escape(cd.get("squadron_name") or "Awaiting SquadronStartup")
            rank = cd.get("squadron_rank_name")
            if rank is None:
                rank = cd.get("squadron_rank")
            squadron_text = f"**{squadron}**"
            if rank is not None and str(rank).strip():
                squadron_text += f" · {_discord_escape(rank)}"
            add_field("SQUADRON", squadron_text)

        fuel = _discord_number(cd.get("fuel_level"))
        capacity = _discord_number(cd.get("fuel_capacity") or 1000)
        if fuel is not None and event_type in {
            "jump_plotted", "jump_cancelled", "status_update", "test",
        }:
            fuel_text = f"{fuel} / {capacity} T"
            fuel_text += " · estimated" if cd.get("fuel_level_estimated") else " · journal confirmed"
            add_field("TRITIUM", fuel_text, True)

        if detailed_status:
            current_range = _discord_number(cd.get("jump_range_curr"), 1)
            maximum_range = _discord_number(cd.get("jump_range_max"), 1)
            range_parts = []
            if current_range is not None:
                range_parts.append(f"{current_range} LY current")
            if maximum_range is not None:
                range_parts.append(f"{maximum_range} LY max")
            if range_parts:
                add_field("JUMP RANGE", " · ".join(range_parts), True)

            capacity_parts = []
            for key, label in (
                ("space_cargo", "cargo"),
                ("space_free", "free"),
                ("space_total", "total"),
            ):
                value = _discord_number(cd.get(key))
                if value is not None:
                    capacity_parts.append(f"{value} T {label}")
            if capacity_parts:
                add_field("CARRIER CAPACITY", " · ".join(capacity_parts), True)

            access_names = {
                "all": "All commanders",
                "none": "None",
                "friends": "Friends",
                "squadron": "Squadron",
                "squadronfriends": "Squadron + friends",
            }
            access_key = str(cd.get("docking_access") or "all").replace("_", "").casefold()
            access = access_names.get(access_key, _discord_escape(cd.get("docking_access") or "All"))
            notorious = "notorious allowed" if cd.get("allow_notorious") else "notorious blocked"
            add_field("DOCKING ACCESS", f"{access} · {notorious}", True)

        route = [row for row in (cd.get("expedition_route") or []) if isinstance(row, dict)]
        if route:
            done = sum(1 for row in route if row.get("visited"))
            remaining = max(0, len(route) - done)
            expedition_name = _discord_escape(cd.get("expedition_name") or "Carrier expedition")
            next_stop = _next_pending_route(cd)
            if detailed_status:
                route_lines = [
                    f"**{expedition_name}**",
                    f"{done}/{len(route)} stops complete · {remaining} remaining",
                ]
                total_distance = _discord_number(cd.get("expedition_total_distance_ly"), 1)
                if total_distance is not None:
                    route_lines.append(f"{total_distance} LY plotted")
                add_field("EXPEDITION", "\n".join(route_lines))

                if next_stop:
                    next_bits = [_discord_location(next_stop.get("system"), next_stop.get("body"))]
                    next_distance = _discord_number(next_stop.get("distance_ly"), 1)
                    next_fuel = _discord_number(next_stop.get("fuel_used_t"))
                    leg_bits = []
                    if next_distance is not None:
                        leg_bits.append(f"{next_distance} LY")
                    if next_fuel is not None:
                        leg_bits.append(f"{next_fuel} T planned")
                    if leg_bits:
                        next_bits.append(" · ".join(leg_bits))
                    add_field("NEXT EXPEDITION STOP", "\n".join(next_bits))
            else:
                route_lines = [f"**{expedition_name}** · {done}/{len(route)} stops"]
                if next_stop and event_type in {
                    "jump_completed", "jump_cancelled", "cooldown_finished",
                }:
                    next_bits = [_discord_location(next_stop.get("system"), next_stop.get("body"))]
                    next_distance = _discord_number(next_stop.get("distance_ly"), 1)
                    next_fuel = _discord_number(next_stop.get("fuel_used_t"))
                    leg_bits = []
                    if next_distance is not None:
                        leg_bits.append(f"{next_distance} LY")
                    if next_fuel is not None:
                        leg_bits.append(f"{next_fuel} T")
                    route_lines.append(
                        "**Next:** " + next_bits[0]
                        + (f" · {' · '.join(leg_bits)}" if leg_bits else "")
                    )
                add_field("EXPEDITION", "\n".join(route_lines))

            if detailed_status:
                remaining_fuel = []
                for row in route:
                    if row.get("visited") or row.get("fuel_used_t") is None:
                        continue
                    try:
                        remaining_fuel.append(max(0, int(float(row.get("fuel_used_t")))))
                    except (TypeError, ValueError):
                        pass
                if remaining_fuel:
                    reserve = _discord_number(cd.get("expedition_reserve_fuel") or 0)
                    add_field(
                        "ROUTE FUEL PLAN",
                        f"{sum(remaining_fuel):,} T remaining · {reserve} T reserve",
                        True,
                    )

        if detailed_status:
            active_services = []
            paused_services = []
            for member in cd.get("crew") or []:
                if not isinstance(member, dict) or not member.get("Activated"):
                    continue
                role = member.get("CrewRole") or "Service"
                label = _DISCORD_SERVICE_NAMES.get(role, role)
                (active_services if member.get("Enabled") else paused_services).append(
                    _discord_escape(label)
                )
            service_lines = []
            if active_services:
                service_lines.append("**Online:** " + " · ".join(active_services))
            if paused_services:
                service_lines.append("**Paused:** " + " · ".join(paused_services))
            if service_lines:
                add_field("CARRIER SERVICES", "\n".join(service_lines))

            destination_note = _discord_escape(cd.get("destination_note"))
            if destination_note:
                add_field("PLANNED DESTINATION", destination_note)
            note = _discord_escape(cd.get("notes"))
            if note:
                add_field("OPERATOR NOTE", note)

        link_system = (
            cd.get("jump_destination") if event_type == "jump_plotted"
            else cd.get("system")
        )
        author_name = f"VOIDCOMPASS // {carrier_label.upper()} COMMAND"
        footer_text = f"VoidCompass · {carrier_label} Command · journal-backed"
        title = _discord_clip(event_label, 256)
        description = _discord_clip(description, 4096)
        # Discord applies a 6,000-character aggregate limit across all embed
        # text. Keep a small margin and preserve earlier operational fields if
        # unusually long user notes or imported route names consume the rest.
        text_used = len(author_name) + len(footer_text) + len(title) + len(description)
        bounded_fields = []
        for field in fields[:25]:
            field_name = _discord_clip(field.get("name"), 256)
            remaining = 5900 - text_used - len(field_name)
            if remaining <= 1:
                break
            field_value = _discord_clip(field.get("value"), min(1024, remaining))
            if not field_value:
                continue
            bounded_fields.append({
                "name": field_name,
                "value": field_value,
                "inline": bool(field.get("inline")),
            })
            text_used += len(field_name) + len(field_value)
        embed = {
            "author": {"name": author_name},
            "title": title,
            "description": description,
            "color": self._discord_color(event_type),
            "fields": bounded_fields,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "footer": {"text": footer_text},
        }
        link_url = _edsm_system_url(link_system)
        if link_url and event_type != "jump_plotted":
            embed["url"] = link_url
        return {
            "username": "Void Compass",
            "allowed_mentions": {"parse": []},
            "embeds": [embed],
        }

    def _send_discord(self, url, event_type, cd):
        try:
            import requests
            response = requests.post(
                url,
                json=self._build_discord_payload(event_type, cd),
                timeout=8,
            )
            if response.status_code not in (200, 204):
                raise RuntimeError(f"Discord returned HTTP {response.status_code}")
            return True, None
        except Exception as exc:
            detail = _discord_error_detail(exc)
            self._warn_throttled(
                "discord-webhook",
                "Carrier Discord webhook failed: %s",
                detail,
                interval_s=300.0,
            )
            return False, detail

    def set_note(self, note: str):
        """Update the operator status note and persist to config."""
        self.carrier_data["notes"] = (note or "").strip()
        self.save_state()
        if callable(self.on_panel_updated):
            try:
                self.on_panel_updated(self.carrier_data)
            except Exception as exc:
                self._warn_throttled(
                    "panel-note-callback",
                    "Carrier note panel refresh failed: %s",
                    exc,
                )

    def set_destination_note(self, destination: str):
        """Update the operator's stated destination and persist."""
        self.carrier_data["destination_note"] = (destination or "").strip()
        self.save_state()
        if callable(self.on_panel_updated):
            try:
                self.on_panel_updated(self.carrier_data)
            except Exception as exc:
                self._warn_throttled(
                    "panel-destination-callback",
                    "Carrier destination panel refresh failed: %s",
                    exc,
                )

    def send_status_update(self, departure_ts=None):
        """Manually fire a Discord status-update notification with current state.

        departure_ts: optional int Unix timestamp for a manual departure time.
        """
        url = (self._config.get("carrier_discord_webhook_url") or "").strip()
        if not url:
            return False, "No webhook URL configured."
        with self._profile_lock:
            snapshot = deepcopy(self.carrier_data)
        if departure_ts is not None:
            snapshot["_manual_departure_ts"] = int(departure_ts)
        threading.Thread(
            target=self._send_discord,
            args=(url, "status_update", snapshot),
            daemon=True,
        ).start()
        return True, None

    def send_test_discord(self, url):
        with self._profile_lock:
            snapshot = deepcopy(self.carrier_data)
        return self._send_discord(url.strip(), "test", snapshot)
