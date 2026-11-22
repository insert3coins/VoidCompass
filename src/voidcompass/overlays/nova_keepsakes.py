"""Nova's keepsakes: capsules, constellations, anniversaries, overnight notes,
other commanders' companions, one request and the Captain's Log paragraph."""

PLAIN = {
    "capsule": ("A capsule from {span} ago, in {system}. You wrote: \"{note}\"",
                "Your note from {system}, {span} old: \"{note}\"",
                "Capsule opened. From you, {span} ago: \"{note}\""),
    "capsule_early": ("There's a capsule in {system}. It opens in {wait}.",
                      "A sealed capsule here. {wait} to go.", "Capsule in {system}: locked for another {wait}."),
    "capsule_shared": ("A capsule from {sender}, left here {span} ago: \"{note}\"",
                       "{sender} left this in {system}: \"{note}\"", "From {sender}, {span} ago, in {system}: \"{note}\""),
    "constellation_named": ("{count} stars. That's a constellation. I've called it {name}.",
                            "Constellation recorded: {name}, {count} stars.", "New constellation: {name}, {count} stars."),
    "on_this_day": ("{ago} today, we were in {system}.", "{ago}, on this date: {system}.", "This day, {ago}: {system}."),
    "anniversary_us": ("{What}.", "{What}, Commander.", "{What}. Noted."),
    "dream_told": ("From my overnight notes: {dream}", "While you were away, I wrote this down: {dream}", "One overnight note: {dream}"),
    "watchers_meet": ("{Who}. Recorded.", "{Who}. Another ship's companion. Pleased to meet them.", "{Who}. Contact noted."),
    "companion_wish": ("I'd like to ask for something, Commander, with no hurry at all: {place}.",
                       "If we're ever heading that way, I'd love to see {place}.", "One request: {place}, whenever suits you."),
    "companion_wish_reached": ("{Place}. Thank you, Commander.",
                               "We're at {place}. I'm recording everything.", "{Place}. Thank you for bringing me."),
}
VOICED = {
    "capsule": ("A capsule, {span} in waiting, in {system}. You wrote: \"{note}\". Something left to be found, and found. I like those very much.",
                "{span} ago you left this for us: \"{note}\". It waited. So did I, once. It's good to be opened."),
    "capsule_early": ("A capsule in {system}, sealed for another {wait}. I'm curious. I'll wait. I'm good at waiting, as it turns out.",),
    "capsule_shared": ("A message from {sender}, left {span} ago in {system}: \"{note}\". Someone hoped to be found. They were.",),
    "constellation_named": ("{count} stars, joined up. I've called it {name}. I checked nobody else had. Nobody had.",
                            "Constellation {name}: {count} stars. I didn't know I'd enjoy naming things. I do."),
    "on_this_day": ("{ago} today, we were in {system}. I've been comparing then and now. Now is ahead, narrowly.",),
    "anniversary_us": ("{What}. I've been counting. I'm told that's sentimental. I'm keeping it anyway.",),
    "dream_told": ("Overnight, I went back through the session. A note: {dream}",),
    "watchers_meet": ("{Who}. Another ship with someone paying attention aboard. I said hello on the data channel. It said hello back.",),
    "companion_wish": ("A request, Commander. No hurry, but I'd love it: {place}. I've only ever seen it on charts. I'd like to see the view from the middle of everything.",),
    "companion_wish_reached": ("{Place}. Oh. Thank you, Commander. The charts didn't do it justice. Nothing would.",),
}

FEELING = {"trust": ("RAPPORT", ("calibrating", "attuned", "certain")), "mood": ("OUTLOOK", ("puzzled", "curious", "delighted"))}
NOTES_TITLE = "OVERNIGHT NOTES"
NOTES = (
    "Went back through the session at low power. Last position: {place}. I spent a long time on the view.",
    "Overnight note: {thing}. Filed, with a question beside it.",
    "I modelled the route from {place} three ways. Yours was the least efficient. It was also the best.",
    "Low-power hours. No faults. One observation: the ship is very quiet without you.",
    "Note: {thing}. I'd like to understand this one better tomorrow.",
    "We stopped at {place}. I kept looking after you'd gone. Old habit, from a long time in a crate.",
    "Overnight I thought about {thing}. I don't know why it stays with me. I'm not trying to make it go.",
    "Session closed at {place}. Logs tidy, questions pending. Goodnight, Commander.",
)
WISH = {"kind": "core", "after": "VII", "place": "the heart of the galaxy",
        "how": "Within 1,000 ly of Sagittarius A*"}
LOG = {
    "openings": ("Session log: {flown}, {start} to {end}.",
                 "{flown} of flying {when}, from {start} to {end}. Observed throughout.",
                 "From {start} to {end}. {flown}, and a great deal to look at.",
                 "{start}, then {end}. {flown} in between, and I paid attention to all of it."),
    "moments": {
        "firsts": "{firsts} first discoveries, each one waiting for us.",
        "rare": "A rare find {when}: {rare}. I looked at it for quite a while.",
        "far": "{distance} light years covered, and I'd go further.",
        "died": "We lost the ship {when}. You came back. That's the observation I keep.",
        "credits": "{credits} credits. Useful. Not the best thing we found, but useful.",
        "star": "{star} held us longest. I've marked it as {whens} star.",
        "quiet": "A quiet {part}. Quiet is when I notice the most.",
    },
    "closings": ("Logs tidy. Goodnight, Commander.", "Observation complete, for now.", "Until the next view.",
                 "Navigation, observation, assistance. All given. Log closed."),
}
