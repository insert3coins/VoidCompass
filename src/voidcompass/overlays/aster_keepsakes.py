"""Aster's keepsakes: capsules, constellations, anniversaries, watch notes,
other commanders' companions, one request and the Captain's Log paragraph."""

PLAIN = {
    "capsule": ("A note you left in {system}, {span} ago. It reads: \"{note}\"",
                "Your capsule from {system} is back in hand, {span} later: \"{note}\"",
                "{span} ago you left this here for yourself: \"{note}\""),
    "capsule_early": ("There is a capsule waiting in {system}. It opens in {wait}.",
                      "Something is filed here under later. It opens in {wait}.", "Your capsule in {system} is not due for another {wait}. I shall keep it sealed."),
    "capsule_shared": ("A capsule from {sender}, left here {span} ago: \"{note}\"",
                       "{sender} left this in {system} for you: \"{note}\"", "Correspondence for you, from {sender}, left {span} ago: \"{note}\""),
    "constellation_named": ("{count} stars recorded. That makes a constellation. I have entered it as {name}.",
                            "A constellation completed: {name}, {count} stars.", "{name}: {count} stars, entered as one constellation."),
    "on_this_day": ("{ago} today, we were in {system}.", "{ago} on this date, the log puts us in {system}.", "This date, {ago}: {system}, according to our log."),
    "anniversary_us": ("{What}. I have noted it in the handover book.", "{What}, Commander. A date worth keeping.", "{What}. It is in the book, Commander."),
    "dream_told": ("From last watch's notes: {dream}", "I wrote this after our last watch. {dream}", "A line from last watch's notes: {dream}"),
    "watchers_meet": ("{Who}. I have added them to the crew list, in pencil.", "{Who}. A good officer keeps track of the other crews.", "{Who}. Noted, with my compliments to their crew."),
    "companion_wish": ("When you have a moment, I should like to go back to {place}. That is where I received this watch.",
                       "A request, Commander, entirely optional: take us back to {place}, where my page in your log begins.", "If we are ever passing, Commander, I should like to see {place} again. No hurry."),
    "companion_wish_reached": ("{Place}. Thank you, Commander. I have written it in the margin of the first page.",
                               "We are back at {place}. Received the watch here. It is good to see it again.", "{Place}, Commander. The request is closed, with thanks."),
}
VOICED = {
    "capsule": ("{span} ago you filed a note in {system}. I have kept it in order: \"{note}\"",
                "A capsule, delivered on time to the minute: \"{note}\". Left in {system}, {span} ago."),
    "capsule_early": ("A capsule waits in {system}, marked not before. Another {wait}. I shall resist reading it.",),
    "capsule_shared": ("Correspondence from {sender}, left in {system} {span} ago: \"{note}\". Properly addressed, too.",),
    "constellation_named": ("{count} stars, all accounted for. I have registered the constellation as {name}. A satisfying count.",
                            "A new constellation, {name}. {count} stars, entered with the appropriate ceremony."),
    "on_this_day": ("{ago} today, the arrival column says {system}. I remember the entry.",),
    "anniversary_us": ("{What}. I have no salary to raise, but I did consider a small ceremony.",),
    "dream_told": ("Last watch's notes, for the record: {dream}",),
    "watchers_meet": ("{Who}. Another officer, more or less. We exchanged entries.",),
    "companion_wish": ("A personal request, filed under optional: {place}. That is where I received the watch. I should like to see it again.",),
    "companion_wish_reached": ("{Place}. Received the watch, here. I find I am rather glad you brought us back.",),
}

FEELING = {"trust": ("CONFIDENCE", ("reserved", "steady", "complete")), "mood": ("MORALE", ("low", "even", "high"))}
NOTES_TITLE = "WATCH NOTES"
NOTES = (
    "Watch closed at {place}. Nothing to add to the official log. I added something anyway.",
    "Note for the handover book: {thing}. Filed under worth remembering.",
    "The watch ended at {place}. The console lights are still a little brighter than regulations require.",
    "Counted, delivered, accounted for. {thing}, mainly. The rest was flying.",
    "Last entry of the watch: {place}. Somebody should be awake. I volunteered.",
    "{thing}. I wrote it down twice, once for the log and once for me.",
    "A quiet note: we stopped at {place}. I left a blank line beneath it, as is my habit.",
    "Standing orders observed. {thing} noted. Commander rested, I hope.",
)
WISH = {"kind": "first_place", "after": "VII", "place": "the system where you first switched me on",
        "how": "The system where Aster first came aboard"}
LOG = {
    "openings": ("{flown} on watch {when}, {start} to {end}. Entered in full.",
                 "From {start} to {end}: {flown}. A complete watch.",
                 "The watch ran {flown}, departing {start}, arriving {end}.",
                 "{start} to {end}, {flown}. All hands accounted for."),
    "moments": {
        "firsts": "{firsts} first discoveries, each one a new line in somebody's future chart.",
        "rare": "A rare finding {when}: {rare}. I gave it a proper entry.",
        "far": "{distance} light years. The arrival column was busy.",
        "died": "We lost the ship {when}. You came back. The rest is paperwork.",
        "credits": "{credits} credits, and the accounts approve.",
        "star": "{star} held us longest {when}. A familiar entry already.",
        "quiet": "A quiet {part}. A watch properly kept, all the same.",
    },
    "closings": ("I have the watch.", "Standing on, Commander.", "The book stays open.", "Until the next watch."),
}
