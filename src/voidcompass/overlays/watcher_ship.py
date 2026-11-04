"""Working the ship by asking (5.7.3): "open the galaxy map", "gear down",
"four pips to systems", "next target". Which of Elite's actions a request
means in the ship, the SRV or on foot, whether Status.json says it's done
already, and the presses that set the power distributor. It only decides:
the deck presses the keys (elite_keys), with the key your bindings give.

Never here, on purpose: anything that throws cargo away or destroys the
ship. A request has to be the whole of what you said ("lights on"), so
talk that merely mentions the galaxy map does nothing.
"""
from __future__ import annotations

from collections import deque
import re

# Status.json flags it reads.
GEAR, FA_OFF, HARDPOINTS, LIGHTS, SCOOP, SILENT = 0x4, 0x20, 0x40, 0x100, 0x200, 0x400
DRIVE_ASSIST, IN_FIGHTER, IN_SRV, ANALYSIS, NIGHT_VISION = 0x8000, 0x02000000, 0x04000000, 0x08000000, 0x10000000
ON_FOOT = 0x1  # Flags2
# GuiFocus.
SCREEN_FOCUS = {"right_panel": 1, "left_panel": 2, "comms_panel": 3, "role_panel": 4, "galaxy_map": 6,
                "system_map": 7, "fss": 9, "codex": 11}
WHERE = {"ship": "in the ship", "srv": "in the SRV", "foot": "on foot", "fighter": "in a fighter"}

_PLEASE = r"(?:(?:please|could you|can you|would you|will you|go on|ok|okay|hey|watcher|now|and)[\s,]+)*"
_FILLER = r"(?:the|my|our|your|a|an|some|ship'?s?)"
_AFTER = r"(?:\s+(?:please|now|for me|thanks|thank you|quick|quickly))*"
_ON = (r"open|show(?: me)?|let me see|display|bring up|pull up|call up|access|load|view|check|look at|take me to|get|"
       r"deploy|extend|lower|drop|put down|turn on|switch on|enable|activate|engage|start|enter|go to")
_OFF = (r"close|hide|exit|leave|quit|dismiss|shut|back out of|stop showing|get rid of|retract|raise|stow|pull in|"
        r"put away|turn off|switch off|disable|deactivate|disengage|cancel")
_PRESS = (r"use|fire|launch|pop|deploy|drop|hit|press|engage|activate|do|give me|select|target|cycle|set|go|order|initiate|"
          r"request|ask for|draw|equip|switch to|throw|toss|apply|take|charge")
_TOGGLE = r"toggle|flip|switch|turn"


class Command:
    """One thing it can do. ``kind`` is "screen" (a map or panel, open or
    closed by GuiFocus), "switch" (on or off by a Status.json flag) or
    "press". ``actions`` gives Elite's action in each place it works."""

    def __init__(self, ident, say, kind, actions, nouns, group, flag=0, inverted=False, words=("on", "off"),
                 tails=("", ""), default="toggle", done=None, close=None, example="", macro=(),
                 menu=False, docked=False):
        self.id = ident
        self.say = say
        self.kind = kind
        self.actions = actions
        self.close = close or {}
        self.nouns = nouns
        self.group = group
        self.flag = flag
        self.inverted = inverted
        self.words = words
        self.tails = tails
        self.default = default if kind == "switch" else ("open" if kind == "screen" else "press")
        self.done = done or ()
        self.example = example or nouns.split("|")[0]
        self.macro = tuple(macro)
        self.menu = menu
        self.docked = docked
        on_tail = "|".join(filter(None, ("on", "open", "up" if kind == "screen" else "", tails[0])))
        off_tail = "|".join(filter(None, ("off", "closed?", "away", tails[1])))
        self.pattern = re.compile(
            rf"^{_PLEASE}(?:(?P<verb>{_ON}|{_OFF}|{_TOGGLE}|{_PRESS})\s+)?(?:{_FILLER}\s+)*(?:{nouns})"
            rf"(?:\s+(?P<tail>{on_tail}|{off_tail}))?{_AFTER}$", re.I)
        self._on_tail = re.compile(rf"^(?:{on_tail})$", re.I)
        self._off_tail = re.compile(rf"^(?:{off_tail})$", re.I)

    def action(self, place, op="on"):
        """Elite's action for this in ``place`` (a fighter flies like the
        ship), or None when it isn't one for there."""
        table = self.close if op == "off" and self.close else self.actions
        return table.get(place) or (table.get("ship") if place == "fighter" else None)

    def op_for(self, verb, tail):
        """"on", "off", "toggle" or "press" from the verb or the word after."""
        verb = (verb or "").casefold()
        if self.kind == "press":
            # "Heat sink off" isn't a heat sink.
            return None if tail or re.fullmatch(_OFF, verb) else "press"
        if tail:
            return "on" if self._on_tail.match(tail) else "off"
        if not verb:
            return "on" if self.default in ("on", "open") else "toggle"
        if re.fullmatch(_TOGGLE, verb):
            return "toggle"
        if re.fullmatch(_OFF, verb):
            return "off"
        return "on"


def _c(*args, **kwargs):
    return Command(*args, **kwargs)


SHIP = "ship"
COMMANDS = (
    # Maps and panels.
    _c("galaxy_map", "the galaxy map", "screen", {SHIP: "GalaxyMapOpen", "srv": "GalaxyMapOpen_Buggy",
                                                  "foot": "GalaxyMapOpen_Humanoid"},
       r"galaxy map|galmap|gal map|galactic map|star map|stellar map|map of (?:the )?galaxy",
       "Maps and panels", example="open the galaxy map"),
    _c("system_map", "the system map", "screen", {SHIP: "SystemMapOpen", "srv": "SystemMapOpen_Buggy",
                                                  "foot": "SystemMapOpen_Humanoid"},
       r"system map|sys map|orrery|local map|solar system map", "Maps and panels", example="open the system map"),
    _c("fss", "the full spectrum scanner", "screen", {SHIP: "ExplorationFSSEnter"},
       r"fss|full spectrum scanner|spectrum scanner|discovery scanner mode", "Maps and panels",
       close={SHIP: "ExplorationFSSQuit"}, example="open the FSS"),
    _c("codex", "the codex", "screen", {SHIP: "OpenCodexGoToDiscovery", "srv": "OpenCodexGoToDiscovery_Buggy"},
       r"codex", "Maps and panels", example="open the codex"),
    _c("left_panel", "the left panel", "screen", {SHIP: "FocusLeftPanel", "srv": "FocusLeftPanel_Buggy"},
       r"left(?: hand)? panel|navigation(?: panel)?|nav panel|target panel|contacts(?: panel)?|external panel",
       "Maps and panels", close={SHIP: "UI_Back", "srv": "UI_Back"}, example="open the left panel"),
    _c("right_panel", "the right panel", "screen", {SHIP: "FocusRightPanel", "srv": "FocusRightPanel_Buggy"},
       r"right(?: hand)? panel|systems panel|internal panel|(?:ship )?status(?: panel)?|functions panel|modules(?: panel)?",
       "Maps and panels", close={SHIP: "UI_Back", "srv": "UI_Back"}, example="open the right panel"),
    _c("comms_panel", "the comms panel", "screen", {SHIP: "FocusCommsPanel", "srv": "FocusCommsPanel_Buggy",
                                                    "foot": "FocusCommsPanel_Humanoid"},
       r"comms panel|comms|communications(?: panel)?|chat panel|messages(?: panel)?", "Maps and panels",
       close={SHIP: "UI_Back", "srv": "UI_Back", "foot": "UI_Back"}, example="open comms"),
    _c("role_panel", "the role panel", "screen", {SHIP: "FocusRadarPanel", "srv": "FocusRadarPanel_Buggy"},
       r"role panel|bottom panel|radar panel|crew panel|helm panel|ship role panel", "Maps and panels",
       close={SHIP: "UI_Back", "srv": "UI_Back"}, example="open the role panel"),
    _c("camera", "the camera suite", "press", {SHIP: "PhotoCameraToggle", "srv": "PhotoCameraToggle_Buggy",
                                               "foot": "PhotoCameraToggle_Humanoid"},
       r"camera suite|camera|photo mode", "Maps and panels", done=("The camera.",), example="camera suite"),
    # Menu keys use the General preset and only run with an in-game screen open.
    *(_c(ident, label, "press", {SHIP: action, "srv": action, "foot": action}, nouns, "Menus",
         menu=True, done=(said,), example=example)
      for ident, action, label, nouns, said, example in (
          ("ui_next_tab", "CycleNextPanel", "the next tab", r"next (?:tab|panel)|tab right", "Next tab.", "next tab"),
          ("ui_previous_tab", "CyclePreviousPanel", "the previous tab", r"previous (?:tab|panel)|last tab|tab left", "Previous tab.", "previous tab"),
          ("ui_next_page", "CycleNextPage", "the next page", r"next page", "Next page.", "next page"),
          ("ui_previous_page", "CyclePreviousPage", "the previous page", r"previous page", "Previous page.", "previous page"),
          ("ui_up", "UI_Up", "menu up", r"(?:menu|cursor) up|move up", "Up.", "menu up"),
          ("ui_down", "UI_Down", "menu down", r"(?:menu|cursor) down|move down", "Down.", "menu down"),
          ("ui_left", "UI_Left", "menu left", r"(?:menu|cursor) left|move left", "Left.", "menu left"),
          ("ui_right", "UI_Right", "menu right", r"(?:menu|cursor) right|move right", "Right.", "menu right"),
          ("ui_select", "UI_Select", "the menu selection", r"menu select|select|confirm selection|confirm|accept", "Selected.", "select"),
          ("ui_back", "UI_Back", "back", r"back|go back|menu back|close (?:the )?(?:panel|menu)|return to (?:the )?cockpit", "Back.", "go back"))),
    # The ship's switches.
    _c("gear", "the landing gear", "switch", {SHIP: "LandingGearToggle"},
       r"landing gear|gear|wheels|undercarriage|landing legs", "The ship", flag=GEAR, words=("down", "up"),
       tails=("down|out", "up|in"), example="gear down"),
    _c("hardpoints", "the hardpoints", "switch", {SHIP: "DeployHardpointToggle"},
       r"hardpoints|hard points|weapons|guns", "The ship", flag=HARDPOINTS, words=("out", "away"),
       tails=("out|ready|hot", "in|cold|safe"), example="deploy hardpoints"),
    _c("scoop", "the cargo scoop", "switch", {SHIP: "ToggleCargoScoop", "srv": "ToggleCargoScoop_Buggy"},
       r"cargo scoop|scoop|cargo hatch|hatch", "The ship", flag=SCOOP, words=("open", "closed"),
       tails=("out|down", "in|up"), example="open the cargo scoop"),
    _c("lights", "the lights", "switch", {SHIP: "ShipSpotLightToggle", "srv": "HeadlightsBuggyButton",
                                          "foot": "HumanoidToggleFlashlightButton"},
       r"lights|spotlights?|headlights|flashlight|torch|light", "The ship", flag=LIGHTS, example="lights on"),
    _c("night_vision", "night vision", "switch", {SHIP: "NightVisionToggle", "foot": "HumanoidToggleNightVisionButton"},
       r"night vision|nightvision|night sight", "The ship", flag=NIGHT_VISION, example="night vision on"),
    _c("silent_running", "silent running", "switch", {SHIP: "ToggleButtonUpInput"},
       r"silent running|silent mode|run silent|stealth mode", "The ship", flag=SILENT, default="on",
       example="silent running on"),
    _c("flight_assist", "flight assist", "switch", {SHIP: "ToggleFlightAssist"},
       r"flight assist|fa", "The ship", flag=FA_OFF, inverted=True, example="flight assist off"),
    _c("analysis_mode", "analysis mode", "switch", {SHIP: "PlayerHUDModeToggle", "srv": "PlayerHUDModeToggle_Buggy"},
       r"analysis mode|analysis hud|exploration mode|scanner mode", "The ship", flag=ANALYSIS, default="on",
       example="analysis mode"),
    _c("combat_mode", "combat mode", "switch", {SHIP: "PlayerHUDModeToggle", "srv": "PlayerHUDModeToggle_Buggy"},
       r"combat mode|combat hud", "The ship", flag=ANALYSIS, inverted=True, default="on", example="combat mode"),
    _c("orbit_lines", "orbit lines", "press", {SHIP: "OrbitLinesToggle"}, r"orbit lines|orbits",
       "The ship", done=("Orbit lines.",), example="toggle orbit lines"),
    _c("head_look", "head look", "press", {SHIP: "HeadLookToggle", "srv": "HeadLookToggle_Buggy"},
       r"head look|headlook|free look", "The ship", done=("Head look.",), example="head look"),
    # Flight.
    _c("supercruise", "supercruise", "press", {SHIP: "Supercruise"},
       r"supercruise|super cruise|cruise", "Flight", done=("Supercruise. Charging.", "Charging for supercruise."),
       example="engage supercruise"),
    _c("jump", "the jump", "press", {SHIP: "Hyperspace"},
       r"jump|hyperspace|hyperspace jump|hyper jump|fsd jump|frame shift jump|jump to the next system|"
       r"jump to (?:the )?next (?:star|system)|next jump", "Flight",
       done=("Jumping. Charging the drive.", "The drive's charging.", "Here we go."), example="jump"),
    _c("boost", "the boost", "press", {SHIP: "UseBoostJuice"}, r"boost|engine boost|boosters?", "Flight",
       done=("Boost.",), example="boost"),
    _c("throttle_0", "zero throttle", "press", {SHIP: "SetSpeedZero"},
       r"zero throttle|throttle (?:to )?zero|all stop|full stop|cut (?:the )?throttle|stop the ship|zero speed",
       "Flight", done=("All stop.", "Throttle to zero."), example="all stop"),
    _c("throttle_25", "quarter throttle", "press", {SHIP: "SetSpeed25"},
       r"quarter throttle|throttle (?:to )?(?:a )?quarter|throttle (?:to )?25(?: percent)?|25 percent throttle",
       "Flight", done=("A quarter.",), example="quarter throttle"),
    _c("throttle_50", "half throttle", "press", {SHIP: "SetSpeed50"},
       r"half throttle|throttle (?:to )?half|half speed|throttle (?:to )?50(?: percent)?|50 percent throttle",
       "Flight", done=("Half.", "Half throttle."), example="half throttle"),
    _c("throttle_75", "three quarter throttle", "press", {SHIP: "SetSpeed75"},
       r"three quarters? throttle|throttle (?:to )?three quarters?|throttle (?:to )?75(?: percent)?|75 percent throttle",
       "Flight", done=("Three quarters.",), example="three quarter throttle"),
    _c("throttle_100", "full throttle", "press", {SHIP: "SetSpeed100"},
       r"full throttle|full speed|max(?:imum)? throttle|throttle (?:to )?(?:full|max|100(?: percent)?)|"
       r"100 percent throttle", "Flight", done=("Full throttle.", "All ahead."), example="full throttle"),
    # Targets.
    _c("next_route_system", "the next system on the route", "press", {SHIP: "TargetNextRouteSystem"},
       r"next system|next route system|next system on (?:the|my|our) route|next waypoint|next (?:jump )?destination",
       "Targets", done=("The next system's targeted.", "Targeted: the next system."), example="target the next system"),
    _c("next_target", "the next target", "press", {SHIP: "CycleNextTarget"}, r"next target", "Targets",
       done=("Next target.",), example="next target"),
    _c("previous_target", "the previous target", "press", {SHIP: "CyclePreviousTarget"},
       r"previous target|last target", "Targets", done=("The one before.",), example="previous target"),
    _c("target_ahead", "the target ahead", "press", {SHIP: "SelectTarget", "srv": "SelectTarget_Buggy"},
       r"target ahead|target in front|target under (?:the )?(?:reticle|crosshairs)|lock target",
       "Targets", done=("Target ahead.",), example="target ahead"),
    _c("highest_threat", "the highest threat", "press", {SHIP: "SelectHighestThreat"},
       r"highest threat|biggest threat|most dangerous", "Targets", done=("The biggest threat, targeted.",),
       example="target the highest threat"),
    _c("next_hostile", "the next hostile", "press", {SHIP: "CycleNextHostileTarget"},
       r"next hostile|next enemy|hostile", "Targets", done=("Next hostile.",), example="next hostile"),
    _c("previous_hostile", "the previous hostile", "press", {SHIP: "CyclePreviousHostileTarget"},
       r"previous hostile|previous enemy|last hostile", "Targets", done=("Previous hostile.",), example="previous hostile"),
    _c("targets_target", "the target's target", "press", {SHIP: "SelectTargetsTarget"},
       r"target'?s target|their target", "Targets", done=("Their target.",), example="target's target"),
    _c("next_subsystem", "the next subsystem", "press", {SHIP: "CycleNextSubsystem"},
       r"next subsystem|subsystem", "Targets", done=("Next subsystem.",), example="next subsystem"),
    _c("previous_subsystem", "the previous subsystem", "press", {SHIP: "CyclePreviousSubsystem"},
       r"previous subsystem|last subsystem", "Targets", done=("The subsystem before.",), example="previous subsystem"),
    _c("wingman_1", "wingman one", "press", {SHIP: "TargetWingman0"}, r"wingman (?:one|1)|first wingman", "Targets",
       done=("Wingman one.",), example="target wingman one"),
    _c("wingman_2", "wingman two", "press", {SHIP: "TargetWingman1"}, r"wingman (?:two|2)|second wingman", "Targets",
       done=("Wingman two.",), example="target wingman two"),
    _c("wingman_3", "wingman three", "press", {SHIP: "TargetWingman2"}, r"wingman (?:three|3)|third wingman",
       "Targets", done=("Wingman three.",), example="target wingman three"),
    _c("wing_nav_lock", "wing nav lock", "press", {SHIP: "WingNavLock"}, r"wing nav lock|nav lock|wing lock",
       "Targets", done=("Nav lock.",), example="wing nav lock"),
    *(_c(f"assist_wingman_{number}", f"wingman {word}'s target", "press", {SHIP: f"TargetWingman{number - 1}"},
         rf"assist (?:my )?wingman (?:{word}|{number})|wingman (?:{word}|{number})(?:'s|s)? target",
         "Targets", macro=(f"TargetWingman{number - 1}", "wait 0.4", "SelectTargetsTarget"),
         done=(f"Wingman {word}'s target.",), example=f"assist wingman {word}")
      for number, word in enumerate(("one", "two", "three"), 1)),
    # Combat.
    _c("heat_sink", "a heat sink", "press", {SHIP: "DeployHeatSink"}, r"heat ?sink|heatsink", "Combat",
       done=("Heat sink away.", "Heat sink."), example="heat sink"),
    _c("shield_cell", "a shield cell", "press", {SHIP: "UseShieldCell"}, r"shield cell|scb|shield bank|cell",
       "Combat", done=("Shield cell.", "A shield cell, firing."), example="shield cell"),
    _c("chaff", "chaff", "press", {SHIP: "FireChaffLauncher"}, r"chaff", "Combat", done=("Chaff away.",),
       example="chaff"),
    _c("ecm", "the ECM", "press", {SHIP: "ChargeECM"}, r"ecm|electronic countermeasures?", "Combat",
       done=("ECM.",), example="ECM"),
    _c("next_fire_group", "the next fire group", "press", {SHIP: "CycleFireGroupNext",
                                                         "srv": "BuggyCycleFireGroupNext"},
       r"next fire ?group|fire ?group", "Combat", done=("Next fire group.",), example="next fire group"),
    _c("previous_fire_group", "the previous fire group", "press", {SHIP: "CycleFireGroupPrevious",
                                                                 "srv": "BuggyCycleFireGroupPrevious"},
       r"previous fire ?group|last fire ?group", "Combat", done=("The fire group before.",),
       example="previous fire group"),
    _c("radar_up", "the radar range", "press", {SHIP: "RadarIncreaseRange"},
       r"(?:increase|raise) (?:the )?radar(?: range)?|radar (?:range )?up|radar out", "Combat",
       done=("Radar out.",), example="radar range up"),
    _c("radar_down", "the radar range", "press", {SHIP: "RadarDecreaseRange"},
       r"(?:decrease|lower|reduce) (?:the )?radar(?: range)?|radar (?:range )?down|radar in", "Combat",
       done=("Radar in.",), example="radar range down"),
    # Fighter orders.
    _c("fighter_orders", "the fighter orders", "press", {SHIP: "OpenOrders"},
       r"(?:fighter|crew) orders|orders menu", "Fighter", done=("Fighter orders.",), example="open fighter orders"),
    _c("fighter_attack", "the attack order", "press", {SHIP: "OrderFocusTarget"},
       r"(?:fighter )?attack (?:my )?target|fighter attack|focus (?:my )?target", "Fighter",
       done=("The fighter's on your target.",), example="fighter attack my target"),
    _c("fighter_defend", "defensive", "press", {SHIP: "OrderDefensiveBehaviour"},
       r"(?:fighter )?defen[cs]ive|fighter defend|defend (?:me|the ship)", "Fighter", done=("Defending.",),
       example="fighter defend"),
    _c("fighter_aggressive", "aggressive", "press", {SHIP: "OrderAggressiveBehaviour"},
       r"(?:fighter )?aggressive|fighter engage at will|engage at will", "Fighter", done=("Engaging at will.",),
       example="fighter aggressive"),
    _c("fighter_hold_fire", "hold fire", "press", {SHIP: "OrderHoldFire"}, r"(?:fighter )?hold fire|cease fire",
       "Fighter", done=("Holding fire.",), example="hold fire"),
    _c("fighter_hold_position", "hold position", "press", {SHIP: "OrderHoldPosition"},
       r"(?:fighter )?hold position|stay there", "Fighter", done=("Holding position.",), example="hold position"),
    _c("fighter_follow", "follow me", "press", {SHIP: "OrderFollow"}, r"(?:fighter )?follow(?: me)?|form up",
       "Fighter", done=("Following.",), example="fighter follow me"),
    _c("fighter_recall", "the fighter's recall", "press", {SHIP: "OrderRequestDock"},
       r"recall (?:the )?fighter|fighter (?:return|dock|come home)|dock (?:the )?fighter", "Fighter",
       done=("Calling the fighter home.",), example="recall the fighter"),
    # The SRV.
    _c("recall_ship", "the ship", "press", {"srv": "RecallDismissShip"},
       r"recall (?:the |my )?ship|dismiss (?:the |my )?ship|send (?:the |my )?ship away|call (?:the |my )?ship",
       "The SRV", done=("The ship's told.",), example="recall the ship"),
    _c("drive_assist", "drive assist", "switch", {"srv": "ToggleDriveAssist"}, r"drive assist", "The SRV",
       flag=DRIVE_ASSIST, example="drive assist on"),
    _c("turret", "the turret", "press", {"srv": "ToggleBuggyTurretButton"}, r"turret(?: mode)?|srv turret",
       "The SRV", done=("The turret.",), example="turret mode"),
    # On foot.
    _c("holster", "your weapon", "press", {"foot": "HumanoidHideWeaponButton"},
       r"holster(?: (?:my |your |the )?weapons?)?|put (?:my |the )?(?:weapon|gun) away", "On foot",
       done=("Holstered.",), example="holster"),
    _c("reload", "a reload", "press", {"foot": "HumanoidReloadButton"}, r"reload", "On foot", done=("Reloading.",),
       example="reload"),
    _c("primary_weapon", "the primary weapon", "press", {"foot": "HumanoidSelectPrimaryWeaponButton"},
       r"primary(?: weapon)?|main weapon|rifle", "On foot", done=("Primary.",), example="primary weapon"),
    _c("secondary_weapon", "the secondary weapon", "press", {"foot": "HumanoidSelectSecondaryWeaponButton"},
       r"secondary(?: weapon)?|sidearm|pistol", "On foot", done=("Secondary.",), example="secondary weapon"),
    *(_c(ident, label, "press", {"foot": action}, nouns, "On foot", example=example)
      for ident, action, label, nouns, example in (
          ("suit_shields", "HumanoidToggleShieldsButton", "the suit shields", r"suit shields|personal shields", "toggle suit shields"),
          ("medkit", "HumanoidHealthPack", "a medical pack", r"(?:health|medical|med) (?:pack|kit)|medkit|heal me", "use a medical pack"),
          ("battery", "HumanoidBattery", "an energy cell", r"battery|battery pack|energy cell|power cell", "use an energy cell"),
          ("next_weapon", "HumanoidSelectNextWeaponButton", "the next weapon", r"next (?:weapon|gun)", "next weapon"),
          ("previous_weapon", "HumanoidSelectPreviousWeaponButton", "the previous weapon", r"previous weapon|last weapon", "previous weapon"),
          ("utility_weapon", "HumanoidSelectUtilityWeaponButton", "the utility slot", r"utility (?:slot|weapon)|gadget", "select utility slot"),
          ("swap_weapon", "HumanoidSwitchWeapon", "the other weapon", r"(?:swap|switch) weapons?|other (?:gun|weapon)", "swap weapons"),
          ("energy_link", "HumanoidSwitchToRechargeTool", "the energy link", r"energy link|recharge tool|recharger", "equip energy link"),
          ("composition_scanner", "HumanoidSwitchToCompAnalyser", "the composition scanner", r"composition scanner|comp analy[sz]er|compound scanner", "equip composition scanner"),
          ("suit_tool", "HumanoidSwitchToSuitTool", "the suit tool", r"suit tool|profile analy[sz]er|genetic (?:sampler|scanner)", "equip suit tool"),
          ("tool_mode", "HumanoidToggleToolModeButton", "the tool mode", r"tool mode", "toggle tool mode"),
          ("item_wheel", "HumanoidItemWheelButton", "the item wheel", r"item wheel|inventory wheel", "open item wheel"),
          ("emote_wheel", "HumanoidEmoteWheelButton", "the emote wheel", r"emote wheel|emotes", "open emote wheel"),
          ("mission_help", "HumanoidToggleMissionHelpPanelButton", "mission help", r"(?:mission|objective) help(?: panel)?", "show mission help"),
          ("access_panel", "HumanoidOpenAccessPanelButton", "the access panel", r"access panel", "open access panel"),
          ("next_grenade", "HumanoidSelectNextGrenadeTypeButton", "the next grenade type", r"next grenade(?: type)?", "next grenade type"),
          ("previous_grenade", "HumanoidSelectPreviousGrenadeTypeButton", "the previous grenade type", r"previous grenade(?: type)?", "previous grenade type"),
          ("frag_grenade", "HumanoidSelectFragGrenade", "frag grenades", r"(?:frag|fragmentation|explosive) grenades?", "select frag grenade"),
          ("emp_grenade", "HumanoidSelectEMPGrenade", "EMP grenades", r"(?:emp|e m p|electromagnetic) grenades?", "select EMP grenade"),
          ("shield_grenade", "HumanoidSelectShieldGrenade", "shield grenades", r"shield(?:ing)? grenades?", "select shield grenade"),
          ("throw_grenade", "HumanoidThrowGrenadeButton", "a grenade", r"grenade|frag out", "throw a grenade"),
          ("melee", "HumanoidMeleeButton", "a melee attack", r"melee(?: attack)?", "melee"),
          ("foot_interact", "HumanoidPrimaryInteractButton", "interact", r"interact|primary interact|open (?:the )?door", "interact"),
          ("foot_secondary_interact", "HumanoidSecondaryInteractButton", "the secondary interact", r"secondary interact", "secondary interact"),
          ("foot_crouch", "HumanoidCrouchButton", "crouch", r"crouch|duck|take cover", "crouch"),
          ("foot_sprint", "HumanoidSprintButton", "sprint", r"sprint|run", "sprint"),
          ("foot_walk", "HumanoidWalkButton", "walk", r"walk|walking pace", "walk"),
          ("foot_jump", "HumanoidJumpButton", "a jump", r"hop|jump up|on foot jump|suit jump", "hop"),
          ("foot_aim", "HumanoidZoomButton", "aim", r"aim|aim down (?:the )?sights|zoom", "aim"),
          ("foot_ping", "HumanoidPing", "a ping", r"ping|mark (?:that|this|target)", "ping"))),
    # Sequences: Starling's action names and pauses, using this commander's keys.
    _c("request_docking", "the docking request", "press", {SHIP: "FocusLeftPanel"},
       r"docking(?: (?:permission|clearance|request))?|landing (?:permission|clearance)|permission to (?:dock|land)|"
       r"request (?:permission to )?(?:dock|land)|docking request", "Sequences",
       macro=("focus FocusLeftPanel 2", "wait 0.5", "hold CycleNextPanel 0.15", "wait 0.5",
              "hold CycleNextPanel 0.15", "wait 1.15",
              "ensure FocusLeftPanel 2", "hold UI_Right 0.15", "wait 1.2", "ensure FocusLeftPanel 2",
              "hold UI_Select 0.15", "wait 1.2", "hold UI_Left 0.15", "wait 1.2",
              "ensure FocusLeftPanel 2", "hold CyclePreviousPanel 0.15", "wait 0.7",
              "hold CyclePreviousPanel 0.15", "wait 0.85", "leave UI_Back 2"),
       done=("Requesting docking.",), example="request docking"),
    _c("deploy_nomad", "the Nomad", "press", {SHIP: "FocusRadarPanel"},
       r"nomad(?: shuttle)?|exploration shuttle", "Sequences",
       macro=("focus FocusRadarPanel 4", "wait 0.8", "UI_Down", "wait 0.2", "UI_Right", "wait 0.2", "UI_Select"),
       done=("Deploying the Nomad.",), example="deploy the Nomad"),
    _c("auto_launch", "the launch", "press", {SHIP: "UI_Select"},
       r"launch|auto launch|launch (?:the )?ship|undock|take off|launch sequence", "Sequences", docked=True,
       macro=("UI_Down", "wait 0.6", "UI_Select"), done=("Launching.",), example="launch the ship"),
)
BY_ID = {command.id: command for command in COMMANDS}
GROUPS = tuple(dict.fromkeys(command.group for command in COMMANDS)) + ("Power",)


def sequence_key(command, where="ship", op="on"):
    where = "ship" if where == "fighter" else where
    return command.id + (":off" if command.kind == "screen" and op == "off" else "") + (f":{where}" if where != "ship" else "")


def sequence_options(command):
    for where in command.actions:
        for op in (("on", "off") if command.kind == "screen" else ("on",)):
            action = command.action(where, op)
            if action:
                yield sequence_key(command, where, op), where, op, command.macro or (action,)


def _clean(text):
    words = " ".join(str(text or "").replace("-", " ").replace("’", "'").split()).strip(" .!,").casefold()
    # A few common speech spellings; no fuzzy match that could fire another action.
    words = re.sub(r"\b(?:galaxey|galaxi)\b", "galaxy", words)
    words = re.sub(r"\bgalaxy (?:mat|mab)\b", "galaxy map", words)
    return words


_QUESTION = re.compile(r"^(?:what|why|how|where|when|who|which|whose|is|are|was|were|do|does|did|should|have|has)\b")


def literal_words(text):
    words = " ".join(re.sub(r"[,;:!?]+", " ", _clean(text)).split())
    words = re.sub(rf"^{_PLEASE}", "", words).strip()
    return re.sub(rf"{_AFTER}$", "", words).strip()


def request(text, commands=None):
    """{"command": id, "op": "on" | "off" | "toggle" | "press"} for a ship
    command that's the whole of what was said, or None."""
    words = _clean(text).rstrip("?").strip()
    # "Is the gear down?" asks; "can you lower the gear?" doesn't.
    if not words or len(words) > 70:
        return None
    for command in COMMANDS if commands is None else commands:
        if hasattr(command, "phrases") and literal_words(words) in {literal_words(phrase) for phrase in command.phrases}:
            verb = re.match(rf"^({_OFF}|{_TOGGLE}|{_ON}|{_PRESS})(?:\s|$)", literal_words(words))
            normal = literal_words(words)
            original = command.pattern.match(normal)
            tail = normal.rsplit(" ", 1)[-1]
            tail = tail if command._on_tail.fullmatch(tail) or command._off_tail.fullmatch(tail) else ""
            op = ("press" if command.kind == "press" else
                  command.op_for(original.group("verb"), original.group("tail")) if original else
                  command.op_for(verb.group(1) if verb else "", tail))
            if op is not None:
                return {"command": command.id, "op": op}
        if _QUESTION.match(re.sub(rf"^{_PLEASE}", "", words)):
            continue
        if not getattr(command, "keep_defaults", True):
            continue
        found = command.pattern.match(words)
        if found:
            op = command.op_for(found.group("verb"), found.group("tail"))
            if op is not None:
                return {"command": command.id, "op": op}
    return None


def place(flags, flags2):
    """Where you are, for which action a command means."""
    if int(flags2 or 0) & ON_FOOT:
        return "foot"
    if int(flags or 0) & IN_SRV:
        return "srv"
    if int(flags or 0) & IN_FIGHTER:
        return "fighter"
    return "ship"


def already(command, op, flags=0, focus=-1, where="ship"):
    """"already" when Status.json says it's done, "not_open" for closing a
    screen that isn't up, else ""."""
    if command.kind == "screen":
        shown = screen_shown(command, focus)
        if op == "on" and shown:
            return "already"
        if op == "off" and not shown:
            return "not_open"
        return ""
    # On foot, Status.json says nothing of your torch or night vision.
    if command.kind != "switch" or op not in ("on", "off") or where == "foot":
        return ""
    state = bool(int(flags or 0) & command.flag) != command.inverted
    return "already" if state == (op == "on") else ""


def screen_shown(command, focus):
    return SCREEN_FOCUS.get(command.id) == focus or (command.id == "system_map" and focus == 8)


# -- the power distributor --------------------------------------------------------------
# Half pips, as Status.json gives them: (systems, engines, weapons), 12 in all, 8 at most each.
SYSTEMS = {"sys": 0, "eng": 1, "wep": 2}
SYSTEM_NAMES = ("systems", "engines", "weapons")
POWER_ACTIONS = {"ship": {"sys": "IncreaseSystemsPower", "eng": "IncreaseEnginesPower", "wep": "IncreaseWeaponsPower",
                          "reset": "ResetPowerDistribution"},
                 "srv": {"sys": "IncreaseSystemsPower_Buggy", "eng": "IncreaseEnginesPower_Buggy",
                         "wep": "IncreaseWeaponsPower_Buggy", "reset": "ResetPowerDistribution_Buggy"}}
BALANCED = (4, 4, 4)
_SYSTEM = r"(sys(?:tems?)?|shields?|eng(?:ines?)?|thrusters|wep|weapons?|guns)"
_COUNT = r"(one|two|three|four|zero|none|no|[0-4]|max(?:imum)?|full|all)"
# "4 pips to systems", "full power to weapons", "weapons 2".
_PAIR = re.compile(rf"{_COUNT}(?: pips?| power)?(?: (?:to|in|into|on))? {_SYSTEM}|{_SYSTEM}(?: to)? {_COUNT}(?: pips?)?")
_NUMBERS = {"zero": 0, "none": 0, "no": 0, "one": 1, "two": 2, "three": 3, "four": 4, "max": 4, "maximum": 4,
            "full": 4, "all": 4}


def _system(word):
    word = word.casefold()
    return "sys" if word.startswith(("sys", "shield")) else "eng" if word.startswith(("eng", "thrust")) else "wep"


def _count(word):
    word = word.casefold()
    return int(word) if word.isdigit() else _NUMBERS[word]


def power_request(text):
    """What was asked of the power distributor, or None:
    {"reset": True}, {"press": "sys"} (one pip more), or
    {"target": (sys, eng, wep)} in half pips ("four pips to systems",
    "4 sys 2 wep", "pips 4 0 2", "max engines")."""
    words = re.sub(rf"^{_PLEASE}", "", _clean(text).rstrip("?"))
    words = re.sub(rf"{_AFTER}$", "", words)
    if not words or len(words) > 70:
        return None
    # Never "balance" alone: that's your credits.
    if re.fullmatch(r"(?:balance|reset|equali[sz]e|even out|centre|center) (?:the )?(?:power|pips|distributor|power distributor)"
                    r"|(?:power|pips)(?: to)? (?:balanced?|reset|even|equal)|balanced power"
                    r"|(?:pips|power)(?: to)? (?:two|2) (?:two|2) (?:two|2)", words):
        return {"reset": True}
    one = re.fullmatch(rf"(?:(?:more|extra|add) )?(?:power|a pip|one pip|pip|1 pip)(?: to)? {_SYSTEM}"
                       rf"|(?:boost|increase) {_SYSTEM}(?: power)?", words)
    if one:
        return {"press": _system(next(group for group in one.groups() if group))}
    order = re.fullmatch(rf"(?:set )?(?:pips|power)(?: to)? {_COUNT} {_COUNT} {_COUNT}", words)
    if order:
        target = tuple(2 * _count(word) for word in order.groups())
        return {"target": target} if sum(target) == 12 and max(target) <= 8 else {"invalid": True}
    pairs = _PAIR.findall(words)
    leftover = _PAIR.sub("", words)
    if not pairs or re.sub(r"\b(?:and|then|power|pips?|set|put|give me|all|with|the|,)\b", "", leftover).strip():
        return None
    if not re.search(r"\b(?:pips?|power|max(?:imum)?|full|all)\b|\d|^(?:one|two|three|four|zero) ", words) \
            and len(pairs) < 2:
        return None
    chosen = {}
    for count_a, system_a, system_b, count_b in pairs:
        system = _system(system_a or system_b)
        chosen[system] = 2 * _count(count_a or count_b)
    if len(chosen) > 3 or any(value > 8 for value in chosen.values()):
        return {"invalid": True}
    rest = [name for name in SYSTEMS if name not in chosen]
    left = 12 - sum(chosen.values())
    if left < 0 or (not rest and left):
        return {"invalid": True}
    for index, name in enumerate(rest):
        # What's left, shared: the first of the rest takes the odd half pip.
        share = left // len(rest) + (1 if index < left % len(rest) else 0)
        chosen[name] = share
    target = tuple(chosen[name] for name in SYSTEMS)
    return {"target": target} if max(target) <= 8 else {"invalid": True}


def press_power(state, system):
    """One press of a pip key, as the distributor answers it: a pip more
    (half a pip near the top), taken half from each of the others, or all
    from one when the other is empty."""
    pips = list(state)
    which = SYSTEMS[system]
    gain = min(2, 8 - pips[which])
    if gain <= 0:
        return tuple(pips)
    others = [index for index in range(3) if index != which]
    if gain == 2 and all(pips[index] >= 1 for index in others):
        for index in others:
            pips[index] -= 1
    else:
        donor = max(others, key=lambda index: pips[index])
        gain = min(gain, pips[donor])
        pips[donor] -= gain
    pips[which] += gain
    return tuple(pips)


def plan_power(current, target, limit=8):
    """The fewest presses ("reset", "sys", "eng", "wep") from ``current``
    to ``target``, or None. Unknown ``current`` starts with a reset."""
    target = tuple(target)
    start = tuple(current) if current else None
    if start == target:
        return []
    queue = deque([(start, [])] if start else [])
    queue.append((BALANCED, ["reset"]))
    seen = set()
    while queue:
        state, steps = queue.popleft()
        if state == target:
            return steps
        if state in seen or len(steps) >= limit:
            continue
        seen.add(state)
        for system in SYSTEMS:
            following = press_power(state, system)
            if following != state:
                queue.append((following, [*steps, system]))
    return None


def pips_words(state):
    def one(half):
        return str(half // 2) if half % 2 == 0 else f"{half / 2:g}"
    return ", ".join(f"{name} {one(value)}" for name, value in zip(SYSTEM_NAMES, state))


# -- what it says --------------------------------------------------------------------------
REPLIES = {
    "screen_open": ("{Label}.", "Opening {label}.", "{Label}, open."),
    "screen_close": ("Closing {label}.", "{Label}, closed."),
    "screen_already": ("{Label} is already open.",),
    "screen_not_open": ("{Label} isn't open.",),
    "switch_on": ("{Label}: {on}.", "{Label} {on}."),
    "switch_off": ("{Label}: {off}.", "{Label} {off}."),
    "switch_toggle": ("{Label}.",),
    "switch_already_on": ("{Label} is already {on}.",),
    "switch_already_off": ("{Label} is already {off}.",),
    "press": ("{Label}.",),
    "no_key": ("{Label} has no keyboard key in Elite's controls, only a pad or stick button, and I can only "
               "press keys. Give it a key there, and I can.",
               "There's no keyboard key for {label_l} in Elite's controls. Bind one, as a secondary if you like, "
               "and I'll press it."),
    "odd_key": ("Elite's key for {label_l} is one I can't press ({key}).",),
    "not_here": ("That's not one for {where}.",),
    "not_running": ("Elite isn't running. Nothing to press.",),
    "ship_off": ("Ship controls are off. Turn them on in Settings, under Voice.",),
    "power_reset": ("Power balanced.", "Two, two, two."),
    "power_press": ("More to {system}.", "A pip to {system}."),
    "power_set": ("Power: {pips}.",),
    "power_already": ("The power's already there: {pips}.",),
    "power_invalid": ("The distributor can't do that. Six pips in all, four at most in one.",),
    "power_unknown": ("I can't read the distributor from here.",),
    # Said after its first line, when pressing went wrong.
    "focus_failed": ("Elite wouldn't come to the front, so I pressed nothing.",),
    "lost_front": ("Elite stopped being in front, so I stopped pressing.",),
    "power_stuck": ("The distributor didn't answer. I stopped.",),
    "menu_closed": ("Open a panel or map first, then ask me to use its menu.",),
    "not_docked": ("The ship needs to be docked for that launch sequence.",),
    "macro_invalid": ("{Label} sequence in Settings needs fixing: {reason}",),
    "screen_stuck": ("The panel didn't open, so I stopped the sequence.",),
    "screen_changed": ("The screen changed, so I stopped the sequence.",),
    "place_changed": ("You changed vehicle, so I stopped pressing.",),
    "binding_changed": ("An Elite key binding changed, so I stopped the sequence.",),
    "press_failed": ("I couldn't finish pressing the ship's keys.",),
    "cancelled": ("The sequence stopped.",),
}


def reply(outcome, rng=None, **fields):
    if getattr(rng, "companion_identity", "") in {"axiom", "meridian"}:
        from voidcompass.overlays.crew_mind import command_reply
        return command_reply(outcome, rng, fields)
    if getattr(rng, "companion_identity", "") == "aster":
        from voidcompass.overlays.aster_lines import command_reply
        own = command_reply(outcome, rng, fields)
        if own:
            return own
    lines = REPLIES.get(outcome) or REPLIES["not_here"]
    line = rng.choice(lines) if rng is not None else lines[0]
    try:
        return line.format(**fields)
    except (KeyError, IndexError, ValueError):
        return lines[0] if "{" not in lines[0] else "Done."


def fields(command):
    label = command.say
    return {"Label": label[:1].upper() + label[1:], "label": label, "label_l": label,
            "on": command.words[0], "off": command.words[1]}
