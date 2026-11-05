"""Axiom's keepsakes: capsules, constellations, anniversaries, overnight notes,
other commanders' companions, one request and the Captain's Log paragraph."""

PLAIN = {
    "capsule": ("A capsule from {span} ago, in {system}. You wrote: \"{note}\"",
                "Retrieved: your note from {system}, left {span} ago. \"{note}\"",
                "Observation from your past self, {span} old: \"{note}\""),
    "capsule_early": ("There is a capsule in {system}. It opens in {wait}.",
                      "A sealed capsule is here. Time remaining: {wait}.", "A capsule waits in {system}. It is sealed for another {wait}."),
    "capsule_shared": ("A capsule from {sender}, left here {span} ago: \"{note}\"",
                       "{sender} left this in {system}: \"{note}\"", "A message from {sender}, recorded {span} ago in {system}: \"{note}\""),
    "constellation_named": ("{count} stars. That is a constellation. I have named it {name}.",
                            "Constellation complete: {name}, {count} stars.", "New entry: constellation {name}, {count} stars."),
    "on_this_day": ("{ago} today, we were in {system}.", "{ago}, on this same date: {system}.", "Matching date, {ago}: we were in {system}."),
    "anniversary_us": ("{What}. I have checked the date. It is correct.", "{What}, Commander.", "{What}. Recorded."),
    "dream_told": ("From my overnight notes: {dream}", "While you were away I wrote this down: {dream}", "One overnight note: {dream}"),
    "watchers_meet": ("{Who}. Added to the catalogue.", "{Who}. A new entry, with a narrow error bar.", "{Who}. Observation recorded."),
    "companion_wish": ("I have a request, Commander, with no deadline: I would like to see {place}. In person.",
                       "If you are ever near one, I would like to visit {place}. My old catalogue never counted one properly.", "One request, Commander: {place}, whenever convenient."),
    "companion_wish_reached": ("{Place}. Thank you, Commander. I have taken more readings than strictly necessary.",
                               "We are at {place}. I am recording everything. Mostly for pleasure.", "{Place}. Request fulfilled. Thank you."),
}
VOICED = {
    "capsule": ("A capsule, recovered after {span}. Source: you. Location: {system}. Content: \"{note}\". I find time capsules very satisfying.",
                "{span} ago you sent a message to the future. It has arrived: \"{note}\". Delivery confirmed."),
    "capsule_early": ("A capsule in {system}, sealed for another {wait}. I have measured the wait. It is precise and unhelpful.",),
    "capsule_shared": ("Incoming observation from {sender}, left {span} ago in {system}: \"{note}\". A message across time. Excellent.",),
    "constellation_named": ("{count} stars, joined into one shape. I have named it {name}. I checked that nobody else had. Nobody had.",
                            "Constellation {name}: {count} stars, counted once each, as is proper."),
    "on_this_day": ("{ago} today, we were in {system}. Sorted by date, our history has a pleasing shape.",),
    "anniversary_us": ("{What}. I have recounted. It is still that number. I am pleased.",),
    "dream_told": ("Overnight, I reprocessed our last session. A finding: {dream}",),
    "watchers_meet": ("{Who}. Another light in the sky that comes and goes. I have classified it as a visitor.",),
    "companion_wish": ("A request, Commander. Optional, low priority, high personal significance: {place}. I would like to see one with my own sensors.",),
    "companion_wish_reached": ("{Place}. I have taken four hundred readings. I will take more. Thank you for bringing me.",),
}

FEELING = {"trust": ("CERTAINTY", ("uncertain", "confident", "certain")), "mood": ("OUTLOOK", ("cautious", "steady", "bright"))}
NOTES_TITLE = "OVERNIGHT NOTES"
NOTES = (
    "Reprocessed the session. Last position: {place}. One discrepancy: I enjoyed it more than the data justifies.",
    "Overnight finding: {thing}. Confidence high. Error bar honest.",
    "Sorted the session by time. The pattern ends at {place}. I would like to continue it.",
    "Recount complete. Everything present, including one extra light. That was us.",
    "Note: {thing}. I have filed it under remarkable, which is not a catalogue category. I made it one.",
    "We stopped at {place}. I counted the stars there twice. Both counts agree.",
    "Overnight I thought about {thing}. I do not know why. I have decided that is acceptable.",
    "Session closed at {place}. I kept the instruments warm. Just in case.",
)
WISH = {"kind": "black_hole", "after": "VI", "place": "a black hole", "how": "Any black hole: a star of class H"}
LOG = {
    "openings": ("Session record: {flown}, {start} to {end}.",
                 "{flown} of observations {when}, beginning at {start} and ending at {end}.",
                 "From {start} to {end}. Duration: {flown}. Consistent and complete.",
                 "{start}, then {end}. {flown} between them, all recorded."),
    "moments": {
        "firsts": "{firsts} first discoveries. New entries, every one of them ours.",
        "rare": "A rare observation {when}: {rare}. I counted it three times.",
        "far": "{distance} light years covered. The map is wider now.",
        "died": "We lost the ship {when}. You came back. I have recorded that part twice.",
        "credits": "{credits} credits. The arithmetic was in our favour.",
        "star": "{star} held us longest. I have marked it as {whens} star.",
        "quiet": "A quiet {part}. The absence of events is still data.",
    },
    "closings": ("Investigation continues.", "Session closed. Catalogue open.", "Until the next observation.",
                 "Confidence high. Error bar honest."),
}
