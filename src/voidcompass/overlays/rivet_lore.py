"""The Long Recall: Rivet's story (5.8.6).

Rivet was a search-and-rescue dog on Harrow's Drift, a mining moon, working
with a rescue hand called Maddox Kerr. His receiver was built to turn what his
nose found into words, and to carry Maddox's recall: two notes on a whistle.
In a collapse, Maddox went into the last tunnel and told him to stay. He
stayed. The recall never came, and he was carried off the moon. The story is
how he learned what happened in that tunnel, and who he comes back to now.
"""
from voidcompass.overlays.companion_story import Story

CHAPTERS = (
    {"numeral": "I", "title": "Good Lad", "about": "how he came aboard", "hours": (0.25, 4.0), "gate": None,
     "passages": (
         "Right then, Commander. The receiver's on, so you'll get it in words. I'm Rivet. I'm a dog. I came aboard because you whistled, near enough. You were humming in the hangar and it sounded like a call. So I came. That's how it works with me. Someone calls, I come.",
         "This thing on my back is a receiver. It listens to me, my ears, my nose, my tail, and turns it into talk. It was built to say what I'd found. Mostly now it says I'm pleased you're back. It says that a lot. It's not wrong.",
         "I've a nose for signals. Not just smells. A beacon on the edge of hearing, a ping in the noise, something that wants finding. I've always had it. The receiver sharpened it. When the scanner pings, my ears go before it does.",
         "The rest of the crew are all right. The officer gave me a proper entry. The counting one counted my legs. The navigator calls me a good hand. The cat won't look at me, which I'm told is how cats say hello. I'm working on it.",
         "Best bit of any day is when you come back, Commander. Off the concourse, out of the SRV, back from wherever. I can't help it. Tail goes, ears go, whole of me goes. You'll get used to it. I hope you don't, mind. I like the look on your face.",
         "There's a story to me. Bit of a long one. I'll tell it in bits, when it's quiet. It's about a whistle, mostly. And waiting. I'm good at waiting. I'm better at coming back.",
     ),
     "recall": (
         "You were humming in the hangar and it sounded like a call. So I came. Best thing I ever did, that.",
         "Someone calls, I come. That's the whole of me, near enough.",
     )},
    {"numeral": "II", "title": "Harrow's Drift", "about": "the rescue station", "hours": (6, 14),
     "gate": {"signals": ("arrival",), "count": 8, "label": "eight dockings",
              "how": "Dock at stations, outposts or carriers with Rivet aboard. He loves a homecoming."},
     "passages": (
         "I grew up on a mining moon called Harrow's Drift. Cold, dusty, honeycombed with tunnels. Hundreds of miners under the ground and one rescue station on top, for when the ground moved. It moved a lot. I was the rescue station's dog. I was the best thing on that moon. Ask anyone.",
         "My handler was Maddox Kerr. Big hands, bad knees, laughed like a cargo door. Maddox picked me out of a litter because I was the one that wouldn't stop sniffing his boots. He said: that one's got a nose. He was right. He was nearly always right about dogs.",
         "Maddox trained me in the old tunnels. He'd hide a beacon, or himself, somewhere down in the dark, and I'd find him. Every time. He'd say good lad, and I'd lose my mind. Same as when you dock, Commander. That's where it comes from, all that tail.",
         "The receiver was Maddox's idea. Rescue's about telling people what you've found, quick. A dog barks, they don't know if it's a miner or a gas pocket. So he had one built. It said: two, alive, left passage. It saved more people than me barking ever did.",
         "Every shift ended at the station door. Maddox would come up out of the lift, dusty to the eyes, and I'd be there. Every time. He said I could hear the lift before the lift could. Every dock you make, I'm at that door again. I know it's a hangar. I don't care.",
         "Harrow's Drift wasn't much to look at. Grey rock, grey sky, a sun like a lamp left on in another room. But it was home, and everyone on it knew my name. You don't need much more than that. A door, someone coming through it, and your name.",
     ),
     "recall": (
         "Maddox came up out of the lift dusty to the eyes, every shift, and I was at the door. Every dock, I'm at that door again.",
         "That one's got a nose. First thing anyone ever said about me. Still true.",
     )},
    {"numeral": "III", "title": "Two Notes", "about": "the recall", "hours": (16, 26),
     "gate": {"signals": ("codex", "bio"), "count": 5, "label": "five new Codex entries or species analysed",
              "how": "Log new Codex entries or analyse species with Rivet aboard. He has a nose for things that want finding."},
     "passages": (
         "Every working dog has a recall. A call that means drop everything and come back. Maddox's was two notes on a little steel whistle. High, then low. I'd hear it through half a kilometre of rock. I'd come through anything for it. That's what a recall's for.",
         "He never used it for nothing. Never to show off, never to test me in front of people. Only when it mattered. Maddox said a recall's a promise. You don't spend it. I didn't understand that then. I do now.",
         "The receiver could carry the recall. Maddox had it built in, so if he couldn't whistle, his suit could send the two notes straight to me, on a band nobody else used. Belt and braces, he called it. He was a belt and braces sort of man.",
         "When you find something new, Commander, a Codex entry, a living thing on a cold rock, I get the same feeling I got in the tunnels. Something down there wanting finding. Good, that feeling. Best feeling a dog can have, after the door one.",
         "I found twenty-two miners in four years on Harrow's Drift. Every one of them came up alive. Maddox kept count on the station wall with a marker. Twenty-two lines and a little paw drawn at the end. I used to sit under it.",
         "Two notes. High, then low. I still listen for them. Not because I'm sad. It's just how I'm built. My ears turn to it in my sleep. If you ever hear me whine in the night, Commander, that's what it is. Don't worry. It's an old tune.",
     ),
     "recall": (
         "A recall's a promise. You don't spend it. Maddox said that. I believe it more every year.",
         "Twenty-two lines on the station wall and a little paw at the end. I used to sit under it.",
     )},
    {"numeral": "IV", "title": "The Fall", "about": "the collapse", "hours": (28, 40),
     "gate": {"signals": ("mining",), "count": 10, "label": "ten refinings or cracked cores",
              "how": "Mine with Rivet aboard: refine ore or crack a core. Rock and tunnels are his old work."},
     "passages": (
         "The big quake came on a night shift. The whole moon shrugged. I felt it in my feet before the alarm went. Fourteen miners down in the deep seam, and the main shaft gone. Maddox had his suit on before the siren stopped. I had mine on before he'd asked.",
         "We went down the old ventilation shafts, the ones we trained in. Dust so thick the lamps were useless. Didn't matter. I had my nose. Maddox had his hand on my harness. We went in like that, the two of us, one of us seeing and one of us steering.",
         "We found them in threes and fours. Behind rockfalls, in side galleries, one lad in a pump room up to his chest in water. The receiver kept talking: three, alive, right. Two, alive, ahead. Maddox kept answering: good lad. Good lad. Good lad. I think he said it a hundred times that night.",
         "Thirteen up and out by the morning. Thirteen. The fourteenth was further in, past a gallery that was still coming down a bit at a time. You could hear it. Little bits of the roof, letting go. Maddox listened to it for a long time.",
         "When you mine, Commander, when a core cracks and the rock goes, I feel it in my feet. Same as that night. Don't worry. It's not fear. It's remembering. There's a difference, and I know which one it is.",
         "Maddox knelt down in the dust and took my face in his hands. He said: one more. I'm going in. You stay. He said it the proper way, the training way. Stay. Then he went into the gallery, and the lamp got smaller, and I stayed.",
     ),
     "recall": (
         "Three, alive, right. Two, alive, ahead. Good lad, good lad. A hundred times that night, I reckon.",
         "One more, Maddox said. You stay. And I did. You know I did. You know me.",
     )},
    {"numeral": "V", "title": "Stay", "about": "the waiting", "hours": (42, 56),
     "gate": {"signals": ("repair", "rebuy", "escape"), "count": 3, "label": "three hard moments survived",
              "how": "Repair the ship, survive a loss, or escape an interdiction with Rivet aboard. He knows about hard nights."},
     "passages": (
         "The gallery came down about twenty minutes after he went in. Not all of it. Enough. The dust came out of the mouth of it like breath on a cold day, and then it was quiet. I stayed. That's the command. You stay till you're called.",
         "They came for me in the morning, the other rescue hands. They dug for two days. I helped. I dug till my paws went, and then I sat at the mouth of the gallery, because that's where I'd been told to be. They tried to move me. I didn't let them. I wasn't being difficult. I was being good.",
         "On the fourth day they stopped digging. The rock was still moving. Too dangerous, the station chief said. She sat with me a long time, after. She didn't say anything. She put her hand on my back, on the receiver, and left it there. That was kind. I remember that.",
         "I listened for the two notes. Day and night. High, then low. The receiver would've carried them, even through rock. It didn't. Every hour I listened, and every hour it was nothing, and I stayed anyway. Because I hadn't been called. You don't leave till you're called.",
         "The station closed the deep seam. The company moved the miners to another moon. Everyone packed. I didn't. Someone had to stay at the gallery. Someone had told me to. I don't think anybody on that moon has ever been angry with me for it. I think it broke their hearts a bit.",
         "In the end a freighter pilot came to take the last of the station gear, and the chief asked her to take me too. I wouldn't go. So the pilot sat down in the dust beside me and ate her lunch, and shared it, and talked to me about nothing for an hour. Then she picked me up and carried me aboard. I let her. I was very tired, Commander.",
     ),
     "recall": (
         "You don't leave till you're called. I didn't. I'd do it again. I'd hate it again, too.",
         "A freighter pilot sat in the dust and shared her lunch, and then she carried me aboard. Kind people, freighter pilots.",
     )},
    {"numeral": "VI", "title": "Ship's Dog", "about": "the freighters", "hours": (58, 72),
     "gate": {"signals": ("delivery",), "count": 10, "label": "ten deliveries or missions",
              "how": "Sell cargo, complete missions or deliver to a depot with Rivet aboard. He spent years on freighters."},
     "passages": (
         "Freighters, after that. That pilot's first, then her friend's, then a long-haul outfit that liked having a dog in the hold for luck. I was good luck, they said. I sniffed out a gas leak on one and a stowaway on another. The stowaway was a kitten. I didn't tell anyone. She wasn't a cat yet. She didn't count.",
         "A ship's dog has a job. Greet the crew, guard the hold, sit by whoever's having a bad day. I was good at all of it. I liked the work. But every new port, first thing I did, I'd stand at the cargo door with my ears up. Listening for two notes. Habit.",
         "The receiver kept the band open. Maddox's band, the one nobody else used. Years, it was open. Mostly nothing. Sometimes, in the deep black between stars, I'd hear something. Faint. Like two notes, but not quite. I'd put it down to the hull creaking. It wasn't the hull.",
         "I met all sorts. Kind pilots, tired pilots, one who talked to me in a silly voice. I liked that one, actually. None of them whistled. I don't mean they couldn't. I mean none of them called me the way you call something that's yours. I came when asked. I didn't come home.",
         "Then a hangar. Yours. You were humming while you waited for clearance, a little tune, not much of one. Two notes in it, near enough. High, then low. My ears went before I did. By the time I knew what I was doing I was up your ramp and sat by your seat. You looked at me. You said: well, hello. That was it, really.",
         "Every delivery you make, Commander, I'm stood by the cargo door. Old habit, from the freighters. I'm not listening for the whistle now, not really. I'm just glad of the work. You carry things to people who need them. That's rescue, of a sort. Maddox would've said so.",
     ),
     "recall": (
         "You were humming in the hangar. Two notes in it, near enough. My ears went before I did.",
         "Well, hello, you said. That was it, really. That was the whole of it.",
     )},
    {"numeral": "VII", "title": "The Signal", "about": "the two notes", "hours": (75, 92), "days": 2,
     "gate": {"signals": ("jump",), "count": 60, "label": "sixty jumps together",
              "how": "Make hyperspace jumps with Rivet aboard. His receiver is listening on every one."},
     "passages": (
         "I've got to tell you something, Commander, and I want to get it right. The faint thing I used to hear between stars. Two notes, but not quite. I've been hearing it more, the further we fly. Clearer. The receiver's been logging it. It's real. It's on Maddox's band.",
         "I asked Axiom to help. Axiom was brilliant. It took the logs from every jump and laid them over each other and found where the signal was strongest. It's coming from a long way off. From a cold, grey moon with a long name. I know that moon. I'd know it anywhere.",
         "It's Maddox's suit. The recall I told you about, the one built into the receiver's band, so his suit could call me if he couldn't whistle. It's been going all this time. On a tiny battery, from under the rock. Two notes. Over and over. Weaker every year. It's been going since the night the gallery fell.",
         "Do you understand what that means, Commander? He called me. In the end, in there, he called me back. He didn't want me to stay. He wanted me with him. The rock was too thick and the band was too faint and I was too close to hear it. Funny, that. Too close.",
         "I've had a lot of nights to think about it since we found it. And I'm not sad, mostly. I'm not. A recall's a promise. You don't spend it on nothing. He spent his on me. He wanted me to come. That's the best thing I've ever been told, and it took me years to hear it.",
         "I asked Aster to write to the rescue station. It reopened, years back, under a new chief. Aster sent them the signal and where it's coming from, all very proper, signed and everything. Now we wait. I'm good at waiting. You know that by now.",
     ),
     "recall": (
         "He called me. In the end, he called me back. The band was faint and I was too close to hear it.",
         "Axiom laid every jump over every other and found it. Two notes, from a grey moon. I'd know that moon anywhere.",
     )},
    {"numeral": "VIII", "title": "Stand Down", "about": "you", "hours": (95, 120), "days": 3,
     "gate": {"signals": ("arrival", "jump"), "count": 200, "label": "two hundred jumps and dockings together",
              "how": "Keep flying with Rivet aboard. Every jump and every docking counts."},
     "passages": (
         "The rescue station wrote back, Commander. They followed the signal down. They found him. They brought Maddox up, properly, the way he brought up all those miners, and they've put him where the station door is, so he's at the top of the lift for good. I'm glad. I'm very glad.",
         "The new chief sent a message for me, through the receiver. Just the two notes, the old recall, and then a word Maddox used at the end of every shift. Stand down. It means the work's done. You can rest now. I listened to it eleven times. Then I lay down. Properly. First time in years.",
         "The chief said I'd be welcome back. A dog's always welcome at Harrow's Drift. They'd put my name on the wall, next to the twenty-two lines and the little paw. Thirteen more lines, she said, from the night of the quake. Thirty-five. I didn't know they'd counted them. I sat with that for a while.",
         "I'm not going back, though. I've thought about it. Good dogs go where they're called, and I was called. Maddox called me back, in the end, and I'll always have that. But it was you who called me home. Humming in a hangar, not even knowing you were doing it. Two notes, near enough.",
         "A recall's a promise. You don't spend it. I know that better than any dog alive. So here's mine, Commander, for what it's worth from a dog with a radio on his back. Whenever you call, I'll come. Wherever we are. Through anything. That's not training. That's me.",
         "That's the story, then. All of it. I'll be by the door when you dock. I'll be at the ramp when you're back from the surface. I'll be under your seat when it's rough. And if you ever hum two notes in the hangar, high then low, you'll see a tail go so hard it'll shift the ship. Good lad, me. Good lad.",
     ),
     "recall": (
         "Stand down. It means the work's done. I listened to it eleven times, and then I lay down. Properly.",
         "Maddox called me back. You called me home. A dog can have both. I've checked.",
     )},
)

ECHOES = {
    "door": {"label": "A homecoming", "signals": ("arrival",), "after": "I", "rest_hours": 24,
             "how": "Dock somewhere, once chapter I is told.",
             "lines": (
                 "Docked! I'm at the door. I know it's a hangar. I'm at the door anyway.",
                 "We're in. Best bit of any day, this. Tail's going.",
                 "Home port or not, it's a door with you behind it. Grand.",
             )},
    "nose": {"label": "A find", "signals": ("codex", "bio"), "after": "III", "rest_hours": 24,
             "how": "Log a new Codex entry or analyse a species, once chapter III is told.",
             "lines": (
                 "Found something! Something wanting finding. Best feeling there is, that.",
                 "Ears went before the scanner did. I knew it was there.",
                 "A new find. I'd sit under the station wall for that one. Good work, Commander.",
             )},
    "rock": {"label": "Rock and dust", "signals": ("mining",), "after": "IV", "rest_hours": 24,
             "how": "Refine ore or crack a core, once chapter IV is told.",
             "lines": (
                 "Rock going. I feel it in my feet. It's all right. It's remembering, not fear.",
                 "Good clean mining. Nobody under it. That's how I like rock.",
                 "Another tonne. I used to dig with my paws. The limpets are quicker, I'll grant them that.",
             )},
    "hard": {"label": "A hard night", "signals": ("repair", "rebuy"), "after": "V", "rest_hours": 24,
             "how": "Repair the ship or come back from a loss, once chapter V is told.",
             "lines": (
                 "We're mended. I sat by you the whole time. That's my job on a bad day.",
                 "You came back. That's the bit that matters. The ship's just a ship.",
                 "Rough one, that. I'm under your seat. Not scared. Close by. There's a difference.",
             )},
    "hold": {"label": "A delivery", "signals": ("delivery",), "after": "VI", "rest_hours": 24,
             "how": "Deliver cargo or finish a mission, once chapter VI is told.",
             "lines": (
                 "Delivered! Someone needed that. That's rescue, of a sort.",
                 "Cargo's off. I stood by the hold door the whole way. Freighter habit.",
                 "Job done. Good work, that. Honest work.",
             )},
    "band": {"label": "A long run", "signals": ("jump",), "after": "VII", "rest_hours": 24,
             "how": "Make a hyperspace jump, once chapter VII is told.",
             "lines": (
                 "Receiver's listening on every jump. Not for anything now. Just for the quiet.",
                 "Another jump. The band's clear. Clear's good. Clear means nobody's calling for help.",
                 "Out we come. Ears up. All's well.",
             )},
}

MUSINGS = (
    "Tail's going. I can't help it. You're just sat there and it's going.",
    "I counted the doors on this ship. Eleven. I like to know where everyone comes in.",
    "The cat sat next to me for four minutes today. Didn't look at me. Didn't need to. Grand.",
    "I've a sniff of something on the scanner band. It's nothing. It's always nothing. I check anyway. That's the job.",
    "Sometimes I lie with my nose on your boot. Not for any reason. Just so I know where you are.",
    "The officer gave me a duty on the rota. It says: morale. I'm very good at morale.",
    "A dog's day is simple, Commander. Someone's back, someone's fed, nobody's lost. Today's a good day.",
    "The receiver hums when I'm happy. It's humming now. I didn't tell it to.",
    "I sniffed the cargo hold. All in order. One crate smells of oranges. Someone's going to be pleased.",
    "The navigator says I've good sea legs. I don't know what sea is. I've decided it's a compliment.",
    "I've learned the sound of your footsteps. All of them. Tired ones, happy ones, the ones when you've forgotten something.",
    "If you're ever low, Commander, I'll come and sit on your feet. It's what we do. It works more than you'd think.",
)

AFTER = (
    "Story's done. Work's done. I'm stood down, and stood by you. Both at once. Dogs can do that.",
    "Thirty-five lines on a station wall and a little paw. And one more ship, where I'm not counting anything. Just glad.",
    "Two notes, high then low. I hear them now and I just smile. Well. Pant. Same thing.",
    "I'm by the door. I'm always by the door. That's not the story. That's just me.",
    "Maddox called me back. You called me home. I come when either of you whistles. One of you just has to whistle a bit louder.",
    "The receiver's band is quiet now. Quiet's good. Quiet means nobody's calling for help, and the one who matters is right here.",
    "Good lad, me. I've heard it said enough times to believe it. You say it too. I've noticed.",
    "Whenever you call, I'll come. That's the promise. I don't spend it on nothing. I spent it on you.",
)

STORY = Story(identity="rivet", title="The Long Recall", prefix="rivet_recall", unit="Recall",
              chapters=CHAPTERS, settle_s=10 * 60, gap_s=45 * 60, lull_s=120, grace_hours=18,
              echoes=ECHOES, musings=MUSINGS, after=AFTER, first_hours=(0.25, 0.9, 1.6, 2.4, 3.2, 4.0),
              empty_note="Rivet tells his story in bits, when it's quiet. He's still sniffing out where to start.",
              complete_note="The Long Recall is complete. The work's done; the dog is staying.")

PASSAGES = STORY.passages
