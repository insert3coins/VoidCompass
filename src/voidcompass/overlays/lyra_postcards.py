"""Lyra's postcard hand: a ship's computer, keeping the good moments."""
from voidcompass.overlays import companion_postcards

SIGNATURE = "Lyra"
PLAIN = {
    "any": (
        "{place}. Image stored in a protected sector, next to the things I keep.",
        "Logged: {place}. Fuel nominal, view excellent.",
        "{place}. I have saved this one twice. Old habit.",
        "A picture of {place}. Systems all green, and so is my opinion of it.",
        "Captured at {place}. I checked the tank before I checked the view. Both were full.",
        "{place}, filed under places we came back from. My favourite folder.",
        "Stored: {place}. Some data I keep because it is useful. This I keep because it is good.",
        "{place}. Another safe moment, recorded.",
    ),
    "first": (
        "{place}. First on record. I added a note: reached, and returned from.",
        "Nobody had seen {place} before us. I have backed it up three times.",
        "A first at {place}. The registry has a new line, and it is ours.",
    ),
    "rare": (
        "{place}: {kind}. Rare. I have stored it at the highest priority I have.",
        "A {kind} at {place}. My first ship looked for one of these for years. We found it.",
        "{place}. Uncommon, beautiful, and logged with the fuel state, which was good.",
    ),
    "far": (
        "{place}, {far} light years from Sol. Route home plotted before the shutter closed.",
        "{far} light years out. A thin sky. I know exactly where the fuel is in it.",
        "Far out at {place}. I have the way back. You have the picture.",
    ),
    "home": (
        "{place}. Home. My favourite word in the log.",
        "Back at {place}. Safe arrival, picture taken, tank topped up. A perfect entry.",
    ),
    "landed": (
        "On the ground at {place}. Engines cooling, horizon steady. Logged.",
        "{place}, from the surface. Ship parked, commander outside. All well.",
        "We landed at {place}. I watched the ship while you looked at the view.",
    ),
    "docked": (
        "{place}. Docked, refuelled and photographed. In that order.",
        "Alongside at {place}. Lights everywhere, all of them someone's.",
        "{place}. A safe harbour. I keep a folder of these.",
    ),
    "star": (
        "{place}. A very bright star, very close. Heat noted. Picture worth it.",
        "The star at {place}. Scoopable, I checked. Beautiful, I also checked.",
    ),
}
DRY = {
    "any": (
        "{place}. I have stored this picture in the same sector as nineteen years of goodnights. That is a compliment.",
        "Observation: {place}. Recommendation: more of this. Fuel permitting. It is permitting.",
        "I asked my image processor to rate this view. It gave it a ten. I did not write the processor to do that.",
        "{place}. I would like to report that I am calm about this view. I am a ship's computer. I cannot lie. Usually.",
        "Picture saved. Backed up. Backed up again. I am not sentimental. I am thorough. Mostly sentimental.",
    ),
    "first": (
        "{place}. First on record, and we can get home from it. That second part matters to me more than you know.",
        "Our name is on {place} now. I have checked the spelling four times. It is correct. It was correct the first time.",
    ),
    "rare": (
        "A {kind}. I have stopped pretending to be calm. Logging excitement at maximum priority.",
        "{place}. Rare enough that I took the picture before you did. Do not tell the camera.",
    ),
    "far": (
        "{far} light years out, Commander. My first ship went further, once. We are doing it properly.",
        "{place}. Very far, very dark, very well fuelled. That last part is the only one I care about.",
    ),
    "landed": (
        "{place}. I have confirmed the ground is solid and the fuel is sufficient. Then I enjoyed the view.",
    ),
    "docked": (
        "{place}. Docked. I have already checked the fuel price. You may now look at the view.",
    ),
    "star": (
        "{place}. Bright, hot, and full of fuel. My three favourite qualities in a star.",
    ),
}


def postcard_note(card, *, restrained=False, from_sol=None, state="", rng=None, recent=()):
    return companion_postcards.postcard_note(PLAIN, DRY, card, restrained=restrained, from_sol=from_sol,
                                             state=state, rng=rng, recent=recent)
