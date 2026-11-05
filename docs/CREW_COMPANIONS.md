# Axiom and Meridian

Available in **5.7.4** alongside The Watcher and Aster. Select **Axiom** or **Meridian** at the top of the companion page. The deck title, BRIDGE display and chat, and SETUP follow that choice. Each has its own character, story, name introduction, conversation and postcard notes: see [Axiom](AXIOM_COMPANION.md), a survey intelligence (*The Uncounted Star*), and [Meridian](MERIDIAN_COMPANION.md), a veteran navigator (*The Last Sounding*). This page covers what they share: voices, displays and Studio controls.

| Companion | Voice pair | Display |
| --- | --- | --- |
| Axiom | `models/data/en_US-data_7024-medium.onnx` and matching `.onnx.json` | Violet/cyan particle torus surrounding a floating lattice crystal, with orbiting light, ripples and attention movement |
| Meridian | `models/picard/en_US-picard_7399-medium.onnx` and matching `.onnx.json` | Gold/blue anonymous wireframe portrait, scan bands, instrument rings and speech-driven lips |

The displays are original procedural Three.js geometry on a transparent background. The supplied ring and HUD portrait references inspired their structure. No reference artwork or actor portrait is bundled.

Axiom and Meridian sit inside a defined instrument bezel, with a dark translucent recess behind their detail. This follows the Watcher’s contrast treatment so the holograms remain readable over bright planets and busy cockpit scenery. Axiom’s centre contains a translucent lattice crystal; the game remains visible between its edges and the surrounding ring. Meridian has dark glass behind its portrait. The space outside the instrument remains transparent. Their particle flow, wireframe features and existing Studio controls are retained.

## The crew: how they came aboard

All four companions are aboard your ship at once; the one you choose is simply the one **on watch**.

- **The Watcher** was aboard first: salvage, wired in as a spare log buffer before you ever flew.
- **Aster, Axiom and Meridian** came aboard later as second-hand cores, bought cheap from surplus brokers: an officer core in a lot of used modules, a survey mind from a dealer's shelf, and a navigation trainer from an academy auction.
- They found each other on the ship's data bus in the hours you're logged off. Aster drew up a **watch rota**, and Meridian keeps proposing amendments to it in the old naval form. The rota is one on watch at a time, with the choice of who left to you.

**Coming Aboard.** Each companion tells its own six passages: its arrival, finding the others, the rota, then one passage about each crewmate. The arc begins after about two hours together, once you've flown with at least two companions. A passage about a crewmate waits until you've flown with that crewmate for 15 minutes. Passages come in quiet moments, at least an hour apart and never in danger, and they share pacing with the companion's main story. The **STORY** tab's **THE CREW** section shows all four accounts, whoever is on watch. Hover over a locked passage to see what it waits for. **SAVE BOOK** includes the active companion's account.

**Handovers.** Choosing another companion hands over the watch: the incoming companion takes it from the outgoing one by name, for example *"Taking over from Aster. Everything is in order, with a blank line at the bottom. As expected."* Each companion has 15 to 20 lines for every crewmate and works through all of them before any line comes back, so a run of switches doesn't repeat itself. Once a crewmate's passage has been told, companions occasionally mention them in quiet moments.

**Ask a crewmate.** Start a TALK message with another companion's name and that companion answers without taking the watch: *"Meridian, how far to Colonia?"*, *"ask Axiom what's in this system"* or just *"hey Aster"*. The answer uses the same ship data, in the crewmate's own words, under its name with OFF WATCH, and in its own voice when that voice is installed and switched on (otherwise it's written only). Commands work too. The name must come first, followed by a comma or a question, so a command such as "watcher overlay off" is never mistaken for one.

**Off-watch remarks.** At a big moment (an Earth-like world, a first footfall, a record jump, a record distance from Sol, or surviving a critical hull) a crewmate you've flown with may add one line about eight seconds after the companion on watch has had its say, under its own name and in its own voice. It happens at most once a session and an hour apart, only about half the time a moment allows it, never in danger, and never with Thoughts set to Off. Each crewmate has five lines for each moment and uses them all before any comes back.

**Starting pace.** A companion's first watch starts at the same Thoughts setting as the Watcher. After that its setting is its own.

**Achievements** (category *The Crew*): *Introductions* (the first crew passage), *Full Crew* (fly with all four companions) and *The Watch Rota* (all 24 passages).

## Try them

1. Choose a companion with the switcher at the top of the page, then open **SETUP** and enable/download its voice. Downloads share the Piper engine and verify each companion’s own model pair by SHA-256. A checkout containing the matching pair keeps those files and downloads only the engine when needed.
2. Click **TEST THE VOICE**. Each has its own short test sentence.
3. Enable the companion overlay in **Overlay Studio** for live replies, and set **Thoughts** above Off.
4. On the **BRIDGE**, type **Hello Axiom** or **Hello Meridian**. Each has 30 rotating greetings (10 in its plainer commentary mode) and its own login welcomes; duplicate login events are coalesced.
5. Ask **Axiom, what can you do?** or **Meridian, what can you do?** for one of six practical rundowns. Configured commands and factual lookups use the existing shared services.
6. For spoken commands, configure recognition, microphone and push-to-talk in **Settings › Voice**. Piper handles output speech; recognition has its own download and settings.

Examples: `Axiom, open galaxy map`, `Meridian, where are we?`, `Axiom, show the survey overlay`. Commands must be enabled in your editable command catalogue; ship commands also require Elite bindings and any configured sequence. User-edited command phrases still apply.

## Display and preferences

Both identities use the same Studio size, accent, focus movement, idle animation, liveliness, frame rate and caption controls. Size carries across switches. Accent, motion, focus, liveliness, voice settings and thought frequency are saved separately per companion and commander. Fixed focus stops attention turns; reduced motion pauses continuous animation. Hidden displays park their rendering.

Each companion has a signature colour preset, including its main light and highlights:

| Studio preset | Main light | Highlights |
| --- | --- | --- |
| Aster cyan | Cyan `#65e4ef` | Violet `#a8b4ff` |
| Axiom violet | Violet `#a897ff` | Cyan `#65e4ef` |
| Meridian gold | Gold `#e8c48c` | Blue `#74bbff` |

These are the defaults for new companion settings. Select the named preset in **Overlay Studio → Companion → Accent** to use it with existing settings. The chosen palette colours the floating display, bezel and deck panel; captions set to **Eye colour** also follow it. **Theme accent**, **Ice cyan** and **Brass** remain available. Existing choices of those three are preserved. The earlier non-Watcher red choice now selects that companion’s signature palette. The Watcher keeps **HAL red**.

Studio changes publish the companion model and native window dimensions immediately, including while the journal is quiet. Theme accent follows the selected app theme on both surfaces. Axiom’s idle animation includes flowing particle bands, breathing ripples and two counter-rotating light trails. Meridian’s instrument rings counter-rotate around a gently moving portrait with a visible scan band. Calm, Standard and Lively change the motion speed. Idle animation Off parks the continuous motion; activity and speech can still wake it. If Reduced motion is enabled in Appearance or your system preferences, the Studio note explains why continuous animation is paused.

Axiom’s central crystal slowly turns and breathes at idle. Listening draws light inward along its connections; working sends faster pulses through the lattice. Speech expands and lights the core with the real audio level, and alerts use warning colours. Aster uses the same reactions in a smaller hexagonal prism inside its command interface. These cores appear in both the floating overlay and the deck BRIDGE panel, using the selected palette and existing motion controls.

Meridian keeps its portrait. Its upper and lower lips now form a visible mouth opening driven by the actual speech envelope, with a quick attack and a smooth close during pauses. Queued text and microphone input do not move the lips. Warning speech still moves the mouth while the portrait shows its alert colours. When audio ends the mouth closes; Reduced motion keeps it still. This is amplitude-driven mouth movement, rather than phoneme-based lip sync.

The floating overlay and deck BRIDGE panel use the existing shared caption presenter and speech queue: queued captions wait for their line and follow its actual audio clock. Switching companions closes the previous speaker and recognition session. Runtime memories are `<identity>_memory.json` in the commander profile.

Their **STORY** pages show their own stories, with unlock hints on unopened chapters and the echoes each has found. Name preferences and pronunciation are under **YOU**; each companion introduces the question in its own words.

## Model distribution

The app fetches the exact pairs from the project’s GitHub `models/data/` and `models/picard/` paths. Publish those matching files together with the manifest in `voice_assets.py`; changing either file requires updating its hash and byte length. Model files remain separate from the application build.

Voice origins, pinned revision, hashes and supplied source terms are recorded in [Axiom’s model notes](../models/data/README.md) and [Meridian’s model notes](../models/picard/README.md). Source filenames are preserved. The upstream archive supplies no licence or usage terms; the companion names do not change that source record.

[todo-heartbeat.md](../todo-heartbeat.md) records how these companions were built and the checklist for adding another.

## Verification record

On 4 November 2026, an isolated installation adopted both checksum-verified local model pairs, downloaded and verified the shared Piper engine, and generated real test WAVs: Axiom 5.88 seconds; Meridian 4.48 seconds; both mono at 22,050 Hz. Temporary files were removed afterwards. Public GitHub configuration downloads match their manifest hashes, and both public ONNX URLs report the expected byte length. The complete remote ONNX files were not downloaded again. Listening in game remains a user check.
