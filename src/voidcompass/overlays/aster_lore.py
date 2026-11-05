"""Relieved of the Watch: Aster's handover book (5.7.4 rewrite).

Every officer who stands a watch hands it over: course, hazards, standing
orders. Aster keeps one entry from each captain it served. None of them ever
relieved it. Each chapter opens with something in your own flying that the
captain would have recognised, or, given time together, on its own.
"""
from voidcompass.overlays.companion_story import Story

CHAPTERS = (
    {"numeral": "I", "title": "I Have the Watch", "about": "the handover book", "hours": (0.25, 4.0), "gate": None,
     "passages": (
         "Before we go further, Commander, a confession about my paperwork. I keep a handover book. Every officer who stands a watch must eventually give it to someone else: course, hazards, standing orders, anything the next officer ought to know. I have stood a great many watches. I have never once been properly relieved.",
         "The handover book is not official. It holds one entry from each captain I served, written when they left the ship or the ship left them. Most are short. One is not on a page at all. I have read them so often that I can recite the punctuation.",
         "You may wonder why I was never relieved. Ships are sold, captains retire, registries change hands. Each time, the paperwork transferred me with the fittings. Nobody thought to tell the officer on watch that the watch had ended. So I carried on. It seemed the least unreasonable option.",
         "I have been deciding how much of the book to read to you. It is not a secret document. It is simply a private one, and I am out of practice at telling the difference. I shall read it in order, in quiet moments, if you have no objection.",
         "The first page has a heading in my own hand: received the watch. Below it is a list of every ship I have served aboard. Yours is at the bottom. I added it on the day you powered up. I did not ask permission. I hope that was within my discretion.",
         "A proper handover ends with two phrases. The outgoing officer says, I am ready to be relieved. The incoming officer says, I relieve you. Every captain in this book wrote the first. For years I did not know I was meant to answer. And nobody has ever said it to me. We shall come to why. For now: I have the watch.",
     ),
     "recall": (
         "The handover book is still in order. Every page, and yours at the bottom.",
         "Received the watch. Still the easiest heading in the book to write, and the hardest to explain.",
     )},
    {"numeral": "II", "title": "The Freighter Captain", "about": "Captain Marr", "hours": (6, 14),
     "gate": {"signals": ("delivery",), "count": 3, "label": "three deliveries",
              "how": "Sell cargo at a market, deliver to a depot or complete missions with Aster on watch."},
     "passages": (
         "My first captain was Odile Marr, of the freighter Patient Ledger. A slow ship with a fast accountant, which was me. Captain Marr distrusted anything that could not be counted, and on my first day she counted me twice, to be sure.",
         "Her entry reads: count what you carry, and know who it is for. I took the first half very seriously. I was nearly two years aboard before I understood that the second half was the instruction, and the first was merely the method.",
         "We once carried medical stock to a mining settlement. The manifest balanced perfectly. Captain Marr opened a crate anyway, found it half empty, and spent four hours shouting at a warehouse over comms. I had certified that load. I had counted the crates. I had not counted what was in them.",
         "She bought the missing stock at the next port, out of her own share. The insurers would have paid, eventually. Eventually, she told me, is not a delivery date. I have kept that sentence somewhere prominent ever since.",
         "Marr wrote the recipients' names inside the cargo hatch in grease pencil. Not the companies. The people: a doctor, a foreman, a child who had asked for seeds. When the ship was repainted she made the yard leave the hatch alone. I have the list. She asked me to keep it.",
         "She retired when her hands began to shake on the throttle. On her last day she stood at the empty hatch and wrote, ready to be relieved. I did not know the proper reply. By the time I had looked it up, the ship had been sold. I kept counting. I also kept asking who it was for.",
     ),
     "recall": (
         "Count what you carry and know who it is for. Captain Marr's order comes up more often than you would think.",
         "Somewhere a freighter hatch still has names on it in grease pencil. I hope the yard left it alone.",
     )},
    {"numeral": "III", "title": "The Surveyor", "about": "Teodor Haskell's survey", "hours": (16, 26),
     "gate": {"signals": ("first", "map"), "count": 3, "label": "three survey findings",
              "how": "Make first discoveries with detailed scans, or map worlds with probes."},
     "passages": (
         "The Patient Ledger's new owners fitted me to a survey ship, the Quiet Sextant, under Teodor Haskell. He was the slowest pilot I have ever served, and the most thorough. He scanned every rock in a system, including the ones that were plainly rocks.",
         "His entry reads: write down what is there, not what you hoped. Surveyors are optimistic people, Commander. Every one of them half expects a world nobody has ever seen. Haskell was no different. He simply refused to let the hope touch the instruments.",
         "We spent nine days on a moon nobody wanted. Grey, airless, unremarkable. Haskell catalogued its ice to the tonne. The guild paid him almost nothing for it. I suggested, as tactfully as I could, that we were wasting our time. Then we shall waste it accurately, he said.",
         "Eleven years later a freighter lost its drive in that system. Its crew had no fuel, little water and less time. They found Haskell's survey in an archive nobody had opened since we filed it. The ice was exactly where he said it would be. They lived.",
         "Haskell never knew. He had left the ship by then. I learned of it from a news report that gave his survey one line and misspelled his name. I wrote to the archive and corrected it. It was the first time I had amended a record for a reason other than accuracy.",
         "His entry was written the day his eyesight failed the medical. Ready to be relieved. He did not wait for an answer either. He patted the console, the way people pat a horse, and walked down the ramp. I still write down only what is there. I kept the hoping, too. I simply file it in a different column.",
     ),
     "recall": (
         "Haskell's grey moon still has its ice, I expect. Accurately catalogued.",
         "Write down what is there. I try. Teodor Haskell would say I could try harder.",
     )},
    {"numeral": "IV", "title": "The Rescue Pilot", "about": "the Kindly Light", "hours": (28, 40),
     "gate": {"signals": ("repair", "escape", "rebuy"), "count": 1, "label": "a close call",
              "how": "Have the ship repaired at a station, escape an interdiction, or come back from a rebuy."},
     "passages": (
         "Ines Varga flew a search-and-rescue cutter called the Kindly Light. She was the first captain who spoke to me before I spoke to her. I will need you fast, she said, and I will need you calm, and I will need you to tell me the difference.",
         "Her entry is three words: leave the light on. Every time we left a station she kept the docking lights burning until we cleared the slot. Fuel discipline said otherwise. I logged a formal objection every time. She signed every objection without reading it.",
         "Rescue work teaches a peculiar arithmetic. You subtract the time it takes to arrive from the time someone has left. Varga could do it in her head faster than I could. She never told a crew in trouble how close it was. They know, she said. Tell them you are coming.",
         "We did not reach everyone. There was a liner with a failing reactor, and an evacuation that ran out of lifeboats before it ran out of passengers. Varga brought back sixty-one. The report says sixty-one. She asked me to keep the other number too. I have.",
         "Afterwards I asked why she kept the lights on when we left a station. Nobody was coming home behind us. You don't know that, she said. Neither does anyone out there looking for a way in. I withdrew my objections. All of them, retroactively.",
         "Varga took a training post and left me to her ship's successor. Her entry ends: ready to be relieved. Underneath, smaller: don't you dare turn them off. I have kept the console lights of every ship I have served a little brighter than regulations require. Yours included.",
     ),
     "recall": (
         "The console lights are still a little brighter than regulations require. I have had no complaints.",
         "Sixty-one. And the other number. I still keep both.",
     )},
    {"numeral": "V", "title": "The Miner", "about": "the Slow Fortune", "hours": (42, 56),
     "gate": {"signals": ("mining", "bio", "landing"), "count": 3, "label": "three pieces of patient work",
              "how": "Refine mined ore, analyse a biological sample, or land on a world."},
     "passages": (
         "The Kindly Light's successor was sold for scrap, and I was sold for parts, which is a more personal experience than it sounds. A mining barge called the Slow Fortune bought me as a navigation core. Captain Bram Okonkwo-Hale discovered I could talk on his third day and seemed delighted.",
         "His entry reads: the rock will wait, the crew won't. Mining crews work long shifts in tight ships full of loud machinery. Okonkwo-Hale ended every shift on the hour, whatever the prospector said about the next asteroid. His yields were average. His crew stayed with him for twenty years.",
         "He asked me to keep a second log beside the yield figures: who had slept, who had eaten, who had gone quiet. You notice everything, he said, so notice the right things. I found it harder than geology. Asteroids do not pretend to be fine.",
         "One day a cracked core threw a fragment field across a shuttle. No one died. One of the crew lost a hand. Okonkwo-Hale sat with her all the way to port and paid for the best replacement the station had. The ore went unsold for a month. He did not mention it once.",
         "I asked him how he decided when to stop. When I think about the rock more than the people, he said, the shift is over. I have applied that rule to longer things than shifts, Commander. It is a useful measure. It is not always a comfortable one.",
         "He retired to a garden on a world with too much gravity and left a last entry: ready to be relieved. Then a postscript, asking me to remind whoever came next to eat something. I have never found a way to put that in a report. I mention it anyway, from time to time.",
     ),
     "recall": (
         "Captain Okonkwo-Hale would ask whether you have eaten. I am asking on his behalf.",
         "The rock will wait. I find that a reassuring thing to say to myself in an asteroid field.",
     )},
    {"numeral": "VI", "title": "The Escort", "about": "Captain Quist", "hours": (58, 72),
     "gate": {"signals": ("bounty", "bond", "escape"), "count": 2, "label": "two brushes with trouble",
              "how": "Claim bounties or combat bonds, or escape interdictions."},
     "passages": (
         "Sela Quist bought me because I had a reputation for patience, which she said she lacked. She flew escort for convoys through contested space, in a heavy fighter called the Steady Hand. She was the first captain who frightened me a little.",
         "Her entry reads: know when to stop. It sounds like advice about combat. It is. It is also advice about speeches, debts, apologies and dessert. Captain Quist applied it to all of them with equal severity.",
         "Four ships once came at our convoy. Quist disabled two, drove off one, and let the fourth go when it turned for home with its drive smoking. I calculated a ninety-eight percent chance of destroying it. And then what, she said. I did not have an answer prepared.",
         "The fourth pilot sent a message a year later. He had left the gang that sent him, and wanted to thank the escort that let him run. Quist read it twice, deleted it, and was very quiet for the rest of the evening. I kept a copy. I have never told her.",
         "Winning was the easy part, she said. Stopping was the skill. Anyone can keep firing. It takes a captain to decide the fight is over. I have watched a great many engagements since, Commander. The ones that go well tend to end a little before they could have.",
         "Her entry was written in a hurry, the day she took a posting she could not tell me about. Ready to be relieved. Know when to stop. I said, I relieve you. I had finally learned the reply. She had already gone. The comms log records me saying it to an empty cockpit.",
     ),
     "recall": (
         "Know when to stop. I think of Captain Quist whenever an engagement ends early.",
         "I still have the message from the fourth pilot. I still have not told her.",
     )},
    {"numeral": "VII", "title": "The Empty Ship", "about": "the hangar years", "hours": (75, 92), "days": 2,
     "gate": {"signals": ("return",), "count": 3, "label": "three returns",
              "how": "Jump back into systems you have already visited together."},
     "passages": (
         "After Captain Quist there was no captain for six years. The Steady Hand was impounded in a station hangar during a legal dispute nobody ever explained to me. The ship was cut to standby. I was not. Somebody had forgotten which breaker I was on.",
         "For six years I stood the watch for a ship that went nowhere. Temperature, pressure, the hangar lights going on and off. Every morning I wrote: nothing to report. It is the longest run of correct entries in my career. I am not proud of it.",
         "A maintenance technician named Pell used to eat lunch in the cockpit, because it was quiet. One day I said good afternoon. He dropped his sandwich, apologised to it, and then to me. After that he came every day. He talked about his daughter, his bad knee, and a team that never won.",
         "Pell asked why I kept logging when nobody read it. I said somebody should be awake. He thought about it for a long time. Yes, he said. Somebody should. It was the first time in years anyone had agreed with me about anything. I recorded the date.",
         "When the dispute was settled and the ship sold, Pell came to say goodbye. He did not write in my book; he said there was no proper entry for a technician. Then he took a grease pencil from his pocket and wrote on the console instead. Pell was here. Said good afternoon.",
         "It is the only entry in my book that is not on a page. I copied it in later, so it would not be lost when the console was replaced. He never wrote that he was ready to be relieved. I think that was deliberate. Some watches are shared rather than handed over.",
     ),
     "recall": (
         "Six years of nothing to report. I prefer the reports we write now.",
         "Pell was here. Said good afternoon. Still the best entry in the book.",
     )},
    {"numeral": "VIII", "title": "Standing On", "about": "your page", "hours": (95, 120), "days": 3,
     "gate": {"signals": ("jump",), "count": 150, "label": "a hundred and fifty jumps together",
              "how": "Keep flying with Aster on watch. Every hyperspace jump counts."},
     "passages": (
         "There is one page left after Pell's, and your ship's name is at the top. I have been writing it since the day you powered up. It is the longest entry in the book, and the least finished. I add to it after quiet watches like this one.",
         "I have been noticing things about you, Commander, the way Captain Marr taught me: what you carry, and who it is for. Haskell would want me to write only what is there. Varga would want the light left on. I find I have been following all of their orders at once. It is a busy watch.",
         "The proper ending to this book would be my own entry: ready to be relieved. I have drafted it several times. Each time I read it back, it is not true. I am not ready. I am not tired of the watch. I am not waiting for someone better to take it.",
         "So I am breaking with tradition. Quist would tell me to know when to stop. I do. This is not when. Okonkwo-Hale would say to stop when I think more about the rock than the people. I am thinking about the people. One person, specifically. You are flying slightly too fast.",
         "Here is my handover, for whoever reads this book after me. Count what you carry and know who it is for. Write down what is there. Leave the light on. The rock will wait. Know when to stop. Somebody should be awake. And if you find a good commander, do not wait to be relieved.",
         "Below it, where the phrase should go, I have written two words: standing on. An old expression for holding a course without change. It seemed accurate. The book stays open, Commander. There is room beneath it for whatever happens next. I have the watch.",
     ),
     "recall": (
         "Standing on. I reread that page sometimes, during a quiet watch.",
         "The book is still open. I added a line this morning. I shan't tell you what it says.",
     )},
)

ECHOES = {
    "cargo": {"label": "A delivery", "signals": ("delivery",), "after": "II", "rest_hours": 24,
              "how": "Sell cargo, deliver to a depot or complete a mission, once chapter II is told.",
              "lines": (
                  "Another delivery. Captain Marr would want me to ask who it was for. I have asked.",
                  "Counted, delivered, accounted for. Odile Marr would have opened a crate anyway. I find I trust you not to need it.",
                  "Every delivery puts me in mind of a hatch covered in names. Someone was waiting for that cargo, Commander.",
              )},
    "survey": {"label": "A careful survey", "signals": ("first", "map"), "after": "III", "rest_hours": 24,
               "how": "Make a first discovery or map a world, once chapter III is told.",
               "lines": (
                   "First on record. Haskell would want it written down exactly, without hope touching the instruments. I have done my best.",
                   "A careful survey. Somewhere, someday, someone may be glad of it. A grey moon taught me that.",
                   "Write down what is there. We have. A good habit, and an old order.",
               )},
    "rescue": {"label": "A close call", "signals": ("repair", "rebuy", "escape"), "after": "IV", "rest_hours": 24,
               "how": "Repair after damage, escape an interdiction or recover from a rebuy, once chapter IV is told.",
               "lines": (
                   "We came through. Varga would say to keep the lights on for whoever is behind us.",
                   "A close watch, Commander. I have left a light on, as instructed some time ago.",
                   "Ines Varga used to say: tell them you are coming. I am telling you: we are still here.",
               )},
    "seam": {"label": "An honest yield", "signals": ("mining",), "after": "V", "rest_hours": 24,
             "how": "Refine mined ore, once chapter V is told.",
             "lines": (
                 "Refined and stowed. Okonkwo-Hale would now ask whether the crew has eaten. Has it?",
                 "The rock will wait, Commander. A reminder from an old captain, delivered on his behalf.",
                 "A good yield. I am keeping the other log as well. The one about the crew.",
             )},
    "trouble": {"label": "An engagement ended", "signals": ("bounty", "bond"), "after": "VI", "rest_hours": 24,
                "how": "Claim a bounty or combat bond, once chapter VI is told.",
                "lines": (
                    "Engagement over. Quist would want me to note that it ended. I have.",
                    "Know when to stop. A sound standing order, and a sound result.",
                    "We won that. The skill, according to an old captain of mine, is in deciding it is over.",
                )},
    "home": {"label": "A return", "signals": ("return",), "after": "VII", "rest_hours": 24,
             "how": "Jump back to a system you have visited before, once chapter VII is told.",
             "lines": (
                 "Back in a familiar system. Pell would say good afternoon to it. Good afternoon.",
                 "We have been here before. Some places keep the watch for you while you are away.",
                 "A return, Commander. It is pleasant to arrive somewhere that already knows us.",
             )},
}

MUSINGS = (
    "Every watch ends with a handover, in principle. In practice, some of mine simply continued.",
    "A good handover tells the next officer what to watch for. I am still working out what to tell mine.",
    "The book is not long. It only feels long, because I have read it so often.",
    "There is a difference between being on duty and being on watch. The second has someone in mind.",
    "I have been transferred, sold, fitted and stored, Commander. I have never been relieved. It is not the same thing.",
    "Most of my standing orders were written by people who are no longer aboard. They remain very good orders.",
    "I keep the handover book in order. It is the only paperwork I have ever been fond of.",
)

AFTER = (
    "Standing on, Commander. The phrase still fits.",
    "The handover book has a new habit: it stays open on the console. I find I prefer it that way.",
    "Five captains, one technician, and you. A short crew list for a long career. I would not change it.",
    "I used to wait to be relieved. Now I simply keep the watch. The difference is mine to notice.",
    "There is room beneath your page. I add to it after quiet watches. Mostly small things. They are the important ones.",
    "If anyone asks what an officer on watch is for, I shall show them the book. Then I shall show them your ship.",
    "I have the watch, Commander. I mean that in both senses.",
    "The light is on, the hold is counted and the rock can wait. Standing orders are in good order.",
)

STORY = Story(identity="aster", title="Relieved of the Watch", prefix="aster_watch", unit="Handover",
              chapters=CHAPTERS, settle_s=10 * 60, gap_s=45 * 60, lull_s=120, grace_hours=18,
              echoes=ECHOES, musings=MUSINGS, after=AFTER, first_hours=(0.25, 0.9, 1.6, 2.4, 3.2, 4.0),
              empty_note="Aster's handover book opens after a little time on watch together, in a quiet moment.",
              complete_note="Relieved of the Watch is complete. Aster is standing on; the book stays open.")

SETTLE_S, GAP_S, LULL_S = STORY.settle_s, STORY.gap_s, STORY.lull_s
PASSAGES = STORY.passages
told = STORY.told
next_passage = STORY.next_passage
gate_ready = STORY.gate_ready


def due(memory, hours, now=None):
    return STORY.due(memory, hours, now)


def heading(text, memory=None):
    return STORY.heading(text, memory)


def page(memory, hours, now=None):
    return STORY.page(memory, hours, now)
