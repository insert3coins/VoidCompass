import json
import os
import re
import time
import tkinter as tk
from datetime import datetime

from config import CONFIG_FILE, COLOR_BG, COLOR_PANEL, COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT


class FleetCarrierWatcher:
    def __init__(self, root, config, edsm, waypoint_manager, discord_handler, event_callback, trace_callback=None):
        self.root = root
        self.config = config
        self.edsm = edsm
        self.waypoint_manager = waypoint_manager
        self.discord = discord_handler
        self.event_callback = event_callback
        self.trace_callback = trace_callback

        self.window = None
        self.name_entry = None
        self.status_entry = None
        self.destination_entry = None
        self.departure_entry = None
        self.preview_text = None

        self.watch_name = self.config.get("fc_watch_name", "").strip()
        self.watch_status = self.config.get("fc_watch_status", "").strip()
        self.watch_destination = self.config.get("fc_watch_destination", "").strip()
        self.watch_departure = self.config.get("fc_watch_departure", "").strip()
        state = self.config.get("fc_watch_state", {})
        self.watch_state = state if isinstance(state, dict) else {}
        if self.watch_state.get("resolved_name") is None:
            self.watch_state["resolved_name"] = ""
        if self.watch_state.get("carrier_id") is None:
            self.watch_state["carrier_id"] = None
        if self.watch_state.get("last_change") is None:
            self.watch_state["last_change"] = ""
        self._session_start_ts = time.time()
        self._startup_dispatch_job = None
        self._startup_dispatch_reason = ""
        self._distance_job = 0
        self._last_journal_rescan_ts = 0.0
        self._journal_rescan_cooldown_s = 30.0

    def _emit_event(self, tag, message, severity="INFO", copy_text=None, url=None, pinned=False):
        if not callable(self.event_callback) or not message:
            return
        try:
            self.event_callback(tag, message, severity=severity, copy_text=copy_text, url=url, pinned=pinned)
        except TypeError:
            self.event_callback(tag, message, severity=severity, copy_text=copy_text, pinned=pinned)
        except Exception:
            pass

    def _save_config(self):
        self.config["fc_watch_name"] = self.watch_name
        self.config["fc_watch_status"] = self.watch_status
        self.config["fc_watch_destination"] = self.watch_destination
        self.config["fc_watch_departure"] = self.watch_departure
        self.config["fc_watch_state"] = self.watch_state
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass

    @staticmethod
    def _parse_manual_departure(raw_value):
        text = str(raw_value or "").strip()
        if not text:
            return None
        # Unix epoch seconds are accepted for exact control.
        if text.isdigit():
            try:
                return float(text)
            except Exception:
                return None
        # Accept common local-time formats.
        candidates = (
            text,
            text.replace("T", " "),
            text.replace("/", "-"),
        )
        formats = (
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%y %H:%M",
            "%d/%m/%y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d-%m-%y %H:%M",
            "%d-%m-%y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d-%m-%Y %H:%M:%S",
        )
        for candidate in candidates:
            for fmt in formats:
                try:
                    return datetime.strptime(candidate, fmt).timestamp()
                except Exception:
                    pass
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        except Exception:
            return None

    @staticmethod
    def _format_departed(ts):
        try:
            dt = datetime.fromtimestamp(ts)
            return dt.strftime("%A, %d %B %Y %-I:%M %p").replace("AM", "am").replace("PM", "pm")
        except Exception:
            return "unknown time"

    @staticmethod
    def _format_changed_ago(ts):
        try:
            delta = max(int(time.time() - ts), 0)
        except Exception:
            return "unknown"
        if delta < 60:
            return "just now"
        if delta < 3600:
            mins = delta // 60
            return f"{mins} minute{'s' if mins != 1 else ''} ago"
        if delta < 86400:
            hrs = delta // 3600
            return f"{hrs} hour{'s' if hrs != 1 else ''} ago"
        days = delta // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"

    def _matches_watched(self, raw):
        watched = (self.watch_name or "").strip().lower()
        if not isinstance(raw, dict):
            return False
        # If we've already resolved a carrier id, trust that over text matching.
        known_id = self.watch_state.get("carrier_id")
        raw_id = raw.get("CarrierID")
        if known_id is not None and raw_id is not None:
            try:
                if int(raw_id) == int(known_id):
                    return True
            except Exception:
                pass
        if not watched:
            return False
        for key in ("StationName", "CarrierName", "Callsign", "CallSign", "Name", "CarrierID", "Carrier"):
            val = raw.get(key)
            if val and watched in str(val).lower():
                return True
        return False

    def _extract_carrier_display_name(self, raw):
        if not isinstance(raw, dict):
            return None
        carrier_name = raw.get("CarrierName")
        station_name = raw.get("StationName")
        explicit_name = raw.get("Name")
        callsign = raw.get("Callsign") or raw.get("CarrierID")

        base_name = None
        for candidate in (carrier_name, station_name, explicit_name):
            if isinstance(candidate, str) and candidate.strip():
                base_name = candidate.strip()
                break

        if isinstance(callsign, str):
            callsign = callsign.strip().upper()
        else:
            callsign = None

        if base_name and callsign and callsign not in base_name.upper():
            return f"{base_name} - {callsign}"
        if base_name:
            return base_name
        if callsign:
            return callsign
        return None

    def _update_resolved_name(self, raw):
        resolved = self._extract_carrier_display_name(raw)
        changed = False
        raw_id = raw.get("CarrierID")
        if raw_id is not None:
            try:
                raw_id = int(raw_id)
                if self.watch_state.get("carrier_id") != raw_id:
                    self.watch_state["carrier_id"] = raw_id
                    changed = True
            except Exception:
                pass
        if not resolved:
            return changed
        if self.watch_state.get("resolved_name") != resolved:
            self.watch_state["resolved_name"] = resolved
            changed = True
        return changed

    @staticmethod
    def _extract_system_name(raw):
        if not isinstance(raw, dict):
            return None
        for key in ("StarSystem", "SystemName", "Location", "System", "LastSystem"):
            val = raw.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        return None

    @staticmethod
    def _parse_journal_ts(raw):
        ts = raw.get("timestamp")
        if not isinstance(ts, str):
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except Exception:
            return None

    def _scan_journal_for_watched(self, max_files=30):
        t0 = time.perf_counter()
        if not self.watch_name:
            return False, False
        journal_path = self.config.get("journal_path")
        if not journal_path or not os.path.isdir(journal_path):
            return False, False

        try:
            files = sorted(
                os.path.join(journal_path, f)
                for f in os.listdir(journal_path)
                if f.startswith("Journal.") and f.endswith(".log")
            )
        except Exception:
            return False, False
        if not files:
            return False, False

        files = files[-max_files:]
        latest_loc_ts = None
        latest_loc_name = None
        latest_request_ts = None
        latest_request_dest = None
        latest_arrival_ts = None
        latest_arrival_sys = None
        latest_cancel_ts = None
        latest_name_ts = None
        found_any_match = False

        known_id = self.watch_state.get("carrier_id")
        seen_ids = set()
        if known_id is not None:
            seen_ids.add(int(known_id))

        # Pass 1: collect matching carrier ids from text-based hits (e.g. CarrierStats with callsign/name).
        for path in files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            raw = json.loads(line)
                        except Exception:
                            continue
                        if not isinstance(raw, dict):
                            continue
                        if not self._matches_watched(raw):
                            continue
                        cid = raw.get("CarrierID")
                        if cid is None:
                            continue
                        try:
                            seen_ids.add(int(cid))
                        except Exception:
                            pass
            except Exception:
                continue

        # Pass 2: process full carrier timeline, allowing CarrierID matches even when text fields are absent.
        for path in files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            raw = json.loads(line)
                        except Exception:
                            continue
                        if not isinstance(raw, dict):
                            continue
                        raw_id = raw.get("CarrierID")
                        id_match = False
                        if raw_id is not None:
                            try:
                                id_match = int(raw_id) in seen_ids
                            except Exception:
                                id_match = False
                        if not (self._matches_watched(raw) or id_match):
                            continue
                        found_any_match = True
                        ev = raw.get("event")
                        ts = self._parse_journal_ts(raw) or time.time()
                        if self._update_resolved_name(raw):
                            if latest_name_ts is None or ts >= latest_name_ts:
                                latest_name_ts = ts

                        if ev in ("CarrierLocation",):
                            sys_name = self._extract_system_name(raw)
                            if sys_name and (latest_loc_ts is None or ts >= latest_loc_ts):
                                latest_loc_ts = ts
                                latest_loc_name = sys_name

                        elif ev == "Location" and raw.get("Docked") and raw.get("StationType") == "FleetCarrier":
                            sys_name = self._extract_system_name(raw)
                            if sys_name and (latest_loc_ts is None or ts >= latest_loc_ts):
                                latest_loc_ts = ts
                                latest_loc_name = sys_name

                        elif ev == "Docked" and raw.get("StationType") == "FleetCarrier":
                            sys_name = self._extract_system_name(raw)
                            if sys_name and (latest_loc_ts is None or ts >= latest_loc_ts):
                                latest_loc_ts = ts
                                latest_loc_name = sys_name

                        elif ev == "CarrierJumpRequest":
                            dest = raw.get("SystemName") or raw.get("StarSystem") or raw.get("Body") or raw.get("Location")
                            if latest_request_ts is None or ts >= latest_request_ts:
                                latest_request_ts = ts
                                latest_request_dest = dest

                        elif ev == "CarrierJump":
                            sys_name = self._extract_system_name(raw)
                            if sys_name and (latest_arrival_ts is None or ts >= latest_arrival_ts):
                                latest_arrival_ts = ts
                                latest_arrival_sys = sys_name
                        elif ev == "CarrierJumpCancelled":
                            if latest_cancel_ts is None or ts >= latest_cancel_ts:
                                latest_cancel_ts = ts
            except Exception:
                continue

        changed = False

        latest_settled_ts = latest_loc_ts
        latest_settled_loc = latest_loc_name
        if latest_arrival_ts is not None and (latest_settled_ts is None or latest_arrival_ts >= latest_settled_ts):
            latest_settled_ts = latest_arrival_ts
            latest_settled_loc = latest_arrival_sys

        if latest_settled_loc:
            if self.watch_state.get("last_location") != latest_settled_loc:
                self.watch_state["last_location"] = latest_settled_loc
                changed = True
            if latest_settled_ts and self.watch_state.get("last_location_ts") != latest_settled_ts:
                self.watch_state["last_location_ts"] = latest_settled_ts
                changed = True

        in_transit = False
        if latest_request_ts is not None and (latest_settled_ts is None or latest_request_ts > latest_settled_ts):
            in_transit = True
        if latest_cancel_ts is not None and latest_request_ts is not None and latest_cancel_ts >= latest_request_ts:
            in_transit = False

        if self.watch_state.get("in_transit") != in_transit:
            self.watch_state["in_transit"] = in_transit
            changed = True

        if in_transit:
            if self.watch_state.get("departed_ts") != latest_request_ts:
                self.watch_state["departed_ts"] = latest_request_ts
                changed = True
            if latest_request_dest and self.watch_state.get("destination") != latest_request_dest:
                self.watch_state["destination"] = latest_request_dest
                changed = True
        else:
            if self.watch_state.get("departed_ts") is not None:
                self.watch_state["departed_ts"] = None
                changed = True

        if changed:
            self.watch_state["destination_distance_ly"] = None
            self.watch_state["current_target_distance_ly"] = None
            self._save_config()
            self._update_distance_async()
            self._emit_event("SYSTEM", "Fleet watcher journal scan refreshed", severity="INFO", copy_text=self.watch_name)
        if callable(self.trace_callback):
            try:
                self.trace_callback("fleet.scan_journal_for_watched", (time.perf_counter() - t0) * 1000.0)
            except Exception:
                pass
        return changed, found_any_match

    def _update_distance_async(self):
        last_loc = self.watch_state.get("last_location")
        heading_dest = self.watch_destination or None
        current_target = self.watch_state.get("destination")
        if not last_loc:
            self.watch_state["destination_distance_ly"] = None
            self.watch_state["current_target_distance_ly"] = None
            return
        if not (heading_dest or current_target):
            self.watch_state["destination_distance_ly"] = None
            self.watch_state["current_target_distance_ly"] = None
            return
        self._distance_job += 1
        job_id = self._distance_job

        def _loc_cb(_name1, c1):
            if job_id != self._distance_job:
                return

            pending = 0
            heading_done = False
            target_done = False

            def _finish_if_ready():
                if heading_done and target_done:
                    self._save_config()
                    self._refresh_preview()
                    if not self._startup_dispatch_reason:
                        self._dispatch_discord("Distance recalculated")

            def _calc_distance_and_store(c2, key):
                if c1 and c2:
                    try:
                        d = self.waypoint_manager.get_distance(c1, c2)
                        self.watch_state[key] = round(d, 1)
                    except Exception:
                        self.watch_state[key] = None
                else:
                    self.watch_state[key] = None

            def _heading_cb(_name2, c2):
                if job_id != self._distance_job:
                    return
                nonlocal heading_done
                _calc_distance_and_store(c2, "destination_distance_ly")
                heading_done = True
                _finish_if_ready()

            def _target_cb(_name2, c2):
                if job_id != self._distance_job:
                    return
                nonlocal target_done
                _calc_distance_and_store(c2, "current_target_distance_ly")
                target_done = True
                _finish_if_ready()

            if heading_dest:
                pending += 1
                self.edsm.fetch_system_coords(heading_dest, _heading_cb)
            else:
                self.watch_state["destination_distance_ly"] = None
                heading_done = True

            if current_target and current_target != heading_dest:
                pending += 1
                self.edsm.fetch_system_coords(current_target, _target_cb)
            else:
                # If heading and current target are the same, reuse heading distance.
                self.watch_state["current_target_distance_ly"] = self.watch_state.get("destination_distance_ly")
                target_done = True

            if pending == 0:
                _finish_if_ready()

        self.edsm.fetch_system_coords(last_loc, _loc_cb)

    def _dispatch_discord(self, reason):
        payload = self.build_discord_state()
        payload["refresh_reason"] = reason or "Watcher refresh"
        self.discord.update_fleet_carrier(payload)

    def _is_historical_event(self, raw):
        ts = self._parse_journal_ts(raw) if isinstance(raw, dict) else None
        return bool(ts and ts < (self._session_start_ts - 2))

    def _buffer_startup_dispatch(self, reason):
        self._startup_dispatch_reason = reason or "Journal sync"
        if self._startup_dispatch_job and self.root:
            try:
                self.root.after_cancel(self._startup_dispatch_job)
            except Exception:
                pass
        if not self.root:
            return
        self._startup_dispatch_job = self.root.after(1200, self._flush_startup_dispatch)

    def _flush_startup_dispatch(self):
        self._startup_dispatch_job = None
        if not self._startup_dispatch_reason:
            return
        reason = self._startup_dispatch_reason
        self._startup_dispatch_reason = ""
        self._dispatch_discord(f"Startup sync: {reason}")

    def _dispatch_from_event(self, reason, raw):
        if self._is_historical_event(raw):
            self._buffer_startup_dispatch(reason)
            return
        # Live event arrived; cancel any pending startup flush.
        self._startup_dispatch_reason = ""
        if self._startup_dispatch_job and self.root:
            try:
                self.root.after_cancel(self._startup_dispatch_job)
            except Exception:
                pass
            self._startup_dispatch_job = None
        self._dispatch_discord(reason)

    def build_discord_state(self):
        resolved_name = (self.watch_state.get("resolved_name") or "").strip()
        name = resolved_name or self.watch_name or "UNSET CARRIER"
        callsign = None
        for src in (self.watch_name, resolved_name, str(self.watch_state.get("carrier_id") or "")):
            if not isinstance(src, str):
                continue
            m = re.search(r"\b([A-Z0-9]{3}-[A-Z0-9]{3})\b", src.upper())
            if m:
                callsign = m.group(1)
                break
        loc = self.watch_state.get("last_location")
        loc_ts = self.watch_state.get("last_location_ts")
        in_transit_flag = bool(self.watch_state.get("in_transit"))
        journal_departed_ts = self.watch_state.get("departed_ts")
        manual_departed_ts = self._parse_manual_departure(self.watch_departure)
        departed_ts = manual_departed_ts if manual_departed_ts is not None else journal_departed_ts
        destination = self.watch_destination or self.watch_state.get("destination")
        journal_destination = self.watch_state.get("destination")
        dist_ly = self.watch_state.get("destination_distance_ly")
        current_target_dist_ly = self.watch_state.get("current_target_distance_ly")
        last_change = str(self.watch_state.get("last_change") or "").strip()
        status_note = (self.watch_status or self.watch_state.get("status_note") or "").strip()

        now_ts = time.time()
        is_scheduled = bool(in_transit_flag and departed_ts and departed_ts > now_ts)
        is_in_transit = bool(in_transit_flag and not is_scheduled)
        movement_state = "scheduled" if is_scheduled else ("in_transit" if is_in_transit else "idle")
        # Once the carrier is no longer moving, "current target" should reflect where it is now.
        if not (is_scheduled or is_in_transit) and loc:
            journal_destination = loc

        lines = [f"Fleet Carrier Status: {name}"]
        if loc:
            changed = self._format_changed_ago(loc_ts) if loc_ts else "unknown"
            lines.append(f"📍 Last Known Location: {loc} (changed {changed})")
        else:
            lines.append("📍 Last Known Location: Unknown")

        if is_scheduled:
            depart_text = self._format_departed(departed_ts) if departed_ts else "unknown time"
            lines.append(f"🚀 Jump Scheduled (departs {depart_text})")
        elif is_in_transit:
            departed_text = self._format_departed(departed_ts) if departed_ts else "unknown time"
            lines.append(f"🚀 In Transit (departed {departed_text})")
        else:
            lines.append("🚀 Not In Transit")

        if destination:
            dist_txt = f" ({dist_ly:,.1f} ly)" if isinstance(dist_ly, (int, float)) else ""
            lines.append(f"📌 Destination: {destination}{dist_txt}")
        else:
            lines.append("📌 Destination: Unknown")

        if status_note:
            lines.append(f"ℹ️ Status: {status_note}")
        edsm_url = None
        if loc:
            edsm_url = f"https://www.edsm.net/show-system?systemName={loc.replace(' ', '+')}"

        return {
            "name": name,
            "lines": lines,
            "edsm_url": edsm_url,
            "location": loc,
            "status_note": status_note,
            "callsign": callsign,
            "location_changed_ago": self._format_changed_ago(loc_ts) if loc_ts else None,
            "in_transit": is_in_transit,
            "movement_state": movement_state,
            "departed_ts": departed_ts,
            "departed_text": self._format_departed(departed_ts) if departed_ts else None,
            "destination": destination,
            "manual_heading": self.watch_destination or None,
            "manual_heading_distance_ly": dist_ly if self.watch_destination else None,
            "journal_destination": journal_destination,
            "destination_distance_ly": dist_ly,
            "status_change": last_change or "No recent fleet carrier change.",
            "jump_target": journal_destination or destination or "TBD",
            "jump_target_distance_ly": current_target_dist_ly if journal_destination else dist_ly,
            "current_target_distance_ly": current_target_dist_ly,
            "refresh_reason": "Watcher refresh",
        }

    def _refresh_preview(self):
        if not self.window or not self.window.winfo_exists():
            return
        payload = self.build_discord_state()
        preview = "\n".join(payload.get("lines", []))
        try:
            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert("1.0", preview)
            self.preview_text.config(state=tk.DISABLED)
        except Exception:
            pass

    def open_window(self):
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("FLEET CARRIER WATCHER")
        dlg.geometry(self.config.get("fleet_carrier_watcher_geometry", "620x520"))
        dlg.minsize(620, 520)
        dlg.configure(bg=COLOR_BG)
        dlg.grab_set()
        self.window = dlg

        tk.Label(dlg, text=" // FLEET CARRIER WATCHER", font=("Courier", 13, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG).pack(anchor="w", padx=14, pady=(12, 8))

        row1 = tk.Frame(dlg, bg=COLOR_BG)
        row1.pack(fill=tk.X, padx=14, pady=(4, 6))
        tk.Label(row1, text="Carrier Name / Callsign:", font=("Courier", 9), fg="#aaa", bg=COLOR_BG).pack(anchor="w")
        self.name_entry = tk.Entry(row1, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.name_entry.pack(fill=tk.X, pady=(2, 0), ipady=4)
        self.name_entry.insert(0, self.watch_name)

        row2 = tk.Frame(dlg, bg=COLOR_BG)
        row2.pack(fill=tk.X, padx=14, pady=(4, 6))
        tk.Label(row2, text="Status Note:", font=("Courier", 9), fg="#aaa", bg=COLOR_BG).pack(anchor="w")
        self.status_entry = tk.Entry(row2, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.status_entry.pack(fill=tk.X, pady=(2, 0), ipady=4)
        self.status_entry.insert(0, self.watch_status)

        row3 = tk.Frame(dlg, bg=COLOR_BG)
        row3.pack(fill=tk.X, padx=14, pady=(4, 6))
        tk.Label(row3, text="Destination (optional, auto from journal if empty):", font=("Courier", 9), fg="#aaa", bg=COLOR_BG).pack(anchor="w")
        self.destination_entry = tk.Entry(row3, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.destination_entry.pack(fill=tk.X, pady=(2, 0), ipady=4)
        self.destination_entry.insert(0, self.watch_destination)

        row4 = tk.Frame(dlg, bg=COLOR_BG)
        row4.pack(fill=tk.X, padx=14, pady=(4, 6))
        tk.Label(row4, text="Departure (optional: DD/MM/YY HH:MM, 24h local):", font=("Courier", 9), fg="#aaa", bg=COLOR_BG).pack(anchor="w")
        self.departure_entry = tk.Entry(row4, bg="#111", fg=COLOR_TEXT, font=("Courier", 10), insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.departure_entry.pack(fill=tk.X, pady=(2, 0), ipady=4)
        self.departure_entry.insert(0, self.watch_departure)

        tk.Label(dlg, text="Discord Preview:", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_BG).pack(anchor="w", padx=14, pady=(8, 4))
        self.preview_text = tk.Text(dlg, bg="#111", fg=COLOR_TEXT, font=("Courier", 9), height=10, relief=tk.FLAT, highlightthickness=1, highlightbackground="#333", wrap=tk.WORD)
        self.preview_text.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))
        self.preview_text.config(state=tk.DISABLED)
        self._refresh_preview()

        btn_row = tk.Frame(dlg, bg=COLOR_BG)
        btn_row.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=(0, 12))

        def _save():
            self.watch_name = self.name_entry.get().strip()
            self.watch_status = self.status_entry.get().strip()
            self.watch_destination = self.destination_entry.get().strip()
            self.watch_departure = self.departure_entry.get().strip()
            self.watch_state["status_note"] = self.watch_status
            self._save_config()
            _changed, found = self._scan_journal_for_watched()
            if not found:
                self._emit_event("ALERT", f"No journal matches found for carrier: {self.watch_name or 'UNSET'}", severity="WARN", copy_text=self.watch_name or "")
            if self.watch_departure and self._parse_manual_departure(self.watch_departure) is None:
                self._emit_event("ALERT", "Invalid departure format. Use YYYY-MM-DD HH:MM or epoch seconds.", severity="WARN", copy_text=self.watch_departure)
            self._update_distance_async()
            self._refresh_preview()
            self._emit_event("SYSTEM", f"Fleet watcher updated: {self.watch_name or 'UNSET'}", severity="INFO", copy_text=self.watch_name or "")
            self._dispatch_discord("Manual update (OK)")

        def _push():
            # Mirror save semantics so PUSH UPDATE uses current form values.
            self.watch_name = self.name_entry.get().strip()
            self.watch_status = self.status_entry.get().strip()
            self.watch_destination = self.destination_entry.get().strip()
            self.watch_departure = self.departure_entry.get().strip()
            self.watch_state["status_note"] = self.watch_status
            self._save_config()
            _changed, found = self._scan_journal_for_watched()
            if not found:
                self._emit_event("ALERT", f"No journal matches found for carrier: {self.watch_name or 'UNSET'}", severity="WARN", copy_text=self.watch_name or "")
            if self.watch_departure and self._parse_manual_departure(self.watch_departure) is None:
                self._emit_event("ALERT", "Invalid departure format. Use YYYY-MM-DD HH:MM or epoch seconds.", severity="WARN", copy_text=self.watch_departure)
            self._update_distance_async()
            self._refresh_preview()
            self._dispatch_discord("Manual push update")
            self._emit_event("SYSTEM", "Fleet watcher pushed to Discord", severity="INFO")

        def _cancel():
            self.config["fleet_carrier_watcher_geometry"] = dlg.geometry()
            self._save_config()
            dlg.destroy()

        def _ok():
            _save()
            _cancel()

        tk.Button(btn_row, text="CANCEL", command=_cancel, bg="#222", fg="#888", font=("Courier", 9, "bold"), relief=tk.FLAT, width=10).pack(side=tk.LEFT)
        tk.Button(btn_row, text="PUSH UPDATE", command=_push, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 9, "bold"), relief=tk.FLAT, width=14).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="OK", command=_ok, bg=COLOR_ACCENT, fg="black", font=("Courier", 9, "bold"), relief=tk.FLAT, width=10).pack(side=tk.RIGHT)
        dlg.protocol("WM_DELETE_WINDOW", _cancel)

    def process_event(self, ev, raw, d, current_sys):
        t0 = time.perf_counter()
        if not self.watch_name:
            return
        if not isinstance(raw, dict):
            return

        matched = self._matches_watched(raw)
        if not matched and ev in ("CarrierStats", "CarrierLocation", "CarrierJumpRequest", "CarrierJump", "CarrierJumpCancelled", "CarrierNameChanged"):
            # Fallback: refresh id/name mapping from recent journals, then re-check match.
            now = time.time()
            if (now - self._last_journal_rescan_ts) >= self._journal_rescan_cooldown_s:
                self._last_journal_rescan_ts = now
                self._scan_journal_for_watched(max_files=3)
            matched = self._matches_watched(raw)
        if not matched and ev in ("CarrierJump", "CarrierJumpCancelled"):
            # Some jump-complete/cancel journal variants omit callsign/name fields.
            # If we have an active tracked jump, treat it as our watched carrier.
            if self.watch_state.get("in_transit"):
                matched = True
            else:
                known_id = self.watch_state.get("carrier_id")
                raw_id = raw.get("CarrierID")
                if known_id is not None and raw_id is not None:
                    try:
                        matched = int(known_id) == int(raw_id)
                    except Exception:
                        matched = False
        if not matched:
            return

        name_changed = self._update_resolved_name(raw)
        if name_changed:
            self._save_config()
            self._emit_event("SYSTEM", f"Carrier name resolved: {self.watch_state.get('resolved_name')}", severity="INFO", copy_text=self.watch_state.get("resolved_name"))

        if ev == "CarrierStats":
            # Useful for resolving carrier name/callsign even when location doesn't change.
            self.watch_state["last_change"] = "Carrier stats updated"
            self._save_config()
            self._refresh_preview()
            self._dispatch_from_event("Journal event: CarrierStats", raw)
            return

        if ev == "CarrierLocation":
            sys_name = self._extract_system_name(raw) or current_sys
            self.watch_state["last_location"] = sys_name
            self.watch_state["last_location_ts"] = self._parse_journal_ts(raw) or time.time()
            self.watch_state["in_transit"] = False
            self.watch_state["destination"] = sys_name
            self.watch_state["last_change"] = f"Location updated: {sys_name}"
            self._save_config()
            self._emit_event("SYSTEM", f"Carrier location update: {sys_name}", severity="INFO", copy_text=sys_name)
            self._refresh_preview()
            self._dispatch_from_event("Journal event: CarrierLocation", raw)
            return

        if ev == "Docked":
            station_type = raw.get("StationType")
            station_name = raw.get("StationName")
            if station_type == "FleetCarrier":
                sys_name = raw.get("StarSystem") or current_sys
                self.watch_state["last_location"] = sys_name
                self.watch_state["last_location_ts"] = time.time()
                self.watch_state["in_transit"] = False
                self.watch_state["destination"] = None
                self.watch_state["destination_distance_ly"] = None
                self.watch_state["current_target_distance_ly"] = None
                self.watch_state["last_change"] = f"Docked at carrier in {sys_name}"
                self._save_config()
                self._emit_event("SYSTEM", f"Carrier docked at {sys_name}", severity="INFO", copy_text=station_name or self.watch_name)
                self._refresh_preview()
                self._dispatch_from_event("Journal event: Docked", raw)
                return

        if ev == "Location" and raw.get("Docked") and raw.get("StationType") == "FleetCarrier":
            sys_name = self._extract_system_name(raw) or current_sys
            self.watch_state["last_location"] = sys_name
            self.watch_state["last_location_ts"] = self._parse_journal_ts(raw) or time.time()
            self.watch_state["in_transit"] = False
            self.watch_state["destination"] = sys_name
            self.watch_state["last_change"] = f"Location updated: {sys_name}"
            self._save_config()
            self._emit_event("SYSTEM", f"Carrier location update: {sys_name}", severity="INFO", copy_text=sys_name)
            self._refresh_preview()
            self._dispatch_from_event("Journal event: Location", raw)
            return

        if ev == "CarrierJumpRequest":
            dest = raw.get("SystemName") or raw.get("StarSystem") or raw.get("Body")
            dep_time = raw.get("DepartureTime")
            dep_ts = time.time()
            if isinstance(dep_time, str):
                try:
                    dep_ts = datetime.fromisoformat(dep_time.replace("Z", "+00:00")).timestamp()
                except Exception:
                    pass
            self.watch_state["in_transit"] = True
            self.watch_state["departed_ts"] = dep_ts
            self.watch_state["destination"] = dest
            self.watch_state["last_change"] = f"Jump scheduled -> {dest or 'Unknown'}"
            self._save_config()
            self._update_distance_async()
            self._emit_event("SYSTEM", f"Carrier jump requested to {dest or 'Unknown'}", severity="WARN", copy_text=dest or self.watch_name)
            self._refresh_preview()
            self._dispatch_from_event("Journal event: CarrierJumpRequest", raw)
            return

        if ev == "CarrierJump":
            arrived = raw.get("StarSystem") or d.get("star_system") or current_sys
            previous_dest = self.watch_state.get("destination")
            self.watch_state["last_location"] = arrived
            self.watch_state["last_location_ts"] = time.time()
            self.watch_state["in_transit"] = False
            self.watch_state["destination"] = arrived
            self.watch_state["last_change"] = f"Jump complete -> {arrived}"
            self._save_config()
            self._update_distance_async()
            if previous_dest and str(previous_dest).strip() and str(previous_dest).strip() != str(arrived).strip():
                self._emit_event(
                    "FLEET",
                    f"Carrier jump completed: {previous_dest} -> {arrived}",
                    severity="INFO",
                    copy_text=arrived,
                )
            self._emit_event("SYSTEM", f"Carrier arrived in {arrived}", severity="INFO", copy_text=arrived)
            self._refresh_preview()
            self._dispatch_from_event("Journal event: CarrierJump", raw)
            return

        if ev == "CarrierNameChanged":
            if name_changed:
                self._save_config()
                self._refresh_preview()
                self._dispatch_from_event("Journal event: CarrierNameChanged", raw)
            return

        if ev == "CarrierJumpCancelled":
            self.watch_state["in_transit"] = False
            self.watch_state["departed_ts"] = None
            self.watch_state["destination"] = None
            self.watch_state["destination_distance_ly"] = None
            self.watch_state["current_target_distance_ly"] = None
            self.watch_state["last_change"] = "Jump cancelled"
            self._save_config()
            self._emit_event("SYSTEM", "Carrier jump cancelled", severity="WARN", copy_text=self.watch_name)
            self._refresh_preview()
            self._dispatch_from_event("Journal event: CarrierJumpCancelled", raw)
        if callable(self.trace_callback):
            try:
                self.trace_callback(f"fleet.process_event:{ev}", (time.perf_counter() - t0) * 1000.0)
            except Exception:
                pass
