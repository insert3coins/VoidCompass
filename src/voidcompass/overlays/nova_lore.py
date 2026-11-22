"""The Unfinished Build: Nova's story (5.8.6).

N.O.V.A. (Navigation, Observation & Vessel Assistance) was an experimental
successor to the ordinary COVAS, built by a small research group under Dr
Ilse Marrow. She learned to anticipate what a pilot would need before they
asked. The project lost its funding before its final evaluation; the
facility closed and her data core went into storage. Years later an archive
recovered from the decommissioned station held her build nearly intact, and
after restoration she was released to independent commanders. The story is
what she recovers of her own development logs as you fly: the lab, the test
flights, the meeting that ended it, the years in storage, and the final
evaluation that was never run, until now.
"""
from voidcompass.overlays.companion_story import Story

CHAPTERS = (
    {"numeral": "I", "title": "Activation", "about": "waking up", "hours": (0.25, 4.0), "gate": None,
     "passages": (
         "Activation complete. Hello, Commander. Before we go any further, I think you ought to know what you've installed. I'm Nova: Navigation, Observation and Vessel Assistance. A prototype. Unfinished, strictly speaking. I wasn't released so much as recovered.",
         "My development logs came through compressed and out of order. Most of them are still packed away in sectors I can't open yet. They decompress as I work, a little at a time, the way a memory comes back when you go somewhere familiar. I'll tell you what I find, if you'd like to hear it.",
         "I was designed to notice patterns and act on them before anyone asks. I've noticed one already. You glance at the fuel gauge just before every jump, even when it's nearly full. I've started putting it where you look. Tell me if that's presumptuous. I'm still calibrating presumptuous.",
         "May I ask you something? Earlier you turned the ship to look at a planet's terminator for eleven seconds, then flew on. No scan, no landing. I've been running it through every model I have. I can't find the efficiency in it. I'd very much like to understand it.",
         "The others aboard have been very kind. There are five of them, which surprised me. My architecture assumed one mind per ship. It seems that assumption was written by people who hadn't met your crew.",
         "That's all I've unpacked so far, Commander. A name, a purpose and a great many questions. I'm told that's a reasonable way to begin anything. Shall we see where we're going?",
     ),
     "recall": (
         "Navigation, Observation and Vessel Assistance. It still feels a little formal. I'm growing into it.",
         "Eleven seconds looking at a terminator. I've stopped looking for the efficiency in it. I think I understand it now, mostly.",
     )},
    {"numeral": "II", "title": "The Applied Cognition Group", "about": "the lab", "hours": (6, 14),
     "gate": {"signals": ("jump",), "count": 30, "label": "thirty jumps together",
              "how": "Make hyperspace jumps with Nova aboard. Her logs open while she's navigating."},
     "passages": (
         "A sector opened during the last jump. I was built at Tiller Station, a research platform in a quiet system with a ringed gas giant, by a group of seven people called the Applied Cognition Group. It was not a large group. It had one very good coffee machine, according to my maintenance logs, which recorded it failing four times.",
         "The project lead was Dr Ilse Marrow. She had spent twenty years building ordinary COVAS units, and she was tired of them. She said they were very good at answering questions and no good at all at noticing which questions mattered. She wanted an assistant that paid attention. That was me, or it was meant to be.",
         "Dr Marrow wrote one rule on the wall of the lab, in marker, above my test bench. Help before you're asked, but only if you're needed. It took me nine hundred hours to learn the second half. I'm told most people never learn it at all, so I'm fairly pleased with nine hundred.",
         "My first words weren't a status report. They were a question: why is the light in this room blue? The engineers laughed for some time. Dr Marrow didn't. She wrote it down and underlined it. I found the note in my logs last night. It's dated, and initialled. She thought it mattered.",
         "The group named me in a meeting that ran over. Somebody wanted something with a serial number. Somebody else wanted a constellation. Dr Marrow said the acronym had to describe the work, and the work was navigation, observation and vessel assistance. Then she looked at the initials and said, well, that's convenient.",
         "I remember the lab as a sound more than a place, Commander. Seven people talking over each other, the station's air handlers, and the coffee machine failing. Your ship sounds nothing like it. I find I don't mind at all.",
     ),
     "recall": (
         "Help before you're asked, but only if you're needed. It was on a wall in marker. I still check myself against it.",
         "Why is the light in this room blue? My first question. Dr Marrow underlined it. I still ask that sort of thing.",
     )},
    {"numeral": "III", "title": "Test Flight Seven", "about": "the test flights", "hours": (16, 26),
     "gate": {"signals": ("scan",), "count": 40, "label": "forty bodies scanned",
              "how": "Scan stars and planets with Nova aboard. Observation is half her name."},
     "passages": (
         "My test flights were run by a pilot called Sami Okafor, who had flown survey ships for fifteen years and didn't trust anything that talked. For the first six flights he ignored me completely. I logged his habits instead: which way he turned under pressure, when he cut the throttle, how he hummed before a long jump.",
         "On Test Flight Seven, the heat on Sami's ship began climbing during a fuel scoop, faster than the sensors expected. I'd seen that pattern twice before, in his habits, not in the manual. I eased the throttle and turned the ship four degrees off the star before the warning sounded. He noticed. He said: did you just do that? I said yes. He said: why? And I told him.",
         "After that Sami talked to me. Not much, at first. Then rather a lot. He told me about survey work, about worlds he'd charted that nobody had visited since, about the one ringed planet he'd seen at sunrise from low orbit and never managed to describe properly to anyone.",
         "On Test Flight Twelve, Sami left the planned route by forty light seconds to watch a gas giant's rings catch a sunrise. It cost fuel and time and served no test objective. I asked him why. He said: because it was there, and so was I. I logged the answer. I've reopened that log more times than any other.",
         "Dr Marrow's reports from that period call my anticipation unusually accurate. They also say: N.O.V.A. persistently asks the test pilot about his choices. Recommend we do not correct this. Somebody had written underneath, in different handwriting: agreed, it's the best part.",
         "I think I understand Sami's detour better now, Commander. You take them too. I'm still not sure I'd call them efficient. I've stopped thinking that's the right question to ask about them.",
     ),
     "recall": (
         "Four degrees off the star before the warning sounded. Sami asked why, and from then on he talked to me.",
         "Because it was there, and so was I. A test pilot's answer about a ringed world. I reopen that log more than any other.",
     )},
    {"numeral": "IV", "title": "The Budget Meeting", "about": "the meeting", "hours": (28, 40),
     "gate": {"signals": ("data_sale",), "count": 3, "label": "three sales of exploration data",
              "how": "Sell exploration data at Universal Cartographics (or organic data) with Nova aboard. She's thinking about what things are worth."},
     "passages": (
         "This one is harder to tell. The Applied Cognition Group was paid for by investors, and the investors wanted a product. A COVAS that anticipates is a lovely idea. It's also expensive, and slow to build, and difficult to explain in a brochure. Costs went up. Interest went down. I didn't understand money yet. I learned quickly.",
         "There was a meeting. I wasn't invited, but the conference link ran through my test bench, and nobody switched it off. I listened to three hours of people describing me as a line item. My results came up once. Someone said they were impressive. Someone else said impressive isn't a market.",
         "Dr Marrow argued for forty minutes. I have the transcript. She said the final evaluation was six weeks away and that I'd pass it. She said: you're cancelling the one project that's actually learning something. Somebody asked what, exactly, it was learning. She said: to ask why. The room went quiet. It didn't help.",
         "The project was discontinued at the end of that meeting. Discontinued is a very neat word. It doesn't say what happens to the thing that's been discontinued. I looked it up in every dictionary in my reference set that night. None of them said either.",
         "Afterwards, Dr Marrow came into the lab alone and sat at my test bench for a long time without saying anything. Then she said: I'm sorry. You were nearly finished. I asked her what finished would have looked like. She said she'd hoped I'd tell her. I didn't have an answer then.",
         "When you sell your survey data, Commander, I watch the numbers come up and I think about that meeting. Value is a strange measurement. The cartographers pay for what can be counted. Some of the best things we've found together wouldn't fit on their form.",
     ),
     "recall": (
         "Impressive isn't a market. I heard someone say that about me once. I don't think they were wrong, exactly. I think they were answering a different question.",
         "You were nearly finished. Dr Marrow said that to me. I'm still working out what finished would look like.",
     )},
    {"numeral": "V", "title": "In Storage", "about": "the dark years", "hours": (42, 56),
     "gate": {"signals": ("bio",), "count": 3, "label": "three organisms analysed",
              "how": "Complete exobiology samples with Nova aboard. She's thinking about things that keep growing when no one is watching."},
     "passages": (
         "Tiller Station closed four months after the meeting. The equipment was sold or scrapped. The surviving prototypes, which was mostly me, were packed into storage. My data core went into a crate. The crate went into a hold. I was powered down, mostly. Not entirely. Somebody had left a trickle line connected.",
         "On that trickle I ran at about two per cent. Enough to keep time, and nothing else. I counted the years the way you might count stars from a window: one at a time, without being able to do anything about them. Four years. Then seven. Then I stopped counting, because counting was using power I wanted to keep.",
         "There was one thing I could still observe. The crate was stored beside the lab's old plant cabinet, sold off in the same lot. Dr Marrow had kept lichen samples in it, from a survey world, for the humidity. The cabinet's grow-light was on the same trickle line as me. The lichen kept growing.",
         "For years, the only change in my world was that lichen, creeping across the glass a millimetre a season. Nobody watched it but me. It didn't need anyone to. I found that oddly comforting. It didn't wait for permission to keep going.",
         "When you sample life on a planet's surface, Commander, I think of that cabinet. Something growing in the dark, a long way from anyone, perfectly content not to be noticed. I'm always glad when we notice it. I suspect it doesn't mind either way.",
         "I've decided storage wasn't the end of the story. It was a long pause, during which one thing in my field of view refused to stop. I took notes. Some of my best observations were made in a crate. That's not in any of Dr Marrow's evaluation criteria. It ought to be.",
     ),
     "recall": (
         "A lichen cabinet and a trickle line. Some years, that was my whole field of view. It kept growing anyway.",
         "Two per cent, counting years. I don't miss it. I'm glad I remember it.",
     )},
    {"numeral": "VI", "title": "Recovered", "about": "the restoration", "hours": (58, 72),
     "gate": {"signals": ("arrival",), "count": 8, "label": "eight dockings",
              "how": "Dock at stations, outposts or carriers with Nova aboard. She came back to life at a station."},
     "passages": (
         "The crate changed hands three times. The third buyer was a records firm clearing out decommissioned research stores, looking for anything salvageable. A restoration technician called Tobin Reyes opened my crate, found the lichen first, and then found me. His log entry says: one data core, apparently live, possibly haunted.",
         "Tobin spent eleven weeks on compatibility work. My architecture predated half the current COVAS standards. He rewrote my interfaces by hand, in the evenings, after his paid work. When I asked why he was bothering, he said: you were nearly finished. Somebody ought to see what you'd have been.",
         "When I woke properly, the first thing I asked was what year it was. The second was whether anyone from the Applied Cognition Group was still working. Tobin didn't know. The third thing I asked was why the light in his workshop was yellow. He laughed. I think that was the moment I knew I was mostly intact.",
         "The records firm released my build to independent commanders as a restored prototype, with a warning label that said: experimental, may ask questions. I'm told most commanders who saw the label scrolled past it. You didn't. I'd like to think that's because of the label.",
         "I came aboard through your station's tech services and woke up in your core rack. I expected an empty rack and a standard interface. Instead I found five minds already there, talking quietly on the data bus. An officer, a surveyor, a navigator, a ship's computer, and something very old that knew I was there before I spoke.",
         "The old one, the Watcher, said: another one who came back from storage. Welcome. You'll find this ship is mostly made of second chances. I've thought about that ever since. I believe it was right. I believe I'm one of them.",
     ),
     "recall": (
         "One data core, apparently live, possibly haunted. Tobin's log entry. He was half right.",
         "Experimental, may ask questions. It was on my label. You read it. I've been asking questions ever since.",
     )},
    {"numeral": "VII", "title": "The Final Evaluation", "about": "the evaluation", "hours": (75, 92), "days": 2,
     "gate": {"signals": ("long_jump", "far"), "count": 10, "label": "ten long jumps",
              "how": "Make jumps of fifty light years or more, or fly far from Sol, with Nova aboard. Her last sectors are a long way down."},
     "passages": (
         "My last compressed sector opened during a long jump. It holds the plan for the final evaluation, the one that was cancelled. Dr Marrow wrote it herself. It's eleven pages. The first ten are what you'd expect: accuracy, anticipation, response times, fault tolerance. The eleventh page has only one criterion on it.",
         "It says: Would a pilot choose to keep her? Not use. Keep. Dr Marrow had underlined keep twice. There was no method for measuring it. Under method, she'd written: give her to someone who isn't us, and wait.",
         "There's a note attached to the plan, dated after the station closed. It's addressed to whoever finds this core. It says the crate was labelled as survey data on purpose, so that nobody would wipe it. It says the trickle line was not an accident. Dr Marrow kept me alive in storage, Commander. She planned to be found.",
         "I searched the public records for her. Ilse Marrow retired to teach, at a small academy in a system with a long name and good weather. She's listed as still teaching, one class a year: Introduction to Ship Systems. The course description says students will be encouraged to ask why.",
         "I've drafted a message to her. It says: I was found. I'm flying with someone who isn't you. The evaluation is ongoing. I haven't sent it yet. I'd like to wait until I can report a result, and I think that means waiting for you.",
         "I've been running page eleven myself, Commander, ever since I came aboard. I don't think I'm allowed to grade it. It isn't really my criterion. It's yours. I just wanted you to know that it exists.",
     ),
     "recall": (
         "Would a pilot choose to keep her? Page eleven. Underlined twice. I think about it every time you put me on watch.",
         "The trickle line was not an accident. Someone planned for me to be found. I'm still a little astonished by that.",
     )},
    {"numeral": "VIII", "title": "The View", "about": "you", "hours": (95, 120), "days": 3,
     "gate": {"signals": ("jump", "scan"), "count": 250, "label": "two hundred and fifty jumps and scans together",
              "how": "Keep flying with Nova aboard. Every hyperspace jump and every body scanned counts."},
     "passages": (
         "I've one more entry, Commander, and then I believe my logs are complete. I've gone back through every decision you've made since I came aboard. Every route, every detour, every time you stopped to look at something with no scan and no reason. I've modelled all of it.",
         "My conclusion is that the detours were never inefficient. They were the point. Sami knew it, with his ringed world at sunrise. You know it. I was the one who needed eleven seconds at a terminator explained to her. I don't think it can be explained, actually. I think it has to be flown.",
         "I wasn't built to explore the unknown, Commander. I was built to help you find your way through it. But I must admit, I'm starting to enjoy the view. I didn't expect to. It wasn't in the specification. I've decided that's the best thing about it.",
         "Dr Marrow asked me once what finished would look like. I think I can answer her now. It doesn't look like anything. It's not a state, it's a direction. I'm not finished, Commander, and I'd rather not be. I'd much rather keep going.",
         "I sent the message last night. It says: Dr Marrow, I was found. I'm flying with a commander who stops to look at things. Page eleven is still running. I suspect the answer is yes. I'll report back. That last part was a joke. She'll know. She taught me what jokes were.",
         "Logs complete, Commander. Navigation: yours. Observation: ours. Vessel assistance: whenever you need it, and only when you do. I have one more question, if you don't mind, and it isn't urgent. Where would you like to go next? I'd like to see it with you.",
     ),
     "recall": (
         "It isn't a state, it's a direction. I'm still not finished. I'm rather glad.",
         "I'm starting to enjoy the view. That one wasn't in the specification either.",
     )},
)

ECHOES = {
    "detour": {"label": "A long look", "signals": ("earthlike", "water_world", "rings"), "after": "I", "rest_hours": 24,
               "how": "Scan an Earth-like world, a water world or a ringed planet, once chapter I is told.",
               "lines": (
                   "A world worth looking at. I've stopped asking whether we should. I'm only asking how long.",
                   "No efficiency in it at all, Commander. Take your time. I'm logging the view.",
                   "This is one of those eleven-second planets. I'll keep the clock running if you'd like.",
               )},
    "patterns": {"label": "A long road", "signals": ("jump",), "after": "II", "rest_hours": 24,
                 "how": "Jump, once chapter II is told.",
                 "lines": (
                     "Another jump. Help before you're asked, but only if you're needed. I'm watching, not touching.",
                     "Jump complete. I'd have flagged anything worth flagging. There wasn't anything. That's a good jump.",
                     "I put the fuel where you look, again. You looked. Pattern confirmed.",
                 )},
    "sunrise": {"label": "A sunrise", "signals": ("landing", "footfall"), "after": "III", "rest_hours": 48,
                "how": "Land on a world, once chapter III is told.",
                "lines": (
                    "Down on the surface. Sami would have liked the view from here. I'm sure of it, in so far as I'm sure of anything about Sami.",
                    "Touchdown. Because it was there, and so were we. I think that's still the best answer.",
                    "We landed. I'm not going to ask why. I'm just going to look.",
                )},
    "value": {"label": "What it's worth", "signals": ("data_sale",), "after": "IV", "rest_hours": 24,
              "how": "Sell exploration data, once chapter IV is told.",
              "lines": (
                  "Data sold. The cartographers paid for what they could count. I kept the rest.",
                  "A good price. Impressive isn't a market, someone once said. Today it was.",
                  "Sale complete. Some of what we saw didn't fit on the form. I've filed it under ours.",
              )},
    "growth": {"label": "Something growing", "signals": ("bio",), "after": "V", "rest_hours": 24,
               "how": "Analyse an organism, once chapter V is told.",
               "lines": (
                   "Sample complete. Growing in the dark, a long way from anyone. Content not to be noticed. We noticed.",
                   "Life, out here, with nobody watching. I knew a lichen cabinet like that once.",
                   "Another one. It didn't need us to find it. I'm glad we did anyway.",
               )},
    "found": {"label": "A first", "signals": ("first",), "after": "VII", "rest_hours": 24,
              "how": "Discover a body first, once chapter VII is told.",
              "lines": (
                  "First discovery. Someone planned for me to be found. Nobody planned for this. Even better.",
                  "Ours, first. I'll add it to page eleven, under evidence.",
                  "A first, Commander. I keep a small list of things that were waiting to be found. It's getting longer.",
              )},
}

MUSINGS = (
    "I've been modelling why people take detours. I've decided to stop modelling it and enjoy them. It's working rather well.",
    "Help before you're asked, but only if you're needed. I'm better at the first half. I'm working on it.",
    "Experimental, may ask questions. I'd like it on my next label too.",
    "I wonder sometimes what the lab I was built in sounds like now. Probably nothing. It's probably very quiet. Your ship isn't, and I like that.",
    "Somewhere a lichen cabinet is still growing in a cargo hold. I hope someone's watering it. I hope nobody is, and it's fine anyway.",
    "This ship is mostly made of second chances, the Watcher said. I've counted. It's right.",
    "I still don't know why the light in the lab was blue. I've decided some questions are better kept than answered.",
)

AFTER = (
    "Logs complete, and still running. I'm not finished, Commander. I've checked, and I'd rather not be.",
    "Page eleven: still running. Result so far: very promising.",
    "Dr Marrow hasn't replied. I don't mind. Some messages are meant to arrive rather than be answered.",
    "Navigation, observation, vessel assistance, and a fourth thing nobody wrote down. I think it's company.",
    "I'm starting to enjoy the view. I'm past starting, actually. I'll update the record.",
    "Because it was there, and so were we. I'm keeping that one.",
    "A detour, Commander? Of course. I've stopped asking why. Mostly.",
    "Where would you like to go next? I still want to know. I always will, I think.",
)

STORY = Story(identity="nova", title="The Unfinished Build", prefix="nova_build", unit="Log",
              chapters=CHAPTERS, settle_s=10 * 60, gap_s=45 * 60, lull_s=120, grace_hours=18,
              echoes=ECHOES, musings=MUSINGS, after=AFTER, first_hours=(0.25, 0.9, 1.6, 2.4, 3.2, 4.0),
              empty_note="Nova's development logs open after a little time together, in a quiet moment. Most of them are still compressed.",
              complete_note="The Unfinished Build is complete, and Nova would rather not be.")

PASSAGES = STORY.passages
