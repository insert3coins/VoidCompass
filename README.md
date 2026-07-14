# Void Compass

Real-time Elite Dangerous companion app — desktop dashboard, in-game overlays, route planning, EDSM integration, and a native achievement system.

![Dashboard](DashBoard.PNG)

## Features

- **Live dashboard** — current system, nav route, scan progress, fleet carrier, traffic, and a live event timeline, all driven off the journal in real time.
- **Overlays** — tactical navigation HUD, cargo, scan results, station info, gravity warnings, and more, each independently toggleable.
- **Route planning** — waypoint management, EDSM sync, Spansh/CSV import, duplicate handling, and CSV export with cumulative LY.
- **Career tools** — trade, mining, colonisation, BGS, carrier, and engineer material tracking.
- **Achievements** — 1,023 journal-driven milestones with per-commander progress and live toast unlocks.
- **Multi-commander** — separate profiles, data, and EDSM credentials per commander, detected automatically from the journal.
- **Themes** — 10 built-in themes plus a full custom theme editor.
- **Living Compass AI** — bounded per-commander memory, moods and learned habits, Piper voice callouts, 15 selectable personas, and a lightweight deterministic situational adviser.

![Navigation HUD](NavHud.PNG)
![Achievements](Achievements.PNG)

## Setup

```
pip install -r requirements.txt
python VoidCompass.py
```

`config.json` is created automatically on first launch. If journal auto-detect fails, set `journal_path` (default: `C:\Users\<You>\Saved Games\Frontier Developments\Elite Dangerous`). Everything else is configurable in-app via **[ CONFIGURATION ]** and **SETTINGS**.

Compass runs entirely locally without an LLM service. Its per-commander working brain combines verified route, survey, biology, mission, trade, mining, engineering, data-sale and learned-personality context. Choose from 15 deterministic personas—from Tactical and Scientific to Deadpan, Companion, or Emergent—and preview the selection with **Test Persona**. The situational adviser retains Quiet, Balanced and Proactive frequencies while urgent safety callouts remain isolated from persona styling.

o7
