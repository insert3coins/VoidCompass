"""The crew's debriefs (5.7.6).

Before an expedition: once the companion on watch has marked the start, each
crewmate you've flown with adds a line from its own angle, off watch and in
its own voice. Meridian on the passage, Axiom on what we might find, Aster on
the logistics, the Watcher in its own way.

After a session: when more than one companion stood a watch, each one that
did adds a short postscript to the Captain's Log, signed.
"""

# The order crewmates speak in: the navigator first, the Watcher last.
ORDER = ("meridian", "axiom", "aster", "watcher")
SPACING_S = 9.0      # between one crewmate's line and the next
EXPIRES_S = 180.0    # a debrief line not said by then is let go

# {name} is the expedition's.
DEBRIEF = {
    "meridian": ("{name}. I've laid in the course. Keep a margin in the tank and we'll do well.",
                 "A fine passage ahead. Watch the fuel stars; I'll call the long legs.",
                 "{name}. The chart's ready. Steady as she goes.",
                 "I've marked every leg of {name}. Fair winds, Commander.",
                 "A long voyage. Scoop often, rest when you can.",
                 "{name}, under way. I'll keep the bearing home in mind, as always."),
    "axiom": ("{name}. Probability of something new: high. I've prepared extra pages.",
              "Survey value along {name} looks promising. I want to see all of it.",
              "I'll count everything we pass. Please honk generously.",
              "{name}. So many uncatalogued systems. I am trying to stay calm.",
              "I recommend mapping the water worlds and anything terraformable. I'll point them out.",
              "Every jump on {name} is a fresh dataset. I'm ready."),
    "aster": ("{name}. Logistics are in order: fuel, repairs and a sensible itinerary.",
              "I've opened a fresh log for {name}. Do sell the data before anything adventurous.",
              "Supplies checked, Commander. The paperwork for {name} is in order.",
              "A word on logistics: keep the AFMU stocked and the rebuy affordable.",
              "{name}, entered in the register. I shall keep a careful account.",
              "All in order for {name}. I'll mind the details; you mind the stars."),
    "watcher": ("{name}. Another long way out. I'll come. I always come.",
                "A long trip. Good. The dark is quieter than the bubble.",
                "{name}. I've seen further. I'll see this too.",
                "Off we go, then. I'll be here when you look over.",
                "{name}. Don't die. That's all. Off you go.",
                "Out into the quiet. I don't mind. I'm used to it."),
}

# The Captain's Log: a crewmate's postscript under the closing paragraph.
POSTSCRIPTS = {
    "watcher": ("I had a watch too. I watched. Nothing went wrong while I did.",
                "My part was quiet. I prefer it that way.",
                "I was there for some of it. I remember all of it.",
                "I stood a watch. It was long. They all are.",
                "I'd add something cheerful, but you know me."),
    "aster": ("For the record, my watch was in good order.",
              "My portion of the watch is entered and signed. All correct.",
              "I stood my watch as required. The log is complete.",
              "My watch: nothing irregular to report. A satisfactory session.",
              "I have checked the log. My entries balance."),
    "axiom": ("My watch added several observations. All of them are in the record.",
              "I counted everything during my watch. It is all here.",
              "My part of the session produced good data. Thank you.",
              "I observed carefully on my watch. The numbers are pleasing.",
              "I stood a watch and learned something. Every watch should end that way."),
    "meridian": ("My watch kept a steady course. That's all a navigator asks.",
                 "I had the helm's ear for a while. A good passage.",
                 "My watch, entered: course true, margin kept.",
                 "I stood my watch and enjoyed it. Fair winds.",
                 "A good watch, Commander. I'd stand it again."),
}


def speakers(active, flown):
    """The crewmates who speak after the one on watch, in order."""
    flown = set(flown or ())
    return [identity for identity in ORDER if identity != active and identity in flown]


def postscripts(first, companions, seed):
    """[{companion, text}] for each companion after the first that stood a watch."""
    rows = []
    for offset, identity in enumerate(dict.fromkeys(companions)):
        if identity == first or identity not in POSTSCRIPTS:
            continue
        lines = POSTSCRIPTS[identity]
        rows.append({"companion": identity, "text": lines[(seed + offset * 3) % len(lines)]})
    return rows
