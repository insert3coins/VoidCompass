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
- **Living Compass AI** — bounded per-commander memory, moods and learned habits, Piper voice callouts, plus an optional persisted Ollama working brain with 15 selectable personas and deterministic factual and safety fallbacks.

![Navigation HUD](NavHud.PNG)
![Achievements](Achievements.PNG)

## Setup

```
pip install -r requirements.txt
python VoidCompass.py
```

`config.json` is created automatically on first launch. If journal auto-detect fails, set `journal_path` (default: `C:\Users\<You>\Saved Games\Frontier Developments\Elite Dangerous`). Everything else is configurable in-app via **[ CONFIGURATION ]** and **SETTINGS**.

For optional generative Compass speech, install Ollama for Windows and use **Settings → Compass AI → Local Generative Language** to install, warm, test, and enable `qwen3.5:9b` or the lighter `qwen3.5:4b`. Its per-commander working brain combines verified route, survey, biology, mission, trade, mining, engineering, data-sale, learned-personality, relevant-memory, and recent-decision context. Choose from 15 constrained personas—from Tactical and Scientific to Deadpan, Companion, or Emergent—and preview the selection with **Test Persona**. Compass can add useful observations or intentionally remain quiet at Quiet, Balanced, or Proactive adviser frequency. Ollama is not required for normal operation; urgent safety callouts and all existing Compass behavior remain local and deterministic without it.

o7
