# Adding another heartbeat companion

Reusable implementation checklist, based on **The Watcher → Aster in v5.7.4**. Last reviewed: **5 November 2026**.

Use this when adding a fresh companion with its own character, lore, dialogue, memory, Piper voice and animated display. The goal is the same working capabilities and settings as the Watcher, expressed through the new companion's identity.

The checked items below record work completed for Aster. The unchecked items form a fresh checklist for the next companion. This document does not register or create another companion by itself.

## Start here

1. Complete the identity brief below.
2. Read the shared-resource map and the Aster completion record.
3. Work through the numbered implementation checklist in order.
4. Finish implementation and documentation before writing/running the regression tests for the change.
5. Verify every companion, both display surfaces and switching between them before release.

**Current integration:** the identity registry, profile settings, voice lifecycle, memory paths, companion page, Studio, boot screen and Local API support Watcher, Aster, Axiom and Meridian. Aster, Axiom and Meridian share one persona mind ([companion_personas.py](src/voidcompass/overlays/companion_personas.py)) and the story engine. A new officer-style companion mostly needs a new persona entry and its writing; still audit the dispatch points below.

## Current batch — full stories for Aster, Axiom and Meridian (5 November 2026)

User-approved direction: **Aster** gets a complete story rewrite (new chapters and unlock rules). **Axiom** becomes a survey intelligence: precise, curious and literal, still learning people. Its story is *The Uncounted Star*. **Meridian** becomes a veteran navigator from an old charting fleet: measured, literate and steady. Its story is *The Last Sounding*. All three use one shared persona mind, so they get Watcher-level features in their own words. Tests run only after every task in the batch is built.

**Shared foundations**
- [x] Story engine [companion_story.py](src/voidcompass/overlays/companion_story.py): ordered passages, hours-together thresholds, journal-signal chapter gates with time alternatives, real-day spacing, echoes stirred by real events (only after the related chapter), chapter recollections, musings, after-story lines, page/heading/book payload with unlock hints.
- [x] Shared name arc [companion_name.py](src/voidcompass/overlays/companion_name.py), quiet-watch chooser [companion_idle.py](src/voidcompass/overlays/companion_idle.py), postcard writer [companion_postcards.py](src/voidcompass/overlays/companion_postcards.py), line-bank composer [persona_lines.py](src/voidcompass/overlays/persona_lines.py). Aster's modules delegate to them with unchanged APIs.
- [x] Persona registry and `AsterMind` refactor: lines/lore/name/idle/dock/postcards/commentary key come from the active persona; `CrewMind` becomes a full persona mind (no stubs). Registry: [companion_personas.py](src/voidcompass/overlays/companion_personas.py). Journal signals count towards gates in `aster_marks`; echoes reuse the shared `_event_echo` hook.
- [x] Dispatch: ship/copilot replies, postcard author, dashboard story/headings/book export, voice test line, commentary setting (`<id>_humour`) for every persona.
- [x] Deck story renderer for all three personas: chapter index with unlock hints, reader, next-gate note, echoes and complete-book reader.

**Aster**
- [x] New story *Relieved of the Watch*: 8 chapters, 48 passages. Each chapter is a captain's entry in Aster's handover book, opened by matching play (deliveries, survey findings, a close call, patient work, brushes with trouble, returns, 150 jumps) or by more time together. Later chapters also wait real days.
- [x] Six story echoes, seven musings, eight after-story lines and two recollections per chapter. Removed the old *Unfinished Manifest* recollections.
- [x] Deck copy, docs and migration note (old heard passages are retired; the new book starts from chapter I). Tests follow in the test step below.

**Axiom** — *The Uncounted Star*
- [x] Character: the cataloguing mind of the Lattice, a twelve-station survey array. Precise, literal and earnest; explains its jokes; learning to say "I do not know". Story [axiom_lore.py](src/voidcompass/overlays/axiom_lore.py): 8 chapters / 48 passages. Every recount found one extra light; it turns out to be the keeper Dr Moreau's tender, and finally the commander's own ship. Gates: detailed scans, dockings, first discoveries, long jumps, remarkable stars or complete systems, returns, then 200 jumps and scans. Six echoes, seven musings, eight after-story lines.
- [x] Name introduction *The Observer Field* ([axiom_name.py](src/voidcompass/overlays/axiom_name.py)); 30 greetings, 10 restrained greetings, 6 capability rundowns, every command outcome ([axiom_lines.py](src/voidcompass/overlays/axiom_lines.py)); every event, dockside, idle, habit, hatchling and sign-off topic in both modes ([axiom_events.py](src/voidcompass/overlays/axiom_events.py), [axiom_watch.py](src/voidcompass/overlays/axiom_watch.py)); postcard notes signed Axiom ([axiom_postcards.py](src/voidcompass/overlays/axiom_postcards.py)). Snapshot: 169 topics / 1,021 standard / 484 restrained wordings; 67 command outcomes / 156 acknowledgements.

**Meridian** — *The Last Sounding*
- [x] Character: the navigation mind of the survey ship *Leadline*, one of seven ships in an old expedition sounding the dark between two galactic arms along one line. Measured, literate and nautical; it advises and never commands. Story [meridian_lore.py](src/voidcompass/overlays/meridian_lore.py): 8 chapters / 48 passages. The fleet turns back four hundred light years short; the log's "last sounding" line stays blank until Meridian fills it with the commander. Gates: 25 jumps, survey observations, long jumps or scoops, 10,000 ly from Sol, selling data, homecomings, then 250 jumps. Six echoes, seven musings, eight after-story lines.
- [x] Name introduction *The Ship's Articles* ([meridian_name.py](src/voidcompass/overlays/meridian_name.py)); 30 greetings, 10 restrained greetings, 6 capability rundowns, every command outcome ([meridian_lines.py](src/voidcompass/overlays/meridian_lines.py)); every event, dockside, idle, habit, hatchling and sign-off topic in both modes ([meridian_events.py](src/voidcompass/overlays/meridian_events.py), [meridian_watch.py](src/voidcompass/overlays/meridian_watch.py)); postcard notes signed Meridian ([meridian_postcards.py](src/voidcompass/overlays/meridian_postcards.py)). Snapshot: 169 topics / 1,013 standard / 484 restrained wordings; 67 outcomes / 156 acknowledgements.
- [x] Spoiler check: name introductions, postcards and ordinary banks never name story characters; echoes and recollections only after their chapter.

**Companion page redesign (5 November 2026, user request)**
- [x] Rewrote the 5.7.4 patch notes as one grouped list: companions, stories, overlay displays, Studio, captions, voices, boot, FOLLOW ME, API, fixes.
- [x] A compact switcher in A–Z order (Aster, Axiom, Meridian, The Watcher) replaces the large picker. The sidebar keeps the active companion's name (user choice).
- [x] Tabs are now BRIDGE · STORY · YOU · LOG · SETUP. BRIDGE puts the display beside the conversation, with story, bond, wish and recent thoughts at the side. SETUP combines thoughts, voice and reset. Old stored tabs (talk, voice, mind, library) land in the right place. The chat names the active companion (it used to say "THE WATCHER" for everyone). The question card shows only while asking. Chat chips and the switcher opt out of the deck's bracket button style.
- [x] Tests: [test_companion_page_574.py](tests/test_companion_page_574.py); updated tab/talk expectations in the talk, Aster/crew UI, voice and deeper suites.

**Other pending items in this guide**
- [x] Boot screen presents the selected companion: the boot payload carries the saved identity and display preferences (`HtmlDashboardRuntime._boot_companion`, from the startup config); `boot-scene.js` feeds the existing Aster/crew adapters on the boot canvas and parks the Watcher orb when another companion is selected. Shared progress, countdown and deferred speech are unchanged.
- [x] Companion API, strategy chosen: **one shared companion contract**. `GET /companion`, `GET /companions`, `GET /companions/{id}` (inactive companions read from their own memory, never woken or voiced), `POST /companion/select` and `POST /companion/thought|poke|answer|book`. The `/watcher/*` routes are kept as aliases for the active companion. Each answer carries `companion` (identity, name, generation) and `capabilities`; an optional `"identity"` guard returns `409` after a switch, and unknown IDs return `404`. Watcher-only `code`/`meet` return `409` for the others. `thought` and `voice` events name the companion. Documented in [api.md](api.md) (the in-app docs page renders it).
- [x] Galaxy map (deck Atlas): **FOLLOW ME** button beside the zoom controls. Hovering shows a short description. It keeps YOU ARE HERE centred at the current zoom on every arrival, is saved with the map view (`follow`), turns off when you pan the map (rotating keeps it on), and pauses during replays.
- [x] Docs: [AXIOM_COMPANION.md](docs/AXIOM_COMPANION.md), [MERIDIAN_COMPANION.md](docs/MERIDIAN_COMPANION.md), Aster story/unlock table and migration note in [ASTER_COMPANION.md](docs/ASTER_COMPANION.md), [CREW_COMPANIONS.md](docs/CREW_COMPANIONS.md), mini-readme (5.7.4) and [api.md](api.md#companions).
- [x] Tests: updated suites that assumed the old story and preview stubs. Added [test_companion_stories_574.py](tests/test_companion_stories_574.py) (engine, gates, days, signals, both-mode coverage, field validity, spoiler/crossover checks, echoes, commentary, API guard/routes, boot payload), [test_boot_companion_574.py](tests/test_boot_companion_574.py) and [test_galaxy_follow_574.py](tests/test_galaxy_follow_574.py) (real browser). Fixed five stale expectations that already failed at HEAD from earlier commits, plus a real bug: invalid saved liveliness/focus now fall back in `companions.display_options`. **Full suite: 2,677 tests, 1 failure.** `test_watcher_refined_557…test_the_iris_deepens_toward_its_edge` is a load-sensitive pixel threshold (0.296 vs 0.34); it passes alone and at HEAD, and the Watcher renderer was not changed.
- [ ] Manual: audition Axiom/Meridian voices and story passages in game; check the boot screen and FOLLOW ME in the real app.

**Audit follow-ups (5 November 2026): Watcher-only features now covered for Aster, Axiom and Meridian**
- [x] **Keepsake moments.** `capsule`, `capsule_early`, `capsule_shared`, `constellation_named`, `on_this_day` and `anniversary_us` in both modes, in `<id>_keepsakes.py` ([aster](src/voidcompass/overlays/aster_keepsakes.py), [axiom](src/voidcompass/overlays/axiom_keepsakes.py), [meridian](src/voidcompass/overlays/meridian_keepsakes.py)). They use the Watcher's headings; an anniversary is queued at session start.
- [x] **Captain's Log paragraph.** Live sessions record the companion on watch in the Captain's Log (`_stamp_session_companion`; a switch hands the session to the new one). `flight_log.companion_words` builds each persona's paragraph, and `flightlog.js` cites `companion_name`. Older or replayed sessions stay the Watcher's.
- [x] **Companion page facts:** ROLE shows each companion's own role.
- [x] **Copy:** SETUP notes, voice text, Settings › Voice, the hotkey group/labels ("Companion: …"), capsule/constellation/expedition options, setting details and the listen feed message no longer assume the Watcher or its orb. Lore text such as the hatchling's "Found by the Watcher" is unchanged.
- [x] **Readings of you:** persona `_observe_deeper` shifts trust/mood like the Watcher, with each persona's own labels (`FEELING`). The deck's third reading cell shows the story chapter instead of the Watcher's road.
- [x] **After-watch notes** replace dreams: written at Shutdown (`_dream`), told next session ("dream_told"), shown under each persona's title and exported in the book.
- [x] **Share codes and meeting:** codes carry `companion`; any companion meets any other. The Watcher has wording for meeting the others; API capabilities include `share_code`/`meet` for all.
- [x] **A request** (`WISH`): Aster, the system where it came aboard (after VII); Axiom, a black hole (after VI); Meridian, the edge of the galaxy (after VI). It reuses `pilgrimage` memory, so expeditions can make it an objective. Arrival is noticed and moves its readings.
- [x] **Achievements:** 12 entries in [achievements.json](data/achievements.json) (`<Name>Told/Complete/Echoes/Request` on the shared story event, from `AsterMind.story_progress`).
- [x] Tests: [test_companion_keepsakes_574.py](tests/test_companion_keepsakes_574.py) (every moment kind in both modes with headings, anniversary queue, notes written/told/exported, readings and labels, the request before/after its chapter and on arrival, cross-companion codes including the Watcher meeting an Aster, achievement fields, per-companion Captain's Log paragraph and session stamping, copy). Browser checks for ROLE, readings, request state, notes title and share card in [test_companion_page_574.py](tests/test_companion_page_574.py). Updated the expectations these features changed.

**The crew lore (5 November 2026, user request)**
- [x] Shared backstory in [crew_lore.py](src/voidcompass/overlays/crew_lore.py). The Watcher was aboard first; the others came aboard as second-hand cores. They met on the data bus while the commander was logged off, and Aster's watch rota explains why one is on watch at a time.
- [x] *Coming Aboard*: 6 passages for each of the 4 companions (24). Each starts after 2 h together with at least 2 companions flown (15 min each). A crewmate passage waits for that crewmate; passages are an hour apart, share the main story's pacing, and fill gaps when the next story passage is gated. Told through `WatcherMind._crew_passage` (both minds), recorded in `crew_lore`/`crew_lore_words` with headings "THE CREW · <TITLE> · n OF 6".
- [x] Handovers: switching companion calls `note("crew_handover")`, and the incoming companion says `handover_from_<previous>` under the heading CHANGE OF WATCH. Each pair has its own lines plus 10 general ones naming whoever it relieves (20 per pair for the Watcher, 15 for the others), dealt from a saved rotation per crewmate (`crew_handovers` in its memory): every line once before any repeats, never the same line twice in a row, survives restarts.
- [x] Crewmate remarks (`idle_crew_<other>`) join quiet-moment chat for all four, once that crewmate's passage is told.
- [x] Deck: `MainDashboard._crew_snapshot` reads every companion's memory (live for the active one, files every 30 s for the others). It feeds `context["crew"]["flown"]`, the STORY tab's **THE CREW** section (`_html_crew_page`) and the crew achievements (*Introductions*, *Full Crew*, *The Watch Rota*, via `CrewFlown`/`CrewTold` on the story event). The book export includes the active companion's account.
- [x] Tests: [test_crew_lore_574.py](tests/test_crew_lore_574.py) (content and spoiler check, banks for every pair in all four minds, pacing and crewmate gates, story-first ordering, remarks, handovers for every pair and on deck switches, snapshot and achievement totals, crew page) and a browser check of the STORY crew section in [test_companion_page_574.py](tests/test_companion_page_574.py). The Watcher's crew and meeting topics carry 10 lines each, matching its deep-bank rule.

- [x] The Watcher looked frozen next to the crew with idle animation on (6 November): weary nature, docked stance and drowsiness together left only rare tiny glances. Idle now adds a slow drift (`life.wander`), a look around every 12–26 s (weary looks down and away), glances 0.055 instead of 0.045, and weary spin 0.7 instead of 0.55. Still when idle animation is off, asleep or when the feed goes quiet. Test: `test_idle_it_never_quite_holds_still`.

- [x] The new companions were quiet while jumping and exploring (6 November). Cause: new companions start on Occasional (the user's Watcher is on Chatty), which never mentions a plain arrival or scoop, and Axiom/Meridian had a third of the Watcher's exploration lines. Fix: per-role `INTERESTS` raise a topic's importance for speaking up only (once an everyday topic's lines are used it still goes quiet, so no repeats), [axiom_survey.py](src/voidcompass/overlays/axiom_survey.py) and [meridian_soundings.py](src/voidcompass/overlays/meridian_soundings.py) add lines, `persona_lines.merge` adds banks together. Test: [test_companion_interests_574.py](tests/test_companion_interests_574.py).

- [x] The crew off watch (6 November): [crew_voices.py](src/voidcompass/overlays/crew_voices.py). Ask a crewmate by name in TALK (`addressed`, `CrewRandom` words replies from the crewmate's own lines without touching the active one's rotations, history row `who`, deck chat shows `NAME · OFF WATCH`); off-watch remarks at big moments (`MOMENTS`, close call 45 s after hull_critical with no death; once a session, an hour apart, 50%, flown-with crewmates only; 5 lines per crewmate per moment, rotated); speech in the crewmate's own voice via `feel.voice` (speaker swaps model per line; no voice or voice off means written only); a companion's first watch starts at `heartbeat_thoughts` (`_companion_first_pace`, only when it has no memory file). Test: [test_crew_off_watch_574.py](tests/test_crew_off_watch_574.py).

## Axiom and Meridian — v5.7.4 preview

User-approved original names: **Axiom** (the Data-source Piper voice) and **Meridian** (the Picard-source Piper voice). Start with voice, display and a few welcome messages; defer lore and stories. Setup and examples: [docs/CREW_COMPANIONS.md](docs/CREW_COMPANIONS.md).

- [x] Register both identities and profile-owned settings in both default blocks.
- [x] Give each an independent commander memory, active page title, picker, voice page and pending-story page.
- [x] Register exact model pairs, hashes, GitHub download paths and separate receipts under `models/data/` and `models/picard/`; keep one shared Piper engine until the last installed voice is removed.
- [x] Add six testable welcome messages per companion, two practical capability replies and an identity-specific voice-test sentence. Reuse saved greeting rotation, login deduplication, factual providers and command catalogue.
- [x] Build transparent procedural Three.js displays for both surfaces: Axiom violet/cyan particle torus inspired by `Downloads/ring-glowing-points-black/1374.jpg`; Meridian gold/blue anonymous wireframe portrait inspired by `Downloads/picard overlay.png`.
- [x] Support speech/listening/working/alert reactions, idle animation, attention movement, shared Studio sizes, accent, focus, liveliness, frame rate and reduced motion. Preserve the shared caption/audio clock and speech queue.
- [x] Make idle motion visible: Axiom particle currents, breathing and opposing light trails; Meridian counter-rotating rings, a moving scan band and portrait drift. Publish Studio changes to the browser model immediately along with window dimensions; verify actual rendered changes as well as saved settings. Idle Off still wakes for new activity.
- [x] Check real Studio clicks for both previews, rendered idle motion at 54/96 px, colour changes while parked and Theme accent independent of panel decoration. Regression coverage: [test_crew_motion_studio_574.py](tests/test_crew_motion_studio_574.py).
- [x] Give each companion a real signature palette in Studio: **Aster cyan/violet**, **Axiom violet/cyan**, **Meridian gold/blue**; the Watcher retains **HAL red**. Share labels and both light colours through [companion-colours.js](web/assets/companion-colours.js). Save `signature` per companion, interpret the earlier non-Watcher `hal` choice as its signature, and preserve explicit theme/cyan/brass choices. Apply the palette to the renderers, bezel, deck panel and Eye colour captions.
- [x] Verify signature choices, legacy saves, real rendered colour changes, deck styling and caption ink in [test_companion_colours_574.py](tests/test_companion_colours_574.py). 83 focused companion/Studio/rendering/caption tests passed for this change; the full suite was not run.
- [x] Give Aster, Axiom and Meridian the Watcher’s readable instrument treatment: shared bezel, dark translucent recess and stronger foreground detail. Keep each design and its motion, transparent outer corners and space between Aster/Axiom geometry. Shared renderer resource: [companion-frame.js](web/assets/companion-frame.js).
- [x] Fill Axiom’s centre with a floating violet/cyan lattice crystal and Aster’s command interface with a smaller cyan/violet hexagonal prism. Share reactive geometry in [companion-core.js](web/assets/companion-core.js): idle rotation/breathing, incoming listening light, working pulses, audio-level speech expansion and warning colours. Reuse existing clocks, frame caps, motion preferences, palettes and both display surfaces.
- [x] Keep Meridian’s portrait and give it visible upper/lower lip movement and a dark mouth opening driven by actual speech amplitude, with quick opening and a smooth close through pauses. Do not animate for queued text or microphone input; close when speech ends and keep still under Reduced motion. Preserve mouth movement during alert speech. Phoneme-based lip sync remains outside this implementation.
- [x] Cover both lattice variants at 54/96 px, state reactions and speech expansion, transparent gaps, both deck variants, and Meridian’s audio/pauses/end/queued/microphone/alert/reduced-motion behaviour in [test_companion_centres_574.py](tests/test_companion_centres_574.py).
- [x] Visually review both deck and floating presentations, then run the focused centre/palette/contrast/Studio/animation/caption regressions: **45 tests passed**. No full suite run.
- [x] Verify bright/dark contrast at 54/96 px, selected rim colours, transparent lattice gaps/corners and the same visible size as Watcher. Preserve animation, captions and Studio controls. Coverage: [test_companion_readability_574.py](tests/test_companion_readability_574.py).
- [x] Keep name preferences and pronunciation editable without introducing either existing persona’s name story. Include the active name in recognition hints.
- [x] Keep source filenames, archive provenance and upstream notes unchanged. No source artwork or actor likeness is bundled.
- [x] Write each companion’s original character brief, lore, chapters, story gates and ending (see the current batch above).
- [x] Write an original commander-name introduction and question flow for each companion: *The Observer Field* (Axiom), *The Ship's Articles* (Meridian).
- [x] Expand individual responses: event/advisory banks, dockside/idle company, hatchling reactions, greetings, capability replies and shutdown variants. Use the saved non-repetition/pacing rules below.
- [x] Add original postcard writing/signatures and service/story recollections.
- [x] Verify real Piper installation and synthesis in an isolated temporary folder: Axiom test line 5.88 seconds, Meridian 4.48 seconds, both mono 22,050 Hz. The shared engine archive passes its pinned checksum. Public GitHub JSON pairs match local hashes; both public ONNX URLs return the expected 63,516,050-byte size.
- [x] Pass 94 focused regressions, including all four voice lifecycles, model hashes, welcome rotation, real dashboard module delivery, both new displays, Studio controls, caption timing, existing Aster/Watcher behaviour and postcards. Visually inspect both deck displays and transparent overlay captures. See `tests/test_crew_companions_574.py` and `tests/test_crew_ui_574.py`.
- [ ] Audition the voices in game and adjust speed/volume as desired. Full remote ONNX content was not re-downloaded during these checks; local exact model hashes were verified.

The shared engine is retained by all four registered voices; install/remove tests must cover mixed combinations, not just the original pair. Welcome-only companions deliberately leave fiction hooks empty until their own writing is ready.

**Boot screen (done 5 November 2026):** startup presents the selected companion with its own display. A future companion needs its adapter called from `boot-scene.js` `feedCompanion`.

**Companion API (done 5 November 2026):** one shared contract (`/companion`, `/companions/{id}`) with `/watcher/*` kept as aliases for the active companion. See the [API checklist](#companion-api-work--pending) below and [api.md](api.md#companions).

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
| When it may use a personal name and its formal address | To decide; Aster uses the approved name/nickname as its regular address, while Watcher retains its own once-per-session policy |
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
| Officer-style persona plumbing (5.7.4) | [companion_personas.py](src/voidcompass/overlays/companion_personas.py), [companion_story.py](src/voidcompass/overlays/companion_story.py), [companion_name.py](src/voidcompass/overlays/companion_name.py), [companion_idle.py](src/voidcompass/overlays/companion_idle.py), [companion_postcards.py](src/voidcompass/overlays/companion_postcards.py), [persona_lines.py](src/voidcompass/overlays/persona_lines.py), [crew_mind.py](src/voidcompass/overlays/crew_mind.py) | Register a persona (lines, lore, name arc, postcards, commentary labels, headings, test line), write `<id>_lore/_name/_lines/_events/_watch/_postcards.py`, and `CrewMind` gives it every AsterMind feature. `persona_lines.missing` lists unwritten topics. |
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
| Three.js and motion controls | [heartbeat-orb.js](web/assets/heartbeat-orb.js), [aster-3d.js](web/assets/aster-3d.js), [aster-companion.js](web/assets/aster-companion.js), [crew-3d.js](web/assets/crew-3d.js), [companion-core.js](web/assets/companion-core.js), [companion-frame.js](web/assets/companion-frame.js), [frame-cap.js](web/assets/frame-cap.js), [vendored Three.js](web/galactic_map/vendor/three.module.min.js) | Reuse dependencies and the display-control contract; use shared reactive cores where appropriate and keep mouth movement tied to actual audio, including during alerts. Implement a new companion’s own geometry without adding another animation loop. |
| Deck identity, story, exports and Studio | [html_dashboard.py](src/voidcompass/dashboard/html_dashboard.py), [html_overlay_studio.py](src/voidcompass/dashboard/html_overlay_studio.py), [companion-ui.js](web/dashboard/companion-ui.js), [watcher.js](web/dashboard/watcher.js), [watcher.css](web/dashboard/watcher.css) | Extend labels, picker, panels, story adapter, book export and the common display inspector. |
| Theme and asset serving | [themes.py](src/voidcompass/core/themes.py), [html_dashboard_server.py](src/voidcompass/dashboard/html_dashboard_server.py), [html_overlay_server.py](src/voidcompass/overlays/html_overlay_server.py) | Follow theme accents and explicitly permit new shared browser assets and required module CORS. |
| Local API, routes and event stream | [local_api.py](src/voidcompass/services/local_api.py), [dashboard_api_mixin.py](src/voidcompass/dashboard/dashboard_api_mixin.py), [dashboard_api_records_mixin.py](src/voidcompass/dashboard/dashboard_api_records_mixin.py), [api.md](api.md) | Audit the existing Watcher/voice API for every identity; choose and document the shared/per-companion route strategy, retain compatibility and identify the companion in responses/events. |
| Companion colour presets | [companion-colours.js](web/assets/companion-colours.js), [companions.py](src/voidcompass/core/companions.py) | Add an original named primary/highlight palette, use `signature` as its default, and share it across Studio, both displays and captions. Preserve explicit theme choices and existing Watcher colours. |
| Build and release documentation | [build.py](tools/build.py), [release_packager.py](tools/release_packager.py), [mini-readme.md](mini-readme.md), [ASTER_COMPANION.md](docs/ASTER_COMPANION.md) | Include production code/assets and user docs; keep voice downloads and their runtime receipts separate from the application archive. |

## What we completed for Aster

- [x] Created an original ship's officer: precise, restrained and dryly witty, with its own relationship to the commander.
- [x] Wrote **The Unfinished Manifest**: six chapters, 48 passages, ordered delivery, quiet-time pacing, event gates and time alternatives.
- [x] Added independent commander memory in `aster_memory.json`, service moments and story progress, with switching/reset/export support.
- [x] Kept shared questions, ship controls, maps, panels, app actions, sequences, aliases, microphone and command settings working.
- [x] Added 50 greetings and ten capability rundowns, plus all command outcomes, warnings, failed actions and event reports in Aster's voice.
- [x] Expanded to **163 event topics / 1,470 standard wordings**, **807 restrained wordings**, and **67 command outcomes / 289 acknowledgements**. These are a reference snapshot, not fixed requirements for every future character.
- [x] Fixed rotation boundaries, remembered command/chat cycles, migrated existing history and protected event/headline history from rolling-log loss.
- [x] Matched Watcher's idle pacing and willingness to stay quiet; retained necessary warnings and accurate requested reports.
- [x] Integrated the current matching Piper pair under `models/jarvis/onnx/`, pinned both hashes and sizes, and gave Aster its own receipt at `models/jarvis/installed.json`.
- [x] Fixed voice labels/download selection, checksum mismatch handling, replacement-model engine invalidation and safe sharing/removal of the Piper engine.
- [x] Updated deck/sidebar/Studio labels to follow the selected companion; kept behaviour, voice and appearance settings in their proper locations.
- [x] Gave Aster all Watcher Studio controls, immediate resizing, shared size across switches and visually matching diameter.
- [x] Built a unique transparent Three.js halo and matching officer panel with real idle, listening, working, speaking, charging and alert reactions.
- [x] Replaced its intermediate eye/dot designs with a **hexagonal command core**, rotating arcs and scan traces; its centre now holds a translucent lattice prism. Aster's design has no eyes, paired dots, pupil or central star.
- [x] Matched Watcher's text/speech presentation in **both** the floating overlay and NOW panel through the shared caption presenter.
- [x] Added Aster's original **The Crew Register** name-learning introduction, shared answer keys/panel, contextual typed/spoken replies, pronunciation, persistent choice and heard-passage reader/export.
- [x] Restored varied port company at the selected idle pace, including Rare; added dockside/carrier/concourse banks and startup station context from `Location`.
- [x] Audited idle triggers against Watcher: added factual habits, old postcards/service memories, heard-only lore recollections, queued commander facts, long-watch reminders and contextual call replies in Aster's theme. Watcher's dreams, shutter/eye story and mood arcs remain its own.
- [x] Routed automatic postcard writing to the selected companion, including Aster's own context-aware plain/dry notes, signature, persistent rotations, Studio author/preview, saved PNG/editor and text caption attribution.
- [x] Corrected shutdown reports in both commentary modes: all variants include the completed session totals, label them as the watch just recorded and finish that sentence before the farewell. The shared Captain's Log and immediate-save path remain in use.
- [x] Made the approved name/nickname Aster's regular address across its authored greetings, commands, events, story and farewells. Added larger active/quiet shutdown banks with persistent full-cycle rotation and no consecutive repeats; captured personalised story wording for its reader/export.
- [x] Separated explicit LoadGame handling from fallback waking: Aster welcomes quick relogs and repeated legitimate logins, remembers its welcome rotation immediately, deduplicates the same timestamped login and coalesces a welcome issued in the preceding five seconds.
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
- [ ] Review inherited hooks deliberately: `load_game`, `session_start`, `_event_echo`, `_dream`, `_observe_deeper`, `remember`, `tick`, `poke`, `find_voice`, `voice_stage`, `story_marks`, `story_progress`, `pending_question`, `ask`, `meet`, `memories_page` and `_queue_session_extras`. Aster suppresses or replaces Watcher-only behaviour in these paths; a new character must make its own choices.
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
- [ ] After approval, implement this character's intended address policy. Aster uses `watcher_name.call_name` in its authored templates across greetings, commands, reports, story and farewells; Watcher retains `may_name`/`mark_used` and its once-per-session rule. Respect the explicit Commander choice and require permission before using a journal name.
- [ ] Personalise authored addresses before formatting factual fields, preserving actual system/ship/command names containing Commander. Store personalised story passages as heard so later preference changes do not rewrite the reader/export, and apply pronunciation to whole names rather than substrings of other words.
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
- [ ] Test restart during each stage, answered/unanswered retry behaviour, repeated ticks, the selected persona's name-use policy, journal renames, commander/identity isolation, reset backups and book export.
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
- [ ] Check shutdown reports through the shared Captain's Log sign-off path. Every summary-bearing variant must include the completed session totals, identify them as past activity and end the summary sentence before its farewell. A bare `19 jumps` followed by `Until our next departure` can sound like a future route prediction. Cover both commentary modes, quiet/zero-total sessions and immediate persistence after Shutdown.
- [ ] Give active and quiet shutdown replies explicit saved template rotations rather than relying on time-window freshness alone. Complete the applicable bank before reuse and avoid the previous line at cycle boundaries, after restarts, after style changes and after long gaps. See [aster_signoff.py](src/voidcompass/overlays/aster_signoff.py) and `OfficerRandom.farewell_choice`.
- [ ] Distinguish a real login from fallback `awake` calls. Aster's `load_game` bypasses the old 15-minute session guard for every new LoadGame, while the shared journal path still suppresses historical replay. Test quick relogs with/without Shutdown, early Rank/Location or port-snapshot waking, duplicate timestamped delivery, immediate saved welcome rotations, Off and the actual HUD voice queue. The Watcher's default `load_game` delegates to its existing `session_start` policy.

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

The [model index](models/README.md) lists these alongside the existing Watcher and Aster voices. They now power the Axiom and Meridian previews; real synthesis/listening checks remain pending. The downloaded source revision supplies no licence file or usage terms; retain that source record when evaluating either candidate. A future companion still needs its own original identity, lore, dialogue, memory and display.

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

- [x] Make the **boot screen** follow the saved active companion from its first presentation. Replace the hardcoded Watcher display with the selected companion's existing Three.js renderer and visual identity; for Aster, use its halo/command core. Extend the selection path for future companions rather than adding another two-way fallback.
- [x] Load the commander's saved companion selection before choosing the boot renderer, and make companion-specific names/descriptions agree with it. Retain the shared startup progress/readiness flow and existing rule that speech waits until boot completes. Verify fresh/default startup and restarts with Watcher, Aster and any new companion selected.
- [ ] Define a visual identity from the new character's story. Reuse the rendering infrastructure while giving its geometry, motion and panel their own treatment.
- [ ] Implement the renderer and its adapter, following `createAsterDisplay` and `AsterCompanion.update/dispose`.
- [ ] Support the established controls: `setState`, `setContext`, `setColour`, `setActivity`, `setFocus`, `setMotion`, `setReducedMotion`, `setFrameRate`, `setVisible`, `setTilt`, `inspect` and `destroy`, or adapt them through one common interface.
- [ ] Wire real idle/listening/working/speaking/charging/alert states and actual speech energy. Give idle motion a visible but restrained character.
- [ ] Check the display over both bright scenery and dark, busy cockpit backgrounds at small sizes. Reuse `web/assets/companion-frame.js` where a hologram needs the Watcher’s bezel/recess contrast, choosing whether its centre is open or has translucent glass. Preserve the character’s design and keep outer corners transparent.
- [ ] Compare rendered pixels at 54 and 96 px with fixed focus, no speech and no new journal events. A running frame counter alone does not prove visibly animated idle content. Exercise actual Studio selects/switches through the command handler, immediate browser-model publication and native dimensions; test recolouring a parked display, global Theme accent, motion off/on and an event waking it while idle is off.
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
- [ ] If using a reactive centre, share the renderer clock, audio envelope and colour uniforms through `companion-core.js`. If using a portrait mouth, pass speech separately from microphone/alert state, move lips from actual playback levels, and verify closure during silence, queued text and speech completion. Respect Reduced motion and test both surfaces with [test_companion_centres_574.py](tests/test_companion_centres_574.py).
- [ ] Offer every shared control: sizes 54/72/96/144/192/256; own signature/theme/cyan/brass accent (Watcher keeps HAL red); fixed/tracking/expressive focus; calm/standard/alive intensity; idle animation; frame rate. Verify named presets, saved/legacy choices, both renderer colours, panel styling and Eye colour captions; see [test_companion_colours_574.py](tests/test_companion_colours_574.py).
- [ ] Extend `display_key`, `display_options`, Studio snapshot/save validation and the HUD model/apply-settings path. Save updates must redraw and synchronise the live native window.
- [ ] Extend the shared-size carry/save logic beyond `heartbeat_orb_size` and `aster_hud_size`. Size follows the user's selected size across switches; colour, focus and motion preferences remain independent per companion/profile.
- [ ] Retain shared placement, opacity, thought layout, text scale, map hiding and hotkey behaviour. Avoid duplicating these controls on another page.

## 8. Audit identity dispatch when adding another companion

Tick these only after reviewing the whole relevant path, including its fallbacks:

- [ ] `core/companions.py`: validation, names, settings aliases, defaults, display keys/size, address parsing and factory.
- [ ] `overlays/heartbeat_hud.py`: memory path, mind settings refresh, model identity/accent/focus/nature and shared speech scope.
- [ ] `overlays/watcher_ship.py` and `watcher_copilot.py`: persona reply dispatch.
- [ ] `voice/voice_assets.py`: manifests, receipts, download coercion, engine reuse and removal of any one voice among several.
- [ ] `voice/watcher_voice.py`: installed-model checks and engine selection.
- [ ] `dashboard/dashboard_watcher_voice_mixin.py`: selection, size carry, preferences, download/remove/test labels and voice-found presentation.
- [ ] `dashboard/html_dashboard.py`: workspace identity/nature, thought headings, story, deeper memories and book export.
- [ ] `dashboard/html_overlay_studio.py`: settings snapshot, validation, saved-key mapping, toggles and all-companion sizing.
- [ ] `services/local_api.py`, `dashboard/dashboard_api_mixin.py` and `dashboard_api_records_mixin.py`: public companion/voice routes, provider dispatch, status/debug labels, event identities, compatibility aliases and API reference/examples; complete the API checklist below.
- [ ] `web/dashboard/companion-ui.js`, `watcher.js`, `watcher.css`, `index.html` and relevant `app.js` callers: picker, labels, panels, story, voice, Studio and module loading.
- [x] Dashboard boot presentation and renderer loading: use the saved active companion instead of always constructing the Watcher; include startup identity/profile timing and first-frame selection in the audit.
- [ ] `web/heartbeat/app.js`/`index.html`, the new display adapter and `companion-caption.js`: active renderer selection, labels, caption nature and readiness/rerender handling.
- [ ] `dashboard/html_dashboard_server.py`: shared-file serving and `_SANDBOXED_MODULES` entries.
- [ ] Relevant tests and fixtures: extend identity lists instead of accidentally replacing Watcher/Aster coverage.

Use targeted `rg` searches for the companion IDs and the functions above. Treat two-way `else Watcher` fallbacks as integration points. **Do not perform a global replacement of `aster`: the repository also contains unrelated asteroid data and names.** `web/dashboard/app.js` currently contains a pre-existing NUL, so use `rg -a` when searching that file and preserve its contents if editing it.

### Companion API work — pending

This work is still to implement. Existing public routes use `/api/v1/watcher/*` and `/api/v1/voice/*`. The deck already has an internal `/api/data/companion-live` feed; that feed and the overlay’s `/api/live` transport are separate from the public Local API.

- [x] Choose a route strategy before implementation: extend the existing Watcher routes to cover every active companion; add explicit per-companion routes; or introduce one shared companion API. Prefer a shared provider/contract so fixes and future companions do not need duplicated handlers.
- [x] Consider a neutral shared endpoint such as **`GET /api/v1/companion`** for the active companion, with either **`POST /api/v1/companion`** and an `operation` field or action routes under `/api/v1/companion/*`. These are proposed paths, not existing endpoints. Preserve `/api/v1/watcher/*` as documented compatibility aliases when introducing replacements.
- [x] If explicit identity routes are useful, consider `/api/v1/companions/{id}/*` backed by the same provider. Define how inactive companions behave: reading stored information, returning an unavailable response, or an explicit selection action. A request must not silently switch the active companion or send speech through another voice.
- [x] Audit every current Watcher operation and applicable voice operation: status/current thought, injected thoughts, poke, answers, share/meet/book actions, speech, stop/hush, model installation state, and status/debug/event payloads. Route supported actions through the selected companion’s existing mind, settings and voice services.
- [x] Return stable companion ID and display name, plus identity/generation information where needed for live results. Events must identify which companion produced them. Validate requested IDs; do not silently fall back to Watcher for an unknown identity.
- [x] Expose capabilities or clear unsupported-operation responses. Axiom/Meridian’s pending stories, name introductions and postcard content must not return another companion’s fiction or imply that unfinished features exist.
- [x] Preserve commander/profile isolation, the speech queue and audio/caption timing, existing authentication/control gates and app-thread dispatch. Guard companion/profile switches so a delayed request or response cannot affect the newly selected companion.
- [x] Audit internal deck/overlay feeds and callers alongside the public API. Keep active identity, speech levels, captions and errors consistent across the command deck, floating overlays and API clients; retain working internal routes during migration.
- [x] Update [api.md](api.md), the generated/in-app API documentation under [web/api-docs](web/api-docs), route discovery/help and affected client/debug tooling. Add examples for Watcher, Aster, Axiom and Meridian, shared-endpoint requests, compatibility aliases, inactive/unknown IDs and unsupported capabilities. Record the chosen strategy here.
- [ ] After implementation/docs, add focused route/provider/event tests for all four identities, old aliases, permission failures, disabled overlays/voices, profile isolation and switching during a request. Extend [test_local_api_557.py](tests/test_local_api_557.py) and [test_api_voice_watcher_562.py](tests/test_api_voice_watcher_562.py) as appropriate, and add dedicated companion API coverage.

## 9. Verify the finished implementation

Complete implementation and docs first, then add meaningful regressions and run the checks appropriate to the changed paths.

| Area | Required evidence |
| --- | --- |
| Identity/profile isolation | All identities selectable; restart and commander switches preserve each one's settings, story and hours. |
| Upgrade/reset/export | Older memories load, repeat history migrates, reset backs up only the selected file, exports reveal only heard content. |
| Command compatibility | Editable names/aliases and disabled defaults still work; maps, panels, sequences, music, overlays and uplink use shared actions with the right voice. |
| Companion API | Chosen shared/per-identity contract documented; all companions dispatch correctly; legacy Watcher aliases, event identity, capability errors, permissions, profile isolation and switching during requests verified. |
| Dialogue coverage | Every supported command outcome and event has valid, original wording, including restrained mode and failure replies. |
| Repetition | Several complete command/chat cycles, restart mid-cycle, rolling-log pressure, headline rest, cross-topic duplicates and long simulated sessions. |
| Port company | Long station/carrier/concourse watches in both commentary modes and all frequencies; startup after skipped history; fresh versus stale telemetry; no invented docking events, no port chatter in flight, and the selected voice filter. |
| Story | Ordered one-time passages, settling/spacing, time and event gates, no danger interruption, no inherited Watcher-only fiction. |
| Commander name | Original short introduction; explicit name/title/nickname choice; contextual replies and answer keys; pronunciation; each persona's intended address policy; no restart/retry nagging; rename/reset/export and per-companion/profile isolation. |
| Voice installation | Fresh published download and local adoption; both hashes; cancellation/failure; replacement model; independent receipts; removal with other voices installed. |
| Voice switching | Switch while loading/speaking/listening/searching; late results cannot reach the new identity or commander. |
| Captions | Native overlay and NOW panel agree during cold loading, queue pauses, playback, late/missing samples, hidden/visible transitions and reduced motion. |
| Boot screen | The first visible companion matches the saved active identity on fresh/default startup and restart; Aster uses its own halo/core, future companions use theirs, and shared startup progress and deferred speech still work. |
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
- [tests/test_aster_login_574.py](tests/test_aster_login_574.py) — explicit/quick logins, duplicate events, early journal/port wakes, persisted welcome cycles, Off and actual HUD speech-queue delivery.
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
