# Void Compass

**Current version: 4.9.2**

Void Compass is a native Windows companion for Elite Dangerous. It turns Frontier's live journal, status and companion files into a command dashboard, persistent expedition tools, specialised workspaces, in-game overlays and a local cockpit companion.

![Void Compass operational dashboard](DashBoard.PNG)

## Command workspaces

| Workspace | Purpose |
| --- | --- |
| **Dashboard** | Low-noise flight and Compass briefings, active objective, route/waypoint context, carrier expedition status and a filtered live activity stream. |
| **Profile** | Career ranks, reputation, achievements, lifetime statistics, fleet and loadouts, missions, backups and integration state. |
| **Analytics** | Live session pace, interactive credit-balance and daily-profit graphs, selectable trading periods and top commodity performance from local journal history. |
| **Explore** | System history, scan values, biological survey records, Captain's Log and expedition chronicle tools. |
| **Achieve** | 1,023 native journal-driven achievements with per-commander progress, category controls and toast unlocks. |
| **Trade** | One-click trade overview plus routes, markets, local opportunities, watch tracking and EDDN-maintained market data. |
| **Specialists** | Four profile-local role consoles: elite-trader-style mining runs and economics, Combat/AX readiness and sorties, carrier upkeep/inventory/tritium planning, and exobiology records linked to the Ground tool. |
| **Route** | Separate Elite `NavRoute.json` and expedition-waypoint lanes, waypoint management, CSV/Spansh imports and a manual neutron plotter. |
| **Carrier** | Personal and Squadron Carrier identity, fuel, jump operations, expedition route, finance, services and Discord notifications. |
| **Colony** | Architect Command Centre for colonisation projects, contributions, cargo requirements and persistent planning. |
| **Galaxy** | Current-system factions, influence watches, conflicts, Powerplay, Community Goals, BGS history and Squadron Command. |
| **Engineer** | Goal-driven Engineering Command with shared Horizons and Odyssey wishlists, grade-aware engineer access and blueprint availability, collect/keep/trade inventory relevance, nearby traders and jumponium reserves. |

### Squadron Command

Galaxy includes a dedicated Squadron Command page for journal-backed membership, named rank, Squadron ID, applications, invitations, promotions, trophy wins, shared bookmarks and a bounded activity timeline. Existing faction watches become persistent squadron BGS objectives, while Squadron Carrier operations remain connected to Carrier Command.

Frontier does not publish a complete member roster, online presence, squadron chat or full leaderboard tables through the journal, so Void Compass leaves those fields unavailable instead of inventing them.

![Squadron Command workspace](SquadronCommand.PNG)

*Representative populated Squadron Command state; the page only displays facts reported by the commander's own journal.*

### Mining Specialist

Mining now lives inside Specialist Console as the single authoritative workflow. Runs start manually or from journal mining activity and record prospector quality, refinery and cargo yield, core cracks, limpets and their observed cost, attributable commodity sales, hourly performance and per-commander history. The Dashboard Mining shortcut opens this section directly.

### Specialist Console

Specialists remains local and journal-driven. Mining runs track confirmed refinery yield, prospector quality, limpet economics and attributable sales; Combat/AX records observed loadout readiness, ammunition snapshots, claims, damage, synthesis and recent sorties; Carrier planning combines authoritative owner snapshots with explicit upkeep, inventory and per-leg tritium inputs. Exobiology keeps body-local samples, manual pins and GeoJSON exports, while selected coordinates are handed to the existing Ground tool for navigation.

## Native overlays

Every overlay can be enabled independently, dragged to a saved position and styled with the active theme:

- Navigation HUD with game-route/waypoint switching, scan progress, traffic, biology, value and optional CRT effects.
- Survey Status with body names, scan state, notable worlds and biological sampling progress.
- Cargo, Fleet Carrier, Prospector, System Information, Station Information and Colony overlays.
- Gravity, touchdown/liftoff, on-foot and other low-noise safety notifications.
- Toast notifications and the journal/Compass heartbeat pulse.

![Navigation HUD](NavHud.PNG)

## Achievements and commander profiles

Achievement progress, companion memory, Captain's Log, carrier state, engineering plans, mining history, routes and integration settings are separated by commander profile. The active commander is detected from the journal and can be changed without mixing personal data.

![Native Achievement Centre](Achievements.PNG)

## Compass cockpit companion

Compass runs locally without an LLM, Ollama service or GPU workload. Its bounded per-commander memory combines verified navigation, survey, biology, mission, trade, mining, engineering, carrier, social and data-sale context.

The deterministic cognition engine learns personal baselines and whether advice was useful, varies verified wording, remembers notable episodes, chooses useful silence and supports 15 behavioural personas. Optional Piper voice packs provide cached neural speech; urgent safety callouts remain isolated from persona styling.

## Integrations

- **Elite journal and companion files** provide all live game state.
- **EDSM** upload and traffic lookup are optional and use per-commander credentials.
- **EDDN** incrementally maintains the local market database after its initial seed.
- **Spansh** supports manual neutron routes, ring/hotspot searches and trader lookups.
- **Discord webhooks** can announce personal or Squadron Carrier operations.
- **Piper** voice packs are optional; regular system TTS remains available.

Void Compass does not require an account or cloud database. Network integrations only run when their associated feature is enabled or requested.

`config.json` is created automatically in the working directory. If journal detection fails, set `journal_path` in Settings; the normal location is:

```text
C:\Users\<You>\Saved Games\Frontier Developments\Elite Dangerous
```

## License

Copyright © 2026 insert3coins. Void Compass is free software released under the [GNU General Public License v3.0 only](LICENSE). You may use, study, modify and redistribute it under those terms; redistributed source or binaries must preserve the GPL and provide the corresponding source as required by the licence. The corresponding source is published at [github.com/insert3coins/SurveyAnalysis](https://github.com/insert3coins/SurveyAnalysis).

## Disclaimer

Void Compass is an independent community project and is not affiliated with or endorsed by Frontier Developments. Elite Dangerous and its related marks belong to their respective owners.
