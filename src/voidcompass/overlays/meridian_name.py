"""The Ship's Articles: Meridian learns how this commander wishes to be addressed."""
from voidcompass.overlays import companion_name

TITLE = "THE SHIP'S ARTICLES"
LINES = {
    "notice": (
        "In the old fleets, every crew signed the ship's articles: a name, a rank and a mark. I have read yours from the journal, Commander. It says {name}. An old navigator likes to know the name of the person he is steering for, as well as the rank.",
        "An old captain of mine used to say that a crew which knew each other's names held formation better. The journal tells me yours is {name}. I have been calling you by your rank. That is correct. I am not certain it is complete.",
    ),
    "ask": (
        "So, for the ship's articles: may I call you {name}, would you rather I kept to Commander, or is there another name you prefer? Any of the three is perfectly proper.",
        "A question I should have asked at the start of the voyage. Shall I address you as {name}, keep Commander, or use a name of your own choosing?",
    ),
    "first": (
        "{called}, then. Entered in the articles. I shall use it from now on, in reports as well as in conversation. It is good to know whom I am steering for.",
        "Very good, {called}. The articles are in order. A crew of two still deserves its proper names.",
    ),
    "commander": (
        "Commander it is. A rank honestly held is a fine name to answer to. The articles stand as they are.",
        "Of course, Commander. Some captains prefer the rank. I have never thought less of one for it.",
    ),
    "other": (
        "Certainly. Say call me, then the name you prefer, or write it under YOUR NAME on my YOU page. I shall enter it in the articles.",
        "A name of your choosing. Tell me, call me and the name, or enter it under YOUR NAME on the YOU page. I am ready to write it down.",
    ),
    "renamed": (
        "The journal now records your name as {name}, where it once said {old}. I have amended the ship's articles. How you are addressed remains your choice.",
        "An amendment to the articles, Commander: {old} is now {name}. Your preferred form of address is unchanged.",
    ),
}

ARC = companion_name.NameArc(title=TITLE, arc_key="meridian_arc", lines=LINES, prefix="articles")
