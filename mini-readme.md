# VoidCompass // UPDATE LOG

## v4.1.3 // SrvSurvey-Inspired Overlay Suite
**Release Date:** 2026-Jul-11

### Navigation HUD (Normal + Compact)
*   Redesigned chrome around a SrvSurvey-style tri-line accent stripe border, corner brackets, and a subtle scanline background texture.
*   Replaced the fixed PREV/CURRENT/NEXT strip with a distance-proportional route "pip line" showing every upcoming hop, color-coded past/current/future, with a tick-mark fallback for dense routes.
*   Reworked full-mode layout into flat label/value rows (system, state, credits, cargo, profit, traffic) and consolidated the route mode, waypoint, jump count, and progress readouts into a single line.
*   Alert badges (undiscovered, bio, valuable, FSS) now render with a hazard-stripe diagonal treatment; compact mode gained its own badge row.
*   Kept the existing theme colors, animated corner spinner, and flight-state logic unchanged throughout.
*   Same pip-line route strip added to the dashboard tab's "CURRENT FLIGHT" card.

### System Info Overlay
*   Replaced the static top-3 "notable bodies" line with a scrollable, filtered, newest-first list of interesting bodies (terraformable, ELW/WW/AW, bio signals, or high scan value), each with icons, scan/DSS value, and bio count.
*   Now updates live as the system is surveyed (Scan, FSSBodySignals, SAASignalsFound, SAAScanComplete) instead of only refreshing on arrival.
*   Fixed a dead-code bug where locally scanned Terraformable worlds never tagged as notable due to a stale field name.

### New Overlays
*   **Gravity warning** — flashes when approaching a body whose known surface gravity exceeds a configurable threshold.
*   **Bio value strip** — shows genus/species predictions and credit values for the body being scanned, preferring confirmed organic scans over detected genus over pre-scan predictions.
*   **Station info card** — economy, government, controlling faction, allegiance, services, and landing pads on docking, sourced entirely from the local journal.
*   **Colony shopping list** — added a "This Site" toggle to filter the existing overlay down to just the construction project at the currently docked market.

### Version
*   Bumped app version to **4.1.3**.

## v4.0.4 // Freeze Diagnostics + Deadlock Fixes
**Release Date:** 2026-Jul-10

### Dashboard Reliability
*   Prevented Profile and BGS pages from blocking Tk while the journal watcher owns the shared database lock.
*   Added cached, non-blocking reads for the EDSM upload queue and BGS system/faction lists.
*   Verified every integrated page can be opened in sequence without creating a persistent Not Responding state.

### Diagnostics
*   Re-enabled automatic crash and UI-freeze reporting by default.
*   Added independent runtime-trace and crash-reporter controls under Settings → Diagnostics.
*   Added automatic thread stack dumps after a sustained UI heartbeat stall and retained the Ctrl+Alt+D manual dump shortcut.
*   Crash logs now start fresh on every application launch to prevent indefinite file growth.

### Version
*   Bumped app version to **4.0.4**.

## v4.0.3 // Themed Native Controls
**Release Date:** 2026-Jul-10

### Interface Controls
*   Reworked page actions around shared primary, standard, muted, and destructive button treatments.
*   Added consistent hover, pressed, disabled, and active-subtab states across the integrated application pages.
*   Replaced native page scrollbars with narrow, square, arrowless controls that use the VoidCompass palette and cyan interaction feedback.
*   Preserved specialised Settings toggles and section navigation while keeping them tied to the shared theme colours.

### Version
*   Bumped app version to **4.0.3**.

## v4.0.2 // Native Commander Console
**Release Date:** 2026-Jul-10

### Unified Native Interface
*   Added a shared native Tk theme and component library based on the VoidCompass commander-console design.
*   Restyled the dashboard and application tools with a consistent palette, typography, cards, controls, notebooks, and data tables.
*   Added the persistent left navigation rail, command strip, holographic card details, active cyan page marker, and an inset application frame.

### Integrated Dashboard Pages
*   Profile, Explore, Trade, Mining, Route, Carrier, Colony, BGS, Engineer, and Settings now open inside the main dashboard workspace.
*   Navigation switches pages without creating additional tool windows and keeps the rail and live command strip visible.
*   Existing page calculations, refresh hooks, and actions remain connected to the live application state.
*   Native HUD and overlay windows remain independent and retain their existing styling and behavior.
