# VoidCompass // UPDATE LOG

## v5.4.2.4 // Navigation in Motion
**Release Date:** 2026-Sep-06

*   Rebuilt the Navigation HUD animation catalogue as Elite-inspired holographic instruments: bowed supercruise wakes, local-drive coils, a hypercharge aperture, a faceted witch-space tunnel, settling arrival acquisition and cooling fins. Kept the smooth state transitions, readable centre labels and journal/Status-driven state selection.
*   Added distinct FSS spectra, DSS probe arcs, galaxy/system/orrery displays, planetary glide corridors and ascent/descent instruments, docking pads, station/carrier silhouettes, cockpit panels and hazard signatures. Replaced the old repeated scene drawings rather than layering more effects over them.
*   Gave Rhino, Scarab, Scorpion, Nomad, fighter and on-foot states their own holographic geometry, with smoothed planetary altitude/gravity response and ship-side accents. Arrival and vehicle boarding/departure settle after a single pass instead of endlessly repeating the manoeuvre.
*   Corrected static or barely visible idle effects across station, docked, landed, hold, handbrake, target, carrier and cockpit-panel states. Added visible housing/entrance lighting, stabiliser sweeps and confirmation circuits that keep settled states animated without moving parked vehicles or replaying handoffs.
*   Improved 30 FPS pacing, removed fractional-speed loop snapbacks across indicator states, smoothed telemetry changes and interrupted transitions, and paused hidden canvas rendering while retaining live updates. Preserved themes, ship artwork and reduced-motion support.
*   Reworked the Asteroid Field indicator into layered, shaded low-poly rocks with slow tumbling, depth-dependent drift and subtle debris around the ship. Stable geometry and faded crossings avoid loop jumps while preserving the readable state label and existing journal detection.
*   Corrected the Planet Waypoint compass helper window to use the same invisible, taskbar-hidden setup as the other HTML overlays.
*   Raised Fleet/Squadron Carrier overlay labels and values to the Navigation HUD's readable font sizes, with wrapping route details and roomier logistics metrics to avoid clipping.
*   Replaced the single overwritten carrier record with profile-aware personal and Squadron Carrier records keyed by journal CarrierID. Each carrier now retains its own location, fuel, cargo capacity, jump state, expedition route, notes and Discord transitions, with a clear Carrier Command selector and gap-free card layout.
*   Removed the Carrier overlay's misleading `NEXT JUMP / READY TO PLOT JUMP` block when the selected carrier has no plotted jump, destination note or pending expedition stop.

## Earlier releases

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
