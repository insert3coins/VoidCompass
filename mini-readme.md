# VoidCompass // UPDATE LOG

## v4.6.5 // Accurate Exobiology Tracking + HUD Polish
**Release Date:** 2026-Jul-13

### Fixes
*   Fixed the real root cause behind lingering incorrect bio progress: live `ScanOrganic` journal events never actually carry `Sample`, `IsComplete`, `IsNewEntry`, `IsNewSample`, `BodyID`, or `MaxSamples` fields, despite the app previously assuming they did. Completion and sample progress (1/3, 2/3, 3/3) are now derived from the event's `ScanType` sequence (`Log`/`Sample`/`Analyse`) instead, fixing Survey Status counts that stuck at `0/1`, a silent sample undercount, and Compass's biology-awareness progress capping at `2/3`.
*   Corrected the same flawed assumption in the live bio-sample toast and Compass's own memory tracking, so "Sample n/3" toasts and Compass's biological sample tallies now match what actually happened.

### Navigation HUD
*   Simplified the `BIO`/`VALUE` badges added in 4.6.4 into a single `BIO` presence flag — alert while signals remain unsampled, ok once caught up — since detailed progress and value already live in the Survey Status overlay; removed the redundant `VALUE` badge.
*   Gave the badge row a facelift: badges now pick up the same CRT glow as the rest of the HUD, an ok badge is a solid backlit fill instead of a flat outline, and each state gets a glyph (`●`/`✓`/`○`) for quicker at-a-glance reading.

## v4.6.4 // Living Cockpit Companion
**Release Date:** 2026-Jul-13

### Fixes
*   The Survey Status overlay's `BIO x/y` count no longer sticks at zero after completing organic scans — the overlay is now refreshed on every `ScanOrganic` event instead of only on the next unrelated redraw.
*   The Navigation HUD's `BIO`/`VALUE` badges are no longer static. `BIO` now shows live completed-versus-detected sample progress (`BIO 2/5`) instead of a fixed system-wide signal count, and `VALUE` shows a running credit total of completed organic scans instead of an unrelated valuable-body count.

### Compass Opinions & Anticipation
*   Compass now forms earned opinions about specific systems from real history: a system it has repeatedly had trouble in (heat damage, interdictions, ship loss) gets a wary remark on return visits; a system with valuable finds or first discoveries gets a fond one.
*   Added backtrack impatience — repeatedly bouncing between the same two systems now earns a low-key remark.
*   Added bio-sale anticipation — Compass learns the typical sample count at which you sell biological data and gives a heads-up as you approach it, rather than only reacting after the fact.

### A Living Cockpit
*   Added ambient chatter: occasional unprompted lines during quiet cruising after a long stretch with no journal activity, drawn from a 20-line pool so long sessions do not repeat themselves.
*   Added time-aware session greetings: Compass now recognises "picking back up mid-session," a fresh day, or a long absence, and greets you differently.
*   Added memory callbacks: system opinions now reference the specific remembered event ("I still remember losing a ship here") instead of only an aggregate count, when one exists.
*   Added three independent settings under **Settings → Voice → Compass Memory**: **Ambient chatter while cruising**, **Session greetings**, and **Memory callbacks in system remarks**, each defaulting on and degrading gracefully when off.

## v4.6.2 // Bio-Aware Compass Intelligence
**Release Date:** 2026-Jul-13

- Compass biological awareness now joins journal activity with Survey Status context: it retains bio/geo signal totals, detected and predicted genera, three-stage sample progress, species/body history, reward values, colony spacing, completed analyses, and unique biological Codex records.
- The Compass AI Intelligence State exposes the growing biology model, while only sparse milestones reach the Live Feed or evolved voice lines so routine sampling does not create chatter.

## v4.6.1 // Traffic-Aware Compass Intelligence
**Release Date:** 2026-Jul-13

- Compass now consumes the same EDSM day/week/total traffic shown on the HUD and retains it per remembered system, suppressing contradictory whole-system `UNDISC` state while genuine first discoveries still count.
- Compass now announces newly scanned Earth-like, water, ammonia, and terraformable worlds with class-specific personality variants and remembers each unique valuable body.
- The Dashboard's Current Flight card shows live route progress as remaining NavRoute jumps or labelled visited/total waypoint progress.
- Notable and high-value body rows now live exclusively in the persistent Survey Status overlay; the temporary System Info overlay no longer duplicates them.

## Earlier releases

- **v4.5.9** — Compass AI feed category, AI heartbeat pulse, broad exploration/operational-domain awareness, `LoadGame`/`Shutdown` session lifecycle, persistent notable bodies, combined body labels, and instant Survey Status hide on jump.
- **v4.5.7** — Eighteen optional Piper neural voice packs, low-noise safety/navigation/exploration callouts, and the original bounded local Compass Memory (recurring systems/ships/species, relationship stages, moods, habits, expeditions, session debriefs, memory-cap settings, Compass AI settings page). Native Engineering, Exploration, and Biological Survey HUD improvements including the packaged SrvSurvey Codex catalogue. Added configurable Navigation HUD CRT effects.
- **v4.4.4** — Interactive Galaxy drill-downs for system, factions, Powerplay, squadron, conflicts, and Community Goals.
- **v4.4.3** — Simplified five-area Trade workspace; market database moved to live EDDN/journal maintenance with freshness tracking.
- **v4.4.2** — Galaxy Overview influence tracking, faction watches with low-noise alerts, and BGS History integration.
- **v4.4.1** — Expanded native Engineering page, integrated Galaxy/BGS page, and Commander Companion fleet/mission/jumponium/rebuy warnings.
- **v4.3.4** — Made achievement progress monotonic so journal rebuilds can no longer destroy unlocks; fixed route-achievement resets and playtime-while-not-running; added progress bars.
- **v4.3.2** — Native 1,023-entry journal-driven achievement system with its own Achievement Centre page, legacy migration, and journal-history rebuild, plus general app responsiveness work.
