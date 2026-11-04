# Aster — officer on watch

Aster is a selectable companion alongside The Watcher. Its original identity is a precise ship’s officer with restrained, dry wit. It uses written dialogue and the app’s factual lookups; it does not require a language model. Added for version 5.7.4.

Its halo and command core now have a defined instrument bezel and dark translucent recess, using the Watcher’s contrast treatment for visibility over game scenery. The centre remains open, with the existing animated halo and segmented core; the space outside the display remains transparent. The same shared frame is used by Axiom and Meridian around their own designs.

## Set up

1. Open the **Watcher** page and choose the **Aster** identity card. Only one companion is active at a time.
2. Use **SETTINGS** on that page for thought frequency. The **Officer’s commentary** choice beside the identity cards switches dry wit to restrained replies.
3. Open **VOICE** on the same page to enable/download Aster’s voice, test it, and choose volume, speed and which thoughts are spoken. Speech waits for the current line and its between-line pause.
4. In **Overlay Studio**, enable the Companion overlay, labelled for whoever is on watch. Its single inspector follows the selected companion. All companions offer the same Studio controls: 54/72/96/144/192/256 pixel sizes, accent, Fixed/Tracking/Expressive focus movement, Calm/Standard/Lively animation intensity, idle animation and frame rate. Aster’s default **Aster cyan** preset pairs cyan light with violet highlights; **Theme accent**, **Ice cyan** and **Brass** remain available. The Watcher retains **HAL red**, while Axiom and Meridian have their [own signature palettes](CREW_COMPANIONS.md#display-and-preferences). Display size carries across companion switches and resizes the live overlay immediately; the displays fill the same visible diameter. Colour, focus and animation preferences remain separate. Position, opacity, thought layout and frame rate remain shared.
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

Aster has 50 original greetings, ten capability rundowns, more than 1,400 event wordings and alternatives for every ship/app command outcome. Its officer dialogue covers exploration, combat, trade, mining, missions, vehicles and quiet travel, including unsuccessful commands and unavailable controls.

It follows the Watcher’s repeat rules: unused wording first over 30 days, quiet rather than repeating a recent minor remark, and older wording when an important report must still be made. A fixed minor remark rests for three days after its bank is exhausted; a remark containing changing journal facts rests for a day. Matching words shared by different event topics are checked too. Everyday topics have deeper banks, each idle topic rests for at least half an hour, and the overall idle interval follows the selected frequency: five minutes on Chatty, ten on Occasional and twenty on Rare. An old Galnet headline stays remembered for 30 days.

Greetings, capability rundowns and command acknowledgements finish a complete wording cycle before starting another, avoiding the previous cycle’s final line at the boundary. Their rotations survive restarts and companion switches. Event wording and headline history are kept separately from the rolling activity log, so a busy spell of commands does not make earlier remarks new again. **Officer’s commentary → Restrained** still offers varied reports, using its own plain alternatives instead of repeatedly choosing one fixed line. Immediate warnings stay clear, and requested factual reports continue to give the recorded readings.

Aster acknowledges each new live **LoadGame**, including quick relogs and returning from the main menu while VoidCompass stays open. Its automatic welcomes have their own saved wording rotation and use your approved name. Repeated delivery of the same timestamped login is ignored. If an earlier journal event or fresh port snapshot has just prompted a welcome within five seconds, that welcome serves the same login. Thoughts set to **Off** stay silent; spoken welcomes use the existing voice switch and speech queue. Historical startup replay retains its existing suppression.

For example, repeated `Aster, open the galaxy map` requests can receive “Opening galaxy map, Commander”, “Displaying galaxy map” and other acknowledgements before the cycle repeats. `Hello Aster` and `Aster, what can you do?` each have their own remembered rotation. Unsolicited commentary can simply stay quiet when it has nothing fresh to add.

At shutdown, Aster closes the completed watch using the same Captain's Log session totals as Watcher. Every summary-bearing sign-off identifies those figures as the work just recorded, with a full sentence break before the farewell. For example: “Closing this watch, Commander. Completed this session: 19 jumps. Until our next watch.” A session with no recorded totals uses its separate quiet-watch farewell. Each bank now has 35 Dry wit variants or 24 Restrained variants. Its saved farewell rotation uses the entire applicable set before reuse, including across restarts and long gaps, and avoids the last line when a new cycle begins. A finite set eventually cycles; consecutive shutdowns keep different wording.

Hatchling remarks share a subject cooldown even though the pet has its own timer. Casual observations and comments on its chatter wait for a quiet interval and at least half an hour since the last hatchling remark; they also count toward Aster's overall idle interval. Ordinary pet events rest for at least ten minutes (twenty on Rare). A genuinely new growth stage can be acknowledged sooner. Actual toy, trick and growth reports name the finding, learned trick or new form. Each moment carries its own identity and timestamp, so repeated delivery or a restart cannot turn it into another announcement; old moments are ignored.

### What Aster notices during quiet watches

Aster shares the Watcher's surroundings and activity records. It can comment on the current star/system, distance from home, ship or surface vehicle, travel, mining rings, music, Galnet, the time of day and your growing association. It also has its own wording for learned flight, survey, cargo, combat, trade and activity habits. Those observations wait for enough recorded activity to support the figures; they are not guesses about your play style. Each habit subject rests for at least three hours.

Older records can return as conversation: postcards at least six hours old, and arrivals or service moments at least two days old. For example, “We reached Sol three days ago. I have kept the arrival in our service record.” Aster can recall a docking, completed mission or sale of exploration/biological data using the actual place in its log. Each particular memory or postcard rests for 30 days across restarts, independently of the wording rotation. Postcard remarks also have a ten-hour subject rest.

Small reflections on Aster's appointment begin after its first story passage. Chapter recollections use only completed chapters heard at least a day earlier; later characters and revelations stay sealed until then. After all 48 passages, Aster can reflect on its present posting. Watcher's dreams, shutter choices, eye lore and mood arcs remain part of the Watcher's own story.

After three hours in a session, an occasional break reminder can join the quiet watch, at most once an hour. Queued journal facts about your career, power, squadron or carrier can also be acknowledged. Calling Aster can produce a contextual observation as well as its direct call replies. These additions use the same voice/caption queue and preserve the selected idle interval, danger checks, Off setting and minor-wording exhaustion. Casual conversation remains available on Rare both in port and underway; **Only what matters** still excludes it from speech.

### Writing postcards

On **Postcards → Studio**, choose **Aster's** under **The note** while Aster is selected. This author option follows the active companion automatically: switching to Watcher makes it **The Watcher's**. Existing automatic-note settings already use this behaviour. **Your own words**, your custom signature and **None** remain available.

Aster has 54 short original officer's notes about the actual screenshot context: firsts, notable worlds, distance from Sol, surface stops, port watches and stellar landmarks. **Restrained** uses 36 plain notes; **Dry wit** adds 18 with its own understated humour. For example: “A scenic use of archival space. I shall defend the allocation if challenged.” Its signature is **Aster** in the floating card, saved PNG, editor and caption text file. Each card keeps the author who wrote it, including after a companion switch.

Live Aster notes use its saved wording rotations. Studio previews show the selected author's sample without consuming that rotation. The selected companion's thoughts and Companion overlay must be enabled for an automatic note, matching the existing Watcher rule; speech can remain off. Existing saved postcards retain their original notes and signatures.

### In port

Aster keeps you company while docked, aboard a carrier or on a station concourse. Its port watch draws on separate preparations, crew-register, company and rest topics, with additional wording for the actual berth or concourse. Both Dry wit and Restrained have varied lines. A docked `Location` restores the station; when reopening the app or switching companions mid-session, fresh live telemetry can also establish the current berth and wake Aster without replaying historical events. Stale saved location data alone does not wake it. You do not need to undock and dock again to give it that context.

Port remarks remain eligible on Rare, while keeping the selected overall pace: at least five minutes between idle remarks on Chatty, ten on Occasional and twenty on Rare, after the initial quiet interval. Each port topic still rests for at least half an hour, uses fresh wording first and falls silent after its minor-remark bank is exhausted. Off stays silent. If you want these casual lines spoken too, use **Most thoughts** or **Every thought** in Aster's voice settings; **Only what matters** continues to reserve speech for important reports. Normal commands, warnings and hatchling limits retain their existing behaviour.

Watcher and Aster use the same caption presenter in the floating overlay and the NOW panel. When voice is enabled, both keep the line being spoken and wait for a queued reply’s own playback, including model loading and the pause between lines. Watcher’s character-by-character typing, punctuation pauses and highlighted journal words follow the actual audio clock, including when opening the panel midway through a line. Brief gaps in the live feed do not reveal the rest of a reply early or rewind its text. Full captions remain visible through long replies; synthesis failures fall back to text. With voice off, each companion uses the same natural typing system with its own personality. The NOW panel reserves room for the full line so its controls stay still while text appears; SAID and TALK remain conversation records.

**The Unfinished Manifest** contains 48 passages across six chapters. A relief ship’s former manifest officer carries an unsigned arrival report. Its story concerns names, duty and the space a crew leaves for someone who may return. It is original fiction, separate from The Watcher’s origins, dreams and books, and makes no claim to official Elite history.

The account unfolds in order during quiet periods, after time on watch. Later chapters also respond to recorded deliveries, dockings, jumps and returns, with time-based alternatives so no particular play style is compulsory. The first passage opens after about 15 minutes together; the final chapter unfolds over a much longer association. There is at least 45 minutes between passages, a settling period after session start, and no story interruption during danger. **STORY** shows only passages already heard and seals unopened chapter titles. **SAVE BOOK** exports the heard story and service memories.

## Your name: The Crew Register

Aster reads your commander name from the journal and has a short, original three-part introduction about the person behind the rank. After roughly fifteen minutes together, it waits for a quiet moment to notice the name in its register. At least three minutes later, with room between reports, it asks whether to use that name, retain **Commander**, or call you something you prefer. Your choice concludes the introduction; it does not change the main six-chapter story.

Answer in the NOW panel or with the existing answer hotkeys. While the naming question is pending, TALK and configured voice recognition also accept `yes`, `keep it Commander`, or `Aster, call me Jeff`. Choosing **Call me something else** leaves room to give the name afterward or enter it under **YOU → YOUR NAME**. The pronunciation field and **HEAR IT** use the selected companion's voice; a chosen nickname can have its own pronunciation there too.

The introduction and choice stay in Aster's own commander memory. Heard passages can be reread under YOUR NAME and appear in its exported book. Existing manually chosen preferences are respected. An unanswered question expires after five minutes and is left alone for at least two weeks before another attempt. Quiet/danger checks keep it out of busy moments. Once approved, your journal name or chosen nickname becomes Aster's normal form of address in its own greetings, command replies, reports, story dialogue and farewells. For example, “Opening galaxy map, Jeff” and “Watch complete, Jeff” can both occur in the same session. Choose **Commander** to retain the title. The pronunciation field follows the chosen name, and heard story passages retain the words spoken at the time. A journal name change gets an original register update rather than restarting the introduction.

## Memory and switching

Each commander keeps a separate `aster_memory.json` beside their existing `watcher_memory.json`. These are runtime story files, not development notes. Development notes for this feature are indexed in `C:/Users/Jeff/.claude/projects/d--Programming-Elite-SurveyAnalysis/memory/project_aster_574.md`.

Switching saves the outgoing mind and pauses its clock; it does not convert or reset The Watcher’s memory. Aster’s humour, frequency, voice and display preferences belong to the commander profile. Reset affects the selected companion and backs up its memory first.

A switch stops the old voice and discards queued speech, closes recognition, and rejects late recognition/uplink replies from the previous identity. Existing journal, microphone, overlay and hotkey services are reused. API routes and overlay identifiers remain compatible; snapshots include the selected identity.

## Three.js halo

The live overlay and dashboard use original procedural Three.js geometry in `web/assets/aster-3d.js`: a flowing light halo, layered filaments, drifting particles and a hexagonal command interface containing a floating lattice prism. Counter-rotating segmented arcs, fine calibration marks and scanning traces give the centre an instrument style. There are no eyes, paired dots, central star or opaque disk. The game remains visible between the prism’s edges and the surrounding interface. An orthographic camera keeps its visible envelope consistent with Watcher and the selected Studio size.

The design takes its direction from the user’s local `Data Overlay.avif` reference, rebuilt as animated geometry and shaders. The reference bitmap and its dark background are not bundled or displayed. Aster’s NOW panel uses the same halo with an officer’s station treatment, a **CALL ASTER** control and a live ON WATCH/LISTENING/ASSESSING/REPLYING/ATTENTION state label. These states come from the existing journal, microphone and speech feeds.

Aster’s command core makes subtle orientation changes during quiet periods, settles when docked and responds to flight and scanning activity. Journal events draw its focus toward the corresponding overlay, and rare finds can prompt a longer response and brief flare. New snapshots do not replay old events. Listening and working move a scanning trace through the core; speech brightens its circuits and sends ripples through the halo using the actual Piper envelope. Confirmed danger, fuel and heat warnings use amber. All of this is procedural animation driven by existing signals.

The central prism slowly turns and breathes at idle, gathers light along its connections when listening and carries quicker pulses while working. It expands with the real speech level. Axiom shares these reactions with its own faceted crystal shape through `web/assets/companion-core.js`; both use their existing renderer clock, frame cap and motion preferences.

**Focus movement** controls how both companions follow activity. Fixed focus centres the display, Tracking follows flight and journal activity, and Expressive increases its reach. Each companion saves its own setting. **Idle animation** controls continuous standby motion; disabling it still permits reactions to voice and events. Global/OS reduced motion keeps the instrument still, including when speaking, while allowing the current readings and voice level to update. Hidden renderers park their animation loop. Pixel ratio, frame rate and GPU resources remain bounded, and geometry/materials are disposed on teardown.

No stock image, EPS or premium artwork is embedded. WebGL/hardware acceleration is required; a clear error appears if the instrument cannot start.

The optional design sandbox remains at `web/companion-preview/`, served from a local HTTP server rooted at `web`. Its state controls simulate signals; production uses the live data above.

## Piper assets and release preparation

Aster uses the current matching pair in `models/jarvis/onnx/`, supplied from [praharshbhatt/jarvis-piper-checkpoints](https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints). The supplied README identifies the root-level `en_GB-alan-medium.onnx` and root JSON as older historical files; those are not the selected voice. Do not mix an older root model with the current configuration.

The selected model is British English, Piper medium, one speaker and 22,050 Hz. Both companions reuse one Piper engine. The Aster receipt remains `models/jarvis/installed.json`; the Watcher’s receipt remains `models/installed.json`. Removing one voice preserves the other installed voice and the shared engine. A source checkout adopts an existing local pair only after checking both hashes. Old Aster receipts require verification of the replacement pair.

| Runtime file under `models/jarvis/onnx/` | Bytes | SHA-256 |
| --- | ---: | --- |
| `en_GB-jarvis-medium.onnx` | 63,511,037 | `0b222b43cb882aac25c4eb1b648c80fd855de423351dc778c01102e578c3a64d` |
| `en_GB-jarvis-medium.onnx.json` | 5,068 | `8e189c86e055b672a3380cc68e1c74fe88206b1b0b5c5b1ac791b5511921be90` |

Download source: `https://raw.githubusercontent.com/insert3coins/VoidCompass/master/models/jarvis/onnx/`, using those exact filenames. Publish this current pair at that path when updating the GitHub model assets. The supplied upstream model card limits use to personal, non-commercial purposes; see `models/jarvis/README.md` and `MODEL_CARD.md`. Aster’s character and lore are original and separate from the source voice.

Models remain outside the application archive. Training archives, historical root exports, metadata CSV and installation receipts are not runtime download assets. Documentation is included by the build process.
