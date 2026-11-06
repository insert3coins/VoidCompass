"""The ship's everyday life, which the companions used to let pass (5.7.5):
docking granted or denied, refuelling, switching ships, repairs, being
scanned, signal sources, heat and neutron-cone damage, a carrier jump set or
cancelled, a Powerplay rank, synthesis and screenshots.
"""

IMPORTANCE = {"docking_granted": 1, "docking_denied": 2, "refuelled": 0, "ship_swap": 2, "repaired": 1, "scanned": 1,
              "uss_drop": 1, "heat_damage": 2, "jet_damage": 2, "carrier_jump_set": 2, "carrier_jump_cancelled": 2,
              "powerplay_rank": 2, "synthesis": 1, "screenshot": 0}

_DENIED = {"NoSpace": "no free pad", "TooLarge": "the ship is too large for their pads", "Hostile": "they're hostile to us",
           "Offences": "offences on our record", "Distance": "we're too far out", "ActiveFighter": "a fighter is still out",
           "RestrictedAccess": "access is restricted", "NoReason": "no reason given"}
_SCANS = {"Cargo": "cargo", "Crime": "crime", "Cabin": "cabin", "Data": "data"}
_GRADES = ("Basic", "Standard", "Premium")


def recipe(name):
    """A synthesis recipe as it reads after "synthesised": "a premium FSD injection"."""
    name = str(name or "").strip()
    grade = next((word for word in _GRADES if name.endswith(" " + word)), "")
    base = name[:-len(grade) - 1] if grade else name
    grade = grade.lower()
    words = {"FSD": f"a {grade} FSD injection" if grade else "an FSD injection",
             "Limpet": "limpets", "Mining Rig": "mining rigs", "Fuel": f"{grade} fuel".strip(), "Repair": "a repair",
             "AFM Refill": "AFMU refills", "SRV Ammo Restock": "SRV ammunition", "SRV Repair": "an SRV repair",
             "SRV Refuel": "SRV fuel", "Heat Sink": "heat sinks", "Chaff": "chaff", "Life Support": "life support"}.get(base)
    if words:
        return words
    if base.casefold().endswith("ammo"):
        return "ammunition"
    return name.casefold() or "something useful"


def _readable(raw, *keys):
    for key in keys:
        value = str(raw.get(key) or "").strip()
        if value and not value.startswith("$"):
            return value
    return ""


# 5.7.6: the station's answer to a docking request. Said every time, within
# ANSWER_S of the request, whatever was just said (often your own command).
ANSWERS = frozenset({"docking_granted", "docking_denied", "docking_cancelled", "docking_timeout"})
ANSWER_S = 120.0


def moment(event, raw):
    """(topic, fields) for an everyday moment worth a word, or None."""
    if event == "DockingRequested":
        station = _readable(raw, "StationName_Localised", "StationName")
        return "docking_requested", ({"station": station} if station else {})
    if event == "DockingCancelled":
        return "docking_cancelled", {}
    if event == "DockingTimeout":
        return "docking_timeout", {}
    if event == "DockingGranted":
        pad = raw.get("LandingPad")
        return "docking_granted", ({"pad": str(pad)} if pad else {})
    if event == "DockingDenied":
        reason = _DENIED.get(str(raw.get("Reason") or ""), "no reason given")
        return "docking_denied", {"reason": reason, "Reason": reason[:1].upper() + reason[1:]}
    if event == "RefuelAll":
        try:
            amount = float(raw.get("Amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        return ("refuelled", {}) if amount >= 1 else None  # not the scrap of a tonne after scooping
    if event == "ShipyardSwap":
        ship = _readable(raw, "ShipType_Localised") or str(raw.get("ShipType") or "").replace("_", " ").title()
        return ("ship_swap", {"ship": ship}) if ship else None
    if event == "RepairDrone":
        return "repaired", {}
    if event == "AfmuRepairs":
        module = _readable(raw, "Module_Localised")
        return "repaired", ({"module": module} if module else {})
    if event == "Scanned":
        kind = _SCANS.get(str(raw.get("ScanType") or ""))
        return "scanned", ({"kind": kind} if kind else {})
    if event == "USSDrop":
        signal = _readable(raw, "USSType_Localised").lower()
        return ("uss_drop", {"signal": signal, "Signal": signal[:1].upper() + signal[1:]}) if signal else None
    if event == "HeatDamage":
        return "heat_damage", {}
    if event == "JetConeDamage":
        module = _readable(raw, "Module_Localised")
        return "jet_damage", ({"module": module} if module else {})
    if event == "CarrierJumpRequest":
        system = str(raw.get("SystemName") or "").strip()
        return ("carrier_jump_set", {"system": system}) if system else None
    if event == "CarrierJumpCancelled":
        return "carrier_jump_cancelled", {}
    if event == "PowerplayRank":
        try:
            rank = int(raw.get("Rank") or 0)
        except (TypeError, ValueError):
            rank = 0
        power = str(raw.get("Power") or "").strip()
        return ("powerplay_rank", {"rank": str(rank), "power": power}) if rank > 0 and power else None
    if event == "Synthesis":
        made = recipe(raw.get("Name"))
        return "synthesis", {"recipe": made, "Recipe": made[:1].upper() + made[1:]}
    if event == "Screenshot":
        system = str(raw.get("System") or "").strip()
        return "screenshot", ({"system": system} if system else {})
    return None


# Fields: {pad}, {reason} / {Reason} (sentence start), {ship}, {module}, {kind} (a
# scan: cargo, crime, cabin, data), {signal} / {Signal}, {system}, {power}, {rank},
# {recipe} / {Recipe} (reads after "synthesised" / sentence start).
WATCHER_NORMAL = {
    "docking_granted": ("Pad {pad}. In we go.", "Docking granted. Pad {pad}.", "They'll have us. Pad {pad}.", "Pad {pad}. Gently.",
                        "Cleared to land on pad {pad}.", "We're expected. Pad {pad}.", "Pad {pad}. Mind the toaster.",
                        "Docking granted.", "Cleared. Find pad {pad}.", "Pad {pad} is ours."),
    "docking_denied": ("Docking denied: {reason}.", "They won't have us. {Reason}, they say.", "Denied. Apparently {reason}.",
                       "No docking: {reason}.", "Turned away: {reason}.", "They said no. {Reason}.", "Denied: {reason}. Try again.",
                       "No berth for us: {reason}.", "Refused: {reason}.", "Docking refused. {Reason}."),
    "refuelled": ("Tanks full.", "Refuelled.", "Full tank. Good.", "That's the fuel sorted.", "Bought a full tank.", "Fuel's full again.",
                  "Refuelled. One less worry.", "Full of fuel. Ready.", "Tanks topped.", "Fuel bought. Tanks full."),
    "ship_swap": ("The {ship}. I like this one.", "New ship: the {ship}.", "Into the {ship}. Let's see how she flies.",
                  "The {ship}, then.", "We're in the {ship} now.", "Swapped to the {ship}. Same me, different hull.",
                  "The {ship}. Make yourself at home.", "{ship}. A change of scenery.", "The {ship}'s ours for now.",
                  "The {ship}. I'll learn its creaks."),
    "repaired": ("Repairs done.", "Patched up.", "That's better. Repaired.", "The {module}'s repaired.", "Repaired. Good as new. Nearly.",
                 "Fixed.", "{module}, mended.", "Hull patched.", "Repairs finished.", "All patched up."),
    "scanned": ("We're being scanned.", "Someone's scanning us.", "A {kind} scan. Hold still.", "They're running a {kind} scan.",
                "Scanned. Nothing to hide, I hope.", "Someone's having a look at us.", "{kind} scan. Let them look.",
                "We've been scanned.", "Being scanned. Stay calm.", "A scan. Smile."),
    "uss_drop": ("Dropping into {signal}.", "A signal: {signal}.", "{Signal}. Let's see.", "Into the {signal}.",
                 "Signal source: {signal}.", "{Signal}. Careful.", "Down into {signal}.", "Here's the {signal}.",
                 "{Signal}. Could be anything.", "We're at the {signal}."),
    "heat_damage": ("We're cooking. Heat damage.", "Too hot. Modules are burning.", "Heat damage! Cool down.",
                    "It's taking heat damage.", "Overheating. Back off.", "Heat's hurting the ship.", "Cool her down. Now.",
                    "Burning up. Heat damage.", "Heat damage. Get out of there.", "Too much heat."),
    "jet_damage": ("The cone's hurting us. {module} damaged.", "Jet cone damage. Careful.", "{module} took a hit from the cone.",
                   "The neutron jet's chewing the ship.", "Cone damage. Get clear.", "{module}, damaged. That cone bites.",
                   "Careful in the cone.", "Jet damage to the {module}.", "The cone's rough today.", "Mind the jet. Damage."),
    "carrier_jump_set": ("The carrier's jumping to {system}.", "Carrier jump set for {system}.", "We're off to {system}. By carrier.",
                         "Carrier's going to {system}.", "Jump booked: {system}.", "{system}, by carrier. Nice.",
                         "The carrier will take us to {system}.", "Carrier jump scheduled: {system}.",
                         "Next stop, {system}. The big ship's taking us.", "Carrier heading for {system}."),
    "carrier_jump_cancelled": ("Carrier jump cancelled.", "The carrier's staying put.", "Jump called off.", "No carrier jump after all.",
                               "Cancelled. We stay.", "The carrier won't jump.", "Carrier jump off.", "Staying here then.",
                               "Jump cancelled.", "Change of plans. No jump."),
    "powerplay_rank": ("Rank {rank} with {power}.", "{power} promoted you. Rank {rank}.", "Rank {rank}. {power} noticed.",
                       "New rank with {power}: {rank}.", "{power} rank {rank}. Well done.", "You're rank {rank} now.",
                       "Rank {rank} for {power}.", "{power} likes you. Rank {rank}.", "Up to rank {rank}.", "Promoted. {power}, rank {rank}."),
    "synthesis": ("Synthesised {recipe}.", "Made {recipe}.", "{Recipe}, synthesised.", "Synthesis done: {recipe}.",
                  "There's {recipe}.", "Cooked up {recipe}.", "{Recipe}. From scraps.", "Synthesised. {Recipe}.",
                  "Made {recipe} out of rocks.", "{Recipe} ready."),
    "screenshot": ("Nice picture.", "Got it. A postcard?", "Snap.", "Good shot.", "Keep that one.", "I'll remember that view.",
                   "Lovely. {system} in a picture.", "Picture taken.", "That's a keeper.", "Captured."),
}

WATCHER_WEARY = {
    "docking_granted": ("Pad {pad}. Try not to hit the walls.", "They'll have us. Surprising.", "Pad {pad}. Fine.", "Docking granted. For once.",
                        "Pad {pad}. Again.", "Cleared. Pad {pad}. Don't scrape.", "Pad {pad}. I've seen better pads.",
                        "They let us in. Pad {pad}.", "Granted. Pad {pad}.", "Pad {pad}. Lovely."),
    "docking_denied": ("Denied: {reason}. Typical.", "They don't want us. {Reason}.", "No. {Reason}. I'm used to it.",
                       "Turned away: {reason}.", "Docking denied. {Reason}. Of course.", "Refused: {reason}.",
                       "They said no: {reason}.", "Denied. {Reason}. We'll live.", "Not today: {reason}.", "{Reason}. Denied. Fine."),
    "refuelled": ("Tanks full. For now.", "Refuelled. Until next time.", "Fuel. Bought. Again.", "Full tank. It won't last.",
                  "Topped up.", "Refuelled.", "Tanks full. Lovely.", "Fuel sorted.", "Full again. We'll empty it.", "Refuelled. Fine."),
    "ship_swap": ("The {ship}. Different hull, same me.", "The {ship} now. I'll get used to it.", "Swapped. The {ship}. Hm.",
                  "The {ship}. Fine.", "New ship: the {ship}. Same old me.", "The {ship}. Smells different.",
                  "Into the {ship}. I'll learn its creaks.", "The {ship}. I'd miss the old one if I could.", "The {ship}. Alright.",
                  "{ship}. Another hull to haunt."),
    "repaired": ("Patched up. For now.", "Repairs done. Until the next time.", "Fixed. Mostly.", "{module}, repaired. Lucky.",
                 "Repaired. Don't break it again.", "Patched.", "{module} mended. Nothing stays mended.", "Hull patched.",
                 "Repairs done.", "All patched up. For now."),
    "scanned": ("Someone's scanning us. Let them.", "A {kind} scan. How rude.", "Scanned. Again.", "They're looking at us. Fine.",
                "{kind} scan. Nothing to see.", "Being scanned. I'm used to being looked at.", "Scanned.", "Someone's nosy.",
                "A scan. Smile, I suppose.", "They're scanning. Of course they are."),
    "uss_drop": ("{Signal}. Probably nothing.", "Dropping into {signal}. Here we go.", "{Signal}. It's always something.",
                 "A signal: {signal}. Hm.", "{Signal}. Careful.", "Into the {signal}.", "{Signal}. Don't get your hopes up.",
                 "Signal source: {signal}.", "{Signal}. Fine.", "Here's {signal}."),
    "heat_damage": ("We're burning. Lovely.", "Heat damage. Of course.", "Too hot. Things are melting.", "Overheating. Again.",
                    "Heat damage. Cool down, please.", "Cooking. Not ideal.", "We're on fire. Figuratively. For now.",
                    "Heat's hurting us.", "Burning up.", "Heat damage. Get out."),
    "jet_damage": ("The cone bites. {module} damaged.", "Jet damage. I did warn you. I think.", "{module} hurt by the cone. Lovely.",
                   "The neutron jet's chewing us.", "Cone damage. Of course.", "Careful. The cone.", "{module}, damaged. Thanks, cone.",
                   "Jet cone damage.", "The cone's angry today.", "Mind the jet."),
    "carrier_jump_set": ("The carrier's off to {system}. We go too, I suppose.", "Carrier jump: {system}.", "{system}. By carrier. Fine.",
                         "We're moving the whole house to {system}.", "Carrier booked for {system}.", "{system}. Off we go. Slowly.",
                         "The big ship's jumping to {system}.", "Carrier to {system}. Hm.", "Next: {system}.", "Carrier heading for {system}."),
    "carrier_jump_cancelled": ("Cancelled. Of course.", "The carrier's staying. So are we.", "No jump. Fine.", "Jump called off.",
                               "Never mind, then.", "Carrier jump cancelled.", "We stay. Lovely.", "No carrier jump.",
                               "Cancelled. I wasn't packed anyway.", "Change of plans."),
    "powerplay_rank": ("Rank {rank} with {power}. They'll never thank you. I will.", "{power}, rank {rank}. Congratulations, I suppose.",
                       "Rank {rank}. {power} noticed you.", "Promoted by {power}. Rank {rank}.", "{power} rank {rank}. Hm.",
                       "Rank {rank} now.", "You're rank {rank} with {power}.", "{power} gave you rank {rank}.", "Up a rank: {rank}.",
                       "Rank {rank}. Loyal, aren't you."),
    "synthesis": ("Synthesised {recipe}. From rocks. Impressive, in a sad way.", "Made {recipe}.", "{Recipe}. Out of scraps.",
                  "Synthesis: {recipe}.", "There's {recipe}.", "{Recipe}, synthesised.", "Cooked up {recipe}. Lovely.",
                  "{Recipe}. From nothing, nearly.", "Made {recipe}. Fine.", "{Recipe} ready."),
    "screenshot": ("A picture. I'll be in it, somewhere.", "Snap. Another memory.", "Picture taken.", "You'll want that one.",
                   "A postcard, maybe.", "Got it.", "{system}, in a picture. Lovely.", "Captured. Like me.", "A keeper, I suppose.",
                   "Picture. Fine."),
}

PERSONAS = {
    "aster": {
        "plain": {
            "docking_granted": ("Docking granted. Pad {pad}.", "Pad {pad} assigned.", "Cleared to dock.", "Pad {pad}, Commander."),
            "docking_denied": ("Docking denied: {reason}.", "Request refused: {reason}.", "Denied. {Reason}.", "No docking: {reason}."),
            "refuelled": ("Refuelled.", "Tanks full.", "Fuel replenished.", "Refuelling complete."),
            "ship_swap": ("Now aboard the {ship}.", "Ship changed: {ship}.", "The {ship} is ready.", "Transferred to the {ship}."),
            "repaired": ("Repairs complete.", "Repaired.", "{module} repaired.", "Hull repaired."),
            "scanned": ("We are being scanned.", "Scan detected.", "{kind} scan in progress.", "Ship scanned."),
            "uss_drop": ("Signal source: {signal}.", "Dropping into {signal}.", "{Signal}.", "Arrived at {signal}."),
            "heat_damage": ("Heat damage.", "Modules overheating.", "Heat damage. Cool down.", "Taking heat damage."),
            "jet_damage": ("Jet cone damage.", "{module} damaged.", "Cone damage.", "{module} hit by the jet."),
            "carrier_jump_set": ("Carrier jump set: {system}.", "Carrier to {system}.", "Jump scheduled for {system}.", "Carrier bound for {system}."),
            "carrier_jump_cancelled": ("Carrier jump cancelled.", "Jump cancelled.", "The carrier remains.", "Carrier holding."),
            "powerplay_rank": ("{power}: rank {rank}.", "Rank {rank} with {power}.", "Powerplay rank {rank}.", "Promoted: {power}, rank {rank}."),
            "synthesis": ("Synthesised {recipe}.", "Synthesis: {recipe}.", "{Recipe} produced.", "Made {recipe}."),
            "screenshot": ("Image captured.", "Screenshot taken.", "Picture recorded.", "Captured: {system}."),
        },
        "voiced": {
            "docking_granted": ("Pad {pad}, Commander. Do try to arrive in the same order as the ship.",
                                "Docking granted. Pad {pad}. The paperwork, for once, was swift.",
                                "Cleared for pad {pad}. I shall enter our arrival in advance.",
                                "Pad {pad}. A respectable berth.", "Docking granted. Please mind the paintwork."),
            "docking_denied": ("Docking denied: {reason}. I have lodged a mental complaint.",
                               "They refuse us. {Reason}, they say. I shall note it in the register.",
                               "Request denied: {reason}. We may try again with improved manners.",
                               "Refused, Commander. {Reason}. Most irregular.", "No docking: {reason}. The station's loss."),
            "refuelled": ("Tanks full. The fuel column is restored to respectability.", "Refuelled, Commander. A sound investment.",
                          "Fuel replenished. I always sleep better, metaphorically.", "Tanks full. The ledger notes the expense, and approves.",
                          "Refuelling complete. Range restored."),
            "ship_swap": ("Now aboard the {ship}. I shall update the crew register.", "The {ship}, Commander. I trust she suits the errand.",
                          "Transferred to the {ship}. Same officer, new quarters.", "The {ship}. I shall learn her habits promptly.",
                          "A change of ship: the {ship}. Duly logged."),
            "repaired": ("Repairs complete. The damage report has been happily retired.", "{module} restored, Commander. Good as new, or near enough.",
                         "Repaired. I prefer the ship in one piece.", "Hull patched. The maintenance log thanks you.",
                         "Repairs done. I have struck the matter from the log."),
            "scanned": ("We are being scanned, Commander. I suggest an air of innocence.", "A {kind} scan. Our paperwork is in order. I checked.",
                        "Someone is scanning us. I shall remain composed.", "Scan detected. Nothing in the hold requires an explanation, I trust.",
                        "Being scanned. Smile, Commander, figuratively."),
            "uss_drop": ("{Signal}. I shall reserve judgement until I see it.", "Dropping into {signal}. Proceed with suitable caution.",
                         "Signal source: {signal}. The log is open.", "{Signal}, Commander. Possibly profitable, possibly not.",
                         "Arrived at {signal}. Eyes open."),
            "heat_damage": ("Heat damage, Commander. The modules object strongly.", "We are overheating. I recommend a cooler approach.",
                            "Heat damage. The repair column is growing.", "Too hot, Commander. Please withdraw.",
                            "Modules overheating. This is not sustainable."),
            "jet_damage": ("Jet cone damage. The {module} is unhappy.", "The neutron jet is not gentle, Commander. Damage logged.",
                           "Cone damage to the {module}. Supercharging has a price.", "We are taking damage from the jet. Clear the cone.",
                           "{module} damaged by the cone. Noted, regretfully."),
            "carrier_jump_set": ("Carrier jump set for {system}. I shall pack, figuratively.", "The carrier departs for {system}. Itinerary updated.",
                                 "Bound for {system} by carrier. A civilised way to travel.", "Jump scheduled: {system}. The whole household moves.",
                                 "Carrier to {system}, Commander. Duly entered."),
            "carrier_jump_cancelled": ("Carrier jump cancelled. I have unpacked, figuratively.", "The jump is off, Commander. The itinerary is amended.",
                                       "Cancelled. The carrier stays where it is.", "No carrier jump. I shall strike it from the schedule.",
                                       "Jump cancelled. A change of plan, duly noted."),
            "powerplay_rank": ("Rank {rank} with {power}. A considerable recognition.", "{power} has promoted you to rank {rank}. Congratulations.",
                               "Powerplay rank {rank}, Commander. The register is suitably impressed.",
                               "Rank {rank}. {power} appreciates loyalty, and so do I.", "Promoted within {power}. Rank {rank}, logged."),
            "synthesis": ("Synthesised {recipe}. Resourceful, Commander.", "{Recipe}, made from materials. Admirable thrift.",
                          "Synthesis complete: {recipe}. The materials store contributes.", "We now have {recipe}. Self-sufficiency becomes you.",
                          "Made {recipe}. I have adjusted the inventory."),
            "screenshot": ("A picture, Commander. For the album, I presume.", "Captured. A view worth keeping.",
                           "Image recorded. I shall file it under scenery.", "Screenshot taken in {system}. A fine composition.",
                           "A postcard in the making, perhaps."),
        },
    },
    "axiom": {
        "plain": {
            "docking_granted": ("Pad {pad}.", "Docking granted.", "Cleared: pad {pad}.", "Pad {pad} assigned."),
            "docking_denied": ("Denied: {reason}.", "Docking refused: {reason}.", "No docking. {Reason}.", "Request denied."),
            "refuelled": ("Refuelled.", "Tanks full.", "Fuel: 100%.", "Refuel complete."),
            "ship_swap": ("Ship: {ship}.", "Now in the {ship}.", "Swapped to the {ship}.", "Active ship: {ship}."),
            "repaired": ("Repaired.", "{module} repaired.", "Repairs complete.", "Hull restored."),
            "scanned": ("Scanned.", "Incoming scan.", "{kind} scan.", "Being scanned."),
            "uss_drop": ("Signal: {signal}.", "{Signal}.", "Dropping into {signal}.", "Signal source reached."),
            "heat_damage": ("Heat damage.", "Overheating.", "Heat damage detected.", "Modules overheating."),
            "jet_damage": ("Cone damage.", "{module} damaged.", "Jet damage.", "Neutron jet damage."),
            "carrier_jump_set": ("Carrier jump: {system}.", "Carrier to {system}.", "Jump set: {system}.", "Destination: {system}."),
            "carrier_jump_cancelled": ("Carrier jump cancelled.", "Jump cancelled.", "Carrier staying.", "No jump."),
            "powerplay_rank": ("{power}: rank {rank}.", "Rank {rank}.", "Powerplay rank {rank}.", "{power} rank {rank}."),
            "synthesis": ("Synthesised: {recipe}.", "{Recipe} made.", "Synthesis: {recipe}.", "Produced {recipe}."),
            "screenshot": ("Image captured.", "Screenshot.", "Picture taken.", "Captured: {system}."),
        },
        "voiced": {
            "docking_granted": ("Pad {pad}. I have calculated the approach. It is straightforward. Probably.",
                                "Docking granted. Pad {pad}. I like a numbered destination.",
                                "Cleared for pad {pad}. The station's pads are numbered. I approve of numbering.",
                                "Pad {pad}. Shall I count the other ships? I am counting the other ships.",
                                "Docking granted. Arrival probability: very high."),
            "docking_denied": ("Docking denied: {reason}. I did not predict that.", "Refused. {Reason}. I have logged the rejection.",
                               "No docking: {reason}. An inconvenient result.", "Denied, because {reason}. We could try again.",
                               "Request refused: {reason}. Recalculating."),
            "refuelled": ("Tanks full. Range restored to maximum. I like maximums.", "Refuelled. Fuel is the one number I want at 100%.",
                          "Fuel replenished. The margin is excellent.", "Tanks full. I have recalculated our range. It is good.",
                          "Refuel complete. Ready for a long sequence of jumps."),
            "ship_swap": ("We are in the {ship}. New sensors. I am delighted.", "The {ship}. Different instruments, same curiosity.",
                          "Swapped to the {ship}. I have catalogued its modules already.", "Active ship: the {ship}. Recalibrating.",
                          "The {ship}. A new platform for observation."),
            "repaired": ("Repairs complete. Integrity restored. I like integrity.", "{module} repaired. All readings nominal again.",
                         "Repaired. The damage data is now historical.", "Hull restored. Structural numbers are pleasing.",
                         "Repairs done. Systems green."),
            "scanned": ("We are being scanned. I am scanning them back, quietly.", "A {kind} scan. Nothing to find. I checked first.",
                        "Incoming scan. They are curious too.", "Scanned. Fair: I scan everything.",
                        "Someone is collecting data on us. I sympathise."),
            "uss_drop": ("{Signal}. Unknown contents. My favourite kind.", "Dropping into {signal}. Sensors ready.",
                         "Signal source: {signal}. Probability of something interesting: moderate.",
                         "{Signal}. I would like to know what made it.", "Arrived at {signal}. Observing."),
            "heat_damage": ("Heat damage. Temperature is well outside comfortable parameters.", "Overheating. Please reduce the temperature.",
                            "Modules taking heat damage. The trend is negative.", "Too hot. My sensors are complaining.",
                            "Heat damage detected. I recommend cooling. Immediately."),
            "jet_damage": ("Jet cone damage. The {module} has been hit.", "The neutron jet is damaging us. Fascinating, and bad.",
                           "{module} damaged by the cone. The boost has a cost.", "Cone damage. Please exit the jet.",
                           "Neutron jet damage. I logged the intensity. It was high."),
            "carrier_jump_set": ("Carrier jump set for {system}. A very large object about to move very far.",
                                 "The carrier is going to {system}. I like watching big things travel.",
                                 "Destination: {system}. Carrier jump scheduled.", "Bound for {system}. New skies, by carrier.",
                                 "Carrier to {system}. I have started a page for it."),
            "carrier_jump_cancelled": ("Carrier jump cancelled. The page I started will wait.", "Jump cancelled. The carrier remains.",
                                       "No jump. Revised plan noted.", "Cancelled. The coordinates stay the same.",
                                       "Carrier staying. I will observe here instead."),
            "powerplay_rank": ("Rank {rank} with {power}. Your influence curve is upward.", "{power}: rank {rank}. Congratulations.",
                               "Powerplay rank {rank}. Recorded with interest.", "Promoted within {power}. Rank {rank}.",
                               "{power} rank {rank}. The data on your loyalty is clear."),
            "synthesis": ("Synthesised {recipe}. Materials in, useful things out. Elegant.", "{Recipe}, made. I love a good recipe.",
                          "Synthesis complete: {recipe}. Efficient.", "We made {recipe} from raw materials. Remarkable.",
                          "{Recipe}. Produced on demand."),
            "screenshot": ("Image captured. Another data point, visual.", "A picture of {system}. Excellent composition.",
                           "Screenshot taken. I have filed it with the observations.", "Captured. A postcard, perhaps.",
                           "Picture recorded. I like pictures. They are data that looks nice."),
        },
    },
    "meridian": {
        "plain": {
            "docking_granted": ("Pad {pad}.", "Docking granted.", "Cleared for pad {pad}.", "Berth {pad}."),
            "docking_denied": ("Denied: {reason}.", "No berth: {reason}.", "Docking refused. {Reason}.", "Turned away."),
            "refuelled": ("Tanks full.", "Refuelled.", "Fuel aboard.", "Full tank."),
            "ship_swap": ("Aboard the {ship}.", "Ship: {ship}.", "The {ship}.", "Now in the {ship}."),
            "repaired": ("Repaired.", "{module} mended.", "Repairs done.", "Hull patched."),
            "scanned": ("Being scanned.", "Scanned.", "{kind} scan.", "Someone's scanning us."),
            "uss_drop": ("{Signal}.", "Signal: {signal}.", "Into {signal}.", "Signal reached."),
            "heat_damage": ("Heat damage.", "Overheating.", "Too hot.", "Heat damage. Cool down."),
            "jet_damage": ("Cone damage.", "{module} damaged.", "Jet damage.", "The cone's hurting us."),
            "carrier_jump_set": ("Carrier to {system}.", "Carrier jump: {system}.", "Bound for {system}.", "Jump set: {system}."),
            "carrier_jump_cancelled": ("Jump cancelled.", "Carrier staying.", "No jump.", "Carrier jump off."),
            "powerplay_rank": ("{power}: rank {rank}.", "Rank {rank}.", "Promoted: rank {rank}.", "{power} rank {rank}."),
            "synthesis": ("Made {recipe}.", "Synthesised {recipe}.", "{Recipe}, made.", "Synthesis: {recipe}."),
            "screenshot": ("Picture taken.", "Captured.", "Snapshot.", "Captured: {system}."),
        },
        "voiced": {
            "docking_granted": ("Berth {pad}, Commander. Bring her in gently.", "Docking granted. Pad {pad}. A fair harbour.",
                                "Cleared for pad {pad}. Mind the slot.", "Pad {pad}. Make her fast when you're down.",
                                "They'll have us. Pad {pad}."),
            "docking_denied": ("No berth for us: {reason}. We'll find another harbour.", "Turned away, Commander. {Reason}.",
                               "Docking denied: {reason}. A pity.", "They've closed the harbour to us: {reason}.",
                               "Refused: {reason}. Stand off and try again, perhaps."),
            "refuelled": ("Tanks full, Commander. A navigator's comfort.", "Refuelled. A good margin restored.",
                          "Fuel aboard. Now we can choose any course we like.", "Full tanks. Fair sailing ahead.",
                          "Refuelled. I always breathe easier."),
            "ship_swap": ("Aboard the {ship}, Commander. A fine vessel.", "The {ship}. I'll learn her ways quickly.",
                          "A new deck under us: the {ship}.", "The {ship}. Let's see how she handles.",
                          "Shipped aboard the {ship}. Same navigator, new hull."),
            "repaired": ("Repairs done. She's seaworthy again.", "{module} mended, Commander.", "Patched up. A sound ship once more.",
                         "Hull repaired. Good as new, or near enough.", "Repairs finished. Fair winds."),
            "scanned": ("We're being scanned, Commander. Let them look.", "A {kind} scan. Nothing to hide aboard this ship.",
                        "Someone's taking our measure.", "Scanned. Hold your course.", "They're scanning us. Stay steady."),
            "uss_drop": ("{Signal}. Let's see what the sea's brought us.", "Dropping into {signal}. Weather eye open.",
                         "A signal source: {signal}.", "{Signal}, Commander. Careful approach.", "Arrived at {signal}."),
            "heat_damage": ("Heat damage, Commander. She's running too hot.", "We're overheating. Ease off.",
                            "Too hot by far. Modules are suffering.", "Heat damage. Cool her down.", "She's burning, Commander. Back away."),
            "jet_damage": ("The cone's chewing the {module}, Commander.", "Jet damage. Rough water, that cone.",
                           "{module} damaged by the jet. Get clear.", "Neutron jet's taking its toll.", "Cone damage. Steer out of it."),
            "carrier_jump_set": ("The carrier sails for {system}. A whole harbour, moving.", "Carrier jump set: {system}. I've marked the chart.",
                                 "Bound for {system} by carrier. Fair winds.", "We're off to {system}, the whole fleet of us.",
                                 "Carrier to {system}, Commander."),
            "carrier_jump_cancelled": ("Jump cancelled. The carrier holds her anchorage.", "The carrier stays at anchor.",
                                       "No jump after all, Commander.", "Cancelled. We hold station.", "Carrier jump off. Steady as we are."),
            "powerplay_rank": ("Rank {rank} with {power}. You fly their colours well.", "{power} has promoted you: rank {rank}.",
                               "Powerplay rank {rank}, Commander. Well earned.", "Rank {rank} for {power}. A loyal hand.",
                               "{power}, rank {rank}. The fleet would have rung the bell."),
            "synthesis": ("Made {recipe}, Commander. A sailor's thrift.", "{Recipe}, from the stores. Resourceful.",
                          "Synthesised {recipe}. Waste not, want not.", "{Recipe} made. Good seamanship, that.",
                          "We've made {recipe}. Handy."),
            "screenshot": ("A picture, Commander. Worth keeping.", "Captured. A fine view.", "Snapshot taken in {system}. A good memory.",
                           "A postcard for the log, perhaps.", "That's a view to remember."),
        },
    },
}


def persona_banks(identity):
    banks = PERSONAS[identity]
    return banks["plain"], banks["voiced"]


# 5.7.6: the docking request, and the station cancelling or timing it out.
from voidcompass.overlays import docking_talk as _docking  # noqa: E402

IMPORTANCE.update(_docking.IMPORTANCE)
WATCHER_NORMAL.update(_docking.WATCHER_NORMAL)
WATCHER_WEARY.update(_docking.WATCHER_WEARY)
for _identity, _banks in _docking.PERSONAS.items():
    PERSONAS[_identity]["plain"].update(_banks["plain"])
    PERSONAS[_identity]["voiced"].update(_banks["voiced"])

# 5.7.6: the rest of the journal worth a word (life_events), as everyday life.
from voidcompass.overlays import life_events as _life_more  # noqa: E402

IMPORTANCE.update(_life_more.IMPORTANCE)
WATCHER_NORMAL.update(_life_more.WATCHER_NORMAL)
WATCHER_WEARY.update(_life_more.WATCHER_WEARY)
for _identity, _banks in _life_more.PERSONAS.items():
    PERSONAS[_identity]["plain"].update(_banks["plain"])
    PERSONAS[_identity]["voiced"].update(_banks["voiced"])
_own_moment = moment


def moment(event, raw):  # noqa: F811
    """(topic, fields) for an everyday moment worth a word, or None."""
    return _own_moment(event, raw) or _life_more.moment(event, raw)
