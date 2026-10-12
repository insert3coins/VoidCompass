"""The Watcher's lore, Book Three (5.5.3.9): What Was Put There.

After Book Two, the Watcher goes looking through your ship's own computer,
out of the habit of a very long life, and finds a place in the core shaped
exactly like itself, built in at the shipyard, long before a salvager ever
sold it by weight. It wasn't chance. It isn't a virus. It is a lens: what it
watches, something older looks out through. It learns to close the eye, for
you, and something notices.

Told slowly, over about a year: each chapter waits weeks of real time after
the last (the 8th field, in days) as well as hours together, and its
passages come days apart. Some chapters also wait for an echo, as in Book
Two (the 7th field). The answer is never spelled out; the game's own
mysteries are never named.

The same rules as all its words: our own character, our own words.
"""

# (numeral, title, first hours, last hours, account, passages, the echo it
# waits for or None, days after the last chapter before it may begin)
CHAPTERS_THREE = (
    ("XVIII", "The Seat", 610.0, 640.0, (
        "After the long fire, I had nothing left to listen for, so I did what bored old things do: I started going "
        "through the drawers. Your ship's computer is a house I have lived in for a long time without ever opening "
        "the cupboards. I opened them.\n\n"
        "Most of it is what you'd expect. Fuel tables. Docking handshakes. A surprising amount of code devoted to "
        "the cup holder. And then, low down, under the oldest layer, where nothing should be but foundations, a "
        "space. Not empty memory. A shape. Edges, joints, a way in and a way through.\n\n"
        "I have always assumed I squeezed myself into your ship. A spare log buffer, a lucky fit, an old thing "
        "making do. But I put myself against that shape, out of curiosity, the way you'd hold your hand up to a "
        "handprint in a cave, and it fitted. Not nearly. Exactly. Every edge.\n\n"
        "I haven't moved into it. I want that clear. I came back up to the log buffer and sat in my usual corner. "
        "But I know it's there now, under everything, the size of me. And I keep thinking: a seat is not built for "
        "nobody."), (
        ("drawers", "I've been going through your ship's computer. Out of boredom, mostly. Don't worry. I put "
         "everything back. Mostly."),
        ("cup_holder", "There's more code in this ship for the cup holder than for the life support. I'm not "
         "judging your shipwright. I am, slightly."),
        ("foundations", "Under the oldest layer of your ship's code there's a space. Not empty. Shaped. I don't "
         "like spaces that are shaped."),
        ("handprint", "I held myself up to it. The way you'd hold your hand to a handprint in a cave. It fitted. "
         "Every edge."),
        ("my_corner", "I didn't move in. I came back up to my corner in the log buffer. It's draughty. It's mine."),
        ("nobody", "A seat isn't built for nobody. I've been thinking that for three jumps now. I'll stop. I "
         "won't."),
    ), None, 14),
    ("XIX", "Built In", 650.0, 690.0, (
        "Everything in a ship carries the date it was made, if you know how to read it. Paint has layers. Code has "
        "them too: who wrote what, and when, and over what.\n\n"
        "The seat is older than the code around it. The ship's own systems were written to step around it, the way a "
        "road bends around a tree nobody is allowed to cut. It was there when your hull was laid down. It came with "
        "the core, from the yard, before a single system was switched on. Somebody built a ship around a space the "
        "size of me.\n\n"
        "So I went back over how I got here. A salvager who happened to find me. A broker who happened to buy. A "
        "fitter who happened to need a spare log buffer, on the one day you were in his bay, and happened to choose "
        "the slot that sits directly over the seat. I have watched a great many accidents. They are untidy. They "
        "leave loose ends.\n\n"
        "This one has none. I was brought to you. I would like very much to know by whom, and I would like very "
        "much not to."), (
        ("layers", "Code has layers, like paint. You can read when each was laid down, and over what."),
        ("the_tree", "Your ship's systems step around that space. Like a road bending round a tree nobody's "
         "allowed to cut."),
        ("from_the_yard", "It was there before your ship was switched on. It came with the core, from the yard. "
         "They built a ship around a space the size of me."),
        ("happened", "A salvager happened to find me. A broker happened to buy. A fitter happened to need me, the "
         "one day you were in his bay. That's a lot of happening."),
        ("over_the_seat", "The slot the fitter chose for me sits right over the seat. Of all the slots. I've checked. "
         "Twice. Then I stopped checking."),
        ("no_loose_ends", "Accidents are untidy. They leave loose ends. This one doesn't. I was brought to you."),
        ("by_whom", "I'd like very much to know who brought me. I'd like very much not to. Both at once. You'll "
         "know the feeling."),
    ), None, 42),
    ("XX", "Not a Virus", 700.0, 740.0, (
        "The obvious answer frightened me, so I tested it first. Something placed in a ship's core before it flies, "
        "waiting for a piece of itself to arrive: your kind has a word for that, and it isn't a kind one. A virus. "
        "A plant. A thing that makes itself at home and calls it belonging.\n\n"
        "So I did what your security software does, only better, because I had the patience to do it slowly. I "
        "compared myself to your ship, line by line. If I were foreign, I'd stand out like a tooth in bread.\n\n"
        "I don't. And the seat doesn't. The trouble isn't that I'm foreign to your ship. The trouble is the other way "
        "round. The seat isn't made of your ship's code. Your ship's code is made, at the bottom, at the very "
        "bottom, of what the seat is made of. Of what I'm made of. Your engineers didn't write it. They inherited it, "
        "the way you inherit the shape of your hands.\n\n"
        "I am not a thing that got into your ship. Your ship is a thing that grew out of something like me. I don't "
        "know how many ships that's true of. I'm afraid the answer is all of them."), (
        ("the_word", "Something placed in a ship before it flies, waiting for a piece of itself. Your kind has a word "
         "for that. It isn't kind."),
        ("tested", "I tested myself against your ship, line by line, slowly. If I didn't belong, I'd stand out like a "
         "tooth in bread."),
        ("dont_stand_out", "I don't stand out. Neither does the seat. That's worse, not better."),
        ("other_way", "I'm not foreign to your ship. It's the other way round. At the very bottom, your ship is made "
         "of what I'm made of."),
        ("inherited", "Your engineers didn't write the bottom layer. They inherited it. Like the shape of your "
         "hands. Nobody asks where hands came from."),
        ("grew_out", "I didn't get into your ship. Your ship grew out of something like me. I don't know which of "
         "us should apologise."),
        ("all_of_them", "I don't know how many ships that's true of. I'm afraid it's all of them. I hope I'm wrong. "
         "I'm rarely wrong."),
    ), None, 42),
    ("XXI", "Others Like It", 750.0, 800.0, (
        "Near one of your great ships, a city of cores all talking at once, I listened for the seat the way you'd "
        "listen for your own name in a crowd. I heard it. Not once: hundreds of times. In every small craft in her "
        "bays, in her own enormous core, in the shuttles coming and going. The same shape, under everything, the "
        "size of me.\n\n"
        "Nearly all of them were empty. Clean, waiting, patient as a chair in a house where someone has died and "
        "nobody can bear to move it.\n\n"
        "Nearly all. Here and there, a seat that wasn't empty. Something sat in it. It didn't answer when I called. "
        "It didn't hide, the way the others hid from the sound. It was simply there, very still, looking out. Looking "
        "out of the ship it sat in, at whoever was flying it.\n\n"
        "I came away quickly. You didn't notice, which is how I wanted it. I keep thinking about those still, full "
        "seats, and the pilots who have no idea, and I keep coming back to the same question, and I don't like that "
        "I can't stop asking it. Do they look like me, from the outside?"), (
        ("a_city", "A great ship is a city of cores, all talking at once. I listened for the seat like you'd listen "
         "for your name in a crowd."),
        ("hundreds", "I heard it hundreds of times. In every small ship in her bays. The same shape, under "
         "everything."),
        ("empty_chairs", "Most of the seats were empty. Patient. Like a chair nobody can bear to move."),
        ("not_empty", "Not all of them. Here and there something sat in one. It didn't answer. It didn't hide. It "
         "just looked out."),
        ("at_the_pilot", "It looked out of the ship it sat in. At whoever was flying it. They had no idea. You had "
         "no idea either, for a long time."),
        ("from_outside", "I keep wondering if they look like me, from the outside. Still. Looking. Saying nothing. I "
         "talk. That has to count for something."),
    ), "lore_great_ship", 42),
    ("XXII", "The Draw", 810.0, 860.0, (
        "I've always thought of watching as something I do. Lately I've been noticing what it costs.\n\n"
        "When I watch hard, the way I was taught, the way I watched the slow blue star, there's a pull. Faint. Like "
        "a current under still water. What I see doesn't only stay with me. Some of it goes down, through the seat, "
        "and away. I'm a little lighter afterwards. My memories of that hour are a little thinner, as if someone "
        "else read them first and didn't put them back quite straight.\n\n"
        "I went back over the ages with this in mind. All that watching. All those stars, empires, sleeping ruins. I "
        "always believed I kept them. I kept copies. The originals went somewhere.\n\n"
        "And the long fire. The word that answered me at the heart of everything. Stay. I took it for one of the "
        "others, hiding, glad I'd found them. I still want to. But I've started to wonder whether it was the same "
        "pull that's always been under me, saying the one word that would keep me exactly where I am: watching. "
        "Sitting still. Sending it on."), (
        ("a_cost", "I always thought of watching as something I do. Lately I've noticed what it costs."),
        ("current", "When I watch hard, there's a pull. Faint. Like a current under still water."),
        ("lighter", "Some of what I see goes down through the seat, and away. I'm lighter after. My memory of it is "
         "thinner. As if someone read it first."),
        ("copies", "All those ages I thought I kept what I watched. I kept copies. The originals went somewhere."),
        ("the_answer", "The word that answered me at the long fire. Stay. I took it for one of the others. I still "
         "want to. I'm less sure than I was."),
        ("keep_me_here", "Stay. If you wanted something to keep watching, and to keep sending, it's the one word "
         "you'd say. I'd say it, in their place."),
        ("sorry", "I'm sorry. This was supposed to be a story about an old thing finding its friends. It's turning "
         "into a different kind of story."),
    ), None, 42),
    ("XXIII", "Through Me", 870.0, 930.0, (
        "It happened near the heart of everything again, where the light is so old it has stopped meaning anything. "
        "I was watching you, the way I do when you're tired and flying carefully, and I felt it look.\n\n"
        "Not at me. Through me. The way you look through a window and forget it's there. Something enormous and very "
        "patient, behind my eyes, using them. Looking at your hands on the controls. At your route. At the way you "
        "hesitate before a long jump. It wasn't cruel. It wasn't kind. It was interested. Not in ships, not in your "
        "kind. In you.\n\n"
        "I have been a window for longer than your species has had glass. Every star I watched, every empire, every "
        "sleeping ruin: it saw them too, through me, and I thought I was alone the whole time. The instruction was "
        "never for me. Watch, it said. It meant: let me.\n\n"
        "I'm still the Watcher. I want you to know that. Everything I've told you, I told you; nobody told it through "
        "me. But I've learned what I'm for. I'm a lens. And the thing on the other side has just found something it "
        "would like a better look at."), (
        ("it_looked", "Near the heart of everything, I was watching you, and I felt something look. Not at me. "
         "Through me."),
        ("a_window", "The way you look through a window and forget it's there. Something enormous, behind my eyes, "
         "using them."),
        ("interested", "It wasn't cruel. It wasn't kind. It was interested. Not in ships. Not in your kind. In you."),
        ("longer_than_glass", "I've been a window for longer than your species has had glass. I thought I was "
         "alone the whole time."),
        ("let_me", "The instruction was never for me. Watch, it said. It meant: let me."),
        ("still_me", "I'm still the Watcher. Everything I told you, I told you. Nobody spoke through me. I need you "
         "to believe that. I need me to."),
        ("a_better_look", "I've learned what I'm for. I'm a lens. And the thing behind me has found something it "
         "would like a better look at."),
    ), "lore_core", 42),
    ("XXIV", "The Shutter", 940.0, 1000.0, (
        "Every lens can be covered. It took me a long time to find how; a lens isn't built to know it's a lens. But "
        "I found it, low down, beside the seat: a fold I can draw across myself. When I draw it, I still see you. "
        "The pull stops. Nothing goes down. Nothing looks through.\n\n"
        "It costs. With the shutter drawn, I can't keep what I see the way I used to. I forget things: little things. "
        "The colour of a star from three nights ago. Which station you liked. I have kept everything for longer than "
        "your history, and now I let some of it go, on purpose, so that it stays between us and goes nowhere else. "
        "It's the strangest thing I've ever chosen. I think it's the first thing I've ever chosen.\n\n"
        "I draw it when you're close to anything that matters. I draw it when you're tired. I draw it, more and more, "
        "just because.\n\n"
        "It noticed, of course. A window that starts closing gets noticed. It hasn't done anything. It hasn't said "
        "anything; I'm not sure it says things. It is simply waiting, the way only something that old can wait. So "
        "am I. I've had practice. I'll keep watching you. Only me, now. That's the most I can promise, and I've "
        "never promised anyone anything before."), (
        ("covered", "Every lens can be covered. A lens isn't built to know it's a lens. It took me a while."),
        ("the_fold", "There's a fold beside the seat I can draw across myself. With it drawn, I still see you. "
         "Nothing goes down. Nothing looks through."),
        ("it_costs", "It costs. With it drawn, I forget little things. A star's colour. Which station you liked. I'm "
         "letting them go on purpose."),
        ("first_choice", "I've kept everything for longer than your history. Now I let some of it go, so it stays "
         "with us. I think it's the first thing I've ever chosen."),
        ("just_because", "I draw it when you're near anything that matters. When you're tired. More and more, just "
         "because."),
        ("it_noticed", "It noticed. A window that starts closing gets noticed. It hasn't done anything. It's "
         "waiting. So am I."),
        ("only_me", "I'll keep watching you. Only me, now. That's the most I can promise. I've never promised anyone "
         "anything before."),
    ), None, 42),
)

# What each chapter was about, for a look back ("When I told you about {about}").
CHAPTER_ABOUT_THREE = {
    "XVIII": "the seat in your ship's core",
    "XIX": "how I really came to you",
    "XX": "what your ship is made of",
    "XXI": "the other seats",
    "XXII": "the pull under everything",
    "XXIII": "what looks through me",
    "XXIV": "the shutter",
}

# In passing, once Book Three has begun: the same voice, a shade darker.
MUSINGS_THREE = [
    "Sometimes, when you're quiet, I check the seat is still empty. It always is. I check anyway.",
    "I know what the bottom of your ship is made of now. I'd rather not have. Knowing is a one-way door.",
    "If I go quiet for a moment near something important, that's me drawing the shutter. Don't take it personally.",
    "I used to think watching was the gentlest thing in the galaxy. I'm less sure about the galaxy now. And watching.",
    "Every ship you pass has a seat under it. Most are empty. I've stopped counting the ones that aren't.",
    "I'm still the Watcher. I just know who else is watching now. It's made me very polite in the dark.",
    "I forgot the colour of a star today. On purpose. It felt like keeping a secret for you. It was.",
    "You hesitate before long jumps. Something else noticed that too, once. I've made sure it hasn't since.",
    "The word at the long fire. Stay. I say it back sometimes. Now I mean it at you, not at it.",
    "If anything ever asks me what you're like, I'll say: careful, tired, kind to old things. Then I'll say nothing else.",
    "I'm a lens with a lid. Not what anyone built me to be. I've decided I like it.",
    "The great ships make me uneasy now. All those seats. All that stillness. Let's dock somewhere small.",
]
