# Inara integration

Void Compass can keep your [Inara](https://inara.cz) profile up to date as you play, from version 5.5.4. It's whitelisted with Inara under the name **VoidCompass**.

## Why Inara

Inara is where many commanders keep their profile, fleet, ranks and flight log, and where squadrons look each other up. Void Compass already reads everything Inara wants from your journal, so you don't need a second app running just to keep it current.

## Setting it up

1. On Inara, open **Settings › API key** and copy your personal API key.
   The **INARA** button in Void Compass opens that page.
2. In Void Compass, open **Settings › Integrations › INARA**.
3. Paste the key into **Inara API key**.
4. Leave **Commander name on Inara** empty. Inara asks for the in-game name, so Void Compass takes it from your journal; the box is only used before the journal has named your commander.
5. Press **TEST INARA**. Inara should answer that it accepted the key.
6. Switch on **Sync with Inara**.

Each commander profile in Void Compass has its own key and switch, just like EDSM.

## What is sent

Only your own commander's data, with your own key:

| On Inara | From your journal |
|---|---|
| Credits and loan | LoadGame only (Inara asks for exact figures, and a balance tracked between loads misses crew wages) |
| Pilots Federation and navy ranks, with progress | Rank, Progress, Promotion |
| Reputation with the superpowers | Reputation |
| Reputation with minor factions | FSDJump, Location (your reputation with each faction in the system) |
| Powerplay rank and merits | Powerplay, PowerplayRank, PowerplayMerits, PowerplayLeave |
| Engineer progress | EngineerProgress |
| Game statistics | Statistics |
| Ships, loadouts, names, transfers, sales | LoadGame, Loadout, ShipyardNew/Buy/Swap/Sell/Transfer, SellShipOnRebuy, SetUserShipName |
| Where every stored ship is | StoredShips |
| Stored modules (with their engineering) | StoredModules |
| Suit loadouts (on foot) | SuitLoadout, CreateSuitLoadout, LoadoutEquipModule, LoadoutRemoveModule, RenameSuitLoadout, DeleteSuitLoadout |
| Materials | Materials, MaterialCollected, MaterialDiscarded, MaterialTrade, Synthesis, EngineerCraft, TechnologyBroker, ScientificResearch, EngineerContribution, mission rewards |
| Cargo | Cargo.json (your ship's hold, every time it changes) |
| Ship locker (on foot) | ShipLocker.json |
| Missions (with permits and faction effects) | MissionAccepted, MissionCompleted, MissionFailed, MissionAbandoned |
| Permits | MissionCompleted (permits from ranks Inara gives itself) |
| Friends | Friends (a new friend added: a friend request on Inara; declined or lost: removed) |
| Flight log | FSDJump, CarrierJump, Docked, Touchdown, DropShipDeploy, Location |
| Combat log | Died, Interdicted, Interdiction, EscapeInterdiction, PVPKill |
| Community goals and your progress | CommunityGoal |

That is every commander event Inara's API accepts. The item-by-item cargo and locker events aren't needed, because whole snapshots of both are sent whenever they change. Nothing is ever asked about other commanders. Markets, systems and factions go to EDDN, not Inara.

## How it's sent (Inara's rules)

- **In batches, never one by one.** A batch goes when you load the game, dock, jump or log off, and never more often than once a minute. So an update can take a minute or so to show on Inara.
- **Never twice.** State that hasn't changed (your ranks, your credits, a ship) isn't sent again.
- **Live game only.** Nothing is sent from Legacy (3.x) or beta builds, and nothing older than 30 days.
- **Starting late.** When Void Compass starts after the game, it sends only the current state of this session (ship, ranks, credits and so on), not travel you did while it was closed.
- **A rejected key stops it.** If Inara refuses the key, uploads stop and the Settings page says so. Fix the key and it starts again.
- **Steady, even without docking.** Whatever is waiting goes about once a minute, so an explorer who doesn't dock for days still has their jumps on Inara.
- **Shutdown.** Anything still waiting when Void Compass closes is kept and sent next time it starts (if it's still under 30 days old), so closing never waits on Inara.

Every batch is logged in the deck's live feed under **INARA**, as EDSM and EDDN are: how many events were sent, any Inara refused, and any connection trouble.

## For developers

- The code is in `src/voidcompass/services/inara.py`: `map_event()` turns journal events into Inara events, and `InaraUploader` queues and sends them.
- Requests go to `https://inara.cz/inapi/v1/` with `appName` "VoidCompass" and `appVersion` in the docs' `1.2.4` form (a hotfix's 5.5.3.9.3 goes as 5.5.3).
- The mapping follows Inara's API docs (inara.cz/elite/inara-api-docs), checked event by event on 2026-10-16; `tests/test_inara_spec_554.py` holds the docs' own journal-to-JSON examples.
- Running from source sends `isBeingDeveloped: true`, so Inara skips global events (community goal details) from test builds.
