"""Docking anywhere but home (5.7.7): each officer's own words. Their old
docking lines were all about coming home, so away from it they said nothing.
{station} is the station's name (not given for a carrier); a line quoting it
is skipped without one. No line here may call the station home."""

LINES = {
    "aster": (
        "Docked. Arrival entered.",
        "Docking complete, Commander.",
        "Clamps engaged. The arrivals column has its entry.",
        "Docked at {station}. Logged.",
        "Docked at {station}, Commander. Arrival recorded with the time and the pad.",
        "Clamps engaged at {station}. Repairs, fuel and restock are at your discretion.",
        "A clean docking. I have entered it without further comment, which is the highest praise the log allows.",
        "Docked. The ship is secure and the paperwork is, for once, ahead of us.",
        "Alongside at {station}. I shall keep the watch while you see to business.",
        "Docking complete. A station berth is a good moment to settle the accounts.",
        "Docked and secure. The next departure can wait until you decide on it.",
        "Arrival at {station} recorded. Services are available, should you require them.",
    ),
    "axiom": (
        "Docked.",
        "Docked. Clamps confirmed.",
        "Docked at {station}.",
        "Arrival recorded: {station}.",
        "Docked at {station}. I have counted the pads. You chose a good one.",
        "Clamps engaged. Velocity zero. My favourite velocity, when docked.",
        "Docked. A station is a very dense cluster of data. I am enjoying it.",
        "Docked at {station}. Thousands of ships pass through here. I will try not to count them all.",
        "We are docked. One arrival added to the record. The record approves.",
        "Docked. Everything outside the hull is now measured in metres. A pleasant change of scale.",
        "Docked at {station}. A good moment to sell anything I have catalogued.",
        "Docked. I have logged the arrival and nothing else needs a decision.",
    ),
    "meridian": (
        "Docked.",
        "Made fast.",
        "Moored at {station}.",
        "Alongside {station}.",
        "Moored at {station}, Commander. A safe berth for a while.",
        "Made fast. Lines out, engines quiet. A good docking.",
        "Alongside at {station}. Every harbour has its own character. I like this one's.",
        "Docked. A navigator rests easiest with a wall on every side.",
        "Moored. I will note the berth in the log, as I always have.",
        "Alongside {station}. Take on what you need. The charts will keep.",
        "Made fast at {station}. Landfall, of a kind.",
        "Docked. Well brought in, Commander.",
    ),
    "lyra": (
        "Docked.",
        "Docked. Fuel first.",
        "Docked at {station}.",
        "Clamped at {station}. Systems resting.",
        "Docked at {station}. Refuel, repair, restock. In that order, please.",
        "Clamps on. Engines down. My favourite readings are the boring ones.",
        "Docked. I am topping up the tank before anything else. Habit.",
        "Docked at {station}. Lovely. I have checked the fuel price already.",
        "We are in. Hull sound, tank about to be full. Good docking, Commander.",
        "Docked. Every system green. I like stations. They have fuel.",
        "Docked at {station}. I will run a quiet maintenance pass while we are here.",
        "Docked. Safe, fuelled soon, and nothing on the boards. Perfect.",
    ),
}


def officer(identity):
    """(restrained, full) docking lines for an officer."""
    lines = LINES[identity]
    return lines[:4], lines
