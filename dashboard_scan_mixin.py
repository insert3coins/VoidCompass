import math
import time
import threading

from config import COLOR_ACCENT, COLOR_TEXT


class DashboardScanMixin:
    def _flush_pending_status_update(self):
        self._status_dispatch_scheduled = False
        data = getattr(self, "_pending_status_data", None)
        self._pending_status_data = None
        if data is None:
            return
        self._apply_status_update(data)

    def _apply_status_update(self, data):
        t0 = self._perf_start()
        self.last_status_event_ts = time.time()
        if getattr(self, "mining_window", None) and self.mining_window.is_open():
            self.mining_window.update_status(data)
        was_on_planet = bool(self.on_planet)
        self.current_latitude = self._to_float(data.get("Latitude"))
        self.current_longitude = self._to_float(data.get("Longitude"))
        self.current_heading = self._to_float(data.get("Heading"))
        self.current_planet_radius = self._to_float(data.get("PlanetRadius"))
        self.on_planet = (
            self.current_latitude is not None
            and self.current_longitude is not None
            and self.current_planet_radius is not None
            and self.current_planet_radius > 0
        )

        gui_focus = data.get("GuiFocus", -1)
        in_fss = gui_focus == 9 or gui_focus == "FSS"
        if in_fss != self.in_fss:
            self.in_fss = in_fss
            if self.scan_hud:
                if self.in_fss:
                    if self.scan_hud_hide_job:
                        try:
                            self.root.after_cancel(self.scan_hud_hide_job)
                        except Exception:
                            pass
                        self.scan_hud_hide_job = None
                    self.scan_hud.show()
                else:
                    if self.scan_hud_hide_job:
                        return
                    self.scan_hud_hide_job = self.root.after(
                        self.scan_hud_hide_delay_ms,
                        self._hide_scan_hud_delayed
                    )
            if self.in_fss:
                self.fss_summary_active = False
            else:
                self.fss_summary_active = True
            if not self.batch_mode:
                self.update_hud()
                self.schedule_dashboard_refresh()

        on_planet_changed = (was_on_planet != bool(self.on_planet))
        status_key = None
        if self.on_planet:
            status_key = (
                round(self.current_latitude, 5),
                round(self.current_longitude, 5),
                None if self.current_heading is None else int(round(self.current_heading)),
                int(round(self.current_planet_radius)),
            )
        moved = status_key != getattr(self, "_ground_last_status_key", None)
        self._ground_last_status_key = status_key

        # Only request live ground updates while target tracking is active.
        needs_live_ground_update = bool(self.on_planet and self.target_latlon_active and moved)
        if on_planet_changed or needs_live_ground_update:
            self._ground_ui_needs_update = True
        self._perf_spike("_apply_status_update", t0, threshold_ms=20.0)

    def update_scan_hud(self):
        if not self.scan_hud:
            return

        scanned_count = len(self.scan_items)
        total_value = 0
        for item in self.scan_items:
            reward = item.get("dss_reward") if item.get("dss_complete") else item.get("reward")
            if isinstance(reward, (int, float)):
                total_value += int(reward)

        self.root.after(0, lambda: self.scan_hud.update(
            self.current_sys,
            self.system_undiscovered,
            self.fss_all_bodies,
            scanned_count,
            total_value,
            self.scan_items
        ))

    def _rebuild_scan_index(self):
        self.scan_items_by_id = {}
        for item in self.scan_items:
            self._normalize_scan_item(item)
            body_id = item.get("body_id")
            if body_id is not None:
                self.scan_items_by_id[body_id] = item
            self.save_scan_item_to_db(self.current_sys, item)

    def _format_credits(self, credits, hide_units=False):
        if credits is None:
            return ""
        try:
            credits = int(credits)
        except Exception:
            return ""

        if credits < 1_000:
            txt = f"{credits:,}"
        elif credits < 100_000:
            txt = f"{credits / 1_000:.2f} K"
        elif credits < 1_000_000:
            txt = f"{credits / 1_000:.0f} K"
        elif credits < 100_000_000:
            txt = f"{credits / 1_000_000:.2f} M"
        elif credits < 1_000_000_000:
            txt = f"{credits / 1_000_000:.0f} M"
        else:
            txt = f"{credits / 1_000_000_000:.3f} B"

        if not hide_units:
            txt += " CR"
        return txt

    def _get_fss_summary(self):
        if not self.scan_items:
            return None

        scanned_count = len(self.scan_items)
        total_value = 0
        for item in self.scan_items:
            reward = item.get("dss_reward") if item.get("dss_complete") else item.get("reward")
            if isinstance(reward, (int, float)):
                total_value += int(reward)

        last = self.scan_items[0]
        last_name = last.get("name") or ""
        last_class = last.get("class") or ""
        last_bio = last.get("bio_count", 0)
        last_reward = last.get("reward")
        last_dss = last.get("dss_reward")
        last_is_star = last.get("is_star", False)

        if last.get("dss_complete"):
            last_value = self._format_credits(last_reward, hide_units=True)
        else:
            last_value = self._format_credits(last_reward, hide_units=True)
            if not last_is_star and last_dss:
                last_value = f"{last_value} | {self._format_credits(last_dss, hide_units=True)}"

        high_value = []
        landable_count = 0
        remaining_count = max(self.total - self.scanned, 0) if self.total else 0
        for item in self.scan_items:
            planet_class = item.get("planet_class") or item.get("class") or ""
            terraformable = item.get("terraformable", False)
            icons = item.get("icons") or []
            if not terraformable and "🛠" in icons:
                terraformable = True
            is_high = terraformable or planet_class in ("Earthlike body", "Water world", "Ammonia world") or any(icon in icons for icon in ("🌍", "💧", "☣"))
            if not is_high:
                pass
            else:
                icon = ""
                if planet_class == "Earthlike body":
                    icon = "🌍"
                elif planet_class == "Water world":
                    icon = "💧"
                elif planet_class == "Ammonia world":
                    icon = "☣"
                elif terraformable:
                    icon = "🛠"
                label = item.get("full_name") or item.get("name") or ""
                if label and self.current_sys and self.current_sys not in label:
                    label = f"{self.current_sys} {label}"
                if not label:
                    label = item.get("class") or ""
                if not label:
                    body_id = item.get("body_id")
                    label = f"Body {body_id}" if body_id is not None else "Body"
                if planet_class == "Earthlike body":
                    class_label = "ELW"
                elif planet_class == "Water world":
                    class_label = "WW"
                elif planet_class == "Ammonia world":
                    class_label = "AW"
                elif terraformable:
                    class_label = "TF"
                else:
                    class_label = planet_class if planet_class else "HV"
                high_value.append(f"{icon} {class_label}: {label}".strip())

            if item.get("landable"):
                landable_count += 1

        high_value = high_value[:3]

        return {
            "count": scanned_count,
            "total": self._format_credits(total_value, hide_units=False),
            "high_value": high_value,
            "landable_count": landable_count,
            "remaining_count": remaining_count
        }

    def _get_body_k_value(self, planet_class, is_terraformable):
        if planet_class == "Metal rich body":
            k = 21790
        elif planet_class == "Ammonia world":
            k = 96932
        elif planet_class == "Sudarsky class I gas giant":
            k = 1656
        elif planet_class == "Sudarsky class II gas giant" or planet_class == "High metal content body":
            k = 9654
            if is_terraformable:
                k += 100677
        elif planet_class == "Water world":
            k = 64831
            if is_terraformable:
                k += 116295
        elif planet_class and planet_class.startswith("Earth"):
            k = 64831 + 116295
        else:
            k = 300
            if is_terraformable:
                k += 93328
        return k

    def _get_star_k_value(self, star_type):
        if star_type in ("NS", "BH", "SupermassiveBlackHole"):
            return 22628
        if star_type and star_type.startswith("W"):
            return 14057
        return 1200

    def _get_body_value(self, planet_class, star_type, is_terraformable, mass, is_first_discoverer, is_mapped, is_first_mapped, with_efficiency_bonus=True):
        is_star = False
        if star_type:
            is_star = True
        elif planet_class and (len(planet_class) < 8 or (len(planet_class) > 1 and planet_class[1] == '_') or planet_class in ("SupermassiveBlackHole", "Nebula", "StellarRemnantNebula")):
            is_star = True

        if is_star:
            kk = self._get_star_k_value(star_type or planet_class or "")
            star_value = kk + (mass * kk / 66.25)
            return int(round(star_value))

        k = self._get_body_k_value(planet_class or "", is_terraformable)

        q = 0.56591828
        mapping_multiplier = 1
        if is_mapped:
            if is_first_discoverer and is_first_mapped:
                mapping_multiplier = 3.699622554
            elif is_first_mapped:
                mapping_multiplier = 8.0956
            else:
                mapping_multiplier = 3.3333333333
        value = (k + k * q * pow(mass, 0.2)) * mapping_multiplier
        if is_mapped:
            value += max(value * 0.3, 555)
            if with_efficiency_bonus:
                value *= 1.25
        value = max(500, value)
        if is_first_discoverer:
            value *= 2.6
        return int(round(value))

    def _normalize_scan_item(self, item):
        if item.get("icons") is None:
            item["icons"] = []
        if item.get("body_id") is None:
            item["body_id"] = None

        name = item.get("name")
        if not name:
            fallback = item.get("class") or ""
            if not fallback:
                body_id = item.get("body_id")
                fallback = f"Body {body_id}" if body_id is not None else "Body"
            item["name"] = fallback
        if item.get("full_name") is None:
            item["full_name"] = item.get("name")

        body_class = item.get("class") or "Unknown"
        star_type = item.get("star_type")
        planet_class = item.get("planet_class")

        if not star_type and (body_class.lower().endswith("star") or body_class.lower().endswith(" star")):
            star_type = body_class.split()[0].upper()
        if not planet_class and not star_type:
            planet_class = body_class

        terraformable = item.get("terraformable")
        if terraformable is None:
            terraformable = "🛠" in item["icons"] or "🌍" in item["icons"]

        was_discovered = item.get("was_discovered")
        if was_discovered is None:
            was_discovered = "⚑" not in item["icons"]

        was_mapped = item.get("was_mapped")
        if was_mapped is None:
            was_mapped = False

        mass = item.get("mass")
        if mass is None:
            mass = 1.0

        reward = item.get("reward")
        dss_reward = item.get("dss_reward")
        if reward is None or dss_reward is None:
            is_first_discoverer = not was_discovered
            is_first_mapped = not was_mapped
            reward = self._get_body_value(planet_class, star_type, terraformable, mass, is_first_discoverer, False, is_first_mapped, True)
            dss_reward = self._get_body_value(planet_class, star_type, terraformable, mass, is_first_discoverer, True, is_first_mapped, True)

        dss_complete = item.get("dss_complete")
        if dss_complete is None:
            dss_complete = was_mapped

        bio_count = item.get("bio_count")
        if bio_count is None:
            bio_count = 0

        is_star = item.get("is_star")
        if is_star is None:
            is_star = bool(star_type)

        icons = item["icons"]
        if not was_discovered and "⚑" not in icons:
            icons.append("⚑")
        if terraformable and "🛠" not in icons:
            icons.append("🛠")
        if item.get("landable") and "🚀" not in icons:
            icons.append("🚀")
        if item.get("first_footfall") and "🦶" not in icons:
            icons.append("🦶")

        if not is_star:
            if planet_class == "Earthlike body" and "🌍" not in icons:
                icons.append("🌍")
            elif planet_class == "Water world" and "💧" not in icons:
                icons.append("💧")
            elif planet_class == "Ammonia world" and "☣" not in icons:
                icons.append("☣")

        highlight = (bio_count > 0) or (not is_star and dss_reward > reward)
        color = COLOR_ACCENT if highlight else COLOR_TEXT

        item.update({
            "star_type": star_type,
            "planet_class": planet_class,
            "terraformable": terraformable,
            "was_discovered": was_discovered,
            "was_mapped": was_mapped,
            "mass": mass,
            "reward": reward,
            "dss_reward": dss_reward,
            "dss_complete": dss_complete,
            "bio_count": bio_count,
            "is_star": is_star,
            "color": color,
            "icons": icons,
        })

        if item.get("_ts") is None:
            item["_ts"] = int(time.time())

    def update_status(self, data):
        if threading.current_thread() is not threading.main_thread():
            self._pending_status_data = data
            if not getattr(self, "_status_dispatch_scheduled", False):
                self._status_dispatch_scheduled = True
                self.root.after(0, self._flush_pending_status_update)
            return
        self._apply_status_update(data)

    def _hide_scan_hud_delayed(self):
        self.scan_hud_hide_job = None
        if self.scan_hud and not self.in_fss:
            self.scan_hud.hide()



    def add_scan_item(self, data):
        full_body_name = data.get("BodyName", "Unknown")
        body_name = full_body_name
        if body_name.startswith(self.current_sys):
            body_name = body_name.replace(self.current_sys, "").strip()
            if not body_name:
                body_name = self.current_sys

        star_type = data.get("StarType")
        planet_class = data.get("PlanetClass")
        is_star = bool(star_type)
        if is_star:
            body_class = f"{star_type} Star"
            icons = ["★"]
        else:
            body_class = planet_class or "Unknown"
            icons = []

        terraformable = data.get("TerraformState") == "Terraformable"
        landable = data.get("Landable", False)
        was_discovered = data.get("WasDiscovered", True)
        was_mapped = data.get("WasMapped", True)
        first_footfall = data.get("FirstFootfall", False)

        if not was_discovered:
            icons.append("⚑")

        # Planet/Body icons
        if body_class == "Earthlike body":
            icons.append("🌍")
        elif body_class == "Water world":
            icons.append("💧")
        elif body_class == "Ammonia world":
            icons.append("☣")
        elif "Gas giant" in body_class:
            icons.append("🌀")
        elif "Metal rich" in body_class:
            icons.append("⬢")
        elif "High metal content" in body_class:
            icons.append("⛰")
        elif "Rocky" in body_class:
            icons.append("🪨")

        if terraformable:
            icons.append("🛠")
        if landable:
            icons.append("🚀")
        if first_footfall:
            icons.append("🦶")

        body_id = data.get("BodyID")
        mass = data.get("MassEM") or data.get("StellarMass") or 0
        is_first_discoverer = not was_discovered
        is_first_mapped = not was_mapped
        reward = self._get_body_value(planet_class, star_type, terraformable, mass, is_first_discoverer, False, is_first_mapped, True)
        dss_reward = self._get_body_value(planet_class, star_type, terraformable, mass, is_first_discoverer, True, is_first_mapped, True)
        dss_complete = was_mapped or (body_id in self.body_dss_complete)

        bio_count = 0
        if "BioSignals" in data:
            for signal in data.get("BioSignals", []):
                if signal.get("Type_Localised") == "Biological":
                    bio_count += signal.get("Count", 0)
        elif body_id in self.body_signals:
            bio_count = self.body_signals[body_id].get("bio", 0)

        highlight = (bio_count > 0) or (not is_star and dss_reward > reward)
        color = COLOR_ACCENT if highlight else COLOR_TEXT

        ts = int(time.time())
        item = {
            "body_id": body_id,
            "name": body_name,
            "full_name": full_body_name,
            "class": body_class,
            "star_type": star_type,
            "planet_class": planet_class,
            "terraformable": terraformable,
            "landable": landable,
            "was_mapped": was_mapped,
            "mass": mass,
            "radius": data.get("Radius"),
            "surface_temp": data.get("SurfaceTemperature"),
            "surface_gravity": data.get("SurfaceGravity"),
            "atmosphere": data.get("Atmosphere") or data.get("AtmosphereType"),
            "volcanism": data.get("Volcanism"),
            "icons": icons,
            "color": color,
            "reward": reward,
            "dss_reward": dss_reward,
            "dss_complete": dss_complete,
            "bio_count": bio_count,
            "is_star": is_star,
            "was_discovered": was_discovered,
            "first_footfall": first_footfall,
            "_ts": ts
        }

        existing = None
        if body_id is not None:
            existing = self.scan_items_by_id.get(body_id)
        if existing:
            self.scan_items.remove(existing)
        self.scan_items.insert(0, item)
        self.scan_items = self.scan_items[:60]
        if body_id is not None:
            self.scan_items_by_id[body_id] = item
        self.save_scan_item_to_db(self.current_sys, item)

