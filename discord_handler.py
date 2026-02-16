import time
import threading
import requests
import logging
import math
import json
import hashlib
from datetime import datetime, timezone
from urllib.parse import quote_plus
from config import CONFIG_FILE
from version import APP_VERSION

class DiscordHandler:
    def __init__(self, config, root):
        self.config = config
        self.root = root
        self.last_update = 0
        self.update_timer = None
        self.msg_id = config.get("discord_msg_id", "")
        self.msg_system = config.get("discord_msg_system", "")
        self.last_payload_sig = ""
        self.last_scanned = None
        self.last_traffic_total = None
        self.alerted_valuable_bodies = set()
        self.fc_msg_id = config.get("discord_fc_msg_id", "")
        self.fc_last_status_note = config.get("discord_fc_last_status_note", "")
        cached_fc_state = config.get("discord_fc_last_state", {})
        self.fc_last_state = cached_fc_state if isinstance(cached_fc_state, dict) else {}

    @staticmethod
    def _fmt_num(value):
        try:
            return f"{int(value):,}"
        except Exception:
            return "0"

    def _build_title(self, event_data):
        return "Live Update"

    def _build_payload(self, event_data, state):
        title = self._build_title(event_data)
        event_type = event_data.get("event") if event_data else None

        current_sys = state.get("current_sys", "---")
        sys_url = f"https://www.edsm.net/show-system?systemName={current_sys.replace(' ', '+')}"
        cmdr = state.get("cmdr_name", "CMDR")
        star = state.get("star_class")

        scanned = int(state.get("scanned", 0) or 0)
        total = int(state.get("total", 0) or 0)
        pct = int((scanned / total) * 100) if total > 0 else 0
        progress_delta = scanned - self.last_scanned if self.last_scanned is not None else 0
        progress_trend = f"+{progress_delta}" if progress_delta > 0 else "0"

        traffic = state.get("system_traffic", {}) or {}
        t_day = int(traffic.get("day", 0) or 0)
        t_week = int(traffic.get("week", 0) or 0)
        t_total = int(traffic.get("total", 0) or 0)
        traffic_delta = t_total - self.last_traffic_total if self.last_traffic_total is not None else 0
        traffic_arrow = "↑" if traffic_delta > 0 else ("↓" if traffic_delta < 0 else "→")
        traffic_trend = f"{traffic_arrow}{abs(traffic_delta)}"
        dest_name = state.get("dest_name")

        nav_text = "NO ROUTE"
        if dest_name:
            try:
                curr = state.get("current_coords", [0, 0, 0])
                dest = state.get("dest_coords", [0, 0, 0])
                d = math.sqrt(sum((a - b) ** 2 for a, b in zip(curr, dest)))
                nav_text = f"{dest_name} ({d:,.1f} LY)"
            except Exception:
                nav_text = f"{str(dest_name)}"

        is_valuable_scan = (
            event_type == "Scan" and
            (
                event_data.get("PlanetClass") in ("Earthlike body", "Water world", "Ammonia world") or
                event_data.get("TerraformState") == "Terraformable"
            )
        )
        color_map = {
            "FSDJump": 0x4DA3FF,
            "Scan": 0x00D1FF,
            "FSSDiscoveryScan": 0x7AA2F7,
        }
        if is_valuable_scan:
            embed_color = 0x00FF41
        else:
            embed_color = color_map.get(event_type, 0x00D1FF)

        ops_lines = [
            f"CMDR: {cmdr}",
            f"SYSTEM: {current_sys} [{str(star).upper() if star else 'UNKNOWN'}]",
            f"ROUTE: {dest_name if dest_name else 'INACTIVE'}",
        ]

        fields = [
            {"name": "System Link", "value": f"[{current_sys}]({sys_url})", "inline": False},
            {"name": "Navigation", "value": nav_text, "inline": True},
            {"name": "Exploration", "value": f"{self._fmt_num(scanned)} / {self._fmt_num(total)} ({pct}%) | {progress_trend}", "inline": True},
            {"name": "Traffic", "value": f"24h {self._fmt_num(t_day)} | 7d {self._fmt_num(t_week)} | total {self._fmt_num(t_total)} | {traffic_trend}", "inline": False},
        ]

        return {
            "embeds": [{
                "title": str(title)[:256],
                "description": "\n".join(ops_lines),
                "color": embed_color,
                "fields": fields,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {"text": f"VOID COMPASS v{APP_VERSION}"}
            }]
        }

    def _build_valuable_alert_payload(self, event_data, state):
        if not event_data or event_data.get("event") != "Scan":
            return None

        planet_class = event_data.get("PlanetClass")
        terraformable = event_data.get("TerraformState") == "Terraformable"
        if planet_class not in ("Earthlike body", "Water world", "Ammonia world") and not terraformable:
            return None

        body_name = event_data.get("BodyName", "Unknown Body")
        if body_name in self.alerted_valuable_bodies:
            return None
        self.alerted_valuable_bodies.add(body_name)

        if planet_class == "Earthlike body":
            icon = "🌍"
            label = "Earthlike World"
        elif planet_class == "Water world":
            icon = "💧"
            label = "Water World"
        elif planet_class == "Ammonia world":
            icon = "☣️"
            label = "Ammonia World"
        else:
            icon = "🛠️"
            label = "Terraformable"

        current_sys = state.get("current_sys", "---")
        sys_url = f"https://www.edsm.net/show-system?systemName={current_sys.replace(' ', '+')}"
        return {
            "embeds": [{
                "title": f"{icon} Valuable Discovery",
                "description": f"{label}: **{body_name}**\nSystem: [{current_sys}]({sys_url})",
                "color": 0x00FF41,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {"text": f"VOID COMPASS v{APP_VERSION}"}
            }]
        }

    def update_live(self, event_data, state):
        if not self.config.get("discord_enabled", True):
            return
        if not self.config.get("discord_live_enabled", True):
            return
        webhook = self.config.get("discord_webhook")
        if not webhook: return
        if event_data and event_data.get("event") == "ScanOrganic":
            return

        if self.update_timer:
            self.root.after_cancel(self.update_timer)
            self.update_timer = None

        now = time.time()
        cooldown = 2.0
        is_jump = event_data and event_data.get("event") == "FSDJump"
        time_since = now - self.last_update

        if time_since < cooldown and not is_jump:
            delay_ms = int((cooldown - time_since) * 1000) + 50
            self.update_timer = self.root.after(delay_ms, lambda: self._send(event_data, state))
            return

        self._send(event_data, state)

    def _send(self, event_data, state):
        self.last_update = time.time()
        webhook = self.config.get("discord_webhook")
        if not webhook: return

        payload = self._build_payload(event_data, state)
        valuable_alert_payload = self._build_valuable_alert_payload(event_data, state)
        payload_no_ts = json.loads(json.dumps(payload))
        try:
            payload_no_ts["embeds"][0].pop("timestamp", None)
        except Exception:
            pass
        payload_sig = hashlib.sha1(json.dumps(payload_no_ts, sort_keys=True).encode("utf-8")).hexdigest()
        event_type = event_data.get("event") if event_data else None
        if payload_sig == self.last_payload_sig and event_type not in ("FSDJump",) and not valuable_alert_payload:
            return
        self.last_payload_sig = payload_sig
        current_sys = state.get("current_sys", "---")
        self.last_scanned = int(state.get("scanned", 0) or 0)
        traffic = state.get("system_traffic", {}) or {}
        self.last_traffic_total = int(traffic.get("total", 0) or 0)

        def _post():
            try:
                msg_id = self.msg_id
                if msg_id:
                    edit_url = f"{webhook}/messages/{msg_id}"
                    r = requests.patch(edit_url, json=payload, timeout=5)
                    if r.status_code == 404:
                        msg_id = ""
                
                if not msg_id:
                    r = requests.post(f"{webhook}", json=payload, params={"wait": "true"}, timeout=5)
                    if r.status_code in [200, 201]:
                        msg_id = r.json().get("id")
                        self.msg_id = msg_id
                        self.config["discord_msg_id"] = msg_id
                        self.config["discord_msg_system"] = current_sys
                        with open(CONFIG_FILE, 'w') as f: json.dump(self.config, f, indent=4)

                if valuable_alert_payload:
                    requests.post(f"{webhook}", json=valuable_alert_payload, timeout=5)
            except Exception as e:
                logging.error(f"Discord Live Error: {e}")
        
        threading.Thread(target=_post, daemon=True).start()

    def reset_msg_id(self):
        self.msg_id = ""
        self.config["discord_msg_id"] = ""
        self.config["discord_msg_system"] = ""
        self.alerted_valuable_bodies.clear()

    def update_fleet_carrier(self, fc_state):
        if not self.config.get("discord_enabled", True):
            return
        if not self.config.get("discord_fleet_enabled", True):
            return
        webhook = self.config.get("discord_webhook")
        if not webhook:
            return
        if not isinstance(fc_state, dict):
            return

        name = str(fc_state.get("name") or "UNSET CARRIER").strip()
        edsm_url = str(fc_state.get("edsm_url") or "").strip() or None
        callsign = str(fc_state.get("callsign") or "").strip().upper()
        status_note = str(fc_state.get("status_note") or "").strip()
        location = str(fc_state.get("location") or "Unknown").strip() or "Unknown"
        location_ago = str(fc_state.get("location_changed_ago") or "").strip()
        in_transit = bool(fc_state.get("in_transit"))
        movement_state = str(fc_state.get("movement_state") or "").strip().lower()
        departed_ts = fc_state.get("departed_ts")
        departed_text = str(fc_state.get("departed_text") or "").strip()
        destination = str(fc_state.get("destination") or "TBD").strip() or "TBD"
        manual_heading = str(fc_state.get("manual_heading") or "").strip()
        manual_heading_dist_ly = fc_state.get("manual_heading_distance_ly")
        journal_destination = str(fc_state.get("journal_destination") or "").strip()
        current_target_dist_ly = fc_state.get("current_target_distance_ly")
        status_change = str(fc_state.get("status_change") or "").strip()
        jump_target = str(fc_state.get("jump_target") or destination or "TBD").strip() or "TBD"
        jump_target_dist_ly = fc_state.get("jump_target_distance_ly")
        refresh_reason = str(fc_state.get("refresh_reason") or "").strip()
        dist_ly = fc_state.get("destination_distance_ly")
        try:
            dist_txt = f" ({float(dist_ly):,.1f} ly)" if dist_ly is not None else ""
        except Exception:
            dist_txt = ""

        carrier_search = None
        if callsign and location != "Unknown":
            carrier_search = f"{callsign} [{location}]"
        elif callsign:
            carrier_search = callsign
        elif name:
            carrier_search = name
        carrier_url = f"https://inara.cz/elite/station/?search={quote_plus(carrier_search)}" if carrier_search else None

        if callsign and callsign not in name.upper():
            carrier_name = f"{name} - {callsign}"
        else:
            carrier_name = name
        if carrier_url:
            carrier_name = f"[{carrier_name}]({carrier_url})"
        name_line = f"🛸 Carrier: {carrier_name}"

        loc_suffix = f" (changed {location_ago})" if location_ago else ""
        if location and location != "Unknown":
            location_url = f"https://www.edsm.net/show-system?systemName={quote_plus(location)}"
            location_value = f"[{location}]({location_url})"
        else:
            location_value = "Unknown"
        location_line = f"📍 Current Location: {location_value}{loc_suffix}"
        dep_line_val = None
        if departed_ts is not None:
            try:
                dep_unix = int(float(departed_ts))
                if dep_unix > int(time.time()):
                    dep_line_val = f"<t:{dep_unix}:F> (<t:{dep_unix}:R>)"
            except Exception:
                dep_line_val = departed_text or None
        movement_line = "🚀 Transit: Not In Transit"
        if movement_state == "scheduled":
            movement_line = "🚀 Transit: Jump Scheduled"
        elif movement_state == "in_transit" or in_transit:
            movement_line = "🚀 Transit: In Transit"
        if manual_heading:
            heading_url = f"https://www.edsm.net/show-system?systemName={quote_plus(manual_heading)}"
            heading_value = f"[{manual_heading}]({heading_url})"
            try:
                heading_dist_txt = f" ({float(manual_heading_dist_ly):,.1f} ly)" if manual_heading_dist_ly is not None else ""
            except Exception:
                heading_dist_txt = ""
            heading_line = f"🧭 Heading: {heading_value}{heading_dist_txt}"
        else:
            heading_line = None
        merged_destination = jump_target if jump_target and jump_target != "TBD" else destination
        try:
            if jump_target_dist_ly is not None:
                merged_dist_txt = f" ({float(jump_target_dist_ly):,.1f} ly)"
            elif current_target_dist_ly is not None:
                merged_dist_txt = f" ({float(current_target_dist_ly):,.1f} ly)"
            else:
                merged_dist_txt = ""
        except Exception:
            merged_dist_txt = ""
        destination_line = f"📌 Destination: {merged_destination}{merged_dist_txt}"
        if journal_destination:
            current_target_url = f"https://www.edsm.net/show-system?systemName={quote_plus(journal_destination)}"
            current_target_value = f"[{journal_destination}]({current_target_url})"
        else:
            current_target_value = "TBD"
        current_target_line = f"🛰 Current Target: {current_target_value}"
        status_change_line = f"🔄 Status Change: {status_change or 'No recent fleet carrier change.'}"
        status_line = f"ℹ️ Status: {status_note}" if status_note else None

        snapshot = {
            "name": name,
            "callsign": callsign,
            "location": location,
            "in_transit": in_transit,
            "destination": destination,
            "status_change": status_change,
            "status_note": status_note,
        }
        old = self.fc_last_state or {}
        changes = []
        if old.get("location") and old.get("location") != snapshot["location"]:
            changes.append("location updated")
        if old.get("destination") and old.get("destination") != snapshot["destination"]:
            changes.append("destination updated")
        if old.get("status_change") and old.get("status_change") != snapshot["status_change"]:
            changes.append("status changed")
        if old.get("in_transit") is not None and old.get("in_transit") != snapshot["in_transit"]:
            changes.append("departed" if snapshot["in_transit"] else "jump complete")
        if old.get("status_note") and old.get("status_note") != snapshot["status_note"]:
            changes.append("status updated")
        change_title = f"Changes: {', '.join(changes)}" if changes else f"Update: {refresh_reason or 'refresh'}"
        force_new_message = (
            status_change.startswith("Jump requested ->")
            or status_change.startswith("Jump complete ->")
            or status_change == "Jump cancelled"
        )

        description_lines = [
            name_line,
            location_line,
            movement_line,
            destination_line,
            current_target_line,
            status_change_line,
        ]
        if dep_line_val:
            description_lines.append(f"⏱ Departure: {dep_line_val}")
        if heading_line:
            description_lines.append(heading_line)
        if status_line:
            description_lines.append(status_line)
        description = "\n".join(description_lines)

        payload = {
            "embeds": [{
                "title": change_title[:256],
                "description": description[:4096],
                "color": 0x7AA2F7,
                "author": {"name": "DWEBot"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {"text": f"VOID COMPASS v{APP_VERSION} // Fleet Carrier Watcher"}
            }]
        }

        def _post():
            try:
                # Status-note change should create a fresh Discord message instead of editing prior one.
                if status_note != self.fc_last_status_note or force_new_message:
                    self.fc_msg_id = ""
                    self.config["discord_fc_msg_id"] = ""

                msg_id = self.fc_msg_id
                if msg_id:
                    edit_url = f"{webhook}/messages/{msg_id}"
                    r = requests.patch(edit_url, json=payload, timeout=5)
                    if r.status_code == 404:
                        msg_id = ""

                if not msg_id:
                    r = requests.post(f"{webhook}", json=payload, params={"wait": "true"}, timeout=5)
                    if r.status_code in [200, 201]:
                        msg_id = r.json().get("id")
                        self.fc_msg_id = msg_id
                        self.config["discord_fc_msg_id"] = msg_id
                        self.fc_last_status_note = status_note
                        self.config["discord_fc_last_status_note"] = status_note
                        self.fc_last_state = snapshot
                        self.config["discord_fc_last_state"] = snapshot
                        with open(CONFIG_FILE, "w") as f:
                            json.dump(self.config, f, indent=4)
                else:
                    # Keep status-note cache updated for edit path too.
                    self.fc_last_status_note = status_note
                    self.config["discord_fc_last_status_note"] = status_note
                    self.fc_last_state = snapshot
                    self.config["discord_fc_last_state"] = snapshot
                    with open(CONFIG_FILE, "w") as f:
                        json.dump(self.config, f, indent=4)
            except Exception as e:
                logging.error(f"Discord Fleet Watch Error: {e}")

        threading.Thread(target=_post, daemon=True).start()
