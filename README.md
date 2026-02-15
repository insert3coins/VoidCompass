# Void Compass

Void Compass is a real-time Elite Dangerous companion app with a desktop dashboard, in-game overlays, route planning tools, EDSM integration, and live Discord telemetry.

![Dashboard Screenshot](https://raw.githubusercontent.com/insert3coins/VoidCompass-Release/main/DashBoard.PNG "Dashboard Screenshot")

## Current Features

- Live journal ingestion for `Location`, `FSDJump`, `Scan`, `FSS`, `SAA`, cargo, nav route, and status data.
- Single-instance lock to prevent duplicate app launches.
- Dashboard summary strip for `SYS`, `ROUTE`, `SCAN`, `TRAFFIC`, and `SESSION`.
- Alert bar with live system-state warnings.
- Activity log with filters: `ALL`, `JUMP`, `SCAN`, `ALERT`, `ERROR`.
- Event Feed panel replacing old split drawers, with color-coded entries.
- Tactical Navigation HUD overlay: current system, nav target, distance, scan progress bar, traffic, destination, route progress, and remaining LY.
- Top-right status blip (`OK`, `ALERT`, `FAIL`) for quick health/attention status.
- Cargo overlay for live inventory/capacity.
- Scan results overlay for exploration/FSS workflow.
- Route Planner window: waypoint add/edit/delete/reorder and visited-state tracking.
- Batch actions: copy, mark done/todo, delete.
- Duplicate handling modes: `skip`, `append note`, `keep both`.
- Route health indicators: pending, visited, missing coords, duplicates.
- EDSM route refresh and optional automatic EDSM note enrichment.
- Bulk import from pasted lists and Spansh CSV import.
- Route CSV export with segment and cumulative LY.
- Auto-copy waypoint support (including startup behavior).
- Discord webhook integration with a persistent live message (`Live Update` title) and separate valuable-discovery alerts.
- Screenshot converter (BMP -> PNG) with system/timestamp naming and optional BMP cleanup.
- Auto-saved window positions/geometries for dashboard, settings, overlays, and route tools.

![Tactical HUD](https://raw.githubusercontent.com/insert3coins/VoidCompass-Release/main/NavHud.PNG "Tactical HUD")

![Route Planner](https://raw.githubusercontent.com/insert3coins/VoidCompass-Release/main/RoutePlanner.PNG "Route Planner")

On first launch, `config.json` is created automatically.

## Configuration

Use the in-app **[ CONFIGURATION ]** panel or edit `config.json` directly.

- `journal_path`: Elite journal folder path. If blank, Void Compass tries auto-detect.
- `overlay_enabled`: Enable/disable tactical nav HUD.
- `cargo_overlay_enabled`: Enable/disable cargo overlay.
- `scan_overlay_enabled`: Enable/disable scan overlay.
- `discord_enabled`: Enable/disable Discord integration.
- `discord_webhook`: Discord webhook URL.
- `screenshots_enabled`: Enable/disable screenshot conversion.
- `screenshots_path`: Folder to watch for BMP screenshots.
- `hud_x`, `hud_y`: Tactical HUD position.
- `cargo_hud_x`, `cargo_hud_y`: Cargo HUD position.
- `scan_hud_x`, `scan_hud_y`: Scan HUD position.
- `main_geometry`, `settings_geometry`: Saved window geometry.

Default journal path target:

`C:\Users\<You>\Saved Games\Frontier Developments\Elite Dangerous`

## Notes

- Pillow (`PIL`) is required for screenshot conversion. If missing, that feature auto-disables and logs an error.
- Discord live telemetry updates one persistent message and emits separate one-off valuable discovery alerts.

o7
