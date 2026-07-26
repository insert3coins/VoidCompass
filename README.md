# Void Compass

**Current version: 5.2.2**

Void Compass is a native Windows companion for Elite Dangerous. It turns Frontier's live journal, status and companion files into a command dashboard, persistent expedition tools, specialised workspaces, in-game overlays and a local cockpit companion.

Exploration is the primary experience. Trade, Mining, Combat/AX, Engineering, Powerplay and strategy tools remain fully available as optional add-on workspaces without crowding the live exploration view.

The Dashboard defaults to exploration, then transforms from verified journal activity for Trade, Mining, Combat, Ground, Engineering, Powerplay, Carrier, Colony and station operations. Its hero, telemetry, priority, support and primary action change together; automatic mode returns to exploration context when wider activity is no longer active. A themed mode selector can manually lock and inspect any Dashboard or immediately return to Automatic detection.

The Dashboard's activity log follows the current mode and keeps a curated Flight Log for discoveries, surveys, navigation, operations, Compass, alerts and support services. Frontier's unfiltered journal stream remains one click away in a separate diagnostics view.

![Void Compass exploration dashboard](DashBoard.PNG)

## Command workspaces

| Group | Direct workspaces |
| --- | --- |
| **Core** | Dashboard and Profile. |
| **Explore** | Explore and Galaxy. Explore uses four clear pages—System Survey, Expedition, Discoveries and Logbook—without nested Survey or Chronicle tabs; named Mission Control lives inside Expedition. |
| **Expedition** | Expedition overview plus direct Analytics, Achievements, Carrier and Colony access. |
| **Operations** | Operations overview plus direct Trade and Specialists access, including Mining and Combat/AX. |
| **System** | Engineer and About. |

Every group starts expanded, can be collapsed deliberately, remembers that choice per commander and remains reachable through a themed scrolling rail on smaller windows. Full secondary workspaces are still created only when first opened.

### Deep Survey Intelligence

Explore integrates profile-local Deep Survey intelligence directly into its four workflow pages, built from Frontier journal facts:

- **System Survey** combines the current body list, architecture, actionable DSS/biology/geology planner, stellar wonders and Colonisation Recon in one filterable view.
- **Expedition** uses one compact section switcher for route overview, waypoints, neutron planning, named Mission Control, and an interactive Elite-style 3D galaxy map with route intelligence.
- **Discoveries** is one searchable archive for system history, valuable bodies, Codex discoveries, FSS signals, DSS probe efficiency and screenshot metadata; image previews load only when selected, while system records can be copied or opened directly in EDSM.
- **Logbook** places the live trip summary and retained Captain's Log sessions together instead of separating them across Chronicle tabs, and can copy or save a shareable Markdown Expedition Report.

Named expeditions persist across sessions with journal-verified goals, multi-session statistics, prioritised bookmarks and revisit targets. Their active strip remains visible across Explore, while Compass can brief the next objective and announce verified completion without routine feed spam. The map plots the complete 42-region Universal Cartographics layout offline, supports rotate, pan, zoom and five camera presets, and overlays Valuable, Biology, Codex, Photo, Recon and Bookmark records; selecting an intelligence marker opens its existing record directly. Expedition plans can be exchanged as VoidCompass JSON or newline waypoint lists; full locally generated Markdown reports include the named route, objectives, evidence and bookmarks.

Explore remembers its active page, survey/discovery filters and Expedition section independently for each commander. Colonisation Recon produces a conservative survey-readiness dossier, saved candidate list and direct Architect Command handoff; it does not claim that survey readiness guarantees game eligibility. System architecture follows journal `Parents` relationships, while wonders detection flags unusual measured characteristics without inventing missing orbits.

Existing journals are indexed on a background worker the first time Deep Survey opens for a profile. Stored collections, expedition facts and visible rows are bounded so a long expedition does not turn map, ledger or startup recovery into a cockpit stall.

Trade opens in a compact **Simple Trade** view with cargo selling, routes, the current market and a clear EDDN receive/upload status. Routes, commodities, tracking, station search and database maintenance remain available through **Advanced Tools** and can be returned to the simple view at any time.

### Squadron Command

Galaxy includes a dedicated Squadron Command page for journal-backed membership, named rank, Squadron ID, applications, invitations, promotions, trophy wins, shared bookmarks and a bounded activity timeline. Existing faction watches become persistent squadron BGS objectives, while Squadron Carrier operations remain connected to Carrier Command.

Frontier does not publish a complete member roster, online presence, squadron chat or full leaderboard tables through the journal, so Void Compass leaves those fields unavailable instead of inventing them.

![Squadron Command workspace](SquadronCommand.PNG)

*Representative populated Squadron Command state; the page only displays facts reported by the commander's own journal.*

### Mining Specialist

Mining now lives inside Specialist Console as the single authoritative workflow. Runs start manually or from journal mining activity and record prospector quality, refinery and cargo yield, core cracks, limpets and their observed cost, attributable commodity sales, hourly performance and per-commander history. It remains directly available from the Operations navigation group.

### Specialist Console

Specialists remains local and journal-driven. Mining runs track confirmed refinery yield, prospector quality, limpet economics and attributable sales; Combat/AX records observed loadout readiness, ammunition snapshots, claims, damage, synthesis and recent sorties; Carrier planning combines authoritative owner snapshots with explicit upkeep, inventory and per-leg tritium inputs. Exobiology keeps body-local samples, manual pins and GeoJSON exports, while selected coordinates are handed to the existing Ground tool for navigation.

## Adaptive Command Deck

Void Compass keeps the Dashboard centred on exploration: current flight, route or waypoint progress, system survey, valuable discoveries, expedition support and the next verified exploration priority remain prominent. It still detects Mining, Trade, Combat, Ground, Engineering, Powerplay, Carrier, Architect and station activity from live journal evidence, but presents those optional workflows in a compact add-on strip and their dedicated workspaces instead of displacing exploration.

Each mode can apply a focused overlay scene while gravity, toast and heartbeat safety feedback remains available. Automatic detection can be locked to a chosen mode per commander, and overlay scenes or deterministic Compass briefings/debriefs can be disabled independently in **Settings → Command Deck**.

## Native overlays

Every overlay can be enabled independently, dragged to a saved position and styled with the active theme:

- Navigation HUD with game-route/waypoint switching, scan progress, traffic, biology, value and optional CRT effects.
- Survey Status with body names, scan state, notable worlds and biological sampling progress.
- Cargo, Fleet Carrier, Prospector, System Information, Station Information and Colony overlays.
- Gravity, touchdown/liftoff, on-foot and other low-noise safety notifications.
- Toast notifications and the journal/Compass heartbeat pulse.

![Navigation HUD](NavHud.PNG)

## Achievements and commander profiles

Achievement progress, companion memory, named expeditions, bookmarks, Captain's Log, Deep Survey history, carrier state, engineering plans, mining history, routes and integration settings are separated by commander profile. The active commander is detected from the journal and can be changed without mixing personal data.

![Native Achievement Centre](Achievements.PNG)

## Compass cockpit companion

Compass runs locally without an LLM, Ollama service or GPU workload. Its bounded per-commander memory combines verified navigation, named-expedition objectives, survey, biology, mission, trade, mining, engineering, carrier, social and data-sale context.

The deterministic cognition engine learns personal baselines and whether advice was useful, varies verified wording, remembers notable episodes, chooses useful silence and supports 15 behavioural personas. Optional Piper voice packs provide cached neural speech; urgent safety callouts remain isolated from persona styling.

## Integrations

- **Elite journal and companion files** provide all live game state.
- **EDSM** upload and traffic lookup are optional and use per-commander credentials.
- **EDDN** incrementally maintains the local market database after its initial seed.
- **Spansh** supports manual neutron routes, ring/hotspot searches and trader lookups.
- **Discord webhooks** can announce personal or Squadron Carrier operations.
- **Piper** voice packs are optional; regular system TTS remains available.

Void Compass does not require an account or cloud database. It checks GitHub Releases for a newer version at startup; other network integrations only run when their associated feature is enabled or requested.

## First run, recovery and diagnostics

New installations open a short themed setup for the Elite journal folder, overlays, mouse passthrough, Adaptive Command and optional voice. This is the only visible window and finishes before profile state, voice, overlays or journal catch-up start. Settings can rerun it at any time.

State-heavy journal bursts are buffered through a coalescing background writer, while one bounded dispatcher protects Tk from cross-thread UI work. Closing Void Compass immediately cancels active or queued voice work and uses one short, bounded final-state flush. A profile-local session marker detects an unclean shutdown and restores the last graceful cockpit snapshot while journal catch-up settles. Dashboard and Settings expose Command Health queue status.

**Settings → Diagnostics → Create Support Bundle** produces a ZIP in the `logs` folder with version and health information, sanitized runtime/crash diagnostics, and only journal event names and timestamps. It excludes raw journal payloads, commander identity, profile identifiers, credentials and webhook URLs.

`config.json` is created automatically in the working directory. If journal detection fails, set `journal_path` in Settings; the normal location is:

```text
C:\Users\<You>\Saved Games\Frontier Developments\Elite Dangerous
```

## Contributing and support

Bug reports and feature ideas use the repository's structured [issue forms](https://github.com/insert3coins/VoidCompass/issues/new/choose). Before contributing code, see [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Suspected vulnerabilities must be reported privately according to the [Security Policy](SECURITY.md).

## License

Copyright © 2026 insert3coins. Void Compass is free software released under the [GNU General Public License v3.0 only](LICENSE). You may use, study, modify and redistribute it under those terms; redistributed source or binaries must preserve the GPL and provide the corresponding source as required by the licence. The corresponding source is published at [github.com/insert3coins/VoidCompass](https://github.com/insert3coins/VoidCompass).

The packaged offline galactic-region raster retains its upstream MIT notice in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Disclaimer

Void Compass is an independent community project and is not affiliated with or endorsed by Frontier Developments. Elite Dangerous and its related marks belong to their respective owners.
