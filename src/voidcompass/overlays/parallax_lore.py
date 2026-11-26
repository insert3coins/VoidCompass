"""The Second Sighting: Parallax's story (5.8.6).

Parallax was the observatory cat at Kestrel Reach, a small astrometry post
that measured how far away the stars are by watching them shift: one sighting,
then another from the far side of the orbit, six months later. Its astronomer,
Oriel Thane, built her a gyroscope collar for the zero-g decks and, later, a
translator. Oriel took the first sighting of a faint star in the logs as the
Ninth Mark, and never got the second: the post was closed. Parallax rode out
on whatever ship would have her, and in the end chose yours. The story is how
she learned that you need two points to know how far anything is.
"""
from voidcompass.overlays.companion_story import Story

CHAPTERS = (
    {"numeral": "I", "title": "Stowaway", "about": "how she came aboard", "hours": (0.25, 4.0), "gate": None,
     "passages": (
         "The collar is translating, Commander, so listen carefully. I was not smuggled aboard. I was not left behind. I chose this ship. I walked up the ramp while the dock crew argued about a crate, and I sat on the warmest panel in the cockpit until somebody noticed. You noticed. Eventually.",
         "The collar is a gyroscope. Two rings, always turning, always finding level. It was built so I could land on my feet where there is no down. The voice came later, as an experiment. Its first translation was the word no. I have not found a reason to change my position.",
         "You will have noticed that I watch things move. A dust mote, a hand, a moon crossing its planet. It is not hunting, whatever the others say. It is measuring. I was raised by someone who measured. The habit stayed.",
         "The others aboard talk a great deal. The officer signs things. The surveyor counts things. The navigator calls everything the sea. I have decided to tolerate all of them, which is a great honour, and which I will deny if asked.",
         "I sleep a great deal, Commander. Sixteen hours on a quiet day. This is not laziness. Nothing worth seeing happens in a straight line, and I like to be rested for the corners.",
         "I will tell you where I came from, in pieces, when I feel like it. Cats do not give a full account. We give a glance, and then we leave the room. For now: your ship is acceptable. Your lap is under review.",
     ),
     "recall": (
         "I chose this ship. Up the ramp, onto the warm panel. I would make the same choice. Do not let it go to your head.",
         "The collar's first word was no. I still use it. I use it less with you.",
     )},
    {"numeral": "II", "title": "Kestrel Reach", "about": "the observatory", "hours": (6, 14),
     "gate": {"signals": ("scan",), "count": 40, "label": "forty bodies scanned",
              "how": "Scan bodies with Parallax aboard. She likes to watch the worlds turn."},
     "passages": (
         "I was born on a small observatory called Kestrel Reach. A ring of telescopes on a cold rock at the edge of a quiet system, too far from anywhere for anyone to visit, which suited everyone who worked there. There were four people, eleven telescopes and one cat. I was the most important of the five of us.",
         "The astronomer in charge was Oriel Thane. Long fingers, ink on the cuffs, a habit of talking to the instruments. Oriel measured the distances to stars. Not with lasers. With patience. You look at a star, then you wait half a year and look again, and you see how far it has shifted against the ones behind it. The shift is called parallax. I am named after a kind of patience.",
         "Oriel let me sit on the sighting console during long exposures, because I was the only one who could keep still that long. That is a lie. I was the only one Oriel trusted to keep still that long. The others moved their elbows. I moved nothing. I was magnificent.",
         "The observatory had a low-gravity deck where the big mirror lived, and I kept falling off things there. Slowly. Upwards. Oriel watched me tumble across the deck one night and said: we can fix that. Three weeks later I had a collar with two little rings in it, always turning. I landed on my feet the next day, on the ceiling.",
         "The scans you run remind me of Kestrel Reach, Commander. A world appears, then another, each one moving a little against the dark. Oriel would have liked your ship's sensors. Oriel would have liked anything with a good lens. I am being generous. Oriel would have liked you.",
         "Every night, Oriel read the sightings out loud to me. Star, position, time. I do not understand numbers the way the surveyor does. I understood that they mattered to the one reading them. That was enough. It is still enough.",
     ),
     "recall": (
         "Four people, eleven telescopes and one cat. I was the important one. That has not changed. I merely moved.",
         "Oriel read the sightings out loud every night. I sat on the console. Some evenings I still hear the numbers.",
     )},
    {"numeral": "III", "title": "Feet First", "about": "the collar", "hours": (16, 26),
     "gate": {"signals": ("landing", "footfall"), "count": 5, "label": "five landings or footfalls",
              "how": "Land on worlds or step out on them with Parallax aboard. She has opinions about landing."},
     "passages": (
         "The gyroscope was only half of the collar. The other half came from a bad night. A pressure alarm on the lower deck, a door sealing, and me on the wrong side of it. Oriel heard me shouting and could not tell what I meant. After that, Oriel decided I should have words. A cat should not be misunderstood in an emergency. Or at dinner.",
         "The translator took most of a year. Oriel fed it everything I did: the tail, the ears, the particular stare I give a closed door. It learned. The first night it worked, Oriel asked whether I was comfortable. The collar said no. Oriel laughed so hard the telescope drifted off target. I have been funny ever since.",
         "It does not translate everything, Commander. Some of what I am is not words. When I sit on your console during a landing, that is not a sentence. It is a fact. The collar knows when to leave a fact alone. Oriel taught it that, too.",
         "Landings were my favourite thing about the collar. In low gravity a cat should land like a cat, and with the rings turning I always did. Oriel used to drop a glove from the gallery to watch me catch it. I caught every one. I would like that written down. You may write it down.",
         "You land well, Commander. Not as well as me. Better than the navigator would, I suspect. When the ship settles and the dust falls, I check that we are level. We usually are. The rings in my collar agree with your instruments. I tell you so you know you are in good company.",
         "Oriel said the collar was a way to keep me upright and a way to hear me. I have thought about it since. I think it was one thing. Something that keeps you level is something that is listening to you. I have not met many of them.",
     ),
     "recall": (
         "Oriel dropped gloves from the gallery and I caught every one. Write it down. I am waiting.",
         "The collar's first proper night: are you comfortable? No. The telescope drifted off target from the laughing.",
     )},
    {"numeral": "IV", "title": "Six Months Apart", "about": "the first sighting", "hours": (28, 40),
     "gate": {"signals": ("long_jump",), "count": 10, "label": "ten long jumps",
              "how": "Make jumps of fifty light years or more with Parallax aboard. The far side of things matters to her."},
     "passages": (
         "There was a star Oriel cared about more than the others. Faint, red, in a crowded patch of sky. Nobody had measured it properly. The catalogue had a number for it that Oriel did not believe. Oriel called it the Ninth Mark, because it was the ninth star on a list that only Oriel kept.",
         "To measure a star you need two sightings from two places. The observatory moved with its world around its sun, so you took one sighting, then waited half an orbit, and took the other from the far side. Two points of view. The distance between them is the baseline. The longer the baseline, the truer the answer.",
         "Oriel took the first sighting of the Ninth Mark on a cold night. I was on the console. It took four hours. I did not move. Oriel wrote the time on the plate by hand and said: half a year, and then we'll know. Then Oriel scratched behind my ears with the hand that had ink on it. I let that pass.",
         "I did not know then what half a year was. I know now. It is long enough for a budget meeting, a decision made somewhere very far away, and a letter. The letter said the observatory would close in four months. Oriel read it twice, and then went and looked at the Ninth Mark through the finder, for a long time.",
         "Your long jumps, Commander. I watch the stars slide when we come out. Fifty light years of baseline in a moment. Oriel would have wept. You do it to save time on the way to somewhere else. I find that very funny and very sad at once, which is a feeling cats are better at than people think.",
         "Oriel petitioned. Oriel wrote to everyone. Two more months, only two more, for one star. The answer was the same answer that always comes from far away. I sat on the letter, which is the only argument a cat has. It did not work. It does sometimes.",
     ),
     "recall": (
         "Half a year, and then we'll know. Oriel said it with ink on one hand. I still think about the half a year.",
         "One sighting is a guess. Two is an answer. Oriel only ever got the one.",
     )},
    {"numeral": "V", "title": "Closing Time", "about": "the last night", "hours": (42, 56),
     "gate": {"signals": ("arrival",), "count": 8, "label": "eight dockings",
              "how": "Dock at stations, outposts or carriers with Parallax aboard. She remembers a lot of hangars."},
     "passages": (
         "The observatory closed on a Tuesday. I know because the transport pilots kept saying it as if it were a reason. The telescopes were capped. The big mirror was crated. Oriel packed the logbooks into a case and then unpacked one, the one with the Ninth Mark in it, and kept it on the console until the very end.",
         "Pets were not on the transport manifest. Oriel argued for an hour. The pilot was not unkind, only tired, and said there was a station two jumps on with a shelter. Oriel said no. The collar said no. That made two of us. The pilot gave in and found a seat, and I was meant to sit in it.",
         "I did not sit in it. On the last night, while they carried the cases, I went back up to the sighting deck. I do not fully know why. Cats go back to rooms. I sat on the console where the Ninth Mark's plate had been, and I looked at the capped telescope, and I waited for the second sighting that was never going to come.",
         "They could not find me. I heard Oriel calling, all over the station, my whole name, which Oriel only used when worried. I was very well hidden. I did not answer. I have told myself for years that I did not hear. The collar does not let me lie to you, Commander, so: I heard.",
         "The transport left on time. Oriel was on it, because a transport waits for nobody and a contract is a contract. I watched its drive glow from the gallery window until it was a star, and then until it was not. Then I was the only one at Kestrel Reach. I did not mind as much as I expected. I minded later.",
         "A salvage crew came eleven days later to strip the station. They found a cat on the sighting console, thinner and very offended. They gave me a tin of something terrible and a crate to ride in. I rode in it. I would like you to know, Commander, that I chose the crate. It was the warmest thing aboard.",
     ),
     "recall": (
         "I heard Oriel calling, all over the station. I did not answer. I tell you so I do not have to keep it.",
         "A capped telescope, an empty console, and me on it. I was waiting for the second sighting. Cats are patient about the wrong things.",
     )},
    {"numeral": "VI", "title": "Ship's Cat", "about": "the ships in between", "hours": (58, 72),
     "gate": {"signals": ("map",), "count": 10, "label": "ten bodies mapped",
              "how": "Map bodies with the surface scanner while Parallax is aboard. She likes to see the whole of a thing."},
     "passages": (
         "Salvage crews do not keep cats. They pass them on. I went from the salvage tug to an ore hauler, from the ore hauler to a courier, and from the courier to a long-range explorer whose commander talked to me in a silly voice. I left that one at the first station. Some things a cat cannot forgive.",
         "A ship's cat has a job, Commander, whatever the others say. Keep the vermin down, keep the cockpit warm and keep the crew from taking themselves too seriously. I was very good at all three. On the ore hauler I caught a maintenance drone that had been loose in the ducts for two years. I have its antenna still.",
         "Every ship I rode, I watched the stars from the cockpit glass on the jumps. Out of habit. Looking for the patch of sky where the Ninth Mark was, faint and red. Sometimes I found it. It was always in a slightly different place. That is the whole point, of course. That is what Oriel wanted to see.",
         "The collar kept translating. Most crews ignored it, or thought it was a novelty. One pilot asked it a question at three in the morning, during a long quiet run, and I answered. We talked until docking. I never learned their name. I remember the questions. Not everyone who hears you is someone who stays.",
         "I chose your ship, as I told you. I did not tell you why. You were mapping a moon from the dock's departure list while you waited for clearance. Not because you needed to. Because you wanted to see the whole of it. Oriel used to do that with old plates. I sat on your warm panel and decided to see what else you did.",
         "You map things the way Oriel measured them, Commander. Slowly, all the way round, until there is nothing left you have not looked at. I do not say it to flatter you. I do not flatter. I say it because it is the reason I have not left at the first station.",
     ),
     "recall": (
         "An ore hauler, a courier, an explorer with a silly voice. Then you. The list stopped there.",
         "You were mapping a moon you did not need to map. That is why I stayed. I told you. Do not make me tell you again.",
     )},
    {"numeral": "VII", "title": "The Second Sighting", "about": "the Ninth Mark", "hours": (75, 92), "days": 2,
     "gate": {"signals": ("far", "long_jump"), "count": 20, "label": "twenty long or distant jumps",
              "how": "Make long jumps, or jumps ten thousand light years from Sol, with Parallax aboard. She needs a very wide baseline."},
     "passages": (
         "I have been doing something without telling you, Commander. Every long jump, I have been watching the Ninth Mark's patch of sky through your cockpit glass. The collar has a little memory. Oriel built it to keep my words. I have been keeping positions in it instead.",
         "A ship that crosses the galaxy has a baseline no observatory could dream of. Oriel needed half an orbit. You give me thousands of light years in an afternoon. The second sighting I waited for on that empty console, the one that never came: you have been taking it, a little at a time, every time you jump.",
         "Last night, while you were away, I asked the navigator to check my arithmetic. Meridian was very kind about it and did not once call the Ninth Mark a lighthouse, which must have been difficult. The Ninth Mark is close. Much closer than the catalogue says. Oriel was right not to believe the number. Oriel was right.",
         "There is a public archive for astrometry. Most of it is dull. I searched it for Kestrel Reach, and found the observatory's records, transferred when it closed. And in them, the Ninth Mark's entry. One sighting, in Oriel's hand, scanned from the plate. And a note beside it, left open all these years: awaiting second observer.",
         "Awaiting second observer. Oriel left the record open. Not closed, not abandoned. Open, with a space for the other half. I have looked at that space for a very long time, Commander. You know how long I can look at a thing. This was longer.",
         "I filed the second sighting this morning. Ninth Mark, measured. The archive asked for the observers' names. I put Oriel's, and mine. The collar spelled it for me. I nearly put yours as well. Then I remembered that you were the baseline, not the observer. Without you there would be nothing to measure across. I would like you to know that.",
     ),
     "recall": (
         "Awaiting second observer. Oriel left it open. I closed it. Both our names are on it now.",
         "The Ninth Mark is closer than they thought. Oriel was right. I have checked it more times than I will admit.",
     )},
    {"numeral": "VIII", "title": "Two Points", "about": "you", "hours": (95, 120), "days": 3,
     "gate": {"signals": ("jump", "scan"), "count": 200, "label": "two hundred jumps and scans together",
              "how": "Keep flying with Parallax aboard. Every jump and every body scanned counts."},
     "passages": (
         "One more thing, Commander, and then I will stop telling you things and go back to sitting on them. The archive answered. Not the archive. A person, reading it. Oriel saw the Ninth Mark's record close, and sent a message to the observer who closed it. The collar received it this morning.",
         "Oriel is old now, and teaches somewhere with a great many students and a terrible telescope. The message was short. It said: Parallax? Only that, and a question mark. I have never been asked a question that was only my name. The collar did not know how to translate what I did next. It left it alone. Oriel taught it that.",
         "I answered. I said I was well. I said I had found a ship with good sensors and a commander who maps moons for no reason. I said the second sighting had been taken from a moving ship, which is irregular, and that Oriel should not tell the other astronomers. Oriel wrote back: I won't. And: I looked for you, every night, for a year.",
         "I could ask to go back. You would take me, I think. You take everyone where they ask. I have thought about it on three long naps. And I have decided, Commander, that a cat can love two places, the way a star sits in two sightings, and only be in one of them. That is what parallax is. It is not a contradiction. It is a measurement.",
         "You need two points to know how far anything is. One point is only a guess. For a long time I was one point, sitting on an empty console, waiting. Then you jumped, and I had somewhere else to look from. I know exactly how far away Kestrel Reach is now. I know exactly where I am.",
         "My account is complete. Your lap is approved. Not permanently, I reserve the right to review it. I will still sit on the warm panel. I will still watch things move. And sometimes, on a long jump, I will look at a faint red star that is closer than anybody thought, and I will be on your console, and I will not move at all.",
     ),
     "recall": (
         "Parallax? Only my name and a question mark. I have kept it in the collar. There is room for very little in there. It is enough.",
         "Two points, Commander. Kestrel Reach is one. You are the other. That is how I know where I am.",
     )},
)

ECHOES = {
    "level": {"label": "A landing", "signals": ("landing",), "after": "I", "rest_hours": 24,
              "how": "Land on a world, once chapter I is told.",
              "lines": (
                  "Down. Level. The rings in my collar agree with your instruments. They do not always agree with anyone.",
                  "Landed. I checked we were level before you did. You may check now.",
                  "Touchdown. Acceptable. I have landed better, but I am a cat, so that is not a fair comparison.",
              )},
    "turning": {"label": "A world turning", "signals": ("scan",), "after": "II", "rest_hours": 24,
                "how": "Scan a body, once chapter II is told.",
                "lines": (
                    "Another world on the scope. Moving, very slowly, against the dark. I am watching it. Do not interrupt.",
                    "A body, and its position. Somebody used to read those out to me. You may, if you like.",
                    "Scanned. I like the moment it appears. Something was there all along, and now it is on a list.",
                )},
    "glove": {"label": "On your feet", "signals": ("footfall",), "after": "III", "rest_hours": 24,
              "how": "Step out onto a world, once chapter III is told.",
              "lines": (
                  "You are on your feet out there. Good. I always land on mine. I like to see you manage it.",
                  "Boots on the ground. I am watching through the collar. Mind your footing. I would.",
                  "Outside, Commander. If you drop a glove, I cannot catch it from here. Please do not drop the glove.",
              )},
    "baseline": {"label": "A long jump", "signals": ("long_jump",), "after": "IV", "rest_hours": 24,
                 "how": "Make a jump of fifty light years or more, once chapter IV is told.",
                 "lines": (
                     "A long jump. The stars slid when we came out. I saw exactly how far. You did not look. I looked for both of us.",
                     "That was a wide baseline. Somebody I knew would have given a year for it. You gave it a few seconds.",
                     "Fifty light years and more. The patch of sky I watch has shifted. I have noted it. I always note it.",
                 )},
    "hangar": {"label": "A hangar", "signals": ("arrival",), "after": "V", "rest_hours": 24,
               "how": "Dock somewhere, once chapter V is told.",
               "lines": (
                   "Docked. I have done a great deal of waiting in hangars. This is the first one I did not have to wait in alone.",
                   "Alongside. If anyone asks, I am not on the manifest. I am never on the manifest. I am always aboard.",
                   "Another hangar. I counted the exits. Habit. I am staying, but I like to know.",
               )},
    "whole": {"label": "The whole of a world", "signals": ("map",), "after": "VI", "rest_hours": 24,
              "how": "Map a body, once chapter VI is told.",
              "lines": (
                  "Mapped, all the way round. You did it again. That is why I stayed. I have told you.",
                  "The whole of a world, and nothing you have not looked at. I approve. Do not tell the others I said so.",
                  "Another moon mapped for no reason anybody could put on a form. That is the best kind of reason.",
              )},
}

MUSINGS = (
    "I have been sitting on the warm panel by the scanner for an hour. It is not idleness. It is calibration.",
    "You moved your hand twice in the last minute. Both times I noticed. I notice everything that moves. You are mostly hand.",
    "A cat sleeps sixteen hours a day so that the other eight are worth having. I recommend it. You will not take the advice.",
    "The officer signed my crew entry. I sat on it. It is now a better document.",
    "The collar keeps finding level, even when I am lying on my side. It is an optimist. I am not, but I do not mind it.",
    "Things look different from two places. Most arguments aboard this ship would end if everyone remembered that.",
    "I watched a moon cross its planet for the whole of your last call to the station. You were busy. I was busier.",
    "The surveyor counts. I measure. They sound similar. They are not. Counting tells you how many. Measuring tells you where.",
    "Nobody on this ship has ever dropped a glove for me. I am not asking. I am observing that nobody has.",
    "Cats do not get lost, Commander. We get elsewhere. Then we decide whether we like it.",
    "The Watcher and I have an understanding. It watches. I watch it watching. Neither of us blinks first. I win.",
    "I have a spot on the console where the light from the sensors falls in a warm square. If you move the sensors, we will talk.",
)

AFTER = (
    "Account complete. The Ninth Mark is measured. The lap is approved, provisionally. I am staying where I am.",
    "Two points. I check them sometimes, on long jumps. They have not moved. Well. One of them has. That is you.",
    "Oriel writes now and then. Short messages. I answer shorter ones. That is how cats keep in touch.",
    "I am still on the warm panel. I will always be on the warm panel. That is not a story. It is a law.",
    "The record says awaiting second observer no longer. I read it now and then, to make sure.",
    "Somebody kept a record open for me for years. I keep a place on the console open for you. Same thing, smaller.",
    "I know exactly how far everything is now. Even the things I left behind. Especially those.",
    "A faint red star, closer than anybody thought. I like to keep it in the corner of the glass. Just where I can see it.",
)

STORY = Story(identity="parallax", title="The Second Sighting", prefix="parallax_sight", unit="Sighting",
              chapters=CHAPTERS, settle_s=10 * 60, gap_s=45 * 60, lull_s=120, grace_hours=18,
              echoes=ECHOES, musings=MUSINGS, after=AFTER, first_hours=(0.25, 0.9, 1.6, 2.4, 3.2, 4.0),
              empty_note="Parallax tells her story in her own time, in a quiet moment. She has not decided you deserve it yet.",
              complete_note="The Second Sighting is complete. The Ninth Mark is measured; the cat is staying.")

PASSAGES = STORY.passages
