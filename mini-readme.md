# VoidCompass // UPDATE LOG

## v3.8.4 // Trade Sorting + Mining Cleanup
**Release Date:** 2026-Jul-07

### Trade
*   Added clickable sorting to Trade table headers, including commodity search and station search results.
*   Added short-lived nearby-station caching and extra SQLite indexes to make repeated Trade searches smoother.

### Mining
*   Removed the Mining window's Market tab now that buyer/market workflows live in the Trade window.

### Version
*   Bumped app version to **3.8.4**.

## v3.8.3 // Trade Polish + Exploration Bio Values
**Release Date:** 2026-Jul-07

### Trade
*   Added the remaining useful non-Autoplot pieces from the updated `elite-trader` project.
*   Added Trade guides for Road to Riches and neutron routing reference data.
*   Added station lookup/search tools and colonisation source finding from local market data.
*   Added watch removal controls for live trade route watches.

### Exploration
*   Added exobiology reference value data from `elite-trader` for Vista Genomics estimates.
*   Enriched `ScanOrganic` tracking with species value, genus value range, and colony/sample spacing.
*   Updated the Exploration Bio tab to show genus/sample spacing, estimated Vista value, and predicted genus candidates when body conditions are available.
*   The Bio summary now includes completed organic scan value alongside completed scan count.

### Version
*   Bumped app version to **3.8.3**.

## v3.8.2 // Trade Uploads, Analytics + Route Watches
**Release Date:** 2026-Jul-07

### Trade
*   Compared against the updated `elite-trader` project and ported the useful non-Autoplot trade improvements.
*   Added optional EDDN market publishing for fresh local `Market.json` snapshots after visiting station markets.
*   Added a Trade Database toggle for publishing visited station markets to EDDN, with upload counts and last-error status.
*   Added persistent trade and balance logging from `MarketBuy`, `MarketSell`, and `LoadGame` journal events.
*   Added a new Trade **Analytics** tab showing today/week/period profit, daily profit rows, top traded commodities, and balance delta.
*   Reworked the cargo sell finder to rank stations by total payout for the whole cargo hold instead of listing each commodity separately.
*   Added live loop route watches: selected loop routes can be watched, and incoming EDDN updates warn when stock, demand, or prices move against the route.

### Version
*   Bumped app version to **3.8.2**.

## v3.8.1 // Trade Companion + Market Builder
**Release Date:** 2026-Jul-07

### Trade
*   Added a new **Trade** window with route planning, commodity lookup, local station market data, cargo sell guidance, and database status.
*   Trade data uses the local Spansh market database, live EDDN updates, and local journal `Market.json` imports when commodity markets are opened in game.
*   Added Trade Routes support for local loop routes and chain routes, with saved per-commander route form settings.
*   Added Commodity Search for nearby buy/sell stations with large-pad and carrier filters.
*   Added a new **Radar** tab with profitable local opportunity scanning and cargo sell finder results.
*   Added local station market analysis, market freshness indicators, route/watchlist copy actions, and profit-per-ton details.
*   Added a per-commander Trade Watchlist for quick commodity checks.
*   Added a live Trade Session tracker from `MarketBuy` and `MarketSell` journal events.

### Market Database
*   Added a standalone **VoidCompass Market Builder** app for downloading and building the Spansh market database outside the main app.
*   Build output now packages both `VoidCompass.exe` and `VoidCompassMarketBuilder.exe`.
*   Added `pyzmq` support for EDDN market updates.
*   Ignored local generated Trade database files under `data/`.

### Dashboard + Journal
*   Added a Trade button/window hook to the main dashboard.
*   Journal watcher now tracks `Market.json` updates and feeds them into the local Trade database.
*   Dashboard state now tracks docked station, current cargo, fuel, legal state, destination, jump history, and trade session details for the Trade window.

### Version
*   Bumped app version to **3.8.1**.

## v3.7.1 // Exploration System History
**Release Date:** 2026-Jul-05

### Exploration
*   Added a new **System History** tab to the Exploration window.
*   System history is read from the active commander's profile-local `exploration_data.db`.
*   History merges `visited_systems`, `systems`, and `scan_hud_items` data, including system, last visit, star class, body scan progress, estimated value, bio counts, valuable body count, and DB/live source status.
*   Added filtering and copy support for the system history list.
*   The current system is overlaid with live in-memory scan data so the tab updates during active scanning without adding another persistence file.

### Navigation + Dashboard
*   Fixed Current Flight strip next-hop distance handling for Elite's upcoming-only `NavRoute.json` format.

### Version
*   Bumped app version to **3.7.1**.

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
