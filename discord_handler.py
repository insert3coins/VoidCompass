import time
import threading
import requests
import logging
import math
import json
import hashlib
from datetime import datetime, timezone
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

    @staticmethod
    def _fmt_num(value):
        try:
            return f"{int(value):,}"
        except Exception:
            return "0"

    def _build_title(self, event_data):
        event_type = event_data.get("event") if event_data else None
        if event_type == "FSDJump":
            return "Jump Complete"
        if event_type == "Scan":
            body_name = event_data.get("BodyName", "Unknown Body")
            p_class = event_data.get("PlanetClass", "")
            terraformable = event_data.get("TerraformState") == "Terraformable"
            if p_class == "Earthlike body":
                return f"Scan: Earthlike - {body_name}"
            if p_class == "Water world":
                return f"Scan: Water World - {body_name}"
            if p_class == "Ammonia world":
                return f"Scan: Ammonia World - {body_name}"
            if terraformable:
                return f"Scan: Terraformable - {body_name}"
            return f"Scan: {body_name}"
        if event_type == "ScanOrganic":
            genus = event_data.get("Genus_Localised", "Organic")
            return f"Bio Log: {genus}"
        if event_type == "FSSDiscoveryScan":
            return "System Scan Initiated"
        return "Void Compass Telemetry"

    def _build_payload(self, event_data, state):
        title = self._build_title(event_data)
        embed_color = 0x00D1FF
        if state.get("valuable_system"):
            embed_color = 0x00FF41
        if event_data and event_data.get("event") == "ScanOrganic":
            embed_color = 0xF5A623

        current_sys = state.get("current_sys", "---")
        sys_url = f"https://www.edsm.net/show-system?systemName={current_sys.replace(' ', '+')}"
        cmdr = state.get("cmdr_name", "CMDR")
        star = state.get("star_class")
        organic = int(state.get("organic_count", 0) or 0)

        scanned = int(state.get("scanned", 0) or 0)
        total = int(state.get("total", 0) or 0)
        pct = int((scanned / total) * 100) if total > 0 else 0

        traffic = state.get("system_traffic", {}) or {}
        t_day = int(traffic.get("day", 0) or 0)
        t_week = int(traffic.get("week", 0) or 0)
        t_total = int(traffic.get("total", 0) or 0)

        nav_text = "`NO ROUTE`"
        if dest_name:
            try:
                curr = state.get("current_coords", [0, 0, 0])
                dest = state.get("dest_coords", [0, 0, 0])
                d = math.sqrt(sum((a - b) ** 2 for a, b in zip(curr, dest)))
                nav_text = f"`{dest_name}` ({d:,.1f} LY)"
            except Exception:
                nav_text = f"`{str(dest_name)}`"

        ops_lines = [
            f"CMDR    {cmdr}",
            f"SYSTEM  {current_sys}",
            f"STAR    {str(star).upper() if star else 'UNKNOWN'}",
            f"ROUTE   {dest_name if dest_name else 'INACTIVE'}",
            f"SCAN    {self._fmt_num(scanned)}/{self._fmt_num(total)} ({pct}%)",
            f"BIO     {self._fmt_num(organic)}",
            f"TRAF    {self._fmt_num(t_day)} / {self._fmt_num(t_week)} / {self._fmt_num(t_total)}",
        ]

        fields = [
            {"name": "System Link", "value": f"[{current_sys}]({sys_url})", "inline": False},
            {"name": "Navigation", "value": nav_text, "inline": True},
            {"name": "Exploration", "value": f"`{self._fmt_num(scanned)} / {self._fmt_num(total)} ({pct}%)`", "inline": True},
            {"name": "Traffic", "value": f"`24h {self._fmt_num(t_day)} | 7d {self._fmt_num(t_week)} | total {self._fmt_num(t_total)}`", "inline": False},
        ]

        valuables = state.get("valuable_bodies") or []
        if valuables:
            cleaned = []
            for v in valuables[:6]:
                txt = v[2:] if isinstance(v, str) and v.startswith("- ") else str(v)
                cleaned.append(txt)
            extra = len(valuables) - len(cleaned)
            value_txt = "\n".join(cleaned)
            if extra > 0:
                value_txt += f"\n... +{extra} more"
            fields.append({"name": "Valuable Discoveries", "value": value_txt[:1024], "inline": False})

        return {
            "embeds": [{
                "title": f"VOID COMPASS // OPERATIONS BRIEF",
                "description": "```text\n" + "\n".join(ops_lines) + "\n```",
                "color": embed_color,
                "fields": fields,
                "author": {"name": title},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {"text": f"VOID COMPASS v{APP_VERSION}"}
            }]
        }

    def update_live(self, event_data, state):
        if not self.config.get("discord_enabled", True):
            return
        webhook = self.config.get("discord_webhook")
        if not webhook: return

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
        payload_no_ts = json.loads(json.dumps(payload))
        try:
            payload_no_ts["embeds"][0].pop("timestamp", None)
        except Exception:
            pass
        payload_sig = hashlib.sha1(json.dumps(payload_no_ts, sort_keys=True).encode("utf-8")).hexdigest()
        event_type = event_data.get("event") if event_data else None
        if payload_sig == self.last_payload_sig and event_type not in ("FSDJump",):
            return
        self.last_payload_sig = payload_sig
        current_sys = state.get("current_sys", "---")

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
            except Exception as e:
                logging.error(f"Discord Live Error: {e}")
        
        threading.Thread(target=_post, daemon=True).start()

    def reset_msg_id(self):
        self.msg_id = ""
        self.config["discord_msg_id"] = ""
        self.config["discord_msg_system"] = ""
