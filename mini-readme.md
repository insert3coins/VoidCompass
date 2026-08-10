# VoidCompass // UPDATE LOG

## v5.3.7 // Explorer's Briefing
**Release Date:** 2026-Aug-11

*   Rebuilt the **Dashboard** as one exploration briefing centred on Current Survey, a truthful Next Leg, three ranked Next Actions, Expedition Pulse, Discovery Summary and the curated Flight Log.
*   Unified live game routes, saved waypoint plans and direct navigation targets behind the same Dashboard route model, removing contradictory “no route” and jumps-remaining states and avoiding unnecessary Dashboard-only EDSM waypoint lookups.
*   Added responsive briefing-card reflow for narrower windows, reduced the adaptive context strip to useful status, kept detailed UI/I/O counts in Command Health and moved journal cache rebuilding to **Settings → Diagnostics**.
*   Expanded **Mission Control** to thirteen selectable expedition templates, adding six deep multi-session campaigns for long-range cartography, exobiology, sector mapping, regional science, Outer Rim discovery and galactic circumnavigation; larger templates extend matching goals without losing verified progress.
*   Refined the **Station Link overlay** into a docked dossier with clearer station identity, arrival/pad/support instruments, separated core and explorer services, data-sale readiness and a quieter local profile, with a matching Layout Studio footprint.
*   Corrected Station Link lifecycle recovery after batched Docked or login Location events, including startup catch-up and Carrier-jump refreshes, without reopening an auto-hidden card or restarting its timer for unrelated journal activity.
*   Added a themed keyboard **hotkey recorder** to Settings with per-action Record and Clear controls, live canonical chord capture, conflict feedback and retained manual editing and profile-aware persistence; existing Void Compass shortcuts pause while the recorder is listening and resume safely when it closes.
*   Refined the Navigation HUD centre-state display into a single theme-aware data row: balanced route and known-system-survey tracers now combine with distinct restrained signatures for flight, supercruise, jumps, docking, landing, on-foot travel, SRV/Nomad driving, scanners, maps and combat in both normal and compact layouts, with seamless independent animation cycles plus reduced-motion and hidden-overlay safeguards; retired the unrelated far-right title pip so the new instrument can use the full remaining header width.

## Earlier releases

*   **v5.3.6** — Refocused Void Compass around exploration and mining, consolidated the application shell and Expedition workspace, retired cockpit speech and unrelated career surfaces, added Deep Survey field intelligence and refined the System Intelligence overlay.
*   **v5.3.5.6** — Refined both Navigation HUD layouts with clearer cockpit hierarchy, live fuel integrity, larger telemetry, a segmented survey track and a quiet context footer that appears only for meaningful information.
*   **v5.3.5.5** — Refocused Void Compass by retiring Trade Assist and its market database while retaining independent visited-market EDDN uploads, exploration Analytics, belt-cluster EDSM uploads, fleet synchronisation and the first live-fuel Navigation HUD readout.
*   **v5.3.5.3** — Restored the readable classic Navigation HUD with real route pips, permanent survey progress, live flight/map state, larger text, state-aware context, immediate overlay theme changes and quieter routine docking.
*   **v5.3.5.2** — Rebuilt System Intelligence, Survey Operations, Prospector Analysis, Carrier, Cargo and Colony overlays around theme-aware journal models; removed redundant redraws and corrected false startup survey completion after offline Carrier jumps.
*   **v5.3.5.1** — Added compact theme-aware personal/Squadron Carrier Discord embeds with safe EDSM links and detailed manual status posts, and corrected unknown startup scan totals until journal evidence confirms them.
*   **v5.3.5** — Replaced the multi-gigabyte trade database with on-demand Ardent Insight searches, rebuilt Trade Assist around practical one-way and round-trip planning, added the Trade Route HUD and persistent Trade Log, and kept visited-market EDDN uploads independent.
*   **v5.3.4** — Replaced Trade Command with the three-action Trade Assist, retained automatic EDDN uploads and journal-confirmed Current Run tracking, removed advanced route-watch machinery and made Station Link auto-hide explicit and immediately applied.
*   **v5.3.3.1** — Restored biological sample progress and Survey Status lifecycle, corrected legacy bio predictions, simplified carrier expedition editing, reduced danger noise, rebuilt Station Link, completed remaining overlay theming and removed measured persistence stalls.
*   **v5.3.3** — Added position-aware species-level biological prediction for all 116 published EDMC-BioScan species, including airless families, testable confidence, narrower value estimates, Codex-region HUD awareness and clearer Survey Status and expedition evidence.
