import math
import time
import threading

import bio_values
import compass_operations
from config import COLOR_ACCENT, COLOR_TEXT
from stellar_types import star_type_label


class DashboardScanMixin:
    _STATUS_LANDING_GEAR_DOWN = 0x00000004
    _STATUS_CARGO_SCOOP_DEPLOYED = 0x00000200
    _STATUS_SCOOPING_FUEL = 0x00000800
    _STATUS_ANALYSIS_MODE = 0x08000000
    _STATUS_FSD_MASS_LOCKED = 0x00010000
    _STATUS_FSD_CHARGING = 0x00020000
    _STATUS_FSD_COOLDOWN = 0x00040000
    _STATUS_FSD_JUMPING = 0x40000000
    _STATUS2_FSD_HYPERDRIVE_CHARGING = 0x00080000
    _STATUS2_SUPERCRUISE_OVERCHARGE = 0x00100000

    def _sync_navigation_hud_flight_state(self, *, supercruise=False):
        """Resolve the navigation HUD state from the latest verified vehicle flags."""
        if getattr(self, "current_on_foot", False):
            state = "ONFOOT"
        elif getattr(self, "current_in_fighter", False):
            state = getattr(self, "current_vehicle_name", None) or "FIGHTER"
        elif getattr(self, "current_in_srv", False):
            state = "NOMAD" if getattr(self, "current_vehicle_name", "") == "NOMAD" else "SRV"
        elif getattr(self, "current_docked", False):
            state = "DOCKED"
        elif getattr(self, "current_landed", False):
            state = "LANDED"
        elif supercruise:
            state = "SUPERCRUISE"
        else:
            state = "FLIGHT"
        changed = state != getattr(self, "hud_flight_state", None)
        self.hud_flight_state = state
        return changed

    def _apply_vehicle_switch(self, destination):
        """Apply the journal VehicleSwitch event before Status.json catches up."""
        destination = str(destination or "").strip().casefold()
        self.current_on_foot = False
        if destination == "fighter":
            self.current_in_fighter = True
            self.current_in_srv = False
            self.current_vehicle_name = "FIGHTER"
        elif destination == "srv":
            self.current_in_fighter = False
            self.current_in_srv = True
            vehicle = str(self.current_vehicle_name or "").upper()
            previous = str(self._last_surface_vehicle_name or "").upper()
            self.current_vehicle_name = (
                vehicle if vehicle in ("NOMAD", "SRV")
                else previous if previous in ("NOMAD", "SRV")
                else "SRV"
            )
        elif destination == "mothership":
            self.current_in_fighter = False
            self.current_in_srv = False
            self.current_vehicle_id = None
            self.current_vehicle_name = ""
        self._sync_navigation_hud_flight_state(
            supercruise=self.hud_flight_state == "SUPERCRUISE"
        )
        self.update_hud()
        return self.hud_flight_state

    def _flush_pending_status_update(self):
        self._status_dispatch_scheduled = False
        data = getattr(self, "_pending_status_data", None)
        self._pending_status_data = None
        if data is None:
            return
        self._apply_status_update(data)

    def _current_fuel_percent(self):
        """Tank percentage the Navigation HUD displays, rounded to match it."""
        fuel_main = getattr(self, "current_fuel_main", None)
        fuel_capacity = getattr(self, "fuel_capacity_main", None)
        try:
            if fuel_capacity and float(fuel_capacity) > 0 and fuel_main is not None:
                return max(0, min(100, round(float(fuel_main) * 100 / float(fuel_capacity))))
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        return None

    def _apply_status_update(self, data):
        t0 = self._perf_start()
        self.last_status_event_ts = time.time()
        if getattr(self, "heartbeat_hud", None):
            self.heartbeat_hud.pulse()
        was_on_planet = bool(self.on_planet)
        was_landed = bool(getattr(self, "current_landed", False))
        was_docked = bool(getattr(self, "current_docked", False))
        was_in_fighter = bool(getattr(self, "current_in_fighter", False))
        was_in_srv = bool(getattr(self, "current_in_srv", False))
        was_on_foot = bool(getattr(self, "current_on_foot", False))
        was_gui_focus = getattr(self, "current_gui_focus", -1)
        was_fuel_percent = self._current_fuel_percent()
        was_navigation_awareness = (
            getattr(self, "current_altitude_m", None),
            bool(getattr(self, "current_landing_gear_down", False)),
            bool(getattr(self, "current_cargo_scoop_deployed", False)),
            bool(getattr(self, "current_analysis_mode", False)),
            bool(getattr(self, "current_scooping_fuel", False)),
            bool(getattr(self, "current_supercruise_overcharge", False)),
        )
        was_navigation_readiness = (
            bool(getattr(self, "current_fsd_mass_locked", False)),
            bool(getattr(self, "current_fsd_charging", False)),
            bool(getattr(self, "current_fsd_hyperdrive_charging", False)),
            bool(getattr(self, "current_fsd_cooldown", False)),
            bool(getattr(self, "current_fsd_jumping", False)),
            str(getattr(self, "_navigation_jump_phase", "") or ""),
            dict(getattr(self, "current_destination_details", None) or {}),
        )
        fuel = data.get("Fuel") or {}
        # Status.json is the live source while scooping and during ordinary
        # supercruise consumption. Some vehicle/on-foot snapshots omit Fuel,
        # so never erase the last verified mothership reading with ``None``.
        if isinstance(fuel, dict):
            fuel_main = fuel.get("FuelMain")
            fuel_reservoir = fuel.get("FuelReservoir")
            try:
                if fuel_main is not None:
                    self.current_fuel_main = float(fuel_main)
            except (TypeError, ValueError):
                pass
            try:
                if fuel_reservoir is not None:
                    self.current_fuel_reservoir = float(fuel_reservoir)
            except (TypeError, ValueError):
                pass
        self.current_legal_state = data.get("LegalState")
        dest = data.get("Destination") or {}
        if isinstance(dest, dict):
            self.current_destination_details = {
                key: dest.get(key)
                for key in ("System", "Body", "Name")
                if dest.get(key) is not None
            }
        else:
            self.current_destination_details = {}
        self.current_destination = self.current_destination_details.get("Name") or None
        if data.get("Cargo") is not None:
            try:
                self.current_cargo_tons = int(data.get("Cargo") or 0)
            except Exception:
                self.current_cargo_tons = data.get("Cargo")
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
        altitude = self._to_float(data.get("Altitude"))
        altitude_now = time.monotonic()
        previous_altitude = getattr(self, "current_altitude_m", None)
        previous_altitude_ts = getattr(self, "_status_altitude_observed_monotonic", None)
        if altitude is not None:
            if previous_altitude is not None and previous_altitude_ts is not None:
                elapsed = altitude_now - previous_altitude_ts
                if 0.05 <= elapsed <= 10.0:
                    instantaneous = (float(previous_altitude) - altitude) / elapsed
                    previous_rate = float(getattr(self, "_surface_descent_mps", 0.0) or 0.0)
                    self._surface_descent_mps = (previous_rate * 0.65) + (instantaneous * 0.35)
            self.current_altitude_m = altitude
            self._status_altitude_observed_monotonic = altitude_now
        elif not self.on_planet:
            self.current_altitude_m = None
            self._status_altitude_observed_monotonic = None
            self._surface_descent_mps = 0.0
        specialist_engine = getattr(self, "specialist_engine", None)
        if specialist_engine:
            specialist_engine.update_position({
                "lat": self.current_latitude,
                "lon": self.current_longitude,
                "heading": self.current_heading,
                "radius_m": self.current_planet_radius,
                "alt_m": data.get("Altitude"),
                "body": getattr(self, "current_body_name", None) or getattr(self, "current_body_id", None),
            })
        flags = data.get("Flags")
        in_supercruise = False
        if isinstance(flags, int):
            self.current_status_flags = flags
            self.current_landed = bool(flags & 0x00000002)
            self.current_in_fighter = bool(flags & 0x02000000)
            self.current_in_srv = bool(flags & 0x04000000)
            in_supercruise = bool(flags & 0x00000010)
            self.current_fsd_mass_locked = bool(flags & self._STATUS_FSD_MASS_LOCKED)
            self.current_fsd_charging = bool(flags & self._STATUS_FSD_CHARGING)
            self.current_fsd_cooldown = bool(flags & self._STATUS_FSD_COOLDOWN)
            self.current_fsd_jumping = bool(flags & self._STATUS_FSD_JUMPING)
            self.current_landing_gear_down = bool(flags & self._STATUS_LANDING_GEAR_DOWN)
            self.current_cargo_scoop_deployed = bool(flags & self._STATUS_CARGO_SCOOP_DEPLOYED)
            self.current_analysis_mode = bool(flags & self._STATUS_ANALYSIS_MODE)
            self.current_scooping_fuel = bool(flags & self._STATUS_SCOOPING_FUEL)
            combat_tracker = getattr(self, "combat_awareness", None)
            if combat_tracker:
                combat_tracker.update_status(flags)
        flags2 = data.get("Flags2")
        if isinstance(flags2, int):
            self.current_status_flags2 = flags2
            self.current_on_foot = bool(flags2 & 0x0001)
            self.current_fsd_hyperdrive_charging = bool(
                flags2 & self._STATUS2_FSD_HYPERDRIVE_CHARGING
            )
            self.current_supercruise_overcharge = bool(
                flags2 & self._STATUS2_SUPERCRUISE_OVERCHARGE
            )
        else:
            # Status.json normally supplies Flags2 on every snapshot. If a
            # partial or older snapshot omits it, never leave transient SCO
            # latched on after the game has stopped reporting the state.
            self.current_supercruise_overcharge = False
            if not getattr(self, "current_fsd_charging", False):
                self.current_fsd_hyperdrive_charging = False
        jump_phase = str(getattr(self, "_navigation_jump_phase", "") or "")
        set_jump_phase = getattr(self, "_set_navigation_jump_phase", None)
        if jump_phase == "arrival":
            # FSDJump is the definitive completed-arrival event. A Status
            # snapshot carrying the short-lived fsdJump bit can be delivered
            # just afterwards by the independent file watcher; never let that
            # stale snapshot rewind ARRIVAL back into HYPERSPACE.
            self.current_fsd_jumping = False
        elif getattr(self, "current_fsd_jumping", False):
            # Status' FsdJump bit covers the low-wake transition into
            # supercruise as well as a true high-wake. Only promote the HUD to
            # HYPERSPACE when StartJump/Flags2 supplied high-wake evidence.
            high_wake = bool(
                jump_phase in {"charging", "hyperspace"}
                or getattr(self, "_navigation_jump_charge_seen", False)
                or getattr(self, "current_fsd_hyperdrive_charging", False)
            )
            if high_wake and callable(set_jump_phase) and jump_phase != "hyperspace":
                set_jump_phase("hyperspace", refresh=False)
        elif jump_phase == "charging":
            if (getattr(self, "current_fsd_charging", False)
                    and getattr(self, "current_fsd_hyperdrive_charging", False)):
                self._navigation_jump_charge_seen = True
            elif getattr(self, "_navigation_jump_charge_seen", False):
                # A charging flag that falls without the exact fsdJump flag is
                # a cancelled high-wake. Do not leave the HUD stuck charging.
                clear_jump_phase = getattr(self, "_clear_navigation_jump_phase", None)
                if callable(clear_jump_phase):
                    clear_jump_phase(refresh=False)
        if isinstance(flags, int):
            reported_docked = bool(flags & 0x00000001)
            # The ship remains docked while its commander is walking inside a
            # station, although Status.json clears the ship's Docked flag.
            if self.current_on_foot and isinstance(flags2, int):
                if flags2 & (0x0008 | 0x2000 | 0x4000):
                    self.current_docked = True
                elif flags2 & (0x0010 | 0x8000):
                    self.current_docked = False
                elif reported_docked:
                    self.current_docked = True
            else:
                self.current_docked = reported_docked
        hud_state_changed = False
        if isinstance(flags, int) or isinstance(flags2, int):
            hud_state_changed = self._sync_navigation_hud_flight_state(
                supercruise=in_supercruise,
            )
        if was_docked != bool(getattr(self, "current_docked", False)):
            survey = getattr(self, "survey_status_hud", None)
            if survey:
                if self.current_docked:
                    survey.suppress()
                else:
                    survey.resume()
                    self._refresh_system_info_progress()
        try:
            compass_operations.observe_status(self.ai_operational_state, data)
        except Exception:
            pass

        gui_focus = data.get("GuiFocus", -1)
        self.current_gui_focus = gui_focus
        gui_focus_changed = gui_focus != was_gui_focus
        in_fss = gui_focus == 9 or gui_focus == "FSS"
        fss_changed = in_fss != self.in_fss
        if fss_changed:
            self.in_fss = in_fss
            self.fss_summary_active = not in_fss
        if (gui_focus_changed or fss_changed) and not self.batch_mode:
            self.update_hud()
        if fss_changed and not self.batch_mode:
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
        if moved and getattr(self, "bio_sampling", None):
            self._update_sampling_clearance()

        if moved and self.on_planet and (
            getattr(self, "current_in_srv", False) or getattr(self, "current_on_foot", False)
        ):
            self._record_surface_trail_point()

        # Trail drawing and target tracking share this coalesced ground update.
        needs_live_ground_update = bool(
            self.on_planet and moved and (
                self.target_latlon_active
                or bool(getattr(self, "surface_trail", None))
                or self._widget_alive(getattr(self, "ground_target_window", None))
            )
        )
        if on_planet_changed or needs_live_ground_update:
            self._ground_ui_needs_update = True
        vehicle_state_changed = (
            was_landed != bool(getattr(self, "current_landed", False))
            or was_docked != bool(getattr(self, "current_docked", False))
            or was_in_fighter != bool(getattr(self, "current_in_fighter", False))
            or was_in_srv != bool(getattr(self, "current_in_srv", False))
            or was_on_foot != bool(getattr(self, "current_on_foot", False))
        )
        fuel_percent_changed = self._current_fuel_percent() != was_fuel_percent
        navigation_readiness_changed = was_navigation_readiness != (
            bool(getattr(self, "current_fsd_mass_locked", False)),
            bool(getattr(self, "current_fsd_charging", False)),
            bool(getattr(self, "current_fsd_hyperdrive_charging", False)),
            bool(getattr(self, "current_fsd_cooldown", False)),
            bool(getattr(self, "current_fsd_jumping", False)),
            str(getattr(self, "_navigation_jump_phase", "") or ""),
            dict(getattr(self, "current_destination_details", None) or {}),
        )
        navigation_awareness_changed = was_navigation_awareness != (
            getattr(self, "current_altitude_m", None),
            bool(getattr(self, "current_landing_gear_down", False)),
            bool(getattr(self, "current_cargo_scoop_deployed", False)),
            bool(getattr(self, "current_analysis_mode", False)),
            bool(getattr(self, "current_scooping_fuel", False)),
            bool(getattr(self, "current_supercruise_overcharge", False)),
        )
        if fuel_percent_changed:
            self._invalidate_exploration_intelligence()
        if (vehicle_state_changed or hud_state_changed or fuel_percent_changed
                or navigation_readiness_changed or navigation_awareness_changed) and not self.batch_mode:
            self.update_hud()
        if not self.batch_mode:
            self._check_low_fuel()
            self._check_status_toasts(data, flags, flags2)
        self._perf_spike("_apply_status_update", t0, threshold_ms=20.0)

    def _check_status_toasts(self, data, flags, flags2):
        toast = getattr(self, "toast_hud", None)
        if not toast:
            return
        active = getattr(self, "_toast_status_alerts", set())

        overheat = isinstance(flags, int) and bool(flags & 0x00100000)
        interdicted = isinstance(flags, int) and bool(flags & 0x00800000)
        generic_danger = isinstance(flags, int) and bool(flags & 0x00400000)
        # InDanger is a broad, frequently flapping game flag.  It is useful as
        # a last-resort warning in normal ship flight, but not while a specific
        # actionable alert already explains it or while safely docked/landed.
        generic_danger = bool(
            generic_danger and not overheat and not interdicted
            and not getattr(self, "current_docked", False)
            and not getattr(self, "current_landed", False)
            and not getattr(self, "current_on_foot", False)
            and not getattr(self, "current_in_srv", False)
            and not getattr(self, "current_in_fighter", False)
        )
        checks = (
            ("overheat", overheat, "OVERHEATING", "Ship temperature above 100%", "warn"),
            ("danger", generic_danger, "DANGER", "Ship is in danger", "warn"),
            ("interdicted", interdicted, "INTERDICTION", "Interdiction in progress", "warn"),
        )
        emitted = getattr(self, "_toast_status_last_emitted", {})
        now = time.monotonic()
        if overheat or interdicted:
            emitted["danger"] = now
        for key, enabled, title, message, severity in checks:
            if enabled and key not in active:
                active.add(key)
                cooldown = 300.0 if key == "danger" else 0.0
                may_emit = now - float(emitted.get(key, -cooldown)) >= cooldown
                if toast and may_emit:
                    toast.push(title, message, severity=severity, duration_s=12)
                if may_emit:
                    emitted[key] = now
            elif not enabled:
                active.discard(key)

        if isinstance(flags2, int) and flags2 & 0x0001:
            for key, label, value in (
                ("oxygen", "OXYGEN", data.get("Oxygen")),
                ("health", "SUIT HEALTH", data.get("Health")),
            ):
                try:
                    pct = float(value) * 100
                except (TypeError, ValueError):
                    continue
                triggered = next((n for n in (10, 25, 50) if pct <= n), None)
                state_key = f"{key}_{triggered}" if triggered else None
                old_keys = {item for item in active if item.startswith(f"{key}_")}
                if state_key and state_key not in active:
                    active.difference_update(old_keys)
                    active.add(state_key)
                    if toast:
                        toast.push(f"LOW {label}" if key == "oxygen" else f"LOW {label}", f"{pct:.0f}% remaining", severity="fail" if pct <= 25 else "warn", duration_s=15)
                elif not state_key and pct > 55:
                    active.difference_update(old_keys)

            try:
                temperature = float(data.get("Temperature"))
            except (TypeError, ValueError):
                temperature = None
            temp_danger = temperature is not None and (temperature < 180 or temperature > 330)
            if temp_danger and "suit_temperature" not in active:
                active.add("suit_temperature")
                if toast:
                    toast.push("SUIT TEMPERATURE", f"{temperature:.0f} K — environmental hazard", severity="warn", duration_s=15)
            # Wide recovery band (matching the oxygen/health checks' generous
            # margin above) so ambient temperature hovering near the trigger
            # on a hot/cold world can't flap in and out of a narrow gap and
            # re-toast repeatedly.
            elif temperature is not None and 210 <= temperature <= 300:
                active.discard("suit_temperature")

        legal = data.get("LegalState")
        previous = getattr(self, "_toast_legal_state", None)
        if previous is not None and legal and legal != previous and legal not in ("Clean", "Allied"):
            if toast:
                toast.push("LEGAL STATUS", str(legal).replace("PassengerWanted", "Passenger Wanted"), severity="warn", duration_s=15)
        if legal:
            self._toast_legal_state = legal
        self._toast_status_alerts = active
        self._toast_status_last_emitted = emitted

    def _check_low_fuel(self):
        """Toast once when main tank drops below threshold; re-arms once it
        recovers past the threshold with a small hysteresis band, and stays
        silent while docked/on-foot/in SRV or fighter where it's not urgent."""
        cap = getattr(self, "fuel_capacity_main", None)
        main = getattr(self, "current_fuel_main", None)
        if not cap or cap <= 0 or main is None:
            return
        if self.current_docked or self.current_on_foot or self.current_in_srv or self.current_in_fighter:
            return
        toast_hud = getattr(self, "toast_hud", None)
        if not toast_hud:
            return
        pct = main / cap
        threshold = float(self.config.get("low_fuel_threshold_pct", 0.25) or 0.25)
        if pct < threshold:
            if not self._low_fuel_warned:
                self._low_fuel_warned = True
                if toast_hud:
                    toast_hud.push("LOW FUEL", f"Main tank at {int(pct*100)}%  ({main:.1f}/{cap:.1f}T)", severity="warn", duration_s=15)
        elif pct > threshold + 0.05:
            self._low_fuel_warned = False

    def update_scan_hud(self):
        pass  # ScanHUD overlay removed — scan data now lives on the main dashboard

    def _rebuild_scan_index(self):
        self.scan_items_by_id = {}
        for item in self.scan_items:
            self._normalize_scan_item(item)
            body_id = item.get("body_id")
            if body_id is not None:
                self.scan_items_by_id[body_id] = item
            self.save_scan_item_to_db(self.current_sys, item)
        self._reconcile_scan_progress_from_cache()

    def _rebuild_system_state_from_scan_items(self):
        """Rebuild valuable_bodies, system_bio_signals, and star_class from
        scan_items loaded from the DB. Needed when the journal tail doesn't
        cover the Scan/FSSBodySignals events that originally populated these
        fields (e.g. the system was entered in an older journal file)."""
        bio_total = 0
        primary_star = None
        for item in self.scan_items:
            bio_total += int(item.get("bio_count") or 0)
            p_class = item.get("planet_class", "")
            terraformable = item.get("terraformable", False)
            if p_class in ("Earthlike body", "Water world", "Ammonia world") or terraformable:
                body_name_str = item.get("name", "Unknown")
                if not any(body_name_str in b for b in self.valuable_bodies):
                    icon = "🌍" if p_class == "Earthlike body" else \
                           "💧" if p_class == "Water world" else \
                           "☣️" if p_class == "Ammonia world" else "🛠️"
                    self.valuable_bodies.append(f"- {icon} {body_name_str}")
                    self.valuable_system = True
            if item.get("is_star") and item.get("star_type"):
                bid = item.get("body_id", 9999)
                if primary_star is None or bid < primary_star.get("body_id", 9999):
                    primary_star = item
        self.system_bio_signals = bio_total
        if not self.star_class and primary_star:
            self.star_class = primary_star.get("star_type")

    def _reconcile_scan_progress_from_cache(self):
        cached_ids = set()
        for item in self.scan_items:
            body_id = item.get("body_id")
            if body_id is not None:
                cached_ids.add(body_id)
        if cached_ids:
            before = len(self.scanned_bodies)
            self.scanned_bodies.update(cached_ids)
            if len(self.scanned_bodies) != before:
                for body_id in cached_ids:
                    self.db_add_body(self.current_sys, body_id)
        cached_count = len(self.scanned_bodies)
        if cached_count > self.scanned:
            self.scanned = cached_count
        if self.total < self.scanned:
            self.total = self.scanned
        if self.current_sys and (cached_count or self.total):
            self.db_update_system(self.current_sys, self.total, self.scanned)

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
        if item.get("system_address") is None and getattr(self, "current_system_address", None) is not None:
            item["system_address"] = self.current_system_address

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
            body_class = star_type_label(star_type, include_star=True)
            icons = ["★"]
        else:
            body_class = planet_class or "Unknown"
            icons = []

        terraformable = data.get("TerraformState") == "Terraformable"
        landable = data.get("Landable", False)
        was_discovered = data.get("WasDiscovered", True)
        was_mapped = data.get("WasMapped", True)
        was_footfalled = data.get("WasFootfalled")
        first_footfall = bool(landable and was_footfalled is False)

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
        signal_state = self.body_signals.get(body_id, {}) if body_id is not None else {}
        dss_complete = (
            was_mapped
            or (body_id in self.body_dss_complete)
            or bool(signal_state.get("dss_complete"))
        )

        bio_count = 0
        if "BioSignals" in data:
            for signal in data.get("BioSignals", []):
                if signal.get("Type_Localised") == "Biological":
                    bio_count += signal.get("Count", 0)
        elif signal_state:
            bio_count = signal_state.get("bio", 0)

        highlight = (bio_count > 0) or (not is_star and dss_reward > reward)
        color = COLOR_ACCENT if highlight else COLOR_TEXT

        ts = int(time.time())
        item = {
            "body_id": body_id,
            "system_address": data.get("SystemAddress") or getattr(self, "current_system_address", None),
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
            "distance_to_arrival": data.get("DistanceFromArrivalLS"),
            "surface_temp": data.get("SurfaceTemperature"),
            "surface_gravity": data.get("SurfaceGravity"),
            "gravity_g": self._gravity_to_g(data.get("SurfaceGravity")),
            "parents": list(data.get("Parents") or []),
            "rings": list(data.get("Rings") or []),
            "reserve_level": data.get("ReserveLevel"),
            "rotation_period": data.get("RotationPeriod"),
            "orbital_period": data.get("OrbitalPeriod"),
            "semi_major_axis": data.get("SemiMajorAxis"),
            "eccentricity": data.get("Eccentricity"),
            "axial_tilt": data.get("AxialTilt"),
            "tidal_lock": bool(data.get("TidalLock", False)),
            "age_my": data.get("Age_MY"),
            "luminosity": data.get("Luminosity"),
            "absolute_magnitude": data.get("AbsoluteMagnitude"),
            "atmosphere": data.get("Atmosphere") or data.get("AtmosphereType"),
            "atmosphere_type": data.get("AtmosphereType") or data.get("Atmosphere"),
            "atmosphere_composition": list(data.get("AtmosphereComposition") or []),
            # Published species requirements are bounded by pressure as well as
            # gravity and temperature, so the reported value is retained.
            "surface_pressure": data.get("SurfacePressure"),
            "volcanism": data.get("Volcanism"),
            "icons": icons,
            "color": color,
            "reward": reward,
            "dss_reward": dss_reward,
            "dss_complete": dss_complete,
            "bio_count": bio_count,
            "geo_count": signal_state.get("geo", 0),
            "genuses": list(signal_state.get("genuses") or []),
            "is_star": is_star,
            "was_discovered": was_discovered,
            "was_footfalled": was_footfalled,
            "first_footfall": first_footfall,
            "_ts": ts
        }
        region_id, system_coords = self._bio_location_context()
        item["predicted_genuses"] = bio_values.predict_genera(
            planet_class,
            item.get("atmosphere_type"),
            item.get("surface_temp"),
            item.get("gravity_g"),
            item.get("volcanism"),
            item.get("surface_pressure"),
            region_id,
            system_coords,
        )

        existing = None
        if body_id is not None:
            existing = self.scan_items_by_id.get(body_id)
        if existing:
            # Elite emits a fresh Detailed Scan immediately after
            # SAASignalsFound. Preserve the DSS genus identification and any
            # later organic progress instead of replacing it with the newer
            # planet record.
            for key in (
                "genuses", "organic_scans", "organic_complete_count",
                "geo_count",
            ):
                if existing.get(key) not in (None, [], {}):
                    item[key] = existing[key]
            self.scan_items.remove(existing)
        self.scan_items.insert(0, item)
        self.scan_items = self.scan_items[:60]
        if body_id is not None:
            self.scan_items_by_id[body_id] = item
        self.save_scan_item_to_db(self.current_sys, item)
