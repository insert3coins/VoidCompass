# VoidCompass // UPDATE LOG

## v2.3.3 // Fleet Carrier Watcher + Discord Feed
**Release Date:** 2026-Feb-16
*   **New Fleet Carrier Watcher Window:**
    *   Added dedicated watcher UI in dashboard nav (`[ FLEET CARRIER WATCHER ]`).
    *   Added tracked fields: carrier callsign/name, status note, optional manual heading, optional departure time.
    *   Added `OK`, `PUSH UPDATE`, and `CANCEL` actions with saved geometry/config persistence.
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
*   **Discord Fleet Message Overhaul:**
    *   Added dedicated fleet message flow (separate from Live Update stream).
    *   Updated fleet embed to compact operations format with icon lines and change-aware title.
    *   Added informative refresh reason titles (`Manual update`, `Journal event: ...`, `Distance recalculated`, etc.).
    *   Added carrier headline format (`🛸 Carrier: ...`) and clickable links.
*   **Fleet Discord Routing/Links:**
    *   Carrier headline link now resolves via Inara station search.
    *   Current location and current target lines link to EDSM system pages.
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
    *   Reduced startup fleet Discord spam by buffering historical replay into one consolidated startup update.
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
*   **Discord Live Output Refresh:**
    *   Removed duplicated navigation/exploration details from the live embed for a cleaner status card.
    *   Limited live embed description to a compact 3-line operations summary.
    *   Moved valuable world reporting to dedicated alert posts instead of the persistent live status message.
    *   Added trend indicators in the live embed (`Progress +N`, `Traffic ↑/↓/→`).
    *   Switched to explicit event-based Discord color mapping (`Jump`, `Scan`, `Valuable`, `Bio`, `FSS`).
