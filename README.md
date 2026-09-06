# Void Compass

**Current version: 5.4.2.4**

Void Compass is an exploration-first companion for Elite Dangerous. It turns Frontier's live journal, status and companion files into a persistent command dashboard, deep survey intelligence, expedition planning and native in-game overlays.

[Download releases](https://github.com/insert3coins/VoidCompass/releases) · [Read the wiki](https://github.com/insert3coins/VoidCompass/wiki) · [Report an issue](https://github.com/insert3coins/VoidCompass/issues/new/choose)

Void Compass is distributed as a native Windows x64 application and does not require Python to be installed. Its command deck, Galactic Atlas and cockpit presentation use the bundled local HTML/WebView2 runtime; game processing remains local Python inside the packaged executable.

## At a glance

- **HTML Explorer Decision Deck** — a GPU-composited WebView2 briefing with one explainable Smart Next Action, a journal-aware departure preflight, selectable exploration doctrine, five-jump Route Horizon, Session Pulse, Regional Codex Hunt and commander-specific panel layouts throughout its workspaces.
- **Galnet Relay** — Frontier's official news feed in a quiet bottom-bar ticker beside the clock, with an in-app article reader, non-blocking refresh, a small offline cache and profile-aware controls for visibility, rotation and refresh cadence.
- **Exploration-focused navigation** — seven clear destinations keep survey, map and commander records prominent while a small Field Tools page supports surface work and mining.
- **Stellar Cartography** — a live System Orrery with journal-backed barycentres and Elite body-target lock, commander-controlled Survey Queue, planetary raw-material intelligence, planetary field mapping, expedition replay, a system/body/event-aware Screenshot Chronicle, science correlations and a complete 42-region passport built from retained journal evidence.
- **Deep Survey** — explainable FSS, DSS, biological, geological and planetary-mining signal progress; a Bio Field Assistant; discovery-significance ratings; valuable bodies; revisit targets; Colonisation Recon and a searchable discovery archive.
- **Galactic Atlas** — a fully offline, GPU-accelerated HTML/Three.js Milky Way map docked directly into the command deck, with genuine Elite XYZ structure, all 42 Universal Cartographics regions, routes, travel history, smart clusters, intelligence layers and commander annotations.
- **Cockpit overlays** — themed, profile-aware HTML HUDs with mouse passthrough, global hotkeys, a visual Overlay Layout Studio and quiet renderer self-recovery, rendered by one shared offline WebView2 runtime.
- **Quiet by design** — themed cockpit overlays, HTML notifications and a curated flight log provide useful feedback without cockpit chatter, speech synthesis or an AI service.
- **Explorer field tools** — a touchdown-anchored Surface Survey Trail, Ground/Exobiology, Mining, exploration Engineering/Synthesis, Colonisation Recon and focused Achievements remain available without turning the app into a general career suite.

The HTML Command Deck is the visible application shell for every launch. Its animated galactic flight-computer sequence covers profile, survey-history, live-journal and cockpit readiness, while first launch and later setup reruns use a matching HTML First Commissioning deck with native journal-folder selection. The live exploration briefing combines Current Survey, one explainable primary decision, a factual five-jump Route Horizon, Session Pulse, ranked field priorities, personal regional Codex coverage and the curated Flight Log; a cached Galnet ticker shares the persistent status bar beside the clock. Balanced, Completionist, Exobiology, Codex Hunter, Value Hunter and Fast Transit doctrines tune the advice without inventing journal facts; optional briefing cards can be hidden and reordered independently for each commander. Profile and theme changes update it from the same Python-owned journal state used by the overlays and map. Every presented application workspace now remains inside this command deck; the withdrawn Tk root is an internal journal/state host only and is never exposed as a second UI.

![Void Compass exploration dashboard](DashBoard.PNG)

*The exploration briefing keeps the current survey, route, priorities, expedition and discovery record together above the curated Flight Log.*

## Command workspaces

| Group | Direct workspaces |
| --- | --- |
| **Exploration** | Dashboard, Explore & Survey, Mission Control and Galactic Atlas. Explore adds an Elite-style live system body schematic, System Orrery and Survey Queue to the workboard, alongside editable profile waypoints, Elite NavRoute inspection and manual Spansh neutron plotting/import. |
| **Records** | Flight Records, Analytics, Commander Profile, Captain's Log and the System Value Ledger. Analytics includes the Explorer Science Lab and Galactic Region Passport; Captain's Log includes interactive expedition replay and standalone HTML export. |
| **Field Tools** | Ground/Exobiology with the Planetary Field Map, Mining, Engineering/Synthesis, Fleet Carrier Command, Colonisation Recon and Explorer Achievements. |
| **System** | Overlay Layout Studio, complete profile-aware Settings and About. |

Specialist state is hydrated only when its HTML page is opened, keeping routine journal publications and startup light while preserving live profile and theme changes.

Settings is focused on the application itself: profile themes and the custom palette workshop, journal paths, EDSM/EDDN/Discord integrations and tests, overlays and hotkeys, diagnostics, journal cache maintenance and first-run setup. Voice packs, personas, learned cockpit memory and speech controls are no longer part of the active application.

### Deep Survey Intelligence

Explore integrates profile-local Deep Survey intelligence directly into its four workflow pages, built from Frontier journal facts:

- **System Survey** combines the current body list, explainable FSS/DSS/biology completion matrix, ranked action queue, architecture, stellar wonders and Colonisation Recon in one filterable view. The Bio Field Assistant ranks unfinished worlds and reports live sample progress, spacing, terrain, value and first-footfall evidence; measured bodies receive an explainable significance tier and score. Its evidence inspector compares live, profile-database, Deep Survey, cached EDSM and traffic facts and can repair only the selected system from local journals without triggering uploads.
- **Expedition** uses one compact section switcher for route overview, waypoints, neutron planning, named Mission Control and Route Intelligence. The embedded Field Computer estimates the return journey and monitors route endurance without inventing missing module, service or material facts.
- **Discoveries** is one searchable archive for system history, valuable bodies, all 42 passport regions, Codex discoveries, FSS signals, DSS probe efficiency and screenshot metadata; image previews load only when selected, while system records can be copied or opened directly in EDSM.
- **Logbook** places the live trip summary, reliable resume checkpoint, automatic milestones and retained session debriefs together instead of separating them across Chronicle tabs. Its Explorer Data Vault separates unsold cartographic value, biological value and possible first-discovery bonus from recent sale evidence, while reports can be saved as Markdown or a themed local PNG share card.

![Void Compass System Survey](ExploreSurvey.PNG)

*System Survey combines verified completion, the action queue, missed-discovery revisit work, system architecture, body detail and Colonisation Recon.*

Expedition Overview acts as a live command centre, combining current-leg navigation, route progress, objectives, survey yield, unsold data, return planning, ship readiness and recent activity without replacing the detailed Mission Control, Waypoints or Route Intelligence tools.

![Void Compass Expedition Command](ExpeditionCommand.PNG)

*Expedition Command brings the current leg, route safety, return plan, ship readiness, objectives and recent field activity into one live overview.*

Named expeditions persist across sessions with journal-verified goals, multi-session statistics, prioritised bookmarks and revisit targets. Thirteen ready-made templates range from focused region, value, biology, sector, Codex, photography and mixed-survey goals to long-range cartography, exobiology field seasons, sector mapping, regional science, Outer Rim discovery and full galactic-circumnavigation campaigns. Applying a larger campaign extends matching objectives in place, preserving their verified progress instead of creating duplicate counters. Departing a system can add worthwhile unfinished mapping, biology or FSS evidence to the Missed Discoveries queue, which links directly to its Revisit map layer and expedition bookmarks. Their active strip remains visible across Explore, while verified progress appears through the native feed, toasts and expedition panels. The Galactic Atlas is now a fully HTML-driven Three.js command map served privately from Void Compass on `127.0.0.1` and embedded as a persistent command-deck page. Its focus control temporarily gives the map the complete window without opening a duplicate view, while returning to the Dashboard leaves its camera, filters and layers alive. It uses the GPU for a genuine three-dimensional Elite XYZ scene, consistent galactic-north-up/east-right tilted and top-down cameras, vertical-structure control, zoom-aware clustering and responsive labels while retaining the original Milky Way artwork and complete 42-region Universal Cartographics layout. Live coordinates, a camera-aware compass, dynamic field scale and restrained navigation reticle keep the map readable without crowding it. Profile-local travel history, live game and waypoint routes, the return trail, current ship and next-waypoint animation remain alongside Valuable, Biology, Codex, Photo, Recon, Revisit, Bookmark, Annotation and bounded Expedition Sector layers. Search, inspection and commander notes/danger warnings/regions of interest/survey targets/waypoints are handled directly in the embedded atlas; journal, route, profile and theme updates stream into the open map without a reload. Three.js and every map asset are bundled locally—there is no CDN, internet dependency or retired Tk map fallback. Expedition plans can still be exchanged as VoidCompass JSON or newline waypoint lists, while locally generated Markdown reports retain the named route, objectives, evidence and bookmarks.

![Void Compass Galactic Atlas](GalaxyAtlas.PNG)

*The GPU-driven Galactic Atlas showing its north-up/east-right Milky Way, true XYZ travel history, all 42 regions, live routes, clusters, intelligence filters and current-ship position.*

Explore remembers its active page, survey/discovery filters and Expedition section independently for each commander. Colonisation Recon produces a conservative survey-readiness dossier, saved candidate list and direct Architect Command handoff; it does not claim that survey readiness guarantees game eligibility. System architecture follows journal `Parents` relationships, while wonders detection flags unusual measured characteristics without inventing missing orbits.

Existing journals are indexed on a background worker the first time Deep Survey opens for a profile. Stored collections, expedition facts and visible rows are bounded so a long expedition does not turn map, ledger or startup recovery into a cockpit stall.

Void Compass deliberately leaves trade-route planning to dedicated services. It does not download a galaxy market dump, listen to the live EDDN feed or maintain a local price database. The independent **EDDN Community Market Upload** option remains in **Settings → Integrations**, publishing only fresh markets that the commander visits in game.

### Explorer Field Tools

Mining is the single intentional side activity. Mining Command combines a saved mineral/grade directive, Loadout-backed ship readiness, live prospect decisions, refinery and cargo yield, core cracks, limpet economy, cargo objectives, hourly performance and per-commander run history. It also switches to a journal-backed Rhino surface-mining mode with the active vehicle hold, refined haul and DSS planetary-mining locations; Elite does not journal individual drill deployment or progress, so Void Compass does not invent it. Commander DSS ring evidence and saved ring targets sit beside optional Spansh ring and mined-commodity buyer searches, while Prospector Analysis remains a focused cockpit readout for composition, material proportions, motherlodes and refinery evidence without inventing per-rock yield that the journals cannot prove. The Ground tool's Planetary Field Map plots the touchdown trail, ship return vector, biological samples, colony-distance rings, Codex evidence and commander field markers without claiming terrain the journals do not report. Ground/Exobiology, exploration Engineering/Synthesis, Colonisation Recon and exploration/mining achievement packs complete the focused Field Tools page without exposing general Combat, Powerplay, Squadron or BGS workspaces.

![Void Compass Explorer Field Tools](FieldTools.PNG)

*The deliberately compact Field Tools hub keeps Ground/Exobiology, Mining, exploration Engineering, Colonisation Recon and Explorer Achievements available without crowding the primary rail.*

Carrier Command tracks a commander's personal Fleet Carrier and Squadron Carrier as separate journal-backed vessels, with an in-page selector and independent identity, location, fuel, cargo capacity, jump state, expedition route, notes and Discord jump transitions. It plots either carrier's route through Spansh, can import an existing Fleet Carrier result URL or job, marks journal-confirmed arrivals complete and advances Copy Next to the first pending jump, and carries the selected route/fuel progress into the carrier overlay. Its Tritium view finds known hotspots around the selected carrier through Spansh and can copy or add a selected system to its expedition; its Cargo view combines the exact journal cargo total with an explicitly labelled manual/observed commodity manifest and active market orders.

## Adaptive Command Deck

Void Compass keeps the Dashboard centred on exploration: Current Survey exposes FSS, DSS, biological and geological progress; Explorer Decision ranks one explainable next action; Route Horizon inspects the next five plotted stars for scoopability, compact-star hazards and region crossings; Session Pulse summarises the active journal session; and Regional Codex Hunt compares personal coverage without pretending a missing record must exist locally. Journal activity quietly adjusts contextual emphasis for flight, exploration, mining, surface work, Carrier operations and data sales; there is no separate manual mode to manage, and unrelated career activity does not create dashboard objectives or companion-state records.

Overlay visibility remains an explicit commander choice in **Overlay Studio** and is never silently changed by Dashboard context. Every applicable Dashboard and specialist-workspace panel group can be rearranged in place, with the resulting layout retained independently for each commander profile.

## HTML cockpit overlays

Every overlay can be enabled independently, dragged to a saved position and styled with the active theme. A single isolated WebView2 process renders Navigation plus Cargo, Carrier, Prospector, Gravity, Station Link, Survey Operations, Cockpit Notifications, Heartbeat and Planet Waypoint Navigation surfaces. Every surface now consumes a semantic journal model through its own HTML/CSS presentation rather than replaying Tk canvas primitives. The compact telemetry Heartbeat distinguishes journal writes, Status updates, cockpit-state transitions and recent UI stalls; matching Journal, Status, Navigation and UI-health lamps remain visible in the command-deck footer. The command deck owns the complete visual Overlay Studio; internal compatibility proxies retain journal state, geometry and hotkey integration but no longer present an additional Tk cockpit surface on Windows.

- Journal-aware Navigation HUD with a focused **Standard** everyday layout and an optional **Expanded** planning layout, unified route/state/survey instrumentation, a large current-system readout and journal-restored system-time clock, one scalable distance-proportional waypoint rail for every route length, persistent completed history, an advancing current marker and arrival-driven next-leg handoff, next-star scoop and fuel-range intelligence, live fuel-scoop flow, local-target context, galactic travel direction and plane position, surface approach and ship-configuration cues, traffic and a Discovery Rail that distinguishes unknown, locally retained, live FSS and completed survey evidence while calling out biological, geological, planetary-mining and valuable-body discoveries. Profile waypoints republish immediately when edited and deliberately lead the HUD until that manual plan is cleared. Its bundled offline HTML/CSS renderer runs in an isolated transparent Edge WebView2 surface for fluid state-specific motion while a hidden migration proxy preserves journal drawing state, hotkeys and profile-aware positions. A journal-ID catalogue selects local artwork for the complete mothership and surface-vehicle set, including early `mev_rhino` recognition with the bundled Rhino portrait alongside Nomad, Scarab, Scorpion, fighter and carrier hand-offs.
- Survey Operations as a persistent cockpit work list that appears during FSS intake and defaults to bodies with confirmed biological, geological or planetary-mining signals plus valuable/notable mapping targets such as terraformables, Earth-like worlds, water worlds and ammonia worlds. A profile-aware Overlay Studio switch can instead include every surveyed body. Its focused-body card adds three-stage biological sampling, explicit predicted/detected/completed evidence, geology and mining-location targets, compact completed-species manifests and notable-world value evidence; live signal-cache fallback keeps targets current while detailed body scans catch up, and Navigation remains the single owner of system scan percentage.
- Purpose-built Gravity and Planet Waypoint Navigation HTML surfaces provide a clear descent-envelope warning and live surface bearing, turn and range solution without exposing the old Tk popup renderer.
- A dedicated semantic HTML Cargo Manifest with a live capacity rail, readable commodity stacks, mission/stolen distinctions, compact overflow handling and an explicit empty-hold state.
- Semantic Fleet/Squadron Carrier Command with identity and location, animated jump state, expedition progress, remaining-route fuel, Tritium reserve, range, cargo capacity and market-order evidence.
- Purpose-built Prospector Analysis with deposit state, motherlode emphasis, proportional material rails and a live per-asteroid refinery log.
- A dedicated semantic HTML Station Link with port identity, landing context, flight and explorer service readiness, unsold-data sale status, local authority/economy evidence and specialist availability while docked.
- Gravity, touchdown/liftoff, on-foot and other low-noise safety notifications.
- Severity-aware cockpit notifications, dedicated achievement unlock cards and a lightweight CSS-driven journal heartbeat with live and stalled states.

The HTML command deck's **Overlay Studio** is the single profile-aware overlay-control workspace. Its Layout view enables or disables every module and provides a scaled virtual-desktop preview: drag overlay cards to position the real HUD windows without disabling mouse passthrough. Saved positions remain authoritative through dynamic redraws, and Dashboard context never hides an enabled overlay. Its Overlay Settings view owns passthrough, Standard/Expanded Navigation HUD layout, overlay text scale, alert policy, auto-hide timing, gravity threshold and Navigation HUD CRT controls. Layout snapping, resets and named commander-specific presets remain available alongside those controls; application scale, Calm/Standard/Energetic Navigation animation and reduced motion remain under **Settings → Core → Accessibility**.

Profile-aware global shortcuts can open or close the Layout Studio, switch the Navigation HUD between Standard and Expanded, and temporarily hide or restore all overlays while Elite has focus, with optional individual shortcuts for the main exploration and field overlays. The low-conflict defaults are **Ctrl+Alt+Shift+F10** for Layout Studio, **Ctrl+Alt+Shift+F11** for all overlays and **Ctrl+Alt+Shift+F12** for a field bookmark at the current system/body; the layout switch is intentionally unbound so each commander can avoid game or GPU conflicts. Assignments can be recorded directly from the keyboard, typed manually or cleared on the dedicated **Settings → Hotkeys** page without changing which modules are enabled.

| Navigation HUD | Fleet Carrier HUD |
| :---: | :---: |
| ![Navigation HUD](NavHud.PNG) | ![Fleet Carrier HUD](CarrierHud.PNG) |

*Current Navigation and Fleet Carrier overlays. Enabled overlays remain visible regardless of Dashboard mode and retain their commander-specific positions.*

## Achievements and commander profiles

Achievement progress, exploration history, named expeditions, bookmarks, Captain's Log, Deep Survey records, carrier state, engineering plans, mining history, routes and integration settings are separated by commander profile. The active commander is detected from the journal and can be changed without mixing personal data.

Commander Record can create SQLite-safe manual profile backups and schedule a restore for the next application start. An enabled-by-default, profile-aware setting retains five rotating internal safety snapshots before version changes and cache rebuilds; commanders may disable those automatic snapshots without removing manual backup, while a restore always preserves the replaced profile as a rollback snapshot.

![Void Compass Explorer Achievements](Achievements.PNG)

*Explorer Achievements keeps the active packs centred on exploration, travel, exobiology, expeditions, carriers, colonisation and mining.*

## Visual feedback

Void Compass deliberately keeps feedback visual and deterministic. Survey changes, significant discoveries, route progress and safety events appear through the appropriate overlay, cockpit notification or curated Flight Log entry without spoken callouts, personas, learned cockpit behaviour or background speech generation. The retired speech, persona and learned-memory runtime has been removed; existing profile-local memory and voice-cache files from older releases remain untouched for safe rollback and are never loaded.

## Integrations

- **Elite journal and companion files** provide all live game state.
- **EDSM** upload and traffic lookup are optional and use per-commander credentials; accepted stored-fleet snapshots, ship movements and belt-cluster celestial scans are included while mining prospect events remain filtered.
- **EDDN** can optionally receive fresh commodity snapshots from markets visited in game. Uploads include the commander name as EDDN uploader ID plus game version, system, station and commodity data; Void Compass does not download the EDDN feed.
- **Spansh** supports neutron routes, ring/hotspot searches, material-trader lookups and integrated Fleet/Squadron Carrier route calculation.
- **Discord webhooks** announce personal or Squadron Carrier operations with compact event-specific, active-theme cards. Completed and current locations can link to EDSM, while a newly plotted jump remains plain text until arrival. Automatic posts keep only the jump, Tritium and relevant expedition context; a deliberate manual status post provides the fuller capacity, docking, service and route snapshot. User-entered notes cannot trigger Discord mentions, and carrier finances remain local.

Void Compass does not require an account or Void Compass cloud database. It checks GitHub Releases for a newer version at startup; other network integrations only run when their associated feature is enabled or requested. Retired Trade data from an older installation is ignored and is never opened, updated or deleted by Void Compass.

## First run, recovery and diagnostics

New installations open a short themed setup for the Elite journal folder, overlays, mouse passthrough and Adaptive Command. This is the only visible window and finishes before profile state, overlays or journal catch-up start. Settings can rerun it at any time.

State-heavy journal bursts are buffered through a coalescing background writer, while one bounded dispatcher protects Tk from cross-thread UI work. Closing Void Compass uses one short, bounded final-state flush. A profile-local session marker detects an unclean shutdown and restores the last graceful interface snapshot while journal catch-up settles. Dashboard and Settings expose Command Health queue status.

**Settings → Diagnostics → Create Support Bundle** produces a ZIP in the `logs` folder with version and health information, sanitized runtime/crash diagnostics, and only journal event names and timestamps. It excludes raw journal payloads, commander identity, profile identifiers, credentials and webhook URLs.

Packaged releases create `config.json`, commander profiles and logs beside the executable. If journal detection fails, set `journal_path` in Settings. The normal Windows location is:

```text
C:\Users\<You>\Saved Games\Frontier Developments\Elite Dangerous
```

The 5.4.2.4 interface is Windows x64 only. The former experimental Linux build has been retired as the application moves to one WebView2 presentation architecture.

## Contributing and support

Bug reports and feature ideas use the repository's structured [issue forms](https://github.com/insert3coins/VoidCompass/issues/new/choose). Before contributing code, see [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Suspected vulnerabilities must be reported privately according to the [Security Policy](SECURITY.md).

## License

Copyright © 2026 insert3coins. Void Compass is free software released under the [GNU General Public License v3.0 only](LICENSE). You may use, study, modify and redistribute it under those terms; redistributed source or binaries must preserve the GPL and provide the corresponding source as required by the licence. The corresponding source is published at [github.com/insert3coins/VoidCompass](https://github.com/insert3coins/VoidCompass).

The packaged offline galactic-region raster retains its upstream MIT notice in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Disclaimer

Void Compass is an independent community project and is not affiliated with or endorsed by Frontier Developments. Elite Dangerous and its related marks belong to their respective owners.
