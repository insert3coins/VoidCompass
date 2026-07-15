# VoidCompass // UPDATE LOG

## v4.8.2 // Operational Command Dashboard
**Release Date:** 2026-Jul-16

### Dashboard Recomposition
*   Rebuilt the central Dashboard as a low-noise operational command page while retaining the existing native navigation rail, command strip, embedded workspaces, theme system, overlays, and journal plumbing.
*   Added a unified **Flight Briefing** for ship/flight state, navigation, route/waypoint progress, survey completion, fuel, cargo, legal state, and unsold-data risk without repeating the Navigation HUD's destination strip.
*   Added a live **Compass Briefing** showing persona, relationship stage, mood, latest useful cognitive observation, remembered-system/memory totals, and decision count. Intentional silence is displayed as standing by instead of exposing internal scoring noise.
*   Added a single promoted **Active Objective** chosen from unfinished biological sampling, high-risk unsold data, incomplete system surveys, active routes/waypoints, and mission work, with one-click Copy Next, Explore, and Ground Target actions.
*   Added contextual **Active Operations** summaries for Architect sites, missions, trade/cargo, mining sessions, and carrier expedition stops. Inactive areas stay out of the summary while their detailed workspaces remain available from the navigation rail.
*   Consolidated the two always-visible timelines into one **Activity Stream**. The curated colour-coded feed is the default, while the complete icon-based journal history remains available through **Raw Journal**; both retain hidden-page redraw coalescing.
*   Kept diagnostics collapsed beneath the Dashboard and preserved the existing carrier fuel/jump widgets, route notes, event filters, clipboard behavior, and overlay z-order restoration.

## v4.8.1 // Command Centres & One-Click Trade
**Release Date:** 2026-Jul-16

### Architect Command Centre
*   Evolved the Colonisation page into an **Architect Command Centre** while retaining the existing per-project detail and aggregated Shopping List. The new Command view summarises active sites, delivered and remaining tonnage, ship-load estimates, and a bounded construction activity timeline.
*   Real `ColonisationConstructionDepot` and `ColonisationContribution` journal events now retain progress and commodity-delivery history per commander. Unsupported claim/beacon states are not inferred.

### Fleet Carrier Expedition Navigator
*   Added a persistent **Expedition** tab to the existing Carrier page. Paste a Spansh or hand-planned system list, name the expedition, keep a configurable tritium reserve, copy the next stop, and open the Spansh Fleet Carrier router in one click.
*   Real `CarrierJump` and `CarrierLocation` arrivals automatically mark matching route stops complete. The navigator shows visited/remaining stops, nominal 20-minute-per-jump travel time, and fuel above reserve without inventing per-jump tritium figures that the journal does not provide.

### Captain's Log / Expedition Chronicle
*   Added a per-commander **Captain's Log** to Explore. It reconstructs bounded `LoadGame`/`Shutdown` sessions from the configured live journal folder and records routes, jumps, Codex discoveries, completed biological analyses, screenshots, trade totals, exploration/biology sales, and ship losses.
*   Historical imports run away from the Tk thread, skip unchanged journal files on later launches, merge safely with live callbacks, retain 250 sessions with 180 highlights each, and export any session as Markdown.

### One-Click Trade
*   Reworked Trade around a new **One Click** landing page for best routes, cargo buyers, nearby opportunities, the current market, price tracking, and market-database maintenance. Each action uses the current system, ship and cargo context, then opens its result in the existing advanced panel rather than duplicating the trade engines.
*   Preserved Routes, Markets, Local, Tracking, and Database as detailed workspaces, including the existing fast `marketdb.is_ready()` search path, live EDDN/journal updates, route tracking, watchlists, analytics, and market import tools.

## v4.7.5 // Stable Startup & Overlay Positions
**Release Date:** 2026-Jul-15

### Startup & HUD Persistence
*   Removed the small temporary Tk window that appeared before the dashboard by keeping the main root hidden until the complete interface is ready.
*   Added a four-second startup settling period during which transient Windows coordinates cannot overwrite saved overlay positions. Hidden or not-yet-mapped `(0,0)` readings are also rejected when a valid saved position exists.
*   Unified saved-position reapplication, live persistence, and shutdown capture across the Navigation, Cargo, Carrier, Prospector, System Info, Gravity Warning, Station Info, Survey Status, Toast, Heartbeat, and Colony overlays while preserving each HUD's dynamic size.
*   Confirmed overlay coordinates round-trip through the active commander profile; the Ground Target popup continues to retain its complete saved geometry independently.

## v4.7.4 // Compass Cognitive Engine
**Release Date:** 2026-Jul-14

### Adaptive Local Intelligence
*   Added a bounded, Python-only **Compass Cognitive Engine** with no LLM, GPU workload, model download, server, or network dependency. Verified observations compete through utility scoring based on urgency, novelty, active goals, learned usefulness, current mood, relationship context, adviser frequency, recent repetition, and the active persona; low-value candidates become intentional silence.
*   Evolved all 15 personas from signature prefixes into behavioural policies. Tactical prioritises missions and operational risk, Guardian protects fuel/data/cargo, Scientific and Exobiologist favour survey evidence, Engineer focuses readiness, Pathfinder favours route progress, Archivist recalls history, Companion values shared context, and Emergent favours learning and pattern changes. Curated procedural templates and mood-safe clauses provide substantial line variation without inventing game facts; safety speech remains isolated.
*   Added outcome learning: Compass remembers whether advice was followed—selling exploration/biology data, continuing surveys or samples, completing missions, clearing cargo, following routes, or performing engineering—and adjusts that topic's future utility. Learning is bounded to 48 topics, 40 recent decisions, 8 pending outcomes, and 24 samples per metric.
*   Added lightweight pilot predictions for typical session jumps/duration/distance, surveyed-system size, biological yield, fuel reserve at jump, cargo sale point, docking point, survey completion, profitable trade sessions, and biology sale timing. New baselines appear sparsely in the AI Live Feed and pulse the journal heartbeat.
*   Added anomaly and pattern awareness for unusually large systems, exceptional biological yield, unusually busy EDSM traffic, longer-than-normal sessions, and surveys abandoned earlier than the pilot's normal pattern. Relevant high-salience memories can now be recalled on familiar-system returns using local contextual scoring rather than embeddings.
*   Added explicit goal awareness for routes, mission counts, incomplete FSS work, unresolved biology, active samples, unsold data, and pinned engineering work. Shutdown/app-close/profile-change debriefs compare the session with learned norms and retain the highest outstanding priority.
*   Added **Settings → Compass AI → Cognitive State** transparency showing the last speak/silence decision, exact reason and utility score, current priorities, predictions with confidence, learned advice usefulness, and pending outcome checks. Settings can independently disable decision scoring or outcome learning and reset cognitive learning without deleting the wider autobiographical memory.

## v4.7.3 // Lightweight Deterministic Compass
**Release Date:** 2026-Jul-14

### Compass Runtime
*   Removed the optional Ollama/local-LLM language layer, model downloads, warm-up worker, GPU inference, background server management, language status events, and all related Settings/configuration controls. Compass no longer starts or communicates with Ollama and cannot contend with Elite for GPU time.
*   Preserved the full per-commander cockpit memory, learned habits, moods, journal/gameplay awareness, working-brain file, Piper TTS, session greetings, ambient remarks, and AI Live Feed/heartbeat integration.
*   Kept all 15 personas and moved their recognisable signature cues onto the lightweight deterministic callout path. **Test Persona** now previews and speaks the selected persona locally without model generation; urgent safety speech remains unstyled.
*   Retained the verified situational adviser as a Python-native feature, including mission destinations, survey and biological priorities, data-sale services, mining hold thresholds, trade milestones, and Quiet/Balanced/Proactive cooldowns. Existing adviser preferences migrate automatically from the retired LLM keys.
*   Enforced PyInstaller 6.21 or newer for release builds so the corrected Windows one-file bootloader is used. Together with deterministic Piper shutdown, this addresses the remaining `VCRUNTIME140.dll` `_MEI…` cleanup warning on application exit.

## v4.7.2 // Living Compass Personas
**Release Date:** 2026-Jul-14

### Compass Personas
*   Added 15 per-commander Ollama personas: **Compass, Tactical, Guardian, Scientific, Exobiologist, Engineer, Wayfarer, Pathfinder, Veteran, Deadpan, Stoic, Optimist, Archivist, Companion,** and **Emergent**. Persona controls tone, cadence, humour, initiative, and memory emphasis inside the working brain but cannot override factual validation or deterministic safety speech. Settings now separates persona from Quiet/Balanced/Chatty presence, explains every selection, previews unsaved choices through **Test Persona**, and reports the active persona in Compass Intelligence State and the Live Feed. Ollama warm-up completion now immediately announces that generative language is online and pulses the AI heartbeat; failures include their real reason, while a rejected or timed-out individual callout is accurately reported as a one-callout fallback rather than declaring the whole language layer unavailable.

## v4.7.1 // Local Generative Compass Language
**Release Date:** 2026-Jul-14

### Optional Local Compass Language
*   Added an optional Ollama-powered language layer for Compass using explicit `qwen3.5:9b` (recommended) or `qwen3.5:4b` (performance) models. It enriches navigation, exploration, objectives, greetings, debriefs, and ambient remarks while the existing journal brain remains authoritative.
*   Safety and danger speech never enters the LLM. Every generative request starts from an approved deterministic line, enforces a structured one-sentence response, preserves required system/body/species names and supplied numbers, rejects questions, missing protected terms, and invented numbers, and falls back automatically on any timeout or validation failure.
*   Model loading and generation run off the Tk thread through a latest-wins worker. `LoadGame` prewarms both model weights and the schema-constrained chat path, hiding the one-time AMD compile delay; the journal heartbeat pulses while Compass is generating.
*   Added **Settings → Compass AI → Local Generative Language** controls for enable/disable, automatic local Ollama start, 9B/4B selection, fallback timeout, model installation/update, GPU warm-up, live status, and spoken language testing. Disabling the feature immediately restores the original callout path.
*   Compass's Live Feed reports the language layer coming online or entering fallback once per state transition rather than logging each generation.
*   Expanded the optional language layer into a low-noise **Situational Adviser**. Compass now receives a compact verified snapshot of route/fuel/cargo state, survey and biology progress, valuable bodies, mission destinations, unsold data, station services, engineering intentions, trade/mining progress, and learned gameplay experience. It can add one useful observation to an existing callout and can proactively brief mission destinations, usable data-sale services, FSS priorities, mining hold thresholds, and trade-profit milestones.
*   Added **Quiet**, **Balanced**, and **Proactive** advice frequencies with per-topic and global cooldowns. Startup journal replay remains silent, repeated events are suppressed, and the adviser can be disabled independently without disabling natural LLM wording.
*   Made the expanded **Compass AI** Settings page vertically scrollable while keeping its navigation and Save/Cancel controls fixed. The mouse wheel and visible scrollbar now reach the language controls, intelligence state, and full memory timeline at smaller window sizes.
*   Added automatic generated-voice cache pruning, enabled by default with a **7-day unused-audio retention** setting. Cached WAV hits refresh their last-used timestamp, pruning runs off the UI thread at startup, after playback, and after Settings changes, and the existing 300-file ceiling remains as a secondary cap. Downloaded Piper runtimes and voice packs are never included. The expanded Voice page now scrolls so all retention and voice-pack controls remain reachable.
*   Fixed Survey Status retaining a stale FSS count such as `SCAN 10/11` after `FSSAllBodiesFound`. Batched journal processing now performs one final coalesced overlay refresh after the committed scan state reaches `11/11`.
*   Evolved Ollama from a wording layer into a persisted per-commander **working brain**. `cockpit_ai_brain.json` compiles Compass's identity rules, learned pilot model, mood, intentions, relevant long-term memories, current session/live gameplay, and recent language decisions without exposing the full autobiographical archive to the model. In one structured request Ollama can now choose useful speech or intentional silence for optional thoughts, avoid recent repetition, and produce the contextual line; required callouts, factual validation, deterministic safety speech, and immediate fallback remain enforced by Python.
*   On the development RX 6800, warmed `qwen3.5:9b` responses validated at roughly 1.2–1.4 seconds and remained fully GPU-resident. The model is unloaded on VoidCompass exit by default so VRAM is returned to the game.

## v4.6.6 // Navigation HUD Refinements
**Release Date:** 2026-Jul-13

### Navigation HUD
*   `FSS` is no longer styled as a hazard alert. Badges now have a fourth state, `info` (theme yellow, plain outline, no hazard stripes), reserved for mode indicators rather than genuine warnings — so `FSS` reads clearly instead of blurring into neighbouring `UNDISC`/`BIO` alert badges that share the same orange hazard-stripe treatment.
*   Badge colors are now fully theme-driven end to end, including the muted state, so switching the app's color theme carries through to every badge automatically.
*   Compact layout: `TRAFFIC` now sits right-aligned on the same row as the badges, vertically centered against them, instead of its own mostly-empty row above — the badge row dynamically reserves exactly the space `TRAFFIC` needs so a full badge row never overlaps it. The freed vertical space is reclaimed too: the compact HUD is 10px shorter, tightening the gap that opened up at the bottom.

## v4.6.5 // Accurate Exobiology Tracking + HUD Polish
**Release Date:** 2026-Jul-13

### Fixes
*   Fixed the real root cause behind lingering incorrect bio progress: live `ScanOrganic` journal events never actually carry `Sample`, `IsComplete`, `IsNewEntry`, `IsNewSample`, `BodyID`, or `MaxSamples` fields, despite the app previously assuming they did. Completion and sample progress (1/3, 2/3, 3/3) are now derived from the event's `ScanType` sequence (`Log`/`Sample`/`Analyse`) instead, fixing Survey Status counts that stuck at `0/1`, a silent sample undercount, and Compass's biology-awareness progress capping at `2/3`.
*   Corrected the same flawed assumption in the live bio-sample toast and Compass's own memory tracking, so "Sample n/3" toasts and Compass's biological sample tallies now match what actually happened.

### Navigation HUD
*   Simplified the `BIO`/`VALUE` badges added in 4.6.4 into a single `BIO` presence flag — alert while signals remain unsampled, ok once caught up — since detailed progress and value already live in the Survey Status overlay; removed the redundant `VALUE` badge.
*   Gave the badge row a facelift: badges now pick up the same CRT glow as the rest of the HUD, an ok badge is a solid backlit fill instead of a flat outline, and each state gets a glyph (`●`/`✓`/`○`) for quicker at-a-glance reading.

## v4.6.4 // Living Cockpit Companion
**Release Date:** 2026-Jul-13

### Fixes
*   The Survey Status overlay's `BIO x/y` count no longer sticks at zero after completing organic scans — the overlay is now refreshed on every `ScanOrganic` event instead of only on the next unrelated redraw.
*   The Navigation HUD's `BIO`/`VALUE` badges are no longer static. `BIO` now shows live completed-versus-detected sample progress (`BIO 2/5`) instead of a fixed system-wide signal count, and `VALUE` shows a running credit total of completed organic scans instead of an unrelated valuable-body count.

### Compass Opinions & Anticipation
*   Compass now forms earned opinions about specific systems from real history: a system it has repeatedly had trouble in (heat damage, interdictions, ship loss) gets a wary remark on return visits; a system with valuable finds or first discoveries gets a fond one.
*   Added backtrack impatience — repeatedly bouncing between the same two systems now earns a low-key remark.
*   Added bio-sale anticipation — Compass learns the typical sample count at which you sell biological data and gives a heads-up as you approach it, rather than only reacting after the fact.

### A Living Cockpit
*   Added ambient chatter: occasional unprompted lines during quiet cruising after a long stretch with no journal activity, drawn from a 20-line pool so long sessions do not repeat themselves.
*   Added time-aware session greetings: Compass now recognises "picking back up mid-session," a fresh day, or a long absence, and greets you differently.
*   Added memory callbacks: system opinions now reference the specific remembered event ("I still remember losing a ship here") instead of only an aggregate count, when one exists.
*   Added three independent settings under **Settings → Voice → Compass Memory**: **Ambient chatter while cruising**, **Session greetings**, and **Memory callbacks in system remarks**, each defaulting on and degrading gracefully when off.

## v4.6.2 // Bio-Aware Compass Intelligence
**Release Date:** 2026-Jul-13

- Compass biological awareness now joins journal activity with Survey Status context: it retains bio/geo signal totals, detected and predicted genera, three-stage sample progress, species/body history, reward values, colony spacing, completed analyses, and unique biological Codex records.
- The Compass AI Intelligence State exposes the growing biology model, while only sparse milestones reach the Live Feed or evolved voice lines so routine sampling does not create chatter.

## v4.6.1 // Traffic-Aware Compass Intelligence
**Release Date:** 2026-Jul-13

- Compass now consumes the same EDSM day/week/total traffic shown on the HUD and retains it per remembered system, suppressing contradictory whole-system `UNDISC` state while genuine first discoveries still count.
- Compass now announces newly scanned Earth-like, water, ammonia, and terraformable worlds with class-specific personality variants and remembers each unique valuable body.
- The Dashboard's Current Flight card shows live route progress as remaining NavRoute jumps or labelled visited/total waypoint progress.
- Notable and high-value body rows now live exclusively in the persistent Survey Status overlay; the temporary System Info overlay no longer duplicates them.

## Earlier releases

- **v4.5.9** — Compass AI feed category, AI heartbeat pulse, broad exploration/operational-domain awareness, `LoadGame`/`Shutdown` session lifecycle, persistent notable bodies, combined body labels, and instant Survey Status hide on jump.
- **v4.5.7** — Eighteen optional Piper neural voice packs, low-noise safety/navigation/exploration callouts, and the original bounded local Compass Memory (recurring systems/ships/species, relationship stages, moods, habits, expeditions, session debriefs, memory-cap settings, Compass AI settings page). Native Engineering, Exploration, and Biological Survey HUD improvements including the packaged SrvSurvey Codex catalogue. Added configurable Navigation HUD CRT effects.
- **v4.4.4** — Interactive Galaxy drill-downs for system, factions, Powerplay, squadron, conflicts, and Community Goals.
- **v4.4.3** — Simplified five-area Trade workspace; market database moved to live EDDN/journal maintenance with freshness tracking.
- **v4.4.2** — Galaxy Overview influence tracking, faction watches with low-noise alerts, and BGS History integration.
- **v4.4.1** — Expanded native Engineering page, integrated Galaxy/BGS page, and Commander Companion fleet/mission/jumponium/rebuy warnings.
- **v4.3.4** — Made achievement progress monotonic so journal rebuilds can no longer destroy unlocks; fixed route-achievement resets and playtime-while-not-running; added progress bars.
- **v4.3.2** — Native 1,023-entry journal-driven achievement system with its own Achievement Centre page, legacy migration, and journal-history rebuild, plus general app responsiveness work.
