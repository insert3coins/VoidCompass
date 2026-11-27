"""The settings a binds file holds besides its controls: yes/no switches,
sensitivities and dead zones, and the throttle's range.

Only "1" is on (the game writes 0 or 1). A number is held to what the game
allows (a sensitivity above 0, a dead zone 0 to 1); the slider stops are where
the game's own sliders stop, and files past them are left as they are."""
from __future__ import annotations

TOGGLES = frozenset({
    "DeployHardpointsOnFire", "DriveAssistDefault", "EnableAimAssistOnFoot", "EnableCameraLockOn",
    "EnableMenuGroups", "EnableMenuGroupsOnFoot", "EnableMenuGroupsSRV", "EnableRumbleTrigger",
    "FSSMouseXDecay", "FSSMouseYDecay", "FocusOnTextEntryField", "FreeCamMouseXDecay", "FreeCamMouseYDecay",
    "HeadlookDefault", "HeadlookResetOnToggle", "HeadlookSmoothing", "HumanoidItemWheel_AcceptMouseInput",
    "MotionHeadlook", "MouseBuggyRollingXDecay", "MouseBuggySteeringXDecay", "MouseBuggyYDecay", "MouseDecay",
    "MouseGUI", "MouseHeadingUpInsteadOfRoll", "MouseHeadlook", "MouseHeadlookInvert", "MouseRelativeMode",
    "MouseTurretXDecay", "MouseTurretYDecay", "MouseWheelThrottle", "MouseWheelThrottleInverted",
    "MouseXDecay", "MouseXSign", "MouseYDecay", "MouseYSign", "MultiCrewThirdPersonMouseXDecay",
    "MultiCrewThirdPersonMouseYDecay", "PlacementCamMouseXDecay", "PlacementCamMouseYDecay",
    "SAAThirdPersonMouseXDecay", "SAAThirdPersonMouseYDecay", "yawRotateHeadlook"})

_SENSITIVITY = (0.1, 10.0, 0.01)
_FREE_CAM = (0.1, 20.0, 0.1)
_DEADZONE = (0.0, 0.2, 0.001)
_LINEARITY = (1.0, 3.0, 0.01)
_AXIS = (0.25, 4.0, 0.01)
_THIRD_PERSON = (0.1, 200.0, 0.1)
# Where the game's sliders stop: (min, max, step). None: no stop measured, a typed number.
NUMBERS = {
    "BuggyTurretMouseDeadzone": _DEADZONE, "BuggyTurretMouseLinearity": _LINEARITY,
    "BuggyTurretMouseSensitivity": _SENSITIVITY, "FSSMouseDeadzone": _DEADZONE, "FSSMouseLinearity": _LINEARITY,
    "FSSMouseSensitivity": (0.1, 40.0, 0.1), "FSSTuningSensitivity": _SENSITIVITY,
    "FreeCamMouseSensitivity": _FREE_CAM, "HeadlookMotionSensitivity": None, "HeadlookSensitivity": _AXIS,
    "HumanoidPitchSensitivity": _AXIS, "HumanoidRotateSensitivity": _AXIS, "MouseDeadzone": _DEADZONE,
    "MouseDecayRate": (1.0, 10.0, 0.01), "MouseHeadlookSensitivity": _SENSITIVITY,
    "MouseHumanoidSensitivity": _SENSITIVITY, "MouseLinearity": _LINEARITY, "MouseSensitivity": _SENSITIVITY,
    "MultiCrewThirdPersonMouseSensitivity": _THIRD_PERSON, "PlacementCamMouseSensitivity": _FREE_CAM,
    "SAAThirdPersonMouseSensitivity": _THIRD_PERSON, "YawToRollSensitivity": (0.1, 0.9, 0.01)}

# The Full Range / Forward Only choice beside some throttle axes: (setting, forward-only value, also read as forward).
THROTTLE = {"ThrottleAxis": ("ThrottleRange", "Bindings_ThrottleForewardOnly", ()),
            "DriveSpeedAxis": ("BuggyThrottleRange", "Bindings_BuggyThrottleForewardOnly", ()),
            "MoveFreeCamY": ("ThrottleRangeFreeCam", "Bindings_ThrottleForewardOnlyFreeCam", ("Bindings_ThrottleForewardOnly",))}
FULL_RANGE = {"", "Bindings_ThrottleFullRange", "Bindings_ThrottleFullRangeFreeCam"}


def judge(setting, typed):
    """(value to write, "") or (None, why not). Either decimal mark is taken."""
    try:
        number = float(str(typed).strip().replace(",", "."))
    except ValueError:
        return None, "That isn't a number."
    if number != number or number in (float("inf"), float("-inf")):
        return None, "That isn't a number."
    if setting.endswith("Deadzone"):
        if not 0.0 <= number <= 1.0:
            return None, "A dead zone is between 0 and 1."
    elif number <= 0:
        return None, "It must be above 0."
    return f"{number:.8f}", ""


def shown(value):
    """"1.00000000" -> "1.0"; text that isn't a number as it is."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value or "")
    text = f"{number:.6f}".rstrip("0")
    return text + "0" if text.endswith(".") else text


def throttle_reading(axis, value):
    """"forward", "full" or "other" (a hand edit, kept unless changed)."""
    setting, forward, also = THROTTLE[axis]
    if value == forward or value in also:
        return "forward"
    return "full" if value in FULL_RANGE else "other"
