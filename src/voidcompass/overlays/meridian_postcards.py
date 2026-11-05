"""Meridian's postcard hand: a navigator's note in the margin of the log."""
from voidcompass.overlays import companion_postcards

SIGNATURE = "Meridian"
PLAIN = {
    "any": (
        "{place}. Position fixed, view noted. A good place to have been.",
        "Entered in the log at {place}. Some positions deserve a picture as well as coordinates.",
        "{place}. We paused here. I am glad we did.",
        "A navigator's note: {place}, fair weather, all well aboard.",
        "Not every stop needs a reason. This one has a good one: the view.",
        "{place}. Another line in a long voyage, and one of the better ones.",
        "We marked {place} on the chart, and then we looked at it properly.",
        "Fair skies at {place}. Worth the detour.",
    ),
    "first": (
        "{place}. First to come here. The chart begins with us.",
        "Nobody had sounded {place} before. Now someone has.",
        "{place}, first on record. Old explorers would have raised a glass.",
    ),
    "rare": (
        "{place}: {kind}. Rare waters. I have marked them carefully.",
        "A {kind} at {place}. An old survey fleet would have stopped for a week.",
        "{place}. Uncommon, and well worth the voyage.",
    ),
    "far": (
        "{place}, {far} light years from Sol. Deep water. Steady hands.",
        "{far} light years out. A long way from the harbour, and the ship is well.",
        "{place}. Far from home. Not lost.",
    ),
    "home": (
        "{place}. Home port. The best entry in any log.",
        "Back at {place}. Landfall, as we used to say.",
    ),
    "landed": (
        "Ashore at {place}. Solid ground and a long horizon.",
        "{place}, from the surface. A navigator's view, for once.",
        "We put down at {place}. Good holding ground.",
    ),
    "docked": (
        "{place}. Alongside, all well. A harbour is a fine thing.",
        "In port at {place}. Lights, noise, and a moment's rest.",
        "{place}. Moored safely. The voyage can wait.",
    ),
    "star": (
        "{place}. A star, close enough to feel. We kept a careful distance.",
        "The light at {place} is fierce. A fine sight, at a sensible range.",
    ),
}
DRY = {
    "any": (
        "{place}. A strict commodore would call this an unnecessary stop. She would have taken the photograph anyway.",
        "Position: {place}. Weather: excellent. Navigator's mood: improving.",
        "I have entered {place} in the log with a note that we lingered. I am not sorry.",
        "{place}. Old navigators keep a few pictures for the long watches. This will be one of mine.",
        "A view to steer by, {place}. Recorded for the next long night.",
    ),
    "first": (
        "{place}. First. I checked the figures by hand, for old times' sake. They are good.",
        "Our name on {place}. Well sounded, Commander.",
    ),
    "rare": (
        "A {kind}. I have resisted underlining it in the log. Twice.",
        "{place}. Rare enough that I am tempted to write landfall. I shall restrain myself.",
    ),
    "far": (
        "{far} light years out and the margins are sound. That is the whole art, really.",
        "{place}. Any old fleet would have envied us this. Quietly. Fleets are a dignified lot.",
    ),
    "landed": (
        "{place}. Good ground. An old sailor would want to know whether it was sandy.",
    ),
    "docked": (
        "{place}. In harbour. Every good voyage needs one.",
    ),
    "star": (
        "{place}. Magnificent, and a respectful distance away. I approve of both.",
    ),
}


def postcard_note(card, *, restrained=False, from_sol=None, state="", rng=None, recent=()):
    return companion_postcards.postcard_note(PLAIN, DRY, card, restrained=restrained, from_sol=from_sol,
                                             state=state, rng=rng, recent=recent)
