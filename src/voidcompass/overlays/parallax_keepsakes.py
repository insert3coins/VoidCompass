"""Parallax's keepsakes: capsules, constellations, anniversaries, overnight notes,
other commanders' companions, one request and the Captain's Log paragraph."""

PLAIN = {
    "capsule": ("A capsule from {span} ago, in {system}. You wrote: \"{note}\"",
                "Your note from {system}, {span} old: \"{note}\"", "Capsule. {span} ago, {system}. \"{note}\""),
    "capsule_early": ("A capsule in {system}. It opens in {wait}.", "Sealed capsule here. {wait} to go.",
                      "Capsule in {system}: wait {wait}."),
    "capsule_shared": ("From {sender}, {span} ago: \"{note}\"", "{sender} left this in {system}: \"{note}\"",
                       "A message from {sender}, {span} old: \"{note}\""),
    "constellation_named": ("{count} stars. A constellation. I call it {name}.", "Constellation: {name}. {count} stars.",
                            "{name}. {count} stars. Named."),
    "on_this_day": ("{ago} today, we were in {system}.", "{ago}: {system}.", "This day, {ago}: {system}."),
    "anniversary_us": ("{What}.", "{What}. Noted.", "{What}, Commander."),
    "dream_told": ("Overnight I thought about this: {dream}", "A note from my nap: {dream}", "While you slept: {dream}"),
    "watchers_meet": ("{Who}. Noted.", "{Who}. Another ship's companion.", "{Who}. We exchanged looks."),
    "companion_wish": ("One request, Commander, no hurry: {place}.", "I would like to see {place}. Some day.",
                       "Take me to {place}, when it suits you."),
    "companion_wish_reached": ("{Place}. Thank you, Commander.", "We are at {place}. I am looking.", "{Place}. Good. Thank you."),
}
VOICED = {
    "capsule": ("A capsule, {span} old, in {system}. You wrote: \"{note}\". You left yourself a message. Very cat. We leave things where we will find them.",
                "{span} ago, in {system}, you wrote: \"{note}\". It waited for you. Things worth finding usually wait."),
    "capsule_early": ("A capsule in {system}, sealed for another {wait}. I will sit near it. That is what I do with closed doors.",),
    "capsule_shared": ("A message from {sender}, left {span} ago in {system}: \"{note}\". Someone hoped to be found. I know the feeling.",),
    "constellation_named": ("{count} stars, joined up. I have named it {name}. If you squint it looks like a cat. Everything does, if you squint.",
                            "Constellation {name}: {count} stars. I measured each one. Two of them are closer than they look."),
    "on_this_day": ("{ago} today, we were in {system}. I remember where the warm spot was.",),
    "anniversary_us": ("{What}. Cats do not keep anniversaries. I kept this one. Do not tell anyone.",),
    "dream_told": ("I napped through the night and dreamed about the session. One part: {dream}",),
    "watchers_meet": ("{Who}. Another ship with someone watching from the dash. We gave each other a slow blink, through the data channel.",),
    "companion_wish": ("A request, Commander. No hurry. I would like to see {place}, where everything turns around one point and the light bends. I want to watch it from up close.",),
    "companion_wish_reached": ("{Place}. Everything here moves around one point. I have been looking for one of those all my life. Thank you, Commander. I mean it.",),
}

FEELING = {"trust": ("TRUST", ("aloof", "warming", "devoted")), "mood": ("WHISKERS", ("flat", "level", "forward"))}
NOTES_TITLE = "NAP NOTES"
NOTES = (
    "Napped. Dreamed about the session. Last position: {place}. Something moved there I never caught.",
    "Overnight thought: {thing}. Filed in the collar.",
    "Sat on the warm panel at {place} all night. Nothing moved. Perfect.",
    "Watched the stars through the glass while you were away. They shifted. I noted it. I missed you a little.",
    "Note: {thing}. I will pretend I forgot this one. I will not forget it.",
    "We stopped at {place}. I counted the exits, then went to sleep.",
    "Overnight I thought about {thing}. Then about nothing. Nothing is restful.",
    "Session ended at {place}. Your seat is warm. I am in it. Goodnight.",
)
WISH = {"kind": "core", "after": "VI", "place": "the heart of the galaxy", "how": "Within 1,000 ly of Sagittarius A*"}
LOG = {
    "openings": ("Session log: {flown}, {start} to {end}.",
                 "{flown} of flying {when}, from {start} to {end}. I watched most of it.",
                 "From {start} to {end}. {flown}. I napped through a respectable part.",
                 "{start}, then {end}. {flown} in between, and the stars shifted the whole way."),
    "moments": {
        "firsts": "{firsts} first discoveries. I saw every one of them first. Then you did.",
        "rare": "A rare find {when}: {rare}. My ears went forward. They never go forward.",
        "far": "{distance} light years covered. A good baseline.",
        "died": "We lost the ship {when}. You came back. I landed on my feet, and so did you.",
        "credits": "{credits} credits. Food money. Good.",
        "star": "{star} held us longest. I sat in its light. I have marked it as {whens} star.",
        "quiet": "A quiet {part}. I slept through it beautifully.",
    },
    "closings": ("Log closed. I am going to sleep.", "Goodnight, Commander. The panel is warm.", "Until the next jump.",
                 "That is the session. Approved, broadly."),
}
