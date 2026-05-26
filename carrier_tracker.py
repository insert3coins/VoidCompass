"""
carrier_tracker.py — Fleet carrier state from Elite Dangerous journal events.
Implements the EDCM status state machine.
Discord webhooks use requests only — no discord.py dependency.
State is persisted to carrier_state.json so it survives app restarts.
"""
import json
import logging
import os
import threading
from datetime import datetime, timezone

CARRIER_STATE_FILE = "carrier_state.json"

# Fields that are safe to persist (skip runtime callbacks etc.)
_PERSIST_KEYS = {
    "carrier_id", "callsign", "name",
    "carrier_purchased_at", "carrier_spawn_system",
    "system", "body",
    "fuel_level", "fuel_capacity",
    "jump_range_curr", "jump_range_max",
    "jump_destination", "jump_body", "jump_departure_time",
    "previous_system", "previous_body",
    "docking_access", "allow_notorious", "pending_decom",
    "balance", "available_balance", "reserve_balance", "reserve_percent",
    "tax_rearm", "tax_refuel", "tax_repair",
    "space_total", "space_cargo", "space_crew", "space_free",
    "space_reserved", "space_ship_packs", "space_module_packs",
    "crew", "trade_orders", "jump_history",
    "notes", "destination_note", "last_updated",
}

_COOLDOWN_SECS = 290  # 4m50s post-departure cooldown window

_DISCORD_COLORS = {
    "jump_plotted":      0x5865F2,   # blurple — departure pending
    "jump_completed":    0x57F287,   # green — arrived
    "jump_cancelled":    0xED4245,   # red — cancelled
    "cooldown_finished": 0x5DADE2,   # blue — ready to jump
    "status_update":     0xFEE75C,   # yellow — manual status post
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


def _discord_relative(ts_str):
    """Return a Discord relative timestamp token, e.g. <t:1234567890:R>."""
    dt = _parse_dt(ts_str)
    if not dt:
        return ""
    return f"<t:{int(dt.timestamp())}:R>"


class CarrierTracker:
    def __init__(self):
        self.carrier_data = {
            "carrier_id": None,
            "callsign": None,
            "name": None,
            "carrier_purchased_at": None,
            "carrier_spawn_system": None,
            "system": None,
            "body": None,
            "status": "idle",          # idle | jumping | cooldown | cooldown_cancel
            "fuel_level": None,
            "fuel_capacity": 1000,
            "jump_range_curr": None,
            "jump_range_max": None,
            "jump_destination": None,
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
            "space_cargo": 0,
            "space_crew": 0,
            "space_free": None,
            "space_reserved": 0,
            "space_ship_packs": 0,
            "space_module_packs": 0,
            "crew": [],
            "trade_orders": [],
            "jump_history": [],
            "notes": "",
            "destination_note": "",
            "last_updated": None,
        }
        self._last_cancel_ts = None
        self._prev_status = "idle"
        self._config = {}
        self.on_updated = None          # callback(carrier_data) — grabbed by CarrierWindow
        self.on_panel_updated = None    # callback(carrier_data) — persistent, used by dashboard panel
        self.on_status_changed = None   # callback(old, new, carrier_data)

    def set_config(self, config):
        self._config = config
        self.load_state()

    def scan_journal_history(self, journal_path, max_files=10):
        """
        One-time startup scan through recent journal files to catch carrier
        events that happened while the app was closed.
        """
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
        }
        trade_events = []

        for filepath in recent:
            file_events = {k: None for k in buckets}
            file_trades = []
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
                        cid = raw.get("CarrierID")
                        if carrier_id and cid and cid != carrier_id:
                            continue
                        if ev == "CarrierStats":
                            file_events["CarrierStats"] = raw
                            if not carrier_id:
                                carrier_id = raw.get("CarrierID")
                        elif ev in ("CarrierLocation", "CarrierJump"):
                            file_events["CarrierLocation"] = raw
                        elif ev == "CarrierJumpRequest":
                            file_events["CarrierJumpRequest"] = raw
                        elif ev == "CarrierJumpCancelled":
                            file_events["CarrierJumpCancelled"] = raw
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
        for t in trade_events:
            replay.append(t)

        if not replay:
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
        finally:
            self.on_updated = orig_on_updated

        self.carrier_data["last_updated"] = (
            datetime.utcnow().isoformat(timespec="seconds") + "Z"
        )
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

    def save_state(self):
        try:
            data = {k: v for k, v in self.carrier_data.items() if k in _PERSIST_KEYS}
            with open(self._state_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
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
            self._update_status()
            self._prev_status = self.carrier_data["status"]
            logging.info(
                f"CarrierTracker: loaded state for "
                f"{self.carrier_data.get('name') or 'unknown carrier'} "
                f"@ {self.carrier_data.get('system') or '?'}"
            )
            self._ensure_status_ticker()
        except Exception as exc:
            logging.warning(f"CarrierTracker: could not load state: {exc}")

    def process_event(self, raw):
        ev = raw.get("event") if isinstance(raw, dict) else None
        if not ev:
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
                self.carrier_data["fuel_level"] = int(total)
                changed = True
        elif ev == "CarrierDockingPermission":
            self.carrier_data["docking_access"] = raw.get("DockingAccess", "all")
            self.carrier_data["allow_notorious"] = bool(raw.get("AllowNotorious", False))
            changed = True
        elif ev == "CarrierNameChanged":
            name = raw.get("Name") or raw.get("CarrierName")
            if name:
                self.carrier_data["name"] = name
                changed = True
        elif ev == "CarrierFinance":
            changed = self._handle_finance(raw)
        elif ev == "CarrierBuy":
            changed = self._handle_carrier_buy(raw)

        if changed:
            self.carrier_data["last_updated"] = (
                datetime.utcnow().isoformat(timespec="seconds") + "Z"
            )
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
        cd["callsign"] = raw.get("Callsign")
        cd["name"] = raw.get("Name")
        cd["docking_access"] = (raw.get("DockingAccess") or "all").lower()
        cd["allow_notorious"] = bool(raw.get("AllowNotorious", False))
        cd["pending_decom"] = bool(raw.get("PendingDecommission", False))

        fuel = raw.get("FuelLevel")
        if fuel is not None:
            cd["fuel_level"] = int(fuel)
        cd["jump_range_curr"] = raw.get("JumpRangeCurr")
        cd["jump_range_max"] = raw.get("JumpRangeMax")

        finance = raw.get("Finance") or {}
        cd["balance"] = finance.get("CarrierBalance")
        cd["available_balance"] = finance.get("AvailableBalance")
        cd["reserve_balance"] = finance.get("ReserveBalance")
        cd["reserve_percent"] = finance.get("ReservePercent")
        cd["tax_rearm"] = finance.get("TaxRate_Rearm")
        cd["tax_refuel"] = finance.get("TaxRate_Refuel")
        cd["tax_repair"] = finance.get("TaxRate_Repair")

        space = raw.get("SpaceUsage") or {}
        cd["space_total"] = space.get("TotalCapacity")
        cd["space_cargo"] = space.get("Cargo") or 0
        cd["space_crew"] = space.get("Crew") or 0
        cd["space_free"] = space.get("FreeSpace")
        cd["space_reserved"] = space.get("ReservedSpace") or 0
        cd["space_ship_packs"] = space.get("ShipPacks") or 0
        cd["space_module_packs"] = space.get("ModulePacks") or 0

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

    def _handle_carrier_buy(self, raw):
        cd = self.carrier_data
        if not cd.get("carrier_id"):
            cd["carrier_id"] = raw.get("CarrierID")
        if not cd.get("callsign"):
            cd["callsign"] = raw.get("Callsign")
        cd["carrier_purchased_at"] = raw.get("timestamp")
        cd["carrier_spawn_system"] = raw.get("Location")
        return True

    def _handle_jump_request(self, raw):
        cd = self.carrier_data
        cd["jump_destination"] = raw.get("SystemName")
        cd["jump_body"] = raw.get("Body")
        cd["jump_departure_time"] = raw.get("DepartureTime")
        self._last_cancel_ts = None
        return True

    def _handle_jump_cancelled(self, raw):
        cd = self.carrier_data
        cd["jump_destination"] = None
        cd["jump_body"] = None
        cd["jump_departure_time"] = None
        ts = _parse_dt(raw.get("timestamp"))
        self._last_cancel_ts = ts if ts else datetime.now(timezone.utc)
        return True

    def _handle_location(self, raw):
        cd = self.carrier_data
        system = raw.get("StarSystem") or raw.get("SystemName")
        body = raw.get("Body")

        if system and system != cd.get("system"):
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
            cd["body"] = body
            cd["jump_destination"] = None
            cd["jump_body"] = None
            # Keep jump_departure_time so _update_status() can compute the
            # post-jump cooldown window; it expires naturally after _COOLDOWN_SECS.
        elif body and body != cd.get("body"):
            cd["body"] = body
        return True

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
            self.carrier_data["last_updated"] = (
                datetime.utcnow().isoformat(timespec="seconds") + "Z"
            )
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
            except Exception:
                pass
        if discord:
            self._maybe_discord(old_status, new_status)

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

        threading.Thread(
            target=self._send_discord,
            args=(url, event_type, dict(self.carrier_data)),
            daemon=True,
        ).start()

    def _send_discord(self, url, event_type, cd):
        try:
            import requests
            name         = cd.get("name")     or "Fleet Carrier"
            callsign     = cd.get("callsign") or "???-???"
            curr_sys     = cd.get("system")            or "Unknown"
            curr_body    = cd.get("body")              or ""
            prev_sys     = cd.get("previous_system")   or "Unknown"
            prev_body    = cd.get("previous_body")     or ""
            dest_sys     = cd.get("jump_destination")  or "TBD"
            dest_body    = cd.get("jump_body")         or ""
            dep_token    = _discord_relative(cd.get("jump_departure_time"))
            note          = (cd.get("notes")            or "").strip()
            dest_note     = (cd.get("destination_note") or "").strip()
            dest_display  = dest_note or "TBD"

            def _loc(system, body):
                # Elite body names are "{SystemName} {index}", so strip the
                # redundant system prefix to avoid "Sol / Sol 3" duplication.
                if body and body.startswith(system):
                    suffix = body[len(system):].strip()
                    return f"**{system}**" + (f" / {suffix}" if suffix else "")
                return f"**{system}**" + (f" / {body}" if body else "")

            if event_type == "jump_plotted":
                lines = [
                    "🚀  **Jump Plotted**",
                    f"📍  **Current Location:** {_loc(curr_sys, curr_body)}",
                    # Real game-plotted jump target — label as "Jump Target" to
                    # distinguish it from the user's stated long-term destination.
                    f"🎯  **Jump Target:** {_loc(dest_sys, dest_body)}",
                ]
                if dep_token:
                    lines.append(f"⏰  **Departing:** {dep_token}")
            elif event_type == "jump_completed":
                lines = [
                    "✅  **Jump Complete**",
                    f"📍  **Arrived At:** {_loc(curr_sys, curr_body)}",
                    f"🔙  **Departed From:** {_loc(prev_sys, prev_body)}",
                ]
            elif event_type == "jump_cancelled":
                lines = [
                    "❌  **Jump Cancelled**",
                    f"📍  **Remaining At:** {_loc(curr_sys, curr_body)}",
                ]
            elif event_type == "cooldown_finished":
                lines = [
                    "🔓  **Cooldown Complete — Ready to Jump**",
                    f"📍  **Location:** {_loc(curr_sys, curr_body)}",
                ]
            elif event_type == "status_update":
                lines = [
                    "📢  **Status Update**",
                    f"📍  **Current Location:** {_loc(curr_sys, curr_body)}",
                ]
                manual_dep_ts = cd.get("_manual_departure_ts")
                if manual_dep_ts:
                    # Show both full date/time (F) and relative (R) so every
                    # reader sees it in their own local timezone automatically.
                    lines.append(
                        f"🕐  **Departure:** <t:{manual_dep_ts}:F> (<t:{manual_dep_ts}:R>)"
                    )
            else:
                lines = [event_type]

            lines.append(f"📌  **Destination:** {dest_display}")
            if note:
                lines.append(f"ℹ️  *{note}*")

            requests.post(
                url,
                json={
                    "username": "Void Compass",
                    "embeds": [{
                        "title": f"{name}  ·  {callsign}",
                        "description": "\n".join(lines),
                        "color": _DISCORD_COLORS.get(event_type, 0x888888),
                        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "footer": {"text": "VoidCompass · Fleet Carrier Tracker"},
                    }],
                },
                timeout=8,
            )
        except Exception:
            pass

    def set_note(self, note: str):
        """Update the operator status note and persist to config."""
        self.carrier_data["notes"] = (note or "").strip()
        self.save_state()
        if callable(self.on_panel_updated):
            try:
                self.on_panel_updated(self.carrier_data)
            except Exception:
                pass

    def set_destination_note(self, destination: str):
        """Update the operator's stated destination and persist."""
        self.carrier_data["destination_note"] = (destination or "").strip()
        self.save_state()
        if callable(self.on_panel_updated):
            try:
                self.on_panel_updated(self.carrier_data)
            except Exception:
                pass

    def send_status_update(self, departure_ts=None):
        """Manually fire a Discord status-update notification with current state.

        departure_ts: optional int Unix timestamp for a manual departure time.
        """
        url = (self._config.get("carrier_discord_webhook_url") or "").strip()
        if not url:
            return False, "No webhook URL configured."
        snapshot = dict(self.carrier_data)
        if departure_ts is not None:
            snapshot["_manual_departure_ts"] = int(departure_ts)
        threading.Thread(
            target=self._send_discord,
            args=(url, "status_update", snapshot),
            daemon=True,
        ).start()
        return True, None

    def send_test_discord(self, url):
        try:
            import requests
            resp = requests.post(
                url.strip(),
                json={
                    "username": "Void Compass",
                    "embeds": [{
                        "title": "Fleet Carrier — Test Notification",
                        "description": "Webhook connection confirmed from Void Compass.",
                        "color": _DISCORD_COLORS["cooldown_finished"],
                    }],
                },
                timeout=8,
            )
            if resp.status_code in (200, 204):
                return True, None
            return False, f"HTTP {resp.status_code}"
        except Exception as exc:
            return False, str(exc)
