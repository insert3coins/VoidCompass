# Aster — officer on watch

Aster is a selectable companion alongside The Watcher. Its original identity is a precise ship’s officer with restrained, dry wit. It uses written dialogue and the app’s factual lookups; it does not require a language model. Added for version 5.7.4.

## Set up

1. Open the **Watcher** page and choose the **Aster** identity card. Only one companion is active at a time.
2. Use **SETTINGS** on that page for thought frequency. The **Officer’s commentary** choice beside the identity cards switches dry wit to restrained replies.
3. Open **VOICE** on the same page to enable/download Aster’s voice, test it, and choose volume, speed and which thoughts are spoken. Speech waits for the current line and its between-line pause.
4. In **Overlay Studio**, enable the existing Watcher/companion overlay. Aster has 96, 144 and 192 pixel sizes, theme/cyan/brass accents, and an instrument-motion switch. Existing position, opacity, thought layout and frame-rate controls still apply.
5. For spoken input, configure your microphone, recognition model and talk key in **Settings → Voice**. Command names, aliases, keyboard bindings and recorded sequences remain there. Keyboard/controller shortcuts remain in **Settings → Hotkeys**.

TALK accepts typed commands without a microphone. For example:

- `Hello Aster`
- `Aster, what can you do?`
- `Aster, open the galaxy map`
- `Aster, open the system map`
- `Aster, where are we?`
- `Aster, where can I sell platinum?`

Aster’s address is optional. Configured command names and aliases still apply after the address; disabling a command’s default phrases continues to disable them. Ship actions require their existing Elite bindings and permissions. Market searches use the existing uplink and integration settings.

## Dialogue and story

Aster has 50 original greetings, ten capability rundowns, its own ship/app acknowledgements and event dialogue for exploration, combat, trade, mining, missions, vehicles and quiet travel. Immediate warnings remain plain. The restrained option limits event variations and greetings rather than changing the officer’s identity.

**The Unfinished Manifest** contains 48 passages across six chapters. A relief ship’s former manifest officer carries an unsigned arrival report. Its story concerns names, duty and the space a crew leaves for someone who may return. It is original fiction, separate from The Watcher’s origins, dreams and books, and makes no claim to official Elite history.

The account unfolds in order during quiet periods, after time on watch. Later chapters also respond to recorded deliveries, dockings, jumps and returns, with time-based alternatives so no particular play style is compulsory. The first passage opens after about 15 minutes together; the final chapter unfolds over a much longer association. There is at least 45 minutes between passages, a settling period after session start, and no story interruption during danger. **STORY** shows only passages already heard and seals unopened chapter titles. **SAVE BOOK** exports the heard story and service memories.

## Memory and switching

Each commander keeps a separate `aster_memory.json` beside their existing `watcher_memory.json`. Switching saves the outgoing mind and pauses its clock; it does not convert or reset The Watcher’s memory. Aster’s humour, frequency, voice and display preferences belong to the commander profile. Reset affects the selected companion and backs up its memory first.

A switch stops the old voice and discards queued speech, closes recognition, and rejects late recognition/uplink replies from the previous identity. Existing journal, microphone, overlay and hotkey services are reused. API routes and overlay identifiers remain compatible; snapshots include the selected identity.

## Three.js instrument

The live overlay and dashboard use original procedural Three.js geometry in `web/assets/aster-3d.js`: layered instrument rings, instanced ticks, segmented annuli, a six-spoke centre and a speech band. Listening follows the microphone level; speaking follows Piper’s playback envelope; recognition and pending lookups show a working state; confirmed danger, low fuel and overheating show an alert. Reduced motion keeps a still instrument while retaining signal updates. Hidden renderers are parked, pixel ratio is bounded, and resources are disposed on page teardown.

The local HUD reference inspired the concentric instrument direction. No stock image, EPS or premium artwork is embedded. WebGL/hardware acceleration is required; a clear error appears if the instrument cannot start.

The optional design sandbox remains at `web/companion-preview/`, served from a local HTTP server rooted at `web`. Its state controls simulate signals; production uses the live data above.

## Piper assets and release preparation

Aster uses the supplied pair in `models/jarvis/`. The folder name and filenames identify the source model, not Aster’s character or lore. Both companions reuse one Piper engine; model installation receipts are separate. Removing one voice preserves the other installed voice and its shared engine. An existing local pair is checksum-verified and adopted during installation.

| Runtime file | Bytes | SHA-256 |
| --- | ---: | --- |
| `en_US-Jarvis_Real-medium.onnx` | 63,516,050 | `b947bfec049798c9df91f6010625db527dcb5ad00af011fa05036001df6eec2d` |
| `en_US-Jarvis_Real-medium.onnx.json` | 7,611 | `53d944f306bab1655dbdb2bae22919e5b702781caa112f4430eeeebbcbf2f537` |

Download source: `https://raw.githubusercontent.com/insert3coins/VoidCompass/master/models/jarvis/`, using those exact filenames. **Release preparation:** publish the runtime pair there so installed releases can download it; this implementation does not push files to GitHub. Record the supplied model’s upstream source/licence in `models/jarvis/MODEL_CARD.md` before redistribution. Character originality does not establish rights to a source voice model.

Models remain outside the application archive. Training archives, metadata CSV and installation receipts are not runtime download assets. Documentation is included by the existing build process.
