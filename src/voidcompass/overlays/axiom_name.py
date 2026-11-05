"""The Observer Field: Axiom learns how this commander wishes to be named."""
from voidcompass.overlays import companion_name

TITLE = "THE OBSERVER FIELD"
LINES = {
    "notice": (
        "Every observation in a catalogue records who made it. There is a field for it: observer. Since I came aboard, I have been filling it with your rank. The journal also gives me a name: {name}. Rank is accurate. I am not sure it is complete.",
        "I have a small data-quality concern, Commander. In my records, the observer field says Commander. The journal says {name}. Both are true. I would like the entry to be the one you prefer, rather than the one I happened to read first.",
    ),
    "ask": (
        "For the observer field, then: shall I call you {name}, keep Commander, or use another name you prefer? I will record the answer exactly. I am very good at that part.",
        "A direct question, so I do not have to estimate. May I call you {name}, would you rather I kept Commander, or is there another name you would like me to use?",
    ),
    "first": (
        "{called}. Recorded. I will use it from now on, in reports as well as conversation. The observer field is complete. That is a rarer outcome than you might think.",
        "Thank you, {called}. Entry updated, confidence high. I find a catalogue is much easier to love when the observer has a name.",
    ),
    "commander": (
        "Commander it is. Recorded exactly as requested. A rank is a perfectly good name if it is the one you choose.",
        "Understood, Commander. The observer field stays as it is. I checked: there is no rule that says it has to change.",
    ),
    "other": (
        "Of course. Say call me, then the name, or type it under YOUR NAME on my YOU page. I will update the observer field when it arrives.",
        "A name of your own choosing. Tell me, call me and the name, or enter it under YOUR NAME on the YOU page. I am ready to record it.",
    ),
    "renamed": (
        "The journal now gives your name as {name}. It used to say {old}. I have corrected the observer field. How I address you is still your choice.",
        "A change in the source data, Commander: {old} is now {name}. Record updated. Your preferred form of address has not been touched.",
    ),
}

ARC = companion_name.NameArc(title=TITLE, arc_key="axiom_arc", lines=LINES, prefix="observer")
