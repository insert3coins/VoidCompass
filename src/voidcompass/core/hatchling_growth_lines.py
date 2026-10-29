"""5.6.8: small changes in a companion's outlook as it grows.

Adult forms are already earned by the pet's care and travels; these lines
only refer to that established history. The old form names are deliberately
not spoken as if the hatchling had chosen them itself.
"""

STAGE_LINES = {
    "hatchling": ("Everything is so big.", "Still learning this place."),
    "juvenile": ("I can reach further now.", "I'm getting bigger."),
    "adult": ("We've grown together.", "I've come a long way."),
}

FORM_LINES = {
    "thargoid": {
        "standard": ("Our ship is my home.", "I know its quiet now."),
        "explored": ("So many lights behind us.", "I remember the long way."),
        "scarred": ("The loud times passed.", "We held together through it."),
        "neglected": ("You're here with me again.", "There is light here still."),
        "rare": ("I remember the other signals.", "The quiet has many voices."),
    },
    "larva": {
        "standard": ("The pod feels like home.", "I know your ship now."),
        "explored": ("So many stars behind us.", "I remember the long way."),
        "scarred": ("The loud times passed.", "Still here. Still together."),
        "neglected": ("You're here again.", "I'm glad we stayed."),
        "rare": ("I remember those other lights.", "The quiet has a song."),
    },
    "bot": {
        "standard": ("Habitat checks complete.", "Companion duties understood."),
        "explored": ("Route memories retained.", "Many systems logged together."),
        "scarred": ("Old damage. Still operational.", "Survival routine: stay together."),
        "neglected": ("Restoration continues. Thank you.", "Reconnected. Staying close."),
        "rare": ("Discovery archive expanding.", "Many first finds logged."),
    },
    "sample": {
        "standard": ("I've made roots here.", "This little place is home."),
        "explored": ("So much light remembered.", "I grew beneath many stars."),
        "scarred": ("I kept growing through it.", "Even now, new growth."),
        "neglected": ("A little light again.", "I'm growing back, slowly."),
        "rare": ("So much life we've seen.", "I remember the discoveries."),
    },
}
