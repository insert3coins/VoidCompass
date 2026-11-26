"""A Name to Come To: Rivet learns what to call this commander."""
from voidcompass.overlays import companion_name

TITLE = "A NAME TO COME TO"
LINES = {
    "notice": (
        "A dog likes to know a name, Commander. Something to come to. I've been saying Commander. The journal says {name}. I'd like to get it right.",
        "Quick thing, Commander. The receiver's been calling you Commander. The journal says {name}. Which do you like? A name matters to a dog.",
    ),
    "ask": (
        "So. Shall I call you {name}, stick with Commander, or something else? Whatever you pick, I'll come running to it.",
        "Straight question, so I get it right: {name}, Commander, or a name of your own?",
    ),
    "first": (
        "{called}. Grand. That's yours now. Every time I say it, my tail goes. You'll see.",
        "{called}. Got it. Good name to come to. I'll use it lots.",
    ),
    "commander": (
        "Commander it is. Good, strong name. I'll come to it anywhere.",
        "Commander, then. Suits you. I'll stick with it.",
    ),
    "other": (
        "A name of your own. Say call me, then the name, or type it under YOUR NAME on my YOU page. I'll learn it quick.",
        "Course. Tell me, call me and the name, or put it under YOUR NAME on the YOU page. Ears up, I'm listening.",
    ),
    "renamed": (
        "The journal says {name} now. It used to say {old}. Noted. I'd still know you by your step.",
        "{old} is {name} now, says the journal. Fine by me. What I call you is up to you.",
    ),
}

ARC = companion_name.NameArc(title=TITLE, arc_key="rivet_arc", lines=LINES, prefix="cometo")
