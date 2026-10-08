# VoidCompass // UPDATE LOG

## v5.5.3 // Fixes from the field
**Release Date:** 2026-Oct-08

* **Codex flags now on by default, and in more places.**
  * Survey Operations' flags are switched on for every commander, once. Turn them off in Overlay Studio if you prefer.
  * A genus the game finds on a body but our prediction didn't expect now lists the species it is likely to be, with their colours and flags.
  * When the brightest star gives a species no colour (a neutron star, say), the planet's other parent stars are tried.
  * Once the species is known, a detected genus shows that species' value, not the whole genus range (a Bacterium named as Acies reads 1M, not 1–8.42M), and the body estimate follows.
* **Galnet shows each story's real date.** Stories now carry their in-game broadcast date (01 OCT 3312), read from the Galnet page. Before, every story showed the date the feed was last updated.
* **Ship loadouts import as they are in game.**
  * Empty hardpoints stay empty. Before, they showed the stock Pulse Lasers.
  * Every module goes to the slot the journal names, so medium weapons no longer land in large hardpoints and internals sit in the right size of slot.
  * Engineering comes across with each module, and the Rhino's vehicle hangar is recognised.
* **Achievements:**
  * Shock and Awe now needs three core asteroids cracked with seismic charges. Before, launching any limpet counted. Progress counted the old way is cleared once.
  * Drone Operator counts only prospector and collector limpets.
* **Jump Info appears the moment you press jump,** while the drive charges, not when the countdown ends.
* **Jump Info fits its window at any text size,** as the Navigation HUD does. If the window comes out smaller than your text size needs (Windows display scaling, say), the panel shrinks to fit rather than being cut off, and returns to full size as the window catches up.
* **Survey Operations lists Earth-likes, water worlds and other high-value bodies right after biology,** the most valuable first, and they are the last to page out when space is short.
* **Explore & Survey:**
  * Unsold **exobiology** has its own readout beside cartography, with the samples aboard and any first-footfall bonus.
  * Each body says who discovered it (from EDSM), or that it was undiscovered and the discovery is yours.
  * Bodies carry their Codex flag, and the system's EDSM traffic shows in the survey band.
* **Navigation HUD hologram: Full, Still or Off** (Overlay Studio). **Still** is for low-end PCs: the hologram plays its change animation when the state changes, then holds that state's settled scene and draws nothing until the next change. **Off** shows the readouts only. Alerts still flash in every mode.
* **Cargo** is listed in alphabetical order.
* **Exobiology bonuses are counted.** On a first-footfall body every species pays five times its base value (your journals: 228 of 228 such samples were paid it). Survey Operations shows those values with a **1ST FOOTFALL ×5** badge, and the unsold exobiology on the dashboard, Explore, Flight Log and the Station overlay now includes it. Exploration values already included the first-discovery and first-mapped bonuses.
* **The Watcher has a life of its own between events:**
  * It blinks, breathes and glances around, and looks the way each event points: up for jumps, sweeping for scans, down for docking and landing.
  * It takes a double take at a first discovery, an Earth-like or water world, or a new Codex entry.
  * It side-eyes danger, squints into the star while you scoop, and tires over a long session.
  * Overlay Studio adds **Liveliness** (Calm, Standard or Alive) and an **Idle motions** switch.

## Earlier releases

* **v5.5.2.9** — Survey Operations' Codex flags per colour, like SrvSurvey's: each species with the colours it will show and a flag on each colour you lack.
* **v5.5.2.8** — Commander Record covers Odyssey on foot: suit and loadout with real grades, on-foot record, exobiology career, backpack and ship locker; the ship locker no longer overwrites the backpack.
* **v5.5.2.7** — Overlays grow with the text size in both directions, overlays show up to date when they appear (Survey's first planet after a jump), and the Navigation HUD always fits its window.
* **v5.5.2.6** — New Trading tab with Spansh routes, loop routes, selling your cargo, finding any commodity, station markets and your profit history with charts; and the Trade Route overlay.
* **v5.5.2.5** — Install updates from inside Void Compass: downloaded and checked from GitHub, swapped in on a restart, with your settings and profiles kept and the old version put back if anything goes wrong.
* **v5.5.2.4.1** — Surface gravity fixed for worlds under about 0.5 G (shown ten times too heavy, which also skewed species predictions and set off false gravity warnings); BGS Refresh from EDSM gets fresh data; conflicts listed newest first.
* **v5.5.2.4** — New BGS tab: every faction in every system you visit, tracking and alerts, conflicts, any system looked up on EDSM, influence charts, your work per tick with a Discord report, and a guide to the states.
* **v5.5.2.3** — Deep Space Contact Scope rebuilt from the journal alone: signals named by type, nothing missed on arrival, honk counts, expiring unidentified signals, and busy systems kept readable.
* **v5.5.2.2** — Commanders renamed in game keep their profile and history under the new name.
* **v5.5.2.1** — Colonisation's System Planner with Raven Colonial's own model, a station identifier, uploading your scans, Where to Buy, project stats, assignments, fleet carrier tools, Nexus plans, Raven stats and new Construction Needs options.
* **v5.5.2** — New Colonisation tab with Raven Colonial: projects, the site you are docked at, fleet carriers, system sites and your journal's construction record; the Construction Needs overlay; and Raven Colonial in Settings > Integrations.
* **v5.5.1.9** — Fixed grey blocks at the corners of most overlays, and between stacked notifications, when overlay opacity was below 100%.
* **v5.5.1.8** — Jump Info redesigned to match the Navigation HUD (and its body counts removed), its corner blocks fixed, and overlay opacity and frame rate now applied straight after a restart.
* **v5.5.1.7** — Overlay opacity now fades each overlay window through Windows itself, so it works on every graphics card.
* **v5.5.1.6** — Overlay switches in the command deck header, Codex flags for Survey Operations, and a fix for finished system surveys showing one body still to go.
* **v5.5.1.5** — Jump Info overlay, overlays hide on the maps (each can opt out), Overlay Studio layout mode, who discovered the system on the Navigation HUD, and switches for the surface and mapped signal notifications.
* **v5.5.1.4** — Fixed Overlay Studio merging every monitor into one wide display, and the command deck reopening in the wrong place on monitors with different Windows scaling.
* **v5.5.1.3** — Text size, smallest text and overlay text size in Settings > Appearance, a working Command deck scale, overlays sized for Windows display scaling, survey overlay fixes, an overlay frame-rate setting, and new installs picking up the commander and their whole history.
* **v5.5.1.2** — OBS can capture each cockpit overlay on its own with Window Capture ("Windows 10 (1903 and up)" method), while the overlays stay off the taskbar and out of Alt-Tab.
* **v5.5.1.1** — Rebuilt the first-time setup into four steps (Welcome, Journal link, Cockpit, Launch), with a live check of the journal folder that shows your journals, commander, ship and last system, and a theme picker that previews each theme as you click it.
* **v5.4.9.9** — Rebuilt the Ship Workshop: a Build Planner with a hangar of builds, a hull drawing that lights the slot you fit, the distributor's pips, a loadout board, a module dock and every performance figure at once; and Engineering with your fleet, what is engineered on each ship, the material locker, the engineers and a new blueprint reference.
* **v5.4.9.8** — Added Music, a local player with playlists, loudness levelling, OBS capture and a Music Player overlay; rebuilt the Galactic Atlas as a regions map of your whole journey and Powerplay Operations around the weekly cycle; and fixed the command deck going blank or dropping its page in long sessions.
* **v5.4.9.7** — Rebuilt Settings as one screen that saves as you go, added the Galnet Ticker overlay with CRT and glitch effects, rebuilt the Navigation HUD's state scenes as solid 3D holograms with stars shaped by their class, switched the Rhino coverage map off, and fixed overlays sometimes not appearing at startup.
* **v5.4.9.6** — Rebuilt the Journal Heartbeat as a HAL 9000-style watcher orb that reacts to every journal event, rebuilt the startup screen around the same eye with an FSD countdown into the deck, added Navigation HUD typeface and text settings, and fixed the HUD's on-foot portrait.
* **v5.4.9.5** — Brought back an animated hologram for every Navigation HUD state with journal event effects, rebuilt Gravity Warning and Overlay Studio (one display at a time), made Survey Operations hold still at or below its rotation threshold, and fixed hidden overlays reloading after five minutes.
* **v5.4.9.4** — Rebuilt Survey Operations around one spotlight world on a single clock, split Explore & Survey into three views with a unified Survey Board, rebuilt the Navigation HUD as a cockpit status panel and Planet Waypoint Navigation as a surface compass, and fixed startup stalling when the dashboard was minimised.
* **v5.4.9.3** — Added the profile-local Return Later board and per-commander survey queue choices, kept every discovered body reachable in the Explore workboard, rebuilt Exploration Archive as a flight-record workspace and reworked Focused Log into a live field brief.
* **v5.4.9.2** — Rebuilt Planet Materials and Planet Waypoint Navigation, introduced the Expedition Bridge across non-map pages, and added animated known-world records to Current System.
* **v5.4.9.1** — Refreshed Survey Operations for every planet scan with compact routine and pinned biology strips, improved exobiology sampling, and rebuilt Achievements and themed cockpit notifications.
* **v5.4.9** — Rebuilt the Navigation HUD with a flight-deck layout, complete animated route, stellar-class visuals and distinct state scenes; redesigned Survey Operations as a bounded, animated planet atlas.
* **v5.4.8.4** — Improved Navigation route and fuel guidance, redesigned startup with an optical core, starfield and rotating Elite facts, and added prompt retry for failed overlay pages.
* **v5.4.8.3** — Rebuilt the theme-aware HAL-inspired heartbeat optics, refreshed the Navigation route rail, and disabled the Rhino Coverage overlay while retaining saved maps and underlying tools.
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
