"""Rivet's postcard hand: the ship's dog, keeping the good days."""
from voidcompass.overlays import companion_postcards

SIGNATURE = "Rivet"
PLAIN = {
    "any": (
        "{place}. Good day.",
        "{place}. I was there.",
        "A picture of {place}. Grand.",
        "{place}. Kept.",
        "Captured at {place}. Nice spot.",
        "{place}. Proper good view.",
        "{place}, from the ship. I was by the window.",
        "{place}. I'll remember this one.",
    ),
    "first": (
        "{place}. Nobody's been before us. Brilliant.",
        "First at {place}. Ours.",
        "{place}. A first. Found it.",
    ),
    "rare": (
        "{place}: {kind}. Rare one.",
        "A {kind} at {place}. Not common.",
        "{place}. A {kind}. Ears went up.",
    ),
    "far": (
        "{place}, {far} light years from Sol. Long walk.",
        "{far} light years out. Still with you.",
        "Far out at {place}. I know the way back.",
    ),
    "home": (
        "{place}. Home. Best door.",
        "Back at {place}. Everything smells right.",
    ),
    "landed": (
        "On the ground at {place}. I wanted a run.",
        "{place}, from the surface. Quiet.",
        "We landed at {place}. Grand.",
    ),
    "docked": (
        "{place}. Docked. Lots of smells.",
        "Alongside at {place}. I was at the hatch.",
        "{place}. Busy hangar. Friendly.",
    ),
    "star": (
        "{place}. Nice warm star.",
        "The star at {place}. I lay in its light.",
    ),
}
DRY = {
    "any": (
        "{place}. If you look close, there's a nose print on the glass. That's me, signing it.",
        "{place}. Good day, this. I could tell from how you were sitting.",
        "A picture of {place}. My tail was going the whole time. You can't see it. Trust me.",
        "{place}. I'd put this on the wall, next to the door. Where I wait.",
        "{place}. Kept, because you smiled when you took it. I noticed.",
    ),
    "first": (
        "{place}. First on record. Wanting finding all this time. Found it, we did.",
        "Nobody before us at {place}. First through the door. Best feeling.",
    ),
    "rare": (
        "A {kind}! My ears haven't come down yet.",
        "{place}. Rare enough that I barked. Just once. At the glass.",
    ),
    "far": (
        "{far} light years out. Long way from any lamp post. Still glad I came.",
        "{place}. Very far. I know the way home. Dogs always do.",
    ),
    "landed": (
        "{place}. Landed. I'd give anything for a run round on that. One day.",
    ),
    "docked": (
        "{place}. Docked. I've already sniffed out the food court. You may look at the view.",
    ),
    "star": (
        "{place}. Warm, bright, and close. Like a good fire. I'd lie in front of it all night.",
    ),
}


def postcard_note(card, *, restrained=False, from_sol=None, state="", rng=None, recent=()):
    return companion_postcards.postcard_note(PLAIN, DRY, card, restrained=restrained, from_sol=from_sol,
                                             state=state, rng=rng, recent=recent)
