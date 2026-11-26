"""What the Cat Calls You: Parallax decides how this commander is named."""
from voidcompass.overlays import companion_name

TITLE = "WHAT THE CAT CALLS YOU"
LINES = {
    "notice": (
        "Cats do not use names, Commander. We use looks. The collar insists on names, though, and the journal says yours is {name}. I have been calling you the commander. I could do better.",
        "A small matter. The collar keeps calling you Commander. The journal says {name}. I have not decided which suits you. I would like you to decide, which is unusual for me.",
    ),
    "ask": (
        "So. Shall I call you {name}, keep Commander, or something else you like better? Choose carefully. I will use it forever.",
        "A direct question, which I rarely ask: {name}, Commander, or another name of your own?",
    ),
    "first": (
        "{called}. Good. The collar has it now. I will use it when I am pleased with you, which is more often than I let on.",
        "{called}. Stored. That is a good name to say slowly, with your eyes half closed. I will.",
    ),
    "commander": (
        "Commander, then. It suits you. Rank is a kind of territory. I understand territory.",
        "Commander it is. I will keep it. I like a name that does not change.",
    ),
    "other": (
        "Your own name, then. Say call me, then the name, or type it under YOUR NAME on my YOU page. The collar will learn it.",
        "Of course. Tell me, call me and the name, or put it under YOUR NAME on the YOU page. I will be listening. I always am.",
    ),
    "renamed": (
        "The journal calls you {name} now. It used to say {old}. I have noted it. Cats notice when things move.",
        "{old} is {name} now, says the journal. Noted. What I call you is still yours to choose.",
    ),
}

ARC = companion_name.NameArc(title=TITLE, arc_key="parallax_arc", lines=LINES, prefix="callname")
