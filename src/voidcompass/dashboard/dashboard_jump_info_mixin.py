"""Jump Info overlay: follows the hyperspace jump phase and EDSM's facts."""
from __future__ import annotations

import time

from voidcompass.dashboard.jump_clock import JumpClock
from voidcompass.exploration.galactic_regions import find_region
from voidcompass.overlays.jump_info_hud import build_jump_info_model, linger_seconds

# EDSM's facts for a system change slowly; a route revisited within the
# session reuses them rather than asking again.
_INTEL_TTL_S = 1800.0
_INTEL_CACHE_SIZE = 48


class DashboardJumpInfoMixin:
    def _jump_info_observe(self, event, raw, startup_replay=False):
        """FSDTarget names the next hop before the drive charges, so EDSM is
        asked then; StartJump confirms (or changes) the target."""
        if startup_replay or not isinstance(raw, dict):
            return
        if event == "FSDTarget":
            name = str(raw.get("Name") or "").strip()
            if name:
                self._jump_info_target = {
                    "name": name, "address": raw.get("SystemAddress"),
                    "star_class": str(raw.get("StarClass") or ""),
                }
                self._jump_info_prefetch(name)
        elif event == "StartJump" and str(raw.get("JumpType") or "").casefold() == "hyperspace":
            name = str(raw.get("StarSystem") or "").strip()
            if name:
                self._jump_info_target = {
                    "name": name, "address": raw.get("SystemAddress"),
                    "star_class": str(raw.get("StarClass") or ""),
                }
                self._jump_info_prefetch(name)

    def _jump_info_prefetch(self, name):
        key = str(name or "").strip().casefold()
        if not key:
            return False
        cache = self.__dict__.setdefault("_jump_info_intel", {})
        pending = self.__dict__.setdefault("_jump_info_pending", set())
        cached = cache.get(key)
        if cached and time.monotonic() - cached[0] < _INTEL_TTL_S and cached[1].get("available", True):
            return False
        if key in pending:
            return False
        edsm = getattr(self, "edsm", None)
        fetch = getattr(edsm, "fetch_jump_intel", None)
        if not callable(fetch):
            return False
        pending.add(key)

        def arrived(intel):
            def apply():
                pending.discard(key)
                if isinstance(intel, dict):
                    cache[key] = (time.monotonic(), intel)
                    while len(cache) > _INTEL_CACHE_SIZE:
                        cache.pop(min(cache, key=lambda item: cache[item][0]))
                self._update_jump_info()
            self._ui_post(apply, key=f"jump-intel-{key}")

        fetch(name, arrived)
        return True

    def _jump_info_current_region(self):
        try:
            position = tuple(float(value) for value in getattr(self, "current_coords", None) or ())[:3]
        except (TypeError, ValueError):
            return None
        region = find_region(*position) if len(position) == 3 else None
        return region[1] if region else None

    def _jump_info_model(self, phase):
        target = dict(getattr(self, "_jump_info_target", None) or {})
        jump_target = str(getattr(self, "_navigation_jump_target", "") or "").strip()
        if jump_target and jump_target.casefold() != str(target.get("name") or "").casefold():
            target = {"name": jump_target}
        if not target.get("name"):
            return None
        cached = (getattr(self, "_jump_info_intel", None) or {}).get(target["name"].casefold())
        return build_jump_info_model(
            phase, target,
            route_entries=getattr(self, "nav_route_entries", None) or (),
            intel=cached[1] if cached else None,
            current_region=self._jump_info_current_region(),
            find_region=find_region,
        )

    def _update_jump_info(self):
        """Show Jump Info while the drive charges and in witch space."""
        hud = getattr(self, "jump_info_hud", None)
        if hud is None:
            return False
        phase = str(getattr(self, "_navigation_jump_phase", "") or "")
        if phase in {"charging", "hyperspace"}:
            return hud.update(self._jump_info_model(phase))
        if phase == "arrival" and hud.visible and not hud.lingering:
            # The last model already shows the system just reached.
            model = dict(getattr(hud, "_html_render_model", None) or {})
            if model:
                model["phase"] = "arrival"
            return hud.linger(model, linger_seconds(self.config))
        if hud.lingering and phase in {"", "arrival"}:
            return False
        return hud.clear()

    # ------------------------------------------------------------ jump clock
    # 5.6.9: the Navigation HUD counts down to the real jump, timed from the
    # commander's own jumps (jump_clock.py).
    def _jump_clock(self):
        profile_path = getattr(self, "_profile_path", None)
        try:
            path = profile_path("jump_timing.json") if callable(profile_path) else ""
        except Exception:
            path = ""
        held = self.__dict__.get("_jump_clock_held")
        if not held or held[0] != path:
            held = self._jump_clock_held = (path, JumpClock.load(path) if path else JumpClock())
        return held[1]

    def _jump_clock_view(self):
        held = self.__dict__.get("_jump_clock_held")
        return held[1].view(time.time()) if held else None

    def _jump_clock_cooldown_view(self):
        held = self.__dict__.get("_jump_clock_held")
        return held[1].cool_view(time.time()) if held else None

    def _jump_clock_status(self, data, was):
        """Status: the charge, the hyperdrive bit, the tunnel and the cooldown, at the file's write time."""
        now = (bool(getattr(self, "current_fsd_charging", False)),
               bool(getattr(self, "current_fsd_hyperdrive_charging", False)),
               bool(getattr(self, "current_fsd_jumping", False)),
               bool(getattr(self, "current_fsd_cooldown", False)))
        was = tuple(was) + (False,) * (4 - len(was))
        if now == was:
            return
        charging, hyper, jumping, cooling = now
        was_charging, was_hyper, was_jumping, was_cooling = was
        written = data.get("_written") if isinstance(data, dict) else None
        at = float(written) if isinstance(written, (int, float)) else time.time()
        clock = self._jump_clock()
        if charging and (not was_charging or (hyper and not was_hyper)):
            clock.charging("hyperspace" if hyper else "supercruise", at)
        elif was_charging and not charging:
            clock.charge_dropped(at)
        if jumping and not was_jumping:
            clock.tunnel(at)
        if cooling and not was_cooling:
            clock.cooling(at)
        elif was_cooling and not cooling and clock.cooled(at):
            clock.save(self._jump_clock_held[0])
        self._jump_clock_hurry(clock)

    def _jump_clock_event(self, event, raw, startup_replay=False):
        if startup_replay or not isinstance(raw, dict):
            return
        if event not in {"StartJump", "FSDJump", "SupercruiseEntry", "SupercruiseExit", "Died", "Shutdown", "LoadGame"}:
            return
        clock = self._jump_clock()
        at = time.time()
        if event == "StartJump":
            kind = str(raw.get("JumpType") or "").casefold()
            if kind in {"hyperspace", "supercruise"}:
                clock.started(kind, at)
        elif event in {"FSDJump", "SupercruiseEntry"}:
            if clock.arrived("hyperspace" if event == "FSDJump" else "supercruise", at):
                clock.save(self._jump_clock_held[0])
        elif event == "SupercruiseExit":
            clock.dropped(at)
        else:
            clock.cancel()
        self._jump_clock_hurry(clock)

    def _jump_clock_hurry(self, clock):
        hurry = getattr(getattr(self, "watcher", None), "hurry", None)
        if callable(hurry):
            hurry(45.0 if clock.jump else 0)
