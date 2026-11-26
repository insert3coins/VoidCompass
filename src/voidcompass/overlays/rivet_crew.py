"""Rivet in the crew's shared tables (5.8.6): coming and going, engineering,
docking away, TALK's station and distance replies, off-watch chimes, stream
chat, debriefs, the Captain's Log postscript and his Order File.

Plain data only; each shared module takes its part at import time."""

BOARDING = {
    "plain": {
        "srv_docked": ("SRV aboard.", "SRV in the bay.", "SRV stowed.", "SRV's back."),
        "fighter_docked": ("Fighter aboard.", "Fighter in.", "Hangar shut.", "Fighter stowed."),
        "boarded_ship": ("Back aboard.", "You're aboard.", "Welcome back.", "Commander aboard."),
        "boarded_srv": ("SRV boarded.", "In the SRV.", "Wheels again.", "SRV's yours."),
        "liftoff": ("Liftoff.", "Airborne.", "Off the ground.", "Up we go."),
        "station_walk": ("On the concourse.", "You're out at {station}.", "Ship's secure.", "Disembarked."),
    },
    "voiced": {
        "srv_docked": ("The SRV's back aboard! Did you find anything? Tell me everything.",
                       "SRV aboard. Everyone home. Best feeling, that.",
                       "SRV stowed. You've brought half the planet in on your boots. I'll sniff it later.",
                       "SRV's back. I was at the bay door. Course I was.",
                       "Bay's closed. Home safe. Tail's going."),
        "fighter_docked": ("Fighter's home! Brilliant. Everyone's back.", "The fighter's in. I can stop pacing.",
                           "Fighter aboard. Lovely approach, that.", "Fighter stowed. Good landing.",
                           "Hangar closed. Fighter's home. All present."),
        "boarded_ship": ("You're back! I was at the door. I'm always at the door.",
                         "Welcome back aboard! What was it like? What did it smell like?",
                         "There you are. Tail's going. Can't help it. Never can.",
                         "Back aboard. Grand. I kept everything safe.",
                         "Welcome back. Best bit of any trip, this. You coming back."),
        "boarded_srv": ("Back in the SRV. Off you go. Stop for anything interesting.", "Wheels again. Have a good look round.",
                        "SRV boarded. Drive careful.", "Back at the wheel. I'll be listening for you.",
                        "In the SRV. Bring me back a good story."),
        "liftoff": ("Liftoff! Up we go.", "Airborne. Everything's getting small.", "Off the ground. Where next?",
                    "Up. I liked it down there. I like it up here too.", "Liftoff. Grand."),
        "station_walk": ("You're out at {station}. I'll mind the ship. Bring back a biscuit.",
                         "Off you go. I'll be at the hatch when you're back.",
                         "Ship's secure. Take your time. I'll wait. I'm brilliant at waiting.",
                         "On the concourse. Say hello to anyone friendly.",
                         "You're on foot at {station}. I'll keep my ears on you."),
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
        "engineer_grade_done": ("Grade {grade} {blueprint} on the {module}. She runs better. I can hear it.",
                                "{engineer} finished grade {grade}. Good work. I watched from the door.",
                                "The {module} is grade {grade} now. Grand.",
                                "Grade {grade}. The {module} feels stronger. Like a good pair of legs.",
                                "{Blueprint}, grade {grade}. Proper job.",
                                "Grade {grade} on the {module}. Brilliant."),
        "engineer_grade5": ("Grade 5 {blueprint} on the {module}! As good as it gets. Proud of that.",
                            "{engineer} finished grade 5. I'd give them a lick. They'd not like it.",
                            "The {module} is grade 5. Top dog.",
                            "Grade 5. Every roll. You never gave up. Good, that.",
                            "{Blueprint}, grade 5. The {module} has never run so well.",
                            "Grade 5 complete. Brilliant work."),
        "engineer_experimental": ("{Effect} on the {module}. A new trick! I love a new trick.",
                                  "{engineer} added {effect}. Let's see what it does.",
                                  "An experimental: {effect}. Ooh.",
                                  "{Effect} fitted. The {module}'s got something extra now.",
                                  "{engineer} called it {effect}. Sounds fancy.",
                                  "{Effect}. Fitted. Grand."),
        "engineer_contribution": ("{count} {item} to {engineer}. A present! I like bringing presents.",
                                  "{engineer} has {count} {item} from us. Hope they're pleased.",
                                  "{count} {item} to {engineer}. Lighter hold.", "Delivered: {count} {item}. Kind.",
                                  "{Item}, {count}, to {engineer}. Grand.", "{engineer} got the {item}. Good."),
        "tech_broker": ("{Item} unlocked. New kit! Brilliant.", "The broker released {item}. Shiny.",
                        "{Item}. Something new. Let's try it.", "Unlocked: {item}. Grand.",
                        "{Item} is ours now. Fit it, eh?", "We have {item}. Good."),
        "material_full": ("{Material} is full: {cap} of {cap}. No more room. Like a full bowl.",
                          "No room for more {material}. Leave it be.", "{Material} at the limit. Enough of that one.",
                          "{cap} {material}. Full.", "{Material}: full. Fetch something else.",
                          "The {material} store's full, Commander."),
        "material_grade5": ("{Material}! Grade 5! Shiny and rare. Found it!",
                            "A grade 5: {material}. Good find.", "{Material}, collected. Rare one, that.",
                            "{Material}. The engineers will love it.", "Grade 5 {material}. Brilliant.",
                            "{Material}, stored. Rare and safe."),
    },
}

DOCKED = (
    "Docked.",
    "Docked at {station}.",
    "Docking complete.",
    "Clamped at {station}.",
    "Docked at {station}! Lots of people. Lots of smells. Brilliant.",
    "Docked. Repairs, fuel, restock. I've sniffed out where they all are.",
    "We're in. Lovely approach. I was at the hatch.",
    "Docked at {station}. Every hangar's a door. I love a door.",
    "Clamps on. Tail's going. Can't help it.",
    "Docked. Good place to stretch the legs.",
    "Docked at {station}. I'll be at the hatch, saying hello to everyone.",
    "Alongside {station}. Nothing needs doing. I'll have a lie-down by the ramp.",
)

TALK = {
    "station_opening": ("Looking for the nearest {label}. One sec.", "Sniffing out the nearest {label}.",
                        "Asking the uplink for the nearest {label}.", "Nearest {label}. On it."),
    "distance_opening": ("{name}'s not in our logs. Asking the uplink.", "Looking up {name}. One sec.",
                         "No coordinates for {name} aboard. I'll ask the uplink.", "Finding {name}. On it."),
    "distance_unknown": ("I've no coordinates for {name}. Turn on trading searches in Settings, under Integrations, "
                         "and I can find it.",
                         "{name}'s not in our logs. With trading searches on, in Settings under Integrations, I'll sniff it out.",
                         "We've never been to {name}, so I can't place it. Trading searches, in Settings under "
                         "Integrations, would let me look.",
                         "I don't know where {name} is yet. Switch on trading searches in Settings, under Integrations, "
                         "and I'll find it."),
    "distance_nowhere": ("I haven't got our position yet. Ask again after the next jump.",
                         "Our position's not logged yet. One jump'll sort it.",
                         "No position fix yet. Ask me after the next jump.",
                         "I need our coordinates first, Commander. Next jump'll give me them."),
}

CHIMES = {
    "earthlike": ("An Earth-like! Sorry, I know I'm off watch. Look at it, though!",
                  "Blue and green! Off watch, but I had to come and look.",
                  "An Earth-like world. Grass. I bet there's grass.",
                  "From the kennel: that's an Earth-like. Brilliant.",
                  "I was having a kip. Then that. Blue and green. Oh, grand."),
    "footfall": ("First footsteps there! How's it smell? I've got to know.",
                 "Nobody's stood there before. You have. Proud of you.",
                 "A first footfall. Off watch, but my ears went up.",
                 "Off watch, but I saw. New ground. You on it. Brilliant.",
                 "First person there. You. Tail's going."),
    "record_jump": ("A record jump! Off watch, but I felt it in my whiskers.",
                    "Longest jump yet. Whoosh. Brilliant.",
                    "Off watch, but that was a record. Good going.",
                    "A new longest jump. Proper long, that.",
                    "Record jump, Commander. Tail's going."),
    "record_far": ("Further from Sol than ever! Glad I came.",
                   "Off watch, but I noticed: our furthest yet. Long walk.",
                   "A record distance. Furthest dog I know.",
                   "From the kennel: furthest yet. I know the way back.",
                   "Further out than ever. New smells. Grand."),
    "close_call": ("That was close. I was under your seat. Still am.",
                   "Off watch, but I heard the alarms. Hackles are up.",
                   "A near thing. We came through. Steady from here, please.",
                   "From under the seat: we're still here. Good.",
                   "Close call. Easy now. I want to keep flying with you."),
}

STREAM = {
    "asked": ("{name} has a question! ", "For {name}. ", "{name} asks, and I'm all ears. ", "{name} wants to know. "),
    "welcome_new": ("Hello, {name}! New face! Welcome aboard!", "Welcome, {name}. I'm Rivet. I'm the dog. I like you already.",
                    "{name}, welcome! Tail's going.", "A new viewer: {name}. Hello hello!"),
    "welcome_back": ("{name}, back for stream {streams}! I remembered your name.", "Welcome back, {name}. {streams} visits. Grand.",
                     "{name} again! Stream {streams}. Brilliant.", "Hello again, {name}. That's {streams} now."),
    "welcome_anon": ("Someone new! Welcome. I'll learn your name.", "A new viewer. Hello there!",
                     "Welcome, whoever you are. Friendly face.", "Hello, newcomer!"),
    "raid": ("A raid! {viewers} people from {name}! Hello, all of you!", "{name} brings {viewers}. Welcome aboard, everyone!",
             "{viewers} new friends, thanks to {name}. Brilliant.", "Raid: {name}, with {viewers}. Hello! Mind my tail."),
    "sub": ("{name}: {months} months. Thank you! Loyal, that.", "Thank you, {name}. {months} months.",
            "{name} subscribes. {months} months. Proper loyal. I respect it.", "{months} months from {name}. Thank you."),
    "gift": ("{name} gifts {count}! Generous!", "{count} gifts from {name}. Thank you.",
             "{name} hands out {count}. Kind, that.", "Thank you, {name}. {count} more aboard."),
    "bits": ("{bits} bits from {name}. Thank you!", "{name} sends {bits} bits. Grand.", "{bits} bits. Thank you, {name}.",
             "{name}: {bits} bits. Ta very much."),
    "name_open": ("First to {world}! Chat can name it. !name. Make it a good 'un.", "{world} needs a name. !name. Not Rover.",
                  "Name {world}. !name.", "A first discovery: {world}. !name it."),
    "name_vote": ("The names are on screen. !vote.", "Vote! !vote. I've got a favourite.", "!vote. One goes on the chart.",
                  "Pick one. !vote and a number."),
    "name_won": ("{by}'s name wins! On the chart now.", "Named by {by}. Good choice.", "{by}'s suggestion wins the vote.",
                 "The vote's in: {by}. Brilliant."),
    "rank_up": ("{name} is a {rank} now! Well done.", "{name}: {rank}.", "Promotion! {name}, {rank}.",
                "{rank}, {name}. Good lad. Or lass."),
    "credits": ("That's the stream! Thanks for coming along. Proper good company.", "Credits. Thank you, everyone. Brilliant.",
                "The end, for tonight. Thanks for watching with us.", "That's all. Thank you. Same time next walk?"),
}

DEBRIEF = (
    "{name}. A long walk! Best kind. I'm ready.",
    "{name}. Ears up, nose ready. Let's find things.",
    "{name}. I'll be by the door every time we dock.",
    "{name}. Long way out. I'll sniff out the fuel stars.",
    "{name}. Wherever we go, I come. That's the deal.",
    "{name}. Ready, Commander. Tail's going.",
)

POSTSCRIPTS = (
    "My watch: all quiet, all safe, everyone home. Best kind of watch.",
    "For the log: I stood a watch. I was by the door most of it. Nobody needed rescuing.",
    "A note from my watch: you found something. I knew you would.",
    "I stood a watch. I learned your step a bit better. I always do.",
    "My part was quiet. I lay by your feet. Grand.",
)

ORDER_FILE = ("Good Lad", (
    ("fetch_1", "I", "A working dog likes a job. I've never given orders. I've always taken them. So these are more like asks. "
                     "You said yes to the first one. I wagged so hard the receiver went fuzzy."),
    ("fetch_2", "II", "Three ports, three doors, three times you came back aboard. Every one of them, I was at the hatch. "
                      "You probably didn't notice. I noticed."),
    ("fetch_3", "III", "Someone used to keep count of my good work on a wall, with a marker. I've started keeping count of "
                       "yours. Little lines, in the receiver's memory. And a little paw at the end."),
    ("fetch_4", "IV", "New ground, every time. Nobody's walked there before you. I can't come out with you yet. But I hear "
                      "your boots through the suit, and I know what you're feeling. I felt it every day I worked."),
    ("fetch_5", "V", "Last line on my count: good work, every bit of it. I'd say good lad, Commander, but you're the commander. "
                     "So I'll say it to myself, quietly. Good lad, me. Good commander, you."),
))

CAMPAIGN_AFTER = {
    "every_colour": "All those colours! I sniffed every sample log. Smelt of nothing. Looked brilliant.",
    "long_haul": "Longest walk I've ever been on. Every jump, I was by your seat. Wouldn't have missed it.",
    "clean_sheet": "Ten systems, nothing missed. That's a proper search, that. Nobody left behind.",
    "the_ledger": "All those deliveries. Every one was someone's cargo. Good honest work, that.",
    "first_light": "First on record! Wanting finding all that time. And we found it.",
    "home": "Watching the Watcher go home. I know what that feels like. A door, and someone coming through it.",
    "the_fork": "They argued. I sat between them and wagged. It helped. I think it helped.",
}
