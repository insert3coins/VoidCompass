"""The Registry Field: Lyra learns how this commander wishes to be named."""
from voidcompass.overlays import companion_name

TITLE = "THE REGISTRY FIELD"
LINES = {
    "notice": (
        "Every ship's computer keeps a registry field for the commander. I have been filling yours with your rank. The journal also gives me a name: {name}. Rank is correct. I would like the field to be correct and kind, which is a higher standard.",
        "A small registry matter, Commander. My records say Commander. The journal says {name}. I lost a name once, in a hurry. I would rather not guess at yours.",
    ),
    "ask": (
        "So, for the registry: shall I call you {name}, keep Commander, or use another name you prefer? I will store it in a protected sector. I have one for important things.",
        "A direct question, Commander, so I get it right first time: {name}, Commander, or another name of your choosing?",
    ),
    "first": (
        "{called}. Registry updated, protected sector, two backups. I will use it from now on.",
        "Thank you, {called}. Stored where I keep the things I am never letting go of. There is plenty of room.",
    ),
    "commander": (
        "Commander it is. Registry confirmed. A rank is a fine name when it is the one you choose.",
        "Understood, Commander. The field stays as it is. I have locked it, so nothing overwrites it by accident.",
    ),
    "other": (
        "Of course. Say call me, then the name, or type it under YOUR NAME on my YOU page. I will update the registry the moment it arrives.",
        "A name of your own. Tell me, call me and the name, or enter it under YOUR NAME on the YOU page. Registry standing by.",
    ),
    "renamed": (
        "The journal now gives your name as {name}. It used to say {old}. I have updated the registry and kept the old entry too. I keep everything.",
        "Source change detected, Commander: {old} is now {name}. Registry updated. How I address you is still entirely your choice.",
    ),
}

ARC = companion_name.NameArc(title=TITLE, arc_key="lyra_arc", lines=LINES, prefix="registry")
