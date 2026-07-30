# VoidCompass // UPDATE LOG

## v5.3.3 // Species-Level Biology Prediction
**Release Date:** 2026-Jul-30

*   The Navigation HUD now shows the current Codex region beside the system it belongs to, in both the normal and compact layouts, using the empty middle of the CURRENT SYSTEM row so no existing reading is displaced. Crossing into a new region lifts the text to the accent colour for a short spell, marking a rare event without spending a badge slot on it.
*   Galactic Atlas region names are no longer hover or click targets. Their anchors sit at region centroids, which in populated space is exactly where marker density is highest, so a label could win a click intended for a system, cluster or annotation. Region names still draw as before, and searching for a region still selects it and holds its label on screen.
*   Added published **species-level spawn requirements** for 116 organic species across all 20 Codex genus identifiers, covering body type, atmosphere, gravity, temperature, pressure and volcanism. Biological prediction previously worked at genus level from a small hand-maintained ruleset, so it could say *Bacterium* but never *Bacterium Aurasus*.
*   Biological signals on **airless bodies are now predicted at all**. The previous rules returned nothing unless a body had a thin atmosphere, which silently excluded Anemone, Brain Trees, Sinuous Tubers and Crystalline Shards — four families that only occur on bodies without one.
*   Predictions now state whether every published requirement could actually be tested. Galactic region, star luminosity, Guardian and nebula proximity and parent-body composition cannot be judged from a body scan, so a species relying on them is reported as possible rather than confirmed instead of being quietly assumed to qualify.
*   Surface pressure is retained from body scans, since 126 of the published rulesets are bounded by it, and minimum gravity is now enforced — 230 rulesets specify one and the previous rules modelled no lower bound whatsoever, which over-predicted Bacterium on bodies that cannot host it.
*   The coarser genus rules remain, but only for scans too incomplete to judge. A body that was tested against the published requirements and matched nothing is now a factual answer rather than an invitation to guess.
*   Biological prediction now uses the commander's own galactic position. Several published requirements are bounded by Codex region, or by distance to a Guardian nebula or Sinuous Tuber zone, and the region groups are expressed in the same 1-42 region identifiers the Galactic Atlas already draws — so the existing offline region map decides them with no further lookup. Across a sweep of locations and body types this ruled out 44% of candidate species that a body scan alone had to keep, and removed region, Guardian and Tuber uncertainty entirely.
*   Brain Trees are now confined to the six galactic regions the published data restricts them to — Empyrean Straits, Inner Scutum-Centaurus Arm, Norma Expanse, Temple, Inner Orion Spur and Outer Orion Spur — instead of being offered anywhere in the galaxy. The upstream data expresses that restriction under a differently spelled key which its own evaluator has no branch for, so the restriction was never being applied; VoidCompass honours it.
*   Survey Status now names the species behind a prediction rather than only its genus, and separates a **PREDICTED** candidate whose every published requirement was tested from a **POSSIBLE** one that depends on something a body scan cannot check. System mode continues to show no predictions at all, so they can never be mistaken for completed DSS results.
*   Estimated survey value for unidentified biological signals now spans only the species that actually fit the body instead of everything its genus can contain. On a cold carbon-dioxide rocky world with two signals the estimate narrowed from 2.0–16.8 million to 2.0–3.3 million credits; where several genuinely different-value species do fit, the range stays wide rather than pretending to precision.
*   System Survey body rows mark a genus as uncertain when every candidate species behind it rests on an untested requirement, and expedition reports list the candidate species with their values and exactly which requirements could not be verified.

## Earlier releases

*   **v5.3.2** — Added searchable commander-profile map annotations with direct edit/delete, zoom-aware marker clustering with expanding count badges, and restrained live-navigation cues that respect Reduced Motion.
*   **v5.3.1** — Replaced the orbiting 3D galaxy with a top-down Galactic Atlas built on original artwork and the full 42-region layout, adding system/region search, framing presets, saved camera state and corrected runtime image packaging.
*   **v5.2.9.7** — Made Overlay Layout Studio positions authoritative while Tk applies a move, removed the Fleet Carrier HUD height clamp and corrected negative virtual-desktop coordinates.
*   **v5.2.9.6** — Added live Fleet Carrier Tritium burn calculation between `CarrierStats` snapshots, a carrier-expedition Dashboard mode and a non-blocking Spansh Tritium hotspot finder.
*   **v5.2.9.5** — Made Fleet Carrier arrivals mark the matching expedition stop complete and unified route checkmarks, the next-stop arrow, overlay progress and Copy Next on one pending waypoint.
*   **v5.2.9.4** — Made Fleet Carrier jumps update system, dashboard, HUD, route and scan state when travelling on the concourse on foot, including during startup journal recovery.
*   **v5.2.9.3** — Fixed Studio-positioned overlays snapping back during dynamic redraws and stopped adaptive activity modes hiding enabled overlays.
*   **v5.2.9.2** — Listed every configurable overlay in Layout Studio including disabled ones, consolidated the overlay settings pages into it and replaced the GPU-conflicting default shortcuts.
*   **v5.2.9.1** — Added a themed virtual-desktop preview to Overlay Layout Studio for dragging real HUD windows, plus a global open shortcut and a dedicated Hotkeys settings page.
*   **v5.2.9** — Added route-safety forecasting, a Missed Discoveries queue, the Survey Evidence Inspector, Explorer Data Vault, Overlay Layout Studio, SQLite-safe profile backups and an app-wide responsiveness pass.
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
