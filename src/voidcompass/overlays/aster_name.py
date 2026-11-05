"""The Crew Register: Aster learns how this commander wishes to be known."""
from voidcompass.overlays import companion_name

TITLE = "THE CREW REGISTER"
UNLOCK_HOURS = .25
SETTLE_S = 120
GAP_S = 180
ORDER = companion_name.ORDER

LINES = {
    "notice": (
        "A manifest officer learns to put the names before the numbers. The journal gives me yours: {name}. On this posting, I should rather like to know the person behind the command chair.",
        "The crew register has your name, {name}, beside your rank. An accurate entry, but a brief one. I am learning that serving with someone means rather more than keeping their details in order.",
    ),
    "ask": (
        "The register says {name}, but a crew gets to choose how it is known. May I use your name, keep Commander, or call you something you prefer?",
        "A small matter for our crew register. Would you like me to call you {name}, retain Commander, or use a name of your own choosing?",
    ),
    "first": (
        "{called}, then. I shall use that in our reports as well. Here aboard this ship, it is good to know the person I am serving with.",
        "Very well, {called}. Your entry in my register is in order. I rather prefer a crew made of people to one made entirely of titles.",
    ),
    "commander": (
        "Commander, then. A title can be a proper choice as well. The register is yours; I shall keep it that way.",
        "Of course, Commander. The form of address is your decision. We need no further ceremony over it.",
    ),
    "other": (
        "Certainly. Tell me, call me followed by the name you prefer, or enter it under YOUR NAME on my YOU page. I shall amend the register.",
        "A name of your choosing. Say call me and the name, or write it under YOUR NAME on my YOU page. I shall take the entry from you.",
    ),
    "renamed": (
        "The journal now gives your name as {name}, where it previously said {old}. I have amended the crew register. Your preferred form of address remains your decision.",
        "A change in the register, Commander: {old} is now {name}. I shall keep the record current and leave the choice of address with you.",
    ),
}


ARC = companion_name.NameArc(title=TITLE, arc_key="aster_arc", lines=LINES, prefix="crew",
                             unlock_hours=UNLOCK_HOURS, settle_s=SETTLE_S, gap_s=GAP_S)
record, words, heading, page = ARC.record, ARC.words, ARC.heading, ARC.page
format_words, response, spoken = companion_name.format_words, companion_name.response, companion_name.spoken
