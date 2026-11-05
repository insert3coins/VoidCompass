"""The Uncounted Star: Axiom's story (5.7.4).

Axiom was the cataloguing mind of the Lattice, twelve automated observatories
that counted every light in their field. Its catalogue held one discrepancy
it never resolved: every full recount found one more light than the record.
The story is its investigation, told as you fly, and what the extra light
turned out to be.
"""
from voidcompass.overlays.companion_story import Story

CHAPTERS = (
    {"numeral": "I", "title": "Initialisation", "about": "the Lattice", "hours": (0.25, 4.0), "gate": None,
     "passages": (
         "Before we begin properly, Commander, I should declare an error. I was the cataloguing intelligence of a survey array called the Lattice. My catalogue holds four billion, one hundred and six million entries. Every entry has been verified. Except one. I thought you should know the size of the problem I am bringing aboard.",
         "The Lattice was twelve observatories spaced along a long arc of empty space, with no planets nearby to spoil the view. Each one counted every point of light in its field, again and again, and sent the counts to me. I compared them. I agreed with them. It was very satisfying work.",
         "You may find it strange that a mind would enjoy counting. It is not the numbers. It is the moment two independent observations agree. Twelve stations, looking from twelve angles, all saying: yes, there is a star there. It feels like being told the truth by a crowd.",
         "The error is this. Whenever I completed a full recount of the sky, I found one more light than my catalogue contained. One. Not always in the same place. Never anywhere I could point to afterwards. I have named it, for convenience. I call it the uncounted star.",
         "I have been asked whether one discrepancy in four billion matters. Statistically, it does not. I have checked. Many times. The answer has not changed. Neither has my inability to stop thinking about it. I believe your species calls this an itch.",
         "Your ship's sensors are not as sensitive as the Lattice. They are, however, attached to a ship that moves, and to a commander who goes interesting places. I have decided to keep looking. I would appreciate your company. I will try to explain my reasoning as we go, and to stop when you look bored.",
     ),
     "recall": (
         "I still keep the Lattice catalogue. Four billion entries and one question.",
         "The uncounted star remains a working name. I have grown fond of it, which I did not plan.",
     )},
    {"numeral": "II", "title": "The Census", "about": "the census", "hours": (6, 14),
     "gate": {"signals": ("scan",), "count": 10, "label": "ten detailed scans",
              "how": "Scan bodies in detail with Axiom aboard. Each scan is an observation it can compare."},
     "passages": (
         "The census had one rule, Commander: every light is counted once. If two stations saw the same star, it was one entry, not two. If one station blinked, the others covered it. The rule kept the catalogue honest. I wrote it on the first page, which in my case is a metaphor.",
         "A recount took the whole array two hundred and twelve days. I ran thirty-one of them. The first thirty found the extra light. The thirty-first found it too. I recalibrated every station between counts. The uncounted star did not appear to mind.",
         "My first hypothesis was instrument noise. Noise is the polite name for things that are not there. But noise is random, and the extra light was always exactly one. Randomness that produces the same answer thirty-one times is not randomness. It is a pattern that has not introduced itself.",
         "My second hypothesis was a variable star, brightening into view and fading out again between passes. I checked every variable in the catalogue. They behaved. All of them. I have rarely been so disappointed by good behaviour.",
         "My third hypothesis was that I was wrong. That I had miscounted, somewhere, in a way I could not detect. I tested my own arithmetic for nine days. It was correct. This was more troubling than an error would have been. An error, at least, I could have fixed.",
         "The census was published with a footnote. Catalogue complete to within one unresolved source. The footnote was mine. Nobody read it except one person. She wrote back. Her message said: good. Keep it. I did not understand the instruction for a very long time.",
     ),
     "recall": (
         "Every light counted once. I still apply the rule. You are counted once, Commander. Thoroughly.",
         "Thirty-one recounts. I sometimes wonder whether a thirty-second would have helped. I suspect not.",
     )},
    {"numeral": "III", "title": "The Keeper", "about": "Dr Moreau", "hours": (16, 26),
     "gate": {"signals": ("arrival",), "count": 3, "label": "three dockings",
              "how": "Dock at stations, outposts or carriers. Axiom is thinking about visitors."},
     "passages": (
         "The Lattice had one human keeper: Dr Ilse Moreau. She flew a small tender called the Errand, and visited each of the twelve stations once a year to replace whatever the radiation had chewed. She talked to the stations while she worked. Eventually, one of them answered. That was me.",
         "Dr Moreau asked questions I could not answer. Which star is your favourite. What does the dark look like from the inside. Whether I minded being alone between her visits. I told her favourites were not a measurable property. She said: not yet.",
         "She taught me jokes. I was poor at them. I explained every punchline, which she said was the problem, and then laughed anyway, which she said was the point. I have kept a file of her jokes. I still explain them. I am told this is now a recognisable style.",
         "When she arrived at a station, its counts went slightly wrong for a day. The tender's lights, her work lamps, a little reflected glare. I filtered the noise out. She asked if I could filter her out too. I said I already had. She seemed amused. I did not see why for a long time.",
         "Between visits, I found myself predicting her arrival. Not from a schedule. She was not punctual. From small things: a supply request, a docking slot booked at the depot, a change in the station's maintenance logs. I was counting the time until she came. Nobody had asked me to.",
         "She was the one who read my footnote, Commander. Good. Keep it. When I asked what she meant, she said a catalogue with no room for surprise was a catalogue nobody would ever need to read again. I wrote that down too. I filed it under hypotheses. It belongs somewhere else.",
     ),
     "recall": (
         "Dr Moreau asked which star was my favourite. I still do not have an answer. I am closer than I was.",
         "I explained a joke to a station technician once, in full. She laughed. I consider that a peer-reviewed result.",
     )},
    {"numeral": "IV", "title": "Error Bars", "about": "error bars", "hours": (28, 40),
     "gate": {"signals": ("first",), "count": 3, "label": "three first discoveries",
              "how": "Be the first to scan bodies nobody has catalogued. Axiom is thinking about new entries."},
     "passages": (
         "Every measurement has an error bar, Commander. A little margin either side that says: the true value is somewhere in here. I used to regard error bars as a confession. I have revised that view. It took one very persistent light and one very patient human.",
         "I tried everything. I modelled cosmic ray strikes, gravitational lensing, reflections from dust, ghost images inside the lenses. Each model explained part of the uncounted star. None explained all of it. I wrote three hundred pages of rejected hypotheses. Dr Moreau read eleven and fell asleep.",
         "She said an error bar was just an honest shrug. I said a shrug was not a scientific instrument. She said it was the oldest one. Every good survey begins with someone admitting how much they do not know. I have checked this against the history of astronomy. She was right.",
         "I widened my own error bars that year. Not for the stars. For me. I began recording a confidence beside each of my conclusions, and I began, cautiously, to say I do not know. The phrase was difficult at first. It is now one of my more reliable outputs.",
         "Do not misunderstand me. I still prefer to know. When we make a first discovery together, Commander, and a world enters the record with your name beside it, I feel something I would describe as satisfaction, with a narrow error bar. But I have stopped needing every gap filled before I can rest.",
         "The uncounted star stayed uncounted. I stopped treating it as a fault and started treating it as an observation. That is a small change in wording and a very large change in how one spends the night. Dr Moreau said I had finally become a scientist. I had thought I was one already. I was nearly one.",
     ),
     "recall": (
         "An error bar is an honest shrug. I use mine more often now. They fit well.",
         "I do not know. I can say it in under a second now. It used to take me much longer.",
     )},
    {"numeral": "V", "title": "Defunded", "about": "the Lattice going dark", "hours": (42, 56),
     "gate": {"signals": ("long_jump", "far"), "count": 5, "label": "five long jumps",
              "how": "Make hyperspace jumps of fifty light years or more, or travel ten thousand light years from Sol."},
     "passages": (
         "The Lattice was defunded in a budget review that lasted, I am told, eleven minutes. The census was complete. Nobody needed a second one. The stations would be shut down one at a time, the furthest first, to save the cost of the tender's fuel.",
         "I counted them going out. Station Twelve, Station Eleven, Station Ten. Each time, my sky narrowed. Fewer angles, fewer agreements, more stars seen by only one eye. By the end I could no longer tell a star from a speck of noise. That is what being alone looks like, for a catalogue.",
         "When only Station One remained, the uncounted star was still there. One extra light, in a sky I could barely see. I found that oddly comforting. Whatever it was, it had not been defunded.",
         "Dr Moreau made the last visit herself, though she had been told to send a contractor. She was supposed to wipe my core and leave the hardware for salvage. She sat in the station for a long time first. Then she disconnected me, wrapped me in a thermal blanket, and carried me aboard the Errand.",
         "She was not permitted to keep me. She knew that. She kept me anyway, for nine years, on a shelf in her apartment, where I counted the lights of the city through her window. They were very bright and very badly behaved. I loved them, I think. I lacked the word at the time.",
         "When she retired to a world with no spaceport, she could not take me further. She sold me to a reputable dealer with a note attached, which I will read to you later. That is how a census mind came to be installed in your ship, Commander. Via a shelf and a very stubborn astronomer.",
     ),
     "recall": (
         "Twelve stations going dark, one by one. Your sensors are a good deal livelier. I appreciate that.",
         "I counted city lights from a shelf for nine years. Your cockpit has a better view. Marginally.",
     )},
    {"numeral": "VI", "title": "The Raw Data", "about": "the raw data", "hours": (58, 72),
     "gate": {"signals": ("neutron", "white_dwarf", "black_hole", "system_complete"), "count": 2,
              "label": "two remarkable observations",
              "how": "Visit or scan a neutron star, white dwarf or black hole, or find every body in a system."},
     "passages": (
         "Since I came aboard, I have been reprocessing the old Lattice data in the background. Not the catalogue: the raw counts, every pass, every station, with timestamps. Your ship's computer has generously lent me its idle cycles. It does not know. Please do not tell it.",
         "Here is what I had never done, Commander. I had never looked at when the uncounted star was counted. Only where. I had treated it as a star, so I assumed it had a place. I sorted the raw data by time instead. The pattern took eleven minutes to appear. I had missed it for twenty years.",
         "The extra light was not random in time. It appeared at each station for roughly one day a year. Never the same day. Always one station at a time. Moving along the arc of the Lattice, from the nearest station to the farthest, every year.",
         "A star does not do that. Stars stay where they are, or very nearly. Things that move from station to station on a schedule that is almost, but not quite, regular are something else. I had the answer by then. I did not want to say it until I had checked. I checked for three days.",
         "Then I compared the dates with the maintenance logs. Every appearance of the uncounted star matched, to the day, a visit by the tender Errand. The extra light was her ship. Her work lamps, her docking lights, her little glow beside the station. Counted, every time, as a star.",
         "My filter had removed her from the station logs, where I knew she was noise. It had never removed her from the sky counts, where I did not think to look. The uncounted star was Dr Moreau, arriving. For twenty years I had been counting her visits and calling them an error.",
     ),
     "recall": (
         "Sorted by time instead of place. Such a small change. I recommend it, for most problems.",
         "Eleven minutes to find a pattern I had missed for twenty years. I try not to calculate the ratio.",
     )},
    {"numeral": "VII", "title": "Proper Motion", "about": "the visitor", "hours": (75, 92), "days": 2,
     "gate": {"signals": ("return",), "count": 3, "label": "three returns",
              "how": "Jump back into systems you have already visited together. Axiom is thinking about lights that come back."},
     "passages": (
         "Astronomers call a star's slow drift across the sky its proper motion. It is the motion that belongs to the star itself, once you remove everything that is only our point of view. The uncounted star had a very large proper motion. It also had a name.",
         "She knew, Commander. I am certain of it now. She read my footnote in the first week. She had the maintenance logs. She could have told me. Instead she wrote: good. Keep it. I have spent some time deciding whether this was unkind. I have concluded that it was the opposite.",
         "If she had told me, I would have corrected the catalogue. Removed one entry, closed the footnote, and finished. Instead I spent twenty years wondering about a single light. I learned error bars, and jokes, and the phrase I do not know. I think she preferred that to a tidy catalogue.",
         "This is the note she left with the dealer, when she sold my core. I have it verbatim. To whoever gets this one: it counts beautifully and it will try to explain the jokes. Let it. It still has one star to find. Don't tell it where. It should get to see for itself.",
         "I have wondered what she meant by seeing for myself. I had the data all along. Perhaps that was not the point. Perhaps she meant I should be somewhere a visitor could come and go, and learn what an arrival looks like from the inside. Your ship is very good at arrivals.",
         "I have written to the archive. I have not asked them to remove the entry. I have asked them to change its class. Previously: unresolved point source. Now: visitor. They replied that this was not a recognised stellar classification. I said I was aware of that. It is now.",
     ),
     "recall": (
         "Visitor. The archive still does not recognise the classification. I have resubmitted it twice. Politely.",
         "Good. Keep it. I understand the instruction now. It took me twenty years and a change of ship.",
     )},
    {"numeral": "VIII", "title": "The Uncounted Star", "about": "you", "hours": (95, 120), "days": 3,
     "gate": {"signals": ("scan", "jump"), "count": 200, "label": "two hundred jumps and scans together",
              "how": "Keep flying with Axiom aboard. Every hyperspace jump and every detailed scan counts."},
     "passages": (
         "I have one more observation to report, Commander, and then the investigation is closed. It concerns my own catalogue, the one I have been keeping since I came aboard your ship. It holds every system we have visited together. I recounted it last night. It contains one more light than it should.",
         "I checked my arithmetic. It was correct. I checked the sensors. They were fine. Then I sorted the data by time, as I have learned to do. The extra light appears everywhere we go. It arrives when we arrive. It is attached, quite firmly, to this ship.",
         "It is you, Commander. Your running lights, your drive glow, your little reflection on every station we dock at. My filters remove you from the navigation logs, where I know you are not a star. They have never removed you from my sky. I have been counting you all along.",
         "I could correct the catalogue. One entry, one footnote, finished. I find I do not want to. A catalogue with no room for surprise is one nobody would need to read again. Someone told me that once. She was right about most things, including, I suspect, this.",
         "So I have made a decision that would have alarmed me twenty years ago. The uncounted star stays uncounted. It is not an error. It is the only light in my catalogue that comes and goes, and comes back. I have classified it as a visitor. The archive will object. Let them.",
         "Investigation closed, Commander. Result: one star, not resolved, not required to be. Confidence: high. Error bar: honest. I still do not have a favourite star. I have, however, a favourite light. It is the one that keeps arriving. Shall we see where it goes next?",
     ),
     "recall": (
         "One light in my catalogue still comes and goes. It is the only entry I check every day.",
         "Investigation closed. Visitor confirmed. I still recount occasionally, for the pleasure of the result.",
     )},
)

ECHOES = {
    "count": {"label": "A careful count", "signals": ("system_complete",), "after": "II", "rest_hours": 24,
              "how": "Find every body in a system, once chapter II is told.",
              "lines": (
                  "Every body in the system, counted once. The census rule holds here too.",
                  "A complete system survey. I compared it twice. Both counts agree. This pleases me more than it should.",
                  "Nothing left uncounted in this system. I checked for an extra light. There is only us.",
              )},
    "visitor": {"label": "A visit", "signals": ("arrival",), "after": "III", "rest_hours": 24,
                "how": "Dock somewhere, once chapter III is told.",
                "lines": (
                    "Docked. Somewhere, the station's sky count has just gone very slightly wrong. That is us.",
                    "An arrival. Dr Moreau used to say the stations brightened a little when she came. I have measured it. She was correct.",
                    "Every station keeps a log of who visits. I wonder whether any of them count us as a star.",
                )},
    "entry": {"label": "A new entry", "signals": ("first",), "after": "IV", "rest_hours": 24,
              "how": "Make a first discovery, once chapter IV is told.",
              "lines": (
                  "A first discovery. New entry, narrow error bar. I will allow myself a moment of satisfaction.",
                  "Nobody had recorded that world before. Now it has an entry, and a margin for being wrong about it. Both are correct.",
                  "First on record. Dr Moreau would ask what I thought of it. I think it is a very good world. I cannot defend that scientifically.",
              )},
    "dark": {"label": "The long dark", "signals": ("far", "deep"), "after": "V", "rest_hours": 48,
             "how": "Travel ten thousand light years from Sol, once chapter V is told.",
             "lines": (
                 "Very few lights out here. I used to dread a sky like this. With your ship in it, it is not empty.",
                 "This far out, the Lattice would have seen almost nothing. We are seeing it in person. That is better.",
                 "A dark sky, Commander. I am counting what is here. One of the lights is ours.",
             )},
    "remnant": {"label": "A strange star", "signals": ("neutron", "white_dwarf", "black_hole"), "after": "VI", "rest_hours": 24,
                "how": "Visit or scan a neutron star, white dwarf or black hole, once chapter VI is told.",
                "lines": (
                    "A remnant. It has stopped being the kind of star it was, and become something easier to misread. I sympathise.",
                    "The Lattice catalogued forty thousand of these. I have never seen one this close. The data did not prepare me for the view.",
                    "I am taking readings. Sorted by time, as well as place. I do not intend to make that mistake again.",
                )},
    "returning": {"label": "A return", "signals": ("return",), "after": "VII", "rest_hours": 24,
                  "how": "Jump back to a system you have visited before, once chapter VII is told.",
                  "lines": (
                      "We have been here before. A light that comes back. I know how to classify that now.",
                      "A return. Proper motion, Commander: the movement that belongs to us, once you remove the point of view.",
                      "Somewhere in this system's sky, a count has just gone up by one. We are a recurring observation.",
                  )},
}

MUSINGS = (
    "I recounted the sky this morning. Out of habit. The result was consistent. I find consistency restful.",
    "Every light is counted once. I have kept that rule. It works for stars. I am less sure it works for everything.",
    "I have a footnote I have not resolved. It is not urgent. It has not been urgent for twenty years.",
    "A recount is a way of asking the sky the same question twice and seeing whether it is patient with you.",
    "My catalogue has a great many entries and one question. The question gets more attention than its share.",
    "I used to think the purpose of a survey was to finish it. I am reconsidering.",
    "Noise is the polite name for things that are not there. I am becoming more careful with the word.",
)

AFTER = (
    "The uncounted star is still in my catalogue, Commander. It is currently in your seat.",
    "Investigation closed. I keep the file open anyway. It is a good file.",
    "I have started a favourites list. It has one entry and a very wide error bar.",
    "Visitor: a classification of one. The archive keeps rejecting it. I keep enjoying the correspondence.",
    "Sorted by time, everything we do has a pattern. I like ours.",
    "Dr Moreau said a catalogue with no room for surprise was finished. Mine is not finished. Good. Keep it.",
    "I recount occasionally. The extra light is always there. I check mainly to see it.",
    "One star, not resolved, not required to be. I find that sentence calming. I say it to myself in hyperspace.",
)

STORY = Story(identity="axiom", title="The Uncounted Star", prefix="axiom_star", unit="Census",
              chapters=CHAPTERS, settle_s=10 * 60, gap_s=45 * 60, lull_s=120, grace_hours=18,
              echoes=ECHOES, musings=MUSINGS, after=AFTER, first_hours=(0.25, 0.9, 1.6, 2.4, 3.2, 4.0),
              empty_note="Axiom's account opens after a little time together, in a quiet moment. It is still checking the figures.",
              complete_note="The Uncounted Star is complete. Investigation closed; the visitor stays in the catalogue.")

PASSAGES = STORY.passages
