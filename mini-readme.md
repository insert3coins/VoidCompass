# VoidCompass // UPDATE LOG

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

## v2.8.10 // Startup Scan Progress Restore
**Release Date:** 2026-May-26
*   **Scan progress now reliably loads on restart (`dashboard.py`, `dashboard_db_mixin.py`):**
    *   **`FSSDiscoveryScan` total-override bug fixed:** the `BodyCount` field in the journal event was normalised with a `0` default. When missing, `self.total = 0` wiped whatever `load_system_from_db` had just restored from the DB. Fixed by treating `body_count = 0` as "not provided" and using `max(body_count, self.total)` so the stored value is never decreased.
    *   **Startup batch `BEGIN TRANSACTION` removed** (`process_batch` in `dashboard.py`): same implicit-transaction conflict as the `dashboard_db_mixin.py` fix in v2.8.8. The explicit `BEGIN TRANSACTION` failed silently when an implicit transaction was already open (from the startup-seed `process_event` call), setting `in_transaction = False` and skipping the commit at the end of the batch. Python's sqlite3 now manages the transaction implicitly; the batch always commits.
    *   **Post-startup DB sync added:** on the first batch (`is_first_load`), after all events are processed and committed, the main thread calls `load_system_from_db` before running `update_dashboard_ui`. This ensures `scan_stat` always reflects the authoritative committed DB values rather than whatever in-memory state the batch left behind.
    *   **`import_scan_cache_json` now populates `bodies` and `systems` tables:** previously only inserted into `scan_hud_items`, so players who migrated from the old JSON scan cache saw `0 / 0` scan counts until a full Rebuild Cache was run. Now the scan body IDs from the cache are also written to `bodies`, and `systems` is updated with `scanned_count = number of body IDs`, using `max(existing, new)` to avoid regressing data already in the DB.

## v2.8.9 // Discord Embed Duplicate System Name Fix
**Release Date:** 2026-May-26
*   **Carrier location/target lines no longer repeat the system name (`carrier_tracker.py`):** Elite body names always start with the system name (e.g. `Parrot's Head Sector EL-Y d83 2`). The `_loc()` helper now strips the system-name prefix from the body string when present, showing `**System** / 2` instead of `**System** / System 2`.

## v2.8.8 // DB Rebuild Transaction Fix
**Release Date:** 2026-May-26
*   **Rebuild Cache no longer crashes (`dashboard_db_mixin.py`):**
    *   Removed three explicit `conn.execute("BEGIN TRANSACTION")` calls from `import_scan_cache_json`, `migrate_json_history`, and `scan_all_logs`.
    *   Python's `sqlite3` module manages implicit transactions automatically — any DML statement auto-begins a transaction. Issuing an explicit `BEGIN TRANSACTION` while an implicit one is already open caused SQLite to raise "cannot start a transaction within a transaction", aborting the entire rebuild.
    *   `conn.commit()` and `conn.rollback()` calls are preserved; only the redundant explicit `BEGIN` is removed.

## v2.8.7 // History Builder CarrierJump
**Release Date:** 2026-May-26
*   **Scan history rebuild now tracks FC jumps (`journal_watcher.py`):**
    *   `scan_history()` now advances `current_sys_context` when it encounters a `CarrierJump` event with `Docked=True`, in addition to `FSDJump` and `Location`.
    *   Previously, bodies scanned in systems reached by carrier jump were attributed to the wrong system during a history rebuild, because the context variable was never updated for `CarrierJump`.

## v2.8.6 // CarrierJump Startup Restore
**Release Date:** 2026-May-26
*   **Last-system restore works after carrier jumps (`journal_watcher.py`):**
    *   `_seed_startup_location()` now matches `CarrierJump` with `Docked=True` as a valid location anchor in addition to `FSDJump` and `Location`.
    *   Previously, if the last position update in the journal was a `CarrierJump` (because the player was docked when the carrier jumped), the app restarted with no system or an outdated one.

## v2.8.5 // Manual Discord Post + Departure Time
**Release Date:** 2026-May-26
*   **"Post Status to Discord" button (`carrier_window.py`, `carrier_tracker.py`):**
    *   Added a **📢 Post Status to Discord** button at the bottom of the carrier window to manually fire a Discord status embed at any time.
    *   Added an editable **Departure Time** field in the carrier window. Accepted formats: `18:30`, `18:30:00`, `DD/MM HH:MM`, `DD/MM/YYYY HH:MM`, `YYYY-MM-DD HH:MM`.
    *   Departure time is interpreted as the local machine time and converted to a UTC unix timestamp. Discord renders it in each recipient's own timezone via `<t:unix:F>` / `<t:unix:R>` tokens.
    *   UI shows a green **✓ Sent** or red **✗ reason** feedback label for 4 s after the post attempt; parse errors are surfaced for 5 s.
    *   `carrier_tracker.send_status_update(departure_ts=None)` — fires the `status_update` embed in a background thread, returns `(ok, err)`. Embeds include the `🕐 Departure` line only when a timestamp is provided.

## v2.8.4 // Editable Carrier Status & Destination
**Release Date:** 2026-May-26
*   **Editable fields in carrier window (`carrier_window.py`, `carrier_tracker.py`):**
    *   Added **Planned Destination** entry field. Saved value is used as the destination in Discord jump embeds (`🎯 Jump Target`, `📌 Destination`); defaults to `TBD` when blank.
    *   Added **Status Note** entry field. Saved value appears as the `ℹ️` italic line at the bottom of Discord embeds.
    *   Both fields show a green flash confirmation on save (1.2 s). Enter key triggers save. Fields do not clobber user edits in progress — they only sync from tracker state when the entry is not focused.
    *   `carrier_tracker.set_note(note)` and `carrier_tracker.set_destination_note(destination)` persist the values to config.

## v2.8.3 // Discord Carrier Embed Redesign
**Release Date:** 2026-May-26
*   **Emoji-rich multi-line Discord embeds (`carrier_tracker.py`):**
    *   Rewrote `_send_discord()` to produce structured, emoji-annotated embeds instead of plain-text messages.
    *   Per-event content:
        *   **Jump Plotted 🚀** — current location, jump target, departure time (if set), distance, and planned destination.
        *   **Jump Completed ✅** — arrived-at system, departed-from system, planned destination.
        *   **Jump Cancelled ❌** — remaining location and planned destination.
        *   **Cooldown Finished 🔓** — current location and carrier readiness.
        *   **Status Update 📢** — current location, optional departure timestamp, status note, and planned destination.
    *   All embeds include a UTC `"timestamp"` field and footer `VoidCompass · Fleet Carrier Tracker`.
    *   Departure times use Discord's `<t:unix:F>` (full local date/time) and `<t:unix:R>` (relative) tokens — each reader sees their own timezone automatically.
    *   Per-event embed accent colours: jump plotted (#5865F2 blurple), completed (#57F287 green), cancelled (#ED4245 red), cooldown (#5DADE2 blue), status (#FEE75C yellow).

## v2.8.2 // Scan Progress Accuracy
**Release Date:** 2026-May-26
*   **Known-System Scan Progress (`dashboard.py`, `dashboard_db_mixin.py`):**
    *   Fixed `load_system_from_db` ignoring `systems.scanned_count` — it was read from the DB but never used; `scanned` was derived only from counting rows in the `bodies` table, so completion counts stored by `FSSAllBodiesFound` or the history builder were silently lost on app restart.
    *   `FSSAllBodiesFound` now sets `scanned = total` (previously only updated `total`) and persists all current scan-item body IDs to the `bodies` table so return visits restore correctly.
    *   `FSSDiscoveryScan` with `Progress ≥ 1.0` now sets `scanned = total` — in pre-populated/known systems (Sol, Shinrarta Dezhra, etc.) the game returns `Progress=1.0` on the first honk, meaning every body is already catalogued; the HUD now shows 100% immediately instead of 0/N.
    *   Fixed double-counting in the `Scan` event handler: `scanned` was incremented with `+= 1` per new body, but when it was pre-loaded from `db_scanned_count` without individual body IDs, new scan events pushed `scanned` above `total`. Now derived from `len(scanned_bodies)` so it only advances when the set of known body IDs genuinely grows.

## v2.8.1 // Fleet Carrier Follow-ups
**Release Date:** 2026-May-26
*   **Window Position Persistence (`carrier_window.py`):**
    *   Carrier window now restores its last position and size from config on open (`carrier_window_geometry` key).
    *   Saves geometry and flushes `config.json` on close — same pattern as the Mining and Route Planner windows.
*   **Discord Webhook Configuration (`settings_ui.py`):**
    *   Added **FLEET CARRIER** section to the Configuration window with a webhook URL input field.
    *   Added **Send Test Message** button that dispatches a test embed to the configured webhook via a background thread (no UI blocking).
    *   Webhook URL is saved to config on save; leaving it empty silently disables all carrier Discord notifications.
*   **Fleet Carrier Jump = Player Location Update (`dashboard.py`, `journal_watcher.py`):**
    *   When docked on a fleet carrier that jumps, the game fires `CarrierJump` instead of `FSDJump` or `Location`. The dashboard was unaware of this, so `current_sys`, `current_system_address`, and `current_coords` were never updated — navigation HUD and scan state appeared frozen in the old system.
    *   `journal_watcher.py` now normalises `CarrierJump` with `star_system`, `system_address`, `star_pos`, `docked`, `body`, and `body_id` fields.
    *   `dashboard.py` extends the `FSDJump`/`Location` branch to handle `CarrierJump` when `docked=True`: resets scan state, loads system DB history, updates all HUDs, counts the jump in session stats, and logs a distinct **FC JUMP / Carrier arrived** event-feed entry.

## v2.8.0 // Fleet Carrier Manager
**Release Date:** 2026-May-26
*   **Fleet Carrier Tracking (`carrier_tracker.py`):**
    *   Tracks carrier identity, location, fuel, balance, services, and jump schedule from journal events.
    *   Handles `CarrierStats`, `CarrierJump`, `CarrierJumpRequest`, `CarrierJumpCancelled`, `CarrierLocation`, `CarrierTradeOrder`, `CarrierDepositFuel`, `CarrierDockingPermission`, `CarrierNameChanged`, `CarrierFinance`, and `CarrierBuy`.
    *   EDCM-aligned status state machine: `idle` → `jumping` (departure in future) → `cooldown` (≤290 s after jump) → `idle`; cancelled jumps enter `cooldown_cancel` within 60 s window.
    *   Background 30 s timer chain keeps status current without UI polling.
    *   Scans last 10 journal files on startup to restore carrier state without triggering Discord notifications.
    *   Discord webhook notifications for jump requests, cancellations, and completed jumps; suppresses notifications for replayed history events via freshness check.
    *   Three callback hooks: `on_updated` (carrier window), `on_panel_updated` (dashboard panel), `on_status_changed` (event feed).
    *   Persists carrier state to config across sessions.
*   **Fleet Carrier Window (`carrier_window.py`):**
    *   Three-tab window: Overview, Finance, Services.
    *   Overview: carrier identity, jump schedule with Discord-style relative timestamp (`<t:unix:R>`) copy button, carrier stats (fuel bar, jump range, space usage, docking access).
    *   Finance: balance display, tax rates, storage costs, upkeep estimate with funded-for calculation (years/weeks/days) and low-funds warning.
    *   Services: 11-service grid with three-state colouring — Active (green), Paused (orange + PAUSED label), Off (grey).
*   **Dashboard Integration:**
    *   Fleet Carrier button in the top navigation bar opens the carrier window.
    *   Carrier panel on the main dashboard: status badge, carrier name, current location, jump countdown or destination, and a compact fuel bar.
    *   Carrier status changes are logged to the event feed.
*   **Defensive Architecture (fixes from prior regression):**
    *   `journal_watcher.py`: event callback wrapped in `try/except` so `file_pos` is always updated even if a callback throws — prevents the watcher from replaying the same event and starving all subsequent navigation events.
    *   `dashboard.py`: carrier event routing isolated in its own `try/except` block before the navigation `if/elif` chain — a tracker failure cannot cascade into FSDJump/Location/Scan handling.
    *   `dashboard_ui_mixin.py`: `update_carrier_panel()` call guarded in `try/except` — a panel rendering error cannot prevent `update_waypoint_display()` and `update_hud()` from running.

## v2.7.6 // Mining Hotspot Data + Session Persistence
**Release Date:** 2026-May-26
*   **Hotspot Database Import:**
    *   Added flexible EliteMining `user_data.db` import — detects `hotspot_data` or `hotspots` source table automatically.
    *   Dynamic column mapping handles schema differences between EliteMining versions without hard-coded field lists.
    *   Normalises material names and ring types on import so local search filters match correctly.
    *   Import deduplicates on `(system_name, body_name, material_name)` using upsert — safe to re-run.
*   **Material & Ring Normalisation:**
    *   Added `MATERIAL_CANONICAL` lookup and `normalize_material_name()` shared across data layer and UI.
    *   Added `RING_TYPE_CANONICAL` lookup and `normalize_ring_type()` replacing ad-hoc string replacements.
    *   `_normalize_existing_hotspots()` runs on startup to clean any legacy data already in the local DB.
    *   `upsert_hotspot()` and `search_hotspots()` both normalise before write/compare.
    *   `_clean_name()` in the mining window now delegates to `normalize_material_name()`.
*   **Hotspots Table:**
    *   Removed the Source column from the hotspots treeview — System · Ring · Material · Signals · Ring Type · LY · LS · Overlap · RES.
*   **Session Persistence:**
    *   Added `update_session()` to write in-progress session data without ending it.
    *   Session progress (prospected count, core count, tons, material stats) is saved to DB after each prospector result and each refined event, not only on session stop.
    *   Progress is also saved when the mining window is closed mid-session.
    *   Extracted `_current_session_summary()` helper used by both in-progress saves and final close.

## v2.7.5 // Scan Body Accuracy + HUD Progress Fixes
**Release Date:** 2026-May-25
*   **Elite Journal Scan Alignment:**
    *   Preserved `SystemAddress` across location, scan, FSS, SAA, DSS, and organic scan events.
    *   Filters body-level scan updates by active `SystemAddress` so same-numbered `BodyID` values from another system cannot contaminate the current dashboard/HUD state.
    *   Stores `system_address` with scan HUD cache items for clearer source tracking.
*   **Scan Result Refresh:**
    *   Updates existing body cards when later detailed/nav-beacon `Scan` events add fields missing from earlier basic scan data.
    *   Derives biological signal totals from per-body signal records instead of mixing max and incremental counting.
*   **Navigation HUD Progress:**
    *   Stopped treating `FSSDiscoveryScan.Progress` and `FSSAllBodiesFound` as completed body scans.
    *   Scan progress now advances from actual body `Scan` events, and the HUD/dashboard percentage is clamped against stale historical data.

## v2.7.4 // Navigation HUD Route Polish
**Release Date:** 2026-May-25
*   **Navigation HUD Route Targeting:**
    *   Changed the route-planner footer target from the final destination to the next unvisited waypoint.
    *   Kept the top `NAV` row dedicated to the in-game navigation target.
    *   Relabeled the route-planner target as `WP` to distinguish it from game navigation.
*   **Navigation HUD Layout:**
    *   Compact route progress formatting so waypoint and route status fit on one footer line.
    *   Added dynamic waypoint font fitting to avoid overlap with long waypoint names.
    *   Updated HUD geometry restoration to use the HUD's configured dimensions instead of a hardcoded size.
*   **Navigation HUD Animation:**
    *   Added a lightweight Braille-style title animation on the right side of the HUD header.
    *   Animation redraws only the title glyph items and respects the HUD animation interval guardrail.

## v2.7.3 // Fleet Backout + Journal API Alignment
**Release Date:** 2026-May-19
*   **Fleet Carrier Feature Removed:**
    *   Removed the Fleet Watcher/Carrier Manager window from the top navigation.
    *   Removed fleet-carrier event forwarding, manager modules, Discord webhook settings, and saved fleet config keys.
    *   Fleet carrier work is parked for now and can be revisited later with a cleaner product fit.
*   **Journal API Alignment:**
    *   Added handling for `DiscoveryScan` and `NavBeaconScan` totals per the Elite Dangerous Journal docs.
    *   Added `FSSDiscoveryScan.Progress` support for better scan-progress restoration.
    *   Normalized `FileHeader`/`fileheader` casing and improved `FSSBodySignals` / `SAASignalsFound` biological/geological signal parsing.
    *   Reconciles HUD scan progress from stored body rows, stored scan counts, and scan HUD cache when revisiting systems.

## v2.7.2 // Mining Overlay Backout
**Release Date:** 2026-May-19
*   **Prospector Overlay Removed:**
    *   Removed the experimental enhanced prospector overlay.
    *   Removed the Mining window overlay toggle and Settings toggle.
    *   Removed prospector overlay config defaults and screen-position persistence keys.
*   **Mining Window Preserved:**
    *   Mining session tracking, prospector history, cargo, hotspots, market search, missions, reports, and bookmarks remain in place.

## v2.7.1 // Mining Companion + Startup Batching
**Release Date:** 2026-May-19
*   **New Mining Window:**
    *   Added top-nav `Mining` button.
    *   Added native mining companion tabs for session tracking, prospector results, cargo, hotspots, market search, missions, and history.
    *   Tracks live mining events from the existing journal watcher without VoiceAttack automation.
*   **Mining Session Tracking:**
    *   Tracks `ProspectedAsteroid`, `MiningRefined`, cargo state, material percentages, core asteroids, and mined tons.
    *   Saves mining session summaries into `mining_data.db`.
    *   Added HTML mining session report generation under `Reports/Mining`.
*   **Hotspot Finder:**
    *   Added local mining hotspot database support via `mining_data.db`.
    *   Added EliteMining `user_data.db` import for hotspot, overlap, and RES data.
    *   Added live Spansh ring search with material/ring/source/range controls.
    *   Added hotspot bookmarks.
*   **Market Search:**
    *   Added Spansh buyer search for mined commodities.
    *   Shows station, price, demand, distance, arrival LS, station type, and market update time.
*   **Build Packaging:**
    *   Build script now creates `mining_data.db` when missing and copies it to `dist/mining_data.db`.
    *   Bundles `mining_data.db` as PyInstaller data for packaged builds.
*   **Startup Performance:**
    *   Fixed current-journal startup catch-up so grouped journal events use the existing batch path.
    *   Reduces dashboard/UI redraw churn while the active journal is being scanned at launch.

## v2.3.3 // Fleet Carrier Watcher + Event Feed
**Release Date:** 2026-Feb-16
*   **New Fleet Carrier Watcher Window:**
    *   Added dedicated watcher UI in dashboard nav (`[ FLEET CARRIER WATCHER ]`).
    *   Added tracked fields: carrier callsign/name, status note, optional manual heading, optional departure time.
    *   Added `OK` and `CANCEL` actions with saved geometry/config persistence.
*   **Carrier Identity + Journal Sync:**
    *   Added callsign/name resolution from journal (`CarrierStats`) with carrier-id correlation.
    *   Added startup/history scan pass to restore last known carrier state from recent journals.
    *   Added resilient event matching for jump/cancel events when journal payloads are sparse.
*   **Fleet Carrier Journal Event Handling:**
    *   Added/verified watcher handling for:
        *   `CarrierStats`
        *   `CarrierLocation`
        *   `CarrierJumpRequest`
        *   `CarrierJump`
        *   `CarrierJumpCancelled`
        *   `CarrierNameChanged`
        *   carrier-related `Docked` / `Location` cases
    *   Added explicit event-feed entries for jump request, jump complete, cancel, and location updates.
*   **Fleet Status Preview:**
    *   Added a compact operations preview with icon lines and change-aware carrier state.
    *   Added informative refresh reasons (`Manual update`, `Journal event: ...`, `Distance recalculated`, etc.) for local state updates.
*   **Fleet Targeting + Distance Logic:**
    *   Split distance tracking into:
        *   manual heading distance
        *   live current-target (journal) distance
    *   Fixed stale-distance issue where destination line could show old/manual LY after new jump requests.
    *   Current target now updates to arrived location once jump completes.
*   **Fleet Output Conditional Display Rules:**
    *   Hide `Departure` when empty or when departure time has passed.
    *   Hide `Status` when empty.
    *   Hide `Heading` when manual heading is empty.
    *   Added `Current Target` label rename and destination/current-target clarity updates.
*   **Startup Noise/Performance Guardrails (Fleet Path):**
    *   Reduced startup fleet watcher noise by buffering historical replay into one consolidated startup update.
    *   Added journal-tail startup read behavior to reduce launch stalls during large journal files.

## v2.3.2 // HUD Telemetry + Event Reliability
**Release Date:** 2026-Feb-16
*   **Journal/Event Coverage Validation:**
    *   Audited live handlers against `Journal.2026-02-16T143413.01.log` and confirmed active scan/navigation coverage.
    *   Confirmed `SAAScanComplete` handling path and added active `ScanOrganic` processing in dashboard flow.
*   **Journal Trigger Reliability:**
    *   Added explicit handling for `Cargo`, `NavRoute`, and `NavRouteClear` journal events.
    *   Added `force_check_nav()` path in watcher to refresh `NavRoute.json` immediately on route events.
*   **Organic Scan Tracking:**
    *   Added per-body/species organic state tracking with completion gating.
    *   Added `BIO` event-feed entries for sample progress/completion and synced HUD/dashboard refresh.
*   **HUD Telemetry Widget Upgrade:**
    *   Added source-health indicators for `J/S/N/C/E` with freshness-aware states.
    *   Added clickable source/reason routing to focus dashboard event-feed filters.
    *   Added tuned source freshness thresholds to reduce false `FAIL` during normal idle periods.
*   **HUD Visual Cleanup:**
    *   Removed duplicated/ambiguous top-line text and simplified status area to source telemetry + age readout.
    *   Increased source-row readability (larger labels/dots and spacing alignment improvements).
    *   Added per-source age rotation (`J/S/N/C/E`) instead of fixed `J`-only timing output.
    *   Removed persistent sparkle travel effects after usability testing to reduce distraction.
*   **Log/Console Behavior:**
    *   Renamed `ACTIVITY LOG` to `CONSOLE LOG`.
    *   Restored curated operational logging (game version, journal file changes, settings updates, errors, maintenance lines).
    *   Added explicit journal file rollover line (`Journal file: ...`) in console output.

## v2.3.1 // Route Plotter Update
**Release Date:** 2026-Feb-16
*   **Dashboard Redesign (same color theme):**
    *   Added top summary strip for `SYS`, `ROUTE`, `SCAN`, `TRAFFIC`, and `SESSION`.
    *   Added alert bar with live system-state indicators.
    *   Added operations card grid, details drawer, and filtered activity log.
*   **Route Plotter Redesign:**
    *   Reworked planner layout with dedicated selection panel and action buttons.
    *   Added explicit per-item actions for copy/delete/edit/reorder/mark.
    *   Added optional EDSM auto-note enrichment for waypoint notes.
*   **Advanced Route Tools:**
    *   Added route health panel (`pending`, `visited`, `missing coords`, `duplicates`).
    *   Added duplicate handling modes: `skip`, `append note`, `keep both`.
    *   Added batch actions for copy/delete/mark done/mark todo.
    *   Added distance inspector (`from current`, `segment`, `cumulative`).
    *   Added import report summaries and CSV route export.
    *   Added Spansh CSV import button and parser support.
*   **Runtime Safety:**
    *   Added single-instance lock to prevent launching duplicate app processes.

### 🐞 BUG FIXES
*   **Traffic Refresh Reliability:**
    *   Fixed traffic fetch/update logic to refresh dashboard + HUD consistently on system changes.
*   **System Intel Refresh:**
    *   Fixed stale card updates by scheduling panel refreshes from scan/FSS/status event paths.
*   **Star Class Detection:**
    *   Added robust fallbacks so star class is captured from jump/location events and system-star scan events.
*   **UI Performance:**
    *   Added throttled dashboard refresh scheduling to prevent redraw storms during heavy event bursts.

### 🔧 IMPROVEMENTS
*   **Route Planner Defaults:**
    *   Increased default window size to `1020x700` for the expanded control set.
*   **Naming/Clarity:**
    *   Merged duplicate system/star presentation in dashboard cards for cleaner intel display.
*   **Live Status Refresh:**
    *   Removed duplicated navigation/exploration details from the status card.
    *   Limited status details to a compact operations summary.
    *   Moved valuable world reporting into dedicated event-feed alerts.
    *   Added trend indicators for progress and traffic.
