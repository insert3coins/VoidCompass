# VoidCompass // UPDATE LOG

## v4.2.1 // Color Themes + Trustworthy Trade Routes
**Release Date:** 2026-Jul-12

### Color Themes
*   Added 10 built-in color themes (Void Cyan, Elite Orange, Emerald, Amber Terminal, Ice, Synthwave, Crimson, Solar Gold, Nebula Purple, Graphite) covering the whole app — native windows and the chroma-key overlays alike.
*   New Settings → Theme page: theme picker with live swatch preview, a full 18-slot color editor with system color-picker integration, and save/delete for named custom themes.
*   Themes apply instantly on Save Settings — the running UI, open tool windows, and on-screen overlays all recolor in place, no restart.
*   Theme choice and custom themes are saved per commander profile.

### Trade Route Quality
*   Multi-hop chain routes are now ranked by estimated profit per hour using the same travel-time model as loops (jumps at your ship's range + supercruise + docking) instead of raw profit; the Jump Range field now applies to both route modes.
*   Loop, chain, and opportunity-radar rankings are now freshness-weighted: an hour-old price beats a marginally better month-old one. Displayed prices stay raw.
*   Wide-radius searches no longer risk crashing on SQLite parameter limits (station sets are staged in a temp table instead of unbounded IN lists).

### Trade Watches & Data
*   Price watches now persist across restarts, and fired alerts re-anchor their baseline so continued price decay produces a fresh alert per further 10% step instead of one alert ever.
*   Watch alerts now pop a toast the moment they fire instead of waiting for the Watchlist tab to be opened.
*   The EDDN live listener starts with the app (when the market DB is seeded) rather than on first Trade-window open, so prices stay fresh all session.
*   EDDN uploads are schema-compliant again: station-illegal and nonmarketable items are excluded (regression vs. the original implementation).
*   Fixed a market database rebuild silently wiping trade analytics history and balance logs — user data now survives re-seeds on both swap paths.

### Version
*   Bumped app version to **4.2.1**.

## v4.1.8 // Overlay Polish Pass
**Release Date:** 2026-Jul-11

### Navigation HUD
*   Fixed hard-to-read alert badges (UNDISC, BIO, VALUE, FSS) — the hazard-stripe diagonal lines were cutting straight through the text at the same color. A flat backdrop now sits behind the letters, so the stripes stay confined to the badge's margins instead of fighting the text for contrast.

### Overlay Layout
*   Gravity warning and bio value strip no longer default to the same crowded left-edge column as system info / carrier / station info / survey status — both can fire together (a high-gravity body can also carry bio signals), so they now default to the right edge instead, spaced clear of each other.
*   Fixed a config default that was silently overriding those position fixes on every launch.

### Survey Status Strip
*   Fixed the body list rendering as a single line that truncated to "+N more" almost immediately on any system with more than a handful of unmapped bodies. It now wraps across up to 4 lines and sizes the panel to fit, so it actually shows what it claims to track instead of mostly blank space.
*   Fixed the "+N more" counter itself overflowing past the panel's right edge on very crowded systems.

### Version
*   Bumped app version to **4.1.8**.

## v4.1.6 // Proactive Toasts + Journal Heartbeat
**Release Date:** 2026-Jul-11

### New Toast Notifications
*   **Fleet carrier jumps** — "Carrier Jumped" and "Carrier Ready" toasts on arrival and cooldown-complete, alongside the existing Discord webhook notifications.
*   **Colonization project complete** — fires once when a construction project crosses 100%.
*   **Big trade profit** — fires when a single sale's profit crosses a configurable threshold (default 1M CR).
*   **Low fuel warning** — new percentage-based main-tank threshold check (added fuel-capacity tracking from the Loadout event, since only raw tonnage was tracked before); silent while docked, on foot, or in an SRV/fighter, with hysteresis so it doesn't spam right at the threshold edge.

### Journal Heartbeat Overlay
*   Added a small always-on corner pulse, modeled on SrvSurvey's PlotPulse, that flashes on every processed status update and turns red if nothing's come through for 15 seconds — a quick visual "is the watcher still alive" check that complements the existing freeze-diagnostics work.

### Settings
*   Added a toggle for the new heartbeat overlay alongside the existing overlay switches.

### Version
*   Bumped app version to **4.1.6**.

## v4.1.5 // Overlay Settings + Survey Strip Cleanup
**Release Date:** 2026-Jul-11

### Settings
*   Added Overlays toggles for the Gravity Warning, Bio Value Strip, Station Info, Survey Status Strip, and Toast Notification overlays — previously always-on with no way to disable them from the UI.
*   Exposed the gravity warning's trigger threshold (g) as an editable setting.
*   Increased the default Settings window size so the now-longer Overlays page doesn't need a manual resize to see everything.

### Survey Status Strip
*   Removed the scanned/total percentage and progress bar, which duplicated the navigation HUD's own SCAN PROGRESS row.
*   Now shows only what the nav HUD doesn't: the list of bodies still needing DSS mapping (bio-bearing ones highlighted) and the bio-remaining count. Hides itself once nothing's left instead of sitting at 100%.

### Version
*   Bumped app version to **4.1.5**.

## v4.1.4 // Unified Overlay Chrome + Survey Alerts
**Release Date:** 2026-Jul-11

### Overlay Visual Consistency
*   Extracted the navigation HUD's chrome (tri-line accent stripe border, corner brackets, scanline texture) into a shared helper and applied it to every overlay: system info, prospector, cargo, carrier, gravity warning, bio strip, station info, survey status, and the colony shopping list.
*   Fixed a pre-existing bug in the fleet carrier overlay where its window briefly collapsed to 1px tall after opening due to a geometry race condition.

### New Overlays
*   **Survey status strip** — persistent (non-auto-hiding) readout of scan progress for the current system, listing bodies still needing DSS mapping with bio-bearing ones highlighted.
*   **Toast notifications** — a generic transient popup stack for warnings and alerts (valuable worlds, undiscovered systems, etc.), reusing the existing event feed's severity plumbing so no new call sites were needed app-wide.

### Exploration Safety
*   Added a stale bio-sample warning: leaving a body with an incomplete (not yet 3-sample) organic scan sequence now pops a toast so in-progress samples aren't abandoned unnoticed.

### Version
*   Bumped app version to **4.1.4**.

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
