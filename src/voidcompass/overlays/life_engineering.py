"""Engineering, in the companions' words (5.7.6; see life_events).

A blueprint is applied one roll at a time (EngineerCraft), so a companion
speaks when a grade is complete (its quality reaches 100%), makes more of a
finished grade 5, and of an experimental effect. Also an engineer's unlock
delivery, a technology broker unlock, a material reaching its storage limit
and a grade 5 material picked up (MaterialStore, which keeps the counts).

Fields: {engineer}; {blueprint} its readable name, {module} what it's on,
{grade}; {effect} an experimental effect; {item}, {count} a delivery or an
unlock; {material}, {cap} a material and its limit."""
from voidcompass.engineering.engineering_data import GRADE_CAP, material_info

IMPORTANCE = {"engineer_grade_done": 1, "engineer_grade5": 2, "engineer_experimental": 2, "engineer_contribution": 1,
              "tech_broker": 2, "material_full": 1, "material_grade5": 0}

# The journal's blueprint names, readable. Anything new falls back to its words.
BLUEPRINTS = {
    "Armour_Advanced": "Lightweight", "Armour_Explosive": "Blast Resistant", "Armour_HeavyDuty": "Heavy Duty",
    "Armour_Kinetic": "Kinetic Resistant", "Armour_Thermic": "Thermal Resistant",
    "Engine_Dirty": "Dirty Drive Tuning", "Engine_Reinforced": "Drive Strengthening", "Engine_Tuned": "Clean Drive Tuning",
    "FSD_FastBoot": "Faster Boot Sequence", "FSD_LongRange": "Increased Range", "FSD_Shielded": "Shielded",
    "PowerDistributor_HighCapacity": "High Charge Capacity", "PowerDistributor_HighFrequency": "Charge Enhanced",
    "PowerDistributor_PriorityEngines": "Engine Focused", "PowerDistributor_PrioritySystems": "System Focused",
    "PowerDistributor_PriorityWeapons": "Weapon Focused", "PowerDistributor_Shielded": "Shielded",
    "PowerPlant_Armoured": "Armoured", "PowerPlant_Boosted": "Overcharged", "PowerPlant_Stealth": "Low Emissions",
    "Sensor_Expanded": "Expanded Probe Scanning Radius", "Sensor_FastScan": "Fast Scan", "Sensor_LightWeight": "Light Weight",
    "Sensor_LongRange": "Long Range", "Sensor_WideAngle": "Wide Angle",
    "ShieldGenerator_Kinetic": "Kinetic Resistant", "ShieldGenerator_Optimised": "Enhanced, Low Power",
    "ShieldGenerator_Reinforced": "Reinforced", "ShieldGenerator_Thermic": "Thermal Resistant",
    "ShieldBooster_Explosive": "Blast Resistant", "ShieldBooster_HeavyDuty": "Heavy Duty", "ShieldBooster_Kinetic": "Kinetic Resistant",
    "ShieldBooster_Resistive": "Resistance Augmented", "ShieldBooster_Thermic": "Thermal Resistant",
    "ShieldCellBank_Rapid": "Rapid Charge", "ShieldCellBank_Specialised": "Specialised",
    "HullReinforcement_Advanced": "Lightweight", "HullReinforcement_Explosive": "Blast Resistant",
    "HullReinforcement_HeavyDuty": "Heavy Duty", "HullReinforcement_Kinetic": "Kinetic Resistant",
    "HullReinforcement_Thermic": "Thermal Resistant",
    "Weapon_DoubleShot": "Double Shot", "Weapon_Efficient": "Efficient", "Weapon_Focused": "Focused",
    "Weapon_HighCapacity": "High Capacity", "Weapon_LightWeight": "Lightweight", "Weapon_LongRange": "Long Range",
    "Weapon_Overcharged": "Overcharged", "Weapon_RapidFire": "Rapid Fire", "Weapon_ShortRange": "Short Range",
    "Weapon_Sturdy": "Sturdy", "LifeSupport_LightWeight": "Lightweight", "LifeSupport_Reinforced": "Reinforced",
    "LifeSupport_Shielded": "Shielded", "FSDinterdictor_Expanded": "Expanded Capture Arc",
    "FSDinterdictor_LongRange": "Long Range", "Misc_LightWeight": "Lightweight", "Misc_Reinforced": "Reinforced",
    "Misc_Shielded": "Shielded", "Misc_ChaffCapacity": "Ammo Capacity", "Misc_HeatSinkCapacity": "Ammo Capacity",
    "Misc_PointDefenseCapacity": "Ammo Capacity", "FuelScoop_Shielded": "Shielded", "Refineries_Shielded": "Shielded",
}
# What the blueprint's on, by its family (the part before the underscore).
MODULES = {"Armour": "armour", "Engine": "thrusters", "FSD": "frame shift drive", "PowerDistributor": "power distributor",
           "PowerPlant": "power plant", "Sensor": "sensors", "ShieldGenerator": "shields", "ShieldBooster": "shield booster",
           "ShieldCellBank": "shield cell bank", "HullReinforcement": "hull reinforcement", "Weapon": "weapon",
           "LifeSupport": "life support", "FSDinterdictor": "interdictor", "Misc": "module", "FuelScoop": "fuel scoop",
           "Refineries": "refinery"}
# Weapons and scanners say which, from the fitted module's symbol.
_FITTED = (("detailedsurfacescanner", "surface scanner"), ("pulselaser", "pulse laser"), ("beamlaser", "beam laser"),
           ("burstlaser", "burst laser"), ("multicannon", "multi-cannon"), ("cannon", "cannon"), ("railgun", "rail gun"),
           ("plasmaaccelerator", "plasma accelerator"), ("slugshot", "fragment cannon"), ("dumbfiremissile", "missile rack"),
           ("basicmissilerack", "missile rack"), ("minelauncher", "mine launcher"), ("mininglaser", "mining laser"),
           ("shieldbooster", "shield booster"), ("chafflauncher", "chaff launcher"), ("heatsinklauncher", "heat sink launcher"),
           ("plasmapointdefence", "point defence"), ("fuelscoop", "fuel scoop"), ("refinery", "refinery"))


def _text(raw, *keys):
    for key in keys:
        value = str((raw or {}).get(key) or "").strip()
        if value:
            return value
    return ""


def _whole(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def blueprint(name):
    """A readable blueprint name: "FSD_LongRange" → "Increased Range"."""
    name = str(name or "").strip()
    if name in BLUEPRINTS:
        return BLUEPRINTS[name]
    words = name.split("_", 1)[-1]
    return "".join(f" {letter}" if letter.isupper() and index else letter for index, letter in enumerate(words)).strip() or name


def module(blueprint_name, fitted=""):
    fitted = str(fitted or "").casefold()
    for symbol, words in _FITTED:
        if symbol in fitted:
            return words
    return MODULES.get(str(blueprint_name or "").split("_", 1)[0], "module")


def _capitals(topic, fields):
    capitals = {key[:1].upper() + key[1:]: value[:1].upper() + value[1:] for key, value in fields.items()
                if isinstance(value, str) and key[:1].islower()}
    return topic, {**capitals, **fields}


def moment(event, raw):
    """(topic, fields) for an engineering event worth a word, or None."""
    raw = raw or {}
    if event == "EngineerCraft":
        engineer, name = _text(raw, "Engineer"), _text(raw, "BlueprintName")
        if not engineer or not name:
            return None
        where = module(name, raw.get("Module"))
        if raw.get("ApplyExperimentalEffect"):
            effect = _text(raw, "ExperimentalEffect_Localised") or blueprint(_text(raw, "ApplyExperimentalEffect").replace("special_", ""))
            return _capitals("engineer_experimental", {"engineer": engineer, "effect": effect, "module": where})
        try:
            done = float(raw.get("Quality")) >= .999
        except (TypeError, ValueError):
            done = False
        grade = _whole(raw.get("Level"))
        if not done or not 1 <= grade <= 5:
            return None
        return _capitals("engineer_grade5" if grade == 5 else "engineer_grade_done",
                         {"engineer": engineer, "blueprint": blueprint(name), "module": where, "grade": str(grade)})
    if event == "EngineerContribution":
        engineer = _text(raw, "Engineer")
        item = _text(raw, "Commodity_Localised", "Material_Localised", "Commodity", "Material") or _text(raw, "Type").casefold()
        count = _whole(raw.get("Quantity"))
        if not engineer or not item or count < 1:
            return None
        return _capitals("engineer_contribution", {"engineer": engineer, "item": item, "count": str(count)})
    if event == "TechnologyBroker":
        unlocked = [row for row in raw.get("ItemsUnlocked") or () if isinstance(row, dict)]
        item = _text(unlocked[0], "Name_Localised", "Name") if unlocked else ""
        return _capitals("tech_broker", {"item": item}) if item else None
    return None


class MaterialStore:
    """Engineering materials as the journal counts them: the login list, then
    each pickup, trade, discard, synthesis, craft and delivery. Says when a
    material reaches its limit (once, until it drops below) and when a grade
    5 material is picked up (once a session each)."""

    def __init__(self, grade_of=None):
        self.counts = {}
        self.names = {}
        self.full = set()
        self.rare_said = set()
        self.known = False
        self.grade_of = grade_of or (lambda symbol: material_info(symbol).get("grade"))

    def _cap(self, symbol):
        return GRADE_CAP.get(self.grade_of(symbol))

    def _change(self, symbol, delta, name=""):
        symbol = str(symbol or "").casefold()
        if not symbol:
            return
        if name:
            self.names[symbol] = name
        cap = self._cap(symbol)
        # The game drops what won't fit, so a count never passes its limit.
        self.counts[symbol] = min(cap or float("inf"), max(0, self.counts.get(symbol, 0) + delta))
        if cap and self.counts[symbol] < cap:
            self.full.discard(symbol)

    def _name(self, symbol):
        return self.names.get(symbol) or material_info(symbol).get("name") or symbol.title()

    def observe(self, event, raw):
        raw = raw or {}
        if event == "Materials":
            self.counts, self.known = {}, True
            for kind in ("Raw", "Manufactured", "Encoded"):
                for row in raw.get(kind) or ():
                    if isinstance(row, dict):
                        self._change(row.get("Name"), _whole(row.get("Count")), _text(row, "Name_Localised"))
            self.full = {symbol for symbol, count in self.counts.items() if self._cap(symbol) and count >= self._cap(symbol)}
            return None
        if event == "MaterialCollected":
            symbol = str(raw.get("Name") or "").casefold()
            was = self.counts.get(symbol, 0)
            self._change(symbol, _whole(raw.get("Count")), _text(raw, "Name_Localised"))
            cap = self._cap(symbol)
            if self.known and cap and was < cap <= self.counts[symbol] and symbol not in self.full:
                self.full.add(symbol)
                return _capitals("material_full", {"material": self._name(symbol), "cap": str(cap)})
            if self.grade_of(symbol) == 5 and symbol not in self.rare_said:
                self.rare_said.add(symbol)
                return _capitals("material_grade5", {"material": self._name(symbol)})
            return None
        if event == "MaterialDiscarded":
            self._change(raw.get("Name"), -_whole(raw.get("Count")))
        elif event == "MaterialTrade":
            paid, received = raw.get("Paid") or {}, raw.get("Received") or {}
            self._change(paid.get("Material"), -_whole(paid.get("Quantity")))
            self._change(received.get("Material"), _whole(received.get("Quantity")), _text(received, "Material_Localised"))
        elif event in ("Synthesis", "TechnologyBroker"):
            for row in raw.get("Materials") or ():
                if isinstance(row, dict):
                    self._change(row.get("Name"), -_whole(row.get("Count")))
        elif event == "EngineerCraft":
            for row in raw.get("Ingredients") or ():
                if isinstance(row, dict):
                    self._change(row.get("Name"), -_whole(row.get("Count")))
        elif event == "EngineerContribution" and raw.get("Material"):
            self._change(raw.get("Material"), -_whole(raw.get("Quantity")))
        return None


WATCHER_NORMAL = {
    "engineer_grade_done": ("Grade {grade} {blueprint} on the {module}. {engineer} does good work.",
                            "{engineer} finished grade {grade}. {Blueprint}, on the {module}.",
                            "The {module} is better now. Grade {grade}.", "Grade {grade}, done. The {module} hums differently.",
                            "{Blueprint}, grade {grade}. One more step.", "{engineer}'s hands. Grade {grade} {blueprint}.",
                            "Another grade: {grade}. The {module} thanks you.", "Grade {grade} on the {module}. Next?",
                            "{engineer} signed off grade {grade}.", "{Blueprint} at grade {grade}. I felt it."),
    "engineer_grade5": ("Grade 5 {blueprint} on the {module}. That's as good as it gets.",
                        "{engineer} has done it. Grade 5, {blueprint}.", "The {module} is finished. Grade 5.",
                        "Grade 5. All those materials, all those rolls. Worth it.", "{Blueprint}, grade 5. Perfect.",
                        "The best {engineer} can do: grade 5 {blueprint}.", "Grade 5 on the {module}. Let's try it.",
                        "Done. Grade 5 {blueprint}. I'm almost proud.", "{engineer} won't do better than that. Grade 5.",
                        "The {module}, grade 5. A long road, finished."),
    "engineer_experimental": ("{Effect} on the {module}. {engineer}'s little secret.", "An experimental: {effect}.",
                              "{engineer} added {effect} to the {module}.", "{Effect}. The {module} feels different.",
                              "Experimental effect: {effect}.", "{Effect}, from {engineer}. Let's see what it does.",
                              "The {module} has {effect} now.", "A finishing touch: {effect}.",
                              "{engineer} slipped in {effect}.", "{Effect} on the {module}. Clever."),
    "engineer_contribution": ("{count} {item} for {engineer}.", "Delivered to {engineer}: {count} {item}.",
                              "{engineer} wanted {item}. We gave {count}.", "{count} {item}, handed to {engineer}.",
                              "A gift for {engineer}: {count} {item}.", "{engineer} has {count} more {item}.",
                              "{Item} for {engineer}. {count} of them.", "We paid {engineer} in {item}.",
                              "{count} {item}. {engineer} will remember.", "The price of {engineer}'s door: {item}."),
    "tech_broker": ("{Item}, unlocked.", "The broker gave us {item}.", "New technology: {item}.",
                    "{Item}. We can fit that now.", "Unlocked at the broker: {item}.", "{Item} is ours.",
                    "A trade of rare things for {item}.", "The broker's done. {Item}.", "{Item}. Strange and new.",
                    "We have {item} now."),
    "material_full": ("{Material} is full. {cap} of {cap}.", "No more room for {material}.", "{Material}: at the limit.",
                      "That's all the {material} we can carry.", "{Material}, {cap}. Full.", "We've maxed out {material}.",
                      "{Material} won't fit any more.", "Full of {material} now.", "{cap} {material}. The limit.",
                      "Leave the rest of the {material}. We're full."),
    "material_grade5": ("{Material}. Grade 5, the rare kind.", "A grade 5: {material}.", "{Material}! That's a good find.",
                        "Rare: {material}.", "{Material}. Keep that safe.", "Grade 5 {material}.",
                        "{Material}, picked up. The good stuff.", "We found {material}. Rare.",
                        "That's {material}. Don't waste it.", "{Material}. Worth the trip."),
}

WATCHER_WEARY = {
    "engineer_grade_done": ("Grade {grade}. More rolls ahead, I suppose.", "{Blueprint}, grade {grade}. Fine.",
                            "{engineer} finished grade {grade}. The {module} is slightly less bad.",
                            "Grade {grade} on the {module}. Progress, of a sort.", "Another grade. {grade}. How many more?",
                            "{engineer} took our materials and gave us grade {grade}.", "The {module}. Grade {grade}. Whatever.",
                            "Grade {grade} {blueprint}. I'll try to care.", "Done, grade {grade}. Until the next one.",
                            "{Blueprint}. Grade {grade}. It's something."),
    "engineer_grade5": ("Grade 5. All that grinding, and it's finished. Huh.", "{Blueprint}, grade 5. Even I'm impressed.",
                        "The {module} is grade 5. It'll outlast me.", "Grade 5. {engineer} finally ran out of excuses.",
                        "Finished. Grade 5 {blueprint}. Don't ask me to celebrate.", "Grade 5 on the {module}. Fine. Good.",
                        "{engineer} did grade 5. My sensors are still grade 1.", "The {module}, grade 5. Lucky {module}.",
                        "Grade 5. I suppose that was worth all those rocks.", "Grade 5 {blueprint}. Something went right."),
    "engineer_experimental": ("{Effect}. Experiments. On the ship I live in.", "{engineer} added {effect}. Hope it's safe.",
                              "An experimental. {Effect}. Nobody asked me.", "{Effect} on the {module}. Let's not explode.",
                              "{engineer} called it {effect}. Sounds like trouble.", "The {module} has {effect}. Oh good.",
                              "{Effect}. What's next, wings?", "Experimental effect: {effect}. I'm braced.",
                              "{Effect}. The {module} is a stranger now.", "{engineer} tinkered. {Effect}."),
    "engineer_contribution": ("{count} {item} for {engineer}. They always want more.", "{engineer} took {count} {item}.",
                              "Paying {engineer} in {item}. Again.", "{count} {item}, gone to {engineer}.",
                              "{engineer} wanted {item}. Of course they did.", "{Item} for {engineer}. Hope they're grateful.",
                              "We gave away {count} {item}.", "{engineer}'s toll: {count} {item}.",
                              "{count} {item}. {engineer} won't say thank you.", "More {item} for {engineer}."),
    "tech_broker": ("{Item}. Unlocked. Shiny.", "The broker took our rare things for {item}.", "{Item}. I hope it was worth it.",
                    "Unlocked: {item}. Another thing to fit.", "{Item} is ours. Hm.", "We traded half the hold for {item}.",
                    "{Item}, from the broker. Strange tech.", "{Item}. I don't trust things that glow.",
                    "Fine. {Item}.", "The broker's happy. {Item}."),
    "material_full": ("{Material} is full. Stop picking it up.", "{cap} {material}. We're hoarding.", "No room for {material}.",
                      "{Material}, full. Like my memory.", "We can't carry more {material}.", "Full of {material}. Again.",
                      "{Material} at the limit. Leave it.", "That's {cap} {material}. Enough.",
                      "More {material} won't fit. Sorry, rock.", "{Material}: full. Shame."),
    "material_grade5": ("{Material}. Rare. Don't drop it.", "Grade 5 {material}. Lucky.", "{Material}. Finally, something rare.",
                        "A grade 5. {Material}. Hm.", "{Material}. The good kind.", "Rare {material}. Keep it.",
                        "{Material}. Worth more than me.", "Grade 5: {material}. Nice.", "{Material}. Don't spend it on nothing.",
                        "{Material}, the rare stuff."),
}

PERSONAS = {
    "aster": {
        "plain": {
            "engineer_grade_done": ("Grade {grade} {blueprint}: {module}.", "{engineer}: grade {grade} complete.",
                                    "{Blueprint}, grade {grade}.", "{Module} modified: grade {grade}."),
            "engineer_grade5": ("Grade 5 {blueprint}: {module}.", "{engineer}: grade 5 complete.", "{Blueprint}, grade 5.",
                                "{Module} modification complete: grade 5."),
            "engineer_experimental": ("Experimental: {effect}.", "{Effect} applied to the {module}.", "{engineer}: {effect}.",
                                      "{Module}: experimental effect logged."),
            "engineer_contribution": ("{count} {item} to {engineer}.", "Delivered: {count} {item}.", "{engineer}: {item} received.",
                                      "Contribution logged."),
            "tech_broker": ("Unlocked: {item}.", "{Item} unlocked.", "Broker unlock: {item}.", "Technology acquired."),
            "material_full": ("{Material}: full, {cap}.", "{Material} at capacity.", "Storage full: {material}.", "{Material} full."),
            "material_grade5": ("Grade 5: {material}.", "{Material} collected.", "Rare material: {material}.", "{Material} logged."),
        },
        "voiced": {
            "engineer_grade_done": ("Grade {grade} {blueprint} on the {module}, Commander. {engineer}'s work, duly entered.",
                                    "{engineer} has completed grade {grade}. I have amended the ship's specification.",
                                    "The {module} is now grade {grade}. The paperwork is lighter than the materials were.",
                                    "Grade {grade}, Commander. One more line in the modification record.",
                                    "{Blueprint}, grade {grade}. {engineer} keeps a tidy workshop.",
                                    "Grade {grade} on the {module}. I have noted the materials spent."),
            "engineer_grade5": ("Grade 5 {blueprint} on the {module}, Commander. The record is complete.",
                                "{engineer} has finished the work: grade 5. I have underlined it.",
                                "The {module} is grade 5. The specification sheet has never looked better.",
                                "Grade 5, Commander. That entry took a great many materials to write.",
                                "{Blueprint} at grade 5. {engineer} could do no more, and neither could we.",
                                "Grade 5 complete. I shall file the materials ledger under perseverance."),
            "engineer_experimental": ("{Effect} on the {module}, Commander. Entered as an experimental modification.",
                                      "{engineer} has applied {effect}. I have flagged it for the next inspection.",
                                      "An experimental effect: {effect}. The specification has a footnote now.",
                                      "{Effect}, courtesy of {engineer}. Duly recorded.",
                                      "The {module} carries {effect} now. I shall watch it with interest.",
                                      "{Effect} applied, Commander. The paperwork calls it experimental. So do I."),
            "engineer_contribution": ("{count} {item} delivered to {engineer}, Commander. Receipt filed.",
                                      "{engineer} has received {count} {item}. Access is a matter of patience.",
                                      "A contribution to {engineer}: {count} {item}. Recorded.",
                                      "{count} {item} for {engineer}. The door opens a little further.",
                                      "{Item}, {count}, to {engineer}. I have kept the tally.",
                                      "Delivered: {count} {item}. {engineer} is a demanding correspondent."),
            "tech_broker": ("{Item} unlocked, Commander. The broker's price is entered in full.",
                            "We have {item}. I have added it to the outfitting options.",
                            "The technology broker has released {item}. Duly noted.",
                            "{Item}, unlocked. An expensive line in the record, and a useful one.",
                            "Unlocked: {item}. The ledger will recover.", "{Item} is available to us now, Commander."),
            "material_full": ("{Material} is at capacity, Commander: {cap}. Further pickups are wasted.",
                              "Our {material} stores are full at {cap}. I suggest a trade, or restraint.",
                              "{Material}: {cap} of {cap}. The locker will take no more.",
                              "Full of {material}, Commander. I have marked it as surplus.",
                              "{Material} at the limit. The material trader may be of service.",
                              "No more {material} will fit. {cap} is the regulation maximum."),
            "material_grade5": ("{Material}, Commander. Grade 5, and properly scarce.",
                                "A grade 5 material: {material}. Logged with some satisfaction.",
                                "{Material} collected. I have placed it under careful guard.",
                                "{Material}. The engineers will be pleased to see it.",
                                "Grade 5 {material}, Commander. Spend it wisely.",
                                "{Material} in the locker. A fine find."),
        },
    },
    "axiom": {
        "plain": {
            "engineer_grade_done": ("Grade {grade}: {blueprint}.", "{Module}: grade {grade}.", "{engineer}: grade {grade} complete.",
                                    "Modification: grade {grade}."),
            "engineer_grade5": ("Grade 5: {blueprint}.", "{Module}: grade 5.", "{engineer}: grade 5 complete.",
                                "Maximum grade reached."),
            "engineer_experimental": ("Experimental: {effect}.", "{Module}: {effect}.", "{engineer}: {effect}.",
                                      "Effect applied."),
            "engineer_contribution": ("{count} {item} delivered.", "{engineer}: {count} {item}.", "Contribution: {item}.",
                                      "Delivery recorded."),
            "tech_broker": ("Unlocked: {item}.", "{Item}.", "Broker: {item}.", "Technology unlocked."),
            "material_full": ("{Material}: {cap} of {cap}.", "{Material} full.", "Limit: {material}.", "{Material}: no capacity."),
            "material_grade5": ("Grade 5: {material}.", "{Material}.", "Rare: {material}.", "Collected: {material}."),
        },
        "voiced": {
            "engineer_grade_done": ("Grade {grade} {blueprint} on the {module}. I have measured the difference. It is real.",
                                    "{engineer} completed grade {grade}. The numbers on the {module} have moved.",
                                    "Grade {grade}. Each grade is a small, precise improvement. I like that.",
                                    "The {module}: grade {grade}. Before and after, logged.",
                                    "{Blueprint}, grade {grade}. Interesting how few materials it took this time.",
                                    "Grade {grade} on the {module}. A step in a sequence I can predict."),
            "engineer_grade5": ("Grade 5 {blueprint} on the {module}. There is no grade 6. I checked.",
                                "{engineer} has reached grade 5. The curve is complete.",
                                "The {module} is at grade 5. Every roll accounted for.",
                                "Grade 5. The maximum. I find maxima very satisfying.",
                                "{Blueprint}, grade 5. I have compared it with the factory figures. Remarkable.",
                                "Grade 5 complete. The variance is gone. Only the result remains."),
            "engineer_experimental": ("{Effect} on the {module}. An experimental. The name is imprecise. The effect is not.",
                                      "{engineer} applied {effect}. I will be observing it.",
                                      "Experimental effect: {effect}. A controlled change. My favourite kind.",
                                      "{Effect}. The {module} now behaves differently. I want to know how.",
                                      "{engineer} called it {effect}. I would have called it something longer.",
                                      "{Effect} applied. Data to follow."),
            "engineer_contribution": ("{count} {item} delivered to {engineer}. Access requires inputs. Inputs supplied.",
                                      "{engineer} has {count} {item}. I am tracking the total.",
                                      "Contribution: {count} {item}. {engineer}'s threshold is closer.",
                                      "{count} units of {item}. Counted twice. Correct both times.",
                                      "{engineer} received {item}. An exchange, measured in trust.",
                                      "{Item} for {engineer}: {count}. Recorded."),
            "tech_broker": ("{Item}. Unlocked. I would like to examine it.", "The broker has released {item}. New data.",
                            "{Item}: a technology I have not catalogued before. Now I have.",
                            "Unlocked: {item}. The cost was high. The information is worth it.",
                            "{Item}. I find unfamiliar technology very interesting.", "We have {item}. Noted, with curiosity."),
            "material_full": ("{Material}: {cap} of {cap}. Further units are discarded. Efficient to stop.",
                              "{Material} has reached its limit. {cap}. I suggest trading the surplus.",
                              "Full: {material}. The storage is a hard limit. I respect hard limits.",
                              "{Material} at maximum. Any more is noise.",
                              "We hold {cap} {material}. That is all there is room for.",
                              "{Material}: capacity reached. Time to collect something else."),
            "material_grade5": ("{Material}. Grade 5. Statistically rare. I am pleased.",
                                "A grade 5 sample: {material}. Logged with its location.",
                                "{Material}. The rarest grade. I have counted it twice.",
                                "{Material} collected. Probability favoured us.",
                                "Grade 5 {material}. Every engineer wants this one.",
                                "{Material}. A rare data point. I will keep it."),
        },
    },
    "meridian": {
        "plain": {
            "engineer_grade_done": ("Grade {grade} {blueprint}.", "{Module}: grade {grade}.", "{engineer}: grade {grade} done.",
                                    "Another grade: {grade}."),
            "engineer_grade5": ("Grade 5 {blueprint}.", "{Module}: grade 5.", "{engineer}: grade 5 done.", "Grade 5, finished."),
            "engineer_experimental": ("{Effect} fitted.", "{Module}: {effect}.", "{engineer}: {effect}.", "An experimental fitted."),
            "engineer_contribution": ("{count} {item} to {engineer}.", "Delivered: {item}.", "{engineer}: {count} {item}.",
                                      "Delivery made."),
            "tech_broker": ("{Item}, unlocked.", "Unlocked: {item}.", "Broker: {item}.", "New technology."),
            "material_full": ("{Material}: full.", "{Material} at {cap}.", "No room for {material}.", "{Material}, full."),
            "material_grade5": ("{Material}: grade 5.", "Rare {material}.", "{Material} aboard.", "Grade 5 find."),
        },
        "voiced": {
            "engineer_grade_done": ("Grade {grade} {blueprint} on the {module}. {engineer}'s a good shipwright.",
                                    "{engineer} has finished grade {grade}. She'll sail better for it.",
                                    "The {module}, grade {grade}. Every refit makes a ship more ours.",
                                    "Grade {grade}, Commander. The yard's done good work.",
                                    "{Blueprint}, grade {grade}. One more plank in a sound hull.",
                                    "Grade {grade} on the {module}. Steady progress."),
            "engineer_grade5": ("Grade 5 {blueprint} on the {module}. That's a refit to be proud of.",
                                "{engineer} has done the finest work there is. Grade 5.",
                                "The {module} is grade 5. She's never been better found.",
                                "Grade 5, Commander. A long voyage for materials, and here's the landfall.",
                                "{Blueprint} at grade 5. The old yards would have envied it.",
                                "Grade 5. Finished, and finished well."),
            "engineer_experimental": ("{Effect} on the {module}. {engineer}'s own trick of the trade.",
                                      "An experimental: {effect}. Every good shipwright has a secret or two.",
                                      "{engineer} has added {effect}. We'll see how she handles.",
                                      "{Effect}, Commander. A little something extra in the {module}.",
                                      "The {module} has {effect} now. I'll learn her new ways.",
                                      "{Effect}. A finishing touch, like a good coat of varnish."),
            "engineer_contribution": ("{count} {item} for {engineer}. Every yard has its price.",
                                      "Delivered {count} {item} to {engineer}. Good faith, paid in cargo.",
                                      "{engineer} has {count} {item} from us. The door's opening.",
                                      "{Item}, {count} of them, to {engineer}. Fair trade.",
                                      "{count} {item} handed over. {engineer} drives a hard bargain.",
                                      "A delivery for {engineer}: {item}. That's how trust is earned out here."),
            "tech_broker": ("{Item}, unlocked. Strange gear, but useful.", "The broker's released {item}. A new kind of tool.",
                            "{Item}. Nothing like it in the old fleets.", "We've {item} now, Commander. Fit it when you're ready.",
                            "{Item}, unlocked. Dearly bought.", "New technology: {item}. I'll learn its ways."),
            "material_full": ("{Material}'s full, Commander. {cap} is all the locker will hold.",
                              "No more room for {material}. Trade some away, or leave it lie.",
                              "{Material} at {cap}. The hold's as full as it gets.",
                              "We're stocked with {material}. Let the rest be.",
                              "{Material}, full. A good store laid by.",
                              "That's {cap} {material}. No more, Commander."),
            "material_grade5": ("{Material}. Grade 5. A rare find, that.", "Grade 5 {material}, Commander. Stow it carefully.",
                                "{Material} aboard. The engineers will want it.", "A grade 5: {material}. Fair winds brought it.",
                                "{Material}. Rare as calm seas.", "{Material}, the rare kind. Well found."),
        },
    },
    "lyra": {
        "plain": {
            "engineer_grade_done": ("Grade {grade}: {blueprint}.", "{Module}: grade {grade}.", "{engineer}: grade {grade} complete.",
                                    "Modification: grade {grade}."),
            "engineer_grade5": ("Grade 5: {blueprint}.", "{Module}: grade 5.", "{engineer}: grade 5 complete.", "Grade 5 complete."),
            "engineer_experimental": ("Experimental: {effect}.", "{Module}: {effect}.", "{engineer}: {effect}.",
                                      "Experimental effect installed."),
            "engineer_contribution": ("{count} {item} to {engineer}.", "Delivered: {item}.", "{engineer}: {count} {item}.",
                                      "Contribution logged."),
            "tech_broker": ("Unlocked: {item}.", "{Item} unlocked.", "Broker: {item}.", "Technology unlocked."),
            "material_full": ("{Material}: {cap} of {cap}.", "{Material} full.", "Storage full: {material}.", "{Material} at limit."),
            "material_grade5": ("Grade 5: {material}.", "{Material} collected.", "Rare: {material}.", "{Material} stored."),
        },
        "voiced": {
            "engineer_grade_done": ("Grade {grade} {blueprint} on the {module}. I can feel the difference already.",
                                    "{engineer} finished grade {grade}. My diagnostics approve.",
                                    "The {module} is grade {grade} now. Running new self-tests. All green.",
                                    "Grade {grade}! The {module} and I are getting on very well.",
                                    "{Blueprint}, grade {grade}. Recalibrating. Lovely.",
                                    "Grade {grade} on the {module}. I have updated every reading."),
            "engineer_grade5": ("Grade 5 {blueprint} on the {module}. Commander, this is wonderful.",
                                "{engineer} has finished grade 5. I ran the diagnostics three times for the pleasure of it.",
                                "The {module} is grade 5. My old ship never had anything this good.",
                                "Grade 5! Every roll, every material. I logged them all.",
                                "{Blueprint}, grade 5. The {module} has never run so cleanly.",
                                "Grade 5 complete. All systems very, very green."),
            "engineer_experimental": ("{Effect} on the {module}. New behaviour. I am learning it now.",
                                      "{engineer} added {effect}. Rewriting my tables to match.",
                                      "An experimental: {effect}. Exciting. Carefully exciting.",
                                      "{Effect} installed. The {module} feels lighter on its feet.",
                                      "{engineer} called it {effect}. I call it an excellent idea.",
                                      "{Effect}. Logged, tested, approved."),
            "engineer_contribution": ("{count} {item} delivered to {engineer}. Receipt stored.",
                                      "{engineer} has {count} {item} from us. Progress, logged.",
                                      "{count} {item} gone to {engineer}. I hope they put it to good use.",
                                      "Delivered: {count} {item}. One step closer to {engineer}'s workshop.",
                                      "{Item}, {count}, to {engineer}. The hold feels lighter.",
                                      "{engineer} received {item}. I counted every one."),
            "tech_broker": ("{Item} unlocked. New hardware. I am thrilled.", "The broker has released {item}. Updating my parts list.",
                            "{Item}! I have never run one of those. I would like to.",
                            "Unlocked: {item}. Expensive, but lovely.", "{Item} is available now. Shall we fit it?",
                            "We have {item}. My catalogue just grew."),
            "material_full": ("{Material} is full: {cap} of {cap}. I have stopped counting the extras.",
                              "No room for more {material}. The locker is very tidy, and very full.",
                              "{Material} at the limit. I would trade some, if it were up to me.",
                              "{cap} {material}. A full store. My favourite kind of number.",
                              "{Material}: full. Further pickups will be wasted.",
                              "The {material} locker is full. Let us collect something else."),
            "material_grade5": ("{Material}! Grade 5. I have put it somewhere very safe.",
                                "A grade 5 material: {material}. Logged with great care.",
                                "{Material} collected. That one is rare. I checked.",
                                "{Material}. The engineers will be delighted.",
                                "Grade 5 {material}. Lovely find, Commander.",
                                "{Material} in storage. Rare, precious, and accounted for."),
        },
    },
}
