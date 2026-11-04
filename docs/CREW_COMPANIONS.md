# Axiom and Meridian — preview companions

Available in **5.7.4** alongside The Watcher and Aster. Select **Axiom** or **Meridian** at the top of the companion page. The deck title, NOW display, VOICE and TALK pages follow that choice. Their lore, stories, personal introductions and postcard writing are pending.

| Companion | Voice pair | Display |
| --- | --- | --- |
| Axiom | `models/data/en_US-data_7024-medium.onnx` and matching `.onnx.json` | Violet/cyan particle torus surrounding a floating lattice crystal, with orbiting light, ripples and attention movement |
| Meridian | `models/picard/en_US-picard_7399-medium.onnx` and matching `.onnx.json` | Gold/blue anonymous wireframe portrait, scan bands, instrument rings and speech-driven lips |

The displays are original procedural Three.js geometry on a transparent background. The supplied ring and HUD portrait references inspired their structure. No reference artwork or actor portrait is bundled.

Axiom and Meridian sit inside a defined instrument bezel, with a dark translucent recess behind their detail. This follows the Watcher’s contrast treatment so the holograms remain readable over bright planets and busy cockpit scenery. Axiom’s centre contains a translucent lattice crystal; the game remains visible between its edges and the surrounding ring. Meridian has dark glass behind its portrait. The space outside the instrument remains transparent. Their particle flow, wireframe features and existing Studio controls are retained.

## Try them

1. Choose a companion, then open **VOICE** and enable/download its voice. Downloads share the Piper engine and verify each companion’s own model pair by SHA-256. A checkout containing the matching pair keeps those files and downloads only the engine when needed.
2. Click **TEST THE VOICE**. Each has its own short test sentence.
3. Enable the companion overlay in **Overlay Studio** for live replies, and set **Thoughts** above Off.
4. Open **TALK** and type **Hello Axiom** or **Hello Meridian**. Each has six rotating welcome messages. New game logins also use these welcomes; duplicate login events are coalesced.
5. Ask **Axiom, what can you do?** or **Meridian, what can you do?** for a short practical rundown. Configured commands and factual lookups use the existing shared services.
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

Axiom’s central crystal slowly turns and breathes at idle. Listening draws light inward along its connections; working sends faster pulses through the lattice. Speech expands and lights the core with the real audio level, and alerts use warning colours. Aster uses the same reactions in a smaller hexagonal prism inside its command interface. These cores appear in both the floating overlay and the deck NOW panel, using the selected palette and existing motion controls.

Meridian keeps its portrait. Its upper and lower lips now form a visible mouth opening driven by the actual speech envelope, with a quick attack and a smooth close during pauses. Queued text and microphone input do not move the lips. Warning speech still moves the mouth while the portrait shows its alert colours. When audio ends the mouth closes; Reduced motion keeps it still. This is amplitude-driven mouth movement, rather than phoneme-based lip sync.

The floating overlay and deck NOW panel use the existing shared caption presenter and speech queue: queued captions wait for their line and follow its actual audio clock. Switching companions closes the previous speaker and recognition session. Runtime memories are `<identity>_memory.json` in the commander profile.

Their **STORY** page clearly marks the unfinished content. There is no Watcher/Aster story, name-introduction arc, dream or automatic postcard note substituted for these companions. You can manually set their preferred form of address and pronunciation under **YOU**.

## Model distribution

The app fetches the exact pairs from the project’s GitHub `models/data/` and `models/picard/` paths. Publish those matching files together with the manifest in `voice_assets.py`; changing either file requires updating its hash and byte length. Model files remain separate from the application build.

Voice origins, pinned revision, hashes and supplied source terms are recorded in [Axiom’s model notes](../models/data/README.md) and [Meridian’s model notes](../models/picard/README.md). Source filenames are preserved. The upstream archive supplies no licence or usage terms; the companion names do not change that source record.

Follow [todo-heartbeat.md](../todo-heartbeat.md) for the remaining original-character work and the reusable integration checklist.

## Verification record

On 4 November 2026, an isolated installation adopted both checksum-verified local model pairs, downloaded and verified the shared Piper engine, and generated real test WAVs: Axiom 5.88 seconds; Meridian 4.48 seconds; both mono at 22,050 Hz. Temporary files were removed afterwards. Public GitHub configuration downloads match their manifest hashes, and both public ONNX URLs report the expected byte length. The complete remote ONNX files were not downloaded again. Listening in game remains a user check.
