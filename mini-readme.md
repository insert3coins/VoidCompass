# VoidCompass // UPDATE LOG

## v4.8.3 // Command Workspaces
**Release Date:** 2026-Jul-16

### Profile Recomposition
*   Rebuilt Profile as a native **Commander Record** with focused **Career Overview**, **Fleet & Loadouts**, **Missions**, and **Data & Backups** tabs. Live flight operations and active navigation are no longer duplicated from the Dashboard.
*   Added career rank and superpower-reputation progress, achievement completion and recent milestones, Captain's Log lifetime totals and highlights, and factual lifetime records from Elite's `Statistics` journal event.
*   Added a dedicated fleet workspace for the active ship, EDSY/SLEF loadout exports, stored-ship locations and transfer state, and a concise fleet-carrier identity with direct access to the Carrier Navigator.
*   Expanded mission responsibilities into a full tab with active/expiring totals, delivery and cargo progress, destinations, expiry state, and consolidated massacre-stack progress and rewards.
*   Moved profile files, integration state, EDSM queue visibility, folder access, and complete per-commander backups into **Data & Backups**, keeping maintenance information out of the main career view.
*   Replaced full-page live rebuilds with visible-tab refreshes and content fingerprints. Journal fallback data is cached per commander, session-credit queries are throttled, profile folder size is evaluated only in the maintenance tab, and the existing non-blocking EDSM queue read remains intact.
*   Persisted the latest complete `Statistics` snapshot inside each commander's companion state so lifetime career records survive restarts without repeatedly rescanning journal history.

### Route Command Recomposition
*   Rebuilt Route around a new **Route Overview** that presents the live Elite `NavRoute.json` lane and the persistent expedition-waypoint lane separately, with game jumps, waypoint completion, next stop, remaining distance, star classes, notes, and one-click **Copy Next**. An active game route takes copy priority and cleanly falls back to the next pending waypoint.
*   Replaced the clipped waypoint action rail and monospaced pseudo-table with a real column layout for status, system, segment distance, cumulative distance, and notes. Selection, batch, ordering, EDSM refresh, CSV export, and destructive controls now remain visible at the embedded dashboard size.
*   Renamed **System Plotter** to **Neutron Plotter** to match its actual manual Spansh workflow. Normal 4x and Overcharge 6x plotting, explicit import, list copying, CSV imports, duplicate policies, and the no-autoplot behavior remain intact.
*   Deferred Route table and overview redraws while its dashboard page is hidden, then coalesced the latest current-system, live-route, and waypoint state when Route becomes visible again.
*   Hardened waypoint storage with UTF-8 validation, atomic replacement writes, visible save errors, single-write batch deletion, state-preserving edits, and first-pending fallback for auto-copy when the current system is between saved waypoints. Removed nested Tk `update()` calls from route clipboard actions.

### Engineering Workshop Recomposition
*   Reworked Engineer into a native **Engineering Workshop** with a concise Overview for held material types, ready and pinned goals, missing shared units, engineer access, jumponium reserves, near-capacity stock, and the highest combined shortages.
*   Expanded the verified planner from two starter recipes to 16 high-use ship blueprints covering FSD, thrusters, power plants, distributors, shields, shield boosters, armour, life support, and surface scanning. Plans now support current grade, target grade, and module quantity using the post-rebalance G1-G5 application budget.
*   Added a combined, non-double-counted shopping list across every pinned goal. Individual goals retain conservative same-family material-trader suggestions, while nearby Spansh trader results remain visible inside Planner and can be handed to the existing manual Route Command plotter.
*   Added searchable Raw, Manufactured, Encoded, Engineer, and Odyssey views. Ship materials can switch between held-only, complete catalogue, and near-capacity stock; Engineer now shows the full 38-entry known catalogue while clearly separating synced access from unknown progress.
*   Made **Route Selected** contextual to engineer and trader rows, clarified that Odyssey currently presents live locker inventory without guessing recipe purposes, and kept all Workshop controls visible at the native minimum page size.
*   Deferred and coalesced Workshop redraws while the page is hidden. Engineering saves now use validated atomic replacement, report failures to the page, and preserve a timestamped copy of unreadable data before recovering safely.

### Squadron Carrier Awareness
*   Extended the existing Carrier Command panel for Frontier's journal-backed `CarrierStats.CarrierType`, distinguishing personal `FleetCarrier` and squadron-owned `SquadronCarrier` records without creating a second carrier tracker.
*   Added carrier type plus squadron name/rank to Carrier Overview using `SquadronStartup`, creation/join, promotion/demotion, leave, kick, and disband journal events. Missing membership or management data remains explicitly unsynced rather than inferred.
*   Preserved the existing jump, expedition, fuel, finance, storage, services, trade-order, HUD, and Discord paths for either carrier type. Personal-carrier upkeep rates are not applied to a squadron carrier; its journal finance remains authoritative.
*   Extended the existing Carrier Discord webhook to Squadron Carrier jump-plotted, jump-complete, cancellation, cooldown-ready, manual status, and test notifications. Embeds now identify personal versus squadron carriers and include the squadron name/rank when journal data is available; the shared webhook remains configurable under **Settings → Integrations**.
*   Hardened carrier identity matching so travelling aboard or donating tritium to an unrelated carrier cannot overwrite the commander's managed carrier state. Updated current journal field handling for cargo-reserved space and service tax rates.

## v4.8.2 // Operational Command Dashboard
**Release Date:** 2026-Jul-16

*   Rebuilt Dashboard as a low-noise operational command page with unified Flight and Compass briefings, a promoted Active Objective, contextual operations, and one consolidated Activity Stream.
*   Preserved the native navigation rail, command strip, embedded workspaces, overlays, diagnostics, carrier widgets, route notes, event filters and raw journal access while coalescing hidden-page redraws.

## v4.8.1 // Command Centres & One-Click Trade
**Release Date:** 2026-Jul-16

*   Added the Architect Command Centre, Fleet Carrier Expedition Navigator, and per-commander Captain's Log with bounded background journal imports and Markdown exports.
*   Reworked Trade around a One Click landing page while preserving the detailed Routes, Markets, Local, Tracking and Database workspaces.

## v4.7.5 // Stable Startup & Overlay Positions
**Release Date:** 2026-Jul-15

*   Removed the temporary startup window and added a protected settling period plus unified coordinate persistence for every native HUD and overlay.

## v4.7.4 // Compass Cognitive Engine
**Release Date:** 2026-Jul-14

*   Added the bounded Python-only Compass Cognitive Engine with utility scoring, outcome learning, pilot predictions, anomaly detection, contextual memories, goals and intentional silence.
*   Evolved all 15 personas into behavioural policies and added transparent cognitive state, learned usefulness and reset controls without an LLM or GPU workload.

## v4.7.3 // Lightweight Deterministic Compass
**Release Date:** 2026-Jul-14

*   Removed Ollama and its GPU/server lifecycle while preserving personas, cockpit memory, learned habits, Piper speech, the situational adviser, Live Feed and AI heartbeat integration.

## v4.7.2 // Living Compass Personas
**Release Date:** 2026-Jul-14

*   Added 15 per-commander personas with distinct tone, priorities and initiative, plus preview controls and accurate language-layer status reporting.

## v4.7.1 // Local Generative Compass Language
**Release Date:** 2026-Jul-14

*   Added the optional guarded Ollama language layer, working-brain context, situational adviser, prewarming, validation/fallback controls and scrollable Compass settings; this experimental runtime was removed in v4.7.3 after real-game performance testing.
*   Added automatic voice-cache pruning and corrected final FSS completion refreshes in Survey Status.

## v4.6.6 // Navigation HUD Refinements
**Release Date:** 2026-Jul-13

*   Added theme-driven informational badges, improved CRT badge states and moved Traffic into the compact badge row.

## v4.6.5 // Accurate Exobiology Tracking + HUD Polish
**Release Date:** 2026-Jul-13

*   Corrected biological progress to follow real `ScanOrganic` `ScanType` sequences and simplified the Navigation HUD's live BIO state.

## v4.6.4 // Living Cockpit Companion
**Release Date:** 2026-Jul-13

*   Added earned system opinions, backtrack impatience, bio-sale anticipation, quiet-cruise chatter, time-aware greetings and specific memory callbacks.
*   Fixed Survey Status organic refresh and made the Navigation HUD's biology state live.

## v4.6.2 // Bio-Aware Compass Intelligence
**Release Date:** 2026-Jul-13

*   Joined journal and Survey Status evidence into a bounded Compass biology model covering signals, genera, sampling, rewards, colony spacing and Codex discoveries.

## v4.6.1 // Traffic-Aware Compass Intelligence
**Release Date:** 2026-Jul-13

*   Added EDSM traffic awareness, valuable-world callouts and live route/waypoint progress on Dashboard.
*   Consolidated notable bodies into persistent Survey Status instead of duplicating them in System Info.

## Earlier releases

*   **v4.5.9** — Compass AI feed category, AI heartbeat pulse, broad exploration/operational-domain awareness, `LoadGame`/`Shutdown` session lifecycle, persistent notable bodies, combined body labels, and instant Survey Status hide on jump.
*   **v4.5.7** — Eighteen optional Piper neural voice packs, low-noise safety/navigation/exploration callouts, the original bounded Compass Memory, native Engineering/Exploration/Biological Survey improvements, and configurable Navigation HUD CRT effects.
*   **v4.4.4** — Interactive Galaxy drill-downs for system, factions, Powerplay, squadron, conflicts, and Community Goals.
*   **v4.4.3** — Simplified five-area Trade workspace; market database moved to live EDDN/journal maintenance with freshness tracking.
*   **v4.4.2** — Galaxy Overview influence tracking, faction watches with low-noise alerts, and BGS History integration.
*   **v4.4.1** — Expanded native Engineering page, integrated Galaxy/BGS page, and Commander Companion fleet/mission/jumponium/rebuy warnings.
*   **v4.3.4** — Made achievement progress monotonic so journal rebuilds can no longer destroy unlocks; fixed route-achievement resets and playtime-while-not-running; added progress bars.
*   **v4.3.2** — Native 1,023-entry journal-driven achievement system with its own Achievement Centre page, legacy migration, journal-history rebuild, and general responsiveness work.
