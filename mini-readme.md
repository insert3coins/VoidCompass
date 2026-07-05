# VoidCompass // UPDATE LOG

## v3.6.5 // Profile Dashboard + Route Refresh Polish
**Release Date:** 2026-Jul-05

### Commander Profile
*   Reworked the Commander Profile window from a plain text report into a dashboard layout.
*   Added summary cards for commander identity, credits, current location, and session travel.
*   Added active ship details, rank progress bars, reputation bars, profile storage status, and integration status cards.

### Navigation + Dashboard
*   Added a compact Current Flight strip inspired by SrvSurvey-style alignment visuals, showing previous/current/next route state without cramming system names into the strip.
*   Forced `NavRoute.json` to be checked on startup so existing route data is picked up when the app opens.
*   Route load/clear updates now refresh the dashboard panels, flight strip, nav label, and HUD immediately.

### Version
*   Bumped app version to **3.6.5**.

## v3.6.3 // Commander Profiles, Exploration Companion + Dashboard Rework
**Release Date:** 2026-Jul-05

### Commander Profiles
*   Added profile-aware commander handling so the app can switch cleanly between different commanders as journal events arrive.
*   Moved commander-specific settings/data paths into the active profile flow, including EDSM upload settings, carrier Discord webhook settings, route/config state, exploration data, and mining data.
*   New commander profiles seed their local mining database from the root `mining_data.db` when available.
*   The active commander is shown in the main command strip and profile windows refresh when commander data changes.

### Main Dashboard
*   Reworked the main window into a companion-style cockpit dashboard:
    *   Top flight deck for current system, route notes, and fleet carrier state.
    *   Left journal history stream with Elite Dangerous journal event icons.
    *   Right live event timeline retained for scan/value/route/system alerts.
*   Removed the old duplicated Mission Status cards and kept the underlying journal/session/scan data flowing through the real app state, databases, command strip, and dedicated windows.
*   Moved Ground Target setup into its own remembered-position tool window, with toolbar/footer access from the main dashboard.
*   Build script now packages the `Images` tree so journal history icons are available in packaged builds.

### Exploration
*   Added the Exploration companion window with current-system body details, bio tracking, route enrichment, trip/history stats, and a merged Value Ledger tab.
*   Bio information now tracks body signal counts, genuses/species, samples, and completion state where the journal provides it.
*   EDSM estimated-value enrichment is cached per commander profile and throttled to avoid noisy network refreshes.
*   Exploration refreshes automatically on relevant journal updates and remembers window geometry.

### Colony, BGS + Commander Tools
*   Added BGS visit tracking for faction/influence snapshots from visited systems.
*   Added Commander Profile dashboard support for ranks, progress, reputation, credits, and ship details from journal events.
*   Colonisation planning was merged into the Colony window as a shopping/planning workflow instead of a separate dashboard concept.
*   System Value Ledger was merged into the Exploration window so scan value and exploration context live together.
*   Squadron lookup work was removed after testing showed it was not useful for this app flow.

### Stability + Performance
*   Fixed UI freeze/crash behavior caused by worker threads updating Tk widgets directly.
*   Event feed updates now queue onto the Tk main thread.
*   Exploration database reads use nonblocking lock attempts with cached fallback where appropriate, reducing journal-update jitter.
*   Runtime trace review showed normal DB commits are tiny; the remaining work focused on avoiding UI refresh contention.
*   Crash reporter remains in the codebase but is disabled by default behind `CRASH_REPORTING_ENABLED`.

### Version
*   Bumped app version to **3.6.3**.
