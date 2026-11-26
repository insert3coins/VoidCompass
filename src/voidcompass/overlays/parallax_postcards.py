"""Parallax's postcard hand: the ship's cat, keeping the views she approves of."""
from voidcompass.overlays import companion_postcards

SIGNATURE = "Parallax"
PLAIN = {
    "any": (
        "{place}. Approved.",
        "{place}. I watched this from the warm panel.",
        "A picture of {place}. I am not in it. I was watching.",
        "{place}. Things moved. I noticed.",
        "Captured at {place}. Good light. I would nap in it.",
        "{place}. Kept.",
        "{place}, from the cockpit glass. My glass.",
        "{place}. I have looked at this for a long time.",
    ),
    "first": (
        "{place}. Nobody saw it before us. I saw it before you.",
        "First at {place}. Ours. Mostly mine.",
        "{place}. A first. I sat on the scanner for it.",
    ),
    "rare": (
        "{place}: {kind}. Rare. My ears went forward.",
        "A {kind} at {place}. Uncommon. Like me.",
        "{place}. A {kind}. I stared for an hour.",
    ),
    "far": (
        "{place}, {far} light years from Sol. A wide baseline.",
        "{far} light years out. The stars have all shifted.",
        "Far out at {place}. I know exactly how far.",
    ),
    "home": (
        "{place}. Home. My usual spot.",
        "Back at {place}. Everything smells right.",
    ),
    "landed": (
        "On the ground at {place}. Level. I checked.",
        "{place}, from the surface. Still and quiet.",
        "We landed at {place}. I found the sunny side.",
    ),
    "docked": (
        "{place}. Docked. Lots of doors.",
        "Alongside at {place}. I counted the exits.",
        "{place}. Busy hangar. I watched it all.",
    ),
    "star": (
        "{place}. A very warm star.",
        "The star at {place}. I sat in its light.",
    ),
}
DRY = {
    "any": (
        "{place}. If you look closely, there is a cat-shaped smudge on the glass. That is a signature.",
        "Observation: {place}. Verdict: acceptable. That is the best verdict I give.",
        "{place}. I would like it known that I saw this first and did not make a fuss.",
        "A picture of {place}. I slow-blinked at it. That is how cats say thank you.",
        "{place}. Kept, because I liked it. I like very little. Treasure it.",
    ),
    "first": (
        "{place}. First on record. I would have put a paw print on it, but the probes are rude about paw prints.",
        "Nobody before us at {place}. Somebody had to be first. I prefer it to be me.",
    ),
    "rare": (
        "A {kind}. I have stopped pretending to be bored. Do not get used to it.",
        "{place}. Rare enough that my tail did something. I disown my tail.",
    ),
    "far": (
        "{far} light years out. The sky has rearranged itself. I watched it happen, jump by jump.",
        "{place}. Very far. I know exactly where my bowl is from here.",
    ),
    "landed": (
        "{place}. I have confirmed the ground is level. Then I went to sleep on it.",
    ),
    "docked": (
        "{place}. Docked. I have counted the exits and found a warm vent. You may now look at the view.",
    ),
    "star": (
        "{place}. Bright, warm and very close. My three favourite qualities in anything.",
    ),
}


def postcard_note(card, *, restrained=False, from_sol=None, state="", rng=None, recent=()):
    return companion_postcards.postcard_note(PLAIN, DRY, card, restrained=restrained, from_sol=from_sol,
                                             state=state, rng=rng, recent=recent)
