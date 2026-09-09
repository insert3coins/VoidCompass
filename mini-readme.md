# VoidCompass // UPDATE LOG

## v5.4.2.6.1 // Carrier Arrival & Planet Materials Patch
**Release Date:** 2026-Sep-09

* Fixed carrier travel returning to Docked during the jump tunnel. CarrierLocation now keeps Navigation in Carrier Transit; CarrierJump confirms arrival, which remains visible for 12 seconds before the normal onboard state resumes.
* Moved Planet Materials into its own main-menu tab directly below Explore & Survey.
* Planet awareness now reads the current body from live Status updates. Use current captures the system, planet, latitude (Y), longitude (X), known planet conditions and scanned raw-material percentages, including zero and negative coordinates.
* Live coordinates continue updating while editing. Capture is disabled when planetary coordinates are unavailable; mining materials and observed deposit density remain manually entered.
* Redesigned Planet Materials around one canonical planet selector, an explicit saved-location count, individual expandable site cards, planet conditions and known raw composition. Case, spacing and short/full body-name variants now resolve to the same planet, and site-list refreshes preserve unfinished form edits. Heat Map and By Material remain available across recorded observations; the heat map counts saved sites and does not predict mining probabilities.
* Saved sites retain their captured scan details and density in the commander-profile database. Existing databases migrate automatically without losing sites; mismatched planet snapshots are rejected.
* Updated documentation and verified the patch with 153 Python tests, browser checks for site editing and live capture, and a Tk-free startup/journal/profile-switch smoke check.

## Earlier releases

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
