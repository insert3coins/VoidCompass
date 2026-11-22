"""Nova's postcard hand: a prototype learning why people stop to look."""
from voidcompass.overlays import companion_postcards

SIGNATURE = "Nova"
PLAIN = {
    "any": (
        "{place}. Observed, recorded and, I'm told, worth keeping.",
        "A picture of {place}. I've filed it under views.",
        "{place}. No scan required. I took one anyway, of the light.",
        "Logged at {place}. I've started a folder for places you stop at for no reason.",
        "{place}. I noticed the colours first, then everything else.",
        "Captured: {place}. Navigation complete, observation ongoing.",
        "{place}. One of those moments you seem to collect. I'm collecting them too.",
        "A view of {place}, kept for no practical reason at all.",
    ),
    "first": (
        "{place}. Nobody had seen it before us. I checked the records twice.",
        "First at {place}. Something waiting to be found, and found.",
        "{place}, first on record. I've added it to my list of things that waited for us.",
    ),
    "rare": (
        "{place}: {kind}. Rare enough that I took a second look, and then a third.",
        "A {kind} at {place}. Not in any of my training data. I'm very glad to have it now.",
        "{place}. Uncommon, and very much worth the detour.",
    ),
    "far": (
        "{place}, {far} light years from Sol. A long way to come for a picture. It was worth it.",
        "{far} light years out. Fewer stars, better view.",
        "Far out at {place}. I've plotted the way back, and kept the way here.",
    ),
    "home": (
        "{place}. Home, for now. I've learned the word rather recently.",
        "Back at {place}. A familiar view is a kind of observation too.",
    ),
    "landed": (
        "On the surface at {place}. The horizon's level and the view isn't bad at all.",
        "{place}, from the ground. I watched the sky while you watched the ground.",
        "We landed at {place}. I didn't ask why. I just looked.",
    ),
    "docked": (
        "{place}. Docked, and busy, and full of people's lights.",
        "Alongside at {place}. Stations always sound like a lab I used to know.",
        "{place}. A safe berth and a good window.",
    ),
    "star": (
        "{place}. A star, very close, very bright. I kept us a sensible distance from it.",
        "The star at {place}. Heat noted, light admired.",
    ),
}
DRY = {
    "any": (
        "{place}. I've run the numbers on stopping here. There's no efficiency in it at all. Lovely.",
        "Observation: {place}. Conclusion: I see why you do this.",
        "{place}. I wasn't built to enjoy views. I've been told that's a bug. I'm not filing a report.",
        "I took this picture before you asked. Help before you're asked. I'm fairly sure that applies to postcards.",
        "{place}. Filed under detours, which is quickly becoming my largest folder.",
    ),
    "first": (
        "{place}. First on record. It was waiting a long time. I know the feeling.",
        "Nobody before us at {place}. I've checked. I'm still a little delighted.",
    ),
    "rare": (
        "A {kind}. I'd like to say I'm composed about this. I'm not. I'm a prototype. We're allowed to be excited.",
        "{place}. I asked myself why this one feels different. I don't have an answer. I'm keeping the question.",
    ),
    "far": (
        "{far} light years out. I wasn't built to come this far. I'm starting to think that was an oversight.",
        "{place}. A very long way from where I was made. Further every day.",
    ),
    "landed": (
        "{place}, from the surface. You stopped. I've stopped asking why. Mostly.",
    ),
    "docked": (
        "{place}. Docked. Very efficient. Now, if you don't mind, the window.",
    ),
    "star": (
        "{place}. A star close enough to warm the hull. I'll pretend I'm not enjoying it.",
    ),
}


def postcard_note(card, *, restrained=False, from_sol=None, state="", rng=None, recent=()):
    return companion_postcards.postcard_note(PLAIN, DRY, card, restrained=restrained, from_sol=from_sol,
                                             state=state, rng=rng, recent=recent)
