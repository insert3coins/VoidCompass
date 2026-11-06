"""More of your game, in the companions' words (5.7.6): the journal events they
used to let pass, as the schema (schemas.edomh.nl) describes them. Danger and
the law, missions and community goals, ships, outfitting and engineers, the
carrier, colonies and Powerplay, the crew, wings and the kit you wear.

The words are in the life_* modules; ship_life merges them in, so every
companion picks them up the way it does the ship's everyday life."""
from voidcompass.overlays import life_carrier, life_crew, life_danger, life_missions, life_ships

GROUPS = (life_danger, life_missions, life_ships, life_carrier, life_crew)
IMPORTANCE = {topic: level for group in GROUPS for topic, level in group.IMPORTANCE.items()}

COMBAT_RANKS = ("Harmless", "Mostly Harmless", "Novice", "Competent", "Expert", "Master", "Dangerous", "Deadly", "Elite")
_CRIMES = {
    "assault": "assault", "murder": "murder", "piracy": "piracy", "interdiction": "an illegal interdiction",
    "illegalcargo": "carrying illegal cargo", "disobeypolice": "ignoring the police", "fireinnofirezone": "firing in a no-fire zone",
    "fireinstation": "firing inside a station", "dumpingdangerous": "dumping dangerous cargo",
    "dumpingnearstation": "dumping cargo near a station", "recklessweaponsdischarge": "reckless weapons fire",
    "passengerwanted": "carrying a wanted passenger", "collidedatspeedinnofirezone": "ramming at speed in a no-fire zone",
    "collidedatspeedinnofirezone_hulldamage": "ramming at speed in a no-fire zone",
    "detectionofweapon": "carrying a weapon where it's banned", "recklessendangerment": "reckless endangerment",
    "trespass": "trespassing", "theft": "theft", "identitytheft": "identity theft", "propertytheft": "theft",
    "datatransfer": "an illegal data transfer", "settlementshutdown": "shutting down a settlement",
    "occupiedescapepod": "an escape pod with someone in it", "overcharge": "overcharging a settlement's power",
}


def _text(raw, *keys):
    for key in keys:
        value = str((raw or {}).get(key) or "").strip()
        if value and not value.startswith("$"):
            return value
    return ""


def _whole(value):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def credits(value):
    return f"{_whole(value):,} credits"


def crime(kind):
    """A CrimeType as words, said mid-sentence ("firing in a no-fire zone")."""
    key = str(kind or "").strip()
    bare = key.split("_", 1)[1] if key.casefold().startswith("onfoot_") else key
    if bare.casefold().startswith("docking"):
        rest = bare.casefold()
        return ("blocking the airlock" if "airlock" in rest else "blocking a landing pad" if "landingpad" in rest
                else "trespassing on a pad")
    found = _CRIMES.get(bare.casefold())
    if found:
        return found
    words = "".join(f" {ch.lower()}" if ch.isupper() else ch for ch in bare).replace("_", " ").strip()
    return words or "a crime"


def _ship(raw):
    return _text(raw, "ShipType_Localised") or str((raw or {}).get("ShipType") or "").replace("_", " ").title()


def moment(event, raw):
    """(topic, fields) for one of these events worth a word, or None. Each
    field also comes capitalised ({Crime}), for the start of a sentence."""
    found = _moment(event, raw or {})
    if not found:
        return None
    topic, fields = found
    capitals = {key[:1].upper() + key[1:]: value[:1].upper() + value[1:] for key, value in fields.items()
                if isinstance(value, str) and key[:1].islower()}
    return topic, {**capitals, **fields}


def _moment(event, raw):
    if event == "CockpitBreached":
        return "cockpit_breached", {}
    if event == "SystemsShutdown":
        return "systems_shutdown", {}
    if event == "SelfDestruct":
        return "self_destruct", {}
    if event == "CommitCrime":
        fields = {"crime": crime(raw.get("CrimeType"))}
        if _whole(raw.get("Bounty")):
            fields["penalty"] = f"a {_whole(raw['Bounty']):,} credit bounty"
        elif _whole(raw.get("Fine")):
            fields["penalty"] = f"a {_whole(raw['Fine']):,} credit fine"
        return "crime_committed", fields
    if event == "CrimeVictim":
        offender = _text(raw, "Offender_Localised", "Offender")
        return ("crime_victim", {"offender": offender, "crime": crime(raw.get("CrimeType"))}) if offender else None
    if event in ("PayFines", "PayBounties"):
        if not _whole(raw.get("Amount")):
            return None
        return "paid_off", {"credits": credits(raw["Amount"]), "kind": "fines" if event == "PayFines" else "bounties"}
    if event == "ClearImpound":
        ship = _ship(raw)
        return ("impound_cleared", {"ship": ship}) if ship else None
    if event == "RebootRepair":
        return "reboot_repair", {}
    if event == "Interdiction":
        target = _text(raw, "Interdicted_Localised", "Interdicted")
        return ("interdicted_them", {"target": target}) if raw.get("Success") and target else None
    if event == "MissionAccepted":
        mission = _text(raw, "LocalisedName")
        if not mission:
            return None
        fields = {"mission": mission}
        where = _text(raw, "DestinationStation") or _text(raw, "DestinationSystem")
        if where:
            fields["where"] = where
        return "mission_accepted", fields
    if event in ("MissionFailed", "MissionAbandoned"):
        mission = _text(raw, "LocalisedName")
        return ("mission_failed" if event == "MissionFailed" else "mission_abandoned", {"mission": mission}) if mission else None
    if event == "MissionRedirected":
        mission = _text(raw, "LocalisedName")
        station, system = _text(raw, "NewDestinationStation"), _text(raw, "NewDestinationSystem")
        return ("mission_redirected", {"mission": mission, "station": station, "system": system}) if mission and station and system else None
    if event == "SearchAndRescue":
        item = _text(raw, "Name_Localised", "Name")
        return ("rescue_handed_in", {"item": item.lower(), "count": str(_whole(raw.get("Count"))),
                                     "credits": credits(raw.get("Reward"))}) if item and _whole(raw.get("Count")) else None
    if event in ("CommunityGoalJoin", "CommunityGoalDiscard"):
        goal = _text(raw, "Name")
        if not goal:
            return None
        return ("cg_joined", {"goal": goal, "system": _text(raw, "System") or "its system"}) if event == "CommunityGoalJoin" \
            else ("cg_left", {"goal": goal})
    if event == "CommunityGoalReward":
        goal = _text(raw, "Name")
        return ("cg_reward", {"goal": goal, "credits": credits(raw.get("Reward"))}) if goal else None
    if event == "ShipyardBuy":
        ship = _ship(raw)
        return ("ship_bought", {"ship": ship, "credits": credits(raw.get("ShipPrice"))}) if ship else None
    if event == "ShipyardSell":
        ship = _ship(raw)
        return ("ship_sold", {"ship": ship}) if ship else None
    if event == "SetUserShipName":
        name = _text(raw, "UserShipName")
        return ("ship_named", {"name": name}) if name else None
    if event in ("ModuleBuy", "ModuleSwap", "ModuleRetrieve"):
        module = _text(raw, "BuyItem_Localised", "ToItem_Localised", "RetrievedItem_Localised")
        return ("outfitted", {"module": module}) if module else None
    if event == "ShipyardTransfer":
        ship, system = _ship(raw), _text(raw, "System")
        if not ship or not system:
            return None
        return "ship_transfer", {"ship": ship, "system": system, "minutes": str(max(1, round(_whole(raw.get("TransferTime")) / 60)))}
    if event == "EngineerProgress":
        engineer = _text(raw, "Engineer")
        if not engineer or raw.get("Engineers"):
            return None  # the start-of-session list, not news
        progress = str(raw.get("Progress") or "").casefold()
        rank = _whole(raw.get("Rank"))
        if rank >= 2:
            return "engineer_rank", {"engineer": engineer, "rank": str(rank)}
        if progress == "unlocked":
            return "engineer_unlocked", {"engineer": engineer}
        if progress == "invited":
            return "engineer_invited", {"engineer": engineer}
        return None
    if event == "MaterialDiscovered":
        material = _text(raw, "Name_Localised", "Name")
        return ("material_discovered", {"material": material}) if material else None
    if event == "MaterialTrade":
        paid, received = raw.get("Paid") or {}, raw.get("Received") or {}
        paid_name, received_name = _text(paid, "Material_Localised", "Material"), _text(received, "Material_Localised", "Material")
        if not paid_name or not received_name:
            return None
        return "material_traded", {"paid": paid_name, "paid_n": str(_whole(paid.get("Quantity"))),
                                   "received": received_name, "received_n": str(_whole(received.get("Quantity")))}
    if event == "CarrierBuy":
        callsign = _text(raw, "Callsign")
        return ("carrier_bought", {"callsign": callsign, "system": _text(raw, "Location") or "here"}) if callsign else None
    if event == "CarrierNameChange":
        name = _text(raw, "Name")
        return ("carrier_renamed", {"name": name}) if name else None
    if event == "CarrierDecommission":
        return "carrier_decommission", {}
    if event == "CarrierCancelDecommission":
        return "carrier_kept", {}
    if event == "CarrierDepositFuel":
        if not _whole(raw.get("Amount")):
            return None
        return "carrier_fuelled", {"tonnes": str(_whole(raw.get("Amount"))), "total": str(_whole(raw.get("Total")))}
    if event == "CarrierTradeOrder":
        commodity = _text(raw, "Commodity_Localised", "Commodity")
        if not commodity:
            return None
        order = ("cancelled order" if raw.get("CancelTrade") else "buy order" if raw.get("PurchaseOrder")
                 else "sell order" if raw.get("SaleOrder") else "")
        return ("carrier_order", {"commodity": commodity, "order": order}) if order else None
    if event in ("ColonisationSystemClaim", "ColonisationSystemClaimRelease"):
        system = _text(raw, "StarSystem")
        return ("colony_claimed" if event == "ColonisationSystemClaim" else "colony_released", {"system": system}) if system else None
    if event == "ColonisationBeaconDeployed":
        return "colony_beacon", {}
    if event == "ColonisationContribution":
        rows = [row for row in raw.get("Contributions") or () if isinstance(row, dict) and _whole(row.get("Amount"))]
        if not rows:
            return None
        top = max(rows, key=lambda row: _whole(row.get("Amount")))
        return "colony_contribution", {"tonnes": f"{sum(_whole(row.get('Amount')) for row in rows):,}",
                                       "commodity": _text(top, "Name_Localised", "Name") or "cargo"}
    if event in ("PowerplayJoin", "PowerplayLeave"):
        power = _text(raw, "Power")
        return ("power_joined" if event == "PowerplayJoin" else "power_left", {"power": power}) if power else None
    if event == "PowerplayDefect":
        new, old = _text(raw, "ToPower"), _text(raw, "FromPower")
        return ("power_defected", {"power": new, "old": old}) if new and old else None
    if event == "PowerplayMerits":
        if _whole(raw.get("MeritsGained")) <= 0:
            return None
        return "power_merits", {"merits": f"{_whole(raw.get('MeritsGained')):,}", "total": f"{_whole(raw.get('TotalMerits')):,}"}
    if event == "PowerplaySalary":
        power = _text(raw, "Power")
        return ("power_salary", {"credits": credits(raw.get("Amount")), "power": power}) if power and _whole(raw.get("Amount")) else None
    if event in ("BuySuit", "BuyWeapon"):
        item = _text(raw, "Name_Localised", "Name")
        return (("suit_bought", {"suit": item}) if event == "BuySuit" else ("weapon_bought", {"weapon": item})) if item else None
    if event in ("UpgradeSuit", "UpgradeWeapon"):
        item = _text(raw, "Name_Localised", "Name")
        return ("kit_upgraded", {"item": item, "grade": str(_whole(raw.get("Class")))}) if item and _whole(raw.get("Class")) else None
    if event == "DropshipDeploy":
        body = _text(raw, "Body")
        return ("dropship_deployed", {"body": body}) if body else None
    if event in ("JoinACrew", "QuitACrew"):
        captain = _text(raw, "Captain")
        return ("multicrew_joined" if event == "JoinACrew" else "multicrew_left", {"captain": captain}) if captain else None
    if event in ("CrewMemberJoins", "CrewMemberQuits"):
        name = _text(raw, "Crew")
        return ("multicrew_member_joined" if event == "CrewMemberJoins" else "multicrew_member_left", {"name": name}) if name else None
    if event in ("CrewHire", "CrewFire"):
        name = _text(raw, "Name")
        return ("npc_hired" if event == "CrewHire" else "npc_fired", {"name": name}) if name else None
    if event == "NpcCrewRank":
        name = _text(raw, "NpcCrewName")
        level = _whole(raw.get("RankCombat"))
        return ("npc_ranked", {"name": name, "rank": COMBAT_RANKS[max(0, min(8, level))]}) if name else None
    if event == "WingInvite":
        name = _text(raw, "Name")
        return ("wing_invite", {"name": name}) if name else None
    if event == "WingLeave":
        return "wing_left", {}
    return None


WATCHER_NORMAL = {topic: lines for group in GROUPS for topic, lines in group.WATCHER_NORMAL.items()}
WATCHER_WEARY = {topic: lines for group in GROUPS for topic, lines in group.WATCHER_WEARY.items()}
PERSONAS = {identity: {"plain": {topic: lines for group in GROUPS for topic, lines in group.PERSONAS[identity]["plain"].items()},
                       "voiced": {topic: lines for group in GROUPS for topic, lines in group.PERSONAS[identity]["voiced"].items()}}
            for identity in ("aster", "axiom", "meridian")}
