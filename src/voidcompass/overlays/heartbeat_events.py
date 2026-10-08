"""What the journal heartbeat orb does for each journal event.

The orb watches every journal line. Each event gets a family (what part of
the game it belongs to), a theme tone (the colour it leaves in the iris), a
visual effect and a weight from 0 to 1 (how strongly the orb reacts and
which effect wins when a burst of events lands at once). Events that are
not listed here still reach the orb: prefixes cover whole event groups, and
anything else falls back to a quiet generic pulse, so a new Frontier event
is never ignored.

The effect names are the painters in web/heartbeat/orb.js.
"""

from __future__ import annotations

TONES = ("accent", "orange", "green", "yellow", "red", "muted")

EFFECTS = (
    "pulse", "tick", "wake", "sleep", "warp", "charge", "cruise", "plot",
    "approach", "depart", "sweep", "honk", "signal", "spark", "complete",
    "lock", "alarm", "breach", "die", "clear", "strike", "gather", "payout",
    "crack", "dock", "undock", "deny", "speak", "glint",
)

# event: (family, tone, effect, weight)
_EVENTS = {
    # Session. The orb wakes with the game and sleeps when it closes.
    "Fileheader": ("system", "muted", "tick", .05),
    "Commander": ("system", "muted", "tick", .05),
    "LoadGame": ("system", "accent", "wake", 1.0),
    "NewCommander": ("system", "accent", "wake", 1.0),
    "ClearSavedGame": ("system", "muted", "sleep", .6),
    "Shutdown": ("system", "muted", "sleep", 1.0),
    "Continued": ("system", "muted", "tick", .02),
    "Music": ("system", "muted", "tick", .05),
    "Statistics": ("system", "muted", "tick", .05),
    "Materials": ("system", "muted", "tick", .05),
    "Cargo": ("system", "muted", "tick", .05),
    "Missions": ("system", "muted", "tick", .05),
    "Loadout": ("system", "muted", "tick", .08),
    "Rank": ("system", "muted", "tick", .05),
    "Progress": ("system", "muted", "tick", .05),
    "Reputation": ("system", "muted", "tick", .05),
    "Powerplay": ("system", "muted", "tick", .05),
    "SquadronStartup": ("system", "muted", "tick", .05),
    "Backpack": ("system", "muted", "tick", .05),
    "ShipLocker": ("system", "muted", "tick", .05),
    "Market": ("system", "muted", "tick", .08),
    "Outfitting": ("system", "muted", "tick", .08),
    "Shipyard": ("system", "muted", "tick", .08),
    "StoredShips": ("system", "muted", "tick", .08),
    "StoredModules": ("system", "muted", "tick", .08),
    "ModuleInfo": ("system", "muted", "tick", .05),
    "ReservoirReplenished": ("system", "muted", "tick", .08),
    "CarrierStats": ("system", "muted", "tick", .05),
    "CarrierLocation": ("system", "muted", "tick", .08),
    "FCMaterials": ("system", "muted", "tick", .05),
    "EngineerProgress": ("system", "yellow", "tick", .12),

    # Travel.
    "StartJump": ("travel", "orange", "charge", .85),
    "FSDJump": ("travel", "accent", "warp", .95),
    "CarrierJump": ("travel", "accent", "warp", .95),
    "SupercruiseEntry": ("travel", "orange", "cruise", .55),
    "SupercruiseExit": ("travel", "accent", "cruise", .5),
    "SupercruiseDestinationDrop": ("travel", "accent", "cruise", .5),
    "FSDTarget": ("travel", "orange", "plot", .35),
    "NavRoute": ("travel", "orange", "plot", .55),
    "NavRouteClear": ("travel", "muted", "plot", .3),
    "JetConeBoost": ("travel", "accent", "charge", .8),
    "Location": ("travel", "accent", "pulse", .3),
    "ApproachBody": ("travel", "accent", "approach", .5),
    "LeaveBody": ("travel", "green", "depart", .45),
    "ApproachSettlement": ("travel", "accent", "approach", .4),
    "USSDrop": ("travel", "yellow", "signal", .55),
    "FuelScoop": ("travel", "yellow", "gather", .25),
    "BookTaxi": ("travel", "accent", "plot", .35),
    "BookDropship": ("travel", "accent", "plot", .35),
    "CancelTaxi": ("travel", "muted", "deny", .3),
    "CancelDropship": ("travel", "muted", "deny", .3),
    "DropshipDeploy": ("travel", "orange", "undock", .6),
    "CarrierJumpRequest": ("travel", "accent", "charge", .7),
    "CarrierJumpCancelled": ("travel", "yellow", "deny", .45),

    # Exploration and scanning.
    "FSSDiscoveryScan": ("scan", "accent", "honk", .75),
    "DiscoveryScan": ("scan", "accent", "honk", .7),
    "NavBeaconScan": ("scan", "accent", "honk", .6),
    "Scan": ("scan", "accent", "sweep", .4),
    "ScanBaryCentre": ("scan", "accent", "sweep", .3),
    "FSSSignalDiscovered": ("scan", "accent", "signal", .25),
    "FSSBodySignals": ("scan", "yellow", "signal", .5),
    "SAASignalsFound": ("scan", "yellow", "signal", .55),
    "FSSAllBodiesFound": ("scan", "green", "complete", .8),
    "SAAScanComplete": ("scan", "green", "complete", .75),
    "CodexEntry": ("scan", "yellow", "spark", .7),
    "ScanOrganic": ("scan", "green", "spark", .6),
    "DataScanned": ("scan", "accent", "sweep", .35),
    "DatalinkScan": ("scan", "accent", "sweep", .35),
    "DatalinkVoucher": ("scan", "green", "payout", .4),
    "MaterialDiscovered": ("scan", "yellow", "spark", .45),
    "Screenshot": ("scan", "accent", "glint", .35),
    "ShipTargeted": ("scan", "yellow", "lock", .2),
    "Scanned": ("scan", "orange", "lock", .45),
    "ProspectedAsteroid": ("trade", "yellow", "sweep", .45),
    "AsteroidCracked": ("trade", "orange", "crack", .7),

    # Combat and hazards. Red is the orb's HAL moment.
    "UnderAttack": ("danger", "red", "alarm", .85),
    "HullDamage": ("danger", "red", "alarm", .9),
    "ShieldState": ("danger", "red", "breach", .9),
    "Interdicted": ("danger", "red", "alarm", 1.0),
    "Interdiction": ("danger", "orange", "lock", .7),
    "EscapeInterdiction": ("danger", "green", "clear", .8),
    "HeatWarning": ("danger", "orange", "alarm", .85),
    "HeatDamage": ("danger", "red", "alarm", .9),
    "CockpitBreached": ("danger", "red", "breach", 1.0),
    "SystemsShutdown": ("danger", "red", "alarm", 1.0),
    "JetConeDamage": ("danger", "red", "breach", .9),
    "SelfDestruct": ("danger", "red", "die", 1.0),
    "Died": ("danger", "red", "die", 1.0),
    "Resurrect": ("danger", "accent", "wake", .9),
    "FighterDestroyed": ("danger", "red", "breach", .85),
    "SRVDestroyed": ("danger", "red", "breach", .85),
    "FighterRebuilt": ("danger", "green", "clear", .4),
    "CrimeVictim": ("danger", "orange", "alarm", .6),
    "CommitCrime": ("danger", "orange", "alarm", .6),
    "Bounty": ("danger", "yellow", "strike", .6),
    "FactionKillBond": ("danger", "yellow", "strike", .6),
    "CapShipBond": ("danger", "yellow", "strike", .8),
    "PVPKill": ("danger", "red", "strike", .85),
    "RebootRepair": ("danger", "yellow", "wake", .8),
    "AfmuRepairs": ("danger", "green", "clear", .55),

    # Cargo, mining, materials and trade.
    "MarketBuy": ("trade", "orange", "gather", .45),
    "MarketSell": ("trade", "green", "payout", .55),
    "CollectCargo": ("trade", "orange", "gather", .4),
    "EjectCargo": ("trade", "orange", "payout", .35),
    "MiningRefined": ("trade", "orange", "gather", .55),
    "CargoTransfer": ("trade", "orange", "gather", .35),
    "CargoDepot": ("trade", "orange", "gather", .35),
    "LaunchDrone": ("trade", "muted", "tick", .15),
    "BuyDrones": ("trade", "orange", "gather", .25),
    "SellDrones": ("trade", "orange", "payout", .2),
    "MaterialCollected": ("trade", "yellow", "gather", .35),
    "MaterialDiscarded": ("trade", "muted", "tick", .1),
    "MaterialTrade": ("trade", "yellow", "gather", .35),
    "Synthesis": ("trade", "accent", "spark", .45),
    "EngineerCraft": ("trade", "yellow", "glint", .6),
    "EngineerContribution": ("trade", "yellow", "gather", .35),
    "TechnologyBroker": ("trade", "yellow", "glint", .55),
    "BuyTradeData": ("trade", "muted", "tick", .15),
    "BuyExplorationData": ("trade", "accent", "plot", .3),
    "CollectItems": ("trade", "green", "gather", .35),
    "DropItems": ("trade", "muted", "tick", .1),
    "BackpackChange": ("trade", "muted", "tick", .08),
    "BuyMicroResources": ("trade", "orange", "gather", .35),
    "SellMicroResources": ("trade", "green", "payout", .4),
    "TradeMicroResources": ("trade", "orange", "gather", .3),
    "TransferMicroResources": ("trade", "muted", "tick", .1),
    "UseConsumable": ("trade", "green", "clear", .35),
    "UpgradeSuit": ("trade", "yellow", "glint", .5),
    "UpgradeWeapon": ("trade", "yellow", "glint", .5),
    "BuySuit": ("trade", "orange", "gather", .35),
    "BuyWeapon": ("trade", "orange", "gather", .35),
    "SellSuit": ("trade", "green", "payout", .3),
    "SellWeapon": ("trade", "green", "payout", .3),
    "RefuelAll": ("trade", "yellow", "gather", .35),
    "RefuelPartial": ("trade", "yellow", "gather", .3),

    # Missions, money and rank.
    "MissionAccepted": ("career", "yellow", "glint", .45),
    "MissionCompleted": ("career", "green", "payout", .7),
    "MissionFailed": ("career", "orange", "deny", .6),
    "MissionAbandoned": ("career", "muted", "deny", .45),
    "MissionRedirected": ("career", "yellow", "plot", .45),
    "Promotion": ("career", "yellow", "glint", .95),
    "CommunityGoal": ("career", "muted", "tick", .1),
    "CommunityGoalJoin": ("career", "yellow", "glint", .4),
    "CommunityGoalReward": ("career", "green", "payout", .8),
    "CommunityGoalDiscard": ("career", "muted", "deny", .3),
    "RedeemVoucher": ("career", "green", "payout", .6),
    "SellExplorationData": ("career", "green", "payout", .75),
    "MultiSellExplorationData": ("career", "green", "payout", .75),
    "SellOrganicData": ("career", "green", "payout", .8),
    "SearchAndRescue": ("career", "green", "payout", .45),
    "PayFines": ("career", "orange", "payout", .35),
    "PayBounties": ("career", "orange", "payout", .35),
    "PayLegacyFines": ("career", "orange", "payout", .35),
    "PowerplayMerits": ("career", "yellow", "gather", .3),
    "PowerplayRank": ("career", "yellow", "glint", .7),

    # Docking, landing, vehicles and station services.
    "DockingRequested": ("port", "green", "pulse", .35),
    "DockingGranted": ("port", "green", "dock", .55),
    "DockingDenied": ("port", "orange", "deny", .7),
    "DockingCancelled": ("port", "muted", "deny", .35),
    "DockingTimeout": ("port", "yellow", "deny", .5),
    "Docked": ("port", "green", "dock", .8),
    "Undocked": ("port", "accent", "undock", .75),
    "Touchdown": ("port", "accent", "dock", .7),
    "Liftoff": ("port", "orange", "undock", .6),
    "LaunchSRV": ("port", "accent", "undock", .6),
    "DockSRV": ("port", "accent", "dock", .6),
    "LaunchFighter": ("port", "accent", "undock", .6),
    "DockFighter": ("port", "accent", "dock", .6),
    "VehicleSwitch": ("port", "accent", "pulse", .4),
    "Embark": ("port", "accent", "dock", .6),
    "Disembark": ("port", "accent", "undock", .6),
    "Repair": ("port", "green", "clear", .4),
    "RepairAll": ("port", "green", "clear", .4),
    "RestockVehicle": ("port", "green", "clear", .4),
    "BuyAmmo": ("port", "green", "clear", .35),
    "ClearImpound": ("port", "green", "clear", .4),
    "ShipyardBuy": ("port", "accent", "glint", .6),
    "ShipyardNew": ("port", "accent", "glint", .6),
    "ShipyardSwap": ("port", "accent", "glint", .55),
    "ShipyardSell": ("port", "accent", "pulse", .35),
    "ShipyardTransfer": ("port", "accent", "pulse", .35),
    "ShipyardRedeem": ("port", "accent", "glint", .5),
    "ShipRedeemed": ("port", "accent", "glint", .5),
    "SetUserShipName": ("port", "accent", "glint", .4),
    "SellShipOnRebuy": ("port", "accent", "pulse", .3),

    # Comms, wings, crew and squadrons.
    "ReceiveText": ("comms", "accent", "speak", .45),
    "SendText": ("comms", "accent", "speak", .4),
    "Friends": ("comms", "accent", "pulse", .3),
    "WingJoin": ("comms", "green", "glint", .5),
    "WingAdd": ("comms", "green", "glint", .5),
    "WingInvite": ("comms", "green", "glint", .45),
    "WingLeave": ("comms", "muted", "deny", .35),
    "JoinACrew": ("comms", "accent", "dock", .5),
    "CrewMemberJoins": ("comms", "accent", "dock", .5),
    "QuitACrew": ("comms", "muted", "undock", .45),
    "CrewMemberQuits": ("comms", "muted", "undock", .45),
    "EndCrewSession": ("comms", "muted", "undock", .45),
    "KickCrewMember": ("comms", "muted", "undock", .45),
    "CrewLaunchFighter": ("comms", "accent", "undock", .45),

    # Carrier operations.
    "CarrierBuy": ("carrier", "accent", "glint", .9),
    "CarrierDecommission": ("carrier", "red", "deny", .6),
    "CarrierCancelDecommission": ("carrier", "green", "clear", .6),
    "CarrierDepositFuel": ("carrier", "yellow", "gather", .4),
    "CarrierTradeOrder": ("carrier", "orange", "gather", .35),
    "CarrierBankTransfer": ("carrier", "green", "payout", .35),
    "CarrierFinance": ("carrier", "muted", "tick", .08),
}

# Whole event groups, checked in order, for events the table does not name.
_PREFIXES = (
    ("Carrier", ("carrier", "accent", "pulse", .3)),
    ("Mission", ("career", "yellow", "glint", .35)),
    ("Powerplay", ("career", "yellow", "glint", .35)),
    ("CommunityGoal", ("career", "yellow", "glint", .35)),
    ("Squadron", ("comms", "accent", "glint", .35)),
    ("Wing", ("comms", "accent", "pulse", .3)),
    ("Crew", ("comms", "accent", "pulse", .3)),
    ("NpcCrew", ("comms", "accent", "pulse", .25)),
    ("Shipyard", ("port", "accent", "pulse", .3)),
    ("Module", ("port", "accent", "pulse", .25)),
    ("MassModule", ("port", "accent", "pulse", .25)),
    ("FetchRemote", ("port", "accent", "pulse", .25)),
    ("Docking", ("port", "green", "pulse", .35)),
    ("Suit", ("port", "accent", "pulse", .25)),
    ("SwitchSuit", ("port", "accent", "pulse", .25)),
    ("CreateSuit", ("port", "accent", "pulse", .25)),
    ("DeleteSuit", ("port", "accent", "pulse", .25)),
    ("RenameSuit", ("port", "accent", "pulse", .25)),
    ("LoadoutEquip", ("port", "accent", "pulse", .25)),
    ("LoadoutRemove", ("port", "accent", "pulse", .25)),
    ("Engineer", ("trade", "yellow", "glint", .4)),
    ("Colonisation", ("trade", "orange", "gather", .35)),
    ("Construction", ("trade", "orange", "gather", .35)),
    ("Market", ("trade", "orange", "gather", .3)),
    ("Material", ("trade", "yellow", "gather", .3)),
    ("Buy", ("trade", "orange", "gather", .3)),
    ("Sell", ("trade", "green", "payout", .35)),
    ("Pay", ("career", "orange", "payout", .3)),
    ("FSS", ("scan", "accent", "signal", .3)),
    ("SAA", ("scan", "accent", "signal", .35)),
    ("Codex", ("scan", "yellow", "spark", .4)),
    ("Scan", ("scan", "accent", "sweep", .35)),
    ("Taxi", ("travel", "accent", "plot", .3)),
    ("Dropship", ("travel", "accent", "plot", .3)),
    ("Supercruise", ("travel", "accent", "cruise", .45)),
    ("Fighter", ("port", "accent", "pulse", .35)),
    ("SRV", ("port", "accent", "pulse", .35)),
)

_DEFAULT = ("log", "muted", "pulse", .15)

# Where the eye looks when an event lands (todo-watcher-life.md). The
# direction is symbolic, never a measurement: travel looks ahead and up,
# scans sweep, ports and surfaces look down, danger gets a side-eye.
GAZES = ("centre", "up", "down", "left", "right", "sweep", "side")
_FAMILY_GAZE = {
    "travel": "up", "scan": "sweep", "danger": "side", "port": "down",
    "trade": "left", "career": "up", "comms": "right", "carrier": "up",
    "system": "centre", "log": "centre",
}
_EFFECT_GAZE = {
    "warp": "up", "charge": "up", "cruise": "up", "plot": "up",
    "approach": "down", "dock": "down", "undock": "down",
    "honk": "sweep", "signal": "sweep", "sweep": "sweep",
    "alarm": "side", "breach": "side", "strike": "side", "lock": "side",
}
_RARE_PLANETS = {"earthlike body", "water world", "ammonia world"}

# Channels that are real people rather than NPC or station chatter.
_PEOPLE_CHANNELS = {"player", "wing", "friend", "squadron", "squadleaders", "local", "voicechat"}


def classify(event, detail=None):
    """Return {event, family, tone, effect, weight} for one journal event."""
    name = str(event or "").strip()
    detail = detail if isinstance(detail, dict) else {}
    spec = _EVENTS.get(name)
    if spec is None:
        spec = next(
            (value for prefix, value in _PREFIXES if name.startswith(prefix)),
            _DEFAULT,
        )
    family, tone, effect, weight = spec
    # A handful of events mean opposite things depending on their fields.
    if name == "ShieldState" and detail.get("ShieldsUp"):
        tone, effect, weight = "green", "clear", .6
    elif name == "StartJump" and str(detail.get("JumpType") or "") == "Supercruise":
        effect, weight = "cruise", .55
    elif name == "CodexEntry" and detail.get("IsNewEntry"):
        weight = .85
    elif name == "ShipTargeted" and not detail.get("TargetLocked", True):
        effect, weight = "tick", .05
    elif name == "ReceiveText":
        channel = str(detail.get("Channel") or "").casefold()
        if channel in _PEOPLE_CHANNELS:
            weight = .6
        elif channel == "npc":
            weight = .25
    elif name == "Music":
        # The game's own music is a fair read of the moment: combat themes
        # warm the iris red, and the main menu puts the orb to sleep.
        track = str(detail.get("MusicTrack") or "")
        if track.startswith("Combat") or track in {"Unknown_Encounter", "Thargoid_Combat"}:
            tone, effect, weight = "red", "pulse", .35
        elif track == "MainMenu":
            tone, effect, weight = "muted", "sleep", .4
    gaze = _EFFECT_GAZE.get(effect) or _FAMILY_GAZE.get(family, "centre")
    if name in {"FuelScoop"}:
        gaze = "down"
    # Rare finds earn a double take: a first discovery, an Earth-like,
    # water or ammonia world, or a Codex entry new to the commander.
    rare = False
    if name == "Scan" and (detail.get("PlanetClass") or detail.get("StarType")):
        rare = (detail.get("WasDiscovered") is False
                or str(detail.get("PlanetClass") or "").casefold() in _RARE_PLANETS)
    elif name == "CodexEntry":
        rare = bool(detail.get("IsNewEntry"))
    elif name in {"Promotion", "CarrierBuy", "ShipyardNew"}:
        rare = True
    return {
        "event": name[:40] or "Journal",
        "family": family,
        "tone": tone,
        "effect": effect,
        "weight": round(float(weight), 2),
        "gaze": gaze,
        "rare": rare,
    }
