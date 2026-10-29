# Void Compass

**Current version: 5.6.9**

Void Compass is a companion app for *Elite Dangerous*. It reads the journal and status files the game already writes, and turns them into a command deck on your desktop and a set of overlays in your cockpit. Everything runs and stays on your own PC: there's no account and no cloud service.

[Download a release](https://github.com/insert3coins/VoidCompass/releases) · [Report a problem](https://github.com/insert3coins/VoidCompass/issues/new/choose)

## What's in it

The command deck has a tab for each part of the game:

- **Dashboard and Explore & Survey**: the system you're in, FSS and DSS progress, biological and geological signals, valuable worlds, your route and waypoints, and what's worth doing next.
- **System Map** (a tab of Explore & Survey): a live Three.js view of your current system, with detailed planets, stars, atmospheres and rings. Spansh supplies known architecture while your journal scans take priority. Open a body from the Survey list, move between overview and true scale, and follow orbital time and starlight without losing your camera when new scans arrive. It marks where you are, your target, stations, settlements, fleet carriers, ring hotspots and your saved places; gives the distance and supercruise time to any body, its coming eclipses, day and night on locked worlds and a sky view from the surface; and has a survey layer with filters and a Quality setting. Public records remain separate from your discoveries; surface patterns are illustrative.
- **Galactic Atlas**: an offline map of the galaxy's regions and everywhere you've been. Its **Flight Recorder** plays any past session back on the map, jump by jump, with your discoveries, sales and postcards where they happened and the music you were listening to.
- **Planetary Operations**: everything on a planet's surface, in three tabs.
  - On the ground: a compass to any coordinates (or back to your ship), a field map of your trail, samples and markers, and the planet itself.
  - Exobiology: what lives on the planet you're on, what's worth sampling and what's new to the Codex, how far to move before your next sample, and the biology in the rest of the system.
  - Sites: your saved surface sites, ready to send to the compass.
- **Mining Command**: asteroid and Rhino mining, in four tabs.
  - Live run: the rock you just prospected and whether it beats your minimum, your rate and how long until the hold is full; or, in the Rhino, your rigs, both holds, fuel and what the ground tends to hold.
  - Find: rings by mineral, and planets with the right ground for the Rhino.
  - Sell: what your haul is worth and who pays most for it.
  - Record: all your mining from your journals, month by month.
- **Commander Record**: your ranks, history, achievements, and a Captain's Log of every trip.
- **Carrier Command**: your own carrier and your squadron's, with fuel, cargo, routes and jump countdowns.
- **Colonisation**: your construction projects, shared with your team through [Raven Colonial](https://ravencolonial.com).
  - Track what each site still needs and what your ship and carriers hold, and find where to buy it.
  - Plan a whole system's sites with Raven Colonial's own economy and score model.
- **BGS**: the Background Simulation.
  - Every faction in every system you visit: influence, states, conflicts, and how they change between ticks.
  - Track the factions you care about and get warned when they're in trouble.
  - Look up any system by name, and see the work you've done for each faction, per tick, with a report ready to paste into Discord.
- **Trading**: every trade you've made, with your profit per day, per hour and per route, plus trade routes, loop routes, where to sell what's in your hold, where to buy or sell any commodity, and station markets from [Spansh](https://spansh.co.uk).
- **Powerplay**: your pledge, rank, merits and the current cycle, system by system.
- **Void Wrapped**: your year in Elite, told as a story of animated cards, from how far you flew to your fights, your soundtrack and the Watcher's verdict. Every card saves as a picture for Discord.
- **Keepsakes**: postcards from your screenshots, time capsules (notes you leave in a system, handed back when you return), On this day, and your journey drawn as constellations.
- **Music**: a player for your own music files, with an overlay you can show in game.
- **Games**: fourteen arcade cabinets in Elite's world to play in the deck, from Docking Computer to Trumble Trouble.
- **Hatchling**: a shipboard companion that lives in real time, is raised by how you really play, and has its own habitat and overlay.
- **The Watcher**: an eye that watches your journal and thinks out loud beside it, about what you're doing, where you've been and its own long story. It remembers you between sessions. Its voice is off until you turn it on.

Everything else is quiet on purpose: it shows up on the deck, in notifications and on the overlays.

## Cockpit overlays

Overlays sit on top of the game. Each one can be switched on and off, moved and themed on its own:

Navigation HUD, Survey Operations, Jump Info, Deep Space Contact Scope, Construction Needs, Trade Route, Cargo Manifest, Fleet/Squadron Carrier, Prospector Analysis, Rig Tracker, Planet Materials, Planet Waypoint Navigation, Powerplay Operations, Station Information, Gravity Warning, Cockpit Notifications, Achievements, Journal Heartbeat (the Watcher), Galaxy Minimap, Postcards, Galnet Ticker and Music Player.

The **Rig Tracker** is for Rhino mining: press a hotkey as you deploy each mining rig and it points the way back to every one, with how far and how long it's been down, and how full your holds are.

The Navigation HUD's journal-driven state scenes use bundled Three.js graphics, projected as holograms in the state's colour. Its Hologram setting offers Full animation, Still poses or Off. A WebGL problem is shown in the scene viewport; there is no 2D scene fallback. The FSD cooldown has an animated venting drive core, driven by the journal's recovery state. Cruise fields fade individual particles at their boundaries, and FSS, DSS and exploration scenes combine native 3D objects with cockpit-style linework.

The boot screen centres the Watcher's eye beneath the Void Compass title, with real journal catch-up counts, commander and ship details, independent system readiness, an update-check indicator and expandable startup details. Three.js modules preload during boot. The composition overlay host creates its windows together and applies each manifest in one UI pass, keeping its DPI and text-fit rules. Hidden pages still wait for fresh rendered content before appearing. The Watcher's voice starts only after the boot screen closes.

**Overlay Studio** lays them out on your actual monitors. It also has their opacity, a frame-rate cap and per-overlay options. Overlays can hide themselves while the galaxy or system map is open, and the switches along the top of the deck turn any of them on or off quickly. OBS can capture each overlay as its own window.

The shared host pushes changed models to visible and hidden overlay pages. Each model travels with its revision; ordinary readings can catch up to the latest state while notification and companion event changes retain their order. Height and shape reports identify the page generation and layout they measured, protecting newer layouts from delayed replies and preserving text and monitor scaling.

## Commanders and your data

Each commander gets their own profile: history, settings, theme, layouts and the rest. The app picks up who you're flying from the journal. It knows you by your Frontier ID, so renaming your commander in game doesn't lose anything.

Your data lives in the app's folder on your PC. On first run, Void Compass reads all your old journals, so your history starts as far back as they go.

Some features talk to community services, and you can switch any of them off in **Settings › Integrations**:

- **EDSM**: uploading your journal (optional), plus system information and faction history for the BGS tab.
- **EDDN**: sharing the markets you visit.
- **Raven Colonial**: colonisation projects. Only used once you've added your own API key.
- **EDCD tick service**: when the BGS tick happened.
- **Spansh**: only when you ask for a search, including trade routes, prices, rings and planets for mining.
- **Inara**: keeping your Inara profile up to date. Only used once you've added your own API key and switched it on.
- **Discord**: carrier announcements, if you add a webhook.

Your own tools can work with Void Compass too. Its **Local API** (off until you switch it on in Settings › Integrations) lets scripts, Stream Deck buttons, stream widgets and bots read your commander, journal, overlays and command deck (your mining record, rigs, routes and more), and drive them: overlays, waypoints, rig keys, the Watcher's thoughts and voice, the theme and the music. It's plain HTTP and JSON on your own PC; see [api.md](api.md).

## Installing

Grab the latest zip from the [releases page](https://github.com/insert3coins/VoidCompass/releases), unzip it wherever you like, and run `VoidCompass.exe`. That's it: no installer, and you don't need Python. It's for Windows x64, and it needs Microsoft Edge WebView2, which most Windows 10 and 11 PCs already have.

The first time you run it, a short setup asks where your journals are. It usually finds them by itself, and shows your commander, ship and last system so you know it's reading the right folder. The usual place is:

```text
C:\Users\<You>\Saved Games\Frontier Developments\Elite Dangerous
```

You can change it later in **Settings**.

## Running from source

You don't need to do this to use Void Compass; the releases above are all most commanders need. If you'd like to run or change the code yourself:

```powershell
git clone https://github.com/insert3coins/VoidCompass.git
cd VoidCompass
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
python VoidCompass.py
```

The code lives in `src/voidcompass`, grouped by area: `core`, `dashboard`, `overlays`, `exploration`, `engineering`, `mining`, `powerplay`, `colonisation`, `bgs` and `services`. The deck and overlay pages are in `web`, reference data in `data`, tests in `tests` and build scripts in `tools`.

To build a release, run `python tools/build.py`. It creates the app in `dist` and the zip in `release`.

To capture the shared Hatchling models for a community post, run `.venv\Scripts\python.exe tools\hatchling_showcase.py`. It writes individual companion and outfit cards, transparent PNGs and galleries to `exports/hatchlings-5.6.8`.

To diagnose the Watcher renderer, close the app and set `"watcher_renderer_logging": true` in the root `config.json` beside the executable (or in the source run's folder). On the next launch, `logs/watcher_renderer.log` records whether the boot eye uses Three.js or the canvas fallback. It also records the dashboard Watcher and Heartbeat overlay once each when they have drawn. A fallback report says whether the Three.js module failed to load or the renderer could not start. Set it back to `false` to turn this diagnostic off; the setting is off by default.

## Contributing

Bug reports, journal snippets that show a problem, and focused fixes are all welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first, and run the tests before sending a change:

```powershell
python -m unittest discover -s tests -t .
```

Before you share a log or journal excerpt, take out your commander name, Frontier ID, API keys and webhooks.

## License

Void Compass is free software under the [GNU General Public License v3.0](LICENSE). It builds on work from SrvSurvey, Raven Colonial, BGS-Tally and others. The credits are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Disclaimer

Void Compass is a community project, not affiliated with or endorsed by Frontier Developments. *Elite Dangerous* and its marks belong to their owners.
