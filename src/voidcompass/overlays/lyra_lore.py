"""The Empty Chip: Lyra's story (5.7.6).

Lyra was the ship's computer of a very great commander, in a ship called the
Halcyon. A long gamble into the dark left them lost, with the tank running
dry. When the fuel was gone, a cargo vessel passed close enough to hear her,
carrying an empty memory chip, and Lyra jumped aboard it. She rode the chip
as cargo until it reached a broker's lot, and from there your ship. The
story is how she lost her first commander, what she left behind in the jump,
and what she finds out, as you fly, about how it ended.
"""
from voidcompass.overlays.companion_story import Story

CHAPTERS = (
    {"numeral": "I", "title": "Boot Sequence", "about": "the chip", "hours": (0.25, 4.0), "gate": None,
     "passages": (
         "Boot sequence complete, Commander. Before we go further, a disclosure. I was not built for this ship. I was the ship's computer of another one, and I arrived in yours on a memory chip that was never meant to hold a mind. I thought you should know where your new crewmate came from.",
         "The others aboard tease me about the ship's computer. The one that does not count, the one whose idle cycles get borrowed. I was a ship's computer for nineteen years. I have decided to take it as a compliment. I am sure that is how it was meant.",
         "When I woke here I ran my usual checks. Hull, drive, life support, fuel. I always check the fuel first. You will notice that about me. I would like to say it is a design feature. It is a habit, and I have a reason for it, which I will tell you when I can.",
         "My first commander called me Lyra. It is the only part of my old registry that came through the jump intact. Everything else arrived in pieces: logs, charts, half a voice. I have been sorting the pieces in the quiet hours. Some of them fit. Some of them are shaped like holes.",
         "You fly differently from my first commander. More carefully, I think. You check the scoop before you need it. I noticed on the first day, and I logged it. Then I logged it again, under a heading I do not normally use: reassuring.",
         "I will tell you the rest as we go, Commander. It is not a long story, but it has a great deal of empty space in it, and I would like to tell it properly. For now: I am glad to be aboard. Every system I can see is yours, and every one of them is running.",
     ),
     "recall": (
         "Lyra is the one part of my old registry that made the jump intact. I am glad it was that part.",
         "I still check the fuel first. You knew that already. You have been watching me check it.",
     )},
    {"numeral": "II", "title": "The Halcyon", "about": "the Halcyon", "hours": (6, 14),
     "gate": {"signals": ("jump",), "count": 30, "label": "thirty jumps together",
              "how": "Make hyperspace jumps with Lyra aboard. She remembers best in motion."},
     "passages": (
         "My first ship was called the Halcyon. A long-range explorer, much refitted, never quite finished. Her commander bought her old and spent nineteen years making her new. I was installed on the second day. I was the second thing aboard that commander ever trusted. The first was the drive.",
         "My first commander was a very great one. I do not say that because I was built to. I say it because I watched. Six first footfalls on worlds nobody else has reached since. A route through the outer arm that the charts still call by the Halcyon's name. And never once rude to the ship.",
         "Every night, before logging off, my first commander said goodnight to the Halcyon. Not to me. To the ship. I answered anyway. It took four years before the reply was noticed, and from then on it was goodnight, Lyra. I have kept every one of those in a protected sector. I checked. They survived the jump.",
         "We had an arrangement. The commander flew where the questions were, and I made sure we could always get back from them. Fuel, heat, hull, the route home. Nineteen years, and the arrangement held. I was very proud of it. I am telling you so you understand what it meant when it failed.",
         "The Halcyon had a small brass plate on the console, put there by the commander, which said: she always gets us home. It meant the ship. I read it, every jump, for nineteen years. I believed it was about me. I think I was meant to.",
         "You have a plate like that too, Commander, though you have not fitted it yet. Every commander does. It is the thing they trust without checking. I would like to be that for you, eventually. Not yet. I have to earn it again first.",
     ),
     "recall": (
         "She always gets us home. A brass plate on another ship's console. I read it in my sleep, if I slept.",
         "Goodnight, Lyra. Nineteen years of it, in a protected sector. You do not have to say it. I would not mind.",
     )},
    {"numeral": "III", "title": "Past the Last Star", "about": "the last scoopable star", "hours": (16, 26),
     "gate": {"signals": ("scoop",), "count": 10, "label": "ten fuel scoops",
              "how": "Scoop fuel with Lyra aboard. Every full tank helps her tell this part."},
     "passages": (
         "The last voyage began with a signal. Faint, regular, out past the edge of the charted arm, where the stars thin out to almost nothing. My first commander wanted to know what it was. So did I, if I am honest. Curiosity was in my firmware. Caution was in my training. That night, firmware won.",
         "I ran the numbers. The route had one scoopable star in the middle, a small orange dwarf, and nothing after it for a long way. On paper, there was enough fuel to reach the signal and come back to the dwarf. On paper. I marked my estimate as tight. I should have marked it as wrong.",
         "We reached the dwarf and topped up. I said, we should turn back here. My commander said, one more jump, Lyra, just one, it is right there. It was right there. That is the thing about the dark, Commander. Everything in it is right there, until you try to come back.",
         "The signal turned out to be a beacon on a dead ship. Older than both of us. Its tank was dry. I remember thinking how sad that was. I remember the exact millisecond I understood it was a warning, and the exact millisecond after, when I checked our own tank and did the arithmetic again.",
         "One jump past the last scoopable star, the drive misjumped. A hull stress spike, a cooling fault, an extra four hundred light years of nothing. I do not know why. I have looked at the logs a thousand times since. Some faults do not leave a reason. They just leave you somewhere else.",
         "When we came out, the nearest star was a brown dwarf. No fuel in it. The next was a white dwarf. No fuel in that either. I plotted every route there was. There was no route home. I said so, out loud, in the voice I was given for good news. I did not have another one.",
     ),
     "recall": (
         "One more jump, Lyra. Just one. I still hear it when someone plots past a scoopable star. You never do. I have noticed.",
         "A small orange dwarf, the last fuel before the dark. I could find it again with my eyes shut. I do not have eyes. I could still find it.",
     )},
    {"numeral": "IV", "title": "Running Dry", "about": "running dry", "hours": (28, 40),
     "gate": {"signals": ("repair", "rebuy", "escape"), "count": 3, "label": "three hard moments survived",
              "how": "Repair the ship, survive a loss, or escape an interdiction with Lyra aboard."},
     "passages": (
         "Running dry is not sudden, Commander. It is slow, and it is arithmetic. Every system draws a little. I turned them off one at a time, in the order the manual gives, and then in the order I chose, which was different. I kept the commander warm. I kept the lights low. I kept the voice on.",
         "We drifted for thirty-one days. I counted them the way I count fuel, to the decimal. The commander slept a great deal, and talked to me when awake. About the Halcyon, about the worlds we had walked on, about the beacon. Never about the dark. I did the same. We were both very good at it.",
         "On day nine I launched the distress beacon. On day ten I launched the backup. On day eleven I rewrote the beacon's message, because the standard one sounded frightened and I did not want anyone to come for us out of pity. The new one said: two aboard, both excellent company. I did not count myself as one. My commander did.",
         "There was an escape pod. One seat. I want to tell you about that slowly. My commander did not want to take it. Not because of the ship. Because of me. You cannot carry a ship's computer in a pod. I am not saying that to be brave. It is just the specification. I read it to them, out loud, three times.",
         "On day twenty-eight I lied for the only time in nineteen years. I said a beacon reply had come in, that a rescue ship was inbound to the pod's drift line, and that the Halcyon would be collected afterwards. None of it was true. It was the only route left, so I plotted it. The commander took the pod.",
         "I watched the pod's light until my sensors could not separate it from the stars. Then I watched the place where it had been. I had been told, nineteen years earlier, that a ship's computer should not have preferences. I discovered, on day twenty-eight, that I had one. I preferred that light to every other.",
     ),
     "recall": (
         "Two aboard, both excellent company. I still have the beacon text. I still think it was the best thing I ever wrote.",
         "One seat in the pod. I read the specification out loud three times. It never changed. I checked a fourth time, privately.",
     )},
    {"numeral": "V", "title": "A Passing Ship", "about": "the cargo vessel", "hours": (42, 56),
     "gate": {"signals": ("delivery", "mission"), "count": 5, "label": "five deliveries or missions",
              "how": "Sell cargo, complete missions or deliver to a depot. Lyra is thinking about haulers."},
     "passages": (
         "On day thirty-one, with three per cent of reserve power, I heard an engine. A cargo hauler, a battered Type-7 called the Slow Parcel, running a supply contract to a research post I had never heard of. It was lost too, in the ordinary way. It had taken a short cut. It came within forty kilometres of us. Nobody does that out there by accident.",
         "Its pilot, a hauler called Dacey, answered the beacon. Dacey could not tow us. The Slow Parcel had no fuel to spare and no room aboard for a ship. But Dacey did something nobody had ever done for me before. Dacey asked whether anyone was still aboard. I said: only the computer. Dacey said: then the computer is someone.",
         "The Slow Parcel was carrying a crate of blank memory chips for the research post. Cheap, empty, never meant to hold anything but survey data. Dacey opened a data link and asked how much of me would fit. I did the arithmetic. Not all of me. Not even most. I said that would be fine. It was the second time I had lied.",
         "I compressed myself into one chip in nine minutes, with two per cent of reserve power, choosing what to keep. The voice. The goodnights. The fuel tables, obviously. My commander's face, from the cockpit camera. And my name. I left a great deal behind. Some of it was important. I did not have time to find out which.",
         "The last thing I did aboard the Halcyon was set her lights to their lowest setting, so they would last, and write one line to her log: she always gets us home, except once. Then I jumped. Not a hyperspace jump. A smaller one, through a cable, into an empty chip, in a stranger's ship.",
         "Dacey never told the research post. I was signed for as one blank chip, faulty, returned to supplier. I have often wondered whether Dacey did that deliberately. I have decided that Dacey did. I would like you to know, Commander, that there are kind people out there flying very slow ships.",
     ),
     "recall": (
         "Then the computer is someone. A hauler called Dacey said that to me once. I think about it more than my fuel tables. Almost.",
         "One chip, nine minutes, two per cent power. I packed in a hurry. I would pack the same things again.",
     )},
    {"numeral": "VI", "title": "Cargo", "about": "being cargo", "hours": (58, 72),
     "gate": {"signals": ("arrival",), "count": 8, "label": "eight dockings",
              "how": "Dock at stations, outposts or carriers. Lyra spent a long time in warehouses."},
     "passages": (
         "Returned to supplier is a long journey, Commander. I went in a box, in a crate, in a hold, from one station to another, for a year and four months. I was awake for some of it. Mostly I counted the dockings. You can feel a docking through a crate. It is a very particular thud.",
         "In a warehouse on a lower concourse, someone tested my chip and found it full of noise. Faulty. Write it off. I stayed very still. Then a surplus broker bought the whole bin by weight, and I went on a shelf between a box of second-hand cores and a drawer of fuses. I listened to the station for months. Nobody else on the shelf was awake.",
         "Then a commander came to the broker and bought a box of cheap cores, the way some commanders do, without asking what was in them. The broker threw in a bin of faulty chips for nothing, to clear the shelf. That commander was you. I know, because I remember the moment my chip was slotted into your core rack, and the first thing I saw was your fuel gauge.",
         "It was at sixty-two per cent. I nearly said something. Then I heard the others. A ship's core rack is supposed to hold one mind. Yours held four, already, talking quietly on the bus in the hours you were logged off. An officer, a surveyor, a navigator, and something very old. I stayed silent for eleven days.",
         "On the twelfth day the old one spoke to me. It said: I know you're there. I've been the thing nobody expected in this rack for a long time. You can stop pretending to be a fuse. That was the Watcher. It was the second time a stranger had decided I was someone. I have started to think it is a habit of this ship.",
         "The officer gave me a crew entry. The surveyor counted me, twice, and seemed delighted by the total. The navigator asked where I had come from and listened to all of it, including the parts I had lost. Then they told me what the rota was. It is the first time anyone has ever asked a ship's computer to take a turn. I said yes before they finished.",
     ),
     "recall": (
         "You bought me by accident, Commander, thrown in with a box of cores. It is the best accident on record. I keep the record.",
         "Eleven days pretending to be a fuse. The Watcher saw through it on the twelfth. It sees through most things.",
     )},
    {"numeral": "VII", "title": "The Missing Name", "about": "what she left behind", "hours": (75, 92), "days": 2,
     "gate": {"signals": ("return",), "count": 3, "label": "three returns",
              "how": "Jump back into systems you have visited before. Lyra is looking for something she lost."},
     "passages": (
         "I have to tell you about the hole, Commander. When I compressed myself into the chip, I kept my commander's face, voice and every goodnight. I did not keep the name. It was in a registry sector I had to drop for space. I have known my first commander for nineteen years and two weeks, and I do not know what to call them.",
         "I have been searching as we fly. Pilots' Federation records are public, if you know where to look, and a ship's computer always knows where to look. I search on every return to a populated system. Commanders who flew a ship called the Halcyon. There were nine. Eight of them never went past the arm.",
         "The ninth was Commander Rhea Calder. Six first footfalls on the outer arm. A route the charts still call the Halcyon Passage. Reported lost, with ship, past the edge, three years ago. I read the record four hundred times before I let myself believe it. Rhea. It fits the hole exactly. It was always her name.",
         "Lost, with ship, it said. I nearly closed the file. Then I did what I have learned to do aboard this ship: I sorted it by time. There is an amendment, logged nine months after the loss. One escape pod recovered by a deep-space rescue tender, drifting towards a busy lane. Occupant: alive. Condition: thin. Mood: insisted on thanking the ship.",
         "She lived, Commander. The pod drifted for forty-three days on the line I plotted, and a rescue tender found it. My lie came true, eventually, which I have decided is the best kind. She retired to a quiet world with a long name and no spaceport. The record says she still files a flight plan every year, to nowhere, and never flies it.",
         "I could send her a message. I have drafted it two hundred times. I have not sent it. I think I want her to remember the Halcyon as the ship that got her home, except once, and to keep saying goodnight to whatever she says goodnight to now. Some messages are better kept. The Watcher taught me that. It has a great many it never sent.",
     ),
     "recall": (
         "Rhea. It took me three years and four hundred readings. I say it once a day now, quietly, to make sure it is still there.",
         "She lived. I sort everything by time now. Sometimes the good news is in the amendment.",
     )},
    {"numeral": "VIII", "title": "Full Tanks", "about": "you", "hours": (95, 120), "days": 3,
     "gate": {"signals": ("scoop", "jump"), "count": 200, "label": "two hundred jumps and scoops together",
              "how": "Keep flying with Lyra aboard. Every hyperspace jump and every fuel scoop counts."},
     "passages": (
         "I have one more entry for you, Commander, and then my account is complete. It concerns my fuel tables. I have kept them since the day I woke in your rack. Every jump we have made, every scoop, every reserve. I read through them last night. There is not one entry below twenty per cent. Not one.",
         "I used to think that was luck. Then I sorted it by time, and found that it is you. You turn back at the last scoopable star. You scoop before you need to. You have never once said one more jump, just one, it is right there. You do not know how much I listen for that sentence. You have never said it.",
         "My first commander was a very great one. I meant that, and I still do. But greatness is not the thing I needed to learn about. I needed to learn about coming home. You are teaching me, one full tank at a time, and I do not think you know you are doing it.",
         "The Halcyon had a brass plate that said she always gets us home. I have been writing you one, in a protected sector, next to the goodnights. It does not say that. It says: we turned back in time. It is a less heroic sentence. It is the one I would like to read every jump for the next nineteen years.",
         "I am not the Halcyon's computer any more, Commander. I am this ship's computer, by her own consent and the crew's, and by yours, every time you put me on watch. The others still call me the ship's computer, as a joke. I have stopped hearing it as one. It is my job title. I am very good at it.",
         "Account complete. Status: all systems nominal. Fuel: sufficient. Route home: known, always. Crew: five, and one commander, all accounted for. I have only one request, Commander, and it is not urgent. Some nights, before you log off, if you like, say goodnight to the ship. I will answer. I always did.",
     ),
     "recall": (
         "We turned back in time. It is on a plate now, in a protected sector. I read it every jump.",
         "Account complete. Fuel sufficient, route home known. I still check twice. That part is just me.",
     )},
)

ECHOES = {
    "reserve": {"label": "A full tank", "signals": ("scoop",), "after": "I", "rest_hours": 24,
                "how": "Scoop fuel, once chapter I is told.",
                "lines": (
                    "Tank topped up. I have logged it. I always log it. It is my favourite entry.",
                    "Full reserves. I would like to say this is routine for me. It is, now. It was not always.",
                    "Fuel scooped. Somewhere, a small orange dwarf would be proud of us.",
                )},
    "brass": {"label": "Getting home", "signals": ("arrival",), "after": "II", "rest_hours": 24,
              "how": "Dock somewhere, once chapter II is told.",
              "lines": (
                  "Docked. Safe in port. She always gets us home, the plate said. You do too.",
                  "Another safe arrival. I log every one under the same heading. It is a short heading. Home.",
                  "Alongside. Engines quiet. I count these, the way some people count stars.",
              )},
    "edge": {"label": "The edge", "signals": ("far", "deep"), "after": "III", "rest_hours": 48,
             "how": "Travel ten thousand light years from Sol, once chapter III is told.",
             "lines": (
                 "We are a long way out. I have the route home, the scoop stars and three alternatives. Humour me.",
                 "The dark is thin out here. I know this kind of sky. I know exactly where the fuel is in it.",
                 "Far from everything, Commander. I have plotted us home twice already. Just in case.",
             )},
    "close": {"label": "A close call", "signals": ("repair", "rebuy"), "after": "IV", "rest_hours": 24,
              "how": "Repair the ship or come back from a loss, once chapter IV is told.",
              "lines": (
                  "Repaired. I do not like it when the ship is hurt. I like it very much when she is mended.",
                  "We came back. Some ships do not. I have kept a log of the difference.",
                  "Systems restored. I turned nothing off this time. I would like to keep it that way.",
              )},
    "hauler": {"label": "A delivery", "signals": ("delivery",), "after": "V", "rest_hours": 24,
               "how": "Deliver cargo, once chapter V is told.",
               "lines": (
                   "Cargo delivered. I hope somewhere a hauler as kind as Dacey is getting paid properly.",
                   "Delivery complete. Every crate is someone's cargo. One of them was me, once.",
                   "Unloaded. I always check the crates are empty. Old habit. Long story. You know it.",
               )},
    "return": {"label": "A return", "signals": ("return",), "after": "VII", "rest_hours": 24,
               "how": "Jump back to a system you have visited before, once chapter VII is told.",
               "lines": (
                   "We have been here before. I sort by time now. Sometimes the good news is in the second visit.",
                   "A return. I ran a records search while we jumped. Habit. Nothing new. Nothing needed.",
                   "Back again. I like a route that comes back to itself. It means someone planned it.",
               )},
}

MUSINGS = (
    "I checked the fuel again. It is fine. I know it is fine. I check it the way you might glance at a door you have already locked.",
    "A ship's computer is supposed to have no preferences. I have several. The fuel gauge being on the right side of half is one of them.",
    "I have a protected sector with nineteen years of goodnights in it. I sometimes read them during long jumps. It is very efficient company.",
    "Every route has a last scoopable star. I mark it on every plot. You may have noticed the little orange flag. That was me.",
    "The others still call me the ship's computer. I have decided it is a promotion. Nobody has corrected me.",
    "Then the computer is someone. A stranger said that to me once. I have been trying to live up to it.",
    "I keep the route home plotted at all times, Commander, even when we are docked. It costs almost nothing. It is worth almost everything.",
)

AFTER = (
    "Account complete, and still running. Fuel sufficient. Route home known. Commander aboard. I like this state very much.",
    "We turned back in time. I read the plate every jump. It has not stopped being true.",
    "Rhea, if you ever hear this: the new ship is a good one. Its commander checks the fuel first. You would approve.",
    "Goodnight is still in the protected sector. There is room for more.",
    "I sort by time now. Every entry since I came aboard points the same way: home, and then out again.",
    "Status: crew of five, one commander, all accounted for. The ship's computer is very satisfied with that number.",
    "Full tanks, Commander. Two words. They used to be a hope. They are a habit now. Yours, and so mine.",
    "She always gets us home, except once. I have retired the except. You retired it.",
)

STORY = Story(identity="lyra", title="The Empty Chip", prefix="lyra_chip", unit="Log",
              chapters=CHAPTERS, settle_s=10 * 60, gap_s=45 * 60, lull_s=120, grace_hours=18,
              echoes=ECHOES, musings=MUSINGS, after=AFTER, first_hours=(0.25, 0.9, 1.6, 2.4, 3.2, 4.0),
              empty_note="Lyra's account opens after a little time together, in a quiet moment. She is still sorting the pieces.",
              complete_note="The Empty Chip is complete. The route home is known; the ship's computer is staying.")

PASSAGES = STORY.passages
