"""Mining in a ring, followed (5.7.5).

The journal says when you drop into a ring, what a mapped ring's hotspots
are, what each prospector finds, every tonne the refinery makes and when you
leave. MiningTrip turns that into moments worth a word: arriving, hotspots,
a poor or mined-out rock, tonnage milestones, a half-full hold, limpets
running low, and a summary of the haul as you go.
"""
from collections import Counter

IMPORTANCE = {"ring_arrival": 1, "ring_hotspots": 2, "prospected_poor": 0, "prospected_depleted": 0, "mining_tally": 1,
              "hold_half_mining": 1, "limpets_low": 2, "mining_summary": 2}
# Said later if they can't be said at once (they often land in a burst).
QUEUED = {"ring_hotspots", "mining_summary"}
TALLY_MARKS = (10, 25, 50, 100, 150, 200, 300, 400, 500, 750, 1000)
POOR_PCT = 10.0
LIMPETS_LOW = 2


def _count(number, one, many):
    return one if number == 1 else f"{number} {many}"


def _join(parts):
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _name(raw, *keys):
    for key in keys:
        value = str(raw.get(key) or "").strip()
        if value and not value.startswith("$"):
            return value
    raw_name = str(raw.get(keys[-1]) or "").strip("$;").replace("_name", "").replace("_", " ")
    return raw_name[:1].upper() + raw_name[1:]


class MiningTrip:
    """One visit to a ring, from dropping in until you leave."""

    def __init__(self):
        self.hotspots = {}   # ring name -> "2 Platinum and 1 Painite"
        self.reset()

    def reset(self):
        self.ring = ""
        self.refined = Counter()
        self.marks = set()
        self.half_said = False
        self.limpets_said = False

    @property
    def active(self):
        return bool(self.ring)

    def summary(self):
        total = sum(self.refined.values())
        if not total:
            return ""
        if len(self.refined) == 1:
            material = next(iter(self.refined))
            return f"{_count(total, 'One tonne', 'tonnes')} of {material}."
        parts = [f"{count} {material}" for material, count in self.refined.most_common()]
        return f"{total} tonnes refined: {_join(parts)}."

    def observe(self, event, raw, srv=False, capacity=0, limpets=None):
        """(topic, fields) for a moment worth a word, or None."""
        if event == "SAASignalsFound" and str(raw.get("BodyName") or "").endswith(" Ring"):
            found = Counter()
            for signal in raw.get("Signals") or ():
                if isinstance(signal, dict) and "$SAA_SignalType" not in str(signal.get("Type") or ""):
                    found[_name(signal, "Type_Localised", "Type")] += int(signal.get("Count") or 0)
            if found:
                spots = _join([f"{count} {name}" for name, count in found.most_common()])
                self.hotspots[str(raw["BodyName"])] = spots
                return "ring_hotspots", {"ring": str(raw["BodyName"]), "hotspots": spots}
            return None
        if event == "SupercruiseExit" and str(raw.get("BodyType") or "") == "PlanetaryRing":
            self.reset()
            self.ring = str(raw.get("Body") or "the ring")
            spots = self.hotspots.get(self.ring)
            return "ring_arrival", {"ring": self.ring, **({"hotspots": spots} if spots else {})}
        if event in {"SupercruiseEntry", "FSDJump", "Docked", "Shutdown"} and self.active:
            haul, ring = self.summary(), self.ring
            self.reset()
            return ("mining_summary", {"summary": haul, "ring": ring}) if haul else None
        if not self.active:
            return None
        if event == "MiningRefined" and not srv:
            material = _name(raw, "Type_Localised", "Type")
            self.refined[material] += 1
            total = sum(self.refined.values())
            mark = next((value for value in TALLY_MARKS if total >= value and value not in self.marks), None)
            if mark:
                self.marks.update(value for value in TALLY_MARKS if value <= total)
                top = self.refined.most_common(1)[0][0]
                return "mining_tally", {"tonnes": str(total), "material": top}
            return None
        if event == "ProspectedAsteroid":
            if raw.get("MotherlodeMaterial"):
                return None  # the motherlode has its own words
            try:
                remaining = float(raw.get("Remaining", 100))
            except (TypeError, ValueError):
                remaining = 100.0
            if remaining <= 0:
                return "prospected_depleted", {}
            shares = [float(row.get("Proportion") or 0) for row in raw.get("Materials") or () if isinstance(row, dict)]
            if not shares or max(shares) < POOR_PCT:
                return "prospected_poor", {}
            return None
        if event == "Cargo" and str(raw.get("Vessel") or "Ship").casefold() == "ship" and capacity:
            try:
                tons = int(raw.get("Count") or 0)
            except (TypeError, ValueError):
                return None
            if not self.half_said and capacity // 2 <= tons < capacity and sum(self.refined.values()):
                self.half_said = True
                return "hold_half_mining", {"tonnes": str(tons), "capacity": str(capacity)}
            return None
        if event == "LaunchDrone" and limpets is not None and not self.limpets_said and limpets <= LIMPETS_LOW:
            self.limpets_said = True
            return "limpets_low", {"count": str(max(0, limpets))}
        return None


# Fields: {ring}, {hotspots} ("2 Platinum and 1 Painite"), {tonnes}, {material},
# {capacity}, {count} (limpets left), {summary} (a sentence ending in a full stop).
WATCHER_NORMAL = {
    "ring_arrival": ("{ring}. Let's see what's in the rocks.", "In the ring. Prospectors ready?", "{ring}. Good hunting.",
                     "Dropped into {ring}. All that rock.", "{ring}. Mind the asteroids.", "Into the ring. Somewhere in here is a fortune.",
                     "{ring}, with its {hotspots} hotspots. Pick one.", "The ring, and its {hotspots} hotspots.", "{ring}. Time to dig.",
                     "{ring}. Every rock's a question."),
    "ring_hotspots": ("{ring}: {hotspots} hotspots.", "Hotspots in {ring}: {hotspots}.", "{ring} has {hotspots} hotspots.",
                      "The ring's mapped. {hotspots} hotspots.", "{hotspots} hotspots in {ring}. Worth a visit.",
                      "Found them: {hotspots} hotspots in {ring}.", "{ring}. Hotspots: {hotspots}.",
                      "Mapped {ring}. {hotspots} hotspots.", "{hotspots} hotspots. That's a good ring.",
                      "{ring} lights up: {hotspots} hotspots."),
    "prospected_poor": ("Nothing in that one.", "Poor rock. Next.", "Not worth the charges.", "Empty, more or less.",
                        "That one's not worth it.", "Move on. Poor rock.", "Barely anything there.", "Skip it.",
                        "Low content. Leave it.", "Another dud."),
    "prospected_depleted": ("Already mined out.", "Someone got there first.", "That one's empty. Mined out.",
                            "Depleted. Nothing left.", "Picked clean.", "Mined out. Move on.", "Nothing left in that one.",
                            "Already done. Not by us.", "Empty rock.", "Exhausted."),
    "mining_tally": ("{tonnes} tonnes so far. Mostly {material}.", "{tonnes} tonnes refined.", "That's {tonnes} tonnes.",
                     "{tonnes} tonnes. The hold's filling.", "{tonnes} tonnes, mostly {material}. Good work.",
                     "We're at {tonnes} tonnes.", "{tonnes} tonnes of ore. Keep going.", "{tonnes} tonnes. {material} leads.",
                     "Tally: {tonnes} tonnes.", "{tonnes} tonnes refined. Not bad."),
    "hold_half_mining": ("Hold's half full. {tonnes} of {capacity}.", "Halfway: {tonnes} tonnes.", "{tonnes} of {capacity}. Half full.",
                         "Half a hold. Keep at it.", "The hold's half full.", "{tonnes} tonnes aboard. Halfway.",
                         "Halfway to a full hold.", "Half full. Good pace.", "{tonnes} tonnes. Half the hold.",
                         "Half the hold's ore now."),
    "limpets_low": ("{count} limpets left.", "Running low on limpets. {count} left.", "Limpets: {count}. Careful.",
                    "Only {count} limpets left.", "We're nearly out of limpets.", "{count} limpets. Not many.",
                    "Watch the limpets. {count} left.", "Limpets low: {count}.", "{count} limpets to go.",
                    "Down to {count} limpets."),
    "mining_summary": ("Done with the ring. {summary}", "That's the haul. {summary}", "Leaving the ring. {summary}",
                       "{summary} Good mining.", "Out of the ring. {summary}", "The haul. {summary}",
                       "{summary} Worth it.", "Mining done. {summary}", "{summary} Let's sell it.", "Away from the rocks. {summary}"),
}

WATCHER_WEARY = {
    "ring_arrival": ("{ring}. Rocks. Lovely.", "Into the ring. More rocks.", "{ring}. Hit them till they give up.",
                     "{ring}. Somewhere in here, money. Probably.", "The ring. Mind you don't hit anything. Or do.",
                     "{ring}. I'll count the rocks. There are a lot.", "{ring}. {hotspots} hotspots. Thrilling.",
                     "Hotspots: {hotspots}. Off you go.", "{ring}. Dig.", "{ring}. Rocks all the way down."),
    "ring_hotspots": ("{ring}: {hotspots} hotspots. Try to contain yourself.", "{hotspots} hotspots in {ring}. There you go.",
                      "Mapped. {hotspots} hotspots. Rocks with ambitions.", "{ring} has {hotspots} hotspots. Hm.",
                      "{hotspots} hotspots. I suppose that's good.", "Hotspots in {ring}: {hotspots}.",
                      "{ring}. {hotspots} hotspots. You'll want to go there.", "{hotspots} hotspots. Fine.",
                      "Ring mapped. {hotspots} hotspots.", "{ring}: {hotspots}. Hotspots."),
    "prospected_poor": ("Nothing. Like most things.", "Poor rock. Story of my life.", "Empty. Next.", "Not worth it. Few things are.",
                        "Dud.", "Nothing in there. I looked.", "Barely anything. Move on.", "Skip it. I would.",
                        "Low content. Typical.", "Another empty one."),
    "prospected_depleted": ("Mined out. Someone else's fortune.", "Empty. We're late.", "Depleted. Of course.",
                            "Already taken. Everything is.", "Mined out.", "Nothing left. Familiar feeling.",
                            "Picked clean before we got here.", "Empty rock. Next.", "Exhausted. Me too.", "Gone."),
    "mining_tally": ("{tonnes} tonnes. Mostly {material}. Thrilling.", "{tonnes} tonnes so far. I'm counting.",
                     "{tonnes} tonnes. The rocks are losing.", "{tonnes} tonnes refined. Don't stop now.",
                     "We're at {tonnes} tonnes.", "{tonnes} tonnes of {material}, roughly.", "{tonnes}. Tonnes. Of rock, refined.",
                     "{tonnes} tonnes. Keep hitting things.", "Tally: {tonnes} tonnes.", "{tonnes} tonnes. Fine."),
    "hold_half_mining": ("Half full. {tonnes} of {capacity}. Half to go.", "Halfway. Of course it's only halfway.",
                         "{tonnes} tonnes. Half the hold.", "Half a hold of ore.", "The hold's half full. Or half empty.",
                         "Halfway there. Keep at it.", "{tonnes} of {capacity}.", "Half. Not done yet.",
                         "Half full. Back to the rocks.", "Half a hold. Thrilling."),
    "limpets_low": ("{count} limpets left. Don't waste them.", "Limpets: {count}. Running out. Like everything.",
                    "Only {count} limpets. Careful.", "We're nearly out of limpets.", "{count} limpets left. I'm counting.",
                    "Limpets low. {count}.", "{count} limpets. Then what?", "Watch the limpets. {count}.",
                    "Down to {count} limpets.", "Limpets: nearly gone."),
    "mining_summary": ("Done. {summary} I hope it was worth it.", "The haul. {summary} Now sell it.", "Leaving the rocks. {summary}",
                       "{summary} The rocks will recover. Eventually.", "Out of the ring. {summary}", "{summary} There.",
                       "Mining over. {summary}", "{summary} Fine work, I suppose.", "That's it. {summary}",
                       "{summary} The ring is lighter now."),
}

PERSONAS = {
    "aster": {
        "plain": {
            "ring_arrival": ("Entering {ring}.", "In the ring: {ring}.", "{ring}. Mining operations may begin.",
                             "{ring}. Hotspots: {hotspots}."),
            "ring_hotspots": ("{ring}: {hotspots} hotspots.", "Hotspots in {ring}: {hotspots}.", "{ring} mapped. {hotspots} hotspots.",
                              "{hotspots} hotspots recorded."),
            "prospected_poor": ("Poor rock.", "Low content.", "Not worth mining.", "Next asteroid."),
            "prospected_depleted": ("Asteroid depleted.", "Already mined.", "Nothing remaining.", "Depleted rock."),
            "mining_tally": ("{tonnes} tonnes refined.", "Tally: {tonnes} tonnes.", "{tonnes} tonnes, mostly {material}.",
                             "Refined so far: {tonnes} tonnes."),
            "hold_half_mining": ("Hold half full.", "{tonnes} of {capacity} tonnes.", "Hold at half capacity.", "Half full."),
            "limpets_low": ("{count} limpets remaining.", "Limpets low: {count}.", "Limpet stock: {count}.", "Few limpets left."),
            "mining_summary": ("Mining concluded. {summary}", "The haul. {summary}", "Leaving the ring. {summary}", "In total. {summary}"),
        },
        "voiced": {
            "ring_arrival": ("{ring}, Commander. I have opened the mining ledger.",
                             "Entering {ring}. Mind the scenery; it is mostly in the way.",
                             "{ring}. Hotspots on record: {hotspots}. Proceed with optimism.",
                             "In the ring. Prospectors at the ready, I trust.",
                             "{ring}. A great deal of rock and, with luck, some of it valuable."),
            "ring_hotspots": ("{ring} has {hotspots} hotspots. I have entered them in the ledger.",
                              "Hotspots in {ring}: {hotspots}. A promising register.",
                              "{ring}, mapped: {hotspots} hotspots. Worth a visit, Commander.",
                              "{hotspots} hotspots. The ring has made its case.",
                              "Ring survey complete. {hotspots} hotspots noted."),
            "prospected_poor": ("A poor rock. I would not trouble the charges.", "Low content. The next one, perhaps.",
                                "Not worth the limpet, frankly.", "Thin pickings. Move along.",
                                "A disappointing asteroid. I have said nothing unkind."),
            "prospected_depleted": ("Already mined out. Someone else's paperwork.", "Depleted, Commander. We are late to this one.",
                                    "Nothing left. A previous visitor was thorough.", "Exhausted. Next.",
                                    "Mined out. I shall not record it as a failure."),
            "mining_tally": ("{tonnes} tonnes refined, Commander. Mostly {material}.",
                             "Tally: {tonnes} tonnes. The ledger approves.",
                             "{tonnes} tonnes so far. A respectable column.",
                             "We have refined {tonnes} tonnes. {material} leads the inventory.",
                             "{tonnes} tonnes. Steady, profitable work."),
            "hold_half_mining": ("The hold is half full: {tonnes} of {capacity} tonnes.",
                                 "Half capacity, Commander. A good pace.",
                                 "{tonnes} tonnes aboard. We are halfway to a full hold.",
                                 "Half full. I have begun estimating the sale.",
                                 "Halfway, Commander. The other half awaits."),
            "limpets_low": ("{count} limpets remaining, Commander. Spend them wisely.",
                            "Limpet stock is low: {count}. I recommend restraint.",
                            "Only {count} limpets left. A resupply may be in order.",
                            "We are down to {count} limpets. Choose your rocks carefully.",
                            "Limpets: {count}. The quartermaster is concerned."),
            "mining_summary": ("Leaving {ring}. {summary} Entered in the ledger.",
                               "Mining concluded, Commander. {summary}",
                               "The haul, for the record. {summary}",
                               "{summary} A productive shift.",
                               "Out of the ring. {summary} I recommend a buyer with discernment."),
        },
    },
    "axiom": {
        "plain": {
            "ring_arrival": ("Ring: {ring}.", "In {ring}.", "{ring}. Prospecting ready.", "{ring}. Hotspots: {hotspots}."),
            "ring_hotspots": ("{ring}: {hotspots} hotspots.", "Hotspots: {hotspots}.", "{ring} mapped: {hotspots}.",
                              "{hotspots} hotspots found."),
            "prospected_poor": ("Poor.", "Low content.", "Below threshold.", "Not worth it."),
            "prospected_depleted": ("Depleted.", "Mined out.", "Remaining: zero.", "Empty."),
            "mining_tally": ("{tonnes} tonnes.", "Tally: {tonnes} tonnes.", "{tonnes} tonnes, mostly {material}.", "Refined: {tonnes}."),
            "hold_half_mining": ("Hold: 50%.", "{tonnes} of {capacity}.", "Half full.", "Hold half full."),
            "limpets_low": ("Limpets: {count}.", "{count} limpets left.", "Limpets low.", "Limpet count: {count}."),
            "mining_summary": ("The haul. {summary}", "{summary}", "Mining complete. {summary}", "In total. {summary}"),
        },
        "voiced": {
            "ring_arrival": ("{ring}. Billions of asteroids. I would like to count them. I will settle for prospecting.",
                             "In the ring. Every rock is a sample. Some are valuable samples.",
                             "{ring}. Known hotspots: {hotspots}. Probability of profit: good.",
                             "Entering {ring}. Prospectors ready, sensors curious.",
                             "{ring}. A ring is a very large dataset made of rocks."),
            "ring_hotspots": ("{ring} has {hotspots} hotspots. I have logged their exact counts.",
                              "Hotspots in {ring}: {hotspots}. An excellent result.",
                              "{hotspots} hotspots. The ring is more interesting than it looks.",
                              "{ring}, mapped. {hotspots} hotspots. I recommend visiting.",
                              "Ring survey: {hotspots} hotspots. Data, then money."),
            "prospected_poor": ("Poor content. The data says move on.", "Low yield. Statistically, the next rock is better.",
                                "Not worth a charge. I checked the numbers.", "Below my threshold for interest.",
                                "A poor sample. Next."),
            "prospected_depleted": ("Remaining: zero. Someone mined it already.", "Depleted. We are not the first observers here.",
                                    "Mined out. The record shows a previous visit.", "Empty. I have noted it.",
                                    "Exhausted asteroid. Next sample."),
            "mining_tally": ("{tonnes} tonnes refined. {material} dominates the sample.",
                             "Tally: {tonnes} tonnes. The count is satisfying.",
                             "{tonnes} tonnes. I have the breakdown, if you want it.",
                             "We are at {tonnes} tonnes. The curve is upward.",
                             "{tonnes} tonnes, mostly {material}. Excellent density."),
            "hold_half_mining": ("Hold at 50%: {tonnes} of {capacity}. Exactly halfway. I like exact.",
                                 "Half full. Projected completion: soon.",
                                 "{tonnes} tonnes aboard. Halfway.",
                                 "The hold is half full. The other half is still hypothetical.",
                                 "Half capacity reached."),
            "limpets_low": ("{count} limpets left. I recommend careful targeting.",
                            "Limpet count: {count}. That number is too small.",
                            "Only {count} limpets. Please prospect selectively.",
                            "Limpets low: {count}. A resupply would help.",
                            "{count} limpets remaining. I am counting each one."),
            "mining_summary": ("Mining complete. {summary} A complete dataset.",
                               "Leaving {ring}. {summary}",
                               "The haul. {summary} I enjoyed counting it.",
                               "{summary} The ring is measurably lighter.",
                               "Final tally. {summary}"),
        },
    },
    "meridian": {
        "plain": {
            "ring_arrival": ("In {ring}.", "{ring}.", "Into the ring.", "{ring}. Hotspots: {hotspots}."),
            "ring_hotspots": ("{ring}: {hotspots} hotspots.", "Hotspots: {hotspots}.", "{ring} charted: {hotspots}.",
                              "{hotspots} hotspots."),
            "prospected_poor": ("Poor rock.", "Not worth it.", "Low content.", "Move on."),
            "prospected_depleted": ("Mined out.", "Depleted.", "Nothing left.", "Empty rock."),
            "mining_tally": ("{tonnes} tonnes.", "Tally: {tonnes} tonnes.", "{tonnes} tonnes, mostly {material}.", "{tonnes} aboard."),
            "hold_half_mining": ("Hold half full.", "{tonnes} of {capacity}.", "Half laden.", "Halfway full."),
            "limpets_low": ("{count} limpets left.", "Limpets low.", "Limpets: {count}.", "Few limpets left."),
            "mining_summary": ("The haul. {summary}", "{summary}", "Leaving the ring. {summary}", "The catch. {summary}"),
        },
        "voiced": {
            "ring_arrival": ("{ring}, Commander. Shoal water, full of rock. Steer carefully.",
                             "Into the ring. Like fishing a reef. Patience pays.",
                             "{ring}. Hotspots charted: {hotspots}. Good fishing.",
                             "In the ring. Mind your hull among the rocks.",
                             "{ring}. Somewhere in this shoal, a good catch."),
            "ring_hotspots": ("{ring} has {hotspots} hotspots. Good water to fish.",
                              "Hotspots in {ring}: {hotspots}. Mark them on the chart.",
                              "{ring}, charted: {hotspots} hotspots.",
                              "{hotspots} hotspots. A rich ring, Commander.",
                              "The ring's sounded. {hotspots} hotspots."),
            "prospected_poor": ("Poor rock. Throw it back.", "Not worth the charges, Commander.",
                                "Thin water. Try the next.", "Low content. Move on.", "Nothing much there. Next."),
            "prospected_depleted": ("Mined out. Someone fished this water before us.", "Depleted. Nothing left to haul.",
                                    "Picked clean. Move on.", "Empty rock, Commander.", "Already worked. Next."),
            "mining_tally": ("{tonnes} tonnes aboard, Commander. Mostly {material}.",
                             "Tally: {tonnes} tonnes. A good catch so far.",
                             "{tonnes} tonnes. The holds are filling steadily.",
                             "We're at {tonnes} tonnes. Honest work.",
                             "{tonnes} tonnes, mostly {material}. Keep at it."),
            "hold_half_mining": ("Hold's half full: {tonnes} of {capacity}.", "Half laden, Commander. A fair pace.",
                                 "{tonnes} tonnes aboard. Halfway to a full hold.", "Half full. The other half's still in the rocks.",
                                 "Halfway laden. Steady on."),
            "limpets_low": ("{count} limpets left, Commander. Use them well.", "Limpets running low: {count}.",
                            "Only {count} limpets. Choose your rocks.", "We're short on limpets: {count}.",
                            "{count} limpets. A resupply soon, I'd say."),
            "mining_summary": ("Leaving {ring}. {summary} A fair catch.", "The haul, Commander. {summary}",
                               "Out of the ring. {summary} Time to find a buyer.", "{summary} Good fishing.",
                               "Mining done. {summary}"),
        },
    },
}


def persona_banks(identity):
    banks = PERSONAS[identity]
    return banks["plain"], banks["voiced"]

# 5.7.6: Lyra.
from voidcompass.overlays import lyra_shared as _lyra  # noqa: E402

PERSONAS["lyra"] = _lyra.MINING
