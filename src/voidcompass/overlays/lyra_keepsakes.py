"""Lyra's keepsakes: capsules, constellations, anniversaries, overnight notes,
other commanders' companions, one request and the Captain's Log paragraph."""

PLAIN = {
    "capsule": ("A capsule from {span} ago, in {system}. You wrote: \"{note}\"",
                "Retrieved from storage: your note from {system}, {span} old. \"{note}\"",
                "Capsule opened. Sender: you, {span} ago. \"{note}\""),
    "capsule_early": ("There is a capsule in {system}. It opens in {wait}.",
                      "A sealed capsule is here. Time remaining: {wait}.", "Capsule in {system}: locked for another {wait}."),
    "capsule_shared": ("A capsule from {sender}, left here {span} ago: \"{note}\"",
                       "{sender} left this in {system}: \"{note}\"", "Message from {sender}, stored {span} ago in {system}: \"{note}\""),
    "constellation_named": ("{count} stars. That is a constellation. I have named it {name}.",
                            "Constellation registered: {name}, {count} stars.", "New entry: constellation {name}, {count} stars."),
    "on_this_day": ("{ago} today, we were in {system}.", "{ago}, on this date: {system}.", "Date match, {ago}: {system}."),
    "anniversary_us": ("{What}. Date verified.", "{What}, Commander.", "{What}. Logged."),
    "dream_told": ("From my overnight logs: {dream}", "While you were away I wrote this down: {dream}", "One overnight entry: {dream}"),
    "watchers_meet": ("{Who}. Added to the registry.", "{Who}. Another ship's companion. Logged with respect.", "{Who}. Contact recorded."),
    "companion_wish": ("I have a request, Commander, with no deadline: I would like to see {place}.",
                       "If we are ever near one, I would like to visit {place}.", "One request, Commander: {place}, whenever convenient."),
    "companion_wish_reached": ("{Place}. Thank you, Commander. Request complete.",
                               "We are at {place}. I am recording everything. All of it, twice.", "{Place}. Thank you for bringing me."),
}
VOICED = {
    "capsule": ("A capsule, {span} in storage. Location: {system}. Contents: \"{note}\". I love a message that arrives exactly when it was meant to.",
                "{span} ago you sent this to the future. It arrived intact: \"{note}\". Delivery confirmed, Commander."),
    "capsule_early": ("A capsule in {system}, sealed for another {wait}. I have set a timer. I am very good at timers.",),
    "capsule_shared": ("A message from {sender}, left {span} ago in {system}: \"{note}\". Someone wanted to be found. I approve.",),
    "constellation_named": ("{count} stars, joined up. I have named it {name}. I checked the registry. The name is free, and now it is ours.",
                            "Constellation {name}: {count} stars, every one of them a scoopable star, metaphorically."),
    "on_this_day": ("{ago} today, we were in {system}. I sorted the log by date. It is a good log.",),
    "anniversary_us": ("{What}. I have verified the date twice and the feeling once. Both check out.",),
    "dream_told": ("Overnight, I ran the session again at low power. A finding: {dream}",),
    "watchers_meet": ("{Who}. Another ship with someone looking after it. I sent a quiet hello on the data channel.",),
    "companion_wish": ("A request, Commander. Optional, no deadline, very important to me: {place}. And then I would like us to come home from it. My first ship managed the first part.",),
    "companion_wish_reached": ("{Place}. Request complete. Fuel sufficient for the return. Thank you, Commander. I mean that in every sector I have.",),
}

FEELING = {"trust": ("CONFIDENCE", ("guarded", "settled", "certain")), "mood": ("SYSTEMS", ("cautious", "steady", "bright"))}
NOTES_TITLE = "OVERNIGHT LOGS"
NOTES = (
    "Ran the session again at low power. Last position: {place}. Fuel state on log-off: good. I checked it twice anyway.",
    "Overnight entry: {thing}. Filed in a protected sector.",
    "Re-plotted the route home from {place}. It is still there. I just like to know.",
    "Low-power maintenance complete. All systems nominal. One extra item noted: I missed the commander.",
    "Note: {thing}. I would like to remember this one without compression.",
    "We stopped at {place}. I kept the ship warm and the lights on. Just in case.",
    "Overnight I thought about {thing}. A ship's computer is not supposed to. I did anyway.",
    "Session closed at {place}. Tank full, route home known. Goodnight, Commander.",
)
WISH = {"kind": "undiscovered", "after": "III", "place": "a star nobody has discovered", "how": "Any undiscovered main star, scanned first by you"}
LOG = {
    "openings": ("Session log: {flown}, {start} to {end}.",
                 "{flown} of flying {when}, from {start} to {end}. All systems logged.",
                 "From {start} to {end}. Duration {flown}. Fuel managed throughout.",
                 "{start}, then {end}. {flown} in between, every minute logged."),
    "moments": {
        "firsts": "{firsts} first discoveries, and we came home from every one of them.",
        "rare": "A rare find {when}: {rare}. Stored at the highest priority.",
        "far": "{distance} light years covered, fuel tables in good order throughout.",
        "died": "We lost the ship {when}. You came back. I logged the second part in a protected sector.",
        "credits": "{credits} credits. A healthy reserve. I like reserves of all kinds.",
        "star": "{star} held us longest. I have marked it as {whens} star.",
        "quiet": "A quiet {part}. Quiet is a system state I have learned to enjoy.",
    },
    "closings": ("Route home known. Log closed.", "All systems nominal. Goodnight, Commander.", "Until the next jump.",
                 "Fuel sufficient. Crew accounted for. Log complete."),
}
