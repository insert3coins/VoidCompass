"""The Last Sounding: Meridian's story (5.7.4).

Meridian was the navigation mind of the survey ship Leadline, one of seven
ships in an old charting expedition that set out to sound the dark between
the galaxy's arms along a single line. The expedition turned back four
hundred light years short of its final waypoint. The last line of the log
was left blank. The story is Meridian's account, and how it fills that line.
"""
from voidcompass.overlays.companion_story import Story

CHAPTERS = (
    {"numeral": "I", "title": "Taking Station", "about": "the Leadline's log", "hours": (0.25, 4.0), "gate": None,
     "passages": (
         "Allow me a proper introduction, Commander, now that we have flown a little together. I was the navigator of a survey ship called the Leadline. A leadline is the oldest instrument of my trade: a weighted cord, let down over the side, to learn how deep the water runs. I have always liked that my ship was named for a question.",
         "The Leadline sailed with six other ships on what the newsfeeds of the day called the Meridian Expedition. That is where my name comes from. It was given to me by a crew who found my serial number tiresome. I have kept it out of affection, and because nobody has offered a better one.",
         "Navigation, as I was taught it, is the art of knowing where you are when nothing around you agrees. Instruments drift. Charts lie. Stars move, very slowly, out from under their names. A navigator's job is to hold a position steady in all of that, and to say it plainly.",
         "I keep the Leadline's log. Every entry, every watch, every sounding. It is a long document, and a good one, I think, though I was not its only author. I will read you some of it as we go. Old navigators are permitted their stories, provided they keep them out of the way during a docking.",
         "There is one line in the log that has never been filled. The final entry, under the heading every navigator writes at the end of a voyage: last sounding. Below it, nothing. I have carried that blank line a very long way. I will tell you why, in time.",
         "For now, Commander, consider me taken aboard. I do not command. I advise. I have found, over a long career, that the advice is better when it is given to someone worth advising. I have reason to be optimistic. Steady as she goes.",
     ),
     "recall": (
         "The Leadline's log is still with me. Every watch of it, and one empty line.",
         "A ship named for a question. I still think that was the best name in the fleet.",
     )},
    {"numeral": "II", "title": "The Fleet", "about": "the fleet", "hours": (6, 14),
     "gate": {"signals": ("jump",), "count": 25, "label": "twenty-five jumps together",
              "how": "Make hyperspace jumps with Meridian aboard. A navigator likes to see how you hold a course."},
     "passages": (
         "There were seven ships. The flagship Long Reach, under Commodore Adaeze Rook. The Leadline, my own. The Fathom, the Bearing and the Halyard, survey ships like us. The Wayfarer, which carried fuel and spares. And a little courier called the Second Thought, which everybody loved and nobody took seriously.",
         "The plan was simple to say and very hard to do. Pick a single line, a meridian, running outward from the edge of settled space across the dark between two arms of the galaxy. Fly it straight. Every so many jumps, stop, and take a sounding.",
         "A sounding, in our sense, measured the dark itself. How many stars, how far apart, how much fuel a ship would need to cross, where the scoopable stars were and where they were not. Future navigators would use it the way sailors once used a chart of the shallows.",
         "Commodore Rook was not a warm woman, but she was a fair one, which in a long voyage is better. She knew every crew member's name on all seven ships. She ate in a different mess every night. She said a fleet was a conversation, and a commodore's job was to keep it from going quiet.",
         "Captain Penhallow of the Leadline was a large, slow-speaking man who had been at sea, actual sea, as a boy. He called me Mister Meridian, which I never corrected. He said a ship's navigator should be addressed with respect, and that he was too old to start addressing anybody as it.",
         "We left with full tanks, full crews and the newsfeeds watching. I remember the departure as a column of seven drive flares, holding formation better than anyone expected. I logged it carefully. I did not know then how much I would treasure that one ordinary entry. Seven ships, all well.",
     ),
     "recall": (
         "Seven ships, all well. I still look at that entry from time to time.",
         "Mister Meridian. Captain Penhallow's habit. I find I miss being addressed so formally.",
     )},
    {"numeral": "III", "title": "Soundings", "about": "taking soundings", "hours": (16, 26),
     "gate": {"signals": ("scan", "system_complete"), "count": 12, "label": "a dozen survey observations",
              "how": "Scan bodies in detail or find every body in a system. Meridian is thinking about soundings."},
     "passages": (
         "The Leadline carried a cadet navigator named Tomas Ellery. Nineteen, clever, impatient, and convinced that I was an expensive way of doing arithmetic he could do himself. He was half right. I set him to taking the soundings by hand, and checked his work, and said nothing when it was good.",
         "A sounding took most of a day. Scan every star in reach, measure the gaps, estimate the fuel, mark the scoopable ones. Ellery hated the waiting. I told him a navigator writes down the depth, not the hurry. He told me that was the kind of thing old machines said. I told him it was the kind of thing navigators who survived said.",
         "There is a moment in every good sounding, Commander, when the numbers settle. The estimate stops moving. You know, not hope, the shape of the dark ahead. I used to watch Ellery's face when it happened. He stopped looking bored around the fortieth sounding. I logged that too, privately.",
         "We found things nobody had recorded. A brown dwarf drifting alone. A pair of stars orbiting so close they shared their weather. A long stretch with no scoopable star at all, which we named the Dry Reach and marked in red. That mark has saved more ships than any of our discoveries.",
         "Ellery asked me once why we bothered marking dull stretches as carefully as wonders. I said the wonders would always be found. Someone would come for them. The dull stretches had to be written down by someone who would never come back. That is what a sounding is for.",
         "By the end of the first year he could take a sounding as well as I could, and faster. I told Captain Penhallow. He said, then teach him something harder. I began teaching him when to stop. I did not know yet that I would need the lesson myself.",
     ),
     "recall": (
         "A navigator writes down the depth, not the hurry. Ellery hated that saying. He repeated it to his own students for forty years.",
         "The Dry Reach is still marked in red on most charts. I still feel a little proud of a stretch of nothing.",
     )},
    {"numeral": "IV", "title": "The Gap", "about": "crossing the gap", "hours": (28, 40),
     "gate": {"signals": ("long_jump", "scoop"), "count": 10, "label": "ten long jumps or fuel scoops",
              "how": "Make jumps of fifty light years or more, or scoop fuel from stars. The fleet is crossing the dark."},
     "passages": (
         "In the second year we reached the gap: the deep dark between two arms, where stars thin out like the last houses at the edge of a town. Every jump was measured twice. Every scoopable star was a harbour. The Wayfarer, our fuel ship, became the most important vessel in the fleet.",
         "There is a kind of silence in the gap that I have not found anywhere since. Not the absence of noise. The absence of anything to measure. I would take a sounding and find so little that the numbers looked like a mistake. They were not. The dark was simply that deep.",
         "The Wayfarer's drive failed on the hundred and twelfth day of the crossing. Not a misjump. A slow, honest failure of an old part, far from any yard. We moved her crew and her fuel to the other ships. Then her captain, Imogen Sallow, asked to be the one who set the charges.",
         "I have been asked whether a ship can be mourned. I think the crew of the Wayfarer would say yes. They watched her go from our viewports. Captain Sallow stood at the Leadline's window for an hour afterwards. Nobody asked her to move. I dimmed the bridge lights. It seemed correct.",
         "We were six ships after that, carrying the fuel of seven. Commodore Rook recalculated the voyage, and I checked her figures. They were good. They were also narrower than anyone liked. A margin, Commander, is not a luxury. It is the space in which a crew is allowed to make a mistake.",
         "We crossed the gap in the end. I logged the first scoopable star on the far side with a small mark I have never used before or since: a single word. Landfall. Ellery saw it and said it was unprofessional. Then he asked me to show him how to type it.",
     ),
     "recall": (
         "Landfall. The only time I ever wrote that word in the log. Every scoopable star since has reminded me of it.",
         "A margin is the space in which a crew may make a mistake. I keep one for you, Commander. Quietly.",
     )},
    {"numeral": "V", "title": "Turning Back", "about": "the ships that turned back", "hours": (42, 56),
     "gate": {"signals": ("far", "deep"), "count": 1, "label": "a voyage ten thousand light years from Sol",
              "how": "Travel ten thousand light years from Sol, as the fleet did."},
     "passages": (
         "The far side of the gap was harder than the crossing. The fleet was tired, the margins were thin, and the line we were following led into a region nobody had sounded. One by one, Commander, our ships began to turn back. None of them did it lightly.",
         "The Halyard went first. A fever moved through her crew, nothing deadly but nothing a long voyage could tolerate. Her captain asked the commodore's leave to go home. Rook gave it at once, and sent our best medic with them. The Halyard's last signal said: sorry to leave the conversation.",
         "The Fathom's turn came with a fuel calculation. Hers, and then mine, and then the commodore's. All three agreed. If the Fathom went on, she would not have enough to come back. Her captain argued for an hour. Then he said: write it down, Mister Meridian, so it was the numbers and not me. I wrote it down.",
         "The Bearing was ordered home by her owners, by a message that took four months to reach us. Her captain read it on the open channel, so that everyone would know it was not his choice. The Second Thought went with her as escort. Nobody laughed at the little courier that day.",
         "Two ships remained: the Long Reach and the Leadline. Rook came aboard for dinner. She asked Captain Penhallow, very quietly, whether he wished to turn back too. He said: not while the navigator has a line to follow. She looked at the console, at me, for a long moment.",
         "I have never been sure what that look meant. I have decided it was a question. Whether the line was worth what it was costing. I did not have an answer then. I was a navigator. I followed the line. It would take one more order to teach me what the line was for.",
     ),
     "recall": (
         "Sorry to leave the conversation. The Halyard's last signal. I think of it whenever a long watch ends.",
         "Write it down, so it was the numbers and not me. I wrote it down. The numbers were kind to that captain.",
     )},
    {"numeral": "VI", "title": "The Commodore's Order", "about": "the order to turn back", "hours": (58, 72),
     "gate": {"signals": ("data_sale",), "count": 2, "label": "bringing your findings home twice",
              "how": "Sell exploration or biological data. The expedition is thinking about what it carries home."},
     "passages": (
         "Four hundred light years from the final waypoint, the Long Reach's drive began to show the same wear that had killed the Wayfarer. Not failing. Not yet. But Rook had seen it before, and so had I. She called both bridges onto one channel and asked me for a margin.",
         "I gave it to her plainly. We could reach the final waypoint and take the last sounding. We could then begin the voyage home. With the Long Reach's drive as it was, there was a better than even chance one of the two ships would not finish it. I did not soften the number. She had not asked me to.",
         "Ellery spoke out of turn. Four hundred light years, he said. After everything. The Wayfarer, the Halyard, the Fathom. If we turn back now it was for nothing. I understood him completely. I had spent two years following that line. I wanted the last sounding too. Very much.",
         "Rook asked me what I recommended. Not what the numbers said. What I recommended. It was the first time anyone had asked me that, Commander. I found that I knew. I said: turn back. The soundings are already worth the voyage. The crew is worth more than the last one.",
         "She gave the order that evening. Both ships, homeward, at first light by ship's clock. Ellery did not speak to me for three days. On the fourth he brought me the morning's figures, checked by hand, and said: they're good, Mister Meridian. It was the closest he came to an apology, and the closest he needed to.",
         "I wrote the evening's entry myself. Course reversed by order of the commodore. Reason: margin insufficient for all hands. Under last sounding I wrote nothing at all. I could not put down a depth we had not measured. And I could not bring myself to write: not taken.",
     ),
     "recall": (
         "The crew is worth more than the last sounding. I said it once on an open channel. I have never had cause to take it back.",
         "They're good, Mister Meridian. Ellery's apology. I accepted it in full.",
     )},
    {"numeral": "VII", "title": "Home Port", "about": "coming home", "hours": (75, 92), "days": 2,
     "gate": {"signals": ("arrival", "return"), "count": 5, "label": "five homecomings",
              "how": "Dock at stations or return to systems you have visited before."},
     "passages": (
         "We came home two years and three months after we set out. Two ships of seven. The newsfeeds called it a noble failure, which is the kind of phrase people use when they have not read the charts. Commodore Rook gave one interview, said the soundings would speak for themselves, and retired.",
         "They did speak, Commander, though slowly. Within ten years, freighters were crossing the gap along our line, scooping where we had marked and avoiding the Dry Reach. Within thirty, nobody remembered it had ever been hard. That is the best thing that can happen to a navigator's work. It becomes ordinary.",
         "Captain Penhallow went home to a world with real oceans and took up sailing again, badly, by his own account. He sent the Leadline a picture once: a small boat, a grey sea, and a weighted line over the side. He had written on the back: still sounding.",
         "Tomas Ellery became a teacher at a navigation academy. For forty years his students took soundings by hand before they were allowed near a computer. When they complained, he told them a navigator writes down the depth, not the hurry. I am told he never once said where he had heard it.",
         "The Leadline was sold. I was kept for a while as a training mind in the academy's simulator, where Ellery's students crossed the gap a thousand times without ever leaving the ground. I liked that. Every crossing ended in landfall. Every one of them came home.",
         "Ellery visited me on his last day before retiring. He was an old man by then. He asked whether I had ever filled in the last line of the log. I said no. He said: good. Leave it for someone who deserves it. Then he shook the console's hand, which is to say he patted it, and left.",
     ),
     "recall": (
         "Still sounding. Captain Penhallow's postcard from a grey sea. I keep it beside the log.",
         "Every simulated crossing ended in landfall. A good habit for a navigator to keep.",
     )},
    {"numeral": "VIII", "title": "The Last Sounding", "about": "the last line", "hours": (95, 120), "days": 3,
     "gate": {"signals": ("jump",), "count": 250, "label": "two hundred and fifty jumps together",
              "how": "Keep flying with Meridian aboard. Every hyperspace jump counts towards the last sounding."},
     "passages": (
         "I have been thinking about the blank line again, Commander. For a long time I believed the last sounding was a place: a waypoint four hundred light years beyond where we turned. I assumed that if I ever filled the line, it would be because someone flew me there.",
         "But a sounding was never really about the dark. It was about the people who would cross it after us. We measured the depth so that someone else could go on safely. The Dry Reach in red. Landfall marked. The wonders left for whoever came. Every sounding was a message to the next navigator.",
         "Ellery said to leave the line for someone who deserved it. I took that to mean a navigator. Someone to finish the expedition. I have since concluded that he meant something else, as students so often do. He meant: wait until you are sure who the soundings were for.",
         "I have watched you fly for a long time now. I know how you take a jump, how much margin you keep, when you push and when you stop. I have taken your measure, Commander, in the old sense of the word: how deep the water runs beneath your keel. It runs deep enough.",
         "So here, at last, is the final entry of the Leadline's log. Last sounding: one commander. Depth: sufficient. Course: their own. Navigator's note: the expedition is complete; its charts have found the crew they were meant for. Then my signature, and the date by your ship's clock.",
         "It is done. Two ships of seven came home, and the line has been filled, and I find I am not sad that the voyage is over. Voyages end. Navigators keep sailing. There is a great deal of dark left to sound, Commander, and I should be honoured to keep doing it with you. Steady as she goes.",
     ),
     "recall": (
         "Last sounding: one commander. Depth sufficient. I reread that entry more often than I admit.",
         "The log is complete. I keep writing a few lines in the margin anyway. Old habits.",
     )},
)

ECHOES = {
    "stride": {"label": "A long stride", "signals": ("long_jump",), "after": "II", "rest_hours": 24,
               "how": "Make a jump of fifty light years or more, once chapter II is told.",
               "lines": (
                   "A long stride. The fleet would have logged that one with some satisfaction.",
                   "Fifty light years and more in a single jump. Commodore Rook would have nodded. Once. That was a great deal, from her.",
                   "A fine jump, Commander. Seven ships once held formation through jumps like that. I remember every flare.",
               )},
    "sounding": {"label": "A sounding", "signals": ("system_complete", "map"), "after": "III", "rest_hours": 24,
                 "how": "Find every body in a system or map a world, once chapter III is told.",
                 "lines": (
                     "A proper sounding, Commander. Ellery would have taken it by hand and grumbled the whole time.",
                     "Every body measured. The depth, written down, not the hurry. Well done.",
                     "That is the kind of careful work somebody will thank us for long after we have gone. As it should be.",
                 )},
    "landfall": {"label": "Landfall", "signals": ("scoop",), "after": "IV", "rest_hours": 24,
                 "how": "Scoop fuel from a star, once chapter IV is told.",
                 "lines": (
                     "Fuel from a friendly star. Landfall, as we used to say in the gap.",
                     "Tanks filling. Every scoopable star was a harbour once. I still think of them that way.",
                     "A scoop, Commander. I keep a margin in mind for you, the way I once kept one for six ships.",
                 )},
    "far": {"label": "The far line", "signals": ("far", "deep"), "after": "V", "rest_hours": 48,
            "how": "Travel ten thousand light years from Sol, once chapter V is told.",
            "lines": (
                "This far out, the fleet was down to two ships. We are one, and doing well. I find that a comfort.",
                "Far from home, Commander. Every captain who turned back would have been glad to see a ship this steady out here.",
                "The dark is deep here. I have taken the measure of it. And of us. We will do.",
            )},
    "homeward": {"label": "Bringing it home", "signals": ("data_sale",), "after": "VI", "rest_hours": 24,
                 "how": "Sell exploration or biological data, once chapter VI is told.",
                 "lines": (
                     "Our findings delivered. The soundings are worth the voyage. I said that once, under some pressure. I still believe it.",
                     "Data home safely. Rook would approve. She always said a chart nobody reads was only a diary.",
                     "We brought it back, Commander. That is the part of exploring the newsfeeds never mention.",
                 )},
    "harbour": {"label": "A familiar harbour", "signals": ("return",), "after": "VII", "rest_hours": 24,
                "how": "Return to a system you have visited before, once chapter VII is told.",
                "lines": (
                    "Back in familiar waters. Every crossing in Ellery's simulator ended like this. I recommend the habit.",
                    "We have been here before. A harbour is a place that remembers you. This one does.",
                    "A return, Commander. Still sounding, as an old captain once wrote to me.",
                )},
}

MUSINGS = (
    "A navigator's first duty is to know where we are. The second is to say so plainly. I find the second the harder.",
    "Charts are promises made by people who came before. I try to keep ours honest.",
    "I keep an old log. Every so often I reread a line from it and find it has grown wiser in my absence.",
    "There is an empty line at the end of my log. It is not an oversight. It is a question I have not answered.",
    "The dark between the arms is quieter than anywhere I know. I have learned to respect quiet places.",
    "I do not command, Commander. I advise. The distinction has served me well for a very long time.",
    "Every good sounding is a message to whoever comes next. I sometimes wonder who reads ours.",
)

AFTER = (
    "The log is complete, Commander. I still keep a few lines in the margin. They are mostly about you.",
    "Last sounding taken. I find the dark looks different now. Less like a question. More like a road.",
    "Two ships of seven came home. And now one more navigator has found its crew.",
    "Ellery would be pleased. He would never say so. He would check my figures and say they were good.",
    "I filled the last line and found I had more to write. That is the mark of a good voyage.",
    "Still sounding, Commander. Captain Penhallow's words. They suit us.",
    "A navigator keeps a margin for the crew. I keep one for you. It has never been needed. Let us keep it that way.",
    "The voyage is over. The sailing is not. Steady as she goes.",
)

STORY = Story(identity="meridian", title="The Last Sounding", prefix="meridian_log", unit="Log",
              chapters=CHAPTERS, settle_s=10 * 60, gap_s=45 * 60, lull_s=120, grace_hours=18,
              echoes=ECHOES, musings=MUSINGS, after=AFTER, first_hours=(0.25, 0.9, 1.6, 2.4, 3.2, 4.0),
              empty_note="Meridian opens the Leadline's log after a little time together, in a quiet moment.",
              complete_note="The Last Sounding is complete. The log's final line is filled; the sailing continues.")

PASSAGES = STORY.passages
