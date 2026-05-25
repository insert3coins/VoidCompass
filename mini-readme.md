# VoidCompass // UPDATE LOG

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
