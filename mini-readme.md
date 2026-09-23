# VoidCompass // UPDATE LOG

## v5.4.9.1 // Field Signals
**Release Date:** 2026-Sep-24

* Survey Operations now refreshes for each planet Scan even after FSS has already found the full system. Other scanned planets stay in a compact, independently cycling strip above the atlas, while biology, geology, landable and mining worlds retain detailed cards; the existing option can expand routine cards.
* Scan-confirmed biological planets stay in a pinned mini-atlas above Survey Operations' rotating pages. Crowded systems cycle the pinboard independently in bounded batches while the detailed cards remain available below.
* Reworked the three-step exobiology sampler with captured/next/ready states, live distance remaining, travelled-versus-required spacing and an honest analysis-pending state after the third sample.
* Removed the duplicate clear-to-sample notification and its obsolete toggle. The live spacing guidance stays in Survey Operations.
* Rebuilt Achievements as a commander record with a completion dial, next-milestone spotlight, latest unlock and a searchable, filterable, paged archive. Tracking, unlock notices and manual controls remain available.
* Rebuilt cockpit notifications as severity-coded signal cards and achievement unlocks as distinct milestone cards, preserving category, points and expiry with readable scaling and reduced-motion support. Their accents now follow the active commander profile; warning and reward colours retain their meaning.

## Earlier releases

### v5.4.9 // Flight-Deck Navigation
**Release Date:** 2026-Sep-23

* Rebuilt the Navigation HUD as a flight-deck instrument with a clearer current-system readout, prominent next-system vector, compact jump/distance telemetry and glass-panel survey and metric banks.
* Redesigned the full-route flight tape with a soft scanner sweep, distinct current and next markers, unscoopable-star colouring, and event-driven route-update and arrival confirmations. Every waypoint remains represented, including long routes.
* Added class-coloured stellar illustrations for the known current and next arrival stars, plus spectral-class markers for each live route hop. White dwarfs, neutron stars and black holes have distinct treatments; unknown classes keep a neutral marker instead of a guessed star.
* Linked route motion to charging and jumps while keeping routine telemetry refreshes calm. Both the app's reduced-motion setting and the OS preference stop HUD motion.
* Refreshed the state instrument and completed the right-hand state scenes: travel, scan and map modes, planetary phases, vehicles, targeting, docking outcomes, carrier phases and hazards now have distinct geometry rather than shared fallback drawings. Live ship imagery, journal-event responses and reduced-motion support remain intact.
* Kept the existing fuel-estimate cautions and journal-backed survey data.
* Rebuilt Survey Operations as a title-free field atlas with journal-classed, code-drawn planets, scan-backed atmosphere and ring details, clearer FSS/biology progress, focused surface cards, and a refreshed sampling track. Signal-only bodies retain neutral unknown planets until scanned.
* Added rotating planet surfaces beneath fixed lighting and a bounded atlas for crowded systems. Smaller planet discs and a persistent miniature roster keep every included body visible at once, while full planet cards and biological details cycle below. Removed the 60-body current-system scan-cache limit; the existing All surveyed bodies option includes non-priority scans. Reduced motion keeps the data accessible without visual effects.

### v5.4.8.4 // Navigation Clarity
**Release Date:** 2026-Sep-23

* Strengthened the next-system readout with star class, scoopability and explicit jump/stop progress beside the complete route rail.
* Added route-update, route-clear and arrival feedback with smooth next-target promotion; routine distance updates do not retrigger notifications.
* Added labelled fuel-endurance estimates from recent fuel use, low-endurance caution and an explicit unknown state. These are not exact next-jump fuel or range calculations.
* Surface operations emphasise the context rail without rearranging the HUD. Both layouts reserve a small status row and retain reduced-motion support.
* Redesigned startup around a luminous optical core, real-progress orbital ring and horizontal stage sequence, with compact layouts and reduced-motion support. Once the app is ready, the screen remains for five seconds so the lens and facts can be seen.
* Added a local starfield inspired by the Twitch overlay: layered drifting stars, a galactic band, subtle twinkle and theme-tinted nebula haze. Animation stops after handoff; reduced motion keeps a static sky.
* The boot lens now acts as a silent exploration companion with animated chat bubbles and a shuffled offline Elite fact deck. The editable deck avoids repeats until all entries have appeared.
* Random decorative lens activity adds focus shifts, theme-coloured pulses and expanding rings between facts, without generating journal events or changing progress. It pauses when hidden or reduced motion is enabled and stops at handoff. Now with random elite facst!
* A failed overlay WebView navigation now gets a prompt, bounded page retry. The existing watchdog remains as fallback if the page still cannot render.

### v5.4.8.3 // Living Optics
**Release Date:** 2026-Sep-22

* Replaced the heartbeat eye with HAL-inspired camera optics: a luminous core, counter-rotating lens rings, drifting focus and moving glass reflections, with continuous idle animation and smooth journal-event pulses.
* Lens colours follow the active profile theme and blend between activity states; stalled-feed and reduced-motion behaviour are preserved.
* Replaced the angular heartbeat frame with counter-rotating orbital arcs, an orbiting beacon and breathing index marks. Quiet-feed periods retain a bright theme-coloured lens, with a separate red warning dot instead of dimming the entire eye.
* Refreshed the Navigation HUD route rail with distinct current/next markers and an animated next leg. Every waypoint retains its own evenly spaced marker, including long routes; routine distance updates no longer rebuild the markers.
* Disabled the Rhino Coverage overlay, including for existing profiles, and removed its Settings hotkey bindings. Saved maps and the underlying coverage tools are retained. since we are waiting for journal events, there's a better tool out in the wild that does the overlay 100% better than I could ever do ( https://github.com/Fumlop/EDRhinoSpotter is the better tool for this )

* **v5.4.8.2** — Redesigned the heartbeat, added quick planetary compass coordinates and stabilised overlay startup/recovery with offscreen loading, browser error suppression and reliable readiness handshakes.
* **v5.4.8.1** — Restored Overlay Studio as a standalone Application destination and stabilised overlay startup with staged WebView loading, rendered-page acknowledgements and isolated page recovery.
* **v5.4.8** — Consolidated the command deck into workflow-focused destinations and shared suites, retained compatibility routes, and added an in-app GitHub release notification with matching release notes and links.
* **v5.4.7** — Added Exploration Scout with journal-backed system audits, Codex coverage gaps and commander-requested Spansh prospect searches; split the largest dashboard domains and centralised live journal and companion-file distribution.
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
