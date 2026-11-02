"""Small sequences of Elite actions, resolved through the commander's bindings.

Like Starling's macros: actions, repeats, waits and held keys. ``focus``
opens a panel only if needed and waits for Status.json; ``leave`` closes
only that panel. There are no literal desktop keys or shell commands.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re

MAX_STEPS = 60
MAX_REPEAT = 12
MAX_SECONDS = 5.0
_ACTION = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Step:
    kind: str
    action: str = ""
    seconds: float = 0.0
    focus: int = -1


def parse_macro(lines):
    """Parse a list of action steps; reject the whole sequence on an error."""
    if not isinstance(lines, (list, tuple)) or not lines or len(lines) > MAX_STEPS:
        raise ValueError("Use a list of 1 to 60 steps.")
    steps = []
    for line in lines:
        if not isinstance(line, str):
            raise ValueError("Each step must be text.")
        words = line.split()
        if not words:
            raise ValueError("A step cannot be empty.")
        kind = words[0].lower()
        try:
            if kind == "wait" and len(words) == 2:
                seconds = float(words[1])
                if not math.isfinite(seconds) or not 0 <= seconds <= MAX_SECONDS:
                    raise ValueError
                steps.append(Step("wait", seconds=seconds))
                continue
            if kind == "hold" and len(words) == 3:
                seconds = float(words[2])
                if not math.isfinite(seconds) or not 0.03 <= seconds <= MAX_SECONDS:
                    raise ValueError
                step = Step("hold", words[1], seconds)
            elif kind in ("focus", "ensure", "leave") and len(words) == 3:
                focus = int(words[2])
                if not 1 <= focus <= 11:
                    raise ValueError
                step = Step("focus" if kind == "ensure" else kind, words[1], focus=focus)
            elif kind not in ("wait", "hold", "focus", "ensure", "leave") and len(words) <= 2:
                repeat = 1
                if len(words) == 2:
                    if not re.fullmatch(r"[x*]\d+", words[1]):
                        raise ValueError
                    repeat = int(words[1][1:])
                    if not 1 <= repeat <= MAX_REPEAT:
                        raise ValueError
                step = Step("press", words[0])
            else:
                raise ValueError
            if not _ACTION.fullmatch(step.action) or re.search(r"eject|jettison|destruct", step.action, re.I):
                raise ValueError
            steps.extend([step] * (repeat if step.kind == "press" else 1))
        except (ValueError, OverflowError):
            raise ValueError(f"Invalid sequence step: {line!r}") from None
        if len(steps) > MAX_STEPS:
            raise ValueError("A sequence can have at most 60 steps after repeats.")
    if len(steps) > MAX_STEPS:
        raise ValueError("A sequence can have at most 60 steps after repeats.")
    if not any(step.action for step in steps):
        raise ValueError("A sequence needs at least one bound action.")
    return tuple(steps)


def actions_in(steps):
    return tuple(dict.fromkeys(step.action for step in steps if step.action))
