# VoidCompass // UPDATE LOG

## v5.4.7 // Exploration Scout
**Release Date:** 2026-Sep-15

* Added Exploration Scout to Explore & Survey, combining a live journal-backed current-system audit with personal regional Codex coverage gaps.
* Added on-demand searches for known nearby biological signals, Guardian sites, Thargoid sites and high-value mapping prospects using Spansh community catalogue and route data.
* Added ranked prospect briefings with distance, arrival distance, signal or value evidence, catalogue freshness and clear source/coverage limitations.
* Added actions to copy a prospect, open it in Spansh, add it to the profile waypoint route or create an objective on the active expedition.
* Kept all searches commander-initiated and made the distinction between local Elite journal evidence and community-reported catalogue evidence explicit.
* Centralised live journal and companion-file ingestion behind one coordinator, preserving event order while distributing the same authoritative data to dashboard features and overlays.

## Earlier releases

* **v5.4.6.2** — Updated Rhino driving-ring guidance, deposit observations and rig estimates; added location association, Coverage Maps, ground intelligence and richer Planet Materials integration.
* **v5.4.6.1** — Added the persistent Rhino Coverage Minimap with centres, borders, driving guidance, coloured bookmarks, manual drill markers, profile-local maps, configurable hotkeys and shareable PNG exports; consolidated overlay/runtime plumbing, clarified Build Planner and Engineering ownership, canonicalised NavRoute state and restored the complete tracked regression suite.
* **v5.4.6** — Added the complete offline Build Planner with current ships and modules, Engineering, EDSY/SLEF/Journal interchange, profile builds and full performance analysis; refined planner controls and repaired overlay transparency after the project restructure.
* **v5.4.5** — Reorganised the application into the `src/voidcompass` package and structured `assets`, `data`, `web`, `tests` and `tools` directories; updated imports, resource discovery, build inputs and launch compatibility.
* **v5.4.4** — Rebuilt Powerplay as a complete operations workspace with dossiers, authentic portraits, journal-driven merit and cargo history, weekly archives, profile assignments and a cockpit overlay; fixed Navigation HUD priority after in-game route recalculation.
* **v5.4.3.4** — Replaced generated Engineer and Powerplay artwork with authentic Elite Dangerous portraits, added the shared people-image library and completed all 34 Engineer and 12 current Powerplay leader portraits.
* **v5.4.3.3.1** — Fixed Rhino-to-mothership cargo transfer reconciliation without affecting fleet-carrier transfers.
* **v5.4.3.3** — Rebuilt About as a neon command-deck identity screen with creator, licence, privacy, runtime and project links.
* **v5.4.3.2** — Added the profile-aware Planet Materials cockpit overlay with live surface telemetry, Rhino state, saved sites and Overlay Studio integration.
* **v5.4.3.1** — Rebuilt Galactic Atlas with Elite-inspired cartography, a volumetric background, selection and focus controls, and refined Windows cursors; added Rhino dual-hold tracking and fixed stale Navigation cues.
* **v5.4.3** — Rebuilt Engineering as a complete HTML companion with fleet and planned builds, blueprints, materials, Engineer access, Tech Brokers, Odyssey goals and build interchange; introduced the profile-aware Powerplay workspace.
* **v5.4.2.7** — Redesigned Planet Materials saved locations, added Send to Compass, synchronized edited/deleted compass targets, hardened legacy site loading and completed Settings hotkey coverage for all 11 overlays.
* **v5.4.2.6.1** — Corrected Carrier Transit/arrival journal ordering, moved Planet Materials into its own menu tab, added live planet/coordinate/scan capture and a commander-profile mining-site database.
* **v5.4.2.6** — Replaced the Tk backend with the Python runtime and HTML/WebView2 overlays, repaired HUD startup visibility, added profile-aware planet mining sites and material choices, and introduced carrier preparation/lockdown countdowns for the carrier aboard.
* **v5.4.2.5** — Improved Navigation route hierarchy, next-system and distance labels, expanded survey/discovery rows, brief attention highlights and Survey Operations window sizing.
*   **v5.4.2.4** — Rebuilt navigation state animations with holographic instruments and a layered asteroid field, improved animation pacing, refined carrier readability, and separated personal/Squadron Carrier tracking, routes and Discord transitions.
*   **v5.4.2.3** — Added Rhino mining haul/processing accounting, Planetary Resource Intelligence, barycentre-aware Orrery records, Field Discoveries and vehicle ledgers; tightened Mining Command layout and corrected cargo-hold recovery after returning from an SRV.
*   **v5.4.2.2.1** — Corrected surface-control HUD states so handbrake, turret and drive-assist animations retain the active Rhino, Nomad, Scarab or Scorpion artwork instead of falling back to the mothership portrait.
*   **v5.4.2.2** — Made Cargo Manifest vessel-aware with the Rhino's 72-tonne hold, correct active-vehicle telemetry, profile persistence and clean hold-switch animations.
*   **v5.4.2.1** — Rebuilt the Live System Orrery as a full-width interactive Elite-inspired instrument with journal-accurate orbital architecture, known-system recovery, branch-aware scaling and lightweight profile-aware controls.
*   **v5.4.2** — Added first-class Rhino journal and vehicle-state support, planetary mining-location DSS evidence and retained survey presentation, with Rhino mining and SRV cargo flowing through the existing unified pipelines.
*   **v5.4.1.9** — Rebuilt Mining Command around one journal reducer with target directives, readiness, prospect/refinery yield, objectives, analytics, ring intelligence and buyer lookup; simplified Prospector Analysis and enforced HTML-only overlay presentation.
*   **v5.4.1.8** — Added overlay recovery, Screenshot Chronicle, Exploration Preflight and Smart Next Action; hardened first-launch overlay restoration and station/carrier vicinity state.
*   **v5.4.1.7** — Added Deep Space Contact Scope, FSD-injection and station/carrier awareness, DSS efficiency receipts, animated Cargo and Survey Operations, and profile-aware contact auto-hide.
*   **v5.4.1.6** — Expanded authoritative Navigation states, docking guidance, cockpit modifiers, repair/reboot responses and heat, suit and jet-cone hazards.
*   **v5.4.1.5** — Rebuilt the Navigation System Survey as a discovery-driven angular rail, rebuilt the HTML bootloader and Galnet intelligence reader, and hardened dashboard/overlay update recovery.
*   **v5.4.1.4** — Added the persistent Galnet Relay and in-app archive, official RSS caching and profile-aware controls; repaired complex panel arranging and clarified Navigation waypoint destination, progress and distance.
*   **v5.4.1.3** — Unified theme-aware Dashboard controls and profile panel arranging, rebuilt the System Workboard and waypoint rail, completed semantic Station, Cargo, Carrier, Prospector and Heartbeat overlays, refined vehicle handoffs and added neutron-tier flight animation.
*   **v5.4.1.2** — Added the Explorer Decision Deck, six exploration doctrines, five-jump Route Horizon, Session Pulse, Regional Codex Hunt, profile-aware briefing-card layouts and optional automatic profile safety snapshots.
*   **v5.4.1.1** — Refined Navigation arrival, planetary flight, landing gear, FSD cooldown, map/scanner and side-panel states; simplified vehicle departures and retired the redundant System Intelligence overlay.
*   **v5.4.1** — Stabilised HTML overlay transparency and profile-aware opacity across hide/show cycles, and corrected the Galactic Atlas Focus Map viewport so every WebGL and overlay layer stays clipped and aligned.
*   **v5.4.0** — Added Stellar Cartography with the live System Orrery, Exploration Survey Queue, Planetary Field Map, Expedition Replay, Explorer Science Lab and 42-region Galactic Passport; refined Navigation's vehicle and exploration states, added Survey Operations landability markers and repaired the initial Focus Map layout.
*   **v5.3.9.3** — Completed the visible HTML overlay conversion, rebuilt Overlay Studio dragging, refined Navigation flight effects, retired obsolete speech/career/Tk code, restored Planet Waypoint lifecycle and repaired HTML hotkey recording.
*   **v5.3.9.2** — Converted cockpit notifications and achievement unlocks to semantic HTML, prevented empty Survey Operations startup flashes and restored its planet-side focus lifecycle.
*   **v5.3.9.1** — Rebuilt the Navigation State Spine with a complete ship/vehicle identity catalogue, state-specific 30 FPS motion, readable biological workboards and restart-safe surface context.
