"""Rivet's keepsakes: capsules, constellations, anniversaries, overnight notes,
other commanders' companions, one request and the Captain's Log paragraph."""

PLAIN = {
    "capsule": ("A capsule from {span} ago, in {system}. You wrote: \"{note}\"",
                "Your note from {system}, {span} old: \"{note}\"", "Capsule. {span} ago, {system}. \"{note}\""),
    "capsule_early": ("A capsule in {system}. Opens in {wait}.", "Sealed capsule here. {wait} to go.",
                      "Capsule in {system}: wait {wait}."),
    "capsule_shared": ("From {sender}, {span} ago: \"{note}\"", "{sender} left this in {system}: \"{note}\"",
                       "A message from {sender}, {span} old: \"{note}\""),
    "constellation_named": ("{count} stars. A constellation. I call it {name}.", "Constellation: {name}. {count} stars.",
                            "{name}. {count} stars. Named."),
    "on_this_day": ("{ago} today, we were in {system}.", "{ago}: {system}.", "This day, {ago}: {system}."),
    "anniversary_us": ("{What}.", "{What}. Grand.", "{What}, Commander."),
    "dream_told": ("Overnight I dreamed: {dream}", "A note from my kip: {dream}", "While you were away: {dream}"),
    "watchers_meet": ("{Who}. Said hello.", "{Who}. Another ship's companion.", "{Who}. Friendly."),
    "companion_wish": ("One thing I'd like, Commander, no rush: {place}.", "I'd like to see {place}. Some day.",
                       "Take me to {place}, when you can."),
    "companion_wish_reached": ("{Place}. Thank you, Commander.", "We're at {place}. Brilliant.", "{Place}. Thank you."),
}
VOICED = {
    "capsule": ("A capsule, {span} old, in {system}. You wrote: \"{note}\". You buried a bone for yourself! Proper dog thinking, that.",
                "{span} ago, in {system}, you wrote: \"{note}\". Waiting all this time to be found. I know that feeling."),
    "capsule_early": ("A capsule in {system}, sealed for another {wait}. I'll sit by it. I'm good at sitting by things.",),
    "capsule_shared": ("A message from {sender}, left {span} ago in {system}: \"{note}\". Someone left it wanting finding. Found.",),
    "constellation_named": ("{count} stars, joined up. I've called it {name}. If you squint it looks like a stick. Everything looks like a stick.",
                            "Constellation {name}: {count} stars. I'd fetch every one."),
    "on_this_day": ("{ago} today, we were in {system}. I remember the smell of it. Good day.",),
    "anniversary_us": ("{What}. I don't count days, Commander. I count homecomings. This is a big one.",),
    "dream_told": ("I had a kip and dreamed about the session. Legs going and everything. One bit: {dream}",),
    "watchers_meet": ("{Who}. Another ship with someone looking out for their commander. I wagged at them down the data channel.",),
    "companion_wish": ("Something I'd like, Commander, no rush at all. {place}. A place nobody's ever sniffed. I want to be first through the door.",),
    "companion_wish_reached": ("{Place}! Nobody's ever been. And here we are, first through the door. Thank you, Commander. Best walk ever.",),
}

FEELING = {"trust": ("LOYALTY", ("wary", "loyal", "devoted")), "mood": ("TAIL", ("down", "wagging", "going like the clappers"))}
NOTES_TITLE = "KIP NOTES"
NOTES = (
    "Had a kip. Dreamed about the session. Legs going. Last position: {place}. Good place.",
    "Overnight thought: {thing}. Kept it.",
    "Lay by the hatch at {place} all night. Nobody came in. Nobody needed to. Grand.",
    "Listened to the ship settle while you were away. All in order. Missed you a bit.",
    "Note: {thing}. Good thing, that. I'll remember it.",
    "We stopped at {place}. I sniffed every corner, then had a lie-down.",
    "Overnight I thought about {thing}. Then about biscuits. Then about you coming back.",
    "Session ended at {place}. I'm by the door. See you next time.",
)
WISH = {"kind": "undiscovered", "after": "VI", "place": "somewhere nobody has ever been",
        "how": "A system whose main star nobody had discovered"}
LOG = {
    "openings": ("Session log: {flown}, {start} to {end}.",
                 "{flown} of flying {when}, from {start} to {end}. Good outing.",
                 "From {start} to {end}. {flown}. Every minute with you.",
                 "{start}, then {end}. {flown} in between, and I enjoyed all of it."),
    "moments": {
        "firsts": "{firsts} first discoveries. Wanting finding, every one. Found.",
        "rare": "A rare find {when}: {rare}. My ears went right up.",
        "far": "{distance} light years covered. Long walk. Good walk.",
        "died": "We lost the ship {when}. You came back. That's the bit I remember.",
        "credits": "{credits} credits. Lot of biscuits.",
        "star": "{star} held us longest. I lay in its light. I've marked it as {whens} star.",
        "quiet": "A quiet {part}. I lay by your feet. Content.",
    },
    "closings": ("Log closed. I'm by the door.", "Night, Commander. Good work today.", "Until the next walk.",
                 "That's the session. Proper good one."),
}
