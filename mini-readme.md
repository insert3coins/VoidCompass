# VoidCompass // UPDATE LOG

## v4.6.1 // Traffic-Aware Compass Intelligence

- Compass now consumes the same EDSM day/week/total traffic shown on the HUD and retains it per remembered system. Prior traffic suppresses contradictory whole-system `UNDISC` state, alerts, and voice lines, while genuine first discoveries of individual bodies remain part of its exploration memory.
- The Compass AI Intelligence State now shows how many travelled systems it remembers plus the current system's traffic context.
- Compass now announces newly scanned Earth-like, water, ammonia, and terraformable worlds with class-specific personality variants, remembers each unique valuable body, and grows longer-term high-value survey references without repeating detailed scans or startup history.
- The Dashboard's Current Flight card now shows live route progress as remaining NavRoute jumps, with explicitly labelled visited/total progress for saved waypoint routes and a clear inactive or complete state—without restoring the removed graphical pip strip.
- Notable and high-value body rows now live exclusively in the persistent Survey Status overlay; the temporary System Info overlay no longer duplicates the local list or Spansh Earthlike, Water World, Ammonia World, and Terraformable fallback tags.
**Release Date:** 2026-Jul-13

## v4.5.9 // Autonomous Compass Intelligence

- Compass AI now has a violet `AI` category in the Live Event Timeline. It posts one compact online brain summary, then only meaningful mood, relationship, learned-habit, expedition, and memory-capacity milestones; routine voice lines and ordinary learning stay out of the feed.
- The journal heartbeat now gives a larger violet AI pulse whenever Compass learns from a live event or delivers a cockpit callout. Its normal journal pulse continues underneath and cannot immediately overwrite the short AI activity indication.
- Compass exploration awareness now covers system honks and detected body totals, unique completed FSS surveys, biological/geological signal bodies, Nav Beacon scans, and unique DSS surface maps including efficient-probe results. Per-system memory retains survey depth without turning routine scans into feed spam.
- Compass now builds bounded operational knowledge across missions, combat, trade, mining, Engineering, Odyssey ground activity, career progression, crime/legal history, Powerplay/BGS, fleet carriers, colonisation, ships/modules, squadrons, and community goals. It learns top recurring targets, commodities, minerals, blueprints, factions, settlements, and outcomes while keeping only compact domain summaries; each newly understood gameplay domain appears once in the AI feed.
- Elite's `LoadGame` and `Shutdown` journal events now form Compass's preferred session lifecycle. `LoadGame` starts or enriches one known flight session, while `Shutdown` closes it and posts/speaks one whole-gameplay debrief; automatic activity start and application close remain duplicate-safe fallbacks when either journal boundary is absent.
- Notable bodies now remain in the persistent Survey Status overlay as scan data arrives, using shared valuable-world, terraformable, biological-signal, icon, and reward rules. Completed notable bodies no longer disappear with the temporary System Info timer, while ordinary completed bodies still clear from Survey Status.
- Survey Status body labels now combine the compact orbital designation with the known planet class, such as `A 2 · Water world` or `4 b · High metal content · TF`, so the persistent list identifies both the body number and what kind of world it is.
- Survey Status now hides immediately on every live `StartJump` event and cancels any queued stale scan refresh, preventing the departing system's bodies from reappearing during supercruise or hyperspace.
**Release Date:** 2026-Jul-13

### Voice Packs
*   Added eighteen optional Piper neural voice choices with native download progress, pinned SHA-256 verification, voice selection, volume, testing, and per-commander controls under **Settings → Voice**.
*   Expanded the catalogue with additional British and American voices plus Australian, New Zealand, and Irish accents selected from Piper's shared VCTK multi-speaker model.
*   Voice synthesis and Windows playback run in the background and remain disabled until explicitly enabled.
*   Added an optional persistent audio cache for repeated callouts, including live file/size reporting and a **Clear Cache** action. When disabled, generated WAV files are deleted immediately after playback.
*   Voice changes now become active for live callouts immediately and are saved to the commander profile without requiring a separate **Save Settings** click.
*   Added a consistent cockpit-intelligence personality with non-repeating phrase variations across navigation, ship telemetry, exploration, biology, Engineering, and objectives. The assistant stays calm and personable during routine flight while retaining concise, authoritative safety warnings without increasing callout frequency.

### Callouts
*   Added low-noise safety announcements for route-aware fuel and scoop risks, dry star stretches, interdictions, heat, shields, hull, suit hazards, rebuy coverage, and unsold data risk.
*   Added navigation and exploration announcements for entered systems, route waypoints, route completion, undiscovered systems, biological completion, Codex discoveries, and clear-to-sample guidance. Jet-cone supercharge remains a visual notification without a repetitive voice callout.
*   Added Engineering-ready, massacre-stack-complete, and best trade-route result announcements, each controlled by callout category settings and one-shot cooldowns.

### Compass Memory
*   Added a bounded, entirely local autobiographical memory for the cockpit assistant, stored separately in each commander's profile as `cockpit_ai_memory.json`.
*   Compass learns recurring systems, ships, body scans, first discoveries, completed biological species, journeys, missions, market activity, mining, close calls, losses, and notable shared milestones from live journal events.
*   Familiar systems and repeated biological analyses can now produce contextual remarks based on real shared history; startup journal replay is excluded so old events are never learned twice.
*   Added evolving relationship and activity traits such as Explorer, Exobiologist, Trader, Miner, and Traveller, derived from actual play rather than a fixed personality choice.
*   Added **Quiet**, **Balanced**, and **Chatty** personality levels plus a live learned-history summary and a confirmed **Forget Learned History** action under **Settings → Voice**.
*   Compass now evolves its spoken vocabulary through Newly Activated, Developing, Familiar, Trusted, and Veteran stages. Each stage unlocks a larger phrase pool, warmer shared-language, behavioural observations, restrained humour, and long-term callbacks; personality level can slow or accelerate those unlocks while direct safety wording remains available throughout.
*   Added per-commander memory-cap controls for systems, biological species, ships, and notable episodes. Defaults remain 300/200/30/80, each category can be reduced to zero, and guarded maximums allow up to 5,000 systems, 2,000 species, 250 ships, and 1,000 episodes; reducing a cap immediately retains the most useful records and prunes the excess.
*   Added temporary operational moods that react to discovery, biology, danger, loss, and safe docking, then decay naturally back to calm instead of becoming permanent personality changes.
*   Added learned flight habits and contextual predictions for thorough surveying, fast travel, biological fieldwork, trading, mining, thermal risk, route experience, and accumulated discoveries.
*   Added intention memory for active routes, unsold exploration data, biological sampling, missions, and pinned Engineering work so unfinished business survives as structured context.
*   Added automatic expedition detection from journey length and displacement, dedicated jump/discovery/bio milestones, resumable expedition records, automatic completion on docking, and editable expedition names.
*   Added bounded session history and spoken docking debriefs covering jumps, scans, biological analyses, missions, hazardous events, and the current operational mood.
*   Added adaptive contextual timing: Quiet/Balanced/Chatty control remark priority and spacing, repeated topics are coalesced, and personality chatter is suppressed while Compass is alert or shaken.
*   Added an integrated **Compass AI** settings page showing mood, habits, intentions, favourite systems and ships, sessions, and expedition state, plus a notable-memory browser with pin, edit, delete, and refresh controls.
*   Compass remains autonomous and journal-driven: no microphone, push-to-talk, chat prompt, external AI service, or Ollama dependency is used.

### Dashboard
*   Removed the duplicate graphical route strip from the Dashboard flight card—the CURRENT/DEST pips, route state, and distance remain available in the dedicated Navigation HUD.

### Navigation HUD CRT
*   Added configurable phosphor text glow, scanline strength, edge vignette, stable noise texture, route-line bloom, and a lightweight phosphor shimmer without a full-width refresh bar sweeping down the display.
*   Added **HUD Effects** settings for enabling CRT rendering, selecting Subtle/Standard/Strong intensity, and disabling the phosphor shimmer independently.

### Biological Survey HUD
*   Expanded the existing Survey Status strip into a system overview showing unfinished DSS work, biological completion counts, and estimated exobiology values per body.
*   Approaching a bio-bearing body now switches the same strip to a focused organism view with completed samples, active samples, DSS-detected genera, predicted genera, and reward ranges.
*   Wired the packaged SrvSurvey Codex biological catalogue into VoidCompass, including more than 800 species/variant entries and current reward values; the previous built-in value table remains an offline fallback.
*   The focused view keeps the existing sampling-distance guidance and returns to the system overview when leaving the body—no additional overlay window is created.
*   Survey system and organism lists expand to show every available row instead of collapsing additional entries behind a `+more` count.

### Version
*   Updated app version to **4.5.7**.

## v4.4.4 // Interactive Galaxy Details
**Release Date:** 2026-Jul-13

### Galaxy Drill-Downs
*   Made the current system, factions, Powerplay, squadron, conflicts, and Community Goals interactive inside **GALAXY OVERVIEW**.
*   Added expanded in-page detail cards with full available journal values, influence movement, reputation, faction states, conflict scores and stakes, Powerplay progress, and Community Goal participation.
*   Retained explicit **OPEN BGS HISTORY** and faction-watch actions inside the expanded views without adding pop-up windows.

### Version
*   Bumped app version to **4.4.4**.

## v4.4.3 // Simplified Trade + Market Maintenance
**Release Date:** 2026-Jul-13

### Trade Interface
*   Consolidated the Trade workspace into five primary areas: Routes, Markets, Local, Tracking, and Database.
*   Grouped Road to Riches under Routes; Radar, cargo, commodity, and station tools under Markets; and watchlists and analytics under Tracking.
*   Integrated full database controls directly into Trade and reduced the separate Market Builder to an isolated worker process.

### Market Database
*   Changed normal price maintenance to live EDDN and visited `Market.json` updates after the initial full Spansh baseline.
*   Full rebuilds now preserve locally newer prices, journal-discovered systems and stations, trade history, and watches.
*   Added market freshness and stale-station status information while retaining occasional manual full rebuilds.

### Version
*   Bumped app version to **4.4.3**.

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
