"""The Watcher working the ship (5.7.3): a command you typed or said,
pressed in Elite with the keyboard key your bindings give it. watcher_ship
decides what was asked and whether it's done already; elite_keys presses.
Presses run on their own thread, one command after another, so the deck
never waits on the game; anything that goes wrong there is said after.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import queue
import threading
import time

from voidcompass.core import elite_binds, elite_keys, elite_macros, elite_recorder, voice_commands
from voidcompass.core.config import get_active_profile
from voidcompass.overlays import watcher_ship

GAP_S = 0.12            # between two presses of one command
POWER_WAIT_S = 0.7      # Status.json, after a pip press
POWER_PRESSES = 10
PANEL_WAIT_S = 2.0     # Status.json can trail a panel opening by about a second
RUNNING_EVERY_S = 5.0   # the page asks whether Elite is running on every refresh
PLACE_NAMES = {"ship": "Ship", "srv": "SRV", "foot": "On foot"}
POWER_SAY = {"sys": "more power to systems", "eng": "more power to engines", "wep": "more power to weapons",
             "reset": "balance power"}


class DashboardShipControlMixin:
    def _ship_recorder_current(self):
        recorder = getattr(self, "_ship_sequence_recorder", None)
        if recorder is not None and recorder.profile != get_active_profile(self.config):
            recorder.discard()
            self._ship_sequence_recorder = None
            return None
        return recorder

    def _ship_recording(self):
        recorder = self._ship_recorder_current()
        return bool(recorder is not None and recorder.active)

    def _ship_recorder_state(self):
        recorder = self._ship_recorder_current()
        if recorder is not None:
            return recorder.state()
        return {"status": "idle", "note": "", "events": [], "steps": [], "errors": [], "can_use": False}

    def _ship_recording_saved(self, payload, updates):
        recorder = self._ship_recorder_current()
        if recorder is None or recorder.id != payload.get("recording_id"):
            return
        target = recorder.target
        if target == "new":
            ident = str(payload.get("recorded_command_id") or "")
            definition = updates.get("watcher_ship_commands", {}).get(ident)
            if not ident.startswith("custom_") or not definition or recorder.place not in definition.get("places", ()):
                return
            target = ident + ("" if recorder.place == "ship" else ":" + recorder.place)
        elif "watcher_ship_macros" not in updates:
            return
        recorder.mark_saved(target)

    def _handle_sequence_command(self, operation, payload):
        if operation not in {"sequence_record", "sequence_stop", "sequence_discard", "sequence_choose"}:
            return None
        recorder = self._ship_recorder_current()
        if operation != "sequence_record":
            if recorder is None or payload.get("record_id") != recorder.id:
                return False
            if operation == "sequence_stop":
                recorder.finish()
            elif operation == "sequence_discard":
                recorder.discard()
            else:
                index = payload.get("index")
                return type(index) is int and recorder.choose(index, str(payload.get("action") or ""))
            return True
        if recorder is not None and recorder.active:
            return False
        target = str(payload.get("target") or "")
        options = {key: (where, default) for command in voice_commands.catalogue(self.config.get("watcher_ship_commands"), include_disabled=True)
                   for key, where, _op, default in watcher_ship.sequence_options(command)}
        place = payload.get("place") if target == "new" else options.get(target, (None, ()))[0]
        if not isinstance(place, str) or place not in PLACE_NAMES or (target != "new" and target not in options):
            return False
        binds = self._elite_binds()
        binds.refresh()
        bindings = elite_recorder.bindings_for(binds, place)
        profile = get_active_profile(self.config)
        preferred = ()
        if target in options:
            lines = self.config.get("watcher_ship_macros", {}).get(target, options[target][1])
            try:
                preferred = elite_macros.actions_in(elite_macros.parse_macro(lines))
            except ValueError:
                preferred = elite_macros.actions_in(elite_macros.parse_macro(options[target][1]))
        recorder = elite_recorder.SequenceRecorder(bindings, target, place, profile, gap=GAP_S, target_actions=preferred)
        self._ship_sequence_recorder = recorder
        if not bindings or not self._ship_running(fresh=True):
            recorder.finish("Start Elite and make sure its active bindings can be read, then record again.", failed=True)
            return False
        if getattr(self, "_ship_job_active", False) or (getattr(self, "_ship_jobs", None) is not None and not self._ship_jobs.empty()):
            recorder.finish("Wait for the current ship command to finish, then record again.", failed=True)
            return False
        try:
            keyboard = elite_recorder.BoundKeyboard(bindings)
            hub = self._controller_hub()
            hub.watch(elite_recorder.MAX_RECORD_S + 5)
            def context():
                _flags, actual_place, focus = self._ship_live_status()
                if get_active_profile(self.config) != profile or getattr(self, "_closing", False):
                    actual_place = ""
                return actual_place, focus
            recorder.start(lambda: keyboard.snapshot() | hub.snapshot(), self._ship_game().in_front, context)
        except (OSError, RuntimeError):
            recorder.finish("The recorder could not open Windows input. Your saved sequence has not changed.", failed=True)
            return False
        return True

    def _ship_enabled(self):
        return self.config.get("watcher_ship_enabled", True) is not False

    def _ship_game(self):
        game = getattr(self, "_ship_game_window", None)
        if game is None:
            game = self._ship_game_window = elite_keys.GameWindow()
        return game

    def _ship_presser(self):
        presser = getattr(self, "_ship_key_presser", None)
        if presser is None:
            presser = self._ship_key_presser = elite_keys.KeyPresser(self._ship_game().in_front)
        return presser

    def _ship_running(self, fresh=False):
        seen = getattr(self, "_ship_running_seen", None)
        now = time.monotonic()
        if fresh or seen is None or now - seen[0] > RUNNING_EVERY_S:
            seen = self._ship_running_seen = (now, bool(self._ship_game().find()))
        return seen[1]

    def _ship_binding(self, action):
        """((key, modifiers), "") for an Elite action, or (None, "no_key")
        when it has no keyboard key, or (None, "odd_key: <keys>")."""
        binds = self._elite_binds()
        binds.refresh()
        slots = binds.actions.get(elite_binds.group_of(action), {}).get(action) or ()
        found = elite_keys.keyboard_slot(slots)
        if found is None:
            return None, "no_key"
        odd = elite_keys.pressable(*found)
        if odd:
            return None, "odd_key: " + ", ".join(odd)
        return found, ""

    # -- asked ----------------------------------------------------------------------------
    def _watcher_ship(self, text, rng=None):
        """A ship command (5.7.3): its reply, or None when nothing of the
        ship was asked."""
        catalogue = [item for item in voice_commands.catalogue(self.config.get("watcher_ship_commands"))
                     if not hasattr(item, "native")]
        asked = watcher_ship.request(text, catalogue)
        power = None if asked else watcher_ship.power_request(text)
        if power and (power.get("press") or power.get("reset")):
            step = power.get("press") or "reset"
            shortcut = next((item for item in catalogue if item.id == "power_" + step), None)
            if shortcut is None or not shortcut.keep_defaults:
                power = None
        if power is None and asked is None:
            return None
        if self._ship_recording():
            return "Finish recording your sequence before asking me to press Elite's keys."
        if not self._ship_enabled():
            return watcher_ship.reply("ship_off", rng)
        flags, where, focus = self._ship_live_status()
        if power is not None:
            return self._watcher_ship_power(power, where, rng)
        command = next(item for item in catalogue if item.id == asked["command"])
        if hasattr(command, "power_step") and watcher_ship.sequence_key(command, where) not in self.config.get("watcher_ship_macros", {}):
            return self._watcher_ship_power({"reset": True} if command.power_step == "reset" else {"press": command.power_step}, where, rng)
        op = asked["op"]
        fields = watcher_ship.fields(command)
        action = command.action(where, op)
        if action is None:
            return watcher_ship.reply("not_here", rng, where=watcher_ship.WHERE[where])
        if command.kind == "screen" and op == "toggle":
            op = "off" if watcher_ship.screen_shown(command, focus) else "on"
            action = command.action(where, op)
        if command.menu and focus not in range(1, 12):
            return watcher_ship.reply("menu_closed", rng)
        if command.docked and not flags & 1:
            return watcher_ship.reply("not_docked", rng)
        if command.docked and focus != 0:
            return watcher_ship.reply("screen_changed", rng)
        done = watcher_ship.already(command, op, flags, focus, where)
        if done == "not_open":
            return watcher_ship.reply("screen_not_open", rng, **fields)
        if done:
            return watcher_ship.reply("screen_already" if command.kind == "screen" else f"switch_already_{op}",
                                      rng, **fields)
        try:
            steps = self._ship_macro_steps(command, where, op)
        except ValueError as exc:
            return watcher_ship.reply("macro_invalid", rng, reason=str(exc), **fields)
        actions = elite_macros.actions_in(steps) if steps else [action]
        # A missing sequence key names the precise action that needs binding.
        problem = self._ship_cannot(actions, rng, None if steps else fields)
        if problem:
            return problem
        self._ship_queue(self._ship_command_job(command, op, where, steps))
        if command.kind == "screen":
            return watcher_ship.reply("screen_open" if op == "on" else "screen_close", rng, **fields)
        if command.kind == "switch":
            return watcher_ship.reply(f"switch_{op}", rng, **fields)
        if command.done:
            if not command.custom and getattr(rng, "companion_identity", "watcher") != "watcher":
                return watcher_ship.reply("press", rng, **fields)
            return rng.choice(command.done) if rng is not None else command.done[0]
        return watcher_ship.reply("press", rng, **fields)

    def _ship_macro_steps(self, command, where="ship", op="on"):
        overrides = self.config.get("watcher_ship_macros", {})
        if not isinstance(overrides, dict):
            raise ValueError("Sequences must be an object keyed by command name.")
        key = watcher_ship.sequence_key(command, where, op)
        if key in overrides:
            return elite_macros.parse_macro(overrides[key])
        return elite_macros.parse_macro(command.macro) if command.macro else ()

    def _ship_cannot(self, actions, rng, fields=None):
        """Why these actions can't be pressed (its reply), or None."""
        for action in actions:
            binding, problem = self._ship_binding(action)
            if binding is not None:
                continue
            label = dict(fields or {})
            if not label:
                said = elite_binds.action_label(action)
                label = {"Label": said, "label": said.lower(), "label_l": said.lower()}
            if problem.startswith("odd_key"):
                return watcher_ship.reply("odd_key", rng, key=problem.split(": ", 1)[1], **label)
            return watcher_ship.reply("no_key", rng, **label)
        if not self._ship_running(fresh=True):
            return watcher_ship.reply("not_running", rng)
        return None

    def _watcher_ship_power(self, power, where, rng):
        actions = watcher_ship.POWER_ACTIONS.get("ship" if where == "fighter" else where)
        if actions is None:
            return watcher_ship.reply("not_here", rng, where=watcher_ship.WHERE[where])
        if power.get("invalid"):
            return watcher_ship.reply("power_invalid", rng)
        current = getattr(self, "current_pips", None)
        current = tuple(current) if current else None
        target = power.get("target")
        if power.get("reset"):
            target = watcher_ship.BALANCED
            steps = [] if current == target else ["reset"]
        elif power.get("press"):
            steps = [power["press"]]
        else:
            steps = watcher_ship.plan_power(current, target)
            if steps is None:
                return watcher_ship.reply("power_invalid", rng)
        if not steps:
            return watcher_ship.reply("power_already", rng, pips=watcher_ship.pips_words(target))
        problem = self._ship_cannot([actions[step] for step in dict.fromkeys(steps)], rng)
        if problem:
            return problem
        self._ship_queue(self._ship_power_job(None if power.get("press") or power.get("reset") else target,
                                              steps, actions))
        if power.get("reset"):
            return watcher_ship.reply("power_reset", rng)
        if power.get("press"):
            name = watcher_ship.SYSTEM_NAMES[watcher_ship.SYSTEMS[power["press"]]]
            return watcher_ship.reply("power_press", rng, system=name)
        return watcher_ship.reply("power_set", rng, pips=watcher_ship.pips_words(target))

    # -- pressed (on its own thread) -----------------------------------------------------------
    def _ship_queue(self, job):
        job.companion_generation = getattr(self, "_companion_generation", 0)
        jobs = getattr(self, "_ship_jobs", None)
        if jobs is None:
            jobs = self._ship_jobs = queue.Queue()
            threading.Thread(target=self._ship_worker, args=(jobs,), name="ship-keys", daemon=True).start()
        jobs.put(job)

    def _ship_worker(self, jobs):
        while True:
            job = jobs.get()
            if job is None or getattr(self, "_closing", False):
                return
            try:
                self._ship_job_active = True
                problem = job()
            except Exception:
                logging.exception("A ship command failed")
                problem = "press_failed"
            finally:
                self._ship_job_active = False
            if problem and not getattr(self, "_closing", False) and getattr(job, "companion_generation", 0) == getattr(self, "_companion_generation", 0):
                generation = getattr(self, "_companion_generation", 0)
                self._ui_post(lambda outcome=problem, expected=generation: self._watcher_ship_follow_up(outcome) if expected == getattr(self, "_companion_generation", 0) else None)

    def _ship_close(self):
        recorder = getattr(self, "_ship_sequence_recorder", None)
        if recorder is not None:
            recorder.discard()
        jobs = getattr(self, "_ship_jobs", None)
        if jobs is not None:
            jobs.put(None)

    def _ship_read_status(self):
        folder = self.config.get("journal_path")
        if not folder:
            return {}
        try:
            data = json.loads((Path(folder) / "Status.json").read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _ship_live_status(self):
        data = self._ship_read_status()

        def value(name, attribute, default=0):
            fallback = getattr(self, attribute, default)
            try:
                return int(data.get(name, fallback))
            except (TypeError, ValueError, OverflowError):
                return fallback

        flags = value("Flags", "current_status_flags")
        flags2 = value("Flags2", "current_status_flags2")
        focus = value("GuiFocus", "current_gui_focus", -1)
        return flags, watcher_ship.place(flags, flags2), focus

    def _ship_pause(self, seconds, where):
        """Wait on the keys thread, stopping if the game loses focus or closes."""
        end = time.monotonic() + seconds
        while True:
            if getattr(self, "_closing", False):
                return "cancelled"
            if self._ship_recording():
                return "cancelled"
            if not self._ship_game().in_front():
                return "lost_front"
            if self._ship_live_status()[1] != where:
                return "place_changed"
            remaining = end - time.monotonic()
            if remaining <= 0:
                return None
            time.sleep(min(0.05, remaining))

    def _ship_focus_panel(self, step, where, presser, binding):
        focus = self._ship_live_status()[2]
        if focus == step.focus:
            return None
        if focus != 0:
            return "screen_changed"
        if not presser.press(*binding, hold=0.15):
            return "lost_front"
        end = time.monotonic() + PANEL_WAIT_S
        while time.monotonic() < end:
            problem = self._ship_pause(0.05, where)
            if problem:
                return problem
            focus = self._ship_live_status()[2]
            if focus == step.focus:
                return None
            if focus != 0:
                return "screen_changed"
        return "screen_stuck"

    def _ship_command_job(self, command, op, where, steps):
        """Check state again when the queue reaches this request. Two quick
        'open map' requests must not become an open followed by a close."""
        generation = getattr(self, "_companion_generation", 0)
        def job():
            if generation != getattr(self, "_companion_generation", 0):
                return "cancelled"
            if getattr(self, "_closing", False):
                return "cancelled"
            if self._ship_recording():
                return "cancelled"
            if not self._ship_game().bring_forward():
                return "focus_failed"
            flags, actual_place, focus = self._ship_live_status()
            if actual_place != where:
                return "place_changed"
            if command.menu and focus not in range(1, 12):
                return "menu_closed"
            if command.docked and not flags & 1:
                return "not_docked"
            if command.docked and focus != 0:
                return "screen_changed"
            if watcher_ship.already(command, op, flags, focus, where):
                return None
            presser = self._ship_presser()
            if not steps:
                binding = self._ship_binding(command.action(where, op))[0]
                if binding is None:
                    return "binding_changed"
                if generation != getattr(self, "_companion_generation", 0):
                    return "cancelled"
                return None if presser.press(*binding) else "lost_front"
            expected_focus = 0 if command.docked else None
            for index, step in enumerate(steps):
                if generation != getattr(self, "_companion_generation", 0):
                    return "cancelled"
                problem = self._ship_pause(GAP_S if index else 0, where)
                if problem:
                    return problem
                if generation != getattr(self, "_companion_generation", 0):
                    return "cancelled"
                if step.kind == "wait":
                    problem = self._ship_pause(step.seconds, where)
                    if problem:
                        return problem
                    continue
                binding = self._ship_binding(step.action)[0]
                if binding is None:
                    return "binding_changed"
                focus = self._ship_live_status()[2]
                if step.kind == "focus":
                    problem = self._ship_focus_panel(step, where, presser, binding)
                    if problem:
                        return problem
                    expected_focus = step.focus
                    continue
                if step.kind == "leave":
                    if focus == 0:
                        expected_focus = None
                        continue
                    if focus != step.focus:
                        return "screen_changed"
                elif expected_focus is not None and focus != expected_focus:
                    return "screen_changed"
                if not presser.press(*binding, hold=step.seconds if step.kind == "hold" else elite_keys.HOLD_S):
                    return "lost_front"
                if step.kind == "leave":
                    expected_focus = None
            return None
        return job

    def _ship_read_pips(self):
        """The distributor, straight from Status.json (the deck's own copy
        is a second behind)."""
        data = self._ship_read_status()
        pips = data.get("Pips") if isinstance(data, dict) else None
        if isinstance(pips, list) and len(pips) == 3 and all(isinstance(value, (int, float)) for value in pips):
            return tuple(int(value) for value in pips)
        return None

    def _ship_wait_pips(self, before):
        end = time.monotonic() + POWER_WAIT_S
        latest = None
        while time.monotonic() < end:
            latest = self._ship_read_pips() or latest
            if latest is not None and latest != before:
                return latest
            time.sleep(0.05)
        return latest

    def _ship_power_job(self, target, steps, actions):
        """Presses for the distributor. Aiming at ``target``, it reads the
        pips back after each press and plans again if the game disagreed."""
        generation = getattr(self, "_companion_generation", 0)
        def job():
            if generation != getattr(self, "_companion_generation", 0):
                return "cancelled"
            if self._ship_recording():
                return "cancelled"
            if not self._ship_game().bring_forward():
                return "focus_failed"
            presser = self._ship_presser()
            plan = list(steps)
            state = self._ship_read_pips() if target is not None else None
            if state is not None:
                # Planned from the deck's copy, a second behind: planned again from the game's.
                plan = watcher_ship.plan_power(state, target) or []
            for count in range(POWER_PRESSES):
                if generation != getattr(self, "_companion_generation", 0):
                    return "cancelled"
                if self._ship_recording():
                    return "cancelled"
                if not plan:
                    return None if target is None or state in (None, tuple(target)) else "power_stuck"
                step = plan.pop(0)
                binding = self._ship_binding(actions[step])[0]
                if binding is None:
                    return "power_stuck"
                if count:
                    time.sleep(GAP_S)
                if generation != getattr(self, "_companion_generation", 0):
                    return "cancelled"
                if not presser.press(*binding):
                    return "lost_front"
                if target is None:
                    continue
                expected = (watcher_ship.BALANCED if step == "reset"
                            else watcher_ship.press_power(state, step) if state else None)
                before, state = state, self._ship_wait_pips(state)
                if state is None or state == tuple(target):
                    if state is not None:
                        return None
                    continue
                if before is not None and state == before and expected != before:
                    return "power_stuck"
                if expected is not None and state != expected:
                    plan = watcher_ship.plan_power(state, target) or []
            return None if target is None or state in (None, tuple(target)) else "power_stuck"
        return job

    def _watcher_ship_follow_up(self, outcome):
        mind = getattr(getattr(self, "heartbeat_hud", None), "mind", None)
        line = watcher_ship.reply(outcome, getattr(mind, "random", None))
        if mind is not None:
            mind.say_after(line)
            self._watcher_mind_watch()
        elif callable(getattr(self, "add_event_feed_entry", None)):
            self.add_event_feed_entry("SYSTEM", f"The Watcher: {line}", severity="INFO")

    # -- Settings › Voice ---------------------------------------------------------------------
    def _html_ship_controls(self):
        """What it can do in Elite, the key each needs, and which have none."""
        binds = self._elite_binds()
        binds.refresh()
        presets = {row["group"]: row["preset"] for row in binds.summary()}
        keys = {}

        def key_for(action):
            if action not in keys:
                binding, problem = self._ship_binding(action)
                keys[action] = (elite_keys.label(*binding) if binding else "",
                                "" if binding else problem.split(":")[0])
            return keys[action]

        groups, missing = {}, {}

        def row(say, places, sequence=(), error=""):
            cells = []
            for where, action in places:
                key, problem = key_for(action)
                cells.append({"where": PLACE_NAMES.get(where, where), "action": elite_binds.action_label(action),
                              "key": key, "problem": problem})
                if problem and action not in missing:
                    group = elite_binds.group_of(action)
                    missing[action] = {"action": elite_binds.action_label(action), "say": say,
                                       "where": PLACE_NAMES.get(where, where), "group": group,
                                       "preset": f"{elite_binds.GROUP_LABELS[group]} · {presets.get(group, '?')}"}
            places = {cell["where"] for cell in cells}
            ready = sum(all(not cell["problem"] for cell in cells if cell["where"] == place) for place in places)
            state = ("ready" if ready == len(places) else "some" if ready else "none") if places and not error else "none"
            return {"say": say, "cells": cells, "state": state, "sequence": list(sequence), "error": error}

        for command in voice_commands.catalogue(self.config.get("watcher_ship_commands"), include_disabled=True):
            places, editors, errors = [], [], []
            overrides = self.config.get("watcher_ship_macros", {})
            for key, where, op, default in watcher_ship.sequence_options(command):
                configured = overrides.get(key, default) if isinstance(overrides, dict) else default
                error, actions = "", ()
                try:
                    steps = self._ship_macro_steps(command, where, op)
                    actions = elite_macros.actions_in(steps) if steps else (command.action(where, op),)
                    places += [(where, action) for action in actions if (where, action) not in places]
                except ValueError as exc:
                    error = str(exc)
                    errors.append(error)
                editors.append({"id": key, "where": PLACE_NAMES.get(where, where),
                                "say": f"close {command.say}" if op == "off" else command.example,
                                "sequence": list(configured) if isinstance(configured, (list, tuple)) else [],
                                "default_sequence": list(default), "error": error,
                                "ready": not error and bool(actions) and all(not key_for(action)[1] for action in actions)})
            main = editors[0] if editors else {}
            sequence = main.get("sequence", ())
            error = "; ".join(dict.fromkeys(errors))
            item = row(command.example, places, sequence, error)
            item.update(id=command.id, name=command.say, native=getattr(command, "native", None), phrase=command.example, aliases=list(command.aliases),
                        group=command.group, enabled=command.enabled, custom=command.custom,
                        reply=(command.done or ("Done.",))[0],
                        keep_defaults=command.keep_defaults, places=list(command.actions),
                        default_sequence=main.get("default_sequence", []), editors=editors)
            ready = sum(editor["ready"] for editor in editors)
            item["state"] = "ready" if hasattr(command, "native") or (ready == len(editors) and editors) else "some" if ready else "none"
            groups.setdefault(command.group, []).append(item)
        rows = [item for items in groups.values() for item in items]
        order = {group: index for index, group in enumerate(elite_binds.GROUPS)}
        return {
            "enabled": self._ship_enabled(),
            "running": self._ship_running(),
            "error": binds.error,
            # Ready: it works somewhere (the galaxy map in the ship, if not on foot).
            "ready": sum(1 for item in rows if item["state"] != "none" and item.get("enabled", True)),
            "total": len(rows),
            "groups": [{"title": title, "rows": items} for title, items in groups.items()],
            "macros": self.config.get("watcher_ship_macros") or {},
            "definitions": self.config.get("watcher_ship_commands") or {},
            "missing": sorted(missing.values(), key=lambda row: order.get(row["group"], 9)),
        }
