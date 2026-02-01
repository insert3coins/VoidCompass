import time
import threading
import requests
import logging
import math
import json
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

        title = "🛸 SURVEY TELEMETRY"
        event_type = event_data.get("event") if event_data else None

        if event_type == "FSDJump":
            title = f"🚀 JUMP COMPLETE"
        elif event_type == "Scan":
            body_name = event_data.get("BodyName", "Unknown Body")
            p_class = event_data.get("PlanetClass", "")
            terraformable = event_data.get("TerraformState") == "Terraformable"
            prefix = "🛰️ SCAN: "
            if p_class == "Earthlike body": prefix = "🌍 SCAN: "
            elif p_class == "Water world": prefix = "💧 SCAN: "
            elif p_class == "Ammonia world": prefix = "☣️ SCAN: "
            elif terraformable: prefix = "🛠️ SCAN: "
            title = f"{prefix}{body_name}"
        elif event_type == "ScanOrganic":
            genus = event_data.get("Genus_Localised", "Organic")
            title = f"🌱 BIO-LOG: {genus}"
        elif event_type == "FSSDiscoveryScan":
            title = "📡 SYSTEM SCAN INITIATED"

        embed_color = 0x00d1ff
        if state.get("valuable_system"):
            embed_color = 0x00FF41

        current_sys = state.get("current_sys", "---")
        sys_url = f"https://www.edsm.net/show-system?systemName={current_sys.replace(' ', '+')}"
        
        desc = f"**CMDR {state.get('cmdr_name', 'CMDR')}**\n"
        desc += f"📍 **System:** [{current_sys}]({sys_url})\n"
        if state.get("star_class"):
            desc += f"☀️ **Star Class:** {state.get('star_class').upper()}\n"
        desc += f"🛰️ **Scanned:** {state.get('scanned', 0)} / {state.get('total', 0)}\n"

        if state.get("valuable_bodies"):
            desc += "\n**Valuable Discoveries:**\n"
            desc += "\n".join(state.get("valuable_bodies"))
            desc += "\n"

        traffic = state.get("system_traffic", {})
        t_day = traffic.get('day', 0)
        t_week = traffic.get('week', 0)
        if t_day > 0 or t_week > 0:
            desc += f"🚦 **Traffic (24h/wk):** {t_day} / {t_week}\n"

        dest_name = state.get("dest_name")
        if dest_name:
            try:
                curr = state.get("current_coords", [0,0,0])
                dest = state.get("dest_coords", [0,0,0])
                d = math.sqrt(sum((a-b)**2 for a,b in zip(curr, dest)))
                desc += f"🏁 **Target:** {dest_name} ({d:,.1f} LY)\n"
            except: pass

        payload = {
            "embeds": [{
                "title": title,
                "description": desc,
                "color": embed_color,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {"text": f"SURVEY ANALYSIS v{APP_VERSION}"}
            }]
        }

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