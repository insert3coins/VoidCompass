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


def _discord_location(system, body=None):
    """Format an Elite system/body with a safe EDSM system link."""
    system = " ".join(str(system or "").split()) or "Unknown"
    body = " ".join(str(body or "").split())
    escaped_system = _discord_escape(system)
    url = _edsm_system_url(system)
    system_text = f"[{escaped_system}]({url})" if url else escaped_system
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
        self._last_cancel_ts = None
        self._prev_status = "idle"
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
            self._last_cancel_ts = None
            self._prev_status = "idle"
            self._config = config
            self.load_state()

    def scan_journal_history(self, journal_path, max_files=10, commander=None, fid=None):
        """
        One-time startup scan through recent journal files to catch carrier
        events that happened while the app was closed.
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

        recent = files[-max_files:][::-1]
        carrier_id = self.carrier_data.get("carrier_id")
        buckets = {
            "CarrierStats": None,
            "CarrierLocation": None,
            "CarrierJumpRequest": None,
            "CarrierJumpCancelled": None,
            "CarrierNameChange": None,
            "CarrierBankTransfer": None,
        }
        trade_events = []
        expected_name = str(commander or "").strip().casefold()
        expected_fid = str(fid or "").strip().casefold()

        for filepath in recent:
            file_events = {k: None for k in buckets}
            file_trades = []
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
                        cid = raw.get("CarrierID")
                        if ev == "CarrierJump" and cid is None:
                            cid = raw.get("MarketID")
                        if carrier_id and cid and cid != carrier_id:
                            continue
                        if ev == "CarrierStats":
                            file_events["CarrierStats"] = raw
                            if not carrier_id:
                                carrier_id = raw.get("CarrierID")
                        elif ev == "CarrierLocation":
                            # CarrierLocation is an owner startup event and is
                            # normally written before CarrierStats in the same
                            # journal. Keep it until the later identity snapshot
                            # supplies CarrierID instead of losing the location.
                            file_events["CarrierLocation"] = raw
                        elif ev == "CarrierJump":
                            if not carrier_id:
                                continue
                            file_events["CarrierLocation"] = raw
                        elif ev == "CarrierJumpRequest":
                            file_events["CarrierJumpRequest"] = raw
                        elif ev == "CarrierJumpCancelled":
                            file_events["CarrierJumpCancelled"] = raw
                        elif ev == "CarrierNameChange":
                            file_events["CarrierNameChange"] = raw
                        elif ev == "CarrierBankTransfer":
                            file_events["CarrierBankTransfer"] = raw
                        elif ev == "CarrierTradeOrder":
                            file_trades.append(raw)
            except Exception:
                continue

            for k in buckets:
                if buckets[k] is None and file_events[k] is not None:
                    buckets[k] = file_events[k]
            if not trade_events:
                trade_events = file_trades

            if buckets["CarrierStats"] is not None:
                break

        if generation != self._profile_generation:
            return
        replay = []
        if buckets["CarrierStats"]:
            replay.append(buckets["CarrierStats"])
        if buckets["CarrierLocation"]:
            replay.append(buckets["CarrierLocation"])
        if buckets["CarrierJumpRequest"]:
            replay.append(buckets["CarrierJumpRequest"])
        if buckets["CarrierJumpCancelled"]:
            req_ts = _parse_dt((buckets["CarrierJumpRequest"] or {}).get("timestamp"))
            can_ts = _parse_dt(buckets["CarrierJumpCancelled"].get("timestamp"))
            if req_ts and can_ts and can_ts > req_ts:
                replay.append(buckets["CarrierJumpCancelled"])
        if buckets["CarrierNameChange"]:
            replay.append(buckets["CarrierNameChange"])
        if buckets["CarrierBankTransfer"]:
            bank_ts = _parse_dt(buckets["CarrierBankTransfer"].get("timestamp"))
            stats_ts = _parse_dt((buckets["CarrierStats"] or {}).get("timestamp"))
            if not stats_ts or (bank_ts and bank_ts > stats_ts):
                replay.append(buckets["CarrierBankTransfer"])
        for t in trade_events:
            replay.append(t)

        if not replay:
            return

        with self._profile_lock:
            if generation != self._profile_generation:
                return
            orig_on_updated = self.on_updated
            self.on_updated = None
            try:
                for raw in replay:
                    ev = raw.get("event")
                    if ev == "CarrierStats":
                        self._handle_stats(raw)
                    elif ev in ("CarrierLocation", "CarrierJump"):
                        self._handle_location(raw)
                    elif ev == "CarrierJumpRequest":
                        self._handle_jump_request(raw)
                    elif ev == "CarrierJumpCancelled":
                        self._handle_jump_cancelled(raw)
                    elif ev == "CarrierTradeOrder":
                        self._handle_trade_order(raw)
                    elif ev == "CarrierNameChange":
                        self._handle_name_change(raw)
                    elif ev == "CarrierBankTransfer":
                        self._handle_bank_transfer(raw)
            finally:
                self.on_updated = orig_on_updated

            self.carrier_data["last_updated"] = _utc_stamp()
            self._update_status()
            self._prev_status = self.carrier_data["status"]
            self.save_state()
        logging.info(
            f"CarrierTracker: history scan complete — "
            f"{self.carrier_data.get('name') or 'unknown'} "
            f"@ {self.carrier_data.get('system') or '?'} "
            f"({self.carrier_data.get('status')})"
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
            data = {k: v for k, v in self.carrier_data.items() if k in _PERSIST_KEYS}
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
            for k in _PERSIST_KEYS:
                if k in saved:
                    self.carrier_data[k] = saved[k]
            # Self-heal a route saved before an arrival was observed by the
            # UI. The carrier's persisted system is authoritative on reload.
            route_repaired = bool(self._repair_current_expedition_stop(
                self.carrier_data.get("system"),
                self.carrier_data.get("last_updated"),
                self.carrier_data.get("system_address"),
            ))
            self._update_status()
            self._prev_status = self.carrier_data["status"]
            logging.info(
                f"CarrierTracker: loaded state for "
                f"{self.carrier_data.get('name') or 'unknown carrier'} "
                f"@ {self.carrier_data.get('system') or '?'}"
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

        # CarrierJump is written for any carrier the commander is aboard, and
        # CarrierDepositFuel can describe a donation to somebody else's
        # carrier.  Never let those events replace the owned/managed carrier
        # established by CarrierStats or CarrierBuy.
        identity_events = {"CarrierStats", "CarrierBuy"}
        carrier_events = ev.startswith("Carrier")
        if carrier_events and ev not in identity_events:
            known_id = self.carrier_data.get("carrier_id")
            event_id = raw.get("CarrierID")
            if event_id is None and ev == "CarrierJump":
                event_id = raw.get("MarketID")
            if not known_id:
                return
            if event_id is not None and str(event_id) != str(known_id):
                return

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
        elif ev in ("SquadronStartup", "SquadronCreated", "JoinedSquadron"):
            name = raw.get("SquadronName")
            if name:
                if raw.get("SquadronID") is not None:
                    self.carrier_data["squadron_id"] = raw.get("SquadronID")
                self.carrier_data["squadron_name"] = name
                if raw.get("CurrentRank") is not None:
                    self.carrier_data["squadron_rank"] = raw.get("CurrentRank")
                if raw.get("CurrentRankName"):
                    self.carrier_data["squadron_rank_name"] = raw.get("CurrentRankName")
                changed = True
        elif ev in ("SquadronPromotion", "SquadronDemotion"):
            name = raw.get("SquadronName")
            if name:
                self.carrier_data["squadron_name"] = name
            if raw.get("NewRank") is not None:
                self.carrier_data["squadron_rank"] = raw.get("NewRank")
            if raw.get("NewRankName"):
                self.carrier_data["squadron_rank_name"] = raw.get("NewRankName")
            changed = bool(name or raw.get("NewRank") is not None or raw.get("NewRankName"))
        elif ev in ("LeftSquadron", "KickedFromSquadron", "DisbandedSquadron"):
            self.carrier_data["squadron_id"] = None
            self.carrier_data["squadron_name"] = None
            self.carrier_data["squadron_rank"] = None
            self.carrier_data["squadron_rank_name"] = None
            changed = True

        if changed:
            self.carrier_data["last_updated"] = _utc_stamp()
            old_status = self._prev_status
            self._update_status()
            new_status = self.carrier_data["status"]
            fresh = self._event_is_fresh(raw)
            if new_status != old_status:
                self._prev_status = new_status
                self._fire_status_changed(old_status, new_status, discord=fresh)
            self._ensure_status_ticker()
            self.save_state()
            if callable(self.on_updated):
                self.on_updated(self.carrier_data)
            if callable(self.on_panel_updated):
                self.on_panel_updated(self.carrier_data)

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

    def apply_observed_cargo_transfer(self, raw):
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
            cd = self.carrier_data
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
            self.on_updated(self.carrier_data)
        if callable(self.on_panel_updated):
            self.on_panel_updated(self.carrier_data)
        return True

    def _handle_carrier_buy(self, raw):
        cd = self.carrier_data
        cd["carrier_id"] = raw.get("CarrierID") or cd.get("carrier_id")
        cd["carrier_type"] = "FleetCarrier"
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
        self._last_cancel_ts = None
        return True

    def _handle_jump_cancelled(self, raw):
        cd = self.carrier_data
        cd["jump_destination"] = None
        cd["jump_destination_address"] = None
        cd["jump_body"] = None
        cd["jump_departure_time"] = None
        ts = _parse_dt(raw.get("timestamp"))
        self._last_cancel_ts = ts if ts else datetime.now(timezone.utc)
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

        if self._last_cancel_ts:
            if (now - self._last_cancel_ts).total_seconds() < 60:
                cd["status"] = "cooldown_cancel"
                return

        cd["status"] = "idle"

    # ------------------------------------------------------------------
    # Background status ticker
    # ------------------------------------------------------------------

    def _ensure_status_ticker(self):
        status = self.carrier_data.get("status", "idle")
        if status not in ("jumping", "cooldown", "cooldown_cancel"):
            return
        existing = getattr(self, "_status_ticker", None)
        if existing and existing.is_alive():
            return
        if status == "jumping":
            dep_dt = _parse_dt(self.carrier_data.get("jump_departure_time"))
            if dep_dt:
                secs_until = (dep_dt - datetime.now(timezone.utc)).total_seconds()
                delay = max(5.0, secs_until + 2.0)
            else:
                delay = 30.0
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
        old = self._prev_status
        self._update_status()
        new = self.carrier_data["status"]
        if new != old:
            self._prev_status = new
            self.carrier_data["last_updated"] = _utc_stamp()
            self._fire_status_changed(old, new)
            self.save_state()
            if callable(self.on_updated):
                self.on_updated(self.carrier_data)
            if callable(self.on_panel_updated):
                self.on_panel_updated(self.carrier_data)
        if new in ("jumping", "cooldown", "cooldown_cancel"):
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

    def _fire_status_changed(self, old_status, new_status, discord=True):
        if callable(self.on_status_changed):
            try:
                self.on_status_changed(old_status, new_status, self.carrier_data)
            except Exception as exc:
                self._warn_throttled(
                    "status-callback",
                    "Carrier status callback failed: %s",
                    exc,
                )
        if discord:
            self._maybe_discord(old_status, new_status)

    def _warn_throttled(self, key, message, *args, interval_s=120.0):
        """Retain useful carrier diagnostics without flooding normal logs."""
        now = time.monotonic()
        if now - float(self._diagnostic_last.get(key) or 0.0) < interval_s:
            return
        self._diagnostic_last[key] = now
        logging.warning(message, *args)

    def _maybe_discord(self, old_status, new_status):
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
            snapshot = deepcopy(self.carrier_data)
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

        fields = []

        def add_field(field_name, value, inline=False):
            value = _discord_clip(value)
            if value:
                fields.append({
                    "name": _discord_clip(field_name, 256),
                    "value": value,
                    "inline": bool(inline),
                })

        current = _discord_location(cd.get("system"), cd.get("body"))
        target = _discord_location(cd.get("jump_destination"), cd.get("jump_body"))
        previous = _discord_location(cd.get("previous_system"), cd.get("previous_body"))
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
            if cd.get("jump_destination") and cd.get("status") == "jumping":
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
        if fuel is not None:
            fuel_text = f"{fuel} / {capacity} T"
            fuel_text += " · estimated" if cd.get("fuel_level_estimated") else " · journal confirmed"
            add_field("TRITIUM", fuel_text, True)

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
            route_lines = [f"**{expedition_name}**", f"{done}/{len(route)} stops complete · {remaining} remaining"]
            total_distance = _discord_number(cd.get("expedition_total_distance_ly"), 1)
            if total_distance is not None:
                route_lines.append(f"{total_distance} LY plotted")
            add_field("EXPEDITION", "\n".join(route_lines))

            next_stop = _next_pending_route(cd)
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
        if link_url:
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
