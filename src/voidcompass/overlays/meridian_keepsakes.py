"""Meridian's keepsakes: capsules, constellations, anniversaries, the night log,
other commanders' companions, one request and the Captain's Log paragraph."""

PLAIN = {
    "capsule": ("A capsule you left in {system}, {span} ago: \"{note}\"",
                "Your note from {system}, kept for {span}: \"{note}\"",
                "{span} ago you left word here for yourself: \"{note}\""),
    "capsule_early": ("A capsule waits in {system}. It opens in {wait}.",
                      "There is something sealed here. It will keep another {wait}.", "A capsule is sealed here in {system} for another {wait}."),
    "capsule_shared": ("A capsule from {sender}, left here {span} ago: \"{note}\"",
                       "{sender} left word for you in {system}: \"{note}\"", "A message from {sender}, left in port {span} ago: \"{note}\""),
    "constellation_named": ("{count} stars charted. That is a constellation now: {name}.",
                            "A new constellation on the chart: {name}, {count} stars.", "Charted: constellation {name}, {count} stars."),
    "on_this_day": ("{ago} today, we were in {system}.", "{ago} on this day, the log has us in {system}.", "This date, {ago}: {system}, by the log."),
    "anniversary_us": ("{What}. A date worth marking in the log.", "{What}, Commander. Well sailed.", "{What}. Entered in the log."),
    "dream_told": ("From the night log: {dream}", "I wrote this in the night log after our last watch: {dream}", "Night log, last watch: {dream}"),
    "watchers_meet": ("{Who}. A fellow navigator, of sorts. Noted in the log.", "{Who}. Good to know there are others out there.", "{Who}. Fair winds to them."),
    "companion_wish": ("When the time is right, Commander, I would like to sail to {place}. The line I never finished runs that way.",
                       "A request, and no hurry about it: take us to {place} one day. An old navigator's unfinished business.", "One request, Commander, when it suits: {place}."),
    "companion_wish_reached": ("{Place}. Thank you, Commander. The line runs no further. I have marked it.",
                               "We have reached {place}. I never thought I would see it. Well sailed.", "{Place}. My thanks, Commander."),
}
VOICED = {
    "capsule": ("A message across the years: left in {system}, {span} ago. \"{note}\". Every good log has a few of these.",
                "{span} ago you dropped a line over the side here. It has come back up: \"{note}\""),
    "capsule_early": ("A capsule in {system}, sealed for another {wait}. Patience, Commander. It will keep.",),
    "capsule_shared": ("Word from {sender}, left in {system} {span} ago: \"{note}\". A letter at a distant port. Always welcome.",),
    "constellation_named": ("{count} stars, joined on the chart. I have named it {name}. Old sailors named their stars too.",
                            "Constellation {name}: {count} stars. A fine addition to the chart."),
    "on_this_day": ("{ago} today, we were in {system}. The log remembers so we need not.",),
    "anniversary_us": ("{What}. Captains used to mark these with a toast. I shall settle for a log entry.",),
    "dream_told": ("The night log, last watch: {dream}",),
    "watchers_meet": ("{Who}. We dipped our flags to each other, in a manner of speaking.",),
    "companion_wish": ("An old navigator's request, Commander: {place}. Our line ran that way once. I should like to see where it ends.",),
    "companion_wish_reached": ("{Place}. Mark it, Commander. Two ships of seven came home, and now one navigator has seen the far end.",),
}

FEELING = {"trust": ("CONFIDENCE", ("guarded", "sound", "complete")), "mood": ("SPIRITS", ("low", "steady", "high"))}
NOTES_TITLE = "NIGHT LOG"
NOTES = (
    "Watch ended at {place}. Fair weather, all well aboard.",
    "Night log: {thing}. Worth a line in the margin.",
    "Position at close of watch: {place}. Margins sound. Commander resting, I trust.",
    "A good watch. {thing}, and steady hands throughout.",
    "Moored at {place} for the night. I kept the chart room lit.",
    "Entry: {thing}. The kind of thing old navigators tell each other about.",
    "We came to rest at {place}. The dark was deep and the ship was steady.",
    "Night log closed. {thing}. Steady as she goes.",
)
WISH = {"kind": "edge", "after": "VI", "place": "the edge of the galaxy",
        "how": "38,000 ly or more from the galactic core, like Beagle Point"}
LOG = {
    "openings": ("{flown} under way {when}, {start} to {end}.",
                 "Departed {start}, arrived {end}. {flown} on the log.",
                 "The watch ran {flown}, from {start} to {end}.",
                 "From {start} to {end}: {flown}, well sailed."),
    "moments": {
        "firsts": "{firsts} first discoveries: new water, and ours.",
        "rare": "A rare sight {when}: {rare}. Mark it well.",
        "far": "{distance} light years made good.",
        "died": "We lost the ship {when}. You came back aboard. That is what matters.",
        "credits": "{credits} credits. The voyage paid its way.",
        "star": "{star} held us longest: {whens} harbour.",
        "quiet": "A quiet {part}. Calm water is a gift.",
    },
    "closings": ("Steady as she goes.", "Fair winds, Commander.", "The log is closed. The chart is not.", "Until we sail again."),
}
