# VoidCompass // UPDATE LOG

## v5.2.8 // Carrier Logistics Intelligence
**Release Date:** 2026-Jul-28

*   Rebuilt the Fleet Carrier Expedition Navigator around an integrated Spansh calculation: it resolves the carrier's journal-backed current system, applies the correct personal or Squadron Carrier mass/capacity and latest used capacity, plots multiple requested destinations off the interface thread, then imports every calculated jump into the existing profile-local route.
*   Added a themed per-jump route table with distance, tritium used, remaining tank and required restocks, plus persistent Spansh result links, nominal jump timing, explicit Copy Next and Copy Selected waypoint controls, and automatic progress from CarrierLocation/CarrierJump arrivals. Existing Spansh Fleet Carrier result URLs or job IDs can be imported into either a personal or Squadron Carrier route; the direct Spansh page remains the safe fallback if its live service changes.
*   Added a dedicated Carrier Cargo page that treats `CarrierStats.SpaceUsage.Cargo` as the authoritative aggregate while clearly labelling the commodity rows as a commander-supplied baseline plus transfers observed at the commander's own carrier. Elite's journal does not expose a complete itemised carrier commodity hold, so the interface no longer implies that market orders or bartender stock are cargo inventory.
*   Unified that observed manifest with the existing profile-local Specialist carrier inventory, showed active buy/sell orders separately, and included exact free/reserved capacity and the age/source of the latest owner snapshot. Confirmed own-carrier CargoTransfer events now advance the aggregate cargo/free totals and refresh Carrier Command and its overlay immediately, without restoring cargo event spam to the Live Feed; the next CarrierStats snapshot remains authoritative.
*   Extended carrier journal tracking with current and scheduled system addresses, CarrierBankTransfer balance updates, CarrierStats evidence timestamps and persistent Spansh route provenance, while retaining theme and commander-profile isolation.
*   Upgraded the Fleet/Squadron Carrier overlay with the active route's progress, next plotted leg, per-leg and remaining tritium evidence, exact cargo/free capacity and active market-order count while preserving its compact automatic height.

## Earlier releases

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
