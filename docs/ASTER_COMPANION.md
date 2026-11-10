# Aster — officer on watch

Aster is a selectable companion alongside The Watcher. Its original identity is a precise ship’s officer with restrained, dry wit. It uses written dialogue and the app’s factual lookups; it does not require a language model. Added for version 5.7.4.

Aster is an articulated command android: dark machined armour, a continuous smoked visor with cyan focus shutters, titanium cheek plates, a high collar and an asymmetric communications mast. His restrained movements follow the composed officer voice. The dark recess keeps him readable over game scenery; outside the bezel remains transparent.

## Set up

1. Open the **Watcher** page and choose the **Aster** identity card. Only one companion is active at a time.
2. Use **SETUP** on that page for thought frequency. The **Officer’s commentary** choice beside the companion switcher switches dry wit to restrained replies.
3. In **SETUP** on the same page, enable/download Aster’s voice, test it, and choose volume, speed and which thoughts are spoken. Speech waits for the current line and its between-line pause.
4. In **Overlay Studio**, enable the Companion overlay, labelled for whoever is on watch. Its single inspector follows the selected companion. All companions offer the same Studio controls: 54/72/96/144/192/256 pixel sizes, accent, Fixed/Tracking/Expressive focus movement, Calm/Standard/Lively animation intensity, idle animation and frame rate. Aster’s default **Aster cyan** preset pairs cyan light with violet highlights; **Theme accent**, **Ice cyan** and **Brass** remain available. The Watcher retains **HAL red**, while Axiom and Meridian have their [own signature palettes](CREW_COMPANIONS.md#display-and-preferences). Studio settings are shared by the whole crew except colour, which is each companion’s own: size, focus and animation apply to every companion, along with position, opacity, thought layout and frame rate. Size changes resize the live overlay immediately; the displays fill the same visible diameter.
5. For spoken input, configure your microphone, recognition model and talk key in **Settings → Voice**. Command names, aliases, keyboard bindings and recorded sequences remain there. Keyboard/controller shortcuts remain in **Settings → Hotkeys**.

The BRIDGE chat accepts typed commands without a microphone. For example:

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

Small reflections on Aster's appointment begin after its first story passage. Chapter recollections use only completed chapters heard at least a day earlier; later characters and revelations stay sealed until then. After all 48 passages, Aster can reflect on its present posting, standing on. Watcher's dreams, shutter choices, eye lore and mood arcs remain part of the Watcher's own story.

After three hours in a session, an occasional break reminder can join the quiet watch, at most once an hour. Queued journal facts about your career, power, squadron or carrier can also be acknowledged. Calling Aster can produce a contextual observation as well as its direct call replies. These additions use the same voice/caption queue and preserve the selected idle interval, danger checks, Off setting and minor-wording exhaustion. Casual conversation remains available on Rare both in port and underway; **Only what matters** still excludes it from speech.

### Writing postcards

On **Postcards → Studio**, choose **Aster's** under **The note** while Aster is selected. This author option follows the active companion automatically: switching to Watcher makes it **The Watcher's**. Existing automatic-note settings already use this behaviour. **Your own words**, your custom signature and **None** remain available.

Aster has 54 short original officer's notes about the actual screenshot context: firsts, notable worlds, distance from Sol, surface stops, port watches and stellar landmarks. **Restrained** uses 36 plain notes; **Dry wit** adds 18 with its own understated humour. For example: “A scenic use of archival space. I shall defend the allocation if challenged.” Its signature is **Aster** in the floating card, saved PNG, editor and caption text file. Each card keeps the author who wrote it, including after a companion switch.

Live Aster notes use its saved wording rotations. Studio previews show the selected author's sample without consuming that rotation. The selected companion's thoughts and Companion overlay must be enabled for an automatic note, matching the existing Watcher rule; speech can remain off. Existing saved postcards retain their original notes and signatures.

### In port

Aster keeps you company while docked, aboard a carrier or on a station concourse. Its port watch draws on separate preparations, crew-register, company and rest topics, with additional wording for the actual berth or concourse. Both Dry wit and Restrained have varied lines. A docked `Location` restores the station; when reopening the app or switching companions mid-session, fresh live telemetry can also establish the current berth and wake Aster without replaying historical events. Stale saved location data alone does not wake it. You do not need to undock and dock again to give it that context.

Port remarks remain eligible on Rare, while keeping the selected overall pace: at least five minutes between idle remarks on Chatty, ten on Occasional and twenty on Rare, after the initial quiet interval. Each port topic still rests for at least half an hour, uses fresh wording first and falls silent after its minor-remark bank is exhausted. Off stays silent. If you want these casual lines spoken too, use **Most thoughts** or **Every thought** in Aster's voice settings; **Only what matters** continues to reserve speech for important reports. Normal commands, warnings and hatchling limits retain their existing behaviour.

Watcher and Aster use the same caption presenter in the floating overlay and the BRIDGE panel. When voice is enabled, both keep the line being spoken and wait for a queued reply’s own playback, including model loading and the pause between lines. Watcher’s character-by-character typing, punctuation pauses and highlighted journal words follow the actual audio clock, including when opening the panel midway through a line. Brief gaps in the live feed do not reveal the rest of a reply early or rewind its text. Full captions remain visible through long replies; synthesis failures fall back to text. With voice off, each companion uses the same natural typing system with its own personality. The BRIDGE panel reserves room for the full line so its controls stay still while text appears; LOG and the chat remain conversation records.

**Relieved of the Watch** is Aster's story: 48 passages across eight chapters (rewritten in 5.7.4). Aster keeps a handover book. Every officer who stands a watch eventually hands it to someone else: course, hazards and standing orders. The book holds one entry from each captain Aster served: a freighter captain, a surveyor, a rescue pilot, a miner and an escort, plus a maintenance technician from six years in a locked hangar. None of them ever relieved Aster. The last page is yours. It is original fiction, separate from The Watcher's origins, dreams and books, and makes no claim to official Elite history.

**How it unlocks.** Passages arrive in order during quiet moments: at least 10 minutes into a session, after 2 quiet minutes, never during danger, and at least 45 minutes apart. The first chapter opens after about 15 minutes together. Each later chapter opens when you do something its captain would recognise, or after about 18 more hours together if you don't, so no play style is locked out:

| Chapter | Opens with |
| --- | --- |
| I · I Have the Watch | Time together (about 15 minutes) |
| II · The Freighter Captain | Three deliveries: market sales, depot deliveries or completed missions |
| III · The Surveyor | Three survey findings: first discoveries or mapped worlds |
| IV · The Rescue Pilot | A close call: a repair at a station, an escaped interdiction or a rebuy |
| V · The Miner | Three pieces of patient work: refined ore, analysed organics or landings |
| VI · The Escort | Two brushes with trouble: bounties, combat bonds or escaped interdictions |
| VII · The Empty Ship | Three returns to systems visited together, and two real days after chapter VI |
| VIII · Standing On | 150 jumps together, and three real days after chapter VII |

Hours only count while Aster is the active companion. **STORY** lists heard chapters. Unopened chapters show only their numeral; hovering one shows how it opens. The note below says what the next chapter waits for and how long until it opens anyway. Once a captain's chapter is told, **echoes** can follow: a delivery, a careful survey, a close call, an honest yield, an ended engagement or a return can stir a short remark about that captain. Each echo rests for a day. The STORY page lists the echoes found and how to find the rest. When the book is complete, **READ THE WHOLE STORY** shows it in full, and **SAVE BOOK** exports the heard story and service memories.

**Upgrading from The Unfinished Manifest.** The earlier story is retired. Passages heard from it stay in the memory file but are no longer shown; Aster starts the handover book from chapter I. Its hours, sessions, name, preferences and service memories are unchanged.

## Your name: The Crew Register

Aster reads your commander name from the journal and has a short, original three-part introduction about the person behind the rank. After roughly fifteen minutes together, it waits for a quiet moment to notice the name in its register. At least three minutes later, with room between reports, it asks whether to use that name, retain **Commander**, or call you something you prefer. Your choice concludes the introduction; it does not change the main six-chapter story.

Answer on the BRIDGE or with the existing answer hotkeys. While the naming question is pending, the BRIDGE chat and configured voice recognition also accept `yes`, `keep it Commander`, or `Aster, call me Jeff`. Choosing **Call me something else** leaves room to give the name afterward or enter it under **YOU → YOUR NAME**. The pronunciation field and **HEAR IT** use the selected companion's voice; a chosen nickname can have its own pronunciation there too.

The introduction and choice stay in Aster's own commander memory. Heard passages can be reread under YOUR NAME and appear in its exported book. Existing manually chosen preferences are respected. An unanswered question expires after five minutes and is left alone for at least two weeks before another attempt. Quiet/danger checks keep it out of busy moments. Once approved, your journal name or chosen nickname becomes Aster's normal form of address in its own greetings, command replies, reports, story dialogue and farewells. For example, “Opening galaxy map, Jeff” and “Watch complete, Jeff” can both occur in the same session. Choose **Commander** to retain the title. The pronunciation field follows the chosen name, and heard story passages retain the words spoken at the time. A journal name change gets an original register update rather than restarting the introduction.

## Memory and switching

Each commander keeps a separate `aster_memory.json` beside their existing `watcher_memory.json`. These are runtime story files, not development notes. Development notes for this feature are indexed in `C:/Users/Jeff/.claude/projects/d--Programming-Elite-SurveyAnalysis/memory/project_aster_574.md`.

Switching saves the outgoing mind and pauses its clock; it does not convert or reset The Watcher’s memory. Aster’s humour, frequency, voice and display preferences belong to the commander profile. Reset affects the selected companion and backs up its memory first.

A switch stops the old voice and discards queued speech, closes recognition, and rejects late recognition/uplink replies from the previous identity. Existing journal, microphone, overlay and hotkey services are reused. API routes and overlay identifiers remain compatible; snapshots include the selected identity.

## Three.js officer

The floating overlay, BRIDGE panel and boot screen share `web/assets/aster-3d.js` and the articulated geometry in `web/assets/officer-robots.js`. The design is built directly from meshes: curved armour, a smoked visor, independent focus shutters, a moving jaw, collar and shaped shoulders. No portrait bitmap or external model download is used. The outer diameter remains the same as the other companions at every Studio size.

Aster glances towards activity, blinks, makes small head movements, and wears the mood of his current thought. Fixed focus holds his gaze and orientation still. Actual voice playback opens the jaw and lights the speech bars; microphone levels and queued lines do not move his mouth. The shared caption presenter continues to control text timing.

His cyan/violet instrument track and segmented arcs move behind the helmet. The watch bells, six-duty watch bill, service marks and double acknowledgement pulse remain. A docking grant puts the pad number on his chest and sends a single sweep around the halo. His small command prism sits in the chest medallion and steps aside for the pad display. Confirmed danger, fuel and heat warnings use amber.

Size, accent, focus, liveliness, idle animation and frame rate use the existing Studio controls. Idle animation Off parks quiet displays; speech and events can still wake them. Reduced motion parks continuous movement and applies expressions immediately. Hidden displays stop drawing. Materials, geometry and the procedural reflection map are released when the display is destroyed.

## Piper assets and release preparation

Aster uses the current matching pair in `models/jarvis/onnx/`, supplied from [praharshbhatt/jarvis-piper-checkpoints](https://huggingface.co/datasets/praharshbhatt/jarvis-piper-checkpoints). The supplied README identifies the root-level `en_GB-alan-medium.onnx` and root JSON as older historical files; those are not the selected voice. Do not mix an older root model with the current configuration.

The selected model is British English, Piper medium, one speaker and 22,050 Hz. Both companions reuse one Piper engine. The Aster receipt remains `models/jarvis/installed.json`; the Watcher’s receipt remains `models/installed.json`. Removing one voice preserves the other installed voice and the shared engine. A source checkout adopts an existing local pair only after checking both hashes. Old Aster receipts require verification of the replacement pair.

| Runtime file under `models/jarvis/onnx/` | Bytes | SHA-256 |
| --- | ---: | --- |
| `en_GB-jarvis-medium.onnx` | 63,511,037 | `0b222b43cb882aac25c4eb1b648c80fd855de423351dc778c01102e578c3a64d` |
| `en_GB-jarvis-medium.onnx.json` | 5,068 | `8e189c86e055b672a3380cc68e1c74fe88206b1b0b5c5b1ac791b5511921be90` |

Download source: `https://raw.githubusercontent.com/insert3coins/VoidCompass/master/models/jarvis/onnx/`, using those exact filenames. Publish this current pair at that path when updating the GitHub model assets. The supplied upstream model card limits use to personal, non-commercial purposes; see `models/jarvis/README.md` and `MODEL_CARD.md`. Aster’s character and lore are original and separate from the source voice.

Models remain outside the application archive. Training archives, historical root exports, metadata CSV and installation receipts are not runtime download assets. Documentation is included by the build process.

**The crew.** Aster also tells its six-passage *Coming Aboard* account and hands over the watch to its crewmates by name. See [the crew](CREW_COMPANIONS.md#the-crew-how-they-came-aboard).

## Keepsakes and deeper company

- **Time capsules, constellations, On this day and anniversaries** are spoken by Aster when it is on watch, in either commentary style. With capsule delivery set to "your companion, or a notice", a notice still appears if it stays quiet.
- **Its readings of you.** The BRIDGE and YOU pages show Aster's confidence and morale. They move with real events: answering its questions, close calls, repairs, data sales, losing the ship and meeting other commanders' companions.
- **Watch Notes.** When you log off, Aster writes a short note about the watch. The YOU page keeps them, the book export includes them, and it may mention the last one when you return.
- **Other commanders' companions.** Copy Aster's code from the YOU page; paste a friend's code (from any companion) to meet theirs.
- **A request.** Once, after chapter VII, Aster asks to be taken to the system where it first came aboard. The request appears on the BRIDGE, can become an expedition objective, and Aster notices when you arrive.
- **Achievements.** Four in the Aster category: the first passage, the whole story, every echo, and *Received the Watch* for keeping its request.
- **Captain's Log.** Sessions flown with Aster on watch end with its own closing paragraph, signed Aster.
