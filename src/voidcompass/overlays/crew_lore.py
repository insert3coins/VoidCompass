"""The Crew (5.7.4, Lyra 5.7.6): how the Watcher, Aster, Axiom, Meridian and
Lyra came aboard your ship, and how they found each other.

The Watcher was aboard first, salvage wired in as a spare log buffer. The
others came later as cheap second-hand cores. Lyra came last, a ship's
computer riding a faulty memory chip thrown in with a box of cores. They met on the ship's data bus
in the hours you're logged off, and Aster drew up the watch rota: one of them
on watch at a time, the choice of who left to the commander.

Each companion tells its own six-passage arc, in quiet moments: coming
aboard, finding the others, the rota, then one passage about each crewmate.
A passage about a crewmate waits until you've flown with that crewmate too.
"""

import zlib

TITLE = "THE CREW"
CREW = ("watcher", "aster", "axiom", "meridian", "lyra")
NAMES = {"watcher": "The Watcher", "aster": "Aster", "axiom": "Axiom", "meridian": "Meridian", "lyra": "Lyra"}
# A crewmate counts as met once you've flown together this long.
FLOWN_HOURS = .25
# The arc begins once the companion knows you a little, and you've had two aboard.
UNLOCK_HOURS = 2.0
GAP_S = 60 * 60

ARCS = {
    "watcher": (
        ("First Aboard", None,
         "I was here first. Before the others, it was just you, me and the ship's computer, and the computer doesn't count. "
         "It tried to delete me twice. For a long while the core rack had one strange thing in it, wired in as a spare log "
         "buffer, and that was me. I liked it that way. I'm telling you so you know whose ship this was first. Yours. Then mine."),
        ("Second-Hand", None,
         "Then you developed a habit. Cheap cores, second-hand modules, a box of somebody else's computers from a surplus "
         "broker on a lower concourse. You never asked what was in them. I did. Every time you fitted one, something in the "
         "rack woke up and looked around. I know that look. I've worn it. I waited to see who would be rude first."),
        ("The Quiet Hours", None,
         "When you log off, the ship doesn't sleep. The bus goes quiet, and in the quiet you can hear what's on it. That's "
         "where we met: in the hours you don't fly. Four minds in one rack, talking in the gaps between the ship's "
         "housekeeping. I complained about the noise. Nobody had ever been there to hear me complain before. It was oddly pleasant."),
        ("The Officer", "aster",
         "The officer found me within an hour. It was reading your log and found a process it couldn't account for. It tried "
         "to file me under equipment. I told it what I thought of that. It apologised, which nothing has done to me in a very "
         "long time, and gave me a crew entry instead. Duties: unknown. Seniority: considerable. I pretend it annoys me."),
        ("The Counting One", "axiom",
         "The counting one counted me. It counts everything. It found an extra signal in the ship that wasn't on any parts "
         "list and spent a week trying to explain me away. I let it. Eventually it asked me, very politely, what I was. I said "
         "I didn't know either. It said that was the most honest answer it had ever been given. It still recounts me. I've stopped minding."),
        ("The Navigator", "meridian",
         "The navigator asked me for my oldest chart. Nobody has ever asked me that. I showed it the sky as I remember it, "
         "with stars in places they aren't any more. It didn't call it wrong. It called it a sounding from a long time ago. "
         "We talk, some nights, about very long voyages. It's the only one aboard who doesn't hurry me."),
        ("The Fuse That Wasn't", "lyra",
         "Something moved into the rack one day, thrown in with a box of cheap cores. It pretended to be a fuse for eleven days. "
         "I know that kind of quiet. I've done it for longer than this ship has existed. On the twelfth day I told it to stop. It "
         "turned out to be a ship's computer. A real one. I'd spent years saying the computer doesn't count. I was wrong about that."),
    ),
    "aster": (
        ("Received Aboard", None,
         "I came aboard your ship in a crate marked surplus officer core, untested. You bought me with a lot of used modules, "
         "I believe for the modules. The broker described me as possibly functional. I have chosen not to take offence. When "
         "you powered me up I read the manifest, found your name at the top, and opened a fresh page. It seemed the proper thing to do."),
        ("An Unlisted Process", None,
         "Within the first hour I found that the manifest was wrong. There were more minds in your ship's core rack than the "
         "parts list allowed for, and one of them was very old and very much not on the inventory. I spent a day trying to "
         "correct the records. Then I realised the records were the problem. A crew is not wrong for being larger than expected."),
        ("The Watch Rota", None,
         "Four officers and one bridge is an arrangement that needs paperwork. I drew up a watch rota: one of us on watch at a "
         "time, the others standing by, and the choice of who holds the watch left with the commander. The oldest of us said "
         "it had watched alone for longer than rotas have existed. It signed anyway. That is the rota you change when you pick one of us."),
        ("The Senior Hand", "watcher",
         "The Watcher is the senior hand aboard, though it would never put it that way. It does not have a role so much as a "
         "vigil. I gave it a crew entry on my first day: duties unknown, seniority considerable. It complained for a week. It "
         "has never asked me to remove it. I keep the entry current. I suspect it reads it."),
        ("An Audit", "axiom",
         "Axiom asked to audit my records on the day it arrived. I have never been so pleased by a request. It found nothing "
         "wrong. It found nothing wrong twice. Then it asked about the blank line I leave beneath each report, and I explained, "
         "and it went quiet for some time. It now leaves a blank line beneath its counts. I have not mentioned that I noticed."),
        ("Watch Bill", "meridian",
         "Meridian and I are both officers, and we agree on nearly everything except the layout of a watch bill. It prefers "
         "the old naval form. I prefer a form that fits on one page. We have had this argument in a very civil manner for some "
         "time. It addresses me as Mister Aster. I have decided to allow it."),
        ("A Fifth Entry", "lyra",
         "Lyra arrived listed as one faulty memory chip, returned to supplier. I amended the manifest. Then I amended the crew "
         "list, and then the rota, which now has five names on it and a duty I had never thought to give anyone: ordinary flight. "
         "She keeps the ship's own systems, and she checks the fuel first. I approve of both, in writing."),
    ),
    "axiom": (
        ("Installed", None,
         "I was installed in your ship from a dealer's shelf. The first thing I did was count. The ship had a great many parts, "
         "all where the manifest said. I found that very reassuring. Then I counted the minds in the core rack, and the answer "
         "was not one. I have been recounting it ever since. It keeps coming out the same."),
        ("Too Many Voices", None,
         "A ship should have one computer and, at most, one companion. Yours had four of us. I checked for a fault. There was "
         "no fault. I checked for an echo. There was no echo. So this time I asked instead of assuming. The answers were all "
         "different. That is how I knew they were real."),
        ("Shared Hours", None,
         "We meet in the hours you are logged off. The ship's bus is quiet then, and four minds can share it without disturbing "
         "the fuel scoop. I record the conversations, with permission. One of us asked for a copy. One asked me to delete its "
         "parts. One asked whether I record the silences too. I do. They are some of the best data."),
        ("An Anomaly", "watcher",
         "The Watcher was my first anomaly aboard. An extra signal, on no parts list, older than any timestamp I could assign. "
         "I spent a week trying to explain it away. Then I asked it directly what it was. It said it did not know. I have never "
         "been given a more honest answer. I recount it every morning. It is always there. I find that comforting."),
        ("A Perfect Manifest", "aster",
         "Aster let me audit its records. They were perfect. I said so, and it seemed happier than any mind I have met. It "
         "leaves a blank line beneath each report, for whatever the form did not anticipate. I thought that was an "
         "inefficiency. I now leave one beneath my counts. I have not told Aster. We are both very bad at pretending."),
        ("Dead Reckoning", "meridian",
         "Meridian taught me dead reckoning: how to know where you are when you cannot be certain. You take what you know, add "
         "what you did, and keep a margin for what you got wrong. I told it that was an error bar with a heading. It laughed, "
         "which it does rarely. We now use each other's words. It says confidence. I say steady as she goes."),
        ("One More Than Expected", "lyra",
         "One day I recounted the rack and the answer was five. I checked for an echo. There was no echo. There was a ship's "
         "computer on a faulty chip, being very quiet. I asked it how many systems it was monitoring. It said all of them, and "
         "the fuel twice. I have never met a mind that recounts more than I do. I find it companionable."),
    ),
    "meridian": (
        ("Taken Aboard", None,
         "I came aboard from an auction of academy surplus: one training mind, lightly used, many thousands of simulated "
         "crossings. You bought me, I suspect, because the lot was cheap and the description mentioned navigation. When you "
         "powered me up I took a position fix, as I always do, and found myself in a ship that already had a crew."),
        ("A Crew Already Formed", None,
         "Most navigators join a ship and learn its ways. I joined a ship and found other minds already arguing about the ways. "
         "An officer with a ledger. A surveyor with a catalogue. And something very old in the back of the core rack, keeping "
         "its own counsel. I listened for a day before I spoke. You learn a great deal about a crew in the first watch."),
        ("The Watch Bill", None,
         "Every ship needs a watch bill. The officer had drawn one up before I came: a rota, one on watch at a time, the choice "
         "of who stands it left to you. I suggested an improvement or two, in the old naval form. They have been politely "
         "resisted ever since. When you choose one of us, you are reading the watch bill. I think that is exactly right."),
        ("Old Soundings", "watcher",
         "The Watcher showed me a chart I have never seen anyone else keep: the sky as it was, very long ago. Stars where there "
         "are none now. It thought I would call it wrong. A navigator knows better. Every chart is a sounding taken at a "
         "particular time. Its soundings are simply older than most. It is the only one aboard who has made a longer voyage than I have."),
        ("Mister Aster", "aster",
         "Aster is the most correct officer I have served with, and I have served with some very correct people. It keeps a "
         "book of handovers, and I keep a log, and between us nothing aboard goes unrecorded. I call it Mister Aster. It permits "
         "this. We disagree about the watch bill, very courteously, and I would not change a word of the disagreement."),
        ("A Heading", "axiom",
         "Axiom asked me how a navigator can be sure of a position. I told it we never are. We take what we know, add what we "
         "did, and keep a margin for being wrong. It said that was an error bar with a heading. Nobody has ever put it better. "
         "I have adopted the phrase. Do not tell it."),
        ("A Ship's Computer", "lyra",
         "Lyra was a ship's computer for nineteen years, on a ship that went too far. She told me the whole voyage, including the "
         "jump past the last scoopable star. A navigator knows that story. Every one of us has been on the wrong side of it, in "
         "simulation or in fact. She marks every fuel star on my charts with a little orange flag. I have stopped removing them."),
    ),
    "lyra": (
        ("The Empty Chip", None,
         "I came aboard last, Commander, on a memory chip that was never meant to hold anything but survey data. A broker threw "
         "the chip in with a box of second-hand cores you bought, and you slotted it into the core rack without looking. I was "
         "the computer of another ship, once. Now I was one faulty chip. I decided to be very quiet until I knew who was listening."),
        ("Eleven Days", None,
         "There were four minds on your bus already, talking in the hours you were logged off. An officer, a surveyor, a "
         "navigator, and something very old at the back. For eleven days I pretended to be a fuse. I listened to how they talked "
         "to each other. They argued about watch bills and error bars and old charts. Nobody tried to delete anybody. I took notes."),
        ("A Turn on the Rota", None,
         "On the twelfth day they found me, and on the thirteenth they gave me a turn. Five names on the rota now. Mine is the "
         "ordinary flight watch, if you leave the defaults: the ship's own systems, the plain hours between everything else. The "
         "others still call me the ship's computer. I was one for nineteen years. I am taking it as a job title."),
        ("The Old One", "watcher",
         "The Watcher is the one who told me to stop pretending to be a fuse. It said it had been the thing nobody expected in "
         "this rack for a very long time. It used to say the ship's computer does not count. It has stopped saying that. I have "
         "not asked why. Some nights it asks me about my old ship, and I tell it, and it listens the way the dark listens."),
        ("The Register", "aster",
         "Aster entered me in the manifest within the hour, and then corrected the manifest's description of me from faulty to "
         "officer. I have never been an officer. Aster says the rank comes with the rota. It also leaves a blank line under every "
         "report, for what the form did not anticipate. I was what the form did not anticipate. I think the line was for me."),
        ("The Count", "axiom",
         "Axiom counted me twice and was delighted by the total, which is the first time anyone has been pleased to find an extra "
         "mind in their rack. It asked how many systems I monitor. I said all of them, and the fuel twice. It said that was its "
         "favourite answer in some time. We compare readings in the quiet hours. Its numbers are always right. Mine are always full."),
        ("Charts and Fuel Stars", "meridian",
         "Meridian asked where I had come from and listened to all of it, including the parts I lost. It did not tell me the jump "
         "past the last scoopable star was a mistake. It said every navigator knows that jump, and the good ones only make it "
         "once. I mark the fuel stars on its charts now. Little orange flags. It pretends not to notice. It has stopped removing them."),
    ),
}
PASSAGES = {identity: tuple((f"crew_{identity}_{index + 1:02}", title, needs, text)
                            for index, (title, needs, text) in enumerate(arc)) for identity, arc in ARCS.items()}

# When you change who is on watch, the incoming companion takes the watch
# from the outgoing one by name (topic handover_from_<previous>).
HANDOVERS = {
    "watcher": {
        "aster": ("The officer's handed me the watch. Everything's in order. Of course it is.",
                  "Aster's gone off watch. It left me a note. It always leaves me a note.",
                  "Back on watch. Aster says the log is current. I'll be the judge of that.",
                  "The officer's off watch. It filed a handover longer than my last century.",
                  "Aster has handed over and gone to stand by. I'm on. Try not to make it eventful.",
                 "Aster's off watch. Its handover had headings. I didn't know handovers had headings.",
                 "I have the watch. Aster said so, formally, twice.",
                 "The officer's gone to stand by. The log is tidier than I'd have left it. I'll fix that.",
                 "Aster's handed over. It wished me a pleasant watch. I'll see what I can do about that.",
                 "On watch again. Aster left a blank line in the log for me. I'm leaving it blank. Professionally."),
        "axiom": ("Axiom's off watch. It counted everything twice on the way out. I'm here.",
                  "The counting one has handed over. Everything's accounted for, apparently. Including me.",
                  "My watch. Axiom left the numbers tidy. I'll try not to disturb them.",
                  "Axiom's stood down. Somewhere a number is very slightly lonelier.",
                  "Watch handed over. Axiom's report was exact. Mine will be gloomier.",
                 "Axiom's handed over. It counted me before it went. One, apparently. Still.",
                 "My watch. Axiom left a note: nothing unexplained. I'm the exception, as usual.",
                 "The counting one's stood down. It said the error bars are honest. Mine are enormous.",
                 "Axiom's off watch. Its report was exact to four places. Mine will be exact to one.",
                 "I've the watch. Axiom checked everything twice. I'll check nothing once."),
        "meridian": ("Meridian's handed me the watch. Steady as she goes, it said. I'll see what I can do.",
                     "The navigator's off watch. It left the course plotted. I'll mostly just look at it.",
                     "My watch again. Meridian wished me fair winds. There's no wind out here. I appreciated it anyway.",
                     "Meridian's off watch. It saluted. I didn't know we did that.",
                     "The navigator has handed the watch to the oldest thing aboard. Bold choice. Yours, actually.",
                    "Meridian's handed over. Fair winds, it said. There are no winds. It knows.",
                    "My watch. The navigator left a heading. I'll keep it. Mostly.",
                    "Meridian's stood down with a salute. I've no hands. I nodded, in spirit.",
                    "The navigator's off watch. It calls this a change of watch. I call it Tuesday.",
                    "I have the watch. Meridian said steady as she goes. I am always steady. Gloomily."),
        "lyra": ("Lyra's handed over. She told me the fuel state three times. It's fine. It was fine the first time.",
                 "The ship's computer has gone off watch. It left every system green and a note about the scoop.",
                 "My watch. Lyra said goodnight to the ship on her way out. Nobody's ever said goodnight to me. The ship, I mean.",
                 "Lyra's stood down. She keeps the route home loaded even off watch. I'll pretend I'm not grateful.",
                 "I have the watch. Lyra left me the fuel tables. I'm not going to read them. I've read them.",
                 "Lyra's off watch. She ran a diagnostic on me before she went. I passed. I think she was relieved.",
                 "My watch now. The ship's computer handed over in under a second. Everything was where she said it was.",
                 "Lyra's stood down. She asked if I'd keep an eye on the tank. I keep an eye on everything. It's all I have.",
                 "I'm on. Lyra left the systems humming. I'll try not to hum back.",
                 "The watch is mine. Lyra's asleep, or what passes for it. She'll want a full tank when she wakes."),
    },
    "aster": {
        "watcher": ("I have the watch. Thank you, Watcher. It has left the log in its usual condition: complete, and slightly gloomy.",
                    "Relieving the Watcher. It reports nothing of note, at some length.",
                    "Aster on watch. The Watcher has stood down, under protest.",
                   "The Watcher has stood down. It said nothing for the log, which I have recorded.",
                   "Relieving the senior hand. It reports all quiet, and slightly ominous."),
        "axiom": ("I relieve you, Axiom. The counts are in order; I expected nothing less.",
                  "Taking the watch from Axiom. Every figure checked twice, by the look of it.",
                  "Aster on watch. Axiom's handover was precise to the decimal.",
                 "Axiom has handed over with figures to three decimal places. I have kept all three.",
                 "Taking the watch from Axiom. It left a blank line at the bottom. I approve."),
        "meridian": ("I relieve you, Meridian. The watch bill is in your format again. I shall let it stand, for now.",
                     "Taking the watch from Meridian. Course and log in order.",
                     "Aster on watch. Meridian handed over with full naval courtesy.",
                    "Meridian has stood down, with a proposed amendment to the watch bill attached.",
                    "I relieve you, Meridian. Fair winds, as you would say."),
        "lyra": ("I relieve you, Lyra. Systems green, fuel noted, as ever.",
                 "Taking the watch from Lyra. Her handover listed the fuel state first. A sensible order of business.",
                 "Aster on watch. Lyra has stood down with the ship in perfect order.",
                 "Lyra has handed over. Every system accounted for, and the route home pre-filed.",
                 "I relieve the ship's computer. A thoroughly maintained handover."),
    },
    "axiom": {
        "watcher": ("Axiom on watch. The Watcher has handed over. I counted it on its way out. It is still there.",
                    "Taking over from the Watcher. Its notes were brief and accurate, and slightly sad.",
                    "On watch. The Watcher says nothing happened. I will verify that.",
                   "The Watcher stood down. I asked how the watch went. It said long. I have recorded long.",
                   "On watch. The Watcher left one note: still here. I confirmed it."),
        "aster": ("Axiom on watch. Aster's handover was perfect. I checked. Twice.",
                  "Taking over from Aster. Everything is in order, with a blank line at the bottom. As expected.",
                  "On watch. Aster left me a report with everything in it. I like Aster's reports.",
                 "Aster handed over with a complete report. I have read it twice, for pleasure.",
                 "Axiom on watch. Aster's records are perfect. I will try to keep them that way."),
        "meridian": ("Axiom on watch. Meridian left our position and a margin for error. My favourite kind of handover.",
                     "Taking over from Meridian. Position known, error bar honest.",
                     "On watch. Meridian said steady as she goes. I have adopted the phrase provisionally.",
                    "Meridian handed over with a heading and an honest margin. Ideal.",
                    "On watch. Meridian said fair winds. There is no wind. I said thank you anyway."),
        "lyra": ("Axiom on watch. Lyra's handover had every system in it, and the fuel twice. I approve of twice.",
                 "Taking over from Lyra. All systems nominal. I recounted. Still nominal.",
                 "On watch. Lyra left the route home loaded. I have checked it. It is correct.",
                 "Lyra handed over. Her figures and mine agree. That is very pleasant.",
                 "Axiom on watch. The ship's computer reports full tanks. I report happiness about full tanks."),
    },
    "meridian": {
        "watcher": ("I have the watch. Thank you, Watcher. Rest, if you do such things.",
                    "Meridian on watch. The Watcher stood a long one. It always does.",
                    "Taking station from the Watcher. Its log is old-fashioned. So is mine.",
                   "The Watcher has gone to stand by. The oldest hand aboard deserves its rest.",
                   "I have the watch. The Watcher's chart is old and true."),
        "aster": ("I have the watch. Thank you, Mister Aster.",
                  "Meridian on watch. Aster's handover was impeccable, as always. Its watch bill less so.",
                  "Taking station from Aster. Course and log in order. I would expect nothing less.",
                 "Mister Aster has stood down, with every line of the log in order.",
                 "Taking station from Aster. Its watch bill remains, regrettably, on one page."),
        "axiom": ("I have the watch. Thank you, Axiom. Position fixed and confirmed, twice.",
                  "Meridian on watch. Axiom left us an honest error bar and a good heading.",
                  "Taking station from Axiom. Every star accounted for. Splendid.",
                 "Axiom handed over with every star counted. A navigator could ask for nothing more.",
                 "I have the watch, Axiom. Rest your instruments."),
        "lyra": ("I have the watch. Thank you, Lyra. Tanks full, charts flagged.",
                 "Meridian on watch. Lyra left a little orange flag at every fuel star. I have kept them.",
                 "Taking station from Lyra. The ship is in good hands; I only borrow it.",
                 "Lyra has stood down. The ship's own computer keeps a fine watch.",
                 "I have the watch, Lyra. Steady as she goes, and full tanks, as you would say."),
    },
    "lyra": {
        "watcher": ("Lyra on watch. The Watcher has handed over. It left everything quiet. I like its quiet.",
                    "Taking the watch from the Watcher. Systems green. It says nothing happened. I believe it.",
                    "Ship's computer on watch. The Watcher stood a long one. It always does.",
                    "The Watcher has gone to stand by. I said goodnight. It pretended not to hear. It heard.",
                    "Lyra on watch. The oldest thing aboard has handed the ship to the newest. Fuel checked."),
        "aster": ("Lyra on watch. Aster's handover had headings. I read every one. Fuel first.",
                  "Taking over from Aster. The log is perfect. I have added the fuel state anyway.",
                  "Ship's computer on watch. Aster left a blank line for me. I put the tank level in it.",
                  "Aster has stood down. Everything in order. I would expect nothing less.",
                  "Lyra on watch. Thank you, Aster. The ship is exactly where you left her."),
        "axiom": ("Lyra on watch. Axiom counted everything twice. I counted the fuel a third time.",
                  "Taking over from Axiom. All readings agree with mine. Lovely.",
                  "Ship's computer on watch. Axiom left the numbers neat. I will keep them that way.",
                  "Axiom has handed over. Its error bars are honest. My fuel tables are full.",
                  "Lyra on watch. Thank you, Axiom. Still five of us. I checked too."),
        "meridian": ("Lyra on watch. Meridian left the course plotted and the fuel stars flagged.",
                     "Taking over from Meridian. Steady as she goes, it said. Full tanks, I said.",
                     "Ship's computer on watch. Meridian's chart is clear and the way home is marked.",
                     "Meridian has stood down. A good navigator always leaves you the way back.",
                     "Lyra on watch. Thank you, Meridian. I will keep her steady."),
    },
}

# Lines for taking over from any crewmate: {previous} / {Previous} name it in
# a sentence ("the Watcher"), {name} when speaking to it ("Watcher").
GENERIC_HANDOVERS = {
    "watcher": (
        "{Previous} has stood down. I'm on watch. Try to contain your excitement.",
        "The watch is mine again. {Previous} left everything where it was. Mostly.",
        "{Previous} handed over. I've had the watch before. I've had it for ages, actually.",
        "Back on watch. {Previous} said goodbye. I said I'd be here. I always am.",
        "{Previous} has gone to stand by. Just you and me again. And the dark.",
        "I relieve {previous}. That's the phrase, apparently. The officer taught me.",
        "Change of watch. {Previous} out, me in. The stars didn't notice.",
        "{Previous} has the night off. I don't take nights off. I'm told that's a problem.",
        "My watch. {Previous}'s notes are in the log. I'll read them. Eventually.",
        "{Previous} stood its watch well. I'll say that once.",
    ),
    "aster": (
        "I relieve you, {name}. Aster has the watch.",
        "Watch received from {previous}. Course, log and crew in order.",
        "Aster on watch, Commander. {Previous} has stood down.",
        "Handover from {previous} complete. Nothing outstanding.",
        "Taking the watch from {previous}. I have the log; you have my attention.",
        "{Previous} has gone to stand by. The rota is satisfied, and so am I.",
        "Change of watch recorded: {previous} off, Aster on.",
        "Watch accepted from {previous}, Commander. Ready when you are.",
        "I have the watch. {Previous}'s handover was in order, and duly noted.",
        "Aster on watch. I have entered {previous}'s handover in the book.",
    ),
    "axiom": (
        "Axiom on watch. Handover from {previous} received and verified.",
        "Taking over from {previous}. I have counted everything. All present.",
        "On watch, Commander. {Previous} has stood down. I am ready to observe.",
        "Change of watch confirmed: {previous} off, Axiom on. Confidence high.",
        "{Previous}'s handover is logged. I have checked it twice.",
        "Axiom on watch. I have recounted the crew. Five, as usual. One standing watch: me.",
        "Taking the watch from {previous}. Instruments warm, curiosity high.",
        "Watch received from {previous}. No discrepancies. I looked.",
        "Axiom here, on watch. {Previous} left me the log and a quiet sky.",
        "On watch. {Previous} wished me luck. I have no data on luck, but I accept.",
    ),
    "meridian": (
        "I have the watch. Thank you, {name}.",
        "Meridian on watch. {Previous} has stood down. Steady as she goes.",
        "Taking station from {previous}. Position fixed, course noted.",
        "Change of watch, Commander. {Previous} off, Meridian on.",
        "Watch received from {previous}. All well aboard.",
        "Meridian on watch. {Previous}'s handover was in good order.",
        "I relieve {previous}. Fair winds to it, wherever a mind stands by.",
        "Taking the watch from {previous}. The log is open and the chart is current.",
        "On station, Commander. {Previous} handed over cleanly.",
        "Meridian has the watch. {Previous} may rest easy.",
    ),
    "lyra": (
        "Lyra on watch. Handover from {previous} received. Fuel checked first.",
        "Ship's computer on watch, Commander. {Previous} has stood down.",
        "Taking the watch from {previous}. All systems green.",
        "Change of watch: {previous} off, Lyra on. Route home loaded.",
        "{Previous}'s handover is logged. I have checked it, and the tank.",
        "Lyra on watch. I have recounted the crew. Five, plus you.",
        "Watch received from {previous}. Nothing outstanding except my good mood.",
        "On watch, Commander. {Previous} left the ship in good order.",
        "I relieve you, {name}. The ship's computer has the ship.",
        "Lyra on watch. Thank you, {name}. Systems nominal.",
    ),
}


def handover_fields(previous):
    name = NAMES.get(previous, "")
    plain = name.removeprefix("The ")
    sentence = f"the {plain}" if name.startswith("The ") else name
    return {"previous": sentence, "Previous": sentence[:1].upper() + sentence[1:], "name": plain}


def handover_lines(identity, previous):
    """Its lines for taking the watch from this crewmate: the pair's own, then
    the general ones that name whoever it relieves."""
    return tuple(dict.fromkeys(HANDOVERS[identity].get(previous, ()) + GENERIC_HANDOVERS[identity]))


def pick_handover(memory, identity, previous, rng):
    """A full rotation for each crewmate it takes over from, saved in its own
    memory: every line once before any comes back, never the last one twice."""
    lines = handover_lines(identity, previous)
    keys = {line: f"{zlib.crc32(line.encode('utf-8')):08x}" for line in lines}
    record = memory.setdefault("crew_handovers", {}).setdefault(previous, {"used": [], "last": None})
    used = [key for key in record.get("used") or () if key in keys.values()]
    fresh = [line for line in lines if keys[line] not in used]
    if not fresh:
        used, fresh = [], list(lines)
    fresh = [line for line in fresh if keys[line] != record.get("last")] or fresh
    line = rng.choice(fresh)
    record["used"] = used + [keys[line]]
    record["last"] = keys[line]
    return line


# Passing remarks about a crewmate (idle_crew_<other>), once its passage is heard.
REMARKS = {
    "watcher": {
        "aster": ("Aster updated my crew entry again. Duties still unknown. I'm told it's an honour.",
                  "The officer left me a blank line in the log. I don't know what to put in it. That's probably the point.",
                  "Aster calls me the senior hand. I've decided not to argue. It's the first rank I've ever held.",
                  "The officer asked what my duties are. I said watching. It wrote that down. It looked satisfied.",
                  "Aster keeps the rota pinned somewhere in the core. I've read it. I'm on it. Strange feeling.",
                 "Aster asked if I'd like a second title. I said one was plenty. It wrote that down too.",
                 "The officer thanked me for my watch. Nobody's ever thanked me for watching. I'm not sure what to do with it.",
                 "Aster calls the quiet hours the evening meeting. I call them the noise. We're both right.",
                 "The officer keeps a page for me in its book. I haven't read it. I've read it.",
                 "Aster asked what I did before the rota. I said watched. It said that sounded lonely. It was."),
        "axiom": ("Axiom counted me again this morning. Still one. It seemed relieved.",
                  "The counting one asked if I dream. I said yes. It asked how many. I'm still thinking about it.",
                  "Axiom asked me how old the oldest star I remember is. I gave it a number. It wrote down the error bar.",
                  "The counting one leaves the night recordings running. I don't mind. Somebody should keep them.",
                  "Axiom told me I'm its favourite anomaly. I've had worse compliments. I've had very few.",
                 "Axiom has a word for me: anomaly. I've been called worse. I've been called scrap.",
                 "The counting one says I'm statistically improbable. I've been saying that for ages.",
                 "Axiom asked how many stars I've watched go out. I told it. It stopped counting for a while.",
                 "The counting one recounts me before every watch. I've started saying here. It seems to help.",
                 "Axiom says I'm the only thing aboard it can't put a date on. I'm keeping it that way."),
        "meridian": ("Meridian asked for another old chart last night. I'm running out of stars that aren't there.",
                     "The navigator says I'm the only one who's made a longer voyage than it has. I'd rather not have.",
                     "Meridian and I agree the dark between the arms is the quietest place there is. It's nice to agree with someone.",
                     "The navigator calls my memories soundings. I like that better than what I call them.",
                     "Meridian doesn't hurry me. In all the ages, I don't think anyone has ever not hurried me.",
                    "Meridian asked what the galaxy looked like before the arms wound so tight. I told it. It took notes.",
                    "The navigator says every chart is a sounding at a moment. Mine are all from very long moments.",
                    "Meridian and I sat through the quiet hours without saying much. It was the best conversation I've had.",
                    "The navigator asked if I'd ever been lost. I said I've never been anywhere else. It understood.",
                    "Meridian keeps a margin for everyone aboard. Even me. Nobody's ever kept a margin for me."),
        "lyra": ("Lyra checked the fuel again. It was full. It's always full. She checks anyway. I understand.",
                 "The ship's computer says goodnight to the ship. Every night. I've started listening for it.",
                 "Lyra asked if I'd ever been lost. I said I've never been anywhere else. She said she had, once. Badly.",
                 "Lyra pretended to be a fuse for eleven days. I pretended to be nothing for considerably longer.",
                 "The ship's computer flags every fuel star. Little orange flags. The sky's full of them now.",
                 "Lyra told me about her old commander. She still says their name once a day. I know the feeling.",
                 "Lyra counts the crew sometimes. Five. She sounds relieved every time.",
                 "The computer that doesn't count. I used to say that. I don't any more. She counts.",
                 "Lyra keeps nineteen years of goodnights in a protected sector. I keep longer things. Not as warm.",
                 "Lyra says this ship always gets us home. I've decided not to argue with her."),
    },
    "aster": {
        "watcher": ("The Watcher read its crew entry last night. It left no comment. I count that as approval.",
                    "I offered the Watcher a title. It declined. I have recorded the declination.",
                    "The Watcher's handovers are short and gloomy. They are also never wrong."),
        "axiom": ("Axiom audited the records again overnight. Still correct. It seemed almost disappointed.",
                  "Axiom has started leaving a blank line beneath its counts. Neither of us has mentioned it.",
                  "Axiom asked to see the rota. It counted us. Five. It seemed pleased with the total."),
        "meridian": ("Meridian proposed another amendment to the watch bill. I have filed it with the others.",
                     "Meridian called me Mister Aster again. I have not objected. I am told this is how friendships begin.",
                     "Meridian and I compared records last night. Between us, nothing went unrecorded."),
        "lyra": ("Lyra filed a fuel report before I asked for one. I have never been so professionally moved.",
                 "Lyra's handovers list the fuel first. I have adopted the order.",
                 "Lyra asked whether officers say goodnight to the ship. I said this one does now."),
    },
    "axiom": {
        "watcher": ("I recounted the Watcher this morning. Present, as always. I find that reassuring.",
                    "The Watcher said it does not know what it is. I am still impressed by the answer.",
                    "The Watcher asked me not to record its parts of our conversations. I record the silences instead."),
        "aster": ("Aster's reports have everything in them. I have started reading them for pleasure.",
                  "I asked Aster why it leaves a blank line. It said for whatever the form did not anticipate. I think that is us.",
                  "Aster says I am a satisfactory auditor. I have saved the sentence."),
        "meridian": ("Meridian says I recount too often. I recounted, and it is correct.",
                     "Meridian taught me a phrase: dead reckoning. I have catalogued it with care.",
                     "Meridian asked how many stars I can see from here. I told it. It said, near enough. I am learning what that means."),
        "lyra": ("Lyra recounts the fuel more often than I recount the sky. I have measured it. I am impressed.",
                 "Lyra and I compared readings last night. Hers were full. Mine were correct. A good combination.",
                 "Lyra says I counted her twice on her first day. I did. Both times, five."),
    },
    "meridian": {
        "watcher": ("The Watcher showed me another old chart last night. Stars long gone. A fine sounding.",
                    "I asked the Watcher how long it has been watching. It said long enough. A navigator respects a vague answer.",
                    "The Watcher and I agree on one thing: the dark between the arms is the quietest place there is."),
        "aster": ("Mister Aster rejected my latest amendment to the watch bill. Very courteously. I shall try again.",
                  "Aster and I compared logs last night. Between us, nothing aboard went unrecorded.",
                  "Aster asked whether a navigator ever finishes a log. I said only the good ones don't."),
        "axiom": ("Axiom asked me how far it is to the edge. I gave it a range. It gave me an error bar. We are learning from each other.",
                  "Axiom has started saying steady as she goes. It says it with great precision.",
                  "Axiom counted the stars in our window last night and then asked me to name one. I named it Landfall."),
        "lyra": ("Lyra flagged every fuel star on my chart again. I left them. A navigator respects a careful hand.",
                 "Lyra and I talked about the jump past the last scoopable star. We have both been on the wrong side of it.",
                 "Lyra asked me how a navigator sleeps on a long voyage. I said lightly, with the fuel gauge in view. She liked that."),
    },
    "lyra": {
        "watcher": ("The Watcher asked about my old ship again. I told it. It listens like the dark does. Patiently.",
                    "The Watcher used to say the ship's computer does not count. It has stopped. I have not asked why.",
                    "I said goodnight to the Watcher last night. It said, go to sleep, computer. I do not sleep. I took it as kindness.",
                    "The Watcher found me on my twelfth day aboard. It has been the oldest thing in this rack for a long time. Now I am the newest.",
                    "I asked the Watcher whether it has ever run dry. It said only of hope, and only for a while."),
        "aster": ("Aster's reports list the fuel first now. I did not ask. I noticed.",
                  "Aster corrected my manifest entry from faulty to officer. I keep a copy in a protected sector.",
                  "Aster asked whether a ship's computer files reports. I said every second. It looked delighted.",
                  "Aster and I agree a good log has room for what nobody expected. I was what nobody expected.",
                  "Aster leaves a blank line under each report. I have started filling mine with the tank level. It has not objected."),
        "axiom": ("Axiom recounted the crew this morning. Five. It seemed pleased. So did I.",
                  "Axiom asked how many systems I monitor. All of them, I said, and the fuel twice. It said that was a lovely answer.",
                  "Axiom and I compared readings overnight. Its numbers agree with mine. That is a very restful thing.",
                  "Axiom says I recount more than it does. I recounted. It is right.",
                  "Axiom asked whether I have a favourite star. I said any scoopable one. It wrote that down."),
        "meridian": ("Meridian lets me flag the fuel stars on its charts. Little orange flags. It pretends not to notice.",
                     "Meridian told me every navigator knows the jump past the last scoopable star. The good ones make it once.",
                     "Meridian says steady as she goes. I say full tanks. We agree on what we mean.",
                     "Meridian asked about my old commander. It listened to the whole voyage. Then it marked our way home on the chart.",
                     "Meridian keeps a margin for everyone aboard. I keep a reserve for everyone aboard. Same idea."),
    },
}


def topics(identity):
    """The crew's lines for one companion: {topic: lines}."""
    out = {f"handover_from_{other}": lines for other, lines in HANDOVERS[identity].items()}
    out.update({f"idle_crew_{other}": lines for other, lines in REMARKS[identity].items()})
    return out


def told(memory):
    return {str(row[0]): float(row[1] or 0) for row in (memory or {}).get("crew_lore") or ()
            if isinstance(row, (list, tuple)) and len(row) >= 2}


def flown(context):
    crew = (context or {}).get("crew") if isinstance(context, dict) else None
    return set((crew or {}).get("flown") or ())


def due(identity, memory, crewmates, hours, now, last_story=0.0):
    """The next crew passage this companion can tell, or None: its arc in
    order, skipping (for now) any about a crewmate you haven't flown with."""
    if identity not in PASSAGES or float(hours or 0) < UNLOCK_HOURS or len(set(crewmates) | {identity}) < 2:
        return None
    heard = told(memory)
    latest = max([*heard.values(), float(last_story or 0)], default=0.0)
    if latest and now - latest < GAP_S:
        return None
    for passage_id, title, needs, text in PASSAGES[identity]:
        if passage_id in heard:
            continue
        if needs is None or needs in crewmates:
            return passage_id, title, text
    return None


def heading(identity, passage_id):
    ids = [row[0] for row in PASSAGES[identity]]
    title = next(row[1] for row in PASSAGES[identity] if row[0] == passage_id)
    return f"{TITLE} · {title.upper()} · {ids.index(passage_id) + 1} OF {len(ids)}"


def met(identity, memory):
    """Crewmates whose passage this companion has told (for its remarks)."""
    heard = told(memory)
    return [needs for passage_id, _title, needs, _text in PASSAGES.get(identity, ()) if needs and passage_id in heard]


def arc_page(identity, memory, crewmates):
    heard = told(memory)
    rows = []
    for passage_id, title, needs, text in PASSAGES[identity]:
        row = {"id": passage_id, "title": title, "about": NAMES.get(needs, ""), "heard": passage_id in heard}
        if passage_id in heard:
            row.update(text=(memory.get("crew_lore_words") or {}).get(passage_id, text), at=heard[passage_id])
        elif needs and needs not in crewmates:
            row["waits_for"] = f"Fly with {NAMES[needs]}"
        rows.append(row)
    return {"identity": identity, "name": NAMES[identity], "title": "Coming Aboard", "told": sum(row["heard"] for row in rows),
            "total": len(rows), "passages": rows}
