"""The officers' habit summaries in depth (5.7.6): more lines where they were
thin, and style lines that read right. ``{style}`` is a role with its article
("an explorer", "a trader"), so "you are {style}", never "leans towards {style}".

Fields as the Watcher's habit topics give them (watcher_habits.py)."""

# Replaces each officer's habit_style lines.
STYLE = {
    "aster": (
        ("The record suggests you are {style} at heart: {share} percent of your activity.",
         "By my figures you are mostly {style}, at {share} percent.",
         "{share} percent of your recorded work is that of {style}.",
         "The log reads like the record of {style}: {share} percent of it."),
        ("By the figures you are {style}, {share} percent of the time. Filed under preference, pending your next "
         "complete change of plan.",
         "The figures say {style}, at {share} percent. I shall refrain from ordering a commemorative plaque.",
         "{share} percent of our watches were spent as {style}. The paperwork has adapted accordingly.",
         "If the service record had to name you, it would say {style}. {share} percent, Commander.",
         "You fly as {style}, {share} percent of the time. It helps to know whom I am keeping the log for."),
    ),
    "axiom": (
        ("By activity, you are mostly {style}: {share} percent.",
         "{share} percent of our activity is that of {style}.",
         "Profile: {style}, {share} percent.",
         "You fly as {style}, {share} percent of the time."),
        ("By the numbers you are {style}: {share} percent of our activity. I like knowing what we are.",
         "{share} percent of what we do is the work of {style}. An observation, not a rule. You may change it any time.",
         "The data describes {style}, at {share} percent. I find the shape of it interesting.",
         "Statistically, you are {style}. {share} percent. The other percentages are interesting too.",
         "Pattern: {style}, {share} percent of our activity. The remainder is noise, or curiosity."),
    ),
    "meridian": (
        ("Mostly {style}, Commander: {share} percent.",
         "{share} percent of our work is that of {style}.",
         "By the log, you sail as {style}: {share} percent.",
         "The log has you down as {style}, {share} percent of the time."),
        ("The log has you down as {style}, {share} percent. I like knowing what kind of crew we are.",
         "{share} percent of our voyages were the work of {style}. An observation, not a rule.",
         "You sail as {style}, mostly. {share} percent. A fine trade.",
         "Every captain has a bent. Yours is {style}: {share} percent of the log.",
         "Call it {style}, {share} percent of the time. The rest is weather."),
    ),
    "lyra": (
        ("By activity, you are mostly {style}: {share} percent.",
         "{share} percent of our flying is that of {style}.",
         "Profile: {style}, {share} percent.",
         "Your logs read like {style}'s: {share} percent of them."),
        ("By the numbers you are {style}, {share} percent of the time. I like knowing what we are.",
         "{share} percent of our flying has been the work of {style}. Logged with approval.",
         "My records say {style}, at {share} percent. My first commander was a different sort. I like this sort.",
         "Statistically, you are {style}. {share} percent. And careful with fuel, one hundred percent.",
         "If the ship's registry had to describe you: {style}, {share} percent. I would add: good to fly with."),
    ),
}

# Added to each officer's habit topics: (plain, voiced).
MORE = {
    "aster": {
        "habit_flight": ((), ("{ly} light years in the log, Commander. I have begun numbering the pages twice to keep up.",
                              "{landings} landings. Each one entered with the time and, where possible, the weather.")),
        "habit_scans": ((), ("{firsts} first discoveries. The cartographers will want a word with you, and so shall I.",
                             "{bio} biological analyses. The genetic sampler has earned a commendation in my private notes.")),
        "habit_cargo": ((), ("{mined_n} tonnes of {mined}. I have started a separate ledger for it, out of respect.",
                             "The hold has carried {tonnes} tonnes of {commodity}. I could recite the manifest by now.")),
        "habit_combat": ((), ("{bonds} combat bonds. I record them faithfully, and hope for quieter entries.",
                              "{escaped} escapes from {interdicted} interdictions. Discretion, properly logged.")),
        "habit_trade": ((), ("{best} returned {best_cr} credits in a single trade. I underlined it.",
                             "Our trading profit stands at {profit} credits. The quartermaster in me is quietly delighted.")),
    },
    "axiom": {
        "habit_cargo": (("Most carried: {commodity}, {tonnes} tonnes.", "Mined: {mined}, {mined_n} tonnes."),
                        ("{commodity} leads the manifest at {tonnes} tonnes. I keep a histogram.",
                         "{mined_n} tonnes of {mined}. Each fragment logged by mass and time.")),
        "habit_trade": (("Top commodity sold: {sold}, {sold_t} tonnes.", "Profit to date: {profit} credits."),
                        ("{profit} credits of profit. The curve is going the right way.",
                         "{best} returned {best_cr} credits. An outlier, in the good direction.")),
    },
    "lyra": {
        "habit_cargo": (("Most carried: {commodity}, {tonnes} tonnes.", "Mined: {mined}, {mined_n} tonnes."),
                        ("{commodity} leads the manifest at {tonnes} tonnes. I know every crate.",
                         "{mined_n} tonnes of {mined}, refined and stowed. Good, steady work.")),
        "habit_trade": (("Top commodity sold: {sold}, {sold_t} tonnes.", "Profit to date: {profit} credits."),
                        ("{profit} credits of profit. A lovely, healthy reserve.",
                         "{best} returned {best_cr} credits. I remember the fuel we spent on it. Worth it.")),
    },
    "meridian": {
        "habit_cargo": (("Mostly {commodity} in the hold: {tonnes} tonnes.", "Mined so far: {mined_n} tonnes of {mined}."),
                        ("{tonnes} tonnes of {commodity} through the hold. She's carried it well.",
                         "{mined_n} tonnes of {mined} won from the rock. Good hauls, all of them.")),
        "habit_trade": (("Top cargo sold: {sold}, {sold_t} tonnes.", "Profit so far: {profit} credits."),
                        ("{profit} credits in profit. The voyage pays its own way and then some.",
                         "{best} brought in {best_cr} credits. A fair wind that day.")),
    },
}


def apply(identity, events, restrained):
    """Put the new style lines and the extra habit lines into an officer's banks."""
    plain, voiced = STYLE[identity]
    restrained["habit_style"] = tuple(plain)
    events["habit_style"] = tuple(plain) + tuple(voiced)
    for topic, (plain, voiced) in MORE.get(identity, {}).items():
        restrained[topic] = tuple(dict.fromkeys(restrained.get(topic, ()) + tuple(plain)))
        events[topic] = tuple(dict.fromkeys(events.get(topic, ()) + tuple(plain) + tuple(voiced)))
