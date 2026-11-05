"""Aster's postcard hand: the officer's account of a place worth keeping."""
from voidcompass.overlays import companion_postcards


SIGNATURE = "Aster"
PLAIN = {
    "any": (
        "{place}. A place in the voyage, and now a place in the record.",
        "I have kept this view of {place}. The coordinates alone would be an incomplete account.",
        "An image for the second ledger. Some details deserve more room than a column.",
        "This belongs among the things we chose to notice.",
        "The itinerary brought us here. We made time to look.",
        "{place}, recorded for the crew rather than the accounts.",
        "A brief pause in the duties of the watch. I am glad we took it.",
        "There is room in the log for a view with no immediate purpose.",
    ),
    "first": (
        "A first entered in the journal at {place}. The image keeps something the entry cannot.",
        "The record marks a first here. I have left room beside it for the view.",
        "{place}. A first in the survey record, and a moment worth keeping.",
        "A new first for our voyage. Recorded carefully; remembered with rather more pleasure.",
    ),
    "rare": (
        "A {kind} at {place}. A worthwhile addition to both the survey and the album.",
        "{place}, a {kind}. The description is accurate; the image is more persuasive.",
        "A {kind}. I have made room for it beyond the survey figures.",
        "This {kind} deserved a pause in the itinerary. Arrival duly appreciated.",
    ),
    "far": (
        "{far} light years from Sol. The voyage account has acquired a considerable reach.",
        "{place}, {far} light years from Sol. A place worth recording at the end of a long passage.",
        "{region}. The route is long; the small pauses still belong in its account.",
        "A view from {far} light years out. Distance gives the arrival column some perspective.",
    ),
    "home": (
        "Near Sol. Familiar space still deserves a fresh entry in the album.",
        "Close to Sol again. A return can be as much a part of the voyage as a departure.",
        "{place}, in familiar space. I have kept the view alongside the more distant arrivals.",
        "A view near Sol, retained for this watch. Familiarity need not mean we cease to notice.",
    ),
    "landed": (
        "On the surface at {place}. The arrival report benefits from a little ground beneath it.",
        "{place}, from the ground. A different scale for the voyage account.",
        "A surface view worth keeping. The route can wait for the next departure.",
        "Here on {place}, we made room in the watch to look around.",
    ),
    "docked": (
        "Alongside. A pause between passages belongs in the record too.",
        "In port for this view. A voyage includes the time between departures.",
        "A berth, a view, and room for the next entry. I consider that a sound arrangement.",
        "A moment in port, kept for the crew. The departure column can remain blank a little longer.",
    ),
    "star": (
        "{place}. A striking entry in the watch, kept beyond its navigation coordinates.",
        "A view of {place}. The charts provide its position; this keeps its presence.",
        "The object at {place}, given room beyond the navigation entry.",
        "A landmark along the route. I have kept the image with our other arrivals.",
    ),
}

DRY = {
    "any": (
        "{place}. I have filed this under reasons to look up from the manifest.",
        "No cargo discrepancy, no revised schedule. A remarkably agreeable report.",
        "A scenic use of archival space. I shall defend the allocation if challenged.",
        "This view has no duty assignment. I find that rather refreshing.",
    ),
    "first": (
        "A first at {place}. The journal is entitled to a small degree of professional pride.",
        "The record says first. I have resisted adding an exclamation mark to an official entry.",
    ),
    "rare": (
        "A {kind}. Even the inventory would benefit from a picture on this occasion.",
        "{place}. The phrase {kind} is doing rather less work than the view.",
    ),
    "far": (
        "{far} light years from Sol. A substantial journey for something that fits on a postcard.",
        "{region}. The return column has requested additional stationery.",
    ),
    "home": (
        "Near Sol. The album has room for places with a shorter supporting travel report.",
        "Familiar space. I have declined to mark the view as a duplicate.",
    ),
    "landed": (
        "{place}. The ground has made a convincing case for remaining still while photographed.",
        "A surface posting, briefly. No office has been requested.",
    ),
    "docked": (
        "Alongside. The schedule has been asked to wait while we appreciate the lighting.",
        "A port watch with a view. An agreeable amendment to the duty roster.",
    ),
    "star": (
        "{place}. The navigation account has acquired a rather dramatic illustration.",
        "A portrait for the charts. I shall omit the exposure from the crew's performance review.",
    ),
}


def postcard_note(card, *, restrained=False, from_sol=None, state="", rng=None, recent=()):
    """Use true context and rotate templates through Aster's persisted picker."""
    return companion_postcards.postcard_note(PLAIN, DRY, card, restrained=restrained, from_sol=from_sol,
                                             state=state, rng=rng, recent=recent)
