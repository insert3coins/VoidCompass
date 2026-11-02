"""Controller buttons as shortcuts, and Elite's own bindings (5.7.3), for
MainDashboard.

Each shortcut in Settings › Hotkeys can have a controller button (or a
combination) beside its keyboard shortcut; ControllerHub reads the
controllers and calls the same handler a hotkey does. "SET" learns
the next press in Void Compass itself (not the web page: WebView2 only sees a
pad while its window has focus). Elite's bindings (elite_binds) say what a
key or button already does in the game, shown beside each shortcut.
"""
from __future__ import annotations

import threading
import time

from voidcompass.core import controller_input
from voidcompass.core.controller_input import ControllerHub
from voidcompass.core.elite_binds import EliteBinds, hotkey_control
from voidcompass.core.overlay_registry import OVERLAY_HOTKEY_SPECS

CLASHES_SHOWN = 3
LIVE_WATCH_S = 20.0


class DashboardControllerMixin:
    # -- the hub ----------------------------------------------------------------------
    def _controller_hub(self):
        hub = getattr(self, "_controller_input", None)
        if hub is None:
            hub = self._controller_input = ControllerHub(bindings=self._controller_bindings,
                                                         on_press=self._controller_pressed)
        return hub

    def _controller_bindings(self):
        """{action: spec} for the shortcuts with a controller button, when they're on."""
        if not self.config.get("controller_hotkeys_enabled", True):
            return {}
        known = {action for action, _key, _label, _attr in OVERLAY_HOTKEY_SPECS}
        saved = self.config.get("overlay_controller_bindings") or {}
        return {action: spec for action, spec in saved.items() if action in known and controller_input.valid(spec)}

    def _configure_controller_hotkeys(self):
        """Start reading the controllers once any button is bound (idle, it barely polls)."""
        if self._controller_bindings():
            self._controller_hub().start()

    def _controller_pressed(self, action, spec):
        """A bound button went down (on the hub's thread): the same as its hotkey."""
        if getattr(self, "_closing", False):
            return
        if callable(getattr(self, "_ship_recording", None)) and self._ship_recording():
            return
        if action == "watcher_talk":
            hub = self._controller_hub()
            # Held, it listens until you let go of the button, not a key.
            self._ui_post(lambda: self._watcher_talk_key(held=lambda: hub.is_down(spec)))
            return
        self._ui_post(self._handle_overlay_hotkey, action, key=f"controller:{action}")

    def _controller_close(self):
        hub = getattr(self, "_controller_input", None)
        if hub is not None:
            hub.stop()

    # -- Elite's bindings ---------------------------------------------------------------
    def _elite_binds(self):
        binds = getattr(self, "_elite_bindings", None)
        if binds is None:
            binds = self._elite_bindings = EliteBinds(chosen=lambda: self.config.get("elite_game_folder", ""))
        return binds

    def _elite_clashes(self, control):
        """What a control does in Elite (cached until its bindings change)."""
        if control is None:
            return []
        binds = self._elite_binds()
        binds.refresh()
        cache = getattr(self, "_elite_clash_cache", None)
        if cache is None or cache[0] != binds._stamp:
            cache = self._elite_clash_cache = (binds._stamp, {})
        key = repr((control[0], control[1:-1], sorted(control[-1])))
        if key not in cache[1]:
            cache[1][key] = binds.clashes(control)
        return cache[1][key]

    def _elite_hotkey_clashes(self, canonical):
        return self._elite_clashes(hotkey_control(canonical))

    def _elite_button_clashes(self, spec):
        return self._elite_clashes(controller_input.elite_control(spec))

    # -- the Settings page ----------------------------------------------------------------
    def _html_controller_settings(self):
        hub = self._controller_hub()
        names = hub.names()
        saved = self.config.get("overlay_controller_bindings") or {}
        buttons = {}
        for action, spec in saved.items():
            if controller_input.valid(spec):
                clashes = self._elite_button_clashes(spec)
                buttons[action] = {"spec": spec, "label": controller_input.describe(spec, names),
                                   "clashes": clashes[:CLASHES_SHOWN], "more": max(0, len(clashes) - CLASHES_SHOWN)}
        keys = {}
        for action, key, _label, _attr in OVERLAY_HOTKEY_SPECS:
            clashes = self._elite_hotkey_clashes(self.config.get(key)) if self.config.get(key) else []
            if clashes:
                keys[action] = {"clashes": clashes[:CLASHES_SHOWN], "more": max(0, len(clashes) - CLASHES_SHOWN)}
        binds = self._elite_binds()
        learning = dict(getattr(self, "_controller_learning", None) or {})
        if learning.get("at") and time.time() - learning["at"] > 15 and learning.get("status") != "listening":
            learning = {}
        return {
            "enabled": bool(self.config.get("controller_hotkeys_enabled", True)),
            "buttons": buttons,
            "keys": keys,
            "learning": learning,
            "elite": {"groups": binds.summary(), "error": binds.error},
        }

    def _controller_live(self):
        """/api/data/controllers: the controllers seen and what's held now (polled while you look)."""
        hub = self._controller_hub()
        hub.watch(LIVE_WATCH_S)
        names = hub.names()
        down = sorted(hub.snapshot())
        return {"devices": [dict(row) for row in hub.devices], "down": [controller_input.describe(spec, names)
                                                                        for spec in down],
                "error": hub.error}

    def _handle_controller_command(self, operation, payload):
        """Settings › Hotkeys' controller controls; None when not one of them."""
        if operation == "controller_toggle":
            self.config["controller_hotkeys_enabled"] = bool(payload.get("value"))
            self._persist_config()
            self._configure_controller_hotkeys()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation == "controller_clear":
            action = str(payload.get("hotkey") or "")
            saved = dict(self.config.get("overlay_controller_bindings") or {})
            if saved.pop(action, None) is None:
                return False
            self.config["overlay_controller_bindings"] = saved
            self._persist_config()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation == "controller_cancel":
            self._controller_hub().cancel_learning()
            return True
        if operation == "controller_learn":
            action = str(payload.get("hotkey") or "")
            if action not in {row[0] for row in OVERLAY_HOTKEY_SPECS}:
                return False
            hub = self._controller_hub()
            hub.cancel_learning()
            self._controller_learning = {"action": action, "status": "listening", "at": time.time()}
            self._schedule_html_dashboard_publish(immediate=True)
            threading.Thread(target=self._controller_learn_run, args=(action,), name="controller-learn",
                             daemon=True).start()
            return True
        return None

    def _controller_learn_run(self, action):
        spec = self._controller_hub().learn()
        self._ui_post(self._controller_learned, action, spec)

    def _controller_learned(self, action, spec):
        """The press learned: kept for that shortcut, unless another already has it."""
        names = self._controller_hub().names()
        if not spec:
            self._controller_learning = {"action": action, "status": "none", "at": time.time(),
                                         "note": "No button was pressed. Press SET to try again."}
        else:
            saved = dict(self.config.get("overlay_controller_bindings") or {})
            labels = {row[0]: row[2] for row in OVERLAY_HOTKEY_SPECS}
            other = next((name for name, held in saved.items() if held == spec and name != action), None)
            if other:
                self._controller_learning = {
                    "action": action, "status": "taken", "at": time.time(),
                    "note": f"{controller_input.describe(spec, names)} is already set for {labels.get(other, other)}."}
            else:
                saved[action] = spec
                self.config["overlay_controller_bindings"] = saved
                self._persist_config()
                self._configure_controller_hotkeys()
                self._controller_learning = {"action": action, "status": "done", "at": time.time(),
                                             "note": f"Set: {controller_input.describe(spec, names)}."}
        self._schedule_html_dashboard_publish(immediate=True)
