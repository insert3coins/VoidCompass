# Void Compass

**Current version: 5.4.3.1**

Void Compass is a local exploration companion for *Elite Dangerous*. It reads the game’s journal, status and companion files, then turns them into a useful command deck, survey record and set of in-game overlays. It is built for commanders who want to keep track of a long trip without handing their flight history to a cloud service.

[Download a release](https://github.com/insert3coins/VoidCompass/releases) · [Report a problem](https://github.com/insert3coins/VoidCompass/issues/new/choose)

## What it does

The main window is an HTML command deck backed by a Python application. It follows the active commander’s journals and keeps the important parts of an expedition in one place:

- **Dashboard and Explore & Survey** show current system progress, FSS and DSS work, biological and geological signals, valuable worlds, revisit targets and a short list of sensible next actions.
- **Expedition tools** handle routes, waypoints, named objectives, neutron planning, return planning and expedition replay. Route advice is based on recorded game data and clearly marks anything that is unknown.
- **Galactic Atlas** is an offline Three.js map with Elite XYZ coordinates, travel history, routes, regions, survey layers, annotations and the current ship position. It also includes a live System Orrery and body-target information.
- **Planet Materials** records a planet’s known raw materials and lets you save surface mining sites with latitude, longitude, materials and notes. The current planet and coordinates can be filled from the live journal state, while mining observations remain editable by the commander. Saved sites belong to the active commander profile and can be sent to the Planet Waypoint Navigation overlay.
- **Engineering Companion** provides ship loadouts, planned ship builds, module slots, blueprint and experimental-effect searches, material requirements, engineer information, Tech Broker recipes, Odyssey goals and build import previews. Plans can follow the ship currently in Elite or be kept as separate profile-local builds.
- **Mining and Ground tools** cover ring evidence, prospector details, refinery and cargo records, surface survey trails, exobiology work and journal-backed planetary mining signals.
- **Carrier Command** follows personal and Squadron Carriers separately. It keeps their location, fuel, cargo, routes and jump history, and shows preparation, lockdown, transit and journal-confirmed arrival states.
- **Powerplay, Colonisation Recon and Explorer Achievements** are available under Field Tools for commanders who want those records alongside their exploration data.
- **Galnet Relay** provides an optional local ticker and article reader using Frontier’s news feed.

The app is deliberately quiet. Feedback appears in the dashboard, Flight Log, notifications and overlays instead of through speech, personas or an AI service.

## Cockpit overlays

Every overlay can be enabled, positioned and themed independently. They are rendered through the same local HTML/WebView2 system as the command deck, while the Python runtime owns journal processing, profiles, scheduling, hotkeys and persistence.

Available overlays include Navigation, Cargo, Carrier, Prospector, Gravity Warning, Station Link, Survey Operations, Cockpit Notifications, Journal Heartbeat and Planet Waypoint Navigation. The Navigation HUD includes route progress, survey state, fuel and scoop information, local targets, surface approach details, carrier countdowns and journal-confirmed arrivals. Overlay Layout Studio provides a visual way to arrange them and save commander-specific layouts.

## Profiles and data

Void Compass keeps exploration history, expeditions, engineering plans, mining records, carrier state, settings and overlay layouts separate for each commander. The active commander is detected from the journal, and profiles can also be selected manually. Themes, hotkeys and window positions follow the active profile.

Data is stored locally beside the application’s configuration and in profile folders. There is no Void Compass account or hosted database. Automatic profile safety snapshots can run before upgrades and cache rebuilds, and Settings can create a redacted support bundle containing diagnostic information without raw journal payloads, credentials or commander identifiers.

Void Compass does not download or maintain a local copy of the EDDN market feed. EDDN publishing, EDSM uploads and traffic lookups are optional. Spansh is used only for requested route, ring, trader or carrier searches. Discord webhooks are optional and can announce carrier activity using the active theme.

## Installation

Packaged releases are Windows x64 applications. Python is not required to run a release, but Microsoft Edge WebView2 is required for the command deck and overlays. On first launch, the setup screen asks for the Elite journal folder and basic overlay preferences. The usual journal location is:

```text
C:\Users\<You>\Saved Games\Frontier Developments\Elite Dangerous
```

If the folder is not detected, it can be changed later in **Settings**.

## Running from source

Source development targets Windows x64 and Python 3:

```powershell
git clone https://github.com/insert3coins/VoidCompass.git
cd VoidCompass
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python VoidCompass.py
```

The application uses a local WebView2 window for its HTML interface. The source run and the packaged build use the same Python-owned state and journal pipeline.

## Building a release

Run the build script from Windows:

```powershell
python build.py
```

`build.py` installs the requirements, checks the PyInstaller and WebView2 dependencies, bundles the HTML, map, engineering and image assets, excludes Tk modules, and creates the executable and release archive under `dist` and `release`.

## Contributing

Bug reports, journal evidence, documentation fixes and focused code changes are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Run the test suite before submitting changes:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Please remove commander names, Frontier IDs, API keys, Discord webhooks and other personal information from logs or journal excerpts. Do not commit local databases, profiles, configuration files, generated builds or credentials.

## License

Void Compass is free software released under the [GNU General Public License v3.0 only](LICENSE). The packaged regional map data retains its upstream notice in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Disclaimer

Void Compass is an independent community project. It is not affiliated with or endorsed by Frontier Developments. *Elite Dangerous* and its related marks belong to their respective owners.
