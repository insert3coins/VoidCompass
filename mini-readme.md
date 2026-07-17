# VoidCompass // UPDATE LOG

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
