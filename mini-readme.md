# VoidCompass // UPDATE LOG

## v4.4.2 // Galaxy Intelligence + Faction Watches
**Release Date:** 2026-Jul-13

### Galaxy Overview
*   Added current-versus-previous influence movement to faction rows and made systems and factions open their matching records directly in **BGS HISTORY**.
*   Added journal freshness and source indicators, stale-data highlighting, and a manual refresh control.
*   Expanded conflicts with their leader and both faction stakes, and expanded Community Goals with galaxy totals, contributor counts, bonuses, and top-rank status.

### Faction Watches
*   Added persistent per-commander faction watches using the star control beside each current-system faction.
*   Watched factions produce one low-noise alert when a later journal update reports a meaningful influence change, active-state change, or gain/loss of system control.

### Interface
*   Added compact single-column reflow for narrow Galaxy pages, mouse-wheel overview scrolling, and horizontal scrolling for detailed BGS history.

### Version
*   Bumped app version to **4.4.2**.

## v4.4.1 // Engineering + Galaxy Companion Expansion
**Release Date:** 2026-Jul-13

### Engineering
*   Expanded the native Engineering page with blueprint grades, material requirements, pinned-blueprint tracking, material inventory coverage, missing-material totals, and synthesis/jumponium readiness.
*   Added engineer discovery, unlock, invitation, and reputation progress sourced from commander journals and cached profile data.
*   Added focused material filtering and clearer readiness states without introducing automatic route plotting.

### Galaxy + BGS
*   Replaced the old standalone BGS navigation entry with an integrated **GALAXY** page.
*   Added a **GALAXY OVERVIEW** tab showing the current system and controlling faction, faction influence and states, commander reputation, conflicts, Powerplay status, squadron information, and community goals.
*   Preserved the existing visit and faction records under the **BGS HISTORY** tab.
*   Galaxy information updates from live journal events and remains commander-local; it does not depend on a browser panel or external web service.

### Commander Companion
*   Added native fleet, mission, massacre-stack, community-goal, Powerplay, squadron, and conflict summaries to the existing commander surfaces.
*   Added ship loadout export and station-service lookup support.
*   Added jumponium availability plus rebuy and unsold exploration-data risk warnings.
*   Added sampling-clearance guidance to the Exploration page and Survey HUD, with settings controls for the new companion alerts.

### Version
*   Bumped app version to **4.4.1**.

## v4.3.4 // Achievement Fixes + Progress Bars
**Release Date:** 2026-Jul-12

### Data Safety
*   **"Rebuild from Journals" no longer destroys unlocks it cannot re-derive.** A rebuild previously reset all progress before re-scanning, so imported, manually granted, and long-ago unlocks — earned from journals that have since rotated away — were permanently lost. Progress is now monotonic: prior unlocks are carried forward, counters and lifetime totals only ever move up, and original unlock timestamps survive (the rebuild used to re-stamp them with the rebuild time). Use Reset All for an actual wipe; the confirmation dialog now says so.

### Fixes
*   Resetting a route achievement now clears its route progress. It was left at 100%, so the achievement instantly re-fired on the next jump (affected all 81 route achievements).
*   Playtime now only accrues while Elite Dangerous is actually running, instead of counting VoidCompass uptime. The four `played_*_hours` achievements were unlocking far faster than intended.

### Interface
*   Added progress bars: a drawn bar in the detail pane (green at 100%) and a bar in the catalogue's progress column, alongside the existing percentage and counter.
*   The achievement catalogue now uses the app's standard monospace table font, aligning the progress column.

### Version
*   Bumped app version to **4.3.4**.

## v4.3.2 // Native Achievement System

**Release Date:** 2026-Jul-12

### Integrated Achievements

- Added 1,023 journal-driven achievements covering exploration, exobiology, combat, trade, mining, engineering, travel, ranks, carriers, colonisation, Odyssey activities, and more.
- Integrated the achievement engine directly into VoidCompass. It uses the existing journal watcher and runs inside the main Python application with no webserver, browser panel, Node process, or additional port.
- Achievement progress and settings are stored separately for each commander profile.
- Live unlocks appear in the event feed and use the existing Toast HUD notification system.
- Achievement icons render in a dedicated emoji column in unlock toasts instead of being lost in the standard monospace message font.

### Achievement Centre

- Added an **ACHIEVE** page to the main navigation rail.
- Added a searchable and filterable catalogue showing unlock state, category, progress, points, descriptions, and unlock times.
- Added master tracking and unlock-notification controls.
- Added individual category packs so unwanted achievement groups can be disabled per commander.
- Added manual unlock, individual reset, full-profile reset, and test-toast controls.
- Large catalogue updates are rendered in batches to keep the native Tk interface responsive.

### App Responsiveness

- Coalesced queued event-feed and journal-history updates so a burst of journal events produces one dashboard render instead of rebuilding the full history canvas once per event.
- Hidden dashboard streams now retain their data without redrawing widgets behind the panel currently in use.
- Trade and Mining stop performing recurring UI refresh work while their embedded pages are hidden and refresh when reopened.
- Mining ignores unchanged cargo/status snapshots instead of rebuilding every table repeatedly.
- Reduced idle heartbeat-overlay redraws while preserving immediate pulse and stalled-watcher feedback.

### Migration and Journal History

- Added legacy state import for both the original Node achievement system and the later Python version.
- Legacy unlocks, counters, unique sets, distance, playtime, and other compatible progress are merged into the active commander profile.
- Added a full journal-history rebuild for calculating progress from existing Elite Dangerous journals.
- History rebuilds remain silent, preserve live events received during the scan, and restore the previous state if a rebuild fails.

### Packaging

- Bundled the achievement catalogue into packaged VoidCompass builds.
- Added indexed event matching so journal events only evaluate relevant achievement definitions instead of scanning the entire catalogue.

### Version

- Bumped the app version to **4.3.2**.
