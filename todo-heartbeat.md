# Adding another heartbeat companion

Reusable implementation checklist, based on **The Watcher → Aster in v5.7.4**. Last reviewed: **4 November 2026**.

Use this when adding a fresh companion with its own character, lore, dialogue, memory, Piper voice and animated display. The goal is the same working capabilities and settings as the Watcher, expressed through the new companion's identity.

The checked items below record work completed for Aster. The unchecked items form a fresh checklist for the next companion. This document does not register or create another companion by itself.

## Start here

1. Complete the identity brief below.
2. Read the shared-resource map and the Aster completion record.
3. Work through the numbered implementation checklist in order.
4. Finish implementation and documentation before writing/running the regression tests for the change.
5. Verify every companion, both display surfaces and switching between them before release.

**Current limitation:** the code supports Watcher and Aster through several explicit two-way branches. Adding a name to `IDENTITIES` is only the first step. Audit the dispatch points listed below so a third identity cannot silently receive Watcher's model, memory, lore or display.

## New companion brief — fill this in first

| Decision | New companion |
| --- | --- |
| Stable internal ID, lowercase | `<companion_id>` |
| Display name and spoken address | `<Display Name>` |
| Character, duties and relationship to the commander | To decide |
| Voice/tone and examples of ordinary replies | To decide |
| Optional commentary modes and how each should sound | To decide |
| Original story title, premise, themes and ending | To decide |
| Chapter/passage plan and time/event gates | To decide |
| Commander-name introduction, theme and three short beats | To decide |
| When it may use a personal name and its formal address | To decide; Aster follows Watcher's once-per-session personal-name policy |
| Visual identity, motion language and panel treatment | To decide |
| Piper model source, local folder and exact ONNX/JSON pair | To decide |
| Published download URL and supplied attribution/terms | To record |
| Runtime memory filename | `<companion_id>_memory.json` |
| Settings prefix | `<companion_id>_` |
| User-selected release version | To confirm when a version is chosen |

Choose a stable ID once. Keep runtime filenames and profile keys stable when changing the visible name later.

## Shared resources we already use

Paths are relative to the repository root. Many shared components retain `watcher` or `heartbeat` in their names for compatibility.

| Responsibility | Existing resources | How the next companion uses them |
| --- | --- | --- |
| Identity, labels, settings adapter and mind creation | [companions.py](src/voidcompass/core/companions.py) | Extend identity validation, names, address handling, settings mappings, display mappings and the mind factory. |
| Commander profiles and defaults | [config.py](src/voidcompass/core/config.py) | Register every new setting in the appropriate `PROFILE_*` tuple and both existing default blocks. |
| Journal-driven thought engine and persistence | [watcher_mind.py](src/voidcompass/overlays/watcher_mind.py), [aster_mind.py](src/voidcompass/overlays/aster_mind.py) | Reuse event routing, vitals, providers and persistence; supply the new persona's own selection, wording and story hooks. |
| Context and attention | [watcher_idle.py](src/voidcompass/overlays/watcher_idle.py), [watcher_field.py](src/voidcompass/overlays/watcher_field.py), [heartbeat_events.py](src/voidcompass/overlays/heartbeat_events.py), [heartbeat-life.js](web/assets/heartbeat-life.js) | Use actual surroundings, discoveries, journal events and flight state. Translate their presentation into the new visual style. |
| Factual questions, app actions and market uplink | [watcher_copilot.py](src/voidcompass/overlays/watcher_copilot.py), [dashboard_watcher_voice_mixin.py](src/voidcompass/dashboard/dashboard_watcher_voice_mixin.py) | Keep the factual lookup/action providers and result handling; route acknowledgements through the new dialogue bank. |
| Editable commands, aliases, ship controls and sequences | [voice_commands.py](src/voidcompass/core/voice_commands.py), [watcher_ship.py](src/voidcompass/overlays/watcher_ship.py), [dashboard_ship_control_mixin.py](src/voidcompass/dashboard/dashboard_ship_control_mixin.py) | Share the existing catalogue, bindings, recorder and execution safeguards. Add the new address without bypassing user-edited phrases. |
| Preferred form of address and pronunciation | [watcher_name.py](src/voidcompass/overlays/watcher_name.py), [aster_name.py](src/voidcompass/overlays/aster_name.py) | Share name/pronunciation preferences; give each persona an original introduction and question flow. Keep choices and progress in its own memory. |
| Postcard writing and attribution | [watcher_postcards.py](src/voidcompass/overlays/watcher_postcards.py), [aster_postcards.py](src/voidcompass/overlays/aster_postcards.py), [dashboard_keepsakes_mixin.py](src/voidcompass/dashboard/dashboard_keepsakes_mixin.py), [postcards.py](src/voidcompass/overlays/postcards.py) | Reuse real context and rendering; supply the selected companion's note bank, tone, signature, saved rotation and non-consuming Studio preview. Persist author on each card. |
| Microphone and speech recognition | [listener.py](src/voidcompass/voice/listener.py), [listen_assets.py](src/voidcompass/voice/listen_assets.py), [microphone.py](src/voidcompass/voice/microphone.py), [dashboard_watcher_listen_mixin.py](src/voidcompass/dashboard/dashboard_watcher_listen_mixin.py) | Reuse the one active recognition service, microphone settings and Fast/Accuracy options. |
| Piper downloads and installation | [voice_assets.py](src/voidcompass/voice/voice_assets.py) | Add a verified model manifest, its own receipt and lifecycle handling while sharing the engine. |
| Speech queue, timing and live audio levels | [watcher_voice.py](src/voidcompass/voice/watcher_voice.py) | Use the existing `WatcherSpeaker` queue, pauses, job states, model signature and audio clock. |
| Native companion window and active caption | [heartbeat_hud.py](src/voidcompass/overlays/heartbeat_hud.py), [overlay_registry.py](src/voidcompass/core/overlay_registry.py), [web/heartbeat](web/heartbeat) | Keep one companion overlay, its existing placement/hotkey integration and active-identity payload. |
| Text presentation on both surfaces | [companion-caption.js](web/assets/companion-caption.js), [heartbeat/app.js](web/heartbeat/app.js), [dashboard/watcher.js](web/dashboard/watcher.js) | Use one presenter for natural typing and actual speech timing in the native overlay and deck NOW panel. |
| Three.js and motion controls | [heartbeat-orb.js](web/assets/heartbeat-orb.js), [aster-3d.js](web/assets/aster-3d.js), [aster-companion.js](web/assets/aster-companion.js), [frame-cap.js](web/assets/frame-cap.js), [vendored Three.js](web/galactic_map/vendor/three.module.min.js) | Reuse dependencies and the display-control contract; implement the new geometry and motion in its own renderer. |
| Deck identity, story, exports and Studio | [html_dashboard.py](src/voidcompass/dashboard/html_dashboard.py), [html_overlay_studio.py](src/voidcompass/dashboard/html_overlay_studio.py), [companion-ui.js](web/dashboard/companion-ui.js), [watcher.js](web/dashboard/watcher.js), [watcher.css](web/dashboard/watcher.css) | Extend labels, picker, panels, story adapter, book export and the common display inspector. |
| Theme and asset serving | [themes.py](src/voidcompass/core/themes.py), [html_dashboard_server.py](src/voidcompass/dashboard/html_dashboard_server.py), [html_overlay_server.py](src/voidcompass/overlays/html_overlay_server.py) | Follow theme accents and explicitly permit new shared browser assets and required module CORS. |
| Build and release documentation | [build.py](tools/build.py), [release_packager.py](tools/release_packager.py), [mini-readme.md](mini-readme.md), [ASTER_COMPANION.md](docs/ASTER_COMPANION.md) | Include production code/assets and user docs; keep voice downloads and their runtime receipts separate from the application archive. |

## What we completed for Aster

- [x] Created an original ship's officer: precise, restrained and dryly witty, with its own relationship to the commander.
- [x] Wrote **The Unfinished Manifest**: six chapters, 48 passages, ordered delivery, quiet-time pacing, event gates and time alternatives.
- [x] Added independent commander memory in `aster_memory.json`, service moments and story progress, with switching/reset/export support.
- [x] Kept shared questions, ship controls, maps, panels, app actions, sequences, aliases, microphone and command settings working.
- [x] Added 50 greetings and ten capability rundowns, plus all command outcomes, warnings, failed actions and event reports in Aster's voice.
- [x] Expanded to **163 event topics / 1,410 standard wordings**, **767 restrained wordings**, and **67 command outcomes / 289 acknowledgements**. These are a reference snapshot, not fixed requirements for every future character.
- [x] Fixed rotation boundaries, remembered command/chat cycles, migrated existing history and protected event/headline history from rolling-log loss.
- [x] Matched Watcher's idle pacing and willingness to stay quiet; retained necessary warnings and accurate requested reports.
- [x] Integrated the current matching Piper pair under `models/jarvis/onnx/`, pinned both hashes and sizes, and gave Aster its own receipt at `models/jarvis/installed.json`.
- [x] Fixed voice labels/download selection, checksum mismatch handling, replacement-model engine invalidation and safe sharing/removal of the Piper engine.
- [x] Updated deck/sidebar/Studio labels to follow the selected companion; kept behaviour, voice and appearance settings in their proper locations.
- [x] Gave Aster all Watcher Studio controls, immediate resizing, shared size across switches and visually matching diameter.
- [x] Built a unique transparent Three.js halo and matching officer panel with real idle, listening, working, speaking, charging and alert reactions.
- [x] Replaced its intermediate eye/dot designs with a **hollow hexagonal command core**, rotating arcs and scan traces. Aster's final design has no eyes, paired dots, pupil or central star.
- [x] Matched Watcher's text/speech presentation in **both** the floating overlay and NOW panel through the shared caption presenter.
- [x] Added Aster's original **The Crew Register** name-learning introduction, shared answer keys/panel, contextual typed/spoken replies, pronunciation, persistent choice and heard-passage reader/export.
- [x] Restored varied port company at the selected idle pace, including Rare; added dockside/carrier/concourse banks and startup station context from `Location`.
- [x] Audited idle triggers against Watcher: added factual habits, old postcards/service memories, heard-only lore recollections, queued commander facts, long-watch reminders and contextual call replies in Aster's theme. Watcher's dreams, shutter/eye story and mood arcs remain its own.
- [x] Routed automatic postcard writing to the selected companion, including Aster's own context-aware plain/dry notes, signature, persistent rotations, Studio author/preview, saved PNG/editor and text caption attribution.
- [x] Documented setup and operation, updated the 5.7.4 release notes and saved development memory.

The final reference is the code and [Aster companion guide](docs/ASTER_COMPANION.md). Older development notes and preview screenshots include superseded eye/dot designs.

## 1. Register identity and profile settings

- [ ] Add the stable ID and display name in `companions.py`; reject unknown IDs cleanly.
- [ ] Extend `create_mind`, `settings`, `key`, `Settings`, display helpers and `addressed` for the new identity.
- [ ] Define a distinct runtime memory filename in `heartbeat_hud._memory_path`.
- [ ] Add the actual settings needed for thought frequency, commentary mode, voice enabled/volume/speed/selection and display preferences.
- [ ] Register text, boolean and value settings in `PROFILE_TEXT_SETTINGS`, `PROFILE_BOOL_SETTINGS` and `PROFILE_VALUE_SETTINGS` as appropriate; update **both** config default blocks.
- [ ] Keep the existing shared microphone, command catalogue, bindings and sequences. Make the new spoken address optional and preserve editable greeting/capability aliases and disabled default phrases.
- [ ] Check saved config/profile reload, missing-key defaults and switching between at least two commanders.

Example file layout, using the chosen ID in place of `<id>`:

```text
src/voidcompass/overlays/<id>_mind.py
src/voidcompass/overlays/<id>_lines.py
src/voidcompass/overlays/<id>_responses.py  # optional expansion of authored banks
src/voidcompass/overlays/<id>_lore.py
src/voidcompass/overlays/<id>_name.py
web/assets/<id>-3d.js
web/assets/<id>-companion.js
models/<model-folder>/onnx/<model>.onnx
models/<model-folder>/onnx/<model>.onnx.json
docs/<ID>_COMPANION.md
tests/test_<id>_companion.py
tests/test_<id>_repeat.py
tests/test_<id>_name.py
tests/test_<id>_ui.py
```

Runtime `<id>_memory.json` belongs to the commander profile; installation receipts are runtime files beside the downloaded model. Neither is a replacement for development notes.

## 2. Implement the new mind and original story

- [ ] Use `AsterMind` as a guide to reusing `WatcherMind`'s event plumbing without inheriting Watcher-specific fiction accidentally.
- [ ] Give the mind its own `identity`, dialogue bank, headings, voice feel and spoken-word handling.
- [ ] Review inherited hooks deliberately: `_event_echo`, `_dream`, `_observe_deeper`, `remember`, `tick`, `poke`, `find_voice`, `voice_stage`, `story_marks`, `story_progress`, `pending_question`, `ask`, `meet`, `memories_page` and `_queue_session_extras`. Aster suppresses or replaces Watcher-only behaviour in these paths; a new character must make its own choices.
- [ ] Write original chapters and stable passage IDs. Record heard passages so restarts cannot retell the same story entry.
- [ ] Define settling time, quiet/lull requirements, minimum spacing, hours-together gates and relevant journal-event counters. Provide time alternatives where an event gate would exclude a play style.
- [ ] Keep story delivery out of immediate danger; count hours only while this companion is active.
- [ ] Supply a story-page adapter with heard passages, unopened titles, progress and next-gate information. Aster's `aster_lore.page` is the example.
- [ ] Extend dashboard story rendering, headings, memories and **SAVE BOOK** export. Export only revealed story content.
- [ ] Support reset with a backup of this companion's file and preserve every other companion's memory.
- [ ] Complete the commander-name checklist in section 2a, using an original introduction and the shared preferences/answer paths.

Aster's current pacing example is a ten-minute session settling period, two-minute lull and at least 45 minutes between passages; its first story threshold is about 15 minutes together. Choose the next character's pacing from its own story plan and verify the actual thresholds in its lore module.

## 2a. Learn the commander's name through original lore

**Aster reference: The Crew Register.** It notices the journal name, asks how the commander wishes to be addressed, then acknowledges the choice. This is a short personal introduction alongside its main story. Its wording belongs to the manifest officer's identity; the next companion needs its own reason to care about the name.

Use [aster_name.py](src/voidcompass/overlays/aster_name.py) for the original passages, response grammar, headings, reader payload and pronunciation mapping. Use `AsterMind._name_step`, `ask`, `answer`, `pending_question`, `talk`, `name_page` and `memories_page` in [aster_mind.py](src/voidcompass/overlays/aster_mind.py) for the integration. Shared preferences live in [watcher_name.py](src/voidcompass/overlays/watcher_name.py); existing answer labels/keys and timeout constants come from [watcher_questions.py](src/voidcompass/overlays/watcher_questions.py).

### Journal name, preference and permission

- [ ] Read the actual commander name from journal `LoadGame`/`Commander` events, preserving the commander's FID/profile identity. Wait for real data when the name is unknown.
- [ ] Reuse the selected companion's `memory.name` fields: `known`, `call` (`commander`, `name`, `nickname`), `nickname` and `spoken`. Keep the choice independent from other companions and commanders.
- [ ] Offer all three choices: use the journal name, keep **Commander**, or use a chosen nickname. Reading a name from the journal does not itself grant permission to use it as the preferred address.
- [ ] Honour an existing manual preference before starting the introduction. A manual choice made while its question is open must invalidate that old question.
- [ ] Keep **YOU → YOUR NAME** usable without waiting for the lore. Reuse `name_call`, `name_nickname`, `name_spoken` and `name_hear` actions, including **HEAR IT** with the active companion's voice.
- [ ] Apply the saved pronunciation to the chosen form of address, including a nickname. Keep the visible spelling in text while Piper speaks its pronunciation.

### Short story, pacing and memory

- [ ] Write three brief, original beats: **notice → ask → acknowledge**. Give them their own title and headings; do not reuse the Watcher's passages or reveal the main story's unopened chapters.
- [ ] Set explicit unlock, settling and spacing rules. Aster's example is about **15 minutes together**, at least **two minutes** of session settling and quiet, and at least **three minutes** between the first passage and question.
- [ ] Run the name step from the active mind's `tick`, with thought-frequency, activity and danger checks. Leave space for the short conversation while keeping direct commands and necessary warnings working.
- [ ] Save heard steps and text immediately. Aster uses `name.aster_arc.passages` with `notice`, `ask` and `first`; give another companion its own progress field.
- [ ] Store the question/choice in that companion's memory and restore a still-current pending question after restart. Expire stale questions without guessing the answer.
- [ ] Avoid nagging: Aster's pending question expires after **five minutes**, with at least **14 days** before another attempt if unanswered. Do not let `force=True` bypass the retry interval.
- [ ] After approval, reuse `may_name`/`mark_used` or the equivalent policy. Aster reserves the personal name for suitable moments, **at most once per session**, and keeps Commander for formal reports.
- [ ] Handle journal renames with the persona's own update wording. Cancel a question about the old name, preserve the user's preferred form of address and keep the completed introduction completed.
- [ ] Reset and back up only this companion's name progress. Include heard passages in its memories and **SAVE BOOK** export.

### Answers, deck, overlay and speech

- [ ] Return the existing pending-question shape: `id`, `text`, and ordered `{key, label}` answers. Aster reuses `your_name` with keys `yes`, `commander`, `other` and answer numbers 1–3.
- [ ] Route panel clicks and existing in-game answer hotkeys through `HeartbeatHUD.answer` to the active mind. Supply the pending question and hotkey labels in the dashboard's deeper payload.
- [ ] Check persona CSS as well as Python: Aster previously hid `#watcher-question` entirely. Show the question while asking and retain the correct hidden Watcher-only panels.
- [ ] Support contextual typed/recognised replies while asking, including affirmative answers, explicit refusals and a nickname. Aster accepts `yes`, `no thanks`, `keep it Commander`, and `Aster, call me Jeff`, including polite variants.
- [ ] After **Call me something else**, allow the commander to supply a nickname later through TALK/voice or YOUR NAME. Remember that waiting state across restart.
- [ ] Limit contextual name-response parsing to the naming conversation. Preserve unrelated commands, aliases and ordinary TALK behaviour.
- [ ] Send the introduction, question and acknowledgement through the established thought/speech queue and shared caption presenter on both surfaces.
- [ ] Show the correct persona headings in NOW/SAID, and provide a YOUR NAME reader containing only heard passages. Check narrow-screen answer buttons and the reader's saved spelling/pronunciation.

### Name-specific acceptance checks

- [ ] Test all choices, typed and recognised-speech replies, polite refusals, pronunciation, existing/manual preferences, unknown names, danger/activity/off guards and unrelated commands during the question.
- [ ] Test restart during each stage, answered/unanswered retry behaviour, repeated ticks, once-per-session name use, journal renames, commander/identity isolation, reset backups and book export.
- [ ] Test real browser visibility, button payloads, hotkey labels, 390px layout and heard-only passage rendering. Re-run Watcher's existing name tests to preserve its own arc.

References: [test_aster_name_574.py](tests/test_aster_name_574.py), the name-question/reader cases in [test_aster_ui.py](tests/test_aster_ui.py), and [test_watcher_name_571.py](tests/test_watcher_name_571.py). Aster's implementation passed the 109-check companion regression run; the final name/Watcher/UI recheck passed 26 checks. These are focused results, not a full-suite pass.

## 3. Cover dialogue and repeat behaviour from the start

- [ ] Write greetings and capability explanations in the new character's own voice. Aster's starting target was roughly 50 greetings and ten capability rundowns.
- [ ] Cover every outcome in both `watcher_ship.REPLIES` and `watcher_copilot.REPLIES`: successful actions, already-set states, disabled/unavailable controls, bad bindings, lost focus, sequence failures, cancellation, overlay actions, music and uplink results.
- [ ] Extend both modules' persona dispatch; they currently recognise Aster through `rng.companion_identity == 'aster'`. An unregistered persona must not fall through to Watcher dialogue.
- [ ] Cover the supported event topics: travel, surveys, first discoveries/maps/footfalls, biology samples, fuel/heat/combat, cargo/mining, missions/trade, vehicles, achievements, expeditions, calls and idle observations.
- [ ] Give recurring topics deeper banks. Keep ordinary remarks distinct across topics; use journal placeholders only when the required fields exist.
- [ ] Provide several plain variants for each restrained/commentary-off event. Changing tone must not reduce the whole character to one repeated sentence.
- [ ] Reuse/adapt Aster's persistent choice mechanism for command, greeting and capability cycles. Finish each set before reuse and prevent an immediate repeat at the cycle boundary.
- [ ] Keep event-template history separate from the rolling activity log. Remember templates by stable wording fingerprints and check recent rendered text for cross-topic duplicates.
- [ ] Preserve Watcher-style event selection: unused wording first over 30 days; after exhaustion, minor fixed remarks rest three days and formatted remarks one day; important reports may use older wording.
- [ ] Apply the overall idle interval as well as per-topic rests: Chatty five minutes, Occasional ten, Rare twenty; each idle topic at least 30 minutes apart.
- [ ] Compare the actual idle scheduler with Watcher's, not just the line-bank keys. Feed learned flight/survey/cargo/combat/trade/style habits into choices, and preserve their three-hour subject rest. Supply the new character's own wording for the shared factual fields.
- [ ] Audit passive writing outside `mind.tick` too. Automatic postcard notes must use the active companion's own bank, tone and signature. Keep the existing `watcher` mode token compatible while changing its visible author label; own words/None stay available. Stamp authorship on the card before background saving, retain old authors when switching, attribute caption text correctly, and test overlay/PNG/editor paths.
- [ ] Give postcard templates a per-companion/per-commander saved rotation. Use true screenshot context, omit unknown fields and avoid future lore spoilers. Studio previews need identity/tone/enablement in their cache key, must show the same author and must never advance live note history. Reference: [aster_postcards.py](src/voidcompass/overlays/aster_postcards.py), `DashboardKeepsakesMixin._postcard_companion_note`, and [test_aster_postcards_574.py](tests/test_aster_postcards_574.py).
- [ ] Connect real postcards, arrivals and saved service moments to quiet conversation. Gate their minimum age, topic rest and remembered per-item cooldown; changed wording must not retell the same memory repeatedly. Bound the cache and persist it across restarts. Aster's `aster_idle_recalled` holds up to 256 identities, each resting 30 days.
- [ ] Add the character's own passing lore and chapter lookbacks. Only recall chapters actually completed/heard, with no sealed names or future revelations. Keep the Watcher's dreams, shutter choices, eye lore and mood arc out of another identity unless deliberately rewritten as a new mechanic.
- [ ] Wire existing long-session and journal-career/power/squadron/carrier reply banks into the scheduler. Keep casual reminders within the global idle interval, honour Off/danger/voice filters, and offer contextual responses to a direct call. Test Rare underway as well as in port.
- [ ] Test a long docked session as well as exploration. Restore station/carrier context from a docked `Location`; also cover app startup/companion switching after historical events were skipped, using fresh live telemetry to establish the berth and wake the active mind. Stale saved state must not start a session. Provide enough port topics and wording for both modes, preserving the chosen pace, minor-remark rests and voice filter. See `aster_dockside.py`, Aster's `learn`/`tick`/`_idle_choices`, and the dashboard's `_watcher_context`.
- [ ] Keep Galnet's daily topic interval and 30-day remembered-headline interval; bound recent-text/headline caches. Aster's current caps are 512 rendered texts and 128 headlines.
- [ ] Apply idle/subject cooldowns to out-of-band timers too. The hatchling sends a notice every minute outside `mind.tick`; its idle/chatter reports must respect a shared half-hour subject rest and the overall idle interval. Forced trick notices still need ordinary pet-event pacing.
- [ ] Give real hatchling moments stable per-pet IDs and timestamps; remember delivered IDs, ignore stale moments and name the actual toy/trick/form. Include a pet-enabled long-session workload, repeated delivery and restart in the regressions.
- [ ] Migrate older conversation/event history when adding or changing rotation fields. Save and restore the new fields in this character's own memory.
- [ ] Format eligible command templates before choosing one; use the character's own fallback when fields are missing.
- [ ] Always return requested factual readings and necessary warnings. Repeated questions may require the same truthful answer; external relay text is shown as supplied.

Reference implementation: `OfficerRandom`, `AsterMind._variant`, `consider`, `_utter` and `tick`; banks in `aster_lines.py`, `aster_responses.py` and [aster_idle.py](src/voidcompass/overlays/aster_idle.py); regressions in `tests/test_aster_repeat_574.py` and [test_aster_idle_574.py](tests/test_aster_idle_574.py).

## 4. Add the Piper model and download lifecycle

### Downloaded candidates for future companions

Both voices were downloaded on **4 November 2026** from [dividebysandwich/piper-voice-models](https://github.com/dividebysandwich/piper-voice-models/tree/b9c5f3d1d7b6d0e0f5647ae31dbf13b13b0d3a6f), pinned to revision `b9c5f3d1d7b6d0e0f5647ae31dbf13b13b0d3a6f`. The creator identifies their training dialogue as coming from *Star Trek Generations* (the game).

| Candidate voice | Local model and matching configuration | Source notes and hashes |
| --- | --- | --- |
| Commander Data | `models/data/en_US-data_7024-medium.onnx` and `models/data/en_US-data_7024-medium.onnx.json` | [README](models/data/README.md), [SOURCE.json](models/data/SOURCE.json) |
| Captain Picard | `models/picard/en_US-picard_7399-medium.onnx` and `models/picard/en_US-picard_7399-medium.onnx.json` | [README](models/picard/README.md), [SOURCE.json](models/picard/SOURCE.json) |

- [x] Archived both complete pairs, each with a **63,516,050-byte ONNX model**, its matching JSON and the unchanged upstream README.
- [x] Verified upstream Git blob hashes and file sizes, recorded SHA-256 hashes and pinned download URLs, and checked both configurations: medium quality, `en_US` / eSpeak `en-us`, one speaker, **22,050 Hz**.

The [model index](models/README.md) lists these alongside the existing Watcher and Aster voices. They are stored for future evaluation; synthesis/listening checks and app integration still belong to the checklist below. The downloaded source revision supplies no licence file or usage terms; retain that source record when evaluating either candidate. A future companion still needs its own original identity, lore, dialogue, memory and display.

### Integration checklist

- [ ] Put the exact matching ONNX and JSON files in a dedicated model folder. Record source, attribution and the supplied terms in a README/model card and the download notice.
- [ ] Compute each file's SHA-256 and byte length from the actual current bytes. A replaced model or JSON needs updated metadata for **both** files.
- [ ] Publish that exact pair at the intended GitHub raw path, following the current `insert3coins/VoidCompass/master/models/...` layout.
- [ ] Extend `voice_assets.manifest`, model-path selection, `_receipt`, download sizes and `VoiceDownload.__init__` identity handling. Its current coercion only accepts Aster or Watcher.
- [ ] Extend `_engine_installed` and `remove` to consider **all registered companions**. Removal currently assumes one other voice; with three or more, preserve the shared engine/cache while any remaining installed voice needs them.
- [ ] Keep one shared Piper engine installation. Reuse the installation lock, temporary downloads, checksum verification, cancellation cleanup and independent receipts.
- [ ] Extend selected-model checks in `WatcherSpeaker._ensure_engine`; preserve the model signature containing identity, path and pinned hashes so a replacement model invalidates a warm engine.
- [ ] Extend dashboard install/remove/download/test-voice paths, active model labels, progress, notices and installed status. Check both `dashboard_watcher_voice_mixin.py` and `watcher_voice.py` for Aster-only branches.
- [ ] Verify a fresh download into a temporary base directory, local-pair adoption, cancellation, bad checksums and removal with two other voices installed. A source checkout alone does not prove the published download works.
- [ ] Synthesize a short sample with the production Piper engine and inspect the generated WAV. Play it only as part of an intended audio check.

Aster's current source pair is `models/jarvis/onnx/en_GB-jarvis-medium.onnx` and its `.onnx.json`. Its historical root-level exports are not the selected pair. Use `docs/ASTER_COMPANION.md` and the manifest for the current pinned values rather than copying old filenames or hashes into a new companion.

PowerShell example after replacing the placeholders with the real model path:

```powershell
Get-Item -LiteralPath 'models/<model-folder>/onnx/<model>.onnx' | Select-Object Name, Length
Get-FileHash -Algorithm SHA256 -LiteralPath 'models/<model-folder>/onnx/<model>.onnx'
Get-Item -LiteralPath 'models/<model-folder>/onnx/<model>.onnx.json' | Select-Object Name, Length
Get-FileHash -Algorithm SHA256 -LiteralPath 'models/<model-folder>/onnx/<model>.onnx.json'
```

## 5. Keep speech, captions and switching on the shared path

- [ ] Use `WatcherSpeaker.say`, `status` and `live` for queued/preparing/playing/finished/failed/cancelled states, actual audio timing and live levels.
- [ ] Preserve one-line-at-a-time playback, the playback tail and the between-line pause. A routine new line joins the queue rather than interrupting the current line.
- [ ] Keep queued/active spoken thoughts in `HeartbeatHUD` until their own playback and caption hold finish; normal thought expiry must not remove a long spoken reply.
- [ ] Use `CompanionCaption.createPresenter` from `web/assets/companion-caption.js` in **both** the native overlay and deck NOW panel. Supply the actual thought scope, speech state, elapsed time, duration and live sample time.
- [ ] Map the new text personality deliberately. The shared typing plan currently maps Aster's `officer` nature to Stoic; add an explicit mapping if introducing another label.
- [ ] Wait through queued speech and cold model loads. Retain punctuation pauses, marked journal words, monotonic text progress, bounded interpolation and written fallback on failed/cancelled audio.
- [ ] Keep reduced-motion behaviour and hidden-view timer parking. Opening a panel during speech must join the existing audio position.
- [ ] Reserve full caption layout in the NOW panel so controls remain still. Keep the spoken line ahead of newer queued log entries; SAID/TALK remain historical records.
- [ ] Extend `_companion_switch` and profile-change handling: save the outgoing mind, stop its speech/hearing, increment generation, clear captions, preserve providers and reject stale recognition/download/uplink responses.
- [ ] Preserve commander/identity scope in thought payloads and identity/generation checks in the fast live feed. Read every HTTP response body, including failures.

Keep the existing shared `watcher` page, `heartbeat_hud`/`heartbeat` overlay identifiers and compatible API routes. The active name and payload identify the selected character.

## 6. Build its own Three.js display and matching panel

- [ ] Define a visual identity from the new character's story. Reuse the rendering infrastructure while giving its geometry, motion and panel their own treatment.
- [ ] Implement the renderer and its adapter, following `createAsterDisplay` and `AsterCompanion.update/dispose`.
- [ ] Support the established controls: `setState`, `setContext`, `setColour`, `setActivity`, `setFocus`, `setMotion`, `setReducedMotion`, `setFrameRate`, `setVisible`, `setTilt`, `inspect` and `destroy`, or adapt them through one common interface.
- [ ] Wire real idle/listening/working/speaking/charging/alert states and actual speech energy. Give idle motion a visible but restrained character.
- [ ] Use journal/flight attention and the shared focus setting in a style that fits the design. Focus movement can rotate or orient an instrument; it does not require an eye.
- [ ] Keep background/corners transparent and theme accents responsive. Use amber or another established warning treatment only for real warning state.
- [ ] Match visible diameter to the Watcher at every Studio size. Aster uses an orthographic camera with calibrated bounds; equal canvas sizes alone were insufficient.
- [ ] Pin the visual square to the selected size, including no-caption states and a native window still tall from previous text.
- [ ] Honour idle-animation off, Calm/Standard/Lively intensity, focus off/tracking/expressive, frame caps, OS/app reduced motion and hidden renderer parking.
- [ ] Avoid replaying historical events as fresh reactions on each snapshot; dispose materials, geometry, listeners and frame loops on teardown.
- [ ] Integrate and load the adapter in `web/heartbeat/index.html` and `web/dashboard/index.html`; extend their JS renderer selection so only the active display runs.
- [ ] Add explicit server asset allowlisting and sandboxed-module CORS in `html_dashboard_server.py`; verify actual HTTP serving and browser startup.
- [ ] Give the NOW panel matching scoped styling, labels, live state, accessible descriptions and a character-appropriate call control. Check desktop and narrow layouts.

The optional [companion-preview](web/companion-preview) is useful for trying geometry and simulated states. The native overlay and real deck remain the acceptance targets.

## 7. Give it the complete shared settings experience

- [ ] Extend the picker and labels in `watcher.js`, `companion-ui.js`, the dashboard workspace payload and relevant HTML/CSS. Check sidebar, page title, overlay title, tooltips, status text, voice card, story and exports.
- [ ] Put identity, story, thought frequency/commentary and spoken-output setup on the companion page.
- [ ] Keep microphone/recognition, command names/aliases, bindings and sequences in **Settings → Voice**; shortcuts stay in **Settings → Hotkeys**. Retain TALK and its setup reminder.
- [ ] Put appearance in **Overlay Studio** using the existing single companion inspector.
- [ ] Offer every shared control: sizes 54/72/96/144/192/256; theme/cyan/brass/HAL accent; fixed/tracking/expressive focus; calm/standard/alive intensity; idle animation; frame rate.
- [ ] Extend `display_key`, `display_options`, Studio snapshot/save validation and the HUD model/apply-settings path. Save updates must redraw and synchronise the live native window.
- [ ] Extend the shared-size carry/save logic beyond `heartbeat_orb_size` and `aster_hud_size`. Size follows the user's selected size across switches; colour, focus and motion preferences remain independent per companion/profile.
- [ ] Retain shared placement, opacity, thought layout, text scale, map hiding and hotkey behaviour. Avoid duplicating these controls on another page.

## 8. Audit the places that still assume two identities

Tick these only after reviewing the whole relevant path, including its fallbacks:

- [ ] `core/companions.py`: validation, names, settings aliases, defaults, display keys/size, address parsing and factory.
- [ ] `overlays/heartbeat_hud.py`: memory path, mind settings refresh, model identity/accent/focus/nature and shared speech scope.
- [ ] `overlays/watcher_ship.py` and `watcher_copilot.py`: persona reply dispatch.
- [ ] `voice/voice_assets.py`: manifests, receipts, download coercion, engine reuse and removal of any one voice among several.
- [ ] `voice/watcher_voice.py`: installed-model checks and engine selection.
- [ ] `dashboard/dashboard_watcher_voice_mixin.py`: selection, size carry, preferences, download/remove/test labels and voice-found presentation.
- [ ] `dashboard/html_dashboard.py`: workspace identity/nature, thought headings, story, deeper memories and book export.
- [ ] `dashboard/html_overlay_studio.py`: settings snapshot, validation, saved-key mapping, toggles and all-companion sizing.
- [ ] `web/dashboard/companion-ui.js`, `watcher.js`, `watcher.css`, `index.html` and relevant `app.js` callers: picker, labels, panels, story, voice, Studio and module loading.
- [ ] `web/heartbeat/app.js`/`index.html`, the new display adapter and `companion-caption.js`: active renderer selection, labels, caption nature and readiness/rerender handling.
- [ ] `dashboard/html_dashboard_server.py`: shared-file serving and `_SANDBOXED_MODULES` entries.
- [ ] Relevant tests and fixtures: extend identity lists instead of accidentally replacing Watcher/Aster coverage.

Use targeted `rg` searches for the companion IDs and the functions above. Treat two-way `else Watcher` fallbacks as integration points. **Do not perform a global replacement of `aster`: the repository also contains unrelated asteroid data and names.** `web/dashboard/app.js` currently contains a pre-existing NUL, so use `rg -a` when searching that file and preserve its contents if editing it.

## 9. Verify the finished implementation

Complete implementation and docs first, then add meaningful regressions and run the checks appropriate to the changed paths.

| Area | Required evidence |
| --- | --- |
| Identity/profile isolation | All identities selectable; restart and commander switches preserve each one's settings, story and hours. |
| Upgrade/reset/export | Older memories load, repeat history migrates, reset backs up only the selected file, exports reveal only heard content. |
| Command compatibility | Editable names/aliases and disabled defaults still work; maps, panels, sequences, music, overlays and uplink use shared actions with the right voice. |
| Dialogue coverage | Every supported command outcome and event has valid, original wording, including restrained mode and failure replies. |
| Repetition | Several complete command/chat cycles, restart mid-cycle, rolling-log pressure, headline rest, cross-topic duplicates and long simulated sessions. |
| Port company | Long station/carrier/concourse watches in both commentary modes and all frequencies; startup after skipped history; fresh versus stale telemetry; no invented docking events, no port chatter in flight, and the selected voice filter. |
| Story | Ordered one-time passages, settling/spacing, time and event gates, no danger interruption, no inherited Watcher-only fiction. |
| Commander name | Original short introduction; explicit name/title/nickname choice; contextual replies and answer keys; pronunciation; once-per-session use; no restart/retry nagging; rename/reset/export and per-companion/profile isolation. |
| Voice installation | Fresh published download and local adoption; both hashes; cancellation/failure; replacement model; independent receipts; removal with other voices installed. |
| Voice switching | Switch while loading/speaking/listening/searching; late results cannot reach the new identity or commander. |
| Captions | Native overlay and NOW panel agree during cold loading, queue pauses, playback, late/missing samples, hidden/visible transitions and reduced motion. |
| Visuals | Actual WebGL motion at all intensities, live states, transparent pixels, matched diameter at all six sizes, tall caption windows, hidden GPU parking and clean teardown. |
| UI/Studio | Every shared control works immediately; active labels update; desktop and narrow panels stay readable and controls do not move while text appears. |
| Release | New code/assets and docs included; runtime models/receipts handled as intended; existing companions pass regression checks. |

Useful existing suites to extend:

- `tests/test_aster_companion.py` — identity, story, profile integration, voice assets and caption retention.
- `tests/test_aster_repeat_574.py` — all outcome/event banks, cycles, persistence, pacing and the Watcher's simulated exploration workload.
- `tests/test_aster_hatchling_574.py` — pet-enabled four-hour sessions, the real minute timer, forced notices, moment replays, restart and subject cooldowns.
- `tests/test_aster_dockside_574.py` — long station/carrier/concourse watches, docked/live-state startup, Rare eligibility, minor-wording exhaustion and voice-level filters.
- `tests/test_aster_idle_574.py` — factual habit triggers, heard-only lore, aged postcards/service memories, persisted per-memory rests, queued career facts, contextual calls and sixteen-hour quiet watches.
- `tests/test_aster_postcards_574.py` — selected author/tone, saved note cycles, preview isolation, switching during background save, PNG/editor/caption attribution and real-browser author controls/overlay cards.
- `tests/test_aster_name_574.py` — the original name introduction, choices, typed/spoken replies, quiet pacing, restart, manual preferences, rename, reset and book export; the name question/reader browser cases live in `test_aster_ui.py`.
- `tests/test_aster_ui.py` — real browser/server, shared Studio behaviour and transparent animated renderer.
- `tests/test_companion_captions_574.py` — both identities and both surfaces following one audio clock.
- `tests/test_watcher_speech_queue_573.py`, `tests/test_voice_speed_573.py` — queue/state and voice playback behaviour.
- `tests/test_watcher_talk_573.py`, `tests/test_watcher_uplink_573.py`, `tests/test_watcher_answers_572.py`, `tests/test_watcher_field_572.py` — shared interaction paths.
- `tests/test_heartbeat_orb.py`, `tests/test_watcher_three_568.py`, `tests/test_dashboard_bridge_pages_visuals.py` — Watcher/rendering/Studio compatibility.

Example focused baseline, run from the repository root; add the new companion's suites:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_aster_companion tests.test_aster_repeat_574 tests.test_aster_idle_574 tests.test_aster_dockside_574 tests.test_aster_hatchling_574 tests.test_aster_name_574 tests.test_aster_ui tests.test_companion_captions_574 tests.test_watcher_speech_queue_573 tests.test_voice_speed_573 tests.test_heartbeat_orb tests.test_watcher_three_568
```

Full-suite command when required for the completed release/change:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

Record the actual command, results and remaining failures. Aster's idle-trigger audit passed **164 focused tests**, including eight simulated sixteen-hour watches in port/space, on Occasional/Rare and in both commentary modes, with no repeated lines and the selected idle spacing. The earlier dialogue follow-up passed 180 focused tests, including six four-hour exploration watches. These are not full-suite passes. Earlier broad verification recorded unresolved native WebView startup/delivery failures in `test_composition_host_55341.py` and `test_overlay_delivery_568.py`. Recheck relevant native behaviour when working on window delivery; do not weaken those tests or assume browser-only checks prove native startup.

## 10. Document and finish

- [ ] Add `docs/<ID>_COMPANION.md` with identity, setup, typed/spoken examples, settings locations, lore pacing, memory/reset/switching, display controls and exact current model details.
- [ ] Add a release-note entry under the version selected by the user. Preserve **Earlier releases** structure; do not choose a new version automatically.
- [ ] Verify `tools/build.py` and `tools/release_packager.py` still include `docs/`, and new source imports/browser assets reach the release. This root checklist is a development reference; copying it to root does not automatically put it in packaged `docs/`.
- [ ] Record implementation decisions, test results and known limitations in development memory. Current Aster notes live at `C:/Users/Jeff/.claude/projects/d--Programming-Elite-SurveyAnalysis/memory/project_aster_574.md`; keep this root guide useful without requiring that machine-specific path.
- [ ] Review the changed files, preserve unrelated/staged work and ensure new source, tests and docs are included in the eventual release commit.
- [ ] Complete a manual pass on the actual native overlay and deck, with voice on and off, switching through every installed companion.

## Ready to call the companion complete

- [ ] Its identity and lore stand on their own.
- [ ] It has Watcher-level functional and settings coverage.
- [ ] Its dialogue remains varied and can leave room for silence.
- [ ] Its memory, model and preferences stay with the correct commander/identity.
- [ ] It learns the commander's preferred name through its own introduction, respects the choice and pronunciation, and remembers without nagging.
- [ ] Its voice and text share the established queue and timing on both surfaces.
- [ ] Its display is distinctive, animated, correctly sized and controlled by Studio.
- [ ] Its installation, switching, documentation and regression checks are complete.
