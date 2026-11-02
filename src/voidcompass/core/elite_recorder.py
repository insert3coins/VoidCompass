"""Record bound Elite actions and timing, never keys typed outside the game."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
import os
import threading
import time
import uuid

from voidcompass.core import elite_binds, elite_keys, elite_macros

POLL_S = 0.02
MAX_RECORD_S = 120.0
MAX_EVENTS = 30


@dataclass(frozen=True)
class Binding:
    action: str
    trigger: str
    modifiers: frozenset
    label: str
    playable: bool


def _tokens(binds, device, key):
    if device.casefold() == "keyboard":
        return ("key:" + elite_keys.key_name(key),) if elite_keys.scancode(key) else ()
    pad = binds._pad_name(device, key)
    if pad:
        return ("pad:" + pad,)
    found = []
    for ident in binds._device_ids(device):
        name = binds._joy_name(device, key, ident)
        if name:
            found.append(f"hat:{ident}:{name[4:]}" if name.startswith("hat ") else f"joy:{ident}:{name}")
    return tuple(found)


def bindings_for(binds, place):
    """Only the current vehicle and General bindings, including secondary keys."""
    bindings = []
    for group in ("general", {"ship": "ship", "srv": "srv", "foot": "onfoot"}[place]):
        for action, slots in binds.actions.get(group, {}).items():
            try:
                elite_macros.parse_macro([action])
            except ValueError:
                continue
            playback = elite_keys.keyboard_slot(slots)
            playable = playback is not None and not elite_keys.pressable(*playback)
            for slot in slots:
                modifiers = [_tokens(binds, device, key) for device, key in slot.modifiers]
                if any(len(tokens) != 1 for tokens in modifiers):
                    continue
                for trigger in _tokens(binds, slot.device, slot.key):
                    bindings.append(Binding(action, trigger, frozenset(tokens[0] for tokens in modifiers),
                                            elite_binds.action_label(action), playable))
    return tuple(dict.fromkeys(bindings))


class BoundKeyboard:
    """Poll only keyboard controls found in the active Elite bindings."""
    def __init__(self, bindings):
        if os.name != "nt":
            raise OSError("Sequence recording needs Windows.")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.MapVirtualKeyW.argtypes = [ctypes.c_uint, ctypes.c_uint]
        self.user32.MapVirtualKeyW.restype = ctypes.c_uint
        self.user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.user32.GetAsyncKeyState.restype = ctypes.c_short
        tokens = {token for binding in bindings for token in (binding.trigger, *binding.modifiers)
                  if token.startswith("key:")}
        self.keys = {}
        for token in tokens:
            scan, extended = elite_keys.scancode(token[4:])
            vk = self.user32.MapVirtualKeyW(scan | (0xE000 if extended else 0), 3)
            if vk:
                self.keys[token] = vk

    def snapshot(self):
        return {token for token, vk in self.keys.items() if self.user32.GetAsyncKeyState(vk) & 0x8000}


class SequenceRecorder:
    def __init__(self, bindings, target, place, profile, gap=0.12, clock=time.monotonic):
        self.id = uuid.uuid4().hex
        self.bindings = bindings
        self.target, self.place, self.profile = target, place, profile
        self.gap, self.clock = gap, clock
        self.status = "armed"
        self.note = "Switch to Elite, release held controls, then perform the sequence. Return here to stop."
        self.events = []
        self.choices = {}
        self._lock = threading.RLock()
        self._before = set()
        self._held = {}
        self._began = clock()
        self._started = None
        self._thread = None
        self._stop = threading.Event()

    @property
    def active(self):
        with self._lock:
            return self.status in ("armed", "recording")

    def start(self, snapshot, in_front, context):
        self._thread = threading.Thread(target=self._run, args=(snapshot, in_front, context),
                                        name="elite-sequence-recorder", daemon=True)
        self._thread.start()

    def _run(self, snapshot, in_front, context):
        try:
            while self.active:
                front = in_front()
                # Never sample input while another application has focus.
                self.sample(snapshot() if front else set(), front, context())
                self._stop.wait(POLL_S)
        except Exception:
            self.finish("Recording stopped because its input device could not be read.", failed=True)

    def sample(self, down, front, context):
        with self._lock:
            if not self.active:
                return
            now = self.clock()
            if now - self._began >= MAX_RECORD_S:
                self.finish("The two-minute recording limit was reached.")
                return
            if self.status == "armed":
                if front:
                    if context[0] != self.place:
                        self.finish("The selected vehicle does not match Elite.", failed=True)
                        return
                    self._before = set(down)
                    self._started = now
                    self.status = "recording"
                    self.note = "Recording bound actions in Elite. Return to VoidCompass to stop."
                return
            if not front or context[0] != self.place:
                self.finish("Recording stopped when Elite lost focus." if not front else "Recording stopped when the vehicle changed.")
                return
            for trigger in list(self._held):
                if trigger not in down:
                    self._held.pop(trigger)["end"] = now
            for trigger in sorted(set(down) - self._before):
                matches = [binding for binding in self.bindings
                           if binding.trigger == trigger and binding.modifiers <= set(down)]
                if not matches:
                    continue
                most = max(len(binding.modifiers) for binding in matches)
                matches = list({binding.action: binding for binding in matches if len(binding.modifiers) == most}.values())
                for modifier in set().union(*(binding.modifiers for binding in matches)):
                    if modifier in self._held:
                        self.choices[self._held[modifier]["index"]] = "skip"
                if len(self.events) >= MAX_EVENTS:
                    self.finish("The 30-input recording limit was reached.")
                    return
                event = {"index": len(self.events), "start": now, "end": None, "focus": context[1],
                         "input": trigger, "actions": [{"action": binding.action, "label": binding.label,
                                                        "playable": binding.playable} for binding in matches]}
                self.events.append(event)
                self._held[trigger] = event
            self._before = set(down)

    def finish(self, note="Recording stopped. Review the actions and timing before using it.", failed=False):
        with self._lock:
            if not self.active:
                return
            now = self.clock()
            for event in self._held.values():
                event["end"] = now
            self._held.clear()
            self.status = "failed" if failed else "review"
            self.note = note
            self._stop.set()

    def discard(self):
        self.finish()
        with self._lock:
            self.events.clear()
            self.choices.clear()
            self.status = "discarded"
            self.note = "Recording discarded. Your saved sequence has not changed."

    def choose(self, index, action):
        with self._lock:
            if self.status != "review" or not isinstance(index, int) or not 0 <= index < len(self.events):
                return False
            if action != "skip" and action not in {item["action"] for item in self.events[index]["actions"]}:
                return False
            self.choices[index] = action
            return True

    def state(self):
        with self._lock:
            rows, steps, errors = [], [], []
            previous_end = None
            last_end = None
            for event in self.events:
                choices = event["actions"]
                choice = self.choices.get(event["index"], choices[0]["action"] if len(choices) == 1 else "")
                end = event["end"]
                duration = round(max(.03, (end if end is not None else self.clock()) - event["start"]), 2)
                rows.append({"index": event["index"], "input": event["input"], "actions": choices,
                             "choice": choice, "seconds": duration, "focus": event["focus"]})
                if choice == "skip":
                    continue
                if last_end is not None and event["start"] < last_end:
                    errors.append("Overlapping inputs cannot be replayed in order. Record one action at a time, or skip an overlapping input.")
                last_end = max(last_end or 0, end if end is not None else self.clock())
                if not choice:
                    errors.append("Choose an action for every shared key or button, or skip it.")
                    continue
                if not next(item["playable"] for item in choices if item["action"] == choice):
                    errors.append(f"Bind a keyboard key for {choice} in Elite before recording it again.")
                if duration > elite_macros.MAX_SECONDS:
                    errors.append("A held action exceeded five seconds. Shorten the hold and record again.")
                    continue
                if previous_end is not None:
                    budget = max(0, event["start"] - previous_end - self.gap)
                    while budget > self.gap + .01 and len(steps) <= elite_macros.MAX_STEPS:
                        wait = round(min(elite_macros.MAX_SECONDS, budget - self.gap), 2)
                        steps.append(f"wait {wait:g}")
                        budget -= wait + self.gap
                panel = {"FocusRightPanel": 1, "FocusLeftPanel": 2, "FocusCommsPanel": 3, "FocusRadarPanel": 4}.get(choice.split("_")[0])
                if panel and event["focus"] == 0:
                    steps.append(f"focus {choice} {panel}")
                elif panel and event["focus"] == panel:
                    steps.append(f"leave {choice} {panel}")
                else:
                    steps.append(f"hold {choice} {duration:g}")
                previous_end = end
            if steps:
                try:
                    elite_macros.parse_macro(steps)
                except ValueError as exc:
                    errors.append(str(exc))
            elif self.status == "review":
                errors.append("No bound actions were recorded. Try again using Elite's bound keys or controller buttons.")
            return {"id": self.id, "profile": self.profile, "target": self.target, "place": self.place, "status": self.status,
                    "note": self.note, "events": rows, "steps": steps, "errors": list(dict.fromkeys(errors)),
                    "can_use": self.status == "review" and bool(steps) and not errors}
