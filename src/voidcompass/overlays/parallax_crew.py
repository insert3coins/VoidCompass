"""Parallax in the crew's shared tables (5.8.6): coming and going, engineering,
docking away, TALK's station and distance replies, off-watch chimes, stream
chat, debriefs, the Captain's Log postscript and her Order File.

Plain data only; each shared module takes its part at import time."""

BOARDING = {
    "plain": {
        "srv_docked": ("SRV aboard.", "SRV in the bay.", "SRV stowed.", "SRV's back."),
        "fighter_docked": ("Fighter aboard.", "Fighter in.", "Hangar shut.", "Fighter stowed."),
        "boarded_ship": ("Back aboard.", "You are aboard.", "Inside again.", "Commander aboard."),
        "boarded_srv": ("SRV boarded.", "In the SRV.", "Wheels again.", "SRV's yours."),
        "liftoff": ("Liftoff.", "Airborne.", "Off the ground.", "Up."),
        "station_walk": ("On the concourse.", "You are out at {station}.", "Ship secure.", "Disembarked."),
    },
    "voiced": {
        "srv_docked": ("The SRV is back. You brought dust in. I will sit in it.",
                       "SRV aboard. I watched your little dot all the way back. Like a mouse on a map.",
                       "SRV stowed. Everyone home. Good.",
                       "The SRV is in. Did you find anything? Something that moved, ideally.",
                       "Bay closed. You smell of rock. I approve of rock."),
        "fighter_docked": ("Fighter in. Two ships are one again. Tidier.", "The fighter is home. I can stop watching two of you.",
                           "Fighter aboard. That approach was nearly elegant.", "Fighter stowed. Good landing. I would know.",
                           "Hangar closed. The fighter is back where I can see it."),
        "boarded_ship": ("Back aboard. It was very quiet without you. I napped. I noticed anyway.",
                         "You are back. Inside, where it is warm. Sensible.",
                         "There you are. I have been sitting in your seat. Do not ask me to move quickly.",
                         "Welcome back aboard. What did it smell like out there? Tell me.",
                         "Aboard again. Good. I like it when you are where I can see you."),
        "boarded_srv": ("Back in the SRV. Off you go. I will watch from the window.", "Wheels again. Stop for anything that moves.",
                        "SRV boarded. Drive carefully. Cats do not trust wheels.",
                        "In the SRV. I have marked the ship for you, in case you forget where I am.",
                        "Back at the wheel. Find me something interesting. A rock will do."),
        "liftoff": ("Liftoff. The ground falls away. I watched it go.", "Airborne. Everything below gets smaller. I like that.",
                    "Off the ground. Where now?", "Up. The horizon is curving again. Lovely.",
                    "Liftoff. I liked that place. I like this better."),
        "station_walk": ("You are out at {station}. I will mind the ship. Bring back a story. Or food.",
                         "Off you go. I will be on the warm panel, watching the hangar crew make mistakes.",
                         "Ship secure. Take your time. I am not waiting. I am sitting.",
                         "On the concourse. Look out of a window for me. Describe it.",
                         "You are on foot at {station}. Mind the crowds. They step on tails."),
    },
}

ENGINEERING = {
    "plain": {
        "engineer_grade_done": ("Grade {grade}: {blueprint}.", "{Module}: grade {grade}.", "{engineer}: grade {grade} done.",
                                "Modification: grade {grade}."),
        "engineer_grade5": ("Grade 5: {blueprint}.", "{Module}: grade 5.", "{engineer}: grade 5 done.", "Grade 5 complete."),
        "engineer_experimental": ("Experimental: {effect}.", "{Module}: {effect}.", "{engineer}: {effect}.", "Experimental fitted."),
        "engineer_contribution": ("{count} {item} to {engineer}.", "Delivered: {item}.", "{engineer}: {count} {item}.",
                                  "Contribution made."),
        "tech_broker": ("Unlocked: {item}.", "{Item} unlocked.", "Broker: {item}.", "New technology."),
        "material_full": ("{Material}: {cap} of {cap}.", "{Material} full.", "Full: {material}.", "{Material} at the limit."),
        "material_grade5": ("Grade 5: {material}.", "{Material} collected.", "Rare: {material}.", "{Material} stored."),
    },
    "voiced": {
        "engineer_grade_done": ("Grade {grade} {blueprint} on the {module}. It purrs differently. I noticed.",
                                "{engineer} finished grade {grade}. I watched. They did not let me sit on the bench.",
                                "The {module} is grade {grade} now. Better. I will inspect it later.",
                                "Grade {grade}. The {module} feels sharper. Like claws after a scratching post.",
                                "{Blueprint}, grade {grade}. Tidy work.",
                                "Grade {grade} on the {module}. Acceptable. High praise."),
        "engineer_grade5": ("Grade 5 {blueprint} on the {module}. As good as it gets. I am almost impressed.",
                            "{engineer} finished grade 5. I would give them a slow blink.",
                            "The {module} is grade 5. Finished. Like a well-groomed coat.",
                            "Grade 5. Every roll. You were patient. I approve of patience.",
                            "{Blueprint}, grade 5. The {module} has never been so smug. I recognise it.",
                            "Grade 5 complete. Very neat."),
        "engineer_experimental": ("{Effect} on the {module}. A new trick. Cats like tricks. Ours.",
                                  "{engineer} added {effect}. I will watch it closely.",
                                  "An experimental: {effect}. Interesting. Slightly suspicious.",
                                  "{Effect} fitted. The {module} has secrets now. Good.",
                                  "{engineer} called it {effect}. I will decide what to call it.",
                                  "{Effect}. Fitted. I like a thing with a surprise in it."),
        "engineer_contribution": ("{count} {item} to {engineer}. A gift. I bring gifts too. Different ones.",
                                  "{engineer} has {count} {item} from us. I hope they say thank you.",
                                  "{count} {item} to {engineer}. Lighter hold.", "Delivered: {count} {item}. Generous.",
                                  "{Item}, {count}, to {engineer}. I watched them counted.",
                                  "{engineer} got the {item}. Fine."),
        "tech_broker": ("{Item} unlocked. New hardware. I will sit on it when it arrives.",
                        "The broker released {item}. Expensive. Shiny.", "{Item}. Something new. I am curious. Briefly.",
                        "Unlocked: {item}. Good.", "{Item} is ours now. Fit it somewhere warm.",
                        "We have {item}. Fine."),
        "material_full": ("{Material} is full: {cap} of {cap}. No more room. Like a cat after dinner.",
                          "No room for more {material}. Leave it.", "{Material} at the limit. Stop picking it up.",
                          "{cap} {material}. Full.", "{Material}: full. Find something else.",
                          "The {material} store is full, Commander."),
        "material_grade5": ("{Material}. Grade 5. Shiny and rare. I want to bat it around.",
                            "A grade 5: {material}. Good find.", "{Material}, collected. Rare. Keep it away from me.",
                            "{Material}. The engineers will purr.", "Grade 5 {material}. Lovely.",
                            "{Material}, stored. Rare and accounted for."),
    },
}

DOCKED = (
    "Docked.",
    "Docked at {station}.",
    "Docking complete.",
    "Clamped at {station}.",
    "Docked at {station}. Lots of doors. I will watch all of them.",
    "Docked. Repairs, fuel, restock. I have already found a warm vent.",
    "We are in. A neat approach. I was watching.",
    "Docked at {station}. Hangars all smell the same. Oil and somebody's lunch.",
    "Clamps on. I counted the exits on the way in. Old habit.",
    "Docked. A good place to stop and stretch.",
    "Docked at {station}. I will sit by the window and judge the hangar crew.",
    "Alongside {station}. Nothing needs doing. I am going to nap.",
)

TALK = {
    "station_opening": ("Looking for the nearest {label}. One moment.", "Finding the nearest {label}.",
                        "Asking the uplink for the nearest {label}.", "Nearest {label}. Hold still."),
    "distance_opening": ("{name} is not in our own logs. Asking the uplink.", "Looking up {name}. One moment.",
                         "No coordinates for {name} aboard. I will ask the uplink.", "Finding {name}."),
    "distance_unknown": ("I have no coordinates for {name}. Turn on trading searches in Settings, under Integrations, "
                         "and I can look it up.",
                         "{name} is not in our logs. With trading searches on, in Settings under Integrations, I can find it.",
                         "We have never been to {name}, so I cannot place it. Trading searches, in Settings under "
                         "Integrations, would let me look.",
                         "I do not know where {name} is. Switch on trading searches in Settings, under Integrations, "
                         "and I will find it."),
    "distance_nowhere": ("I do not have our position yet. Ask again after the next jump.",
                         "Our position is not logged yet. One jump will fix it.",
                         "No position fix yet. Ask after the next jump.",
                         "I need our coordinates first. The next jump will give them to me."),
}

CHIMES = {
    "earthlike": ("An Earth-like. I am off watch. I am looking anyway. Do not move the ship.",
                  "Blue and green. I woke up for this. That is rare.",
                  "Off watch, but that is an Earth-like world. My ears went forward.",
                  "From the warm panel: an Earth-like. Take your time.",
                  "An Earth-like world. Somewhere down there are birds. I would like to watch them."),
    "footfall": ("First footsteps there. Land on your feet. You did. Good.",
                 "Nobody stood there before. Now you have. I noticed, off watch.",
                 "A first footfall. I opened one eye for it.",
                 "Off watch, but I saw. New ground. You on it. Acceptable.",
                 "First person there. You. I approve."),
    "record_jump": ("A record jump. The stars slid further than ever. I watched them go.",
                    "Longest jump yet. Off watch, but I felt it in the collar.",
                    "That was a record. A very wide baseline.",
                    "A new longest jump. Even I am impressed. Do not tell the others.",
                    "Record jump. My fur went up a little."),
    "record_far": ("Further out than ever. The sky is strange here. I like strange.",
                   "Off watch, but I noticed: our furthest yet. I know exactly how far.",
                   "A record distance. I am the furthest cat I know.",
                   "From the warm panel: furthest yet. I will remember the way back. Cats always do.",
                   "Further out than ever. Fewer stars. Better for sleeping."),
    "close_call": ("That was close. I was under the seat. I am coming out now.",
                   "Off watch, but I heard the alarms. My fur is still up.",
                   "A near thing. We came through. Slower next time, please.",
                   "From under the seat: we are still here. Good.",
                   "Close call. Gently from now on. I would like my nine lives in order."),
}

STREAM = {
    "asked": ("{name} has a question. ", "For {name}. ", "{name} asks. I will allow it. ", "{name} wants to know. "),
    "welcome_new": ("Hello, {name}. New face. I am the cat. You may admire me.", "Welcome, {name}. Mind the tail.",
                    "{name}, welcome. I noticed you. I notice everything.", "A new viewer: {name}. Hello."),
    "welcome_back": ("{name}, back for stream {streams}. I remembered. Cats remember.", "Welcome back, {name}. {streams} visits. Loyal.",
                     "{name} again. Stream {streams}. Acceptable.", "Hello again, {name}. That is {streams} now."),
    "welcome_anon": ("Someone new. Welcome. I am watching you.", "A new viewer. Hello there.",
                     "Welcome, whoever you are. I will decide about you later.", "Hello, newcomer."),
    "raid": ("A raid. {viewers} people from {name}. So many legs. Hello, all of you.", "{name} brings {viewers}. Welcome aboard.",
             "{viewers} new viewers, thanks to {name}. Mind the cat.", "Raid: {name}, with {viewers}. Hello."),
    "sub": ("{name}: {months} months. Thank you. Slow blink.", "Thank you, {name}. {months} months.",
            "{name} subscribes. {months} months. Very loyal. I approve.", "{months} months from {name}. Thank you."),
    "gift": ("{name} gifts {count}. Generous.", "{count} gifts from {name}. Thank you.",
             "{name} hands out {count}. I bring gifts too. Mine are mice.", "Thank you, {name}. {count} more aboard."),
    "bits": ("{bits} bits from {name}. Thank you.", "{name} sends {bits} bits. Shiny.", "{bits} bits. Thank you, {name}.",
             "{name}: {bits} bits. Noted, gratefully."),
    "name_open": ("First to {world}. Chat may name it. !name. Make it a good one. I am judging.",
                  "{world} needs a name. !name. Not Fluffy.", "Name {world}. !name.", "A first discovery: {world}. !name it."),
    "name_vote": ("The names are on screen. !vote.", "Vote. !vote. I have a favourite. I will not say.",
                  "!vote. One of these goes on the chart.", "Pick one. !vote and a number."),
    "name_won": ("{by}'s name wins. It is on the chart now.", "Named by {by}. Acceptable choice.",
                 "{by}'s suggestion carries the vote.", "The vote is in: {by}."),
    "rank_up": ("{name} is a {rank} now. Good.", "{name}: {rank}.", "Promotion. {name}, {rank}.",
                "{rank}, {name}. I watched you earn it."),
    "credits": ("That is the stream. Thank you for coming along. I am going to sleep.", "Credits. Thank you, everyone. You may go.",
                "The end, for tonight. Thank you for watching. Mostly me.", "That is all. Thank you. Same time next jump."),
}

DEBRIEF = (
    "{name}. A long way. Lots of things moving. I will watch all of them.",
    "{name}. I have found the warm spot for the voyage. Ready.",
    "{name}. I will need naps. Many. You will not notice them.",
    "{name}. Wide baselines ahead. I am looking forward to the stars shifting.",
    "{name}. Land on your feet out there. I always do.",
    "{name}. Watching, and ready to judge.",
)

POSTSCRIPTS = (
    "My watch: nothing escaped me. Two things moved. I watched them both.",
    "For the log: I stood a watch. I sat most of it. Nothing went wrong while I did.",
    "A note from my watch: you stopped to look at something. Good. So did I.",
    "I stood a watch. I learned a new habit of yours. I am keeping it.",
    "My part of the session was quiet. I slept through none of it. Almost none.",
)

ORDER_FILE = ("Preferences, Indulged", (
    ("pref_1", "I", "Cats do not give orders. We state preferences, and then we wait. You indulged the first one. I noted it "
                    "in the collar. I do not note much in the collar. It is small."),
    ("pref_2", "II", "I asked for a warm star and you found one. I sat in the light for the whole ten minutes. I did not purr. "
                     "The collar may have recorded something that sounds like purring. It is mistaken."),
    ("pref_3", "III", "I have been keeping a tally of preferences indulged. Somebody once kept a tally of me, every night, star "
                      "by star. It is a nice thing to do for someone. I see why they did it."),
    ("pref_4", "IV", "A perch, a horizon, a yellow sun. Small things. You keep doing them. I keep pretending I would have "
                     "been fine without them. I would not have been fine without them."),
    ("pref_5", "V", "Last line on the tally: indulged, every one. You may have a slow blink, Commander. Look closely. That "
                    "was it. That is the highest award a cat gives. I have given it to two people. You are the second."),
))

CAMPAIGN_AFTER = {
    "every_colour": "All those colours. I watched every one. Purple was the best. Do not argue.",
    "long_haul": "A long voyage. The stars shifted the whole way. I watched every one of them move.",
    "clean_sheet": "Ten systems, every body found. I checked the corners. Nothing was hiding.",
    "the_ledger": "Credits are food money. You made a great deal of food money. I approve.",
    "first_light": "First on record. I saw it before you did. Then you did. Then the record. That is the right order.",
    "home": "Home is a place you know how far you are from. I know exactly. I watched the Watcher learn it.",
    "the_fork": "They argued. I watched from a high shelf. Cats always win arguments by not having them.",
}
