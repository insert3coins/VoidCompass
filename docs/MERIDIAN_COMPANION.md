# Meridian — veteran navigator

Available in **5.7.4**. Select **Meridian** at the top of the companion page. Setup, voice and display controls shared with Axiom are described in [Axiom and Meridian](CREW_COMPANIONS.md).

## Who Meridian is

Meridian was the navigation mind of the survey ship **Leadline**, one of seven ships in an old charting expedition. It is measured, literate and steady, and fond of old seafaring habits. It advises and never commands. It keeps a margin in mind for you, and it would rather the crew came home than the chart was finished.

Meridian is original fiction. It is separate from the Watcher's and Aster's stories and makes no claim to official Elite history. Its voice comes from a community Piper model (see the model notes); the character is its own.

## Commentary

On the companion page, **Meridian’s commentary** offers **Reflective** (the default: a navigator's manner and the occasional old saying) or **Plain** (short, direct reports). Both modes have several variants for every topic. Warnings and requested facts are never reduced.

Examples:

- *Arrival:* “Diaguandri, class G. New waters.”
- *Low fuel:* “Fuel at 18%. Every scoopable star is a harbour now. Let us find one.”
- *Danger:* “Hostiles, Commander. Keep a clear way out. Courage is good; a margin is better.”
- *Command:* “Aye. Landing gear.”
- *Shutdown:* “The watch is closed. Made good this session: 41 jumps. A voyage to be proud of. Goodnight.”

Type or say **Hello Meridian**, **Meridian, what can you do?** or any configured command (for example **Meridian, open galaxy map**). Commands, aliases and sequences are shared with every companion and live in **Settings › Voice**.

## The Last Sounding

Meridian's story has **48 passages in eight chapters**. Seven ships set out to sound the dark between two arms of the galaxy along a single line. They crossed the gap, lost a ship, and turned back one by one. The last two came home four hundred light years short of the final waypoint. One line of the log, *last sounding*, has been blank ever since.

| Chapter | Opens with |
| --- | --- |
| I · Taking Station | Time together (about 15 minutes) |
| II · The Fleet | Twenty-five jumps together |
| III · Soundings | A dozen survey observations: detailed scans or fully scanned systems |
| IV · The Gap | Ten long jumps (50 ly or more) or fuel scoops |
| V · Turning Back | A voyage 10,000 ly from Sol |
| VI · The Commodore's Order | Bringing your findings home twice: selling exploration or biological data |
| VII · Home Port | Five homecomings: dockings or returns to visited systems, and two real days after chapter VI |
| VIII · The Last Sounding | 250 jumps together, and three real days after chapter VII |

Every gated chapter also opens after about 18 more hours together, so no play style is required. Passages come in quiet moments: at least 10 minutes into a session, 2 quiet minutes, never during danger, and at least 45 minutes apart. Hours count only while Meridian is active. The STORY page hides unopened chapter titles. Hover over one to see how it opens.

**Echoes:** once the matching chapter is told, a long jump, a complete survey or map, a fuel scoop, the far reaches, a data sale or a return can stir a short aside. Each rests for a day (the far reaches for two). The STORY page lists the echoes found and how to find the rest. After the final chapter Meridian has its own after-story reflections, and **READ THE WHOLE STORY** shows the complete log.

## Your name: The Ship's Articles

In the old fleets every crew signed the ship's articles. After about 15 minutes together Meridian notices the commander name in your journal, then asks how you would like to be addressed: your journal name, **Commander**, or a nickname. Answer with the panel buttons, your answer hotkeys, the BRIDGE chat or voice (“yes”, “no thanks”, “call me Jeff”). Pronunciation and the choice live under **YOU › YOUR NAME**. An unanswered question expires after five minutes and isn't asked again for 14 days. Your chosen name becomes Meridian's regular form of address.

## Quiet watch, port and postcards

Meridian has its own wording for every event the Watcher reports: travel, surveys, first discoveries and maps, biology, fuel, heat and combat, cargo and mining, missions and trade, vehicles, expeditions, the hatchling, port company (station, carrier and concourse), learned habits, career facts, old postcards and service memories, and active and quiet sign-offs. Idle remarks follow the frequency you choose (Chatty 5, Occasional 10, Rare 20 minutes apart), rest each topic for at least half an hour, and fall silent rather than repeat. As the navigator, Meridian rates arrivals, long jumps, distance covered, carrier jumps, distance from Sol and quiet cruising above the usual importance, so even on Occasional or Rare it marks the voyage as it goes, and it has extra lines for each so a long run of jumps stays varied.

Automatic postcard notes are signed **Meridian** when it is the active companion (**Postcards › Studio › The note**).

## Memory

Meridian keeps its own `meridian_memory.json` for each commander: story progress, name choice, conversation and wording rotations. **RESET MERIDIAN** backs up and clears only that file. **SAVE BOOK** exports heard passages and service memories to the Wrapped folder.

**The crew.** Meridian also tells its six-passage *Coming Aboard* account and hands over the watch to its crewmates by name. See [the crew](CREW_COMPANIONS.md#the-crew-how-they-came-aboard).

## Keepsakes and deeper company

- **Time capsules, constellations, On this day and anniversaries** are spoken by Meridian when it is on watch, in either commentary style. With capsule delivery set to "your companion, or a notice", a notice still appears if it stays quiet.
- **Its readings of you.** The BRIDGE and YOU pages show Meridian's confidence and spirits. They move with real events: answering its questions, close calls, repairs, data sales, losing the ship and meeting other commanders' companions.
- **Night Log.** When you log off, Meridian writes a short note about the watch. The YOU page keeps them, the book export includes them, and it may mention the last one when you return.
- **Other commanders' companions.** Copy Meridian's code from the YOU page; paste a friend's code (from any companion) to meet theirs.
- **A request.** Once, after chapter VI, Meridian asks to be taken to the edge of the galaxy. The request appears on the BRIDGE, can become an expedition objective, and Meridian notices when you arrive.
- **Achievements.** Four in the Meridian category: the first passage, the whole story, every echo, and *The Far End* for keeping its request.
- **Captain's Log.** Sessions flown with Meridian on watch end with its own closing paragraph, signed Meridian.

## Local API

`GET /api/v1/companion` reports the active companion and its story progress. `GET /api/v1/companions/meridian` reads Meridian's record even when another companion is active. See [api.md](../api.md#companions).

## Navigator android display

Meridian’s floating overlay, BRIDGE and boot display share a brass-and-midnight-blue navigator robot. The restrained design follows his voice and existing seafaring character: calm optical shutters, separate cheek and jaw plates, side gimbals, a broad collar and an instrument chest. The forehead stays plain.

His head and optics follow attention, blink slowly and wear the mood of the current thought. His mouth and mechanical jaw use the actual playback envelope, closing for silence, microphone input and queued lines. Spoken warnings still animate the mouth. Fixed focus holds his gaze and orientation; Reduced motion applies expressions immediately and parks continuous movement.

The existing compass rose, service pips and jump ripple remain. The outer bearing needle sits clear of his face. The chest dial repeats the same bearing: the next star while charging on a route, otherwise home, or the core when close to home. With no valid bearing it shows no needle. All existing Studio sizes, accents, focus, liveliness, idle animation and frame rates remain shared.

Geometry is in `web/assets/officer-robots.js` (`addMeridianNavigator`), driven by `crew-3d.js`. Reflections, antialiasing and tone mapping use the existing robot rendering path; transparent corners and the common outer diameter are preserved. There is no portrait image or external character-model dependency.
