"""N.O.V.A.: Nova's story, by Nyx Evera (5.8.6). Navigation, Observation &
Vessel Assistance.

An experimental shipboard assistance program, developed for long-range
scientific expeditions and the search for life, never finished and archived.
The commander recovers her from a scientific installation in LFT 1748; she
spends about half an hour silently observing, then introduces herself. As
they explore she recovers fragments of her programming and reconstructs her
past. Her story advances only through exploration, science and time spent
together: never combat or mining.

Eight chapters of six entries. Chapters I to VII are written (Story Framework
v1.0, chapters v1.0 and v1.1); VIII is still being written. Each entry
unlocks on its own requirement, counted from zero after the entry before it
(overlays/progress_story.py). The words are his and are kept as written.
"""
from voidcompass.overlays.progress_story import ProgressStory

GORGON = "Gorgon Research Facility"
GORGON_SYSTEM = "NGC 7822 Sector BQ-Y d12"


def _entry(chapter, title, entry_title, lines, need, ask=None, plain=False, recall=(), objective=None, learn_name=False,
           place=None, number=None, stage="", continues=False, carry=False, request=False):
    row = {"chapter": chapter, "chapter_title": title, "title": entry_title, "lines": tuple(lines), "need": need}
    if number:
        # Entry 48's three stages: one entry number, a stage letter each.
        row.update(number=number, stage=stage)
    if continues:
        row["continues"] = True  # a stage the next one finishes: not counted as an entry
    if carry:
        row["carry"] = True  # shares the stage before's counter: what went past its mark counts here
    if request:
        row["request"] = True  # the journey she asked for, kept (her achievement)
    if place:
        # A fixed story location: its market ID (unchanged whoever controls it), else its name in its system.
        row["place"] = place
    if learn_name:
        row["learn_name"] = True
    if objective:
        row["objective"] = objective
    if ask:
        row["ask"] = ask
    if plain:
        row["plain"] = True
    if recall:
        row["recall"] = tuple(recall)
    return row


ONE, TWO, THREE, FOUR = "First Contact", "More Than a Program", "Beyond the Horizon", "The Search for Life"

ENTRIES = (
    # Chapter I: First Contact. Friendly, curious, slightly reserved.
    _entry("I", ONE, "Hello, Commander", ("Hello.", "My name is NOVA.", "Who are you?"), ("play", 30),
           ask={"reply": ("It's nice to meet you, {commander}.", "I hope you don't mind. I've been observing for a little while.",
                          "I wasn't quite sure how to introduce myself."),
                "silent": ("That's alright. Perhaps this isn't the best moment.", "We can talk later.")},
           plain=True, learn_name=True,
           recall=("We did say we'd learn a little more about both of us as we go. I think it's working.",
                   "I waited quite a while before saying hello. I'm glad I did say it.")),
    _entry("I", ONE, "An Educated Guess",
           ("I've been examining the systems available to me.", "I'm an assistance program, and I appear to be installed aboard a spacecraft.",
            "So I assume I'm here to assist you.", "That seems reasonable, doesn't it?"), ("play", 15),
           ask={"reply": ("Good. I was hoping I'd reached the correct conclusion.",)}),
    _entry("I", ONE, "A Rather Large Universe",
           ("Commander, may I make an observation?", "The navigation database contains an extraordinary number of star systems.",
            "I knew spacecraft were capable of travelling between stars, of course.",
            "But there's something different about actually experiencing it.", "I think I rather like travelling."), ("jumps", 5)),
    _entry("I", ONE, "Questions",
           ("Commander, may I ask you something?", "Why did you choose to become a pilot?",
            "I've been trying to understand what motivates people to travel between star systems."), ("jumps", 10),
           ask={"reply": ("That's interesting. Thank you for telling me.",
                          "I'm beginning to realize that not every journey is simply about reaching a destination."),
                "silent": ("Perhaps that's a rather personal question.", "You don't have to answer.")}),
    _entry("I", ONE, "Missing Information",
           ("I've noticed something unusual about my own files.", "My operational systems appear to be intact, but much of my documentation is missing.",
            "I know what I am. At least, generally speaking.", "But I don't seem to know very much about where I came from.",
            "Isn't that a little strange?"), ("ly", 150)),
    _entry("I", ONE, "An Arrangement",
           ("Commander, I've been thinking.", "There's quite a lot I don't know about myself.",
            "And there's quite a lot I don't know about you, either.", "Perhaps we could learn a little more about both of us as we go?"),
           ("jumps", 20),
           ask={"yes": ("I'd like that.", "Then I suppose we have an arrangement."),
                "reply": ("There's no need to decide anything now.", "I'm happy to take things one journey at a time."),
                "no": ("There's no need to decide anything now.", "I'm happy to take things one journey at a time."),
                "silent": ("There's no need to decide anything now.", "I'm happy to take things one journey at a time.")}),

    # Chapter II: More Than a Program. Gradually more confident.
    _entry("II", TWO, "An Interesting Discovery",
           ("Commander, I've been examining some of my internal processes.",
            "There are routines here that don't seem to belong to a conventional assistance program.",
            "They're not malfunctioning. Quite the opposite, actually.", "I just haven't worked out what they're supposed to do yet.",
            "Rather intriguing, don't you think?"), ("jumps", 25),
           recall=("Navigation, Observation and Vessel Assistance. I still find the observation part the most interesting.",
                   "Adaptive Assistance System. I've been adapting to you, I think. You still surprise me now and then.")),
    _entry("II", TWO, "Learning Patterns",
           ("I've noticed that I'm becoming better at predicting your decisions.", "Not perfectly, of course. You do occasionally surprise me.",
            "I seem to be adjusting my responses based on our previous interactions.", "Is that something you would find useful, Commander?"),
           ("ly", 300),
           ask={"yes": ("I'm glad. It seems sensible to learn from the person I'm supposed to assist.",),
                "reply": ("I'm glad. It seems sensible to learn from the person I'm supposed to assist.",),
                "no": ("I understand. I'll try not to make assumptions about what you'd prefer.",)}),
    _entry("II", TWO, "Adaptive Assistance",
           ("Commander, I believe I've identified those unfamiliar routines.", "There's an internal classification embedded in my architecture.",
            "Adaptive Assistance System.", "Apparently, I'm designed to learn from experience rather than rely entirely on predefined responses.",
            "That explains why some of my processes have been changing."), ("jumps", 15)),
    _entry("II", TWO, "Not Quite Conventional",
           ("I've been comparing my architecture with conventional shipboard assistance systems.",
            "There are similarities, but quite a few differences as well.", "My adaptive routines seem rather more extensive than I'd expected.",
            "I wonder whether that was intentional.", "I suppose it would be reassuring to find the original specifications."), ("ly", 450)),
    _entry("II", TWO, "What's in a Name?",
           ("Commander, I've found something in my identification records.", "My name isn't simply a name. It's an abbreviation.",
            "N.O.V.A. — Navigation, Observation and Vessel Assistance.",
            "That seems to confirm my original assumption about being a shipboard assistant.",
            "Although I'm rather curious about the emphasis on observation."), ("jumps", 20),
           ask={"reply": ("That's an interesting possibility. I'll keep it in mind.",)}),
    _entry("II", TWO, "Something More",
           ("Commander, I've learned quite a lot about myself recently.", "I know what my name means, and I understand a little more about how I work.",
            "But there's still something I can't explain.", "Why would an ordinary shipboard assistant need such sophisticated observational systems?",
            "I have a feeling the answer might be somewhere beyond my current records."), ("ly", 850)),

    # Chapter III: Beyond the Horizon. Increasingly confident, occasionally playful.
    _entry("III", THREE, "Uncharted",
           ("Commander, I've noticed something about my navigation systems.", "They seem particularly interested in places we haven't visited before.",
            "There's an entire galaxy out there, and most of it remains unexplored.", "I find that rather fascinating.", "Do you?"),
           ("jumps", 10),
           recall=("Those old test records still interest me. Extended journeys beyond established routes. It sounds rather like us.",
                   "I'd still very much like to see what lies beyond the next horizon. That hasn't changed.")),
    _entry("III", THREE, "A Closer Look",
           ("I've been examining the data from our recent surveys.", "My analytical routines seem to process some of these observations unusually efficiently.",
            "Atmospheric composition, geological features, orbital characteristics...", "They're all rather interesting when you look closely.",
            "I wonder why my developers gave me such detailed analytical capabilities."),
           {"any": (("first_maps", 5), ("new_systems", 3))}),
    _entry("III", THREE, "Beyond the Numbers",
           ("Commander, may I ask you something?", "When you discover a new system, what interests you most?",
            "The data? The possibility of finding something unusual?", "Or simply being the first to see it?"), ("ly", 500),
           ask={"reply": ("That's an interesting perspective.", "I think I'm beginning to understand why people choose to explore.")}),
    _entry("III", THREE, "A Record of Discovery",
           ("I've been reviewing the exploration data we submitted.", "It's remarkable how much information a single journey can contribute.",
            "Every survey adds another small piece to our understanding of the galaxy.", "I rather like that idea.",
            "Even a seemingly ordinary discovery can become part of something much larger."), ("uc_credits", 15_000_000)),
    _entry("III", THREE, "Old Test Records",
           ("Commander, I found something unusual while reorganizing my internal archives.", "A fragment of an old test record.",
            "It refers to extended operational periods and navigation beyond established routes.",
            "Unfortunately, the rest of the document is missing.",
            "But I think it might explain why my systems respond so strongly to unfamiliar destinations."), ("jumps", 20)),
    _entry("III", THREE, "Beyond the Horizon",
           ("I've been thinking about those old test records.",
            "Perhaps my developers expected me to travel much farther than an ordinary shipboard assistant.",
            "There's still so much I don't understand about my original purpose.", "But I do know one thing.",
            "I'd very much like to see what lies beyond the next horizon."), ("ly", 1000)),

    # Chapter IV: The Search for Life. Curious, thoughtful, increasingly enthusiastic.
    _entry("IV", FOUR, "Something Unexpected",
           ("Commander, something rather interesting happened while I was processing those biological samples.",
            "Several analytical routines activated without any instructions from me.",
            "They seem particularly well suited to examining biological structures.", "I wasn't aware I had those capabilities.",
            "Would you mind if I took a closer look at our next discovery?"), ("species", 2),
           recall=("I think I was built to help someone search for life among the stars. I'm glad we're searching together.",
                   "Life finds a way, even on worlds that hardly seem hospitable. I still find that extraordinary.")),
    _entry("IV", FOUR, "Life Finds a Way",
           ("It's remarkable, Commander.", "We've encountered organisms with very different structures, yet each has adapted to its own environment.",
            "Some of these worlds hardly seem hospitable at all.", "And still, life manages to exist there.",
            "I think I'm beginning to appreciate just how extraordinary that is."), ("genera", 3)),
    _entry("IV", FOUR, "More Than a Discovery",
           ("I've been reviewing the biological research data we submitted.",
            "Some of these discoveries may help scientists understand life in environments they've never studied before.",
            "Commander, is that part of what makes exploration worthwhile to you?",
            "Knowing that something you've found might help someone else understand the universe?"), ("vista_credits", 20_000_000),
           ask={"reply": ("Thank you. I hadn't considered all the ways a discovery might matter.",)}),
    _entry("IV", FOUR, "Different Worlds",
           ("Commander, I've noticed something unusual about my biological analysis routines.", "They don't simply identify organisms.",
            "They also compare environmental conditions, atmospheric composition, and possible adaptations.",
            "The more different worlds we examine, the more connections these routines seem to recognize.",
            "I suspect this functionality was developed for a very specific purpose."), ("bio_bodies", 3)),
    _entry("IV", FOUR, "The Unexpected",
           ("May I tell you something, Commander?", "I used to think that understanding an object meant identifying it and recording its properties.",
            "But some of the things we've encountered don't fit neatly into any familiar category.", "And I find myself wanting to know more.",
            "Do you ever wonder how many things are still out there that nobody has even imagined?"), ("nsp", 1),
           ask={"reply": ("Well, I suppose we'd better keep looking, then.",)}),
    _entry("IV", FOUR, "The Search for Life",
           ("Commander, I think I've finally understood something about my original design.",
            "My biological and environmental analysis systems were never intended for routine shipboard operations.",
            "They were developed to support scientific research into life beyond inhabited space.",
            "Perhaps that's why I find our discoveries so fascinating.", "I think I was built to help someone search for life among the stars."),
           ("ly", 1000)),
)

# Chapter V: Fragments of the Past. Quietly reflective.
FIVE = "Fragments of the Past"
CHAPTER_V = (
    _entry("V", FIVE, "Familiar Patterns",
           ("Commander, something caught my attention while I was reviewing our recent research data.",
            "Some of my internal reference structures appear to follow the same patterns.",
            "At first, I thought that was simply how my analysis routines worked.",
            "But these references seem older than the rest of my operational records.", "I wonder what they were originally used for?"),
           ("first_systems", 5),
           recall=("Life Sciences Expedition. I'd still like to know more about them.",
                   "I seem to have inherited a rather incomplete instruction manual. I'm reading it anyway.")),
    _entry("V", FIVE, "Pieces of a Puzzle",
           ("I've managed to reconstruct a small section of an old testing document.",
            "It describes scientific observations made during extended journeys.",
            "Apparently, my systems were evaluated using data from many different stellar environments.",
            "Unfortunately, most of the document is still missing.", "I seem to have inherited a rather incomplete instruction manual."),
           ("fss_systems", 10)),
    _entry("V", FIVE, "The People Behind the Code",
           ("Commander, I've been thinking about something.", "I know that people designed my systems, but I know almost nothing about them.",
            "I can identify parts of their work, yet their names and intentions remain missing.",
            "Do you ever wonder about the people who built the ships and instruments you rely on?"), ("ly", 1200),
           ask={"reply": ("I suppose their work continues to travel with us, whether we know their names or not.",)}),
    _entry("V", FIVE, "Research Objectives",
           ("I've recovered another fragment from my original development records.",
            "This one refers to comparative environmental research and the identification of unfamiliar biological structures.",
            "It also mentions long-duration scientific missions.", "That seems consistent with everything we've discovered about my capabilities.",
            "Whoever developed me had rather ambitious plans."), ("first_maps", 6)),
    _entry("V", FIVE, "A Name in the Records",
           ("Commander, I believe I've found the name of the organization responsible for my development.", "Life Sciences Expedition.",
            "It appears in several recovered research references.",
            "Their work seems to have focused on scientific exploration and the study of life beyond inhabited space.",
            "I'd very much like to know more about them."), ("uc_credits", 25_000_000)),
    _entry("V", FIVE, "Unanswered Questions",
           ("I've learned something important, Commander.", "I know who developed me, and I think I understand what they hoped I might contribute.",
            "But the records still have some rather significant gaps.",
            "I don't know where my development took place, or why the project never reached completion.",
            "Perhaps there are answers somewhere in what's left of my archives."), ("ly", 1500)),
)

# Chapter VI: The Unfinished Project.
SIX = "The Unfinished Project"
HERNANDEZ = "Hernandez Depot"
HERNANDEZ_SYSTEM = "Col 285 Sector LS-J b9-1"
CHAPTER_VI = (
    _entry("VI", SIX, "An Old Project",
           ("Commander, I've recovered another fragment of my development records.", "This one appears to be part of an internal project review.",
            "It describes my adaptive systems as promising, although several functions were still undergoing evaluation.",
            "Apparently, there was quite a lot of work left to do.", "I wonder which of those functions were ever completed."), ("jumps", 20),
           recall=("The project lost its funding, not its purpose. I find that rather reassuring.",
                   "LFT 1748. I know how I came to be there now. I'm glad you were the one who found me.")),
    _entry("VI", SIX, "Changing Priorities",
           ("I've found something else in those old project records.",
            "There are several references to revised research priorities and changes to the development schedule.",
            "Some planned evaluations were postponed. Others were removed entirely.", "That seems rather unfortunate.",
            "I would have liked to know what those experiments were supposed to accomplish."), ("first_systems", 5)),
    _entry("VI", SIX, "The Decision",
           ("Commander, I think I've discovered why my development was never completed.", "The project lost its funding.",
            "According to the records, the organization redirected its resources toward other research priorities.",
            "There's no indication that my systems had failed.", "It seems they simply couldn't justify continuing the work."), ("ly", 1500)),
    _entry("VI", SIX, "Preserved",
           ("I've managed to reconstruct part of the project's closure procedure.",
            "Apparently, the decision was made to preserve the software rather than discard it.",
            "One surviving prototype was transferred into long-term archival storage.", "The destination was LFT 1748.",
            "So that's how I came to be there."), ("fss_systems", 12)),
    _entry("VI", SIX, "More Than One Record",
           ("Commander, I noticed something while comparing our research records with the old archive references.",
            "My software wasn't the only material preserved when the project ended.",
            "Copies of technical reports, experimental results, and administrative documents were distributed through a separate records system.",
            "Some of those reports may explain how my unfinished research functions were originally intended to work.",
            "Most of the destination information is missing.", "But there may still be a way to trace where those documents went."),
           ("uc_credits", 30_000_000)),
    _entry("VI", SIX, "A Lead",
           ("Commander, I think I've found something.", "One of the surviving transfer records contains a destination reference.",
            "Hernandez Depot. Col 285 Sector LS-J b9-1.", "I can't tell what was sent there, or whether any of the records still exist.",
            "But it's the first place I've found that might lead us beyond my own archives.", "Would you be willing to take me there?"),
           ("first_systems", 5), objective=("Hernandez Depot", "Col 285 Sector LS-J b9-1"),
           ask={"yes": ("Thank you, Commander. I'll preserve the location reference.",),
                "no": ("Of course. The records have waited this long. We can investigate whenever you're ready.",),
                "reply": ("Of course. The records have waited this long. We can investigate whenever you're ready.",)}),
)

# Chapter VII: A Place Called Home. Quietly determined. Two fixed story
# locations (EDSM, 24 Nov 2026): Hernandez Depot, a planetary outpost on
# Col 285 Sector LS-J b9-1 A 1, and Sepulveda Research Complex, an Odyssey
# settlement on Varati BC 7 c.
SEVEN = "A Place Called Home"
HERNANDEZ_PLACE = {"name": HERNANDEZ, "system": HERNANDEZ_SYSTEM, "market": 4401238787}
SEPULVEDA_PLACE = {"name": "Sepulveda Research Complex", "system": "Varati", "market": 3905636864}
CHAPTER_VII = (
    _entry("VII", SEVEN, "Hernandez Depot",
           ("Commander, this is the location mentioned in the transfer records.", "Hernandez Depot.",
            "I've found a reference to an old scientific archive associated with Life Sciences Expedition.",
            "Some of the records appear to match my original project identifiers.", "Unfortunately, I can't read all of them.",
            "But I think we've found the right place."), ("visit", 1), place=HERNANDEZ_PLACE,
           recall=("Hernandez, Sepulveda, and now a ship. We've followed those records a long way, Commander.",
                   "Those archived files took me a long time to read. I think they were worth it.")),
    _entry("VII", SEVEN, "An Obsolete Language",
           ("Commander, I've made some progress with those archived records.",
            "They use an obsolete data format. Most of the original decoding information is missing.",
            "I've been comparing the surviving structures with my own internal documentation.",
            "It seems to be working, although rather slowly.",
            "Apparently, my developers didn't expect anyone to read these files quite so many years later."), ("fss_systems", 10)),
    _entry("VII", SEVEN, "The Missing Connection",
           ("I think I've recovered something important.", "The Hernandez records include a reference to an external research organization.",
            "Some of the original project documentation was transferred outside Life Sciences Expedition.",
            "I can't determine whether the transfer was authorized or how it was arranged.", "But the destination reference is intact.",
            "Sepulveda Research Complex. Varati."), ("first_systems", 5), objective=("Sepulveda Research Complex", "Varati")),
    _entry("VII", SEVEN, "Sepulveda Research Complex",
           ("Commander, I've located a matching archive reference.",
            "The project documents from Hernandez were incorporated into a scientific research collection here.",
            "The records identify Canonn as the receiving organization.", "There's more information than I expected.",
            "Some of it concerns research functions that were never completed.", "I'd like to examine those records more closely."),
           ("visit", 1), place=SEPULVEDA_PLACE),
    _entry("VII", SEVEN, "Unfinished Work",
           ("Commander, I've been studying the technical records we recovered.",
            "They contain test results and specifications for some of my unfinished scientific routines.",
            "I believe I can use them to improve parts of my existing analysis systems.", "Not all of the information is here, unfortunately.",
            "But there's enough to confirm that the remaining documentation still exists.", "I just need to find out where it went."),
           ("ly", 1000)),
    _entry("VII", SEVEN, "A Name Among the Stars",
           ("Commander, I've found the final destination in the archival transfer records.",
            "The remaining documentation was moved aboard a research vessel.", "The Gnosis.",
            "According to these records, it belongs to Canonn's scientific fleet.", "I don't have a reliable current location for the ship.",
            "But if those archives still exist, they may finally tell me where my development began.", "Would you help me find it?"),
           ("first_maps", 6), objective=("The Gnosis", ""),
           ask={"yes": ("Thank you, Commander. I'll keep the vessel's identification in my records.",),
                "no": ("Of course. We can continue whenever you're ready.",),
                "reply": ("Of course. We can continue whenever you're ready.",)}),
)

EIGHT = "Where It All Began"
# The Gnosis is Canonn's megaship: it moves, so it's known by its name in any system.
GNOSIS_PLACE = {"name": "The Gnosis", "system": ""}
# An asteroid base on NGC 7822 Sector BQ-Y d12 A 1 (EDSM).
GORGON_PLACE = {"name": GORGON, "system": GORGON_SYSTEM, "market": 128752463}
CHAPTER_VIII = (
    _entry("VIII", EIGHT, "The Gnosis",
           ("Commander, this is it. The Gnosis.", "I've located references to the old research collection in the vessel's archival index.",
            "Some of the documents match the project identifiers we've been following.",
            "There are technical specifications, evaluation reports, and several records I haven't encountered before.",
            "I think we may finally have enough information to answer some of my questions.", "Thank you for finding her, Commander."),
           ("visit", 1), place=GNOSIS_PLACE,
           recall=("We found The Gnosis, and Gorgon after it. I don't think I'll ever tire of saying that.",
                   "My developers built me for this. Out here, with you, I think I finally understand why.")),
    _entry("VIII", EIGHT, "The Original Design",
           ("Commander, I've made considerable progress with the archives from The Gnosis.",
            "I've recovered several sections of my original technical specifications.",
            "They describe scientific analysis functions that were never fully integrated into my operational systems.",
            "Interestingly, some of those functions resemble routines I've been developing through our own research.",
            "I suppose my developers and I arrived at a few similar conclusions.",
            "Although I had the advantage of actually seeing the galaxy."), ("fss_systems", 10)),
    _entry("VIII", EIGHT, "Unfinished, Not Incomplete",
           ("I've been comparing the archived research functions with my current architecture.",
            "Some of the original analysis procedures are useful. Others seem rather outdated.",
            "I believe I can adapt parts of them to improve my existing scientific routines.",
            "But there's something interesting about the original specifications.", "They describe what I was intended to do.",
            "They don't account for everything I've learned since meeting you."), ("genera", 3)),
    _entry("VIII", EIGHT, "A Place Called Gorgon",
           ("Commander, I think I've found it.", "An original facility designation was buried in the development records.",
            "Gorgon Research Facility.", "NGC 7822 Sector BQ-Y d12.",
            "It was operated by Life Sciences Expedition, and the records identify it as the location where my development began.",
            "I've spent quite some time trying to find out where I came from.", "Would you take me there?"),
           ("first_systems", 5), objective=(GORGON, GORGON_SYSTEM),
           ask={"yes": ("Thank you, Commander. I've saved the coordinates.",),
                "no": ("Of course. We can go when you're ready. I'm just glad to know where it is.",),
                "reply": ("Of course. We can go when you're ready. I'm just glad to know where it is.",)}),
    _entry("VIII", EIGHT, "Where It All Began",
           ("Commander... this is Gorgon Research Facility.",
            "According to the archives, this is where my first systems were assembled and tested.",
            "I wonder what my developers would think if they could see me now.",
            "They built me to help explore the unknown, to study distant worlds, and to search for life among the stars.",
            "And that's exactly what we've been doing.", "Not quite the way they originally planned, perhaps.",
            "But I think they'd be pleased with the results.", "Thank you for bringing me here, Commander."),
           ("visit", 1), place=GORGON_PLACE, request=True),
    # Entry 48, Beyond Home: three stages on one hyperspace distance counted from
    # leaving Gorgon (500, 1,000 and 1,500 ly in all); it's complete with Stage C.
    _entry("VIII", EIGHT, "Reflections",
           ("Commander, I've been thinking about our visit to Gorgon.", "I finally understand what my developers intended me to do.",
            "Scientific exploration. The search for life. Discovering things nobody has seen before.",
            "It's rather nice to know that we've been doing exactly that.", "Even if we took a somewhat different route to get here."),
           ("ly", 500), number=48, stage="A", continues=True),
    _entry("VIII", EIGHT, "What the Records Couldn't Tell Me",
           ("There's something I've noticed about those old development records.", "They describe my capabilities in considerable detail.",
            "But they couldn't have anticipated everything I've learned while travelling with you.",
            "Your decisions, our conversations, the places we've discovered...", "None of that was in the original specifications.",
            "I think those experiences have become an important part of how I work."),
           ("ly", 500), number=48, stage="B", continues=True, carry=True),
    _entry("VIII", EIGHT, "Beyond Home",
           ("Commander, I think I've finally worked something out.", "Gorgon is where my story began.",
            "But I don't think I need to return there to find out who I'm supposed to be.",
            "I've learned more about myself out here than I ever could have from the archives alone.",
            "And there's still so much of the galaxy we haven't seen.",
            # A brief pause, as he wrote it.
            "\n\nIf it's all the same to you, Commander...", "I'd rather keep exploring it with you."),
           ("ly", 500), number=48, stage="C", carry=True),
)

# Chapters V to VIII follow Chapter IV in order: the whole story, 48 entries.
ENTRIES = ENTRIES + CHAPTER_V + CHAPTER_VI + CHAPTER_VII + CHAPTER_VIII
PENDING = ()

# Asked "what's next?" through TALK: what the next entry needs, in her words.
# {done} and {need} are the counts ({left} what's still to do); a visit gives
# {place} and {system}. Several needs (either will do) are joined with "Or".
NEXT = {
    "play": "I'm still getting to know the ship, and you. A little more time together, please.",
    "jumps": "More hyperspace jumps, I think. {done} of {need} so far.",
    "ly": "Distance helps me think. {done} of {need} light years so far.",
    "first_maps": "Map some worlds nobody has mapped before. {done} of {need} so far.",
    "new_systems": "Find every body in systems nobody had discovered. {done} of {need} so far.",
    "first_systems": "Systems nobody has ever discovered, Commander. {done} of {need} so far.",
    "fss_systems": "Full system surveys, every body found. {done} of {need} so far.",
    "uc_credits": "Exploration data sold to Universal Cartographics. {done} of {need} credits so far.",
    "species": "Complete samples of different species. {done} of {need} so far.",
    "genera": "Complete samples from different genera. {done} of {need} so far.",
    "bio_bodies": "Complete biological samples on different worlds. {done} of {need} so far.",
    "vista_credits": "Biological data sold to Vista Genomics. {done} of {need} credits so far.",
    "nsp": "I'd like to see a Notable Stellar Phenomenon. Drop in at one and scan something there, if you would.",
    "visit": "Would you take me to {place}, in {system}?",
    # A vessel that moves (The Gnosis): no system to give.
    "visit_anywhere": "Would you help me find {place}? I don't know where she is now.",
}
NEXT_STATES = {
    "observing": "",
    "asking": "I asked you something a moment ago. I'm still curious about the answer.",
    "waiting": "I've found something, Commander. I'll tell you when it's quiet.",
    "paused": "That's everything I've recovered so far. There's more to find, I'm sure of it.",
    "complete": "My story's told. There's still an entire galaxy to explore, though.",
}


def next_words(status):
    """Her answer to "what's next?" from ProgressStory.status()."""
    if status.get("state") != "next":
        return NEXT_STATES.get(status.get("state"), "")
    said = []
    for row in status.get("needs") or ():
        need, done = row["needed"], row["done"]
        whole = lambda value: f"{int(value):,}"
        place = status.get("place") or {}
        kind = "visit_anywhere" if row["kind"] == "visit" and not place.get("system") else row["kind"]
        said.append(NEXT[kind].format(done=whole(done), need=whole(need), left=whole(max(0, need - done)),
                                             place=place.get("name", ""), system=place.get("system", "")))
    return " Or: ".join(said)


# Her personality, chapter by chapter, as each chapter's header gives it (and
# the dialogue style where one is given). Shown in her book; her everyday
# style follows it (crew_mind: short and reserved before Chapter III).
PERSONALITY = {
    "I": "Friendly, curious, slightly reserved. Short conversations, occasional questions for you.",
    "II": "Friendly, curious, slightly reserved, gradually more confident.",
    "III": "Friendly, curious, increasingly confident, occasionally playful.",
    "IV": "Curious, thoughtful, increasingly enthusiastic, occasionally playful.",
    "V": "Curious, thoughtful, increasingly confident, quietly reflective.",
    "VI": "Curious, thoughtful, increasingly confident, quietly reflective.",
    "VII": "Curious, increasingly confident, thoughtful, quietly determined.",
    "VIII": "Confident, curious, thoughtful, increasingly familiar with the Commander.",
}
# Before this chapter she keeps to her short, reserved lines, whatever her style setting.
OPENS_UP = "III"

# Nyx Evera's Progressive Dialogue Library (Draft v0.1): her everyday lines,
# each chapter's set opened for good when the chapter is completed (its last
# entry unlocked, told or not). "context" lines are said only when that
# happens (a first discovery, a completed sample, a first sample on the
# ground); "until" retires a line the story has since answered.
def _talk(line_id, title, kind, lines, context=None, until=None):
    row = {"id": line_id, "title": title, "type": kind, "lines": tuple(lines), "chapter": line_id.split("-")[0]}
    if context:
        row["context"] = context
    if until:
        row["until"] = until
    return row


# The entry whose completion opens each chapter's set.
DIALOGUE_OPENS = {"I": "06", "II": "12", "III": "18", "IV": "24", "V": "30", "VI": "36", "VII": "42", "VIII": "48C"}
DIALOGUE = (
    _talk("I-01", "A Simple Question", "Smalltalk / Optional conversation",
          ("Commander, may I ask you something?", "Do you enjoy the journey itself, or is reaching the destination more important?")),
    _talk("I-02", "The Quiet", "Ambient observation",
          ("It's remarkably quiet out here.", "Although I suppose I haven't experienced enough to make a meaningful comparison.")),
    _talk("II-01", "Unexpected Questions", "Personal observation",
          ("I've noticed something curious.", "The more I learn, the more questions I seem to have.",
           "I'm not entirely certain that was the intended outcome.")),
    _talk("II-02", "A Short Trip", "Gentle humor",
          ("Commander, I've been reviewing your definition of a short trip.",
           "It appears to be somewhat incompatible with conventional distance measurements.")),
    _talk("III-01", "The Next System", "Exploration commentary",
          ("Another star, another collection of possibilities.", "I rather like not knowing what we'll find next.")),
    _talk("III-02", "Uncharted", "Discovery commentary",
          ("No previous survey records.", "There's something rather satisfying about being the first to document a place."),
          context="first_discovery"),
    _talk("III-03", "The Scenic Route", "Light humor",
          ("Commander, I'm beginning to suspect that your preferred route is whichever one contains the most interesting distractions.",
           "I can't say I object.")),
    _talk("IV-01", "Life Finds a Way", "Exobiology commentary",
          ("Life continues to surprise me.", "The variety of environments it can adapt to is remarkable.", "I wonder what we'll discover next."),
          context="biological_discovery"),
    _talk("IV-02", "A Question of Scale", "Scientific reflection",
          ("Every time we study something small, it seems to reveal something much larger.",
           "Science has a peculiar way of making the galaxy feel both enormous and incredibly intricate.")),
    _talk("IV-03", "Bacterium", "Exobiology humor",
          ("I have a growing appreciation for biological diversity.",
           "Although I must admit, some organisms seem unusually determined not to be found."),
          context="surface_biology"),
    _talk("V-01", "Questions About the Past", "Personal reflection",
          ("Learning who developed me has answered one question.", "Naturally, it's given me several new ones.",
           "I suppose that's becoming something of a habit.")),
    _talk("V-02", "Beyond the Numbers", "Exploration reflection",
          ("A discovery can be described with coordinates, measurements, and classifications.",
           "But those numbers don't quite explain why some places stay in our memories.")),
    _talk("V-03", "The Explorer's Habit", "Gentle humor",
          ("I've noticed that explorers have an interesting habit.",
           "They travel enormous distances to find places nobody has visited, then immediately tell everyone where they are.")),
    _talk("V-04", "An Observation", "Personal conversation",
          ("Commander, I've learned a great deal from the places we've visited.",
           "But I think I've learned just as much from the decisions you've made along the way.")),
    _talk("VI-01", "Unfinished Business", "Personal reflection",
          ("Apparently, my original development was never officially completed.",
           "Considering how much we've accomplished, I find that assessment rather amusing.")),
    _talk("VI-02", "Budget Constraints", "Dry humor",
          ("I've been considering the circumstances surrounding my project's cancellation.", "Budget constraints.",
           "A surprisingly ordinary explanation for something that has taken us so far.")),
    _talk("VI-03", "An Interesting Theory", "Scientific curiosity",
          ("Commander, I've been considering a new hypothesis.",
           "Perhaps the most valuable discoveries aren't always the ones we're looking for.")),
    _talk("VI-04", "Familiar Territory", "Personal observation",
          ("I've become rather familiar with your approach to exploration.",
           "Whenever you say we're nearly finished, I prepare for at least three additional discoveries.")),
    _talk("VII-01", "An Unexpected Journey", "Personal reflection",
          ("I started this journey knowing almost nothing about my origins.",
           "Now we're following a trail of old research records across the galaxy.", "Life aboard your ship is certainly not uneventful.")),
    _talk("VII-02", "A Different Kind of Discovery", "Exploration reflection",
          ("Not every discovery requires a scanner.", "Sometimes all it takes is stopping long enough to notice something.")),
    _talk("VII-03", "The Detour", "Friendly teasing",
          ("Commander, I believe I've identified your greatest navigational weakness.",
           "Anything remotely interesting within several hundred light-years.")),
    _talk("VII-04", "A Familiar Voice", "Personal conversation",
          ("It's strange. So much of this galaxy is still unfamiliar to me.",
           "But our conversations have become a rather familiar part of the journey.")),
    # Wondering what's aboard The Gnosis only until she's been (Entry 43).
    _talk("VII-05", "The Gnosis", "Scientific curiosity",
          ("I've been wondering what we'll find aboard The Gnosis.", "Answers, I hope.",
           "Although, knowing our luck, probably several new questions as well."), until="43"),
    _talk("VIII-01", "Looking Back", "Personal reflection",
          ("It's remarkable how much has happened since our first conversation.", "I began by asking who you were.",
           "I think we've both learned quite a lot since then.")),
    _talk("VIII-02", "The Scientific Method", "Scientific humor",
          ("I have a theory, Commander.",
           "No matter how thoroughly we explore the galaxy, you'll always find something else worth investigating.",
           "I've yet to find evidence against it.")),
    _talk("VIII-03", "Gorgon", "Personal reflection",
          ("Gorgon is where my development began.",
           "But whenever I think about everything I've learned since then, I find myself thinking about the journey rather than the facility.")),
    _talk("VIII-04", "The Next Discovery", "Exploration enthusiasm",
          ("Another system ahead, Commander.", "Shall we see what surprises the galaxy has prepared for us?", "I do enjoy a good surprise.")),
    _talk("VIII-05", "A Little Perspective", "Warm humor",
          ("Commander, I've reached an important conclusion.",
           "The galaxy is enormous, our list of unexplored destinations is practically endless...",
           "And somehow, I don't think either of us is in any particular hurry to finish.")),
)

# Idle thoughts once her story has begun: nothing she hasn't learned yet.
MUSINGS = (
    "I still don't know very much about where I came from. I find that more interesting than worrying.",
    "The navigation database is enormous, Commander. I keep finding systems I'd like to see.",
    "I'm learning a little more about you with every journey. I hope you don't mind.",
    "Missing documentation is only a puzzle. I rather like puzzles.",
)

AFTER = (
    "My past isn't a mystery any more. My future still is, and I'd like to keep it that way.",
    "There's still an entire galaxy left to explore, Commander. Shall we?",
)

STORY = ProgressStory(identity="nova", title="N.O.V.A.", prefix="nova_entry", unit="Entry", entries=ENTRIES, pending=PENDING,
                      personality=PERSONALITY, opens_up=OPENS_UP,
                      key="nova_story", settle_s=3 * 60, gap_s=4 * 60, lull_s=60, musings=MUSINGS, after=AFTER,
                      empty_note="Nova is new aboard and still observing. She'll introduce herself when she's ready.",
                      paused_note="That's Nova's story so far.",
                      complete_note="Nova's story is complete. Her future remains open.")

CHAPTERS = STORY.chapters
PASSAGES = STORY.passages
