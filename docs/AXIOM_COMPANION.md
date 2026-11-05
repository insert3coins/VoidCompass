# Axiom — survey intelligence

Available in **5.7.4**. Select **Axiom** at the top of the companion page. Setup, voice and display controls shared with Meridian are described in [Axiom and Meridian](CREW_COMPANIONS.md).

## Who Axiom is

Axiom was the cataloguing mind of the **Lattice**, an array of twelve automated observatories that counted every point of light in their field. It is precise, literal and earnest. It likes two observations that agree, explains its jokes, and is still learning to say *I do not know*. It counts things nobody asked it to count, including your landings. It answers from your journal and says plainly when the journal doesn't know.

Axiom is original fiction. It is separate from the Watcher's and Aster's stories and makes no claim to official Elite history. Its voice comes from a community Piper model (see the model notes); the character is its own.

## Commentary

On the companion page, **Axiom’s commentary** offers **Curious** (the default: questions, small enthusiasms and very careful jokes) or **Precise** (plain, short reports). Both modes have several variants for every topic. Warnings and requested facts are never reduced.

Examples:

- *Arrival:* “Arrived in Shinrarta Dezhra. I am already counting.”
- *Low fuel:* “Fuel at 18%. I would like us to find a star of class K, G, B, F, O, A or M. Any of them.”
- *First discovery:* “First on record at Col 285 Sector AB-C d1-2 A 3. I like the sound of that very much.”
- *Command:* “Landing gear. Executed precisely.”
- *Shutdown:* “Session complete. Final tally: 41 jumps, 2 first discoveries. I enjoyed it. That is a precise statement.”

Type or say **Hello Axiom**, **Axiom, what can you do?** or any configured command (for example **Axiom, open galaxy map**). Commands, aliases and sequences are shared with every companion and live in **Settings › Voice**.

## The Uncounted Star

Axiom's story has **48 passages in eight chapters**. Every full recount of the Lattice's sky found one more light than its catalogue held. Axiom tried every explanation it could think of. It met the array's human keeper, learned what an error bar is for, watched the stations go dark, and finally sorted the old data by time instead of place.

| Chapter | Opens with |
| --- | --- |
| I · Initialisation | Time together (about 15 minutes) |
| II · The Census | Ten detailed scans |
| III · The Keeper | Three dockings |
| IV · Error Bars | Three first discoveries |
| V · Defunded | Five long jumps (50 ly or more) or travel 10,000 ly from Sol |
| VI · The Raw Data | Two remarkable observations: a neutron star, white dwarf or black hole, or a fully scanned system |
| VII · Proper Motion | Three returns to systems visited together, and two real days after chapter VI |
| VIII · The Uncounted Star | 200 jumps and detailed scans together, and three real days after chapter VII |

Every gated chapter also opens after about 18 more hours together, so no play style is required. Passages come in quiet moments: at least 10 minutes into a session, 2 quiet minutes, never during danger, and at least 45 minutes apart. Hours count only while Axiom is active. The STORY page hides unopened chapter titles. Hover over one to see how it opens.

**Echoes:** once the matching chapter is told, a complete system scan, a docking, a first discovery, the far dark, a stellar remnant or a return can stir a short aside. Each rests for a day (the far dark for two). The STORY page lists the echoes found and how to find the rest. After the final chapter Axiom has its own after-story reflections, and **READ THE WHOLE STORY** shows the complete book.

## Your name: The Observer Field

Every observation in a catalogue records who made it. After about 15 minutes together Axiom notices the commander name in your journal, then asks how you would like to be addressed: your journal name, **Commander**, or a nickname. Answer with the panel buttons, your answer hotkeys, the BRIDGE chat or voice (“yes”, “no thanks”, “call me Jeff”). Pronunciation and the choice live under **YOU › YOUR NAME**. An unanswered question expires after five minutes and isn't asked again for 14 days. Your chosen name becomes Axiom's regular form of address.

## Quiet watch, port and postcards

Axiom has its own wording for every event the Watcher reports: travel, surveys, first discoveries and maps, biology, fuel, heat and combat, cargo and mining, missions and trade, vehicles, expeditions, the hatchling, port company (station, carrier and concourse), learned habits, career facts, old postcards and service memories, and active and quiet sign-offs. Idle remarks follow the frequency you choose (Chatty 5, Occasional 10, Rare 20 minutes apart), rest each topic for at least half an hour, and fall silent rather than repeat. As a survey intelligence, Axiom rates scans, maps, unexplored systems, terraformable worlds, large systems and Codex entries above the usual importance, so even on Occasional or Rare it speaks up about the survey, and it has extra lines for each so a long night of scanning stays varied.

Automatic postcard notes are signed **Axiom** when it is the active companion (**Postcards › Studio › The note**).

## Memory

Axiom keeps its own `axiom_memory.json` for each commander: story progress, name choice, conversation and wording rotations. **RESET AXIOM** backs up and clears only that file. **SAVE BOOK** exports heard passages and service memories to the Wrapped folder.

**The crew.** Axiom also tells its six-passage *Coming Aboard* account and hands over the watch to its crewmates by name. See [the crew](CREW_COMPANIONS.md#the-crew-how-they-came-aboard).

## Keepsakes and deeper company

- **Time capsules, constellations, On this day and anniversaries** are spoken by Axiom when it is on watch, in either commentary style. With capsule delivery set to "your companion, or a notice", a notice still appears if it stays quiet.
- **Its readings of you.** The BRIDGE and YOU pages show Axiom's certainty and outlook. They move with real events: answering its questions, close calls, repairs, data sales, losing the ship and meeting other commanders' companions.
- **Overnight Notes.** When you log off, Axiom writes a short note about the watch. The YOU page keeps them, the book export includes them, and it may mention the last one when you return.
- **Other commanders' companions.** Copy Axiom's code from the YOU page; paste a friend's code (from any companion) to meet theirs.
- **A request.** Once, after chapter VI, Axiom asks to be taken to a black hole. The request appears on the BRIDGE, can become an expedition objective, and Axiom notices when you arrive.
- **Achievements.** Four in the Axiom category: the first passage, the whole story, every echo, and *Seen in Person* for keeping its request.
- **Captain's Log.** Sessions flown with Axiom on watch end with its own closing paragraph, signed Axiom.

## Local API

`GET /api/v1/companion` reports the active companion and its story progress. `GET /api/v1/companions/axiom` reads Axiom's record even when another companion is active. See [api.md](../api.md#companions).
