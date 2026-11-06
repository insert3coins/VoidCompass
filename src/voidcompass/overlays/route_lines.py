"""Talk along a plotted route (5.7.5), for all four companions.

The journal says how many jumps are left each time the next one is targeted,
so a route has a shape: plotted, halfway, five to go, the last jump, arrival.
And now and then a star on the way has no fuel to give.

Fields: {jumps} the route's length, {left} jumps still to go (5 or more),
{kind} the star ("a {kind}" reads naturally for every kind).
"""

# Topic -> importance. A route is something the commander chose: its start
# and end are worth saying even on Rare; the milestones are remarks.
IMPORTANCE = {"route_plotted": 2, "route_halfway": 1, "route_progress": 1, "route_last": 1, "route_done": 2, "no_scoop": 1}

# What's said jump after jump. On Chatty these start a new round once every
# line is used, rather than going quiet for the rest of a long trip; every
# other remark still keeps its promise not to repeat.
TRAVEL = {"arrival", "scooped", "jump_long", "jump_far", "no_scoop", "route_halfway", "route_progress", "route_last"}

WATCHER_NORMAL = {
    "route_plotted": ("{jumps} jumps. I'll count them with you.", "A route of {jumps} jumps. Let's see where it goes.",
                      "{jumps} jumps plotted. That's a proper trip.", "{jumps} jumps ahead. I like a plan.",
                      "Route set: {jumps} jumps. I'll keep an eye on the stars.", "{jumps} jumps. Plenty of time to think.",
                      "A long line on the map. {jumps} jumps of it.", "{jumps} jumps. Somewhere at the end of it, something new.",
                      "Plotted. {jumps} jumps between us and there.", "{jumps} jumps. I'll be here for every one."),
    "route_halfway": ("Halfway. {left} jumps to go.", "We're halfway there. {left} left.", "The middle of the route. {left} more.",
                      "Half done. The rest of the line is {left} jumps long.", "Halfway. It feels further, doesn't it?",
                      "{left} jumps left. We've passed the middle.", "Halfway. I always notice the halfway point.",
                      "That's half. {left} more stars to meet.", "Halfway mark. Still going.", "Half the route behind us. {left} ahead."),
    "route_progress": ("{left} jumps to go.", "{left} more. Nearly there.", "Only {left} jumps left now.",
                       "{left} to go. I can almost see it.", "Down to {left} jumps.", "{left} left on the route.",
                       "{left} more stars, then we're there.", "Counting down: {left}.", "{left} jumps. Not long now.",
                       "The route's nearly done. {left} jumps."),
    "route_last": ("Last jump.", "One more.", "This is the last one.", "Final jump coming up.", "One to go.",
                   "Last star on the route.", "One more jump and we're there.", "The end of the line is next.",
                   "Just one left.", "Last leg."),
    "route_done": ("We're here. End of the route.", "Arrived. That's the whole route.", "Route complete. We made it.",
                   "That's the last jump. We're here.", "End of the line. Look around.", "Here at last.",
                   "Destination reached. Every jump of it.", "We've arrived. I counted them all.",
                   "That was the route. This is where it led.", "Here. Wherever here turns out to be."),
    "no_scoop": ("Nothing to scoop here. It's a {kind}.", "A {kind}. No fuel from this one.", "Watch the tank. A {kind} won't help.",
                 "No fuel here: a {kind}.", "A {kind}. Look, don't scoop.", "This star's a {kind}. Keep moving.",
                 "A {kind}. Pretty, but no use to the tank.", "No scooping at a {kind}.", "Fuel check: this one's a {kind}.",
                 "A {kind}. We'll fill up at the next good star."),
}

WATCHER_WEARY = {
    "route_plotted": ("{jumps} jumps. Of course it is.", "{jumps} jumps. I'll try to stay awake.", "A route. {jumps} jumps. Lovely.",
                      "{jumps} jumps of the dark. My favourite.", "Plotted. {jumps} jumps. Wake me at the end. I won't sleep.",
                      "{jumps} jumps. That's a lot of stars to be unimpressed by.", "{jumps} jumps. I've done longer. I didn't enjoy those either.",
                      "Another route. {jumps} jumps. Here we go again.", "{jumps} jumps. Somewhere out there, more nothing.",
                      "{jumps} jumps. I'll count them. It's what I do."),
    "route_halfway": ("Halfway. {left} to go. Not that I'm counting. I'm counting.", "Halfway. The worst half, probably.",
                      "Half done. {left} more of the same.", "{left} left. The middle is always the longest.",
                      "Halfway. Don't get excited.", "We're halfway. The universe didn't notice.", "Half the route. {left} jumps of it left.",
                      "Halfway there. Wherever there is.", "The middle. I've spent a lot of time in middles.", "{left} more. Halfway. Hm."),
    "route_progress": ("{left} jumps left. Try to contain yourself.", "{left} more. It'll be over soon. Everything is.",
                       "Down to {left}. Hardly worth mentioning. I mentioned it.", "{left} to go. Same stars, different names.",
                       "{left} more jumps. I've been counting since the first.", "{left} left. Nearly somewhere.",
                       "Only {left}. Don't get your hopes up.", "{left} jumps. Then we'll want to go somewhere else.",
                       "{left} more. The end's in sight. Sort of.", "{left}. Nearly. Probably."),
    "route_last": ("Last jump. Then what?", "One more. Then the quiet.", "Final jump. I'd say it was fun.", "Last one. Finally.",
                   "One left. I'll miss counting.", "The last jump. They always come.", "Last star. Probably a dull one.",
                   "One more. Then you'll plot another.", "Final leg. Don't rush on my account.", "Last jump. Brace for arrival. Or don't."),
    "route_done": ("We're here. It looks like everywhere else.", "Arrived. I hope it was worth it.", "End of the route. Now what?",
                   "Here we are. Wherever this is.", "Route done. I counted every one.", "We made it. I had my doubts.",
                   "That's it. All the jumps. Gone.", "Arrived. The universe remains unbothered.",
                   "Here. You picked it. I'm sure it's lovely.", "Destination. Another word for 'next start point'."),
    "no_scoop": ("A {kind}. No fuel. Naturally.", "Nothing to scoop. It's a {kind}. Of course it is.",
                 "A {kind}. Mind the tank. I'm minding it.", "This one's a {kind}. Useless, fuel-wise. Like me.",
                 "No fuel here. A {kind}. Typical.", "A {kind}. Look at it if you like. Don't scoop it.",
                 "A {kind}. Lovely and useless.", "Fuel? From a {kind}? No.", "A {kind}. I'd keep an eye on the tank.",
                 "A {kind}. The tank won't thank it."),
}

PERSONAS = {
    "aster": {
        "plain": {
            "route_plotted": ("Route plotted: {jumps} jumps.", "{jumps} jumps entered in the log.", "Course laid in. {jumps} jumps.",
                              "A route of {jumps} jumps, Commander."),
            "route_halfway": ("Halfway. {left} jumps remain.", "Midpoint of the route. {left} to go.", "Half the route complete.",
                              "Halfway, Commander. {left} jumps left."),
            "route_progress": ("{left} jumps remaining.", "{left} to go, Commander.", "Route: {left} jumps left.",
                               "{left} jumps from the destination."),
            "route_last": ("Final jump.", "One jump remaining.", "Last jump of the route, Commander.", "One to go."),
            "route_done": ("Destination reached.", "Route complete, Commander.", "Arrived. Route closed in the log.",
                           "End of the route."),
            "no_scoop": ("A {kind}. No fuel available.", "No scooping here: a {kind}.", "Fuel note: this star is a {kind}.",
                         "A {kind}. Mind the tank."),
        },
        "voiced": {
            "route_plotted": ("{jumps} jumps, Commander. I have opened a fresh page for them.",
                              "A route of {jumps} jumps. Ambitious, and duly entered.",
                              "{jumps} jumps plotted. I shall keep the tally, as is my custom.",
                              "Course laid in for {jumps} jumps. The log is ready when you are.",
                              "{jumps} jumps. A respectable itinerary, if not a modest one.",
                              "Route accepted: {jumps} jumps. I shall try not to remark on every one."),
            "route_halfway": ("Halfway, Commander. The log is pleasingly balanced.",
                              "Midpoint reached. {left} jumps remain, and so does my enthusiasm.",
                              "Half the route complete. I have ruled a neat line under it.",
                              "{left} to go. We are past the point where turning back is sensible.",
                              "Halfway. A good moment for a status report: all in order.",
                              "The midpoint, Commander. I shall note it with a small tick."),
            "route_progress": ("{left} jumps to go. The final page of this entry is in sight.",
                               "{left} remaining, Commander. The destination column awaits.",
                               "Down to {left}. I have begun drafting the arrival entry.",
                               "{left} jumps left. Punctual, so far.",
                               "{left} to go. Nothing outstanding to report.",
                               "{left} jumps, Commander. The end is within administrative reach."),
            "route_last": ("Final jump, Commander. I have the pen ready.", "One remaining. Do make it a tidy one.",
                           "The last jump. I shall close the entry on arrival.", "One to go. Steady hands, please.",
                           "Final leg. The log has been very patient.", "Last jump of the route. Proceed when ready."),
            "route_done": ("Destination reached. Route closed in the log, with a flourish I shall not describe.",
                           "Arrived, Commander. Every jump accounted for.",
                           "Route complete. I have signed the entry myself.",
                           "End of the route. A well-run passage, if I may say so.",
                           "We are here. The itinerary has been honoured in full.",
                           "Destination reached. I recommend a moment's satisfaction. Briefly."),
            "no_scoop": ("A {kind}. Decorative, but no fuel. Mind the tank.",
                         "This star is a {kind}. The fuel column will not improve here.",
                         "A {kind}, Commander. Admire it; do not scoop it.",
                         "No fuel from a {kind}. I note it for the next refuelling stop.",
                         "A {kind}. Our tank and this star have nothing to discuss.",
                         "Fuel advisory: a {kind}. Plan the next scoop accordingly."),
        },
    },
    "axiom": {
        "plain": {
            "route_plotted": ("Route: {jumps} jumps.", "{jumps} jumps plotted.", "Course of {jumps} jumps recorded.",
                              "{jumps} jumps to the destination."),
            "route_halfway": ("Halfway. {left} jumps left.", "Midpoint reached.", "Half complete. {left} remaining.",
                              "Route 50% complete."),
            "route_progress": ("{left} jumps left.", "{left} remaining.", "Route: {left} to go.", "{left} jumps from arrival."),
            "route_last": ("Last jump.", "One jump left.", "Final jump next.", "One remaining."),
            "route_done": ("Destination reached.", "Route complete.", "Arrived. Route closed.", "All jumps complete."),
            "no_scoop": ("No fuel: a {kind}.", "A {kind}. Not scoopable.", "Unscoopable star: a {kind}.", "A {kind}. Check fuel."),
        },
        "voiced": {
            "route_plotted": ("{jumps} jumps. That is {jumps} new skies to count. Excellent.",
                              "Route of {jumps} jumps recorded. I have prepared {jumps} fresh pages.",
                              "{jumps} jumps plotted. The probability of something interesting en route is high.",
                              "A {jumps}-jump route. I will observe every one.",
                              "{jumps} jumps. I have already started estimating what we will find.",
                              "Route accepted. {jumps} jumps. My instruments are warm."),
            "route_halfway": ("Halfway. Exactly. I checked.", "Midpoint. {left} jumps remain, give or take zero.",
                              "Half the route observed. The other half is still a hypothesis.",
                              "Halfway reached. Statistically, the best half may be ahead.",
                              "50% complete. A satisfying number.", "{left} to go. The midpoint was unremarkable. I noted it anyway."),
            "route_progress": ("{left} jumps left. The count is getting pleasantly small.",
                               "{left} remaining. I have recalculated our arrival. It is still arriving.",
                               "{left} to go. Every jump has added to the record.",
                               "Route: {left} jumps. Confidence in arrival: high.",
                               "{left} more skies to count before the destination.",
                               "{left} jumps. I am already curious about the last one."),
            "route_last": ("Final jump. I am ready to observe the destination.", "One jump left. Instruments ready.",
                           "Last jump. The final data point of the route.", "One remaining. I have saved space in the log.",
                           "Final leg. I am mildly excited. Mildly.", "The last jump. Let us see what the route was for."),
            "route_done": ("Destination reached. Route complete, all jumps recorded.",
                           "Arrived. The route resolves into a single system. Lovely.",
                           "Route complete. I have closed the count. Nothing missing.",
                           "We are here. A new sky, at the end of a long sum.",
                           "Destination reached. Shall we see what is here?",
                           "All jumps complete. The route was correct. I like when routes are correct."),
            "no_scoop": ("A {kind}. Fascinating, and useless for fuel.", "This is a {kind}. I recommend admiring it rather than scooping it.",
                         "A {kind}. Fuel yield: zero. Interest yield: considerable.",
                         "No fuel from a {kind}. I have noted it, sadly.",
                         "A {kind}. The tank and I are disappointed. The rest of me is delighted.",
                         "Unscoopable: a {kind}. Please watch the fuel gauge."),
        },
    },
    "meridian": {
        "plain": {
            "route_plotted": ("Course set: {jumps} jumps.", "{jumps} jumps to the destination.", "Route plotted. {jumps} jumps.",
                              "{jumps} jumps on the chart."),
            "route_halfway": ("Halfway. {left} to go.", "Half the passage made.", "Midpoint. {left} jumps remain.",
                              "Halfway there, Commander."),
            "route_progress": ("{left} jumps to go.", "{left} remaining.", "{left} jumps from landfall.", "Course holding. {left} left."),
            "route_last": ("Last jump.", "One more jump.", "Final leg.", "One to go, Commander."),
            "route_done": ("Destination reached.", "Landfall. Route complete.", "We have arrived.", "End of the passage."),
            "no_scoop": ("No fuel here: a {kind}.", "A {kind}. Can't scoop it.", "Unscoopable: a {kind}.", "A {kind}. Mind the fuel."),
        },
        "voiced": {
            "route_plotted": ("{jumps} jumps on the chart. Steady as she goes.",
                              "Course laid in: {jumps} jumps. A fair passage, if the stars are kind.",
                              "{jumps} jumps, Commander. I have marked each one in pencil.",
                              "A passage of {jumps} jumps. I'll call them as we go.",
                              "{jumps} jumps plotted. Fair winds to us.",
                              "Route set for {jumps} jumps. Keep a good margin in the tank."),
            "route_halfway": ("Halfway, Commander. The hardest half is often the first.",
                              "Half the passage made good. {left} jumps to landfall.",
                              "Midpoint. In the old fleet we'd ring a bell here.",
                              "Halfway there. Course holding true.",
                              "{left} to go. We're past the point of no return, in the best sense.",
                              "Half the route behind us. Well navigated.",
                              "Halfway, and the chart agrees with us. A good sign.",
                              "The middle watch of the passage. {left} jumps on."),
            "route_progress": ("{left} jumps to landfall. Course holding.",
                               "{left} remaining. The chart is nearly run.",
                               "{left} to go, Commander. Steady as she goes.",
                               "{left} jumps. I can almost smell the harbour.",
                               "Down to {left}. Keep her steady.",
                               "{left} jumps left. A good passage so far.",
                               "{left} to landfall. I've started looking for the harbour lights.",
                               "{left} more, Commander. The last stretch is always the longest."),
            "route_last": ("Last jump, Commander. Bring her in.", "One more. Landfall next.", "Final leg. Steady now.",
                           "The last jump of the passage. Well done so far.", "One to go. Mind the arrival.",
                           "Final jump. I'll mark the landfall.",
                           "One jump to landfall. Bring her home, Commander.",
                           "The last stride of the passage. Make it a clean one."),
            "route_done": ("Landfall, Commander. The passage is complete.",
                           "Destination reached. Every jump made good.",
                           "We have arrived. A well-run passage.",
                           "End of the route. I'll enter it in the log with some satisfaction.",
                           "Here at last. Fine navigating, Commander.",
                           "Passage complete. Rest a moment before the next one."),
            "no_scoop": ("A {kind}, Commander. No fuel from her. Keep a weather eye on the tank.",
                         "This one's a {kind}. A sailor can't drink seawater, and we can't scoop this.",
                         "A {kind}. Mark the fuel and press on to a friendlier star.",
                         "No fuel at a {kind}. The next harbour will have to do.",
                         "A {kind}. Handsome, but she'll not fill the tank.",
                         "Fuel note: a {kind}. Plan the next scoop with care.",
                         "A {kind}. No harbour for us here; the tank stays as it is.",
                         "We'll find no fuel at a {kind}. I've marked the next friendly star."),
        },
    },
}

# A star's class from FSDTarget or StartJump, as a word that reads after "a".
_KINDS = (("N", "neutron star"), ("H", "black hole"), ("SupermassiveBlackHole", "black hole"), ("D", "white dwarf"),
          ("W", "Wolf-Rayet star"), ("TTS", "T Tauri star"), ("AeBe", "Herbig Ae/Be star"), ("C", "carbon star"),
          ("MS", "carbon star"), ("S", "carbon star"), ("L", "brown dwarf"), ("T", "brown dwarf"), ("Y", "brown dwarf"),
          ("X", "exotic star"), ("RoguePlanet", "rogue planet"), ("Nebula", "nebula"), ("StellarRemnantNebula", "nebula"))
SCOOPABLE = set("KGBFOAM")


def scoopable(star):
    star = str(star or "")
    return star in SCOOPABLE or (len(star) > 1 and star[1] == "_" and star[0] in SCOOPABLE)


def kind(star):
    """The star's kind in words, or "" when it's a scoopable main-sequence star."""
    star = str(star or "")
    if not star or scoopable(star):
        return ""
    for prefix, words in sorted(_KINDS, key=lambda row: -len(row[0])):
        if star == prefix or star.startswith(prefix):
            return words
    return "star you can't scoop"


def simple_class(star):
    """A scoopable star's class letter for arrival lines ("K"), else ""."""
    star = str(star or "")
    return star[0] if scoopable(star) else ""


def persona_banks(identity):
    """(plain, voiced) for one of the officer-style companions."""
    banks = PERSONAS[identity]
    return banks["plain"], banks["voiced"]

# 5.7.6: Lyra.
from voidcompass.overlays import lyra_shared as _lyra  # noqa: E402

PERSONAS["lyra"] = _lyra.ROUTE
