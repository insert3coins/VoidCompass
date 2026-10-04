"""Every faction state the BGS has: what it means and how the tab shows it."""

from __future__ import annotations

# state -> (label, group, tone, what it does)
STATES = {
    "War": ("War", "conflict", "red", "Fighting another faction for its assets: combat zones decide it."),
    "CivilWar": ("Civil war", "conflict", "red", "Fighting a faction of the same allegiance for its assets."),
    "Election": ("Election", "conflict", "yellow", "A political contest for assets: missions, trade and data decide it."),
    "Expansion": ("Expansion", "expansion", "accent", "Spreading to a nearby system."),
    "Retreat": ("Retreat", "danger", "red", "Influence below 5%: it leaves the system if it does not recover."),
    "Boom": ("Boom", "good", "green", "Trade booming: trade and mission influence count for more."),
    "Bust": ("Bust", "bad", "orange", "Economy failing: trade counts for less."),
    "Investment": ("Investment", "good", "green", "Investing in the system's future."),
    "CivilLiberty": ("Civil liberty", "good", "green", "Low crime, good security."),
    "PublicHoliday": ("Public holiday", "good", "green", "Celebrations: more passenger demand."),
    "CivilUnrest": ("Civil unrest", "bad", "orange", "Lawlessness: bounty hunting helps."),
    "Famine": ("Famine", "bad", "orange", "Food shortage: deliver food."),
    "Outbreak": ("Outbreak", "bad", "orange", "Disease: deliver medicines."),
    "Lockdown": ("Lockdown", "bad", "orange", "Locked down by security: few services."),
    "PirateAttack": ("Pirate attack", "bad", "orange", "Pirates attacking: fight them."),
    "Terrorism": ("Terrorist attack", "bad", "orange", "Terrorism: missions and bounties help."),
    "Blight": ("Blight", "bad", "orange", "Crop blight: deliver agronomic treatments."),
    "Drought": ("Drought", "bad", "orange", "Water shortage: deliver water."),
    "InfrastructureFailure": ("Infrastructure failure", "bad", "orange", "Infrastructure failing: deliver machinery."),
    "NaturalDisaster": ("Natural disaster", "bad", "orange", "Disaster: rescue and supplies help."),
    "Colonisation": ("Colonisation", "expansion", "accent", "Colonising the system."),
    "TradeWar": ("Trade war", "conflict", "orange", "An economic war."),
    "None": ("None", "none", "muted", "No state."),
}
CONFLICT_STATES = {"War", "CivilWar", "Election"}
BAD_STATES = {name for name, row in STATES.items() if row[1] in ("bad", "danger")}

HAPPINESS = {
    "$Faction_HappinessBand1;": "Elated", "$Faction_HappinessBand2;": "Happy", "$Faction_HappinessBand3;": "Discontented",
    "$Faction_HappinessBand4;": "Unhappy", "$Faction_HappinessBand5;": "Despondent",
}

# Thresholds the alerts use (influence is a fraction, 0..1).
RETREAT_INFLUENCE = 0.05
RETREAT_DANGER = 0.035
CLOSE_RACE = 0.03
BIG_DROP = 0.03


def state_info(name):
    label, group, tone, text = STATES.get(str(name or "None"), (str(name or ""), "other", "muted", ""))
    return {"name": str(name or "None"), "label": label, "group": group, "tone": tone, "text": text}


def clean(value):
    """``$government_Corporate;`` / ``$economy_HighTech;`` -> readable text."""
    text = str(value or "").strip()
    if text.startswith("$") and text.endswith(";"):
        text = text[1:-1]
        for prefix in ("government_", "economy_", "SYSTEM_SECURITY_", "GAlAXY_MAP_INFO_state_", "Faction_"):
            if text.startswith(prefix):
                text = text[len(prefix):]
        text = text.replace("_", " ")
    return text
