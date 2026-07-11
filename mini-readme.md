# VoidCompass // UPDATE LOG

## v4.3.2 // Native Achievement System

**Release Date:** 2026-Jul-12

### Integrated Achievements

- Added 1,023 journal-driven achievements covering exploration, exobiology, combat, trade, mining, engineering, travel, ranks, carriers, colonisation, Odyssey activities, and more.
- Integrated the achievement engine directly into VoidCompass. It uses the existing journal watcher and runs inside the main Python application with no webserver, browser panel, Node process, or additional port.
- Achievement progress and settings are stored separately for each commander profile.
- Live unlocks appear in the event feed and use the existing Toast HUD notification system.

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
