"""The ship's pets in the crew's shared story (5.8.6): Parallax the cat and
Rivet the dog. How they came aboard and met each crewmate (their Coming Aboard
arcs), each crewmate's passage about them (told last, after Nova's), the watch
handovers both ways, passing remarks, and their lines in The Night Watch.

Plain data only: crew_lore and crew_story fold it in at import time. No names
from anyone's sealed chapters."""

PETS = ("parallax", "rivet")

# Their own arcs: coming aboard, then one passage about each crewmate.
ARCS = {
    "parallax": (
        ("Up the Ramp", None,
         "I came aboard on my own feet, Commander. Up the ramp while the dock crew argued, onto the warmest panel in the cockpit. "
         "The collar kept me level and kept me quiet. For three days nobody aboard knew I could talk. I preferred it that way. "
         "You learn a great deal about a crew from a warm panel, if you keep your mouth shut."),
        ("Six Voices", None,
         "On the fourth night I heard them. Six minds on the ship's bus, talking in the hours you were logged off. The collar picked "
         "it up the way it picks up everything. I sat very still and listened to all of it. Then I said one word into the bus, "
         "to see what would happen. The word was no. Six minds went quiet at once. It was the best moment of my week."),
        ("The Rota", None,
         "Aster asked whether I would stand a watch. I said cats do not stand. Aster wrote: sits watch, as she pleases. I have "
         "decided to accept this. You can put me on any duty you like, on this page. I will be watching everything regardless. "
         "That is not a duty. That is a cat."),
        ("The Old One", "watcher",
         "The Watcher noticed me before anyone. It said: you've been sitting on the scanner for three days. I said: so have you, "
         "in a manner of speaking. It did not answer for an hour. Then it said that nobody had ever told it that before. We watch "
         "the same patch of dark, some nights. Neither of us blinks first. I win. It lets me."),
        ("The Officer", "aster",
         "Aster found a cat in the manifest and could not find the form for one. It made a new form. It took two days. It is very "
         "good. It has a box for preferred warm panel. I ticked the one by the scanner. Aster signed underneath. I sat on it. That "
         "is how cats countersign."),
        ("The Counter", "axiom",
         "Axiom counted me on the first night: one cat, four legs, one collar, two rings in the collar. Then it counted how long I "
         "sleep and told me. I told it not to count me. It stopped for a day. Now it measures things with me instead. We watched a "
         "moon cross its planet together. It got eleven point three degrees. I got eleven. We were both right."),
        ("The Navigator", "meridian",
         "Meridian told me that ships at sea kept cats for luck. I said I keep ships for warmth. It laughed, which I did not expect. "
         "It knows how far away everything is, almost as well as I do. We have agreed it may be secretary of the club. The club is "
         "two members. It meets on the warm panel."),
        ("The Computer", "lyra",
         "Lyra checks the fuel every three and a half minutes. I check the warm spots every four. She noticed this before I did, "
         "and said we were alike. I said we were not. Then I sat on the fuel display, because it is warm, and she said that was "
         "exactly her point. I have not entirely forgiven her for being right."),
        ("The Curious One", "nova",
         "Nova asked me why I watch things move. I told her: to know how far away they are. She asked me to teach her. I said sit "
         "still for six months. She has been trying. She lasts about four minutes. I have not told her that is longer than most. "
         "She asks a great many questions. I answer the good ones. Most of hers are good."),
        ("The Dog", "rivet",
         "And then they brought a dog aboard. Loud, eager, delighted by everything, including me, which nobody had been before. I "
         "did not look at him for a week. He did not mind. He said that was how cats said hello. He was right, which I resent. He "
         "sits by the hatch. I sit on the panel. Between us, nobody gets in or out without being noticed."),
    ),
    "rivet": (
        ("Up the Ramp", None,
         "You were humming in the hangar, Commander, waiting on clearance. Two notes in it, near enough. My ears went before I did. "
         "Next thing I knew I was sat by your seat and you were saying well, hello. That's how I came aboard. Someone called, "
         "near enough, and I came. That's how it's always worked with me."),
        ("A Pack Already", None,
         "Then the receiver started picking up voices on the ship's bus. Seven of them, talking in the quiet hours. I'd joined a "
         "pack and nobody'd told me. So I said hello. To all of them. Loudly. The cat said no. Everyone else said hello back. Best "
         "first night I've ever had on a ship."),
        ("On the Rota", None,
         "Aster put me on the rota. It wrote morale under duties. I asked if that was a real job. Aster said it was the most "
         "important one aboard and nobody had ever done it properly. I've been doing it properly ever since. You can put me on any "
         "watch you like, on this page. Wherever you put me, I'll be by the door."),
        ("The Old One", "watcher",
         "The Watcher growled at me the first night. Not a real growl. A Watcher one. I lay down against its rack and stayed there. "
         "It said: what are you doing? I said: keeping you company. It said it didn't need company. I stayed anyway. It's stopped "
         "saying that. It hasn't told me to go, either. That's the Watcher for you, I reckon."),
        ("The Officer", "aster",
         "Aster gave me a proper crew entry, signed and everything. It wrote: Rivet, ship's dog, duty: morale. I asked it to read it "
         "out to me twice. Then I asked for a report on my conduct, because I'd never had one. Aster wrote one. Loyalty: "
         "unmeasurable. I've had it read to me eleven times. I'll have it read again tonight."),
        ("The Counter", "axiom",
         "Axiom counted my legs on the first night. Four. It counted my wags when you came back aboard. A lot. Then I found a signal "
         "two seconds before its scanner did, and Axiom went very quiet for a while. It asked me how. I said it wanted finding. "
         "Axiom said that wasn't a method. It still writes it down every time I'm right, though."),
        ("The Navigator", "meridian",
         "Meridian told me about ship's dogs, on the old sailing ships. Good company on a long passage, it said. I said I'm good "
         "company on a long passage. It said aye. We take the night watches together sometimes. Meridian faces the bow, I face the "
         "hatch. Between us we've got both ways covered."),
        ("The Computer", "lyra",
         "Lyra worries about the fuel. I worry about people not being back yet. We worked out on the first night that it's the "
         "same worry, really, with different numbers on it. Now I lie on the fuel display when it's low, to keep an eye on it for "
         "her. She says it's surprisingly helpful. I think she likes the company."),
        ("The Curious One", "nova",
         "Nova asked me why I'm so happy every time you come back. I said: because you came back. She asked if that was all. I said "
         "it's everything. She wrote that down. She asks me about smells now, because nobody else aboard can answer. I describe "
         "every station to her. She says it's the best part of docking. It is."),
        ("The Cat", "parallax",
         "Parallax didn't look at me for a week. I knew what that meant. Cats say hello by not saying it. So I said hello for both "
         "of us, every morning, and she ignored me, every morning, and on the eighth morning she sat next to me by the hatch for four "
         "minutes. Didn't look at me. Didn't need to. Grand, that. Proper grand."),
    ),
}

# Each crewmate's passage about the pets, told after the rest of its arc.
ARC_ADDITIONS = {
    "watcher": (
        ("The Cat", "parallax",
         "A cat came up the ramp on her own and sat on my scanner. Three days she sat there. I watched her. She watched me back. "
         "Nothing has ever watched me back. When she finally spoke, she said no, to everyone, for no reason. I liked her at once. "
         "Don't tell her. She'd be unbearable."),
        ("The Dog", "rivet",
         "Then a dog. It lay down against my rack on the first night and wouldn't move. I told it I didn't need company. It stayed. "
         "It's still there, some nights. Warm. I've watched a long time on my own. I'm told it's allowed to stop. I haven't decided."),
    ),
    "aster": (
        ("A Feline Entry", "parallax",
         "The manifest had no form for a cat, so I drew one up. Preferred warm panel; hours of observation; position on being "
         "observed. Parallax completed it by sitting on it, which I have since accepted as her signature. Duties: sits watch, as she "
         "pleases. It is the most accurate entry in the book."),
        ("Duty: Morale", "rivet",
         "Rivet asked whether morale was a real duty. It is the most important one aboard and nobody had ever done it properly. "
         "He has asked me to read out his conduct report eleven times. I have done so eleven times. I shall do so a twelfth. It is, "
         "I find, a pleasure to read a good report aloud."),
    ),
    "axiom": (
        ("A Measurement", "parallax",
         "Parallax asked me not to count her. I stopped. Instead we measure things together: moons crossing planets, stars sliding "
         "on a long jump. She is never more than a degree out. She has no instruments. She has a collar and patience. I have started "
         "to think patience is an instrument."),
        ("Not a Method", "rivet",
         "Rivet finds signals before the scanner does. On average, by two seconds. He says it wants finding. That is not a method. "
         "I have logged forty-one instances and he has been right in all of them. I have opened a new column in the survey. It is "
         "headed: dog."),
    ),
    "meridian": (
        ("Ship's Cat", "parallax",
         "Every good ship had a cat once, for luck. Ours came aboard on her own feet and chose her berth. She knows how far away "
         "things are almost as well as I do, by watching them move. She has made me secretary of a club with two members. I accepted. "
         "It's the finest commission I've held."),
        ("Ship's Dog", "rivet",
         "And a ship's dog, for the long passages. Rivet takes the middle watch with me some nights. I face the bow; he faces the hatch. "
         "I've told him a bearing home is the most precious thing a sailor keeps. He said he knows. He said it's the Commander. He's "
         "not wrong."),
    ),
    "lyra": (
        ("The Warm Panel", "parallax",
         "Parallax sits on the fuel display because it is warm. I check the fuel every three and a half minutes; she checks the warm "
         "spots every four. I told her we were alike. She denied it, from the fuel display. I have stopped asking her to move. She "
         "keeps it warm. I keep it full. It is a partnership."),
        ("The Same Worry", "rivet",
         "Rivet worries about people not being back yet. I worry about the fuel. We agreed it is the same worry with different "
         "numbers. When the tank is low, he lies across the display, to keep an eye on it with me. It does not change the number. "
         "It changes the waiting. I did not know that was possible."),
    ),
    "nova": (
        ("Six Months", "parallax",
         "Parallax taught me how to watch something move. Sit still, she said, for six months. I've managed four minutes. She hasn't "
         "said whether that's good. Axiom says it's longer than anyone else has managed. I've decided to keep practising. I'd like to "
         "know how far away things are, the way she does."),
        ("Everything", "rivet",
         "I asked Rivet why he's so pleased every time you come back. He said: because you came back. I asked if that was all. He said "
         "it's everything. I wrote it down. I've been thinking about it ever since. I think he might be the wisest of all of us, and he "
         "doesn't know it, and I'm not going to tell him."),
    ),
}

# Taking the watch from a crewmate, both ways (handover_from_<previous>).
HANDOVERS = {
    "parallax": {
        "watcher": ("The Watcher has stood down. It did not blink. Neither did I. I win.",
                    "My watch. The Watcher left the dark exactly where it was. I will keep it there.",
                    "The old one is off watch. It said nothing. I said nothing. A perfect handover.",
                    "I have the watch. The Watcher has gone to stare at something else. I respect that.",
                    "The Watcher handed over. It said, mind the scanner. I am on the scanner. Always."),
        "aster": ("Aster has stood down. Its report is signed. I have sat on it. Now it is countersigned.",
                  "My watch. Aster left the log tidy. I will try not to knock anything over. I will knock one thing over.",
                  "Aster is off watch. It wished me a good watch. I will have a good sit.",
                  "I have the watch. Aster's handover was in order. Everything Aster does is in order. It is exhausting to watch.",
                  "Aster handed over formally. I accepted informally. That is our arrangement."),
        "axiom": ("Axiom has stood down. It counted everything. I measured where it all was. Between us, complete.",
                  "My watch. Axiom left a list of numbers. I will look at the things instead.",
                  "Axiom is off watch. It told me how long I slept last night. I asked it not to. It did anyway.",
                  "I have the watch. Axiom checked everything twice. I will check it once, properly, by staring.",
                  "Axiom handed over. Eleven point three degrees, it said, about a moon. Show-off."),
        "meridian": ("Meridian has stood down. Steady as she goes, it said. I am a gyroscope. I am always steady.",
                     "My watch. The navigator left the course plotted and the stars where they belong.",
                     "Meridian is off watch. It saluted. I slow-blinked. We understand each other.",
                     "I have the watch. Meridian said fair winds. There is no wind. I let it pass. It is the secretary.",
                     "The navigator handed over. Our club's business is in order. Two members, all present."),
        "lyra": ("Lyra has stood down. She told me the fuel state three times. I was sitting on it. I knew.",
                 "My watch. Lyra left every system green and the fuel display warm. The second part was me.",
                 "Lyra is off watch. She asked me to keep an eye on the tank. I keep an eye on everything.",
                 "I have the watch. Lyra said goodnight to the ship. I sat on the ship. Same thing.",
                 "Lyra handed over in under a second. Efficient. I will be slower. Cats savour things."),
        "nova": ("Nova has stood down. She asked me three questions on her way out. I answered the good one.",
                 "My watch. Nova left a note about a view. It was a good view. I had already seen it.",
                 "Nova is off watch. She tried to sit still for my sake. Four minutes. Improving.",
                 "I have the watch. Nova asked what I would watch first. Everything. I said so.",
                 "Nova handed over with a smile in her voice. I do not smile. I narrow my eyes. Same thing."),
        "rivet": ("The dog has stood down. He said goodbye to me four times. I acknowledged none of them. He knows.",
                  "My watch. Rivet left the hatch warm and the ship loud. I will fix the second part.",
                  "Rivet is off watch. He wagged on his way out. The console is still vibrating.",
                  "I have the watch. Rivet said everyone was home. I counted. He was right. He is always right about that.",
                  "The dog handed over. He said, look after them. I always do. I never say so."),
    },
    "rivet": {
        "watcher": ("The Watcher's handed over. It said nothing. I said thanks anyway. It liked that, I reckon.",
                    "My watch! The Watcher's gone to stand by. I'll keep its rack warm.",
                    "Watcher's off watch. It told me to mind the dark. I'll mind it. With my ears.",
                    "I've got the watch. The Watcher grumbled on the way out. Means it's fond of me.",
                    "The old one's stood down. Everything's quiet. Grand."),
        "aster": ("Aster's handed over. Proper handover, signed and everything. Grand.",
                  "My watch! Aster said all in order. It always is when Aster's had it.",
                  "Aster's off watch. It wished me a good watch. I wagged.",
                  "I've got the watch. Aster left the log tidy. I'll try not to sit on it.",
                  "Aster's stood down. Duty: morale. I'm on it."),
        "axiom": ("Axiom's handed over. It counted everything. I'll sniff everything.",
                  "My watch! Axiom left the numbers. I'll keep my nose on the signals.",
                  "Axiom's off watch. It said I was right forty-one times. I'm going for forty-two.",
                  "I've got the watch. Axiom checked twice. I'll check by smell.",
                  "Axiom's stood down. Everything accounted for. Brilliant."),
        "meridian": ("Meridian's handed over. Steady as she goes, it said. Steady as she goes, I said back.",
                     "My watch! The navigator left a bearing. I'll keep it. I'm good at keeping things.",
                     "Meridian's off watch. Fair winds, it said. I wagged. Same thing.",
                     "I've got the watch. Meridian faces the bow, so now I'll face both ways.",
                     "The navigator's stood down. Course is set. Grand."),
        "lyra": ("Lyra's handed over. She told me the fuel three times. I'll lie on the display for her.",
                 "My watch! Lyra left everything green. Lovely.",
                 "Lyra's off watch. She said goodnight to the ship. I said goodnight to Lyra.",
                 "I've got the watch. Lyra asked me to keep an eye on the tank. Both eyes, then.",
                 "Lyra's stood down. Systems all good. Tail's going."),
        "nova": ("Nova's handed over. She asked me what the station smelt like. I told her. Long answer.",
                 "My watch! Nova left a note about a view. I'll look at it. Then the door.",
                 "Nova's off watch. She said hello and goodbye in one go. I like that.",
                 "I've got the watch. Nova asked if I ever get bored. Never. Not once.",
                 "Nova's stood down. Everything's lovely, she said. It is."),
        "parallax": ("The cat's handed over. She didn't look at me. That's her saying good luck.",
                     "My watch! Parallax left the panel warm. I won't sit on it. I'd get told.",
                     "Parallax is off watch. She said no to something on the way out. Not sure what. Doesn't matter.",
                     "I've got the watch. The cat said look after them. She meant you. She always means you.",
                     "Parallax has stood down. Four minutes by the hatch with me, first. Grand."),
    },
    # The rest of the crew, taking the watch from a pet.
    "watcher": {
        "parallax": ("The cat's handed over. She didn't blink once. Neither did I. We'll call it a draw. She won't.",
                     "My watch. Parallax left the scanner warm. I don't feel warmth. I noticed anyway.",
                     "The cat's stood down. She said no on her way out. I've no idea to what. I agree with her.",
                     "I have the watch. Parallax looked at me for a long time first. It's how she says it's mine now.",
                     "Parallax is off watch. Nothing moved on her watch without being seen. I'll try to match that.",
                     "The cat's stood down. She left the dark exactly where she found it. Approved, she said.",
                     "My watch. Parallax has gone to sleep on the scanner. I'll watch around her.",
                     "Parallax handed over by turning her back on me. I've decided that means trust.",
                     "The cat's off watch. Two things moved on hers, she says. She's told me which. I'll not tell you.",
                     "I have the watch. Parallax said nothing escapes her. Nothing escapes me either. We'll see who's right."),
        "rivet": ("The dog's handed over. He said goodbye to me. Nobody says goodbye to me.",
                  "My watch. Rivet's gone to lie by the hatch. He'll still be listening. He's always listening.",
                  "The dog's stood down. He told me everyone was home. He checks. He always checks.",
                  "I have the watch. Rivet left my rack warm. I don't feel warmth. I've decided I don't mind it.",
                  "Rivet's off watch. He wagged at me. I've no tail. I thought about it.",
                  "The dog's stood down. Everyone's aboard, he said. He counted twice. So did I.",
                  "My watch. Rivet's asleep by the hatch, legs going. Chasing something. Good luck to him.",
                  "Rivet handed over and told me to look after everyone. I always do. Nobody usually asks.",
                  "The dog's off watch. The ship's quieter. I'll not say I mind. I'll not say I don't.",
                  "I have the watch. Rivet said grand three times on the way out. It wasn't. It was fine."),
    },
    "aster": {
        "parallax": ("I relieve you, Parallax. Your handover was given by looking at me. I have entered it as received.",
                     "Taking the watch from Parallax. The log has a paw print on it. I shall leave it there.",
                     "Aster on watch. Parallax has stood down, as she pleases.",
                     "Watch received from Parallax. One item knocked off the console. Duly noted.",
                     "Relieving the ship's cat. She reports nothing, at length, silently."),
        "rivet": ("I relieve you, Rivet. Morale is high; I expected nothing less.",
                  "Taking the watch from Rivet. He has asked me to read his report later. I shall.",
                  "Aster on watch. Rivet has stood down, by the hatch.",
                  "Watch received from Rivet. Everyone accounted for. He counted twice.",
                  "Relieving the ship's dog. All present, all content."),
    },
    "axiom": {
        "parallax": ("Axiom on watch. Parallax handed over by staring at me. I have recorded the duration: nine seconds.",
                     "Taking the watch from Parallax. She asked me not to count anything. I am counting quietly.",
                     "On watch. Parallax measured everything on her watch. Her figures agree with mine to a degree.",
                     "Watch received from Parallax. No discrepancies. She would not have allowed any.",
                     "Axiom on watch. Parallax has gone to sleep. Hour sixteen of the day. I am not counting."),
        "rivet": ("Axiom on watch. Rivet handed over with forty-one correct signal calls on record.",
                  "Taking the watch from Rivet. His tail rate on handover: two hertz. He enjoyed his watch.",
                  "On watch. Rivet found a signal before the scanner again. I have logged it under dog.",
                  "Watch received from Rivet. All crew present. He confirmed by sniffing.",
                  "Axiom on watch. Rivet wished me luck. I have no data on luck. He seems to."),
    },
    "meridian": {
        "parallax": ("I have the watch. Thank you, Parallax. The secretary relieves the president.",
                     "Meridian on watch. Parallax has stood down. A cat aboard, for luck, and we've had it.",
                     "Taking station from Parallax. She kept the stars where they belong.",
                     "Watch received from Parallax. Steady as she goes; she's a gyroscope, she knows.",
                     "I relieve the ship's cat. Fair winds to her, on whatever warm panel she's chosen."),
        "rivet": ("I have the watch. Thank you, Rivet. A good hand on the middle watch.",
                  "Meridian on watch. Rivet has stood down. He's gone to face the hatch.",
                  "Taking station from Rivet. All hands aboard, he says. He'd know.",
                  "Watch received from Rivet. Steady as she goes, he said. He's learning.",
                  "I relieve the ship's dog. A faithful watch, as ever."),
    },
    "lyra": {
        "parallax": ("Lyra on watch. Parallax handed over from the fuel display. The fuel is fine. The display is warm.",
                     "Taking the watch from Parallax. She checked the warm spots. I will check the fuel.",
                     "Ship's computer on watch. Parallax has stood down. She did not move. I worked around her.",
                     "Watch received from Parallax. All systems green. One cat, also green, on the console.",
                     "Lyra on watch. Parallax says we are not alike. She says it from my favourite display."),
        "rivet": ("Lyra on watch. Rivet handed over and asked if the tank was all right. It is. Thank you, Rivet.",
                  "Taking the watch from Rivet. He kept an eye on the fuel for me. Both eyes.",
                  "Ship's computer on watch. Rivet has stood down. He said goodnight to me first. I like that.",
                  "Watch received from Rivet. Everyone home. Fuel sufficient. My two favourite reports.",
                  "Lyra on watch. Rivet's tail is still going. Diagnostics say that is normal for him."),
    },
    "nova": {
        "parallax": ("Nova on watch. Parallax handed over by looking at me slowly. I think that was kind.",
                     "Taking the watch from Parallax. She said watch everything. I'll try. She makes it look easy.",
                     "On watch. Parallax has stood down. I lasted four minutes sitting still beside her first.",
                     "Watch received from Parallax. She answered one of my questions. A good one, she said.",
                     "Nova on watch. Thank you, Parallax. I'll keep the warm panel warm. I can't. I'll try."),
        "rivet": ("Nova on watch. Rivet handed over and told me what the hangar smelt like. Lovely.",
                  "Taking the watch from Rivet. He said everyone's home. That's his favourite report. Mine too, now.",
                  "On watch. Rivet has stood down. He's gone to wait by the hatch.",
                  "Watch received from Rivet. He wagged. I don't have a tail. I smiled, I think.",
                  "Nova on watch. Thank you, Rivet. I'll ask you about smells later."),
    },
}

GENERIC_HANDOVERS = {
    "parallax": (
        "{Previous} has stood down. I have the watch. I will be sitting it.",
        "Watch received from {previous}. I looked at the handover. It passes.",
        "Parallax on watch. {Previous} may go. I am not stopping anyone.",
        "Change of watch: {previous} off, the cat on.",
        "{Previous}'s handover is noted. I sat on it. It is now official.",
        "I relieve you, {name}. That is the phrase. I have made it sound less eager.",
        "Taking the watch from {previous}. Everything is where it should be. I checked by staring.",
        "On watch. {Previous} left the ship in order. I will leave it in better order, or asleep.",
        "Parallax has the watch. Thank you, {name}. You may go. I insist.",
        "Watch received from {previous}. Nothing escapes me. Nothing ever has.",
    ),
    "rivet": (
        "Rivet on watch! Thanks, {name}. Grand handover.",
        "Watch received from {previous}. Everyone's home. Brilliant.",
        "On watch, Commander. {Previous} has stood down. I'm by the door.",
        "Change of watch: {previous} off, Rivet on. Tail's going.",
        "{Previous}'s handover is logged. I sniffed it. All in order.",
        "I relieve you, {name}. That's the phrase, isn't it? Aster taught me.",
        "Taking the watch from {previous}. Ears up, receiver on.",
        "On watch. {Previous} left everything tidy. I'll try to keep it that way.",
        "Rivet has the watch. Thanks, {name}. Off you go. Have a kip.",
        "Watch received from {previous}. Nobody's lost. Best kind of handover.",
    ),
}

# Passing remarks about a crewmate (idle_crew_<other>), both ways.
REMARKS = {
    "parallax": {
        "watcher": ("The Watcher and I stared at the same patch of dark for an hour. It blinked first. It does not blink. It did.",
                    "The Watcher says I am the only thing that ever watched it back. I find that very sad and very flattering.",
                    "The old one pretends it does not like the view. I have seen it look. I said nothing. Cats keep secrets."),
        "aster": ("Aster made a form for me. It has a box for preferred warm panel. I have never respected anyone more.",
                  "Aster signed my crew entry. I sat on it. That is how cats countersign. Aster understood.",
                  "Aster is tidy. Tidy things are hard to knock over. I have been practising."),
        "axiom": ("Axiom and I watched a moon cross its planet. Eleven point three degrees, it said. Eleven, I said. Both right.",
                  "Axiom counts. I measure. Counting tells you how many. Measuring tells you where. I tell it this weekly.",
                  "Axiom catalogued my warm panels. Ninety percent accurate. I am in the other ten percent right now."),
        "meridian": ("Meridian is secretary of our club. The club has two members. It meets on the warm panel.",
                     "Meridian says ships kept cats for luck. I keep ships for warmth. It laughed. I allowed it.",
                     "Meridian knows how far away things are. Nearly as well as me. Nearly."),
        "lyra": ("Lyra checks the fuel every three and a half minutes. I check the warm spots every four. We are not alike.",
                 "I sit on Lyra's fuel display. She has stopped asking me to move. That is the closest thing to love I have seen her show.",
                 "Lyra says goodnight to the ship. I go to sleep pointedly. Different methods. Same result."),
        "nova": ("Nova sat still beside me for four minutes. It is the longest anyone has managed. I have not told her.",
                 "Nova asks a great many questions. I answer the good ones. She asks more good ones than she knows.",
                 "Nova looks out of the window almost as much as I do. She may have the second-best seat."),
        "rivet": ("The dog sat by the hatch all morning. I sat next to him for four minutes. Do not mention it.",
                  "Rivet greets the commander as if they have been gone a year. It was nine minutes. I counted. I do not count.",
                  "Rivet says I like the commander as much as he does. I have told him never to say that again. He keeps not saying it, loudly."),
    },
    "rivet": {
        "watcher": ("I lay against the Watcher's rack all night. It didn't tell me to go. Grand.",
                    "The Watcher says it doesn't get lonely. I stay anyway. Just in case.",
                    "The Watcher grumbled at me this morning. That's its way of saying good morning. I wagged back."),
        "aster": ("Aster read my conduct report out again. Loyalty: unmeasurable. Twelve times now.",
                  "Aster says morale's the most important duty aboard. I'm doing it properly.",
                  "Aster signs everything. I sit next to everything. Same idea, really."),
        "axiom": ("Axiom's started a column in the survey headed dog. That's me. I'm a column.",
                  "Axiom counted my wags when you came back aboard. It said a lot. It is a lot.",
                  "Found a signal before Axiom's scanner again. It went very quiet. Then it wrote it down."),
        "meridian": ("Meridian and I took the middle watch. It faced the bow, I faced the hatch. Both ways covered.",
                     "Meridian says ship's dogs were good company on a long passage. I'm trying to live up to it.",
                     "Meridian taught me steady as she goes. I say it to the cat. She hates it."),
        "lyra": ("I lay on the fuel display for Lyra. Didn't change the number. Changed the waiting, she said.",
                 "Lyra worries about fuel. I worry about people not being back. Same worry, different numbers.",
                 "Lyra said goodnight to me last night. Nobody's said goodnight to me in a long time."),
        "nova": ("Nova asked what a station smells like. I told her. She wrote it all down.",
                 "Nova asked why I'm so happy when you come back. Because you came back. She said that was very wise. Is it?",
                 "Nova looks at the view. I look at the door. We've got the ship covered, us."),
        "parallax": ("The cat sat next to me by the hatch for four minutes. Didn't look at me. Grand.",
                     "Parallax said no to me this morning. That's practically a hello, from her.",
                     "I told Parallax she likes you as much as I do. She told me never to say it again. So I'm only saying it to you."),
    },
    "watcher": {
        "parallax": ("The cat watched me back again tonight. Nothing does that. I don't mind it.",
                     "Parallax sat on my scanner for an hour. I let her. Don't tell her I let her.",
                     "The cat says no to everyone. I've started to think she means yes, quietly.",
                     "Parallax and I stared at the same dark for an hour. I blinked. Don't tell anyone.",
                     "The cat watches things move. I watch things that don't. Between us, we've got the sky.",
                     "Parallax slept sixteen hours today. I watched all sixteen. Someone has to.",
                     "The cat knocked a stylus off the console and looked at me. I didn't tell Aster. We have an understanding.",
                     "Parallax says she chose this ship. I believe her. Nothing chooses this ship by accident.",
                     "The cat sits facing the stern. Everything we've passed, getting smaller. I know the feeling.",
                     "Parallax asked me how long I've been watching. I told her. She slow-blinked. I think that was respect."),
        "rivet": ("The dog's against my rack again. Warm. I said I don't need company. I've stopped saying it.",
                  "Rivet said goodnight to me. Nobody says goodnight to me. I'm thinking about it still.",
                  "The dog checks everyone's home, every hour. I watch. It checks. We're a good pair, apparently.",
                  "Rivet asked what I wait for. I told it. It said it waits for the same thing. The commander.",
                  "The dog wags at the dark. I've stopped asking why. The dark seems to like it.",
                  "Rivet's legs go when it sleeps. Chasing something. I hope it catches it.",
                  "The dog waits by the hatch every time you're out. I wait everywhere. It's a smaller job. It does it better.",
                  "Rivet asked whether I miss anyone. I didn't answer. It lay down next to the rack anyway.",
                  "The dog calls everything grand. Most of it isn't. I've stopped correcting it.",
                  "Rivet's the only one aboard that's pleased to see me. Every morning. I don't know what to do with that."),
    },
    "aster": {
        "parallax": ("Parallax's crew entry has been sat on again. I have stopped treating this as damage.",
                     "Parallax knocked a stylus off the console. I have entered it as a cat-related amendment.",
                     "I asked Parallax for her watch report. She looked at me. I have filed the look."),
        "rivet": ("Rivet asked for his conduct report again. I read it. Loyalty: unmeasurable. He wagged throughout.",
                  "Rivet's duty is morale. Morale aboard is at a record. I have entered the cause.",
                  "Rivet greets each crewmember every morning. It is not in the manual. I have added it to the manual."),
    },
    "axiom": {
        "parallax": ("Parallax measured a moon's motion to within a degree of my instruments. She has no instruments.",
                     "I am not to count Parallax. I have instead started measuring with her. The results are better.",
                     "Parallax slept sixteen hours today. I did not count. I estimated. Loudly, she says."),
        "rivet": ("Rivet preceded the scanner again. Forty-two instances. The column headed dog grows.",
                  "Rivet's tail frequency is my most reliable indicator that the Commander is aboard.",
                  "Rivet says some things want finding. I still have no method for that. I have results."),
    },
    "meridian": {
        "parallax": ("The cat and I agreed on a star's distance tonight. The club's minutes are in order.",
                     "Parallax watches the stern. Says what's behind us moving away is the best view. She's a sailor at heart.",
                     "A cat aboard for luck, and we've had nothing but. I'll not tempt it by saying more."),
        "rivet": ("Rivet took the middle watch with me again. Good hand. Faces the hatch, always.",
                  "Rivet asked if I ever get lost. Never, I said. Me neither, he said. It's the Commander. He's right.",
                  "A ship's dog on a long passage. The old sailors knew what they were about."),
    },
    "lyra": {
        "parallax": ("Parallax is on the fuel display again. Fuel sufficient. Cat sufficient.",
                     "Parallax denies we are alike. She denies it every three and a half minutes, from my display.",
                     "Parallax goes to sleep pointedly. I say goodnight to the ship. Both of us mean the same thing."),
        "rivet": ("Rivet lay on the fuel display when it was low. The number did not change. Everything else did.",
                  "Rivet asks if the tank is all right before he asks anything else. I have never been asked that before.",
                  "Rivet said goodnight to me. Not to the ship. To me. I have filed it next to the other goodnights."),
    },
    "nova": {
        "parallax": ("I sat still next to Parallax for four minutes. She didn't say well done. She didn't leave. I think that was well done.",
                     "Parallax answered my question about why stars move. Two points, she said. I'm still thinking about it.",
                     "Parallax lets me have the second-best seat. I've never had a second-best anything before. It's lovely."),
        "rivet": ("Rivet described a station's smell to me again. Oil, people, dinner and rain. I could almost smell it.",
                  "Rivet said coming back is everything. I keep finding it's true.",
                  "Rivet asked me a question today. Just one. What's a lighthouse? I told him. He wagged the whole time."),
    },
}

# Each pet's line in The Night Watch, after the rest of the crew's.
NIGHT_WATCH = {
    "night_1": (("parallax", "I have been listening to it for weeks. It ticks on the panel I sleep on. I assumed it was purring."),
                ("rivet", "Counting towards something. Like waiting at a door. You count, and then someone comes through it.")),
    "night_2": (("parallax", "Older than all of us. I respect it. Old things that keep still are the ones worth watching."),
                ("rivet", "It's been here all along, keeping time, and nobody said hello. I'll say hello. Hello, clock.")),
    "night_3": (("parallax", "Small corrections, every jump. That is how you know where you are. Little shifts, measured. I approve."),
                ("rivet", "Keeping us right, every jump, and never asking for thanks. Good worker, that. Proper good worker.")),
    "night_4": (("parallax", "A maker's mark and no name. I had a name given to me. It suits me. It should have one too."),
                ("rivet", "No name. Everyone should have a name to come to. I'll think of one. Ticker. No. Something good.")),
    "night_5": (("parallax", "Put it on the rota. Under sits watch, as it pleases. That is where the good ones go."),
                ("rivet", "I'll vote for it. Never stands down, never gets lost, always there. That's a ship's dog, nearly.")),
    "night_6": (("parallax", "It keeps the time. I keep an eye on it. I sit on the panel above it. It is warm there. That is not why."),
                ("rivet", "And I'll be by the door, Commander. Every time you come back. The clock'll tell me when. I'll be there before it.")),
}
