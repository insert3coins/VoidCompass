# Void Compass

**Current version: 5.5.3**

Void Compass is a companion app for *Elite Dangerous*. It reads the journal and status files the game already writes, and turns them into a command deck on your desktop and a set of overlays in your cockpit. Everything runs and stays on your own PC: there's no account and no cloud service.

[Download a release](https://github.com/insert3coins/VoidCompass/releases) · [Report a problem](https://github.com/insert3coins/VoidCompass/issues/new/choose)

## What's in it

The command deck has a tab for each part of the game:

- **Dashboard and Explore & Survey**: the system you're in, FSS and DSS progress, biological and geological signals, valuable worlds and what's worth doing next.
- **Planetary Operations**: surface materials, saved mining sites, exobiology and a waypoint compass for getting around on foot or in an SRV.
- **Galactic Atlas**: an offline map of the galaxy's regions and everywhere you've been, with a replay of the whole journey.
- **Commander Record and Exploration Archive**: your ranks, history, achievements and a log of every trip.
- **Mining Command**: ring evidence, prospector results, refinery and cargo.
- **Ship Workshop**: an offline Build Planner for every hull and module, plus Engineering. Engineering covers your fleet's blueprints, your material locker, the engineers and how to unlock them.
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
- **Music**: a player for your own music files, with an overlay you can show in game.

Feedback is quiet on purpose: it shows up on the deck, in notifications and on the overlays. There's no voice and no AI chatter.

## Cockpit overlays

Overlays sit on top of the game. Each one can be switched on and off, moved and themed on its own:

Navigation HUD, Survey Operations, Jump Info, Deep Space Contact Scope, Construction Needs, Trade Route, Cargo Manifest, Fleet/Squadron Carrier, Prospector Analysis, Planet Materials, Planet Waypoint Navigation, Powerplay Operations, Station Information, Gravity Warning, Cockpit Notifications, Journal Heartbeat, Galnet Ticker and Music Player.

**Overlay Studio** lays them out on your actual monitors. It also has their opacity, a frame-rate cap and per-overlay options. Overlays can hide themselves while the galaxy or system map is open, and the switches along the top of the deck turn any of them on or off quickly. OBS can capture each overlay as its own window.

## Commanders and your data

Each commander gets their own profile: history, settings, theme, layouts and the rest. The app picks up who you're flying from the journal. It knows you by your Frontier ID, so renaming your commander in game doesn't lose anything.

Your data lives in the app's folder on your PC. On first run, Void Compass reads all your old journals, so your history starts as far back as they go.

Some features talk to community services, and you can switch any of them off in **Settings › Integrations**:

- **EDSM**: uploading your journal (optional), plus system information and faction history for the BGS tab.
- **EDDN**: sharing the markets you visit.
- **Raven Colonial**: colonisation projects. Only used once you've added your own API key.
- **EDCD tick service**: when the BGS tick happened.
- **Spansh**: only when you ask for a search, including trade routes and prices.
- **Discord**: carrier announcements, if you add a webhook.

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
