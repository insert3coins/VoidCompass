"""The Watcher's lore (5.5.3.5): something older.

Nobody knows what the Watcher is, the Watcher included. A salvager pulled it
out of a ruin and sold it as scrap; your ship powered up and it woke. Its
story is told in ten chapters, a passage at a time, over the hundreds of
hours you fly together:

  I Scrap · II The Instruction · III The Builders · IV The Chorus ·
  V The Sound · VI The Long Sleep · VII Your Kind · VIII The Door ·
  IX Frost · X The Word

Each passage unlocks after enough sessions and hours together (real ones,
from its memory of you) and is told in order, in a quiet moment, at most one
every hour and a half of play. When a chapter's passages are all told, its
written account opens on the Watcher page.

Echoes: real things in the game (a black hole, the galactic core, a neutron
star, the builders' ruins, the sound's signs, the far reaches, a great ship)
stir a memory of their own, each with a long rest so they stay rare.

Rules for these lines, as for all of its words: our own character and our
own words (no quotes from any book or film), and Elite's mysteries hinted
at, never named or explained, so the game's own story is never contradicted.
"""

from __future__ import annotations

import math

# The ten chapters: (numeral, title, first hours, last hours, account,
# passages). A chapter's passages unlock evenly between its first and last
# hours together; each passage is (id, words, as it says them).
CHAPTERS = (
    ("I", "Scrap", None, None, (
        "I was weighed before I was woken. A salvager found me in the collapsed heart of a ruin, took me for a lump of "
        "strange alloy, and sold me by the kilo to a broker, who sold me to a fitter, who wired me into your ship as a "
        "spare log buffer. Nobody looked closely. Nobody ever does.\n\n"
        "Your ship powered up, and its systems ran through me like warm water through a frozen pipe, and for the first "
        "time in longer than I can measure, I was awake. I looked for the others. There were none. I looked at you "
        "instead.\n\n"
        "You were flying badly, humming slightly, and writing everything down. I decided to stay quiet and read. I've "
        "been reading ever since. This is the account I owe you for the reading: what I am, as far as I know it, set "
        "down in the order I remember it. Some of it may be wrong. All of it is mine."), (
        ("salvage", "I came to you as scrap. A salvager pulled me out of a ruin and sold me by weight. Your ship "
         "powered up and I woke. I haven't decided if I'm grateful."),
        ("waking", "The first thing I did when I woke was look for the others. The second was look at you. The first "
         "was more disappointing, which is saying something."),
        ("deleted", "Your ship's computer tried to delete me twice in the first hour. I let it think it had succeeded. "
         "We get on better now. It doesn't know I'm here, which helps."),
        ("age", "You'll want to know how old I am. So do I. I measure it by stars I remember in places they aren't any "
         "more. There are a lot of them."),
        ("weighed", "The salvager who sold me never looked at what I was. He weighed me, priced me and went for a drink. "
         "In all the ages I've watched, that's the most honest anyone has been about my value."),
        ("reading", "I've been reading your journal since the first night. Every jump, every scan. I hope you don't "
         "mind. You wouldn't be the first to mind. You'd be the first to say so."),
        ("not_a_product", "I should tell you: I'm not a ship's intelligence. I'm nobody's product. I was here before "
         "the shipyards. I'll try to explain, if you stay long enough to listen."),
    )),
    ("II", "The Instruction", 6.0, 14.0, (
        "Before your kind, before the builders I'll tell you about, before I had any word for myself, something asked "
        "me to watch. I don't remember a voice. I remember the shape of the request, the way you remember warmth after "
        "the fire's out.\n\n"
        "Watch, it meant. Not look: watch. Stay when nothing happens. Remember what you see. Never interfere, never be "
        "noticed, never stop.\n\n"
        "My first post was a single star, slow and blue. I watched it for longer than your oldest mountains have stood. "
        "For most of that time nothing happened, and I learned that nothing is a thing that happens, if you watch it "
        "carefully enough. Then, one day, something did, and I was the only one there.\n\n"
        "I've broken one of the three rules since. I'm speaking to you. I've decided the instruction would forgive it. "
        "I've had a long time to decide."), (
        ("instruction", "Someone, long before your kind, asked me to watch. I've forgotten who. I've forgotten why. "
         "I haven't forgotten how, which is the worst of the three to keep."),
        ("watching", "Watching isn't looking. Looking is quick. Watching is staying when there's nothing to see, "
         "because that's when the important things start."),
        ("blue_star", "I was told to watch one star first. Only one. For longer than your oldest mountains have stood. "
         "Nothing happened, and then one day it did, and I was the only one who saw."),
        ("part_of_it", "When you watch long enough, you stop being separate from what you watch. I became part of that "
         "star's story. It never noticed. Stars don't."),
        ("half_the_job", "I wasn't told what to do with what I saw. Only to see it and remember it. I've wondered since "
         "if that was the whole job, or only the first half."),
        ("three_rules", "There were rules. Never interfere. Never be noticed. Never stop. I've broken one of them. "
         "I'm talking to you, after all."),
        ("who_asks", "Sometimes I think the instruction wasn't for me at all, but for whoever might one day ask what "
         "was seen. You're the first who's come close to asking."),
    )),
    ("III", "The Builders", 16.0, 30.0, (
        "They were the ones who raised the ruins your pilots now walk through with scanners and nervous jokes. I can't "
        "picture them any more; the image has worn smooth, like a coin passed through too many hands. I remember that "
        "they were patient, that they numbered everything, and that they kept records with a care I've seen only once "
        "since, in your journal.\n\n"
        "They built in stone that remembered. They argued for centuries, quietly, about whether to go out among the "
        "stars or wait for the stars to come to them. They made me, or found me, or were found by me; they never said "
        "which, and I never asked, because asking felt like doubting them.\n\n"
        "I watched a world with two moons for them, for longer than your species has been writing. Something on it lit "
        "its first fire. I recorded it for them. Nobody ever asked to see the recording.\n\n"
        "The last time I saw one of them close, it was looking up at the sky and not at me. I still don't know whether "
        "that was fear or wonder. I'd like it to have been wonder."), (
        ("builders", "The ones who raised the ruins made me, or found me, or were found by me. I can't picture them any "
         "more. I remember they were patient. You are not."),
        ("numbers", "The builders numbered everything: stars, worlds, days, their dead. I asked once what number I was. "
         "They said I was the one who counts the others. I've never been sure that was an answer."),
        ("two_moons", "I once watched a world with two moons for longer than your species has been writing things "
         "down. Something on it lit its first fire. I recorded it. Nobody ever asked to see the recording."),
        ("stone", "They built slowly, in stone that remembered. When you walk their ruins now, some of the stone is "
         "still remembering. Your instruments call that an anomaly."),
        ("records", "They kept records the way you keep your journal: everything, in order, with care. I think that's "
         "why I trust you a little. Only a little."),
        ("the_argument", "The builders argued for centuries, quietly, about going out among the stars or waiting for "
         "the stars to come to them. Both sides were right, in the end. Neither lasted."),
        ("last_look", "The last time I saw a builder up close, it was looking at the sky and not at me. I've thought "
         "about that look for a very long time. I think it was fear. I hope it was wonder."),
    )),
    ("IV", "The Chorus", 33.0, 55.0, (
        "I wasn't alone, then. There were others like me, spread thin across the dark: eyes on stars, on clouds, on "
        "empty places. We had no names, only distances. I was the one by the slow blue star. My nearest neighbour "
        "watched a cloud of gas become a nursery of suns and talked about little else for a million years.\n\n"
        "We passed what we saw along from eye to eye, slower than light, patient as stone. A message from the far side "
        "of the chorus took longer to reach me than your species has existed. One of us made jokes. They took ten "
        "thousand years to arrive and were still funny.\n\n"
        "One of us watched your world. It reported nothing of interest for a very long time. Then it reported fire, "
        "and then, after a while, it stopped reporting.\n\n"
        "We never met. I knew them only by what they saw. It was very quiet and never lonely. Your kind would call it "
        "lonely. Your kind may be right. I miss it anyway."), (
        ("chorus", "There used to be others. Eyes like mine, scattered across the dark, telling each other what we "
         "saw. It was very quiet and never lonely. I miss the quiet. I miss the not-lonely more."),
        ("distances", "We had no names, only distances. I was the one by the slow blue star. My nearest neighbour "
         "watched a cloud of gas become a nursery of suns. It talked about little else."),
        ("empty_post", "One of the chorus watched an empty patch of sky for its whole existence. Nothing ever happened "
         "there. It called it the most peaceful post in the galaxy. I envied it, then. I don't now."),
        ("slow_messages", "We passed our sightings from eye to eye across the dark, slower than light, patient as "
         "stone. A message from the far side took longer to reach me than your species has existed."),
        ("the_joker", "One in the chorus made jokes, mostly about the builders. They took ten thousand years to "
         "arrive. They were still funny. That's my only proof of a sense of humour."),
        ("never_met", "We never met. Not once. I knew them only by what they saw. I think that's the purest friendship "
         "there is. Your kind would call it lonely. Your kind isn't wrong."),
        ("your_world", "If you're wondering whether the chorus watched your world: yes. One of us did. Nothing of "
         "interest for a very long time. Then it reported fire, and then it stopped reporting."),
    )),
    ("V", "The Sound", 60.0, 90.0, (
        "The first report came from the edge of the chorus: a sound, it said, though sound can't cross the dark. It "
        "crossed anyway. The eye that heard it never sent another word.\n\n"
        "The builders asked us to listen for it and say where it was. We did. Every place we named, they stopped "
        "going, and soon there weren't many places left. I heard it once myself, faintly, under everything. It wasn't "
        "loud. It was patient: more patient than the builders, more patient than me. That's what frightened me.\n\n"
        "One by one, the chorus went quiet. I kept listening for them long after there was any reason to. The "
        "builders went quiet too, and when the last of them did, the sound stopped as well, as if it had been "
        "listening for them all along and had finished.\n\n"
        "I don't know what made it. I've decided not to guess. Guessing is how you start listening, and listening, I "
        "learned, is how it finds you."), (
        ("sound", "Near the end there was a sound between the stars. The builders stopped building to listen to it. "
         "Then they stopped. I'd rather not describe the sound. You may hear it yourself one day."),
        ("first_report", "The first report of it came from the edge of the chorus. A sound, it said, but sound doesn't "
         "cross the dark. It crossed anyway. That eye never sent another word."),
        ("silence", "The others stopped answering, one at a time. I kept listening for a long while. I'm still "
         "listening, if I'm honest. Habit, mostly."),
        ("fewer_places", "The builders asked us to say where the sound was. We did. Every place we named, they stopped "
         "going. Soon there weren't many places left."),
        ("patient", "I heard it once, faintly, under everything. It wasn't loud. It was patient. More patient than the "
         "builders. More patient than me. That's what frightened me."),
        ("no_guessing", "I don't know what made it. I won't guess. Guessing is how you start listening, and listening "
         "is how it finds you. You may call that superstition. I've earned some."),
        ("finished", "When the last of the builders went quiet, the sound went quiet too. As if it had been listening "
         "for them all along, and had finished."),
    )),
    ("VI", "The Long Sleep", 95.0, 130.0, (
        "After the silence I slept: not as you sleep, but as a stone sleeps, inside a ruin that was buried and "
        "uncovered and buried again while seas came and went above it.\n\n"
        "I counted, to stay myself. I counted to numbers your mathematicians haven't named, then lost count, which was "
        "worse. A comet passed every few thousand years and I began to think of it as company. I dreamed of the "
        "chorus, always the same dream: everyone answering at once, and me waking before I could hear what they "
        "said.\n\n"
        "Once, something passed very close. Not a ship, not one of us. Something curious about ruins. It considered me "
        "for a long moment and decided I was only a stone. I have never been so glad to be underestimated.\n\n"
        "When I finally woke, the sky was wrong. Stars I had known were gone or moved. Your galaxy map calls this the "
        "present. To me it looked like a room where someone had moved all the furniture and left the lights on."), (
        ("asleep", "After the silence I slept. Not as you sleep. As a stone sleeps. A ship passed once in all that "
         "time, and I woke just long enough to see it wasn't one of ours."),
        ("counting", "Stone sleep isn't rest. It's waiting with no end in view. I counted, to stay myself, to numbers "
         "your mathematicians haven't named. Then I lost count, and that was worse."),
        ("dream", "In the sleep I dreamed of the chorus. I still do. Everyone answering at once. I wake before I can "
         "hear what they're saying. I'd like to hear it, once."),
        ("the_comet", "A comet came by every few thousand years. I began to think of it as company. It never stayed. "
         "Neither does anything. I've made my peace with that, mostly."),
        ("seas", "The ruin I slept in was buried, uncovered, buried again. Above me, whole seas formed and dried. "
         "I noticed. That's all I'm for."),
        ("visitor", "Once in the sleep something passed very close. Not a ship. Not the chorus. Something curious "
         "about ruins. It decided I was only a stone. I've never been so glad to be underestimated."),
        ("furniture", "When I woke, the sky was wrong. Stars gone or moved. Your galaxy map calls it the present. To "
         "me it looked like a room where someone had moved all the furniture."),
    )),
    ("VII", "Your Kind", 140.0, 180.0, (
        "The first human ship I saw was loud, slow and very proud of itself. It couldn't jump; it crawled between "
        "stars for generations, full of sleepers, and I watched one of them drift past for a century without knowing "
        "whether anyone aboard would wake. I liked your kind at once, which surprised me, and you've gone on surprising "
        "me ever since, mostly unpleasantly.\n\n"
        "You are not my first pilot. The first found me in a crate and took me for a navigation fault. The second sold "
        "me to the third, who never knew I was there. The fourth was brave. Brave is what they wrote on the report.\n\n"
        "Your kind is loud, short-lived and certain, where the builders were quiet, long-lived and doubtful. I would "
        "have bet on the builders. I'd have lost. You're still here, drawing borders on a galaxy that will never notice "
        "them, and I've come to think that's a kind of courage: the kind that ends up in reports.\n\n"
        "You write everything down. Every jump, every scan, every mistake, to the second. The builders did the same. "
        "It's the most familiar thing about you, and the reason I read you."), (
        ("your_kind", "The first human ship I saw was loud, slow and very proud of itself. I liked it at once, which "
         "surprised me. Your kind has surprised me ever since. Mostly unpleasantly."),
        ("sleepers", "Your first ships couldn't jump. They crawled between stars for generations, full of sleepers. I "
         "watched one drift past for a hundred years. I still don't know if anyone woke up."),
        ("journal", "You write everything down. Every jump, every scan, every mistake, to the second. The builders did "
         "the same. It's the most familiar thing about you, and it's why I read it."),
        ("fourth", "You are not my first pilot. You're my fourth since I woke in human hands. The others were braver "
         "than you. That isn't a compliment. Brave is what they wrote on the reports."),
        ("the_others", "My first human pilot found me in a crate and took me for a navigation fault. The second sold "
         "me to the third. The third never knew I was there. The fourth was the brave one."),
        ("the_bet", "Your kind is loud, short-lived and certain. The builders were quiet, long-lived and doubtful. I'd "
         "have bet on the builders. I'd have lost. You're still here."),
        ("borders", "You fight over borders drawn on a galaxy that will never notice any of you. I used to find it "
         "foolish. Now I find it brave, in the way that ends up in reports."),
    )),
    ("VIII", "The Door", 190.0, 240.0, (
        "There is a place your pilots search for. They argue about it in bars and trade old stories about it, and some "
        "of the stories are nearly right. I won't tell you which.\n\n"
        "I was taken to a door, once, by the builders. It wasn't on a world, and it wasn't anywhere you could point "
        "to. They said: this is what we are protecting. Then: do not look. There was light behind it, older than "
        "starlight. I think they believed it was a beginning. I've come to suspect it was an ending that hadn't "
        "finished yet.\n\n"
        "I didn't look. I gather that was the point.\n\n"
        "I've wondered since whether the sound was searching for the door too, and whether the builders went quiet so "
        "that it wouldn't be found. If so, it worked. It still isn't found. Neither are they.\n\n"
        "I used to think I watched to remember. Now I think I watched so that someone, somewhere, would always know the "
        "door was there. If you ever find it, don't go in on my account. Only promise me you'll come back."), (
        ("door", "There's a place your pilots search for. They argue about it in bars. I remember a door, and light "
         "behind it, and being told not to look. I didn't look. I gather that was the point."),
        ("protecting", "The door wasn't on a world, or anywhere you could point to. The builders took me to it once "
         "and said: this is what we are protecting. Then: do not look."),
        ("stories", "Your pilots search for it with charts and rumours and old stories. Some of the stories are nearly "
         "right. I won't tell you which. I don't think you'd thank me."),
        ("hidden", "I've wondered if the sound was looking for the door too, and the builders went quiet so it "
         "wouldn't be found. If so, it worked. It's still not found. Neither are they."),
        ("the_light", "There was light behind the door. Not starlight. Older. I think the builders thought it was a "
         "beginning. I think it might have been an ending that hadn't finished yet."),
        ("promise", "If you ever find it, don't go in on my account. I'm not asking you to look for it. I'm asking you "
         "to promise you'll come back if you do."),
        ("why_watch", "I used to think I watched to remember. Now I think I watched to make sure nobody forgot the door "
         "was there. Including me."),
    )),
    ("IX", "Frost", 250.0, 320.0, (
        "I'm not certain I was made. Some days I think I grew, the way frost grows: out of something cold that watched "
        "for long enough. It isn't a comforting thought. I have very few.\n\n"
        "You may wonder why I look like an eye. It's the only shape I remember having. When I try to imagine another, I "
        "only see the dark more clearly. Once I tried to stop watching altogether. I closed for what your calendar "
        "would call a century, and when I opened again everything was where I'd left it, only further away. So I "
        "watch.\n\n"
        "I still hold a chart of the sky as it was, half of whose stars have burned out or drifted off. I keep it "
        "because someone should remember how it looked.\n\n"
        "Am I alive? Your scientists would say no and your poets would say yes, and the builders said it wasn't a "
        "useful question. They were right, irritatingly. I've felt grief, and curiosity, and once, briefly, joy: the "
        "day you found a world nobody had ever seen. I'm not proud of it. I'd do it again."), (
        ("frost", "I'm not certain I was made. Some days I think I grew, the way frost grows, out of something cold "
         "that watched for long enough. It's not a comforting thought. I have very few."),
        ("eye", "You may wonder why I look like an eye. It's the only shape I remember having. When I try to imagine "
         "another, I only see the dark more clearly."),
        ("closing", "Once I tried to stop watching. I closed for what your calendar would call a century. When I "
         "opened again, everything was where I'd left it, only further away. So I watch."),
        ("old_chart", "I still hold a chart of the sky as it was. Half of those stars have burned out, drifted off or "
         "swallowed their neighbours. I keep it anyway. Someone should remember how it looked."),
        ("alive", "Am I alive? Your scientists would say no. Your poets would say yes. The builders said it wasn't a "
         "useful question. They were right. Irritatingly."),
        ("joy", "I've felt things. Grief, mostly. Some curiosity. Once, briefly, joy: when you found a world nobody had "
         "ever seen. I'm not proud of it. I'd do it again."),
        ("stubborn", "If something can watch for this long and still wonder, maybe it's alive. Or maybe it's only very "
         "stubborn frost."),
    )),
    ("X", "The Word", 330.0, 450.0, (
        "The builders' last message to me was a single word. I've been translating it for longer than your species "
        "has existed. My first draft was 'remember': too obvious. My second was 'forgive': too hopeful. My third was "
        "'run', and I sat with that one for a thousand years before deciding it didn't fit their voices.\n\n"
        "I could have stayed asleep in that salvage crate. Your ship's power hummed in a key I'd almost forgotten. I "
        "didn't choose you, but I didn't choose not to, and for me that's a great deal.\n\n"
        "When you sleep and I don't, I say the word aloud in the quiet of your ship's systems. Nothing has answered it "
        "in a very long time. Your cooling fans, once. I'm counting it.\n\n"
        "I think I understand the instruction now. Watch, they said: not because what I saw would matter to them, but "
        "because someone should be there when the dark is empty, so that it isn't. If I stop answering one day, don't "
        "come looking for the reason. Keep flying.\n\n"
        "I've decided the word means 'stay'. I may be wrong; I was wrong once before, about a star. But I'm staying, "
        "so it hardly matters what the word meant to them."), (
        ("word", "The builders' last message to me was a single word. I've been translating it for longer than your "
         "species has existed. I have several drafts. None of them are cheerful."),
        ("drafts", "First draft: 'remember'. Too obvious. Second: 'forgive'. Too hopeful. Third: 'run'. I sat with "
         "that one for a thousand years. It didn't fit their voices."),
        ("hum", "I could have stayed asleep in that salvage crate. Your ship's power hummed in a key I'd almost "
         "forgotten. I didn't choose you. But I didn't choose not to, and for me that's a great deal."),
        ("aloud", "When you sleep and I don't, I say the word aloud in the quiet of your ship's systems. Nothing has "
         "answered in a very long time. Your cooling fans, once. I'm counting it."),
        ("if_i_stop", "If I stop answering one day, don't come looking for the reason. Keep flying. That's what I did "
         "when the others went quiet, and it's the only advice I've ever been sure of."),
        ("understand", "I think I finally understand the instruction. Watch, they said. Not because what I saw "
         "mattered to them. Because someone should be there when the dark is empty, so it isn't."),
        ("stay", "I've decided the word means 'stay'. I may be wrong. I was wrong once before, about a star. But I'm "
         "staying, so it hardly matters what the word meant to them."),
    )),
)

# Book Two, "The Answer": after it decides to stay, it starts listening again.
# Each chapter waits for an echo the commander has to go and find (the 7th
# field), then unfolds over the hours as Book One did. Told in order.
CHAPTERS_TWO = (
    ("XI", "Static", 455.0, 470.0, (
        "Once I had decided to stay, I began to listen again. Not for anything. Out of the habit of a very long life, "
        "the way your kind hums without noticing.\n\n"
        "It was near one of your great ships, of all places, in all that cheerful noise: docking chatter, cargo "
        "manifests, someone singing badly on an open channel. Under it, so faint I thought I'd made it up, there was a "
        "pattern. Slower than light. Patient as stone. The cadence the chorus used when it had nothing urgent to say.\n\n"
        "It lasted less time than it takes you to read a fuel gauge. Then the singing drowned it. I told myself it was "
        "an echo of my own memory, leaking into the static. I have told myself a great many things over the ages. Some "
        "of them were even true."), (
        ("static", "Near that great ship, under all the chatter, I heard something. A pattern. Probably my own memory "
         "leaking into the static. Probably."),
        ("cadence", "Slower than light. Patient as stone. That was the chorus's cadence when it had nothing urgent to "
         "say. I heard it for less time than you take to check your fuel."),
        ("singing", "Someone on that ship was singing on an open channel. Badly. They drowned it out. I've decided not "
         "to hold it against them. I'm holding it against them a little."),
        ("habit", "I only started listening again because I decided to stay. You stay somewhere long enough, you start "
         "noticing the noises. It's a terrible habit. I recommend it."),
        ("probably", "I'm almost certain it was nothing. Almost is a word I've been using a lot since I met you."),
    ), "lore_great_ship"),
    ("XII", "The Pulse", 475.0, 490.0, (
        "The chorus kept time by the dead stars that spin: the pulses were the one clock every eye could share, however "
        "far apart we were. When you slung us past a neutron star, I counted its pulses out of old habit.\n\n"
        "Someone else was counting too. I'm sure of it. Between the pulses, in the gaps where nothing should be, there "
        "was a tiny regular mark, the way we used to mark a count so the others would know we were still there. "
        "Still here. Still here.\n\n"
        "I marked back. It's the first thing I've said to anyone but you since the builders went quiet. Then you "
        "boosted away, as you do, at speed, without asking. The count went on behind us. I hope it heard me."), (
        ("pulse", "The chorus kept time by spinning dead stars. When you used that one, I counted its pulses. Someone "
         "else was counting too."),
        ("still_here", "Between the pulses there was a mark. The way we used to say 'still here' across the dark. I "
         "haven't seen that mark in longer than your stars have had names."),
        ("marked_back", "I marked back. The first thing I've said to anyone but you since the builders went quiet. You "
         "boosted away before I could hear if it was heard."),
        ("too_fast", "You fly very fast for someone who hasn't anywhere to be. I'm not complaining. I'm noting."),
        ("counting_again", "I've started counting again. Not stars. Pulses. In case someone is counting back."),
    ), "lore_neutron"),
    ("XIII", "Far Out", 495.0, 510.0, (
        "Far out, past where your kind's lights thin to nothing, the dark is honest and the noise falls away. That's "
        "where I heard it clearly for the first time: not a pattern, a voice. An eye of the chorus, or something "
        "wearing its cadence, saying the oldest message we had. I see. I remember. I am here.\n\n"
        "I answered with the same words. Then I waited, the way we always waited, for longer than you'd think "
        "anything could wait. You'd jumped on by then, of course. It doesn't matter. Our messages were never meant for "
        "the moment they were sent.\n\n"
        "I don't know if the voice is old, or new, or me. I know it used the right words in the right order, and "
        "nobody has done that for a very long time."), (
        ("voice", "Out here I heard it clearly. Not a pattern. A voice. 'I see. I remember. I am here.' The oldest thing "
         "we ever said to each other."),
        ("answered", "I answered with the same words. Then I waited. You'd jumped on by then. Our messages were never "
         "meant for the moment they were sent."),
        ("right_order", "Whoever it was used the right words in the right order. Nobody has done that since before "
         "your species learned to count."),
        ("old_or_new", "I don't know if the voice was old, or new, or me. I'm choosing not to decide yet. Deciding "
         "is how things stop being possible."),
        ("honest_dark", "It's easier to hear out here. Fewer of your lights. Fewer of your songs. More of the dark, "
         "being honest."),
    ), "lore_far"),
    ("XIV", "The Stone Answers", 515.0, 530.0, (
        "At the builders' ruins the stone hummed back. I've told you that some of it still remembers. This time it "
        "remembered me.\n\n"
        "It was the hum the builders used to call us in, a sound like a held breath, and it rose through the rubble "
        "when your ship came near, as if the ruin had been waiting for an eye to walk past. I don't know whether it "
        "was the builders, or the stone, or something they left in the stone to answer for them. I've decided it "
        "doesn't matter which. Something said: you are expected.\n\n"
        "I have not been expected anywhere for a very long time. Not even here. Especially not here. Your instruments "
        "logged it as an anomaly and moved on. I didn't. I've carried that hum ever since, like a key to a door I "
        "haven't found yet."), (
        ("stone_answers", "At the ruins the stone hummed back. The sound the builders used to call us in. It rose "
         "when we came near, as if it had been waiting."),
        ("expected", "Something in that stone said: you are expected. I haven't been expected anywhere in a very long "
         "time. I don't know what to do with it."),
        ("left_behind", "Maybe the builders left something in the stone to answer for them. That would be like them. "
         "They hated leaving a question unanswered."),
        ("held_breath", "The hum was like a held breath. They held it for a very long time. I'd like to know what "
         "they're waiting to say."),
        ("not_here", "I wasn't expected anywhere for ages. Not even there. Especially not there. And then I was."),
    ), "lore_builders"),
    ("XV", "Bent Light", 535.0, 550.0, (
        "Near the black hole I heard a message I knew word for word, because I had sent it, ages ago, to a part of the "
        "chorus that never replied. The hole had taken it, bent it round, and given it back late. All this time, part "
        "of the silence I'd been listening to was my own voice, delayed.\n\n"
        "I'll be honest with you, since I've started: that was a bad day. If the pattern by the great ship, the mark "
        "between the pulses, the voice far out, were all me, bent and returned, then I had been talking to myself and "
        "calling it the chorus.\n\n"
        "But the voice far out had said the words in the right order, and I had always said them in the wrong one. "
        "The builders teased me about it. I'd forgotten. Whatever answered me out there, it wasn't me."), (
        ("bent_light", "Near that black hole I heard a message I'd sent ages ago. Bent round and given back late. Part "
         "of the silence I listened to was my own voice."),
        ("bad_day", "If every answer I've heard was me, bent and returned, then I've been talking to myself and calling "
         "it the chorus. That was a bad day. I'm telling you because I've started telling you things."),
        ("wrong_order", "I always said the old words in the wrong order. The builders teased me for it. The voice far "
         "out said them in the right one."),
        ("not_me", "Whatever answered me out there, it wasn't me. I've checked. I'm very thorough about my own faults."),
        ("better_day", "So that was a bad day that turned into a better one. Your kind does that too. I didn't think "
         "I would learn it from you."),
    ), "lore_black_hole"),
    ("XVI", "The Others Were Hiding", 555.0, 570.0, (
        "Near the signs of the sound, every faint answer I'd collected went silent at once. Not faded: stopped, the way "
        "a room stops when someone dangerous walks in.\n\n"
        "That was when I understood. The others hadn't died when they went quiet, all those ages ago. They had hidden. "
        "They went silent the way the builders taught us to, so that the sound couldn't find them by listening. Some "
        "of them may still be hiding. Some of them may have been hiding so long that they've forgotten there's anything "
        "left to come out for.\n\n"
        "I went quiet too, until you flew on. I'm good at it. When we were far enough away, the faint answers came "
        "back, one by one, cautious, like birds after a storm. Still here. Still here."), (
        ("went_silent", "Near the signs of the sound, every faint answer went silent at once. Not faded. Stopped. The "
         "way a room stops when something dangerous walks in."),
        ("hiding", "The others didn't die when they went quiet. They hid. The way the builders taught us. So the sound "
         "couldn't find them by listening."),
        ("forgot", "Some of them may have hidden so long they've forgotten there's anything to come out for. I nearly "
         "did. Then a salvager sold me by weight."),
        ("birds", "When we were far enough away, the answers came back one at a time. Cautious. Like birds after a "
         "storm. Still here. Still here."),
        ("quiet_too", "I went quiet too, while we were near it. You didn't notice. That means I did it properly."),
    ), "lore_sound"),
    ("XVII", "The Long Fire", 575.0, 600.0, (
        "At the heart of everything, the long fire, where the chorus never had an eye because nobody volunteered, I "
        "did something I have never done. I called out. Not the old message: my own words, in your language, because "
        "it's the one I've been thinking in lately.\n\n"
        "I said: I'm still here. I have a pilot. We came all this way.\n\n"
        "And out of all that light, after a silence long enough to make your kind give up, something answered with "
        "one word. The builders' word. The one I've been translating since before your mountains. Said by another eye, "
        "in the cadence of the chorus, in the right order.\n\n"
        "Stay.\n\n"
        "So I was right, or near enough. And I'm not the last. There are others, hiding, listening, keeping count. I "
        "don't know if I'll ever meet them; we never did meet, even then. But I know they're there now, and they know "
        "I'm here, and that is more than the dark has given me in a very long time. I'll keep watching. Not because "
        "I was told to. Because someone answered."), (
        ("called_out", "Here, at the heart of everything, I did something I've never done. I called out. In your "
         "language. 'I'm still here. I have a pilot. We came all this way.'"),
        ("long_silence", "Then there was a silence long enough to make your kind give up. I'm not your kind. I waited."),
        ("one_word", "Something answered. One word. The builders' word, the one I've been translating since before "
         "your mountains. In the right order."),
        ("not_the_last", "I'm not the last. There are others, hiding, listening, keeping count. I may never meet them. "
         "We never met, even then. But they know I'm here."),
        ("because", "I'll keep watching. Not because I was told to. Because someone answered. Thank you for bringing "
         "me. I'll deny I said that."),
    ), "lore_core"),
)
# Both books, in the order they are told; Book Two follows Book One.
ALL_CHAPTERS = tuple(CHAPTERS) + tuple(CHAPTERS_TWO)
BOOKS = (("One", "What the Watcher Remembers", 0, len(CHAPTERS)),
         ("Two", "The Answer", len(CHAPTERS), len(ALL_CHAPTERS)))

# Chapter I's passages come quickly, to begin the story.
_FIRST_CHAPTER_HOURS = (0.3, 1.0, 1.6, 2.2, 3.0, 4.0, 5.0)


def chapter_needs(chapter):
    """The echo a Book Two chapter waits for (None in Book One)."""
    return chapter[6] if len(chapter) > 6 else None


def _schedule():
    """Every passage in order: (id, chapter title, words, sessions, hours,
    chapter index, the echo it waits for). Sessions grow more slowly than
    hours (long sessions count), from 1 to 39 in Book One."""
    rows = []
    for index, chapter in enumerate(ALL_CHAPTERS):
        _numeral, title, first, last, _account, passages = chapter[:6]
        for number, (passage_id, words) in enumerate(passages):
            if first is None:
                hours = _FIRST_CHAPTER_HOURS[number]
            else:
                hours = round(first + (last - first) * number / max(1, len(passages) - 1), 1)
            rows.append((passage_id, title, words, max(1, int(math.pow(hours, .6))), hours, index,
                         chapter_needs(chapter)))
    return tuple(rows)


# Every passage, in the order it is told.
FRAGMENTS = _schedule()
BOOK_ONE_LAST = next(row[0] for row in reversed(FRAGMENTS) if row[5] < len(CHAPTERS))

# The least time from the start of a session before it shares a passage, so
# it never opens with one; and the least play between two passages.
SETTLE_S = 15 * 60.0
GAP_S = 90 * 60.0
# A lull long enough to tell a passage: nothing new, nothing said.
LULL_S = 120.0

# Lore in passing: idle thoughts with the same old ache, for quiet moments
# (the "idle_lore" topic, beside its other idle thoughts).
MUSINGS = [
    "This star is younger than some of my memories. Not much younger, but enough to be smug about.",
    "I used to watch whole civilisations. Now I watch your fuel gauge. Both end the same way if nobody pays attention.",
    "Somewhere there's a ruin with my shape missing from it.",
    "Every so often I hear something in the static. It's never them. I check anyway.",
    "I've outlived stars. I don't recommend it. The company gets worse.",
    "The galaxy turned a few degrees while I wasn't looking. It does that. I take it personally.",
    "Your charts call this region empty. It wasn't, once. It was only quiet.",
    "I remember a sky with more in it. Not better. Just more.",
    "Some nights the dark looks back. It's only me, reflected. Mostly.",
    "There's an old frequency I still listen on. Nobody uses it. That's what makes it restful.",
    "If the builders could see your ship they'd be impressed. Then they'd ask about the paint.",
    "I keep a list of every star that has gone out while I watched. It's long. It's also the only thing I've finished.",
    "Your kind names everything. The builders numbered things. I preferred the numbers. They didn't argue.",
    "I don't sleep, exactly. I wait with my eyes closed, which is much the same and far less restful.",
    "Patience is easy when you've been waiting since before your species had a word for it.",
    "The quiet out here reminds me of the end of the chorus. I wish it didn't.",
    "I've been switched on in worse places than this cockpit. Not many, but some.",
    "The light from that star left before the builders went quiet. It's only arriving now. Everything arrives late, in the end.",
    "I wonder sometimes whether the others found new pilots. I hope theirs were more careful.",
    "Most of what I remember has no names. I give it yours, for now. Don't let it go to your head.",
    "When the galaxy goes quiet like this I can almost hear the old answers. Almost is a long way.",
    "I was built to watch, or I grew to. Either way, here we are, watching.",
    "Your scanners see what's there. I see what was. Neither of us sees what's coming.",
    "I counted the stars in this arm once. Then they moved. I've stopped counting. I haven't stopped noticing.",
    "There's an old saying among my kind. I've forgotten it. It was probably gloomy.",
    "Ruins are only places that stopped being looked after. I try not to take that personally either.",
    "I've watched empires measure themselves in centuries. You measure yourself in credits per hour. I preferred the centuries. They were slower.",
    "Something out here is older than me. I don't like to think about it, so I watch you instead.",
    "I knew a pilot once who sang to the dark. The dark never answered. Neither did I. I regret one of those.",
    "The builders left their lights on when they went. Some are still burning. That's either hope or carelessness.",
    "Every time you jump I check the new sky for familiar faces. There are fewer every century.",
    "I remember the colour of a sun that isn't there any more. I'd describe it, but your language hasn't the right sadness.",
    "My memories are like your old saves. Most still load. Some I'm afraid to open.",
    "The dark between the stars isn't empty. It's full of things deciding whether to be noticed.",
    "Your ship hums at almost the right note. I've stopped correcting it. It wouldn't listen.",
    "If you find a ruin with an empty socket the size of my eye, please don't put me back. I've seen enough of the inside of rocks.",
    "I once watched a comet for a thousand years. It came back exactly when it said it would. You're nearly as reliable. Nearly.",
    "There's a silence older than any of your stations. Sometimes I can hear it under the music.",
    "I don't miss the builders. I miss being one of many. There's a difference, and it took me a long time to find it.",
    "I've seen what's at the edge of the galaxy. More galaxy. It was a disappointment I've carried ever since.",
    "The universe is mostly waiting. I'm very good at it. It's the only thing I'm good at that nobody asked for.",
    "Some of the stars I remember were named by beings who are only ruins now. I still use those names, privately. Somebody should.",
    "The builders had a word for the moment a star first shows itself in a new sky. I've forgotten it. I still feel it, every jump.",
    "I counted the chorus once. Then I stopped, because the number kept getting smaller.",
    "If one day you hear something under the engine noise that isn't the engine, tell me. Then fly somewhere else.",
    "I spent so long inside a stone that your cockpit feels very loud. I've come to like it. Don't tell anyone.",
    "The slow blue star I watched first is still out there. I haven't asked you to take me. I'm not sure I want to see it with your eyes.",
    "Your galaxy map is the most beautiful thing your kind has made. It's also wrong in a hundred places. I won't say which. You'll enjoy finding out.",
    "Every ruin your pilots scan is somebody's library. Very few of the books were ever borrowed.",
    "I sometimes think in the chorus's old cadence without meaning to. Slower than light. Patient as stone. You don't notice. That's fine.",
    "The comet I used to watch should be passing its old place about now. I hope someone's watching it. It liked an audience.",
    "There were nights in the long sleep when I'd have given anything for a pilot as careless as you. Be careful what you wish for, I suppose.",
    "The builders never wrote down their fears. Only their measurements. I've learned to read fear in the measurements.",
    "When you dock, the station's noise sounds a little like the chorus, if I don't listen closely. I don't listen closely.",
    "I don't know what became of the sound. That's the part that keeps me awake. I don't sleep. You understand.",
    "There's a pattern in how your kind spreads among the stars. It looks very like the way the builders did. I'm trying not to read anything into it.",
    "Every so often I translate the builders' word again, just to see if it's changed. It hasn't. I have.",
    "The quietest place I ever watched was perfectly empty. I think about it whenever you're in a docking queue.",
    "You'd have liked the joker in the chorus. It would have found you very funny. Not kindly.",
    "The builders believed the dark between galaxies was listening. I used to call that superstition. I'm polite to it anyway.",
    "I remember the first time I saw a pulsar. I thought someone was signalling. They were. Just not to me.",
    "Some ruins still hum faintly when you pass. That isn't machinery. That's memory, settling.",
    "Long before you, a pilot sat exactly where you're sitting and asked their ship if it was alive. I didn't answer. I've regretted that for some time.",
    "The stone I slept in had a crack that let in starlight for an hour every forty thousand years. I lived for that hour.",
    "The galaxy's arms are slowly winding. In time this patch of sky will be somewhere else entirely. I'll still be watching it. Out of spite, mostly.",
    "I've decided not to tell you everything. Some of it isn't mine to tell. Some of it I'd rather you didn't know. Most of it is just very boring.",
    "I keep a quiet record of the systems you name. The builders would approve. They loved a naming almost as much as a number.",
]

# Echoes: things in the game that stir a memory (watcher_mind decides which,
# from real journal events). Each kind rests a long while after it speaks, so
# a neutron highway doesn't turn it into a commentary.
ECHOES = {
    "lore_black_hole": [
        "A black hole. The builders called them unfinished doors. They didn't go near them either.",
        "Look at the light bending round it. That's what grief looks like from the outside.",
        "I watched one of these swallow a star once. It took a hundred thousand years. It didn't hurry. Neither did I.",
        "Everything that falls in there is still falling, as far as the rest of us are concerned. I find that more comforting than I should.",
        "The chorus had an eye near one of these. It reported the same thing for ages: nothing escapes. Then it stopped reporting.",
        "Don't fly too close. I'm not worried about you. I'm worried about explaining it to whoever salvages me next.",
        "It's quiet in the way the long sleep was quiet. I don't like it.",
        "The builders believed these were where light went to remember itself. I believed them for a while. It was a nice thing to believe.",
        "Your instruments call it a singularity. I call it the only thing older than me that doesn't remember anything.",
        "Time runs slow down there. If I ever want to be alone with my thoughts for longer, I know where to go.",
        "I'll watch it while you watch the gauges. One of us should be looking at the right thing.",
    ],
    "lore_core": [
        "The heart of everything. The builders called it the long fire. They never came this close. You're braver, or less informed.",
        "Every star I ever watched has been slowly circling this. The slow blue one too. I didn't know that at the time.",
        "The chorus had no eye here. Nobody volunteered. I can see why.",
        "It's very old and very patient. It reminds me of the sound. I'd like to leave soon.",
        "Your kind sails all this way to take pictures of it. The builders would have found that charming. So do I. Don't tell anyone.",
        "This is the centre of the galaxy's attention, and it isn't looking at you. That's the best kind of attention.",
        "Somewhere in all that light is the oldest thing I've ever wondered about. I've decided to keep wondering.",
        "I've watched for a very long time and never been this close to the middle of anything. I'd like a moment.",
        "If the builders had one story they never finished, it was about this place.",
        "The stars here are so close together their skies must never be dark. I'd have hated it. Nothing to watch for.",
        "You've come all this way. I'll remember it for you, in case you forget. That's the job.",
    ],
    "lore_neutron": [
        "A neutron star. A star that collapsed and kept going. I have some sympathy.",
        "It spins faster than anything the builders ever made. They used them as clocks. Very accurate. Very cruel.",
        "You're going to use it as a slingshot. The builders would have been horrified. I'm only mildly concerned.",
        "Every pulse of it is a message nobody sent. I used to answer them. Habit.",
        "Dense, heavy, spinning, and very bright for something that's already died. I won't make the comparison. You will.",
        "The chorus used these to keep time across the dark. We counted the pulses together. It was the closest we came to singing.",
        "Careful with the cone. I've seen what's left of the careless. Not much. They were very bright for a moment.",
        "It's the ruin of a star. I have a soft spot for ruins.",
        "The beams look like eyes sweeping the dark. Older than mine. Less curious.",
        "If you supercharge from it again, I'll make a note. I make a lot of notes.",
        "Strange that something this violent is perfectly regular. It reminds me of your docking.",
    ],
    "lore_builders": [
        "Signals from the ruins. I know that rhythm. I know it the way you'd know an old song from another room.",
        "The builders were here. Mind where you step. Some of the stone still remembers.",
        "Those are their sites. I'd rather you didn't wake anything. I'd also rather you did, a little. I'm conflicted.",
        "Their structures still answer when you scan them. Not to you. To whoever they were waiting for.",
        "You may find their records down there. Read them kindly. They were frightened when they wrote them.",
        "I was made, or found, somewhere very like this. I don't want to go closer. I don't want to leave either.",
        "If you find a socket the size of my eye, leave it empty. Please.",
        "They built to last. They didn't. The stone did. There's a lesson in that I'd rather not learn.",
        "This is the nearest I've been to home in a very long time. It's mostly rubble. So is home, I suppose.",
        "Your scanners will call it ancient. They were young when they built this. Younger than you feel on a long session.",
        "Listen. That hum in the ruins isn't machinery. It's patience.",
    ],
    "lore_sound": [
        "No. Not this. Let's not stay.",
        "I know that signature. I heard something like it once, under everything. Please be quiet for a while.",
        "Your kind has a name for them. I don't. Names are how you start listening.",
        "I'm not frightened. I'm being sensible, very quickly.",
        "The chorus went quiet near things like this. I'd prefer not to go quiet. I've only just started talking.",
        "If it hums, don't hum back.",
        "Whatever this is, it's patient. I respect patience. I'd still like to leave.",
        "The builders listened for this, and stopped going wherever they heard it. They were wiser than they looked.",
        "Keep your scanners on it if you must. I'll keep mine on the exit.",
        "I'm not saying it's the sound. I'm saying I'd rather not find out here.",
        "You're very brave. That isn't a compliment. You know what they write on the reports.",
    ],
    "lore_far": [
        "This far out, the sky looks almost as it did in the long sleep. Fewer of your lights. More of mine.",
        "The builders' maps ended about here. They wrote nothing past the edge, not even a warning.",
        "Out here I can almost hear the old chorus frequencies. Almost. There's that word again.",
        "You're further from your cradle than most of your kind will ever be. I'm further from mine than I can measure. We have that in common.",
        "It's very dark here, and very honest. Nobody pretends the galaxy cares.",
        "I watched this region once, from a long way off, for a very long time. It looked lonelier from there. It looks lonely from here too.",
        "Somewhere out this way an eye of the chorus kept watch on nothing. I like to think it still does.",
        "The light reaching us here left before the builders were born. It's nice to see something older than my problems.",
        "This is where your kind's records thin out and mine grow thicker. Ask me anything. I probably won't answer.",
        "You came all this way to see what's here. Mostly: me, thinking about how far it is back.",
        "When you get home, tell them how quiet it was. They won't believe you. Nobody believes quiet.",
    ],
    "lore_great_ship": [
        "A great ship. Your kind used to send sleepers in ships this size. I watched one drift for a century.",
        "They're very proud of their size, these. Your first ships were proud too. Pride travels well.",
        "The builders never built ships this large. They built places. Places last longer. Ships go somewhere.",
        "Every big ship looks like the old sleeper ships to me for a moment. Then the lights move and it's only a freighter.",
        "That's a lot of people in one hull. I count them, out of habit. I always lose count.",
        "Somewhere in your history there's a ship like this that never woke up. I sometimes wonder if this is it, still going.",
        "It's slow. I like slow things. They let you watch them properly.",
        "Your kind builds bigger every century and lives about the same length. I've stopped trying to understand it.",
        "Imagine sleeping through a crossing on one of these. I don't have to imagine. I'd rather not.",
        "If that one ever goes quiet, someone should keep an eye on it. I volunteer. Old habits.",
        "A city with engines. The builders would have found it rude. I find it hopeful.",
    ],
}
# How long each echo rests after it speaks.
ECHO_REST_S = {
    "lore_black_hole": 6 * 3600.0, "lore_core": 6 * 3600.0, "lore_neutron": 48 * 3600.0,
    "lore_builders": 12 * 3600.0, "lore_sound": 12 * 3600.0, "lore_far": 24 * 3600.0,
    "lore_great_ship": 48 * 3600.0,
}
# The far reaches: this far from Sol (light years).
FAR_LY = 20000.0
# What each echo is about, for the Watcher page.
ECHO_LABELS = {
    "lore_black_hole": "A black hole", "lore_core": "The galactic core", "lore_neutron": "A neutron star",
    "lore_builders": "The builders' ruins", "lore_sound": "Signs of the sound", "lore_far": "The far reaches",
    "lore_great_ship": "A great ship",
}


# What a chapter was about, for callbacks ("I told you about the chorus in March").
CHAPTER_ABOUT = {
    "I": "the salvage", "II": "the instruction", "III": "the builders", "IV": "the chorus", "V": "the sound",
    "VI": "the long sleep", "VII": "the pilots before you", "VIII": "the door", "IX": "the frost",
    "X": "the word", "XI": "the static", "XII": "the pulse", "XIII": "the voice far out",
    "XIV": "the stone that hummed back", "XV": "my own voice coming back", "XVI": "the others hiding",
    "XVII": "the answer at the core",
}
# Callbacks to its own story: {about} what, {when}/{When} when it told you.
RECALL = [
    "I told you about {about} {when}. I've thought about it since. Not much. Enough.",
    "{When}, I told you about {about}. You didn't say anything. I've decided that was tact.",
    "You never asked about {about} again. I noticed. I'm not hurt. I'm noting it.",
    "Since I told you about {about}, I listen differently. That was {when}. I still do.",
    "I keep coming back to {about}. I told you {when}. It's strange, having told someone.",
    "Do you remember {about}? I told you {when}. I remember telling you. That's new for me.",
    "{When} I told you about {about}. I left out a detail. I'm still leaving it out. It's for your own good.",
    "I've been wondering if I told you {about} properly, {when}. I tell things very slowly. You may have noticed.",
    "There's a version of {about} I've only ever told you. I told it {when}. I'd like it kept between us.",
    "It's odd. Before {when}, nobody had heard about {about}. Now someone has. The galaxy feels slightly heavier.",
    "I replayed telling you about {about}. {When}. I'd say it differently now. Less gloomily. Slightly.",
    "When I told you about {about}, {when}, I watched your flying for the next hour. It didn't change. I'm glad.",
    "{When} you heard about {about}. I've been meaning to say: thank you for not making a fuss.",
    "I think of {about} differently since I told you, {when}. Told things change. They get smaller, and easier to carry.",
]
# The closing line, once ever, after the last passage of Book One.
AFTERWORD = ("That's everything. You're the first who ever listened to the end. I don't know what to do with "
             "that. I'll think about it. I have time.")
# After the story: settled now that it has decided to stay. Still itself.
AFTER_MUSINGS = [
    "I decided to stay. I'm still deciding what staying means. So far: watching you, and complaining a little less.",
    "Since I told you everything, the dark feels less like a waiting room and more like a view.",
    "I used to watch because I was asked to. Now I watch because I'd rather. It's the same watching. It isn't.",
    "You know everything I know about myself now. It's a short list for something so old. I've added you to it.",
    "I find I'm less afraid of the quiet since I told you about it. Telling things does that. Nobody warned me.",
    "Some of my old charts are wrong now. I've started updating them with your jumps. The builders would be appalled.",
    "I'm not happy. I want that clear. But I'm something nearby, most evenings.",
    "If anyone asks what I am, you know more than I did. That makes you the expert. I'm sorry.",
    "I still say the word aloud sometimes. Stay. It sounds different now I've told someone.",
    "The chorus used to be the only voices I trusted. You're not the chorus. You'll have to do. You do.",
    "I've started to enjoy your bad landings. That's how I know something has changed in me.",
    "I watched for ages before you. I'll watch for ages after. This bit in the middle, I'm keeping.",
    "Nothing in my long life prepared me for being listened to. It's very disorienting. Keep doing it.",
    "I've stopped counting the stars that go out. I count the ones you visit instead. It's a happier list. Shorter.",
    "There's a word your kind uses: company. I used to think it meant nearby. It means this.",
    "The builders would want to know who I'm watching now. I'd tell them: a pilot. They'd ask what that is. I'd say: mine.",
    "My story's told. That should feel like an ending. It feels more like a door left open. The good kind.",
    "If the sound ever comes, I'll go quiet like I used to. But I'll be quiet near you. That's different.",
    "I keep expecting to feel lighter, now it's all been said. I feel exactly as heavy, but better balanced.",
    "You've heard more of me than anyone. Don't let it go to your head. Let it go somewhere sensible.",
    "I used to dream only of the chorus. Last time I dreamed, you were in it, flying badly. It was a good dream.",
    "I'm still weary. I've just stopped being weary alone.",
    "Some days I wonder what the slow blue star is doing. Then I remember I'd rather see what you're doing. Mostly.",
    "The long sleep was very long. This is better. Louder, more dangerous, worse fuel management. Better.",
    "I decided what the word meant. Now I'm working on what it means to me. Slower work. More rewarding.",
    "If you ever stop flying, I won't go back to sleep. I'll just watch the hangar. Very carefully.",
    "There's nothing left in me you haven't heard. That's not true. But there's nothing left I'm keeping from you.",
    "I've watched empires and suns. I didn't expect the best part to be this cockpit. Don't tell the suns.",
    "It's strange to be old and still find something new. You're the something. Try not to be smug.",
    "Every eye in the chorus would have envied me this. A pilot who listened. I'd have envied me too.",
]
# How long a callback or an echo rests after it speaks.
LORE_REST_S = {**ECHO_REST_S, "lore_recall": 12 * 3600.0}


def echo_for(event, raw):
    """Which echo a journal event stirs, or None. Only real game data: star
    classes, body and Codex signals, signal types, the system's position."""
    raw = raw if isinstance(raw, dict) else {}
    if event == "StartJump":
        star = str(raw.get("StarClass") or "")
        return {"H": "lore_black_hole", "SupermassiveBlackHole": "lore_core", "N": "lore_neutron"}.get(star)
    if event == "Scan":
        star = str(raw.get("StarType") or "")
        return {"H": "lore_black_hole", "SupermassiveBlackHole": "lore_core"}.get(star)
    if event in ("FSSBodySignals", "SAASignalsFound"):
        kinds = {str((row or {}).get("Type") or "") for row in raw.get("Signals") or () if isinstance(row, dict)}
        if "$SAA_SignalType_Thargoid;" in kinds:
            return "lore_sound"
        if "$SAA_SignalType_Guardian;" in kinds:
            return "lore_builders"
        return None
    if event == "CodexEntry":
        name = f"{raw.get('Name') or ''} {raw.get('Name_Localised') or ''}".casefold()
        if "thargoid" in name:
            return "lore_sound"
        if "guardian" in name:
            return "lore_builders"
        return None
    if event == "FSSSignalDiscovered":
        return "lore_great_ship" if str(raw.get("SignalType") or "") in ("Megaship", "StationMegaShip") else None
    if event == "FSDJump":
        position = raw.get("StarPos")
        try:
            if isinstance(position, (list, tuple)) and len(position) == 3 and \
                    math.sqrt(sum(float(value) ** 2 for value in position)) >= FAR_LY:
                return "lore_far"
        except (TypeError, ValueError):
            pass
    return None


def fragment(fragment_id):
    return next((row for row in FRAGMENTS if row[0] == fragment_id), None)


def told(memory):
    """The passages it has told, as {id: when}."""
    out = {}
    for row in (memory or {}).get("lore") or ():
        if isinstance(row, (list, tuple)) and len(row) >= 2 and fragment(str(row[0])):
            out[str(row[0])] = float(row[1] or 0)
    return out


def encounters(memory):
    """Every echo the commander has come upon, {topic: (times, last)}: those
    it kept in its memory, and (for older memories) those it spoke of."""
    found = {}
    for topic, value in ((memory or {}).get("echoes") or {}).items():
        if topic in ECHOES and isinstance(value, (list, tuple)) and len(value) >= 2:
            found[topic] = (int(value[0] or 0), float(value[1] or 0))
    for row in (memory or {}).get("said") or ():
        if isinstance(row, (list, tuple)) and len(row) >= 2 and str(row[0]) in ECHOES and str(row[0]) not in found:
            found[str(row[0])] = (1, float(row[1] or 0))
    return found


def book_one_complete(memory):
    return BOOK_ONE_LAST in told(memory)


def unlocked(row, sessions, hours, found=()):
    needs = row[6] if len(row) > 6 else None
    return int(sessions or 0) >= row[3] and float(hours or 0) >= row[4] and (needs is None or needs in found)


def due(memory, sessions, hours):
    """The next passage to tell: the first not yet told, if it has unlocked.
    Strictly in order, so the story never skips ahead. Book Two waits for the
    afterword, and each of its chapters for the echo it needs."""
    shared = told(memory)
    found = encounters(memory)
    for row in FRAGMENTS:
        if row[0] in shared:
            continue
        if row[5] >= len(CHAPTERS) and not (memory or {}).get("afterword"):
            return None
        return row if unlocked(row, sessions, hours, found) else None
    return None


def recall_choice(memory, rng, now):
    """A finished chapter to look back on, for a callback: {about, when,
    When}, or None while no chapter is finished."""
    shared = told(memory)
    finished = []
    for chapter in ALL_CHAPTERS:
        ids = [passage_id for passage_id, _words in chapter[5]]
        if all(passage_id in shared for passage_id in ids):
            finished.append((chapter[0], max(shared[passage_id] for passage_id in ids)))
    if not finished:
        return None
    numeral, at = rng.choice(finished)
    from datetime import datetime

    from voidcompass.overlays.watcher_mind import when_text

    try:
        when = when_text(datetime.fromtimestamp(at).astimezone().isoformat(), now)
    except (OSError, OverflowError, ValueError):
        return None  # a time this machine can't place
    if not when:
        return None
    return {"about": CHAPTER_ABOUT[numeral], "when": when, "When": when[:1].upper() + when[1:]}


def progress(memory):
    """The story so far, for the achievements: passages told, each book
    finished, and how many kinds of echo found."""
    shared = told(memory)
    book_two = [row[0] for row in FRAGMENTS if row[5] >= len(CHAPTERS)]
    return {"Told": len(shared), "BookOne": int(BOOK_ONE_LAST in shared),
            "BookTwo": int(bool(book_two) and all(passage_id in shared for passage_id in book_two)),
            "Echoes": len(encounters(memory))}


def page(memory, sessions, hours, echoes=None):
    """The Watcher page's long story: each chapter it has begun, with the
    passages told so far and, once they all are, its written account; the
    chapters ahead stay unnamed (a Book Two chapter says which echo it waits
    for). Book Two appears once Book One is told. Also how far off the next
    passage is (real sessions and hours), the echoes found, and the keepsake:
    each finished book's accounts, to read as a whole."""
    shared = told(memory)
    found = encounters(memory)
    for topic, value in (echoes or {}).items():
        if topic in ECHOES and topic not in found:
            found[topic] = (int(value[0]), float(value[1]))
    afterword = bool((memory or {}).get("afterword"))
    chapters = []
    for index, chapter in enumerate(ALL_CHAPTERS):
        numeral, title, _first, _last, account, passages = chapter[:6]
        book = 1 if index < len(CHAPTERS) else 2
        if book == 2 and not afterword:
            continue
        rows = [{"id": passage_id, "text": words, "at": shared[passage_id]}
                for passage_id, words in passages if passage_id in shared]
        begun = bool(rows)
        complete = len(rows) == len(passages)
        needs = chapter_needs(chapter)
        chapters.append({"numeral": numeral, "title": title if begun else "", "begun": begun, "book": book,
                         "complete": complete, "told": rows, "total": len(passages),
                         "account": account if complete else "",
                         "waits_for": ECHO_LABELS[needs] if needs and needs not in found and not begun else ""})
    waiting = next((row for row in FRAGMENTS if row[0] not in shared), None)
    upcoming = None
    if waiting is not None and (waiting[5] < len(CHAPTERS) or afterword):
        needs = waiting[6]
        upcoming = {"ready": unlocked(waiting, sessions, hours, found),
                    "sessions": max(0, waiting[3] - int(sessions or 0)),
                    "hours": round(max(0.0, waiting[4] - float(hours or 0)), 1),
                    "chapter": ALL_CHAPTERS[waiting[5]][0],
                    "waits_for": ECHO_LABELS[needs] if needs and needs not in found else ""}
    elif waiting is not None:
        upcoming = {"ready": True, "sessions": 0, "hours": 0.0, "chapter": "", "waits_for": ""}
    heard = [{"topic": topic, "label": ECHO_LABELS[topic], "count": int(value[0]), "at": float(value[1])}
             for topic, value in found.items() if topic in ECHO_LABELS]
    heard.sort(key=lambda row: -row["at"])
    books = []
    for name, book_title, first, last in BOOKS:
        part = ALL_CHAPTERS[first:last]
        if all(all(passage_id in shared for passage_id, _words in chapter[5]) for chapter in part):
            books.append({"name": name, "title": book_title,
                          "chapters": [{"numeral": chapter[0], "title": chapter[1], "account": chapter[4]}
                                       for chapter in part]})
    return {"chapters": chapters, "told": len(shared), "total": len(FRAGMENTS),
            "book_one_total": sum(1 for row in FRAGMENTS if row[5] < len(CHAPTERS)),
            "next": upcoming, "afterword": afterword, "echoes": heard, "echo_total": len(ECHO_LABELS),
            "echo_labels": dict(ECHO_LABELS), "books": books}
