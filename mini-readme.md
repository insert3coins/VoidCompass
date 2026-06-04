# VoidCompass // UPDATE LOG


## v3.0.1 // EDSM Journal Upload
**Release Date:** 2026-Jun-04
*   **Opt-in upload of exploration/scan events to EDSM (`edsm_handler.py`):**
    *   Events are queued and sent in **batches** (up to 50 per POST) as a JSON array — matching the EDDiscovery approach rather than one-request-per-event.
    *   Each event is **enriched** with `_systemName`, `_systemCoordinates`, and `_systemAddress` before queuing so EDSM can correctly attribute scans to the right system.
    *   `fromGameVersion` and `fromGameBuild` are captured from `FileHeader` / `LoadGame` events and included in every POST.
    *   A **denylist** (`_EDSM_DISCARD_EVENTS`) filters out noise — chat, market data, docking events, missions, powerplay, crew, cargo, etc. — before events enter the queue.
    *   The queue **flushes immediately on every `FSDJump` / `CarrierJump`** so the previous system's data is shipped before internal state resets.
    *   The queue also flushes on a **30-second inactivity timer** for events that arrive outside of a jump cycle.
    *   Uploads are skipped during the startup journal catchup (`batch_mode`) so historical events are never replayed to EDSM.
*   **Settings UI** (`settings_ui.py`): new **EDSM UPLOAD** panel with:
    *   *Commander Name* text field.
    *   *API Key* masked password field.
    *   *Upload scan data to EDSM* on/off toggle (default off).
    *   **Test API Key** button — sends a live probe to `api-journal-v1` and reports success or the EDSM error message without leaving the settings window.
*   **Config defaults** (`config.py`): `edsm_cmdr_name` (`""`), `edsm_api_key` (`""`), `edsm_upload_enabled` (`false`).


## v2.9.7 // System Info Overlay
**Release Date:** 2026-Jun-03
*   **New `SystemInfoHUD` overlay (`system_info_hud.py`):**
    *   Appears automatically each time you jump to a system. Auto-hides after a configurable timeout (default 30 s).
    *   Draggable — position saved to `config.json` on mouse-release (`system_info_hud_x`, `system_info_hud_y`). Protected by the `winfo=0` guard so position is never clobbered when the window is hidden.
    *   Content fills in two waves:
        *   **Immediately on jump:** system name, primary star class, total body count, scanned count, total bio signals — all pulled from the DB for known systems. Notable bodies (ELW / Water World / Ammonia World / Terraformable) shown if previously recorded.
        *   **~2–5 s async (EDSM):** traffic (today / week / all-time) and system details — population, allegiance, government, faction, security, state — via `fetch_system_details()` which was already implemented in `edsm_handler.py` but previously never called on arrival.
    *   **Settings UI** (`settings_ui.py`): new *System Info Overlay* on/off toggle + *System Info Auto-Hide (seconds)* input (timeout takes effect without restart).
    *   **Config defaults** (`config.py`): `system_info_enabled` (true), `system_info_timeout_s` (30), `system_info_hud_x` (30), `system_info_hud_y` (30).


## v2.9.6 // Overlay Position Memory Fix
**Release Date:** 2026-Jun-03
*   **Overlay positions are now reliably remembered between restarts (`dashboard.py`):**
    *   `winfo_x()` / `winfo_y()` returns `(0, 0)` when a window is minimised, hidden, or not yet placed by the window manager. Two places were writing this bad reading straight to `config.json`:
        *   `_tick_overlay_position_sync` polls every 700 ms — it had a 4-second grace window at startup, but any `(0, 0)` reading after that was treated as the real position, overwriting saved coordinates.
        *   `on_close` read `winfo_x/y` unconditionally, so closing the app while minimised also clobbered the saved position.
    *   Fix: any `(0, 0)` reading is now always ignored when config already holds a non-zero position, for both the sync ticker and on shutdown.


## v2.9.5 // Mining Sessions · Colonization Window · Overlay Cleanup
**Release Date:** 2026-Jun-03

### Mining Sessions
*   **Sessions auto-start and auto-save to `mining_sessions.json` (`mining_window.py`):**
    *   The first `ProspectedAsteroid` event automatically opens a session — no need to click **Start Session** manually.
    *   Jumping to a new system automatically closes and saves the active session with an `ended_at` timestamp.
    *   Every prospector hit and refine flushes live data to `mining_sessions.json` (newest-first list). The file survives app reinstalls and is readable in any text editor.
    *   Each record stores: `started_at`, `ended_at`, `system_name`, `body_name`, `prospected_count`, `core_count`, `mined_tons` (dict per commodity), `material_stats` (avg / best / hits per material), `in_progress` flag.
    *   The **History** tab in the Mining window now loads from the JSON file on open, so all past sessions appear immediately. The in-progress session shows a `▶ IN PROGRESS` status row.
    *   `reset_session` now correctly clears the JSON session key so a reset followed by auto-start doesn't corrupt the previous record.
    *   `build.py` copies `mining_sessions.json` to `dist/` when building.

### Colonization Tracker Window
*   **New standalone Colonization window (`colonization_window.py`):**
    *   Opened via the **Colonization** button in the nav bar (replaces the old embedded tab).
    *   Left panel: scrollable list of all colonization projects with system name, progress bar, and completion status.
    *   Right panel: detail view with resource requirements table (required / delivered / remaining), free-text notes field, and last-updated timestamp.
    *   Data persisted to `colonisation_data.json` and to the SQLite `colonisation_projects` table. Notes survive depot event refreshes.
    *   Window position remembered in `config.json`.
    *   `build.py` copies `colonisation_data.json` to `dist/`.

### Bio / Geo Overlay Removed
*   **Exobiology overlay removed** — `bio_hud.py`, `bio_predictions.py`, and all 22 `bio-criteria/*.json` files deleted.
*   All wiring in `dashboard.py`, `dashboard_scan_mixin.py` removed (imports, `self.bio_hud` init, all `on_*` call sites, `_bio_hud_startup_replay`, `_bio_predict` usage).
*   **Settings UI** (`settings_ui.py`): removed orphaned *Exobiology Overlay* toggle.
*   **Config** (`config.py`): `bio_overlay_enabled`, `bio_hud_x`, `bio_hud_y` added to `DEPRECATED_CONFIG_KEYS` — they are purged from `config.json` on next settings save.
*   **Build** (`build.py`): removed `bio-criteria` bundle flag and copy step.


## v2.8.13 // Prospector HUD Startup Replay Fix
**Release Date:** 2026-May-26
*   **Prospector overlay no longer pops up on program load (`dashboard.py`):**
    *   `ProspectedAsteroid` and `MiningRefined` events are now gated on `not self.batch_mode`. During the startup journal catchup pass, `batch_mode = True`, so replayed history events are silently skipped by the overlay. Only events that arrive live (after startup completes) will trigger the overlay — same guard pattern used throughout `process_event` for every other UI update.

## v2.8.12 // Prospector HUD Auto-Hide + Position Fixes
**Release Date:** 2026-May-26
*   **Auto-hide timer now works correctly (`prospector_hud.py`):**
    *   `_schedule_hide()` now reads `prospector_hud_timeout_s` from config dynamically on each call, so changing the timeout in Settings takes effect immediately without an app restart. Previously the value was captured once at `__init__` time and never updated.
    *   Clarified the Settings label: "Prospector Overlay Auto-Hide (seconds) — 60 = 1 min · 120 = 2 min · 300 = 5 min". The field has always been in seconds (240 = 4 minutes, not 2).
*   **Overlay no longer jumps to top-left corner on new prospect (`prospector_hud.py`):**
    *   `_redraw()` was calling `win.geometry(f"{w}x{height}+{winfo_x()}+{winfo_y()}")`. When the window is withdrawn (hidden), `winfo_x()/winfo_y()` both return 0, silently resetting the overlay to screen position (0, 0) before it was shown. Fixed by setting only size in `_redraw()` (`win.geometry(f"{w}x{height}")`).
    *   `show()` now explicitly restores position from config (`prospector_hud_x` / `prospector_hud_y`) via `win.geometry(f"+{x}+{y}")` before calling `deiconify()`, so the overlay always appears in the saved location.

## v2.8.11 // Prospector Result Overlay
**Release Date:** 2026-May-26
*   **New `ProspectorHUD` overlay (`prospector_hud.py`):**
    *   Pops up automatically when a `ProspectedAsteroid` journal event fires (limpet returns data ~30 s after launch).
    *   Displays: asteroid type and content level (colour-coded — green HIGH / yellow MED / grey LOW), remaining % from last prospect, material list sorted by proportion with visual fill-bars, and a core/motherlode highlight when `MotherlodeMaterial` is present (border and header turn orange, motherlode material row highlighted).
    *   Running **refined-since-prospect** counter: every `MiningRefined` event after the last prospect increments the material count displayed in the footer (`~4 t refined: 2t Alexandrite  2t Cobaltite`). Resets on each new prospect.
    *   Auto-hides after a configurable timeout (default 45 s, key `prospector_hud_timeout_s`).
    *   Draggable — position is saved to `config.json` on mouse-release (`prospector_hud_x`, `prospector_hud_y`).
    *   On/off toggle in Configuration → **Prospector Result Overlay** (key `prospector_overlay_enabled`, default on). Requires app restart to take effect (same as other overlays).
    *   Canvas uses transparent chroma-key background (`-transparentcolor`), topmost, tool-window — same rendering path as ScanHUD and CargoHUD.
*   **`dashboard.py`:** Imports `ProspectorHUD`; creates it alongside the other overlays in `__init__`; forwards `ProspectedAsteroid` and `MiningRefined` events to it at the end of `process_event`, independent of the main scan/nav elif chain.
