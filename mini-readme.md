# VoidCompass // UPDATE LOG

## v5.2.9.7 // Authoritative Overlay Placement
**Release Date:** 2026-Jul-30

*   Overlay Layout Studio positions now remain authoritative while Tk applies a move, preventing the background position-capture loop from restoring a stale coordinate after a drag, snap or preset change.
*   Audited every Studio-managed overlay and removed the Fleet Carrier HUD's recurring primary-screen height clamp, so dynamic redraws and visibility changes preserve the commander's chosen position.
*   Overlay geometry now supports negative virtual-desktop coordinates correctly, keeping layouts reliable on monitors positioned left of or above the primary display.

## v5.2.9.6 // Live Carrier Fuel
**Release Date:** 2026-Jul-29

*   Fleet Carrier expedition arrivals now calculate the actual Tritium depot burn from the completed jump distance, current used carrier capacity and current tank level, keeping Carrier, Dashboard and HUD fuel current between `CarrierStats` snapshots.
*   Paired `CarrierLocation`/`CarrierJump` notifications are accounted once, older startup evidence cannot overwrite newer fuel, and the next authoritative `CarrierStats` or `CarrierDepositFuel` event reconciles the estimate automatically.
*   Dashboard Carrier mode now uses the carrier expedition rather than the ship waypoint route: its next stop, 2/44-style progress, current load, calculated next-leg burn, copy action, priority and support card all come from the live Carrier tracker.
*   Carrier Command now includes a non-blocking Spansh Tritium hotspot finder centred on the live carrier system, with an adjustable range, ring and reserve details, one-click copy, direct Spansh opening and Add to Expedition.

## v5.2.9.5 // Carrier Expedition Progress
**Release Date:** 2026-Jul-29

*   CarrierLocation and CarrierJump arrivals now mark the matching Fleet/Squadron Carrier expedition stop complete on every notification, using system address where available and repairing an unmarked current stop after restart.
*   Route checkmarks, the next-stop arrow, carrier overlay progress and **Copy Next** now share the first genuinely pending waypoint; repeated systems advance one visit at a time, and a finished route reports that no jumps remain.

## v5.2.9.4 // Fleet Carrier Arrival State
**Release Date:** 2026-Jul-29

*   Fleet Carrier jumps now update the active system, dashboard, Navigation HUD, route context, scan state and traffic when the commander travels on the carrier concourse (`CarrierJump` with `OnFoot:true`) as well as while ship-docked.
*   Startup journal recovery recognises the same on-foot carrier arrival, preserves its system context, restores the correct ON FOOT/DOCKED state and no longer carries the previous system's star class into a carrier destination.

## v5.2.9.3 // Authoritative Overlay Layout
**Release Date:** 2026-Jul-29

*   Fixed Studio-positioned overlays snapping back during dynamic redraws by synchronising each overlay's live window, profile coordinates and internal position target; this covers every overlay and specifically corrects the recurring Fleet Carrier HUD reset.
*   Enabled overlays are no longer hidden by adaptive activity modes. Mode switching still prioritises dashboard content and Compass guidance, while Overlay Layout Studio remains the sole authority for module availability.

## v5.2.9.2 // Complete Overlay Layout
**Release Date:** 2026-Jul-29

*   Overlay Layout Studio now lists every configurable overlay from its saved profile position, including disabled/not-yet-created Cargo and Carrier windows, and can enable or disable every module live while retaining its next position.
*   Consolidated passthrough, compact HUD, overlay text scale, alert policy, auto-hide timing, gravity threshold and Navigation HUD CRT controls into the Studio's new Overlay Settings view; the old duplicate Overlays and HUD Effects settings pages are removed.
*   Replaced the game/GPU-conflicting shipped shortcuts with **Ctrl+Alt+Shift+F10/F11/F12**, while preserving commander-customised assignments and migrating only the retired defaults.

## v5.2.9.1 // Visual Overlay Positioning
**Release Date:** 2026-Jul-29

*   Added a themed virtual-desktop preview to Overlay Layout Studio: drag overlay cards inside the app to move the real HUD windows while mouse passthrough remains enabled.
*   Added the profile-aware **Ctrl+Shift+L** global shortcut to open or close Layout Studio, and moved all shortcut assignments onto a dedicated Settings → Hotkeys page.

## v5.2.9 // Explorer Fieldcraft & Reliability
**Release Date:** 2026-Jul-29

*   Added a live route-safety forecast with scoop horizon, conservative fuel endurance, dry stretches, compact-star hazards and low-noise Navigation HUD warnings.
*   Added a journal-evidence Missed Discoveries queue for valuable unmapped worlds, unfinished biology and worthwhile incomplete FSS work, including Galaxy Map, bookmark, copy and dismiss actions.
*   Added a Survey Evidence Inspector that compares live, SQLite, Deep Survey, EDSM-cache and traffic facts, with a safe per-system local-journal repair instead of a full rebuild or upload.
*   Added the Explorer Data Vault for unsold cartographic and biological value, possible bio bonus and recent sale evidence, plus themed local PNG expedition share cards.
*   Added a fully themed Overlay Layout Studio with live coordinates, clearer overlay controls, snapping, resets, remembered Studio geometry and isolated commander-specific presets; a new **Ctrl+Shift+B** field-bookmark hotkey; independent application/overlay text scaling; and reduced motion.
*   Added SQLite-safe profile backups, rotating pre-upgrade/cache-rebuild safety snapshots and a restart-based profile restore with an automatic rollback snapshot.
*   Completed an app-wide responsiveness pass: cached voice metadata, incremental exploration milestones, stable event-feed/HUD rendering, deferred Specialist persistence and bounded UI-thread delivery for background results.
*   Reworked Specialists so only its visible workflow refreshes, Mining retains stable live tables, and Carrier becomes a clear quick-look linked to the single authoritative Carrier Command route, cargo, finance and squadron workspace.

## Earlier releases

*   **v5.2.8.2** — Fixed Fleet Carrier Spansh destination plotting, route persistence and waypoint selection; added weight-aware Tritium readiness, docking cargo evidence and route deletion.
*   **v5.2.8.1** — Made known-system survey completion persistent and profile-safe, added journal repair, and added profile-aware EDSM cache-rebuild controls with visible Live Feed progress.
*   **v5.2.8** — Added integrated Spansh Fleet/Squadron Carrier plotting, route progress, tritium logistics, carrier cargo evidence and the expanded carrier overlay; also kept that overlay visible in Exploration mode.
*   **v5.2.7** — Removed journal-processing stalls through queued carrier persistence, coalesced state snapshots, cheaper Explore refreshes, a UI stall sampler and lightweight first-map rendering.
*   **v5.2.6** — Added filled theme-aware galactic regions, a dedicated Map workspace, smoother route cameras and the first native Linux x86-64 testing build with WSL-assisted packaging.
*   **v5.2.5** — Added the System Completion Matrix, Exploration Action Queue, regional passport, reliable resume checkpoints, expedition milestones, session debriefs and profile-aware overlay hotkeys.
*   **v5.2.4** — Added the procedurally generated Milky Way layer, current-ship map glyph, cached motion detail and immediate Mission Control restoration.
*   **v5.2.3** — Corrected Galaxy Map orientation and controls and added an in-place full-window map focus mode.
*   **v5.2.2** — Added named journal-verified expeditions, objectives, bookmarks, the interactive 3D galaxy map, persistent expedition strip and portable plan/report tools.
*   **v5.2.1** — Rebuilt Explore around Deep Survey Intelligence with system planning, discoveries, logs, stellar wonders, architecture, screenshot atlas and colonisation reconnaissance.
*   **v5.1.2** — Made the Dashboard transform automatically or manually between exploration, trade, mining, combat, ground, engineering, Powerplay, carrier, colony and station modes.
*   **v5.1.1** — Refocused the Command Deck on exploration while retaining every optional operational workspace through a compact add-on strip.
*   **v5.0.7** — Condensed completed biological survey entries without losing their species, value or completion evidence.
*   **v5.0.6** — Made Survey Status fully theme-aware and aligned its background with the other overlays.
*   **v5.0.5** — Improved Survey Status readability while keeping the compact body, biology and geology details balanced.
*   **v5.0.4** — Added journal-backed geological signals to Survey Status.
*   **v5.0.3** — Added identified biological genera, species, variants and completion state to mapped-body survey rows.
*   **v5.0.2** — Corrected Adaptive Command Deck navigation and replaced the ambiguous Open Mode action with its live destination.
*   **v5.0.1** — Added About, release checking, GPL/privacy/Frontier summaries and direct GitHub Issues support.
*   **v5.0.0** — Added the Adaptive Command Deck, unified Operational Queue, activity overlay scenes, Command Health, first-run setup, support bundles and responsive queued persistence.
*   **v4.9.2** — Added the Specialist Operations Console, journal-driven Mining/Combat/Carrier/Exobiology workflows, root Analytics, GPL-3.0 licensing and community standards.
*   **v4.9.1** — Rebuilt Engineering around goals, inventory, wishlist, engineer access and Odyssey planning and completed the app-wide native theme audit.
*   **v4.8.7** — Added overlay mouse passthrough, themed scrolling, immediate ship-identity updates and the unified Exploration & Routes workspace.
*   **v4.8.6** — Added deliberate activity-aware Compass judgment, evidence age/confidence, intention reconciliation and reliable commander flight-state restoration.
*   **v4.8.5** — Completed commander-profile isolation for themes, databases, routes, cargo, overlays, tools and background workers.
*   **v4.8.4** — Added Squadron Command, rebuilt Mining Command and deepened Compass mining, trade, PvE and Powerplay awareness.
*   **v4.8.3** — Rebuilt Profile, Route and Engineer workspaces and extended Carrier Command with Squadron Carrier operations.
*   **v4.8.2** — Rebuilt the Dashboard as a low-noise operational command page with one Active Objective and Activity Stream.
*   **v4.8.1** — Added Architect Command, Fleet Carrier Expedition Navigator, Captain's Log and simplified One Click trade workflows.
*   **v4.7.5** — Removed the temporary startup window and stabilised overlay position restoration and persistence.
*   **v4.7.4** — Added the bounded Python-only Compass Cognitive Engine with learned utility, predictions, memories, goals and intentional silence.
*   **v4.7.3** — Removed Ollama and its GPU/server cost while preserving deterministic personas, learning, speech and cockpit feedback.
*   **v4.7.2** — Added 15 profile-local Compass personas with distinct priorities, tone and initiative.
*   **v4.7.1** — Added the experimental local generative language layer, working-brain context and voice-cache pruning; the language layer was retired in v4.7.3.
*   **v4.6.6** — Refined the Navigation HUD with theme-driven badges, improved CRT states and compact Traffic display.
*   **v4.6.5** — Corrected biological progress to follow real `ScanOrganic` sequences and simplified the Navigation HUD BIO state.
*   **v4.6.4** — Added earned system opinions, backtrack impatience, bio-sale anticipation, cruise chatter and time-aware memory callbacks.
*   **v4.6.2** — Joined journal and Survey Status evidence into a bounded Compass biology model.
*   **v4.6.1** — Added EDSM traffic awareness, valuable-world callouts, route progress and persistent notable bodies.
*   **v4.5.9** — Added AI feed and heartbeat, broad operational awareness, session lifecycle, persistent notable bodies and instant Survey Status hide on jump.
*   **v4.5.7** — Added eighteen optional Piper voices, low-noise callouts, bounded Compass Memory, survey improvements and configurable Navigation HUD CRT effects.
*   **v4.4.4** — Added interactive Galaxy drill-downs for systems, factions, Powerplay, squadrons, conflicts and Community Goals.
*   **v4.4.3** — Simplified Trade into five areas with live EDDN/journal market maintenance and freshness tracking.
*   **v4.4.2** — Added Galaxy Overview influence tracking, faction watches and BGS History integration.
*   **v4.4.1** — Expanded Engineering, Galaxy/BGS and Commander Companion fleet, mission, jumponium and rebuy tools.
*   **v4.3.4** — Added monotonic achievement progress plus route, playtime and progress-bar fixes.
*   **v4.3.2** — Added the native 1,023-entry journal-driven Achievement Centre with migration and journal-history rebuild.
