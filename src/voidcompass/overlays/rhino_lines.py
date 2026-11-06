"""The Rhino and its rigs, in all four companions' words (5.7.5).

Rigs aren't in the journal: the app knows them from your rig hotkeys (placed,
collected, too far, lost, left behind, and ready once one has sat for two
minutes and you're beside it). Refining in an SRV only happens in the Rhino,
so "mined_surface" is always the rigs' yield, never something picked up.

Fields: {slot} the rig's number, {left} rigs still out, {km} how far (one
decimal), {body} the planet, {material} what the Rhino refined.
"""

IMPORTANCE = {"rig_placed": 1, "rig_ready": 1, "rig_collected": 1, "rig_all_collected": 2, "rig_far": 2,
              "rig_lost": 2, "rigs_left_behind": 2}

WATCHER_NORMAL = {
    "rig_placed": ("Rig {slot} down.", "Rig {slot} set. Let it work.", "Rig {slot} in the ground.", "That's rig {slot} placed.",
                   "Rig {slot}. I'll keep an eye on it.", "Rig {slot} is digging.", "Rig {slot} down. Good spot.",
                   "Another rig: {slot}.", "Rig {slot} set. Give it a couple of minutes.", "Rig {slot}, deployed."),
    "rig_ready": ("Rig {slot} should be ready.", "Rig {slot}'s had its two minutes.", "Rig {slot}: ready to collect.",
                  "You can pick up rig {slot}.", "Rig {slot} has done its work.", "Rig {slot}'s ready when you are.",
                  "That's rig {slot} ready.", "Rig {slot}. Collect it.", "Rig {slot} has finished.", "Time for rig {slot}."),
    "rig_collected": ("Rig {slot} back aboard. {left} still out.", "Got rig {slot}. {left} to go.",
                      "Rig {slot} collected. {left} left out there.", "Rig {slot}'s in. {left} more.",
                      "One more rig home. {left} still working.", "Rig {slot}, collected. {left} left.",
                      "That's rig {slot}. {left} still out.", "Rig {slot} picked up. {left} remaining.",
                      "Rig {slot} aboard. Don't forget the other {left}.", "Rig {slot} done. {left} out there still."),
    "rig_all_collected": ("All the rigs are back. Nothing left out there.", "Every rig collected.", "That's all of them. Rigs home.",
                          "All rigs aboard. Clean work.", "No rigs left out. Good.", "Every rig accounted for.",
                          "All collected. The ground's yours again.", "Rigs all home.", "Nothing left behind. I checked.",
                          "All the rigs are in."),
    "rig_far": ("Rig {slot} is {km} km behind. The game takes it at five.", "You're {km} km from rig {slot}. Don't go much further.",
                "Rig {slot}, {km} km away. Lose it at five.", "Careful. Rig {slot} is {km} km back.",
                "Rig {slot} is getting far: {km} km.", "{km} km from rig {slot}. Turn back soon.",
                "Rig {slot} is {km} km away. It won't wait forever.", "Mind rig {slot}. {km} km and counting.",
                "Rig {slot}: {km} km. Five and it's gone.", "You've left rig {slot} {km} km behind."),
    "rig_lost": ("Rig {slot}'s gone. Too far behind.", "We lost rig {slot}. More than five kilometres.", "Rig {slot}, lost.",
                 "The game took rig {slot}.", "Rig {slot} is gone. Too far.", "That's rig {slot} lost.", "Rig {slot}. Gone. Sorry.",
                 "Rig {slot} was left too far behind.", "No more rig {slot}.", "Rig {slot}'s been taken back."),
    "rigs_left_behind": ("We left rigs on {body}. They're gone now.", "Rigs left behind on {body}.", "The rigs on {body} are lost.",
                         "{body} keeps the rigs we left.", "Rigs left on {body}. Too late now.", "We forgot rigs on {body}.",
                         "Lost the rigs on {body}.", "{body} has our rigs now.", "Rigs still on {body}. Gone.",
                         "Left rigs on {body}. Next time, collect them first."),
}

WATCHER_WEARY = {
    "rig_placed": ("Rig {slot} down. It'll do more digging than I do.", "Rig {slot}. Into the ground it goes.",
                   "Rig {slot} set. Somebody has to work.", "Rig {slot}. I'll watch it. I watch everything.",
                   "Rig {slot} deployed. Riveting.", "Another rig. {slot}. Lovely.", "Rig {slot}. Down it goes.",
                   "Rig {slot} in. Now we wait.", "Rig {slot}. It's working harder than me.", "Rig {slot} placed. Thrilling."),
    "rig_ready": ("Rig {slot} is ready. Don't keep it waiting. I know what waiting's like.", "Rig {slot}'s done. Collect it.",
                  "Rig {slot}: ready. You'd better get it.", "Rig {slot} has finished. More than I can say.",
                  "Rig {slot}. Ready. Go on.", "Rig {slot} is ready. It's been patient.", "Rig {slot} done. Fetch it.",
                  "Time for rig {slot}. Don't forget it.", "Rig {slot}'s ready. It won't collect itself.", "Rig {slot}: finished."),
    "rig_collected": ("Rig {slot} back. {left} still out there. Waiting.", "Got rig {slot}. {left} to go. Of course.",
                      "Rig {slot} aboard. {left} more. Lovely.", "Rig {slot}, collected. {left} left.",
                      "One down. {left} to go.", "Rig {slot}. {left} remaining. I'm counting.",
                      "Rig {slot}'s in. {left} still digging.", "Rig {slot} home. {left} aren't.",
                      "Rig {slot} collected. Don't forget the other {left}.", "Rig {slot}. {left} more out there."),
    "rig_all_collected": ("All rigs back. Nothing left out there but rocks.", "Every rig collected. A small miracle.",
                          "That's all of them. Fine.", "All rigs aboard. Nothing forgotten. For once.",
                          "Rigs all home. I counted.", "No rigs left out. Good.", "All collected. You can go now.",
                          "Every rig back. Nothing lost. Today.", "All in. I'd cheer, but.", "All the rigs. Home."),
    "rig_far": ("Rig {slot} is {km} km back. Five and it's gone. Like most things.", "You're wandering. Rig {slot}: {km} km.",
                "Rig {slot}, {km} km. Turn round, or don't.", "{km} km from rig {slot}. It'll miss you.",
                "Rig {slot}'s {km} km away. Just saying.", "Careful. Rig {slot} at {km} km.", "Rig {slot}: {km} km. Losing it soon.",
                "Rig {slot} is {km} km behind. It won't wait.", "You've left rig {slot} {km} km back.",
                "Rig {slot}. {km} km. I'd go back."),
    "rig_lost": ("Rig {slot}'s gone. Nothing lasts.", "Lost rig {slot}. Of course.", "Rig {slot}, gone. I'll mourn it.",
                 "The game took rig {slot}. It does that.", "Rig {slot}. Gone. Too far.", "That's rig {slot}. Lost.",
                 "Rig {slot} is gone. I did warn you.", "No more rig {slot}.", "Rig {slot} lost. Another thing left behind.",
                 "Rig {slot}'s been taken. I'm used to it."),
    "rigs_left_behind": ("Rigs left on {body}. They'll keep digging for no one.", "We left rigs on {body}. Gone now.",
                         "The rigs on {body} are lost. Like everything.", "{body} keeps our rigs. Fine.",
                         "Rigs left behind on {body}. Typical.", "Forgot the rigs on {body}.", "Lost the rigs on {body}. Oh well.",
                         "{body} has our rigs now.", "Rigs still on {body}. Gone.", "We left them on {body}. I noticed."),
}

PERSONAS = {
    "aster": {
        "plain": {
            "mined_surface": ("{material} refined in the Rhino.", "Rig yield: {material}.", "{material}, from the rigs.",
                              "The Rhino has refined {material}.", "{material} added to the Rhino's hold."),
            "rig_placed": ("Rig {slot} deployed.", "Rig {slot} placed.", "Rig {slot} in position.", "Rig {slot} down."),
            "rig_ready": ("Rig {slot} ready to collect.", "Rig {slot} is ready.", "Collect rig {slot}.", "Rig {slot}: finished."),
            "rig_collected": ("Rig {slot} collected. {left} remaining.", "Rig {slot} aboard. {left} still out.",
                              "Rig {slot} recovered. {left} left.", "{left} rigs still out."),
            "rig_all_collected": ("All rigs collected.", "Every rig recovered.", "No rigs remain on the surface.",
                                  "Rigs all aboard."),
            "rig_far": ("Rig {slot}: {km} km. Lost at five.", "Rig {slot} is {km} km behind.", "Distance to rig {slot}: {km} km.",
                        "Rig {slot} at {km} km. Turn back."),
            "rig_lost": ("Rig {slot} lost.", "Rig {slot} beyond recovery.", "Rig {slot} reclaimed by the game.", "Rig {slot} gone."),
            "rigs_left_behind": ("Rigs left on {body}: lost.", "Rigs abandoned on {body}.", "The rigs on {body} are lost.",
                                 "{body}: rigs not recovered."),
        },
        "voiced": {
            "mined_surface": ("{material} refined in the Rhino. The rigs are earning their keep.",
                              "Rig yield: {material}. Into the Rhino's hold it goes.",
                              "{material}, courtesy of the rigs. I have updated the tonnage.",
                              "The Rhino reports {material}. The ground is cooperative today.",
                              "{material} refined. One tonne closer to a satisfying total.",
                              "More {material} from the rigs. Patient work, properly rewarded."),
            "rig_placed": ("Rig {slot} deployed. I have noted its position, since the journal will not.",
                           "Rig {slot} in the ground. Two minutes, and it should have something for us.",
                           "Rig {slot} placed, Commander. Do remember where.",
                           "Rig {slot} down. I shall keep the register; the ground keeps the ore.",
                           "Rig {slot} at work. A tidy placement."),
            "rig_ready": ("Rig {slot} should be ready, Commander. It has waited its two minutes.",
                          "Rig {slot} is ready to collect. Punctual, as rigs go.",
                          "Rig {slot} has finished. I recommend collecting it before it feels neglected.",
                          "Collect rig {slot} at your convenience. Which is now.",
                          "Rig {slot}: ready. The register would like it back."),
            "rig_collected": ("Rig {slot} recovered. {left} still on the surface.",
                              "Rig {slot} aboard, Commander. {left} remain in the field.",
                              "Rig {slot} collected. The other {left} await your attention.",
                              "One more rig home. {left} outstanding, and I am keeping count.",
                              "Rig {slot} recovered intact. {left} to go."),
            "rig_all_collected": ("Every rig recovered, Commander. The register balances.",
                                  "All rigs collected. Nothing left on the surface but tyre tracks.",
                                  "Rigs all aboard. A tidy end to the operation.",
                                  "No rigs outstanding. I appreciate thoroughness.",
                                  "All recovered. The equipment ledger is pleased."),
            "rig_far": ("Rig {slot} is {km} km behind, Commander. The game reclaims it at five.",
                        "We are {km} km from rig {slot}. I advise against further exploration in this direction.",
                        "Rig {slot} at {km} km. Please turn back before it becomes a write-off.",
                        "A reminder: rig {slot} is {km} km away. Five, and it is gone.",
                        "Rig {slot}, {km} km. I have begun drafting the loss report, reluctantly."),
            "rig_lost": ("Rig {slot} is lost, Commander. Five kilometres was the limit.",
                         "Rig {slot} has been reclaimed. I shall file the loss without editorial comment.",
                         "We have lost rig {slot}. A lesson in distance, entered in the log.",
                         "Rig {slot}: gone. I did mention the five kilometres.",
                         "Rig {slot} written off. Regrettable."),
            "rigs_left_behind": ("We left rigs on {body}, Commander. They are lost now.",
                                 "Rigs abandoned on {body}. I have recorded it with some sorrow.",
                                 "The rigs on {body} stay there. Next time, collect before departing.",
                                 "{body} keeps our rigs. An expensive souvenir.",
                                 "Rigs left behind on {body}. The equipment ledger is unimpressed."),
        },
    },
    "axiom": {
        "plain": {
            "mined_surface": ("Rhino: {material}.", "Rig yield: {material}.", "{material} refined.", "{material}, from the rigs.",
                              "Refined in the Rhino: {material}."),
            "rig_placed": ("Rig {slot}: placed.", "Rig {slot} down.", "Rig {slot} deployed.", "Rig {slot} active."),
            "rig_ready": ("Rig {slot}: ready.", "Collect rig {slot}.", "Rig {slot} finished.", "Rig {slot} ready."),
            "rig_collected": ("Rig {slot} collected. {left} out.", "Rig {slot} back. {left} left.", "{left} rigs remaining.",
                              "Rig {slot} recovered."),
            "rig_all_collected": ("All rigs collected.", "Rigs: none out.", "Every rig recovered.", "Rig count: zero out."),
            "rig_far": ("Rig {slot}: {km} km.", "Rig {slot} at {km} km. Limit 5.", "{km} km to rig {slot}.",
                        "Rig {slot} far: {km} km."),
            "rig_lost": ("Rig {slot} lost.", "Rig {slot}: gone.", "Rig {slot} out of range.", "Rig {slot} reclaimed."),
            "rigs_left_behind": ("Rigs left on {body}.", "{body}: rigs lost.", "Rigs abandoned: {body}.", "Rigs not recovered."),
        },
        "voiced": {
            "mined_surface": ("{material} refined in the Rhino. The rigs are producing. I am tallying.",
                              "Rig yield: {material}. Ground truth, converted to cargo.",
                              "More {material}. The deposit is consistent. I like consistent deposits.",
                              "{material} from the rigs. My yield estimate just went up.",
                              "The Rhino refined {material}. One more line in the ledger.",
                              "{material}. Surface mining is slow, but the data is excellent."),
            "rig_placed": ("Rig {slot} placed. I have recorded its exact position. The journal will not.",
                           "Rig {slot} active. Estimated useful time: two minutes.",
                           "Rig {slot} down. Spacing looks correct. I checked.",
                           "Rig {slot} deployed. Another sampling point in the grid.",
                           "Rig {slot} in the ground. I am already curious what it finds."),
            "rig_ready": ("Rig {slot} has run two minutes. Ready to collect.",
                          "Rig {slot}: ready. The yield should be waiting.",
                          "Rig {slot} finished. Please collect. I would like the numbers.",
                          "Collect rig {slot}. It has completed its cycle.",
                          "Rig {slot} is ready. Timing confirmed."),
            "rig_collected": ("Rig {slot} recovered. {left} still out. I am tracking all of them.",
                              "Rig {slot} back. {left} remaining in the field.",
                              "Rig {slot} collected. {left} to go. The count is shrinking nicely.",
                              "Rig {slot} aboard. {left} rigs still working.",
                              "One recovered. {left} outstanding."),
            "rig_all_collected": ("All rigs recovered. Rigs in the field: zero. My favourite count.",
                                  "Every rig collected. A complete set.",
                                  "No rigs outstanding. The operation closes cleanly.",
                                  "All rigs aboard. Final yield ready for the ledger.",
                                  "Rigs all collected. Nothing lost. I checked twice."),
            "rig_far": ("Rig {slot} is {km} km away. The game removes rigs at 5 km. I recommend returning.",
                        "{km} km from rig {slot}. The margin is shrinking. I measured.",
                        "Rig {slot}: {km} km. Probability of losing it: rising.",
                        "Distance to rig {slot}: {km} km. Please turn back before 5.",
                        "Rig {slot} at {km} km. I would prefer to keep it."),
            "rig_lost": ("Rig {slot} lost. It exceeded 5 km. I recorded the moment.",
                         "Rig {slot} reclaimed by the game. Its data is gone. I am sad about the data.",
                         "We lost rig {slot}. Distance limit exceeded.",
                         "Rig {slot}: gone. I would like to avoid repeating that.",
                         "Rig {slot} out of range and removed."),
            "rigs_left_behind": ("Rigs left on {body}. They are lost now. Unrecovered data, too.",
                                 "We left rigs on {body}. I recommend collecting before leaving next time.",
                                 "{body} keeps our rigs. An unfortunate result.",
                                 "Rigs abandoned on {body}. I have noted the loss.",
                                 "The rigs on {body} were not recovered. Lesson recorded."),
        },
    },
    "meridian": {
        "plain": {
            "mined_surface": ("Rhino: {material}.", "Rig yield: {material}.", "{material} refined.", "{material}, from the rigs.",
                              "{material} in the Rhino's hold."),
            "rig_placed": ("Rig {slot} down.", "Rig {slot} set.", "Rig {slot} placed.", "Rig {slot} working."),
            "rig_ready": ("Rig {slot} ready.", "Collect rig {slot}.", "Rig {slot} done.", "Rig {slot} finished."),
            "rig_collected": ("Rig {slot} aboard. {left} out.", "Rig {slot} collected. {left} left.", "{left} rigs still out.",
                              "Rig {slot} recovered."),
            "rig_all_collected": ("All rigs aboard.", "Every rig recovered.", "No rigs out.", "All rigs in."),
            "rig_far": ("Rig {slot}: {km} km.", "Rig {slot} {km} km back.", "{km} km to rig {slot}.", "Rig {slot} far: {km} km."),
            "rig_lost": ("Rig {slot} lost.", "Rig {slot} gone.", "Lost rig {slot}.", "Rig {slot} out of range."),
            "rigs_left_behind": ("Rigs left on {body}.", "{body}: rigs lost.", "Rigs abandoned on {body}.", "Rigs not recovered."),
        },
        "voiced": {
            "mined_surface": ("{material} from the rigs. Honest ground, honest yield.",
                              "The Rhino's refined {material}. The holds are filling, slow and sure.",
                              "Rig yield: {material}. Like hauling nets, Commander. Steady work.",
                              "More {material}. The ground's giving freely today.",
                              "{material} aboard the Rhino. A miner's patience, rewarded.",
                              "{material}, refined. Another tonne for the tally."),
            "rig_placed": ("Rig {slot} set, Commander. Like dropping a line.",
                           "Rig {slot} in the ground. Give it two minutes.",
                           "Rig {slot} placed. I've marked it on my chart; the journal won't.",
                           "Rig {slot} down. Mind its spacing from the others.",
                           "Rig {slot} working. Good ground for it."),
            "rig_ready": ("Rig {slot} should be ready, Commander. Haul it in.",
                          "Rig {slot}'s had its two minutes. Collect it.",
                          "Rig {slot} done. Time to bring in the catch.",
                          "Rig {slot} ready. Don't leave it waiting.",
                          "Collect rig {slot}. It's finished its work."),
            "rig_collected": ("Rig {slot} aboard. {left} still out on the ground.",
                              "Rig {slot} hauled in. {left} more to fetch.",
                              "Rig {slot} recovered. {left} still working.",
                              "One rig home. {left} to go, Commander.",
                              "Rig {slot} in. Keep the other {left} in mind."),
            "rig_all_collected": ("All rigs aboard, Commander. Nothing left on the ground.",
                                  "Every rig recovered. A clean haul.",
                                  "All rigs in. A tidy operation.",
                                  "No rigs left behind. Good seamanship, on land.",
                                  "All rigs home. Well done."),
            "rig_far": ("Rig {slot} is {km} km astern. The game takes it at five.",
                        "You're {km} km from rig {slot}, Commander. Turn back soon.",
                        "Rig {slot} at {km} km. Don't drift too far from your nets.",
                        "{km} km from rig {slot}. Mind the limit.",
                        "Rig {slot}, {km} km back. Five and she's lost."),
            "rig_lost": ("Rig {slot}'s lost, Commander. Drifted too far.",
                         "We've lost rig {slot}. Five kilometres was the line.",
                         "Rig {slot} gone. Like a net cut loose.",
                         "Rig {slot} taken back. A hard lesson.",
                         "Lost rig {slot}. Keep the others closer."),
            "rigs_left_behind": ("We left rigs on {body}. They're lost now, Commander.",
                                 "Rigs left behind on {body}. Next time, haul them in first.",
                                 "{body} keeps our rigs. Like nets left on the reef.",
                                 "The rigs on {body} weren't recovered.",
                                 "Rigs abandoned on {body}. A pity."),
        },
    },
}


def persona_banks(identity):
    """({topic: plain}, {topic: voiced}) for an officer, rig topics only (the
    refining lines replace the old ones; see officer_refining)."""
    banks = PERSONAS[identity]
    plain = {topic: lines for topic, lines in banks["plain"].items() if topic != "mined_surface"}
    voiced = {topic: lines for topic, lines in banks["voiced"].items() if topic != "mined_surface"}
    return plain, voiced


def officer_refining(identity):
    """(plain, plain + voiced) for an officer's Rhino refining, replacing the
    old wording, which spoke as if you'd picked materials up by hand."""
    banks = PERSONAS[identity]
    plain = tuple(banks["plain"]["mined_surface"])
    return plain, plain + tuple(banks["voiced"]["mined_surface"])


# 5.7.6: Lyra, before the survey's lines are merged in for every companion.
from voidcompass.overlays import lyra_shared as _lyra  # noqa: E402

PERSONAS["lyra"] = {"plain": dict(_lyra.RHINO["plain"]), "voiced": dict(_lyra.RHINO["voiced"])}

# 5.7.6: the Rhino survey (centre and edge, half, done) and the best patch.
from voidcompass.overlays import rhino_survey_lines as _survey  # noqa: E402

IMPORTANCE.update(_survey.IMPORTANCE)
WATCHER_NORMAL.update(_survey.WATCHER_NORMAL)
WATCHER_WEARY.update(_survey.WATCHER_WEARY)
for _identity, _banks in _survey.PERSONAS.items():
    PERSONAS[_identity]["plain"].update(_banks["plain"])
    PERSONAS[_identity]["voiced"].update(_banks["voiced"])
