# VoidCompass // UPDATE LOG

## v5.2.2 // Expedition Mission Control
**Release Date:** 2026-Jul-26

*   Added profile-local **named expeditions** inside Explore's existing Expedition page, with create, activate, pause, resume, complete and delete controls plus durable progress across game and app sessions.
*   Added journal-verified objectives for destinations, complete FSS surveys, individual or counted DSS mappings, biological species or analysis counts, Codex categories or counts, screenshots, galactic regions, valuable worlds, first discoveries and saved Colonisation Recon; manual objectives remain available for facts Elite does not journal.
*   Audited the automation against Frontier's journal specification: a honk records the reported body count, while only `FSSAllBodiesFound` completes an FSS objective. Semantic fact deduplication also prevents repeat scans of one body, species, Codex entry or screenshot from inflating goals and statistics.
*   Added tagged, prioritised **bookmarks and revisit targets** from Mission Control, System Survey and Discoveries, including optional body context, notes, recorded `StarPos`, automatic visited state on a matching arrival or body record and bounded per-commander storage.
*   Rebuilt the expedition map as an interactive Elite-style 3D galaxy view with rotate, pan, zoom, current-system focus, adaptive region labels and Perspective, Galaxy Overview, Top, Side and Route Focus cameras.
*   Added the complete 42-region Universal Cartographics layout for exact offline `StarPos` lookup and bounded map contours, with the pinned MIT data source documented and packaged alongside the application.
*   Retained Valuable, Biology, Codex, Photo, Recon and Bookmark layers. Layer controls follow the active theme, explicit bookmark coordinates can be plotted without route history, and a clicked marker opens its Discoveries or Mission Control record.
*   Added a persistent active-expedition strip across all four Explore pages, showing objective progress, systems, distance and the next goal without adding another top-level workspace or nested notebook.
*   Connected named expeditions to Compass and the Live Feed with a low-noise resume briefing, completed-objective callouts, coloured expedition events and a verified working-brain snapshot containing route, progress and next-action facts.
*   Extended Expedition Reports across the named expedition's full timestamp and system scope, including multi-session route/survey statistics, objective evidence, bookmarks and highlights; reports remain locally copyable or saveable as Markdown.
*   Added portable VoidCompass JSON plan import/export and one-click newline waypoint sharing, with imported expeditions safely paused and assigned fresh local identifiers.
*   Kept Mission Control lightweight through bounded histories, coalesced background persistence, replay-safe journal identities, graceful shutdown flushing and hard profile isolation.

## v5.2.1 // Deep Survey Intelligence
**Release Date:** 2026-Jul-26

*   Rebuilt Explore around four clear pages—**System Survey**, **Expedition**, **Discoveries** and **Logbook**—removing the nested Survey/Chronicle tab stacks while retaining their tools in unified, filterable views.
*   Integrated seven profile-local **Deep Survey** capabilities directly into those pages: System Survey Planner, Expedition Route Map, Stellar Wonders, Research Ledger, Screenshot Discovery Atlas, System Architecture and Colonisation Recon.
*   Built a measured body-by-body survey plan that ranks DSS, biology, geology, first-discovery and first-footfall opportunities, explains every recommendation and stays silent about facts the journal has not supplied.
*   Added a projected expedition map beside route intelligence, with flat Overview, Waypoints, Neutron and Map section controls; it retains up to 5,000 journal `StarPos` arrivals while drawing a representative route on very large histories to protect UI performance.
*   Unified system history, valuable bodies, Codex, transient signals, DSS efficiency and screenshots into one searchable **Discoveries** archive, including new-entry, region, surface-position, threat, expiry-at-discovery and probe-target facts where Frontier journals provide them.
*   Added one-click copy/save **Expedition Reports** in Markdown, combining selected Captain's Log route and highlights with scoped Codex/DSS/signal/photo totals, survey value, stellar wonders, saved recon candidates and top retained worlds.
*   Remembered the active Explore page, System Survey filter, Discoveries filter and Expedition section separately for every commander, and added Copy System/Open EDSM actions to discovery records.
*   Added a lazy screenshot atlas that joins Screenshot metadata to converted images, previews them only on selection and preserves system, body, surface coordinates, altitude and heading when reported.
*   Added a journal-parent system architecture tree and explainable wonders detector for exotic stars, notable worlds, unusual orbits, extreme environments, rings, biology and first-discovery opportunities.
*   Added a conservative colonisation reconnaissance dossier with saved per-commander candidates, remaining-survey gaps, copyable Markdown, Captain's Log entries and direct handoff to Architect Command without claiming journal-unverifiable eligibility.
*   Indexed existing commander journals on a background worker, bounded every retained collection and coalesced Deep Survey persistence so first-time history recovery never blocks the cockpit UI.
*   Standardised internal stellar class labels throughout System Info, Dashboard, Explore and Route views, and moved routine scan-database commits plus Trade startup readiness off the Tk thread after live diagnostics exposed storage stalls.

## v5.1.2 // Adaptive Activity Dashboards
**Release Date:** 2026-Jul-23

*   Made the Dashboard genuinely adaptive: Exploration remains the default, while verified Trade, Mining, Combat, Ground, Engineering, Powerplay, Carrier, Colony and Station activity transforms the hero, telemetry, progress, priority, support card and primary workspace action.
*   Made the curated activity-log heading follow the active mode and added an Operations filter for Trade, Carrier, EDDN/EDSM, profile and achievement events without changing the secondary raw Journal Diagnostics view.
*   Added a themed manual mode selector for Automatic, Exploration, Trade, Mining, Combat/AX, Ground, Engineering, Powerplay, Carrier, Colony and Station dashboards, making every transformation directly testable from the Command Deck.
*   Preserved navigation and the Exploration escape action in every mode, retained persistent manual mode locking, and made automatic add-on activity age safely back to Exploration after 30 idle minutes.

## v5.1.1 // Exploration-First Command Deck
**Release Date:** 2026-Jul-23

*   Reorganised the permanent rail into expanded **Core**, **Explore**, **Expedition**, **Operations** and **System** groups while retaining a direct button for every existing workspace.
*   Added lightweight Expedition and Operations overview pages without replacing Carrier, Colony, Analytics, Achievements, Trade, Mining or Specialists; full workspaces remain first-open lazy.
*   Added themed sidebar scrolling and profile-aware manual group collapsing, with every group expanded by default so tools never disappear unexpectedly.
*   Simplified Trade's default view to four everyday actions and a live EDDN receive/upload status. All existing routes, markets, commodities, tracking and database controls remain available through Advanced Tools.
*   Added direct Galaxy access inside Explore and retained Compass/Adaptive Command awareness across exploration and wider Elite gameplay.
*   Reworked the Dashboard around a wide current-system survey hero and next-destination panel, including live FSS completion, BIO/GEO, notable discoveries, scanned value and traffic; exploration priority, Compass and expedition support remain immediately below while wider gameplay is reduced to a compact add-on strip.
*   Rebuilt Dashboard activity as an **Exploration Log** with a primary Flight Log, grouped discovery/navigation/operations/Compass/alert filters, live counts, selected-event copy/source actions and a clearly secondary raw Journal Diagnostics view.
*   Corrected EDSM cargo synchronization with complete debounced `Cargo.json` snapshots, including empty ship or SRV inventories, while continuing to suppress raw cargo-event spam.

## v5.0.7 // Condensed Completed Biology
**Release Date:** 2026-Jul-23

*   Fully completed biological bodies move into a compact **COMPLETED BIO** section at the bottom, preserving a one-line species summary while keeping unfinished survey targets prominent.

## v5.0.6 // Theme-Aware Survey Status
**Release Date:** 2026-Jul-23

*   Survey Status now adopts the active commander theme across its accent chrome, headings, BIO/GEO states, biology details, notable-body values, separators and supporting text while retaining the same dark scanline background as the other overlays.
*   Live theme changes and profile switches immediately rebuild the visible survey from its cached state, without waiting for another journal event.

## v5.0.5 // Readable Survey Status
**Release Date:** 2026-Jul-23

*   Enlarged the newly added biological identification and **BIO/GEO** status text for easier in-game reading.
*   Preserved the Survey Status overlay's original headings, values, footer typography and compact width while adding space only where the larger signal details need it.

## v5.0.4 // Geological Survey Signals
**Release Date:** 2026-Jul-23

*   Survey Status now retains and displays mapped geological signal counts as **GEO N**, including geo-only bodies that previously disappeared after DSS mapping.
*   Mixed biological and geological planets show a combined status while preserving identified biology, completion state, estimated value and notable-body context.

## v5.0.3 // Identified Biology Survey
**Release Date:** 2026-Jul-23

*   Survey Status now expands mapped planet rows with every journal-identified biological genus, then upgrades each entry to its sampled species, localized variant and completion state as organic scans arrive.
*   Preserved DSS genus and geological results across Elite's post-mapping Detailed Scan event, so identified biology remains visible in the overlay and profile-local scan cache instead of being immediately replaced.

## v5.0.2 // Adaptive Mode Navigation
**Release Date:** 2026-Jul-20

*   Fixed Adaptive Command Deck mode navigation so Explore, Mining, Combat, Trade, Ground, Engineering, Carrier, Colony and Powerplay open their intended workspace or exact Specialist section.
*   Replaced the ambiguous **Open Mode** control with a live destination label. General and Station modes now open the next actionable task, or clearly show **Dashboard Active** when there is nowhere else to navigate.

## v5.0.1 // About & Release Awareness
**Release Date:** 2026-Jul-20

*   Added a themed **About** workspace beneath Engineer with project, release, wiki, Frontier community and dedicated GitHub Issues support links.
*   Added concise in-app GPL-3.0-only, privacy and independent Frontier disclaimer summaries, plus direct access to redacted support bundles and diagnostic logs.
*   Repaired update checks to use the public VoidCompass GitHub Releases feed, with a manual status check and direct release access from About.

## v5.0.0 // Adaptive Command Deck
**Release Date:** 2026-Jul-20

*   Added an **Adaptive Command Deck** that detects Exploration, Mining, Trade, Combat, Ground, Engineering, Powerplay, Carrier, Architect and Station activity from verified journal state, with an optional profile-local manual mode lock.
*   Reworked Dashboard objectives into one priority-ranked **Operational Queue** spanning survey work, routes and waypoints, missions, mining, trade plans, engineering goals, Powerplay logistics, carriers and colony supply.
*   Added activity-focused overlay scenes that keep safety feedback available while reducing unrelated HUD clutter; scenes can be disabled without leaving overlays hidden.
*   Added deterministic Compass mode briefings, activity debriefs and a shutdown summary path without an LLM, external service or new GPU workload.
*   Added live Command Health telemetry for UI backlog, persistence backlog and recent stalls, surfaced on Dashboard and in Settings.
*   Moved high-churn Compass memory, working brain, companion state, achievements, specialist state, Captain's Log and runtime trace writes onto one coalescing background persistence queue.
*   Routed journal, Status, cargo, market, carrier and network callbacks through one bounded Tk dispatcher to protect frame time during event bursts.
*   Made application and profile shutdown cancel active Piper synthesis/playback and discard queued speech immediately; final AI state now uses one bounded durability window instead of waiting for voice work or several sequential flushes.
*   Added profile-aware unclean-shutdown detection and safe cached-state recovery while journal catch-up completes.
*   Added a themed first-run setup for journal location, overlays, mouse passthrough, Adaptive Command and voice. It is the only visible window and completes before profile state, voice, overlays or journal catch-up start; Settings retains an in-app rerun action.
*   Added one-click privacy-redacted support bundles containing health data, sanitized diagnostics and journal event names/timestamps—but no raw journal payloads, commander identity or credentials.

## v4.9.2 // Specialist Operations Console
**Release Date:** 2026-Jul-20

*   Added a profile-local **Specialists** with dedicated Mining, Combat/AX, Carrier and Exobiology sections driven directly by Frontier journal and Status data.
*   Consolidated Mining into Specialists as the single authoritative workflow. Existing Mining shortcuts now open it directly, while the duplicate navigation page has been retired.
*   Added replay-safe mining runs with manual or automatic starts, prospector quality, refinery and cargo yield, core cracks, limpet inventory and observed costs, attributable sales, performance rates and durable history.
*   Added Combat/AX loadout readiness, observed ammunition, session kills, claims, damage, synthesis and AX encounter history without claiming telemetry that Elite does not journal.
*   Added Carrier upkeep runway, explicit inventory, market-order exposure and per-leg tritium planning alongside the existing full Carrier Command workspace.
*   Added Exobiology sampling records, body-local pins, history and GeoJSON export, with selected coordinates handed to the existing Ground tool instead of duplicating surface navigation.
*   Specialist state is isolated per commander, journal-offset deduplicated and protected against assigning historical startup samples to the current live surface position.
*   Promoted Analytics to a root command workspace with live session-rate tiles, selectable performance periods, interactive balance and daily-profit graphs, hover detail and top commodity rankings; Trade now keeps its focused market watchlist instead of hiding Analytics inside a subtab.
*   Removed redundant commander-name badges from root workspace headers; the global commander strip remains the single active-profile identity, while Commander Record keeps identity where it is part of the actual profile content.
*   Licensed Void Compass under GNU GPL v3.0 only and added the complete licence to both the source repository and packaged public releases.
*   Added project-specific community standards: contributor and conduct guidance, private vulnerability reporting, structured bug and feature forms, and a pull-request checklist.

## v4.9.1 // Engineering Materials Command
**Release Date:** 2026-Jul-18

*   Transformed Engineer into a goal-driven **Engineering Command** with Command, Wishlist, Inventory, Engineers and Odyssey workspaces based on the strongest workflows from dedicated Elite Dangerous material helpers.
*   Combined raw, manufactured and encoded stock into one searchable inventory that marks wishlist shortages, protected ingredients, spare trader stock and near-capacity materials, with practical collection or scan guidance for each family.
*   Upgraded the shared ship-engineering wishlist with collection priorities, non-doubled requirements, per-goal readiness, trader alternatives and direct routing to nearby material traders and engineer systems.
*   Rebuilt the Engineers workspace as a fast master-detail roster with live access and rank state, exact unlock paths, grade-aware blueprint availability, material readiness, direct route plotting and one-click wishlist goals.
*   Added persistent per-commander Odyssey suit and weapon modification goals, combined ShipLocker shopping requirements, notable-item guidance and Horizons/Odyssey engineer filtering without introducing an external service or ship-build planner.
*   Completed an app-wide native theme audit: formerly pale ttk controls, notebooks, scrollbars, progress bars, combobox dropdowns and legacy panel surfaces now follow the active commander profile palette, including live theme changes, while gameplay overlays keep their dedicated HUD treatment.

## v4.8.7 // In-Game Overlay Input Safety
**Release Date:** 2026-Jul-17

*   Native HUDs and overlays now pass mouse input through to Elite Dangerous by default, preventing an overlay under the pointer from intercepting flight or camera controls.
*   Added a profile-aware **Mouse passthrough** setting under Overlays. Turn it off temporarily to drag or click overlays, then turn it back on for gameplay; the change applies immediately without restarting VoidCompass.
*   Resized windows now retain access to every workspace through persistent VoidCompass-themed scrolling. Mouse-wheel routing respects nested tables, text views and specialist panels, and every Settings section now has its own themed scrolling surface.
*   Commander Profile ship identity now follows purchases, new-ship assignment, shipyard swaps, full loadouts and ship renames immediately. Empty names no longer retain the previous vessel's name, and SRV naming events cannot replace the active mothership.
*   Explore and Route now share one **Exploration & Routes** workspace. Survey telemetry, the full route overview, waypoint manager, neutron plotter, route-value intelligence and expedition chronicle remain grouped by workflow, while the duplicate Route navigation entry has been removed.

## v4.8.6 // Compass Judgment & Profile-State Reliability
**Release Date:** 2026-Jul-16

### More Deliberate Compass Awareness
*   Added an activity-mode layer for exploration, mining, trade, combat, ground, engineering, Powerplay, carrier, colonisation and station work. Relevant observations receive priority while unrelated commentary is held back; safety warnings remain authoritative.
*   Added source age and confidence to Compass working facts. Advice tied to stale journal, Status, navigation, cargo or EDSM evidence is downgraded, and contradictory state is exposed to the local brain instead of treated as certain.
*   Reconciled intentions after each journal event and cargo refresh. Completed or expired missions, departed biological work, cleared routes, delivered cargo and trade plans older than six hours no longer remain as active objectives.
*   Added a selective `ReceiveText` path for actionable NPC/game communications such as denied docking, mission redirection, distress and security warnings. Routine NPC chatter and all player chat remain silent.
*   Compass now learns recurring preparation gaps once per session and can surface lightweight pre-flight checks after repeated low-limpet mining runs or under-supplied ground deployments.
*   Corrected route-fuel advice to distinguish unknown star data from confirmed non-scoopable arrival primaries, avoid overstating whole-system fuel availability, and stay quiet when current endurance already covers a short dry stretch.
*   Exploration and biological sales now dismiss obsolete data-risk toasts and queued speech, clear pending biology-sale reminders, and silently rebase any genuinely unsold category instead of announcing a fresh warning during the transaction.
*   Commander credits now update immediately across commodity, data, biology, outfitting, shipyard, service, Odyssey and carrier-bank transactions, with refuelling charged from its credit cost rather than its fuel-tonnage field.

### Correct Commander Flight State
*   Navigation HUD state now follows the incoming commander's `Location` and live `Status.json` evidence, including docked, landed, SRV, on-foot, supercruise and normal-flight states.
*   Profile changes cancel delayed HUD callbacks from the outgoing commander and reload the new profile's station and vehicle context without retaining a stale state label.
*   Restarting VoidCompass now paints the active commander's last graceful-shutdown cockpit state immediately while the journal tail catches up silently, then replaces it with one settled live state without replaying historical discoveries into the Live Feed.

## v4.8.5 // Commander Profile Isolation Audit
**Release Date:** 2026-Jul-16

*   Isolated themes, custom palettes, databases, companion state, routes, cargo, overlays, tools and background workers per commander profile.
*   Added a hard runtime boundary on commander changes, followed by forced NavRoute, Status, Cargo, Market and ShipLocker refreshes.

## v4.8.4 // Squadron, Mining & Operational Compass
**Release Date:** 2026-Jul-16

*   Added Galaxy's Squadron Command workspace with journal-backed membership, activity, trophies, BGS objectives and Squadron Carrier context.
*   Rebuilt Mining Command around live overview, prospecting, cargo/contracts, hotspots and history workflows.
*   Deepened Compass mining, trade, PvE and Powerplay awareness with bounded learning, personal baselines and sparse actionable advice.
*   Rebuilt the main README and screenshots around the current command workspaces and local Compass architecture.

## v4.8.3 // Command Workspaces
**Release Date:** 2026-Jul-16

*   Rebuilt Profile as Commander Record, Route as Route Command, and Engineer as Engineering Workshop with focused native workspaces and deferred hidden-page redraws.
*   Added distinct live NavRoute and expedition-waypoint lanes, the manual Neutron Plotter, safer waypoint persistence and a combined engineering shopping list across 16 common blueprints.
*   Extended Carrier Command with Squadron Carrier identity, readiness, expedition and Discord support while keeping journal-unavailable details explicit.

## v4.8.2 // Operational Command Dashboard
**Release Date:** 2026-Jul-16

*   Rebuilt Dashboard as a low-noise command page with unified Flight and Compass briefings, a promoted Active Objective, contextual operations and one Activity Stream.

## v4.8.1 // Command Centres & One-Click Trade
**Release Date:** 2026-Jul-16

*   Added Architect Command, Fleet Carrier Expedition Navigator and per-commander Captain's Log workspaces.
*   Reworked Trade around One Click routes while preserving Markets, Local, Tracking and Database tools.

## v4.7.5 // Stable Startup & Overlay Positions
**Release Date:** 2026-Jul-15

*   Removed the temporary startup window and added a protected settling period plus unified coordinate persistence for every native HUD and overlay.

## v4.7.4 // Compass Cognitive Engine
**Release Date:** 2026-Jul-14

*   Added the bounded Python-only Compass Cognitive Engine with utility scoring, outcome learning, pilot predictions, anomaly detection, contextual memories, goals and intentional silence.
*   Evolved all 15 personas into behavioural policies with transparent cognitive state and learned usefulness.

## v4.7.3 // Lightweight Deterministic Compass
**Release Date:** 2026-Jul-14

*   Removed Ollama and its GPU/server lifecycle while preserving personas, learned habits, Piper speech, the situational adviser, Live Feed and AI heartbeat integration.

## v4.7.2 // Living Compass Personas
**Release Date:** 2026-Jul-14

*   Added 15 per-commander personas with distinct tone, priorities and initiative, plus preview controls and accurate language-layer status reporting.

## v4.7.1 // Local Generative Compass Language
**Release Date:** 2026-Jul-14

*   Added the guarded experimental Ollama language layer, working-brain context, prewarming and validation/fallback controls; removed in v4.7.3 after real-game performance testing.
*   Added automatic voice-cache pruning and corrected final FSS completion refreshes in Survey Status.

## v4.6.6 // Navigation HUD Refinements
**Release Date:** 2026-Jul-13

*   Added theme-driven informational badges, improved CRT badge states and moved Traffic into the compact badge row.

## v4.6.5 // Accurate Exobiology Tracking + HUD Polish
**Release Date:** 2026-Jul-13

*   Corrected biological progress to follow real `ScanOrganic` sequences and simplified the Navigation HUD's live BIO state.

## v4.6.4 // Living Cockpit Companion
**Release Date:** 2026-Jul-13

*   Added earned system opinions, backtrack impatience, bio-sale anticipation, quiet-cruise chatter, time-aware greetings and specific memory callbacks.

## v4.6.2 // Bio-Aware Compass Intelligence
**Release Date:** 2026-Jul-13

*   Joined journal and Survey Status evidence into a bounded Compass biology model covering signals, genera, sampling, rewards, colony spacing and Codex discoveries.

## v4.6.1 // Traffic-Aware Compass Intelligence
**Release Date:** 2026-Jul-13

*   Added EDSM traffic awareness, valuable-world callouts, live route/waypoint progress and persistent Survey Status notable bodies.

## Earlier releases

*   **v4.5.9** — AI feed and heartbeat, broad operational awareness, session lifecycle, persistent notable bodies and instant Survey Status hide on jump.
*   **v4.5.7** — Eighteen optional Piper voices, low-noise callouts, bounded Compass Memory, survey improvements and configurable Navigation HUD CRT effects.
*   **v4.4.4** — Interactive Galaxy drill-downs for systems, factions, Powerplay, squadron, conflicts and Community Goals.
*   **v4.4.3** — Simplified five-area Trade workspace with live EDDN/journal market maintenance and freshness tracking.
*   **v4.4.2** — Galaxy Overview influence tracking, faction watches and BGS History integration.
*   **v4.4.1** — Expanded Engineering, Galaxy/BGS and Commander Companion fleet, mission, jumponium and rebuy tools.
*   **v4.3.4** — Monotonic achievement progress plus route, playtime and progress-bar fixes.
*   **v4.3.2** — Native 1,023-entry journal-driven Achievement Centre with migration and journal-history rebuild.
