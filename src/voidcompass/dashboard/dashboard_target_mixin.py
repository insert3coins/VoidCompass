"""🎯 on the deck (5.8.3): plot a route to a system in the game's galaxy map,
with your own key bindings, from the Route plotter, the Dashboard or the
Local API. The steps are in core/galaxy_target.py; the keys go through the
ship commands' presser, on its thread, only while Elite is in front."""
from __future__ import annotations

import logging
import time

from voidcompass.core import elite_keys, galaxy_target


class DashboardTargetMixin:
    def _target_say(self, title, message, severity="info"):
        toast = getattr(self, "toast_hud", None)
        if toast is not None and hasattr(toast, "push"):
            toast.push(title, message, severity=severity, duration_s=4.0)
        feed = getattr(self, "add_event_feed_entry", None)
        if callable(feed):
            feed("ROUTE", f"{title.title()}: {message}", severity="WARN" if severity == "warn" else "INFO")

    def _target_why_not(self, where, focus, flags):
        """Why the galaxy map can't be driven now, or ""."""
        if not self._ship_enabled():
            return "Elite key commands are off (Settings › Voice › Command controls)"
        if self._ship_recording():
            return "a key sequence is being recorded"
        if getattr(self, "_target_running", None):
            return f"already plotting to {self._target_running}"
        if where not in galaxy_target.MAP_ACTIONS:
            return "the galaxy map can't be opened from here"
        if focus not in (galaxy_target.GUI_COCKPIT, galaxy_target.GUI_GALAXY_MAP):
            return "close the screen you have open first"
        stop = galaxy_target.stopped(flags)
        if stop:
            return galaxy_target.WHY[stop]
        for action in galaxy_target.actions_needed(where):
            binding, problem = self._ship_binding(action)
            if binding is None:
                from voidcompass.core import elite_binds
                said = elite_binds.action_label(action)
                return (f"{said} has a key Void Compass can't press" if problem.startswith("odd_key")
                        else f"give {said} a keyboard key in Elite's controls")
        if not self._ship_running(fresh=True):
            return "Elite isn't running"
        return ""

    def _target_system(self, system, address=None, distance_ly=None):
        """Plot a route to ``system`` in the galaxy map. {"ok", "message"}:
        ok means the keys are on their way; how it went is said after."""
        name = galaxy_target.clean_system(system)
        if not name:
            return {"ok": False, "message": "No system to target."}
        destination = getattr(self, "current_destination_details", None) or {}
        if galaxy_target.plotted({"Destination": destination}, self._target_read_navroute(), name, address):
            return {"ok": True, "message": f"{name} is already your destination."}
        flags, where, focus = self._ship_live_status()
        why = self._target_why_not(where, focus, flags)
        if why:
            self._target_say("TARGET", f"{name}: {why}", severity="warn")
            return {"ok": False, "message": f"Can't target {name}: {why}."}
        try:
            from voidcompass.core.native_services import copy_text
            copy_text(name)
        except Exception:
            return {"ok": False, "message": f"Couldn't put {name} on the clipboard."}
        self._target_running = name
        self._ship_queue(self._target_job(name, address, where, focus == galaxy_target.GUI_GALAXY_MAP, distance_ly))
        return {"ok": True, "message": f"Plotting a route to {name} in the galaxy map…"}

    def _target_read_navroute(self):
        """The route plotted in the game (NavRoute.json), or {}."""
        import json
        from pathlib import Path
        folder = (getattr(self, "config", None) or {}).get("journal_path")
        if not folder:
            return {}
        try:
            data = json.loads((Path(folder) / "NavRoute.json").read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _target_job(self, name, address, where, map_open, distance_ly):
        plan = galaxy_target.steps(where, map_open=map_open, distance_ly=distance_ly)

        def job():
            self._target_step = ""
            try:
                problem = self._target_run(plan, name, address, where)
            except Exception:
                logging.exception("Targeting %s failed", name)
                problem = "cancelled"
            finally:
                self._target_running = None
            if problem:
                logging.warning("Targeting %s stopped at '%s': %s (screens: %s)", name, self._target_step, problem,
                                " ".join(getattr(self, "_target_trace", ()) or ()))
            if problem and not map_open and self._ship_live_status()[2] == galaxy_target.GUI_GALAXY_MAP:
                # Left part way: close the map it opened, if it's still the screen.
                binding = self._ship_binding(galaxy_target.MAP_ACTIONS[where])[0]
                if binding is not None:
                    self._ship_presser().press(*binding)
            if problem:
                words = galaxy_target.WHY.get(problem, problem)
                at = f" (at: {self._target_step})" if self._target_step else ""
                self._ui_post(lambda: self._target_say("TARGET", f"{name}: stopped, {words}{at}", severity="warn"))
            else:
                self._ui_post(lambda: self._target_say("TARGET", f"Route plotted to {name}", severity="success"))
            return None
        return job

    def _target_run(self, plan, name, address, where):
        """The steps, on the keys thread. A problem's code, or None."""
        if not self._ship_game().bring_forward():
            return "focus_failed"
        presser = self._ship_presser()
        expected = None
        self._target_trace = []
        for index, step in enumerate(plan):
            if getattr(self, "_closing", False):
                return "cancelled"
            self._target_step = step["label"]
            flags, place, focus = self._ship_live_status()
            self._target_trace.append(f"{index}:gui{focus}")
            if step.get("closing"):
                expected = None
            if place != where:
                return "place_changed"
            stop = galaxy_target.stopped(flags)
            if stop:
                return stop
            if expected is not None and focus != expected:
                return "map_left" if expected == galaxy_target.GUI_GALAXY_MAP else "screen"
            kind = step["do"]
            if kind == "back_if_map":
                if focus != galaxy_target.GUI_GALAXY_MAP:
                    continue
                kind = "press"
            if kind in ("press", "hold", "keys") and index:
                problem = self._ship_pause(galaxy_target.STEP_PAUSE_S, where)
                if problem:
                    return problem
            if kind in ("press", "hold"):
                binding = self._ship_binding(step["action"])[0]
                if binding is None:
                    return "binding_changed"
                hold = step.get("seconds", elite_keys.HOLD_S)
                if not presser.press(*binding, hold=hold):
                    return "lost_front"
                if step["action"] in galaxy_target.MAP_ACTIONS.values():
                    expected = None
            elif kind == "keys":
                if not presser.press(step["key"], step.get("modifiers", ())):
                    return "paste_failed" if step["key"] == "V" else "lost_front"
            elif kind == "wait":
                problem = self._ship_pause(step["seconds"], where)
                if problem:
                    return problem
            elif kind == "focus":
                end = time.monotonic() + step["timeout"]
                while self._ship_live_status()[2] != step["value"]:
                    if time.monotonic() > end:
                        return "map_stuck" if step["value"] == galaxy_target.GUI_GALAXY_MAP else "cockpit_stuck"
                    problem = self._ship_pause(0.05, where)
                    if problem:
                        return problem
                expected = step["value"] if step["value"] == galaxy_target.GUI_GALAXY_MAP else None
            elif kind == "verify":
                end = time.monotonic() + step["timeout"]
                while not galaxy_target.plotted(self._ship_read_status(), self._target_read_navroute(), name, address):
                    if time.monotonic() > end:
                        return "not_taken"
                    time.sleep(0.1)
        return None

    # -- the deck and the Local API ------------------------------------------------------
    def _html_target_system(self, payload):
        payload = payload or {}
        try:
            distance = float(payload.get("distance_ly")) if payload.get("distance_ly") not in (None, "") else None
        except (TypeError, ValueError):
            distance = None
        address = payload.get("address")
        try:
            address = int(address) if address not in (None, "") else None
        except (TypeError, ValueError):
            address = None
        result = self._target_system(payload.get("system"), address=address, distance_ly=distance)
        if not result["ok"] or "already" in result["message"]:
            toast = getattr(self, "toast_hud", None)
            if result["ok"] and toast is not None and hasattr(toast, "push"):
                toast.push("TARGET", result["message"], severity="info", duration_s=3.0)
        return result["ok"]

    def api_target_system(self, system, address=None):
        from voidcompass.services.local_api import ApiError
        result = self._target_system(system, address=address)
        if not result["ok"]:
            raise ApiError(409, result["message"])
        return result
