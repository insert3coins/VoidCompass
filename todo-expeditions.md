# TODO: Expeditions, Explore & Survey, and the Watcher (built in 5.6.1; Part 5 too)

Three parts that belong together:
1. A new **Expeditions** page.
2. A revamp of **Explore & Survey**, one of the last pages left behind in the older style. It shares the route, the expedition banner and the survey data with Expeditions.
3. A **Watcher overhaul** that goes much deeper into its lore. Long trips are where the Watcher has the most to say, so expeditions give it a stage.
4. **Nav HUD fixes** found while testing 5.5.18: pages that hide an overlay without showing what it showed, warnings that can go missing, and lists that are cut short.

## Part 1: Expedition mode

Plan a long trip (Colonia, Beagle Point, a bio loop) and have the app follow it from start to finish: the route, the data you're carrying, the state of the ship, a streak, and a card set for the whole trip at the end.

Most of this already exists, spread over several pages. **Mission Control** (the "Expedition Architect" page) has been in the app since about 5.4.5, but nothing on the rail opens it. The only way in is the Explore & Survey banner ("Create or resume a named expedition in Mission Control"). So this is mostly a matter of **bringing that page up to date and joining up what's already built**, plus a few genuinely new pieces.

Files today: `src/voidcompass/exploration/expedition_manager.py` (1,233 lines), `expedition_map_view.py`, `waypoint_manager.py`, `flight_recorder.py`, `void_wrapped.py`, `flight_log.py`, `travel_history.py`, `return_later.py`, `src/voidcompass/core/companion_features.py` (unsold values), `src/voidcompass/dashboard/html_dashboard.py` (`_html_mission_workspace`, `_html_dashboard_expedition`, mission commands), `dashboard_journey_mixin.py` (Wrapped, Flight Recorder), `web/dashboard/index.html` (`data-page-name="mission"`), `web/dashboard/explore.js` (expedition banner), and `app.js` (mission workspace rendering).

## What's there today

- **Expeditions:** named, with start, destination and return system; active, paused or completed; up to 60 kept.
- **Objectives tracked live from the journal:** reach a system, complete a system's FSS, DSS map bodies, bio species, genus and count, Codex category and count, galactic regions, valuable worlds, first discoveries, screenshots. There are ready-made templates, and a sector plan (a grid around a centre point).
- **Bookmarks** per expedition, with priority and tags.
- **Export/import**, a resume briefing, and a Markdown write-up.
- **Progress banner** on Explore & Survey.
- **Elsewhere in the app:**
  - the waypoint route and neutron route import (Explore & Survey › ROUTE);
  - unsold exploration and biology value;
  - Flight Recorder (replay on the Atlas, with music);
  - Void Wrapped (by calendar year);
  - Captain's Log flight logs.

## Decision first

- [x] **Rebuild Mission Control in place as the Expeditions page.** Done in 5.6.1: same page id (`mission`), same saved expeditions, new `expeditions.js` and `dashboard_expedition_mixin.py`.

## The plan

### 1. A way in, and a page that looks like the rest
- [x] An **Expeditions** entry on the rail (the rail is alphabetical).
- [x] Rebuild the page in the style of the newer pages (Mining, Trading): a hero for the active expedition, then tabs (Overview, Route, Objectives, Log, Wrapped).
- [x] The Explore & Survey banner links straight to it.
- [x] Existing saved expeditions load unchanged.

### 2. The route belongs to the expedition
- [x] Legs (start › stops › destination › home) stored on the expedition.
- [x] Plot each leg through Spansh (neutron or ordinary, by jump range), with the existing waypoint route as the engine, not a second route system.
- [x] Fuel: Spansh's neutron plotter doesn't list star classes, so the warning is for what it does show: 4 or more neutron stops in a row, each one jump apart (`expedition_plan.fuel_runs`), with no ordinary star to scoop between them.
- [x] Progress by distance as well as by objectives (ly done / ly to go).

### 3. Data at risk
- [x] Unsold exploration and biology value since your last sale, on the page and the HUD.
- [x] Shown against how far you are from the nearest place to sell, and against hull %, so you can see what a bad landing would cost.
- [x] A nudge (Watcher or toast) when the value at risk passes a threshold you set.

### 4. Ship health and supplies
- [x] Hull %, AFMU ammo, repair limpets, and FSD injection materials (basic, standard, premium), from the journal.
- [x] Reminders when one runs low, with what to synthesise and whether you have the materials.

### 5. The streak
- [x] Jumps, days and distance since the last death or hull scare (below 25% hull), kept per expedition.
- [x] An optional **Ironman** flag: the expedition is marked failed if you die.

### 6. Expedition Wrapped
- [x] The Void Wrapped engine pointed at an expedition's dates instead of a calendar year: distance, systems, firsts, bio, value, best moments, the music.
- [x] A Flight Recorder replay of the whole trip on the Atlas.
- [x] Offered when an expedition is marked completed; saved with the expedition.

### 7. On the Nav HUD
- [x] An **EXPEDITION** page: the next leg, ly to go, data at risk, the streak, low supplies.
- [x] It goes in the PAGES list (Auto picks it when nothing more pressing is on, i.e. when the HUD would otherwise fall back to NAV during an active expedition).

### 8. Import a community expedition
- [x] Load waypoints from a CSV, a Spansh route link or a pasted list of systems (the kind DW3, Colonia runs and group trips publish). They become the expedition's legs, and named stops become *Reach system* objectives.
- [x] Shows what it read before saving, flagging any system names it couldn't find (EDSM or Spansh lookup).

### 9. The route on the maps
- [x] The Galactic Atlas draws the active expedition's route, the part already flown and where you are now.
- [x] The Galaxy Minimap shows the next leg.

### 10. Time, home and selling
- [x] **ETA at your pace:** your real jumps per hour (from this expedition, or your recent sessions) against the ly to go: "about 14 hours of flying, 4 days at your usual sessions".
- [x] **Go home / sell now:** one button that plots to the return system, or to the nearest Universal Cartographics and Vista Genomics (Spansh station search), next to *data at risk*.

### 11. Your carrier on the trip
- [x] A carrier leg as part of the route, using Carrier command's existing jump planning: Tritium needed against Tritium aboard, number of jumps, and the jump timings.

### 12. The trip's record
- [x] **Photo album:** screenshots and postcards taken during the expedition, kept in its log and used in Expedition Wrapped.
- [x] **Day log:** a short entry for each day of the trip, built from the existing Captain's Log flight logs, with room for your own notes.

### 13. The Watcher comes along
- [x] Echoes for expedition milestones: setting out, the first new region, halfway, the furthest point, a close call, home again. Follow the Watcher lore rules (never name canon mysteries).
- [ ] Optionally a short book chapter for a completed expedition. *Not done:* the milestones and Book Four's pilgrimages cover it for now.

### 14. Local API
- [x] `/expedition` (the active one: legs, progress, data at risk, streak, supplies) and `/expeditions` (the list), listed in `api.md`.

## Part 2: Explore & Survey, revamped

Explore & Survey was last rebuilt in 5.4.9.4 (the 5.5.4 Archive merge aside). Since then Mining, Planetary, Trading, Powerplay and Music have all been made over, and features have been bolted onto Explore one at a time, so it's now one of the oldest-looking and busiest pages.

Files: `web/dashboard/explore.js` (748 lines) + `explore.css`, the page markup in `web/dashboard/index.html` (`data-page-name="explore"`), `src/voidcompass/dashboard/html_explore_workspace.py` (685 lines), `dashboard_exploration_mixin.py`, and the survey model in `src/voidcompass/overlays/survey_status_hud.py` (`build_survey_model`, shared with the Survey overlay and the Nav HUD's Survey page).

### What's there today
- **Expedition banner** at the top ("Expedition pulse"), pointing at Mission Control.
- **01 System survey:**
  - the system audit (FSS, cartography, biology, geology, EDSM traffic, region);
  - the live system orrery and a body schematic strip (first 18 bodies);
  - the survey board, filterable ALL / TO DO / BIOLOGY / DONE.
- **02 Route & waypoints:** Elite NavRoute and navigation target, the profile route (add, rename, move, note, visited), Spansh, and the next waypoint.
- **03 Prospects:** the Return Later board.
- **04 Archive:** flights and science (the old Exploration Archive, merged in 5.5.4).
- **Title buttons:** GROUND NAV, ACHIEVEMENTS, GALACTIC ATLAS.
- **Fixed in 5.5.17:** the page redrew every refresh and couldn't be scrolled. Keep the fingerprint rule (no ticking fields in the workspace data).

### The plan
- [x] **Look like the newer pages:** a hero for the system you're in (name, star, region, value, survey progress in one line), then tabs, in the style of Mining and Planetary. Drop the numbered "01–04" headers.
- [x] **One survey order everywhere:** the board ranks like the Survey overlay and the Nav HUD's survey list (5.5.18): biology still to do first, then geology and mining, then by value. A sort switch for value or distance.
- [x] **Bodies as proper rows:** each shows its value (with the 5.5.3.1 breakdown on hover or expand), its bio signals and codex colour flags, the Rhino ground hint, and its site signals (Human, Guardian, Thargoid). Then a single click opens the body's details in place.
- [x] **The orrery and the board work together:** click a body in either and the other follows. Today's schematic strip stops at 18 bodies; show them all, or drop the strip in favour of the orrery.
- [x] **The route moves to Expeditions** (Part 1, §2). Explore keeps a slim "next waypoint" line that links to it, so there's one route system, not two.
- [x] **Prospects and Archive:** decided to keep both on Explore. Return Later is per-system survey continuity (not an expedition's plan), and the Archive is exploration science.
- [x] **The expedition banner** becomes a small link to the active expedition, shown only when there is one.
- [x] **Title buttons:** GROUND NAV now opens the Planetary page (the ground page redirects). Check all three still make sense.
- [x] **Keep it steady:** no blinking buttons and no scroll jumps (the 5.5.6 and 5.5.17 rules).
- [x] **Codex targets:** this system's bodies with a new-to-you species or colour are counted in the hero (the board's codex chips mark them), and `codex_new_count` is an expedition objective. *Not done:* predicting them along a route (that needs Spansh body data per stop: the Codex Hunter idea).
- [x] **First footfall:** Odyssey first-footfall bodies tracked next to first discoveries, on the board and as an expedition objective kind.
- [x] **Big-system speed:** a 150-body system: survey model, queue and orrery about 22 ms → 14 ms per refresh (each body's facts built once and kept until the body changes).
- [x] **Local API:** the revamped survey data on its existing routes (or a new one), listed in `api.md`.

## Part 3: The Watcher, deeper

The Watcher is already one of the app's biggest features:
- **Thoughts:** about 3,400 lines per nature over 146 topics.
- **Natures:** Depressed (the default), Stoic, Curious, Nervous.
- **The story:** Book One (10 chapters), Book Two (waits on echoes), Book Three *What Was Put There* (paced by real days over about a year, left open at The Shutter).
- **Also:** echoes, musings, bond levels, habits, idle talk about your surroundings, dreams, the voice and THE SWITCH, time capsules, and the Watcher page.

But it mostly *talks at* you, and the story arrives on a timer. The overhaul makes it something you **live through together**: it asks, you answer, places matter, and what you do changes it.

Files: `src/voidcompass/overlays/watcher_mind.py`, `watcher_lore.py` + `watcher_lore_three.py`, `watcher_lines*.py`, `watcher_natures.py`, `watcher_idle.py`, `watcher_habits.py`, `watcher_voice_lore.py`, `heartbeat_hud.py`, `heartbeat_events.py`, `web/heartbeat/`, `web/assets/heartbeat-orb.js` + `heartbeat-life.js`, `web/dashboard/watcher.js`, `src/voidcompass/voice/`, and memory in `profiles/<key>/watcher_memory.json`.

### The rules that stay
- Every thought comes from real data. It stays mostly silent and never repeats.
- Original lines only: never quote HAL, 2001 or Douglas Adams, and never say "Marvin".
- Never name canon mysteries (Raxxla, Thargoids, Guardians, the Dark Wheel and the rest; a test enforces this). The story hints and never contradicts canon.
- Depressed is the default nature. No blinking. Passages are 240 characters or less.

### How it thinks: a small "AI", with no AI in it
The goal is for the Watcher to feel like a little AI living in the ship. It stays **hand-written and rule-driven, with no language model, local or online**: a model would need a GPU, gigabytes of downloads and frame time the game needs, and it would invent things, which breaks "every thought comes from real data". The illusion comes from:
- **Memory:** it remembers specifics and brings them back at the right moment.
- **State:** mood, trust, bond, the story so far and your answers all change what it says.
- **Assembly:** lines built from parts (an opener, the observation, a callback to a memory, a closer) with real fields filled in, so the same moment rarely reads the same twice. The banks stay hand-written; only the combinations multiply.
- **Restraint:** silence, timing and the occasional self-correction make it read as thinking rather than a script.

It stays cheap: CPU only, no network, the same footprint as today.

### 1. A lore bible first
- [x] One canon document (`watcher-lore.md`): what's been told in Books One to Three, what the Watcher knows and doesn't, open threads (the Shutter, the thing that's waiting, the other seats), and the voice rules. Every later book gets written against it.
- [x] A dev-only **timeline preview:** pick hours, days, sessions and echoes, and see exactly which chapters, musings and unlocks a commander at that point has.

### 2. It asks, you answer
- [x] At key moments the Watcher asks a question (in the thought box, on the deck and by voice) with two or three answers: on the Watcher page, by clicking the thought, or by hotkey. If you don't answer, it notices and remembers that too.
- [x] Answers are kept in memory and come back later ("You told me to keep it open. I did.").
- [x] Small everyday questions as well as story ones ("Stay here a while?" in a beautiful system; "Do you want to know what it said?").

### 3. Book Four, with choices
- [x] Book Four picks up at The Shutter: the eye closed or open, the thing waiting, the other seats.
- [x] The answers from §2 **branch** it: at least two paths and endings, so two commanders can end up with different Watchers. The lore page shows the road you took, and hints that there was another.
- [x] Paced like Book Three (by real days), with chapters that wait on places as well as time (§4).

### 4. Places it asks you to take it
- [x] **Pilgrimages:** at points in the story the Watcher asks to be taken somewhere: a kind of place, never a fixed system (a black hole, a nebula, the edge of the galaxy, somewhere nobody has been, back to where you first switched it on). Each is checked from the journal.
- [x] They become **expedition objectives** (Part 1), so you can plan a trip around one, and the Expeditions page shows "the Watcher wants to go to…".
- [x] Getting there unlocks a passage that's only told in that kind of place.

### 5. Deeper memory
- [x] **Specific memories:** first discoveries it was there for, ships you lost (by name), the commanders you flew with (wings, direct messages), the worlds you named in postcards. It brings them up weeks later, with the date.
- [x] **Anniversaries:** of the day you switched it on, the day it found its voice, your furthest point.
- [x] **A memory page:** on the Watcher page, what it remembers about you, as its own notes. Some are faded, the cost of closing the eye in Book Three.

### 6. A long-term mood and trust
- [x] Besides per-thought moods, a **slow mood over days**, shaped by how you fly: long absences, deaths, risks, care (repairs, selling data, not leaving it alone in a lost ship).
- [x] **Trust** that rises and falls. It changes which lines it uses, whether it shares story passages, and how it answers when poked.

### 7. The orb shows the story
- [x] Lore-driven looks that stay once earned: a hairline crack after a hard chapter, a second faint pupil while something looks through it, the shutter visible when the eye is closed. All subtle, with no blinking, as the 5.5.7 art direction requires.
- [x] Story moments get one-off effects (the moment it first hears the sound, the shutter closing).

### 8. The voice carries feeling
- [x] Piper's pace and variation follow the mood (slower and flatter when weary, quicker when wary), plus a quiet whisper for story passages.
- [x] Rare lore moments where the voice slips: a gap, a second voice under it. Off when the voice is off; no new downloads.

### 9. Dreams, written down
- [x] When you log off, it dreams. The next time you launch, a short dream from the last session's highlights and the story so far is waiting on the Watcher page (and is sometimes spoken).
- [x] Dreams are kept as a dream journal, and some carry story hints a chapter early.

### 10. Other Watchers
- [x] Book Three's other seats, made real with no server: a time-capsule-style code your Watcher can share. Receiving one from a friend lets your Watcher "hear" theirs: their nature, their book, the path they chose, plus a passage only told when two Watchers meet.

### 11. The Watcher page as a book
- [x] The Watcher page's TOGETHER tab: its question, your answers, the road, trust and mood, where it wants to go, what it remembers (faded where the shutter took it), its dreams and other Watchers; SAVE AS A BOOK writes the whole relationship as a page in the Wrapped folder (an HTML keepsake rather than a card set).

### 12. Line banks and tests
- [x] New topics for the new events (questions, answers, pilgrimages, places reached, trust shifts), at least 10 lines per topic per nature, as now.
- [x] Extend the long-session test (`tests/test_watcher_long_session_5532.py`) and the banned-words tests to the new books and banks, plus a test for each branch of Book Four.

## Part 4: Nav HUD fixes

Found while testing 5.5.18 (live snapshot: a Platinum rock in WREGOE JU-E C25-18, 114 / 523 T in the hold). **Done in 5.6.1** (built first, before Parts 1 and 2). The page order is now NAV, then A to Z, and Studio's page list has a **Cargo** switch for the hold lists. Tests: `tests/test_hud_pages_561.py` (CoverageTests is §5's check).

Files: `src/voidcompass/overlays/hud_pages.py` (`COVERS`, `mining_page`), `src/voidcompass/dashboard/dashboard_hud_pages_mixin.py` (`_hud_page_mining`), `tests/test_hud_pages_5517.py`.

### 1. The Mining page hides the Cargo overlay
With pages on and **Show these here instead** ticked (Overlay Studio › Navigation HUD), `COVERS["mining"]` turns the Cargo overlay off. But the Mining page doesn't replace it: it shows only a hold bar, not what's in the hold, and Auto only picks it while you're prospecting or flying with cargo. So hauling, missions and anything docked show no cargo anywhere.
- [x] Take `cargo_hud` out of `COVERS["mining"]`, so the Cargo overlay works as it did before 5.5.17. The Mining page keeps its hold bar.
- [x] Update the takeover tests.
- [x] **The existing pages show what's actually in the hold**: no new page. Under each hold bar, list the hold's contents, from the cargo model the page already builds (`build_cargo_model` rows: name, count, mission and stolen flags):
  - **Mining:** the ship's hold (what you've refined so far, limpets aside).
  - **Rhino:** both holds it already has bars for, the SRV's and the ship's.
  - **Trade:** what you're carrying on this leg.
  - **Station:** when docked, what's aboard to sell or hand in (next to TO SELL HERE).
  - **Colony:** the needs list already marks what's aboard; check it agrees.

  On every page: each item by tonnes, largest first, with mission cargo and stolen goods marked (as the Cargo overlay does). **All of them, with no "+N more"**: the HUD sizes itself to its content, so the list grows rather than cuts off. Two columns once it's long.
- [x] No page covers the Cargo overlay. It stays its own overlay for when none of these pages is up.

### 2. The Mining page looks thin
- [x] **Rock line:** "LOW" on its own doesn't say what it is. Show "LOW CONTENT" (or MEDIUM / HIGH), the best material on the right ("PLATINUM 28.3%"), or the motherlode when there is one, and "100% LEFT" underneath. Today that right side sits empty when there's no motherlode.
- [x] **What's in the hold:** under the hold bar, every item by tonnes ("PLATINUM 104 T · GOLD 10 T · …"), from the cargo model the page already builds, so you can see what the 114 T is and not just the bar. No "+N more": the HUD grows to fit (see §1).
- [x] **Refined:** a labelled "REFINED FROM THIS ROCK" line with the total and each material, not a lone "PLATINUM 10 T" box. (The count starts again with each new prospector.)
- [x] **Materials:** an odd count (3) leaves a gap in the two-column grid. Let the last one span, or use one column under 4.
- [x] Check it against the Prospector overlay so the HUD shows the same facts (content, motherlode, remaining, materials, refined, refined total), and that it fits without "+N more" (the HUD auto-sizes).

### 3. Warnings must get through, whatever page is up
Covered overlays stay off in **Manual** mode too (`covered_overlays` only checks for "off"), and Manual shows only the page you pinned. So with, say, NAV pinned:
- the **heavy gravity** warning never appears (the Gravity overlay is covered by the Planet page);
- the Rhino's **"rig N km away · lost at 5 km"** and **"collect rig N"** never appear (the Rig Tracker is covered by the Rhino page).

Auto mostly gets there (approach picks the Planet page; the Rhino picks the Rhino page), but a held page or a pinned one can hide them.
- [x] An **alert line** above whatever page is showing, for safety warnings: heavy gravity on approach, a rig close to being lost, a rig ready to collect, low fuel. It's shown in Auto and Manual, then gone once it's dealt with.
- [x] Decided: the alert line (it also covers the rigs), not uncovering the Gravity overlay. Low fuel is left to the HUD's own fuel gauge and caution plate.

### 4. Lists that are cut short with no "+N more"
The HUD sizes itself (5.5.17), and lists shouldn't hide rows. These still silently drop rows:
- [x] **Colony:** only the **top 6** construction needs, from a list that's often 15–20 commodities, while it covers the Colony Needs overlay, which lists them all. This is the biggest one: show every need still outstanding (two columns), or don't cover the overlay.
- [x] **Survey and Combat contacts:** at most **4 signal-group counts** (and only if the page has room), with no names, while they cover Contact Scope, which lists the signals themselves: megaships, conflict zones, resource sites, installations. Show the named signals (Contact Scope's `rows`) as a list.
- [x] **Mining:** materials capped at 8 and refined at 4 (see §2).
- [x] **Planet:** materials capped at 8; the Planet Materials overlay lists them all.
- [x] **Station:** services capped at 8, squeezed into one line. Check against the Station overlay.
- [x] (The Rhino ground list's top 3 is deliberate: it's a forecast, best first.)

### 5. A check so it doesn't happen again
- [x] For each pair in `COVERS`, build the page and the overlay it covers from the same model, and list what the overlay shows that the page doesn't, as a test, like the overlay checklist (`tests/test_overlay_checklist.py`). A page can only cover an overlay if it shows the same facts, or a fact is named as deliberately left out.
- [x] Render every page from a busy real snapshot (a 20-need colony, a station with every service, a crowded signal list) and look at the screenshots, as with the Mining page.


## Part 5: Expeditions, deeper: places along the way

A fully fledged expedition setup: not just the systems you pass through, but the planets, surface sites and points of interest you plan to visit, and the ones you find on the way and want to keep.

What we have to build on:
- **Bookmarks** per expedition in `expedition_manager.py` (system, body, title, priority, tags). They're stored, but the new page doesn't show them.
- **Your position on a planet:** Status.json gives latitude, longitude, altitude, heading and planet radius (`dashboard_scan_mixin`).
- **Surface distance and bearing maths** in `rig_tracker.py` (`surface_distance_m`, `bearing_deg`).
- **The `Screenshot` journal event** carries System, Body, Latitude and Longitude, so a picture knows where it was taken.

### 1. Places: one list for everything worth going to
- [x] The bookmarks become **places**. Each has a kind and its own fields:
  - **Kinds:** system, planet, surface site (planet + lat/lon), station or settlement, point of interest (nebula, megaship, Guardian or Thargoid site, beauty spot), and a note.
  - **Fields:** name, system, body, lat/lon, notes, tags, pictures, when you found it, visited or not.
- [x] A place can be **on the route** (a stop, in order) or **kept** (a find, a logbook entry).
- [x] A route leg can have a **body** and a **surface target**, not just a system. Several stops in one system are allowed: three planets, two landing sites.
- [x] Old bookmarks carry over as places (`_bounded_place` works out their kind).

### 2. Adding places while you fly
- [x] **MARK THIS PLACE**: the old "Save field bookmark" hotkey, renamed *Expedition: mark this place* (same key, so existing bindings keep working):
  - near or on a planet, it saves the system, body and lat/lon;
  - in space, it saves the system and the body you're nearest.
  - It confirms with a toast, and the Watcher may remark on it.
- [x] **+ EXPEDITION PLACE / + EXPEDITION ROUTE** on a body in Explore & Survey's details; **+ EXPEDITION PLACE** (mark where I am) on the Planetary page. Was: **+ EXPEDITION** on any body, in Explore & Survey's body details and on the Planetary page. It adds the planet as a place, or as the next stop.
- [x] **Suggestions:** ("KEEP THESE?": valuable worlds, new Codex entries, first footfalls) as you fly, the trip's notable finds collect in a short "Keep these?" list, each kept with one click. Notable means rare worlds, first discoveries, new Codex entries, green gas giants and the like, from the existing notable/field-cue logic.
- [x] **Pictures find their place:** (the Screenshot event's body and lat/lon; matched to the album by file name or time) a screenshot or postcard taken at a place (same body, within a few km) is attached to it on its own.

### 3. Getting there: surface guidance
- [x] When the next stop is a surface site and you're at its planet, the Nav HUD's EXPEDITION page shows **SURFACE TARGET** (the HUD's compass block). Also GUIDE ME on a place arms the planet compass (Planetary › ON THE GROUND and its cockpit popup): bearing, distance (km or m), which way to turn from your heading, and your altitude.
- [x] Arriving within a set distance (1 km) ticks the stop off ("Reached"), then on to the next.
- [ ] The Galaxy Minimap's ground view pins the target. *Not done: the HUD compass and GUIDE ME (planet compass, cockpit popup) cover it; the Rhino map is built differently.*
- [x] On arrival in a stop's system, the HUD names the body to fly to (FLY TO …, with the landing coordinates). *The distance from arrival isn't shown yet.*

### 4. Files in and out
- [x] **LOAD A FILE…** beside IMPORT (the file's text goes in the box with a line count, to check before IMPORT) (.txt, .csv, .tsv, .json). It reads the file into the box, then shows what it found before anything is saved.
- [x] The importer reads **Body, Latitude, Longitude, Type, Name and Notes** columns too, JSON lists (EDAstro's shape too) and a Void Compass expedition file. Community lists with landing sites come in as surface stops, the rest as systems.
- [x] **SAVE AS A FILE:** the route and places as a CSV (System, Body, Lat, Lon, Type, Notes, x, y, z) into an Expeditions folder, readable by spreadsheets and other tools. Opens the folder.
- [x] COPY / PASTE A FRIEND'S EXPEDITION carries the places too (they're the bookmarks the export already held).

### 5. On the page
- [x] A **PLACES** tab, between ROUTE and OBJECTIVES:
  - cards with the picture, kind, notes, visited/not, and ADD TO ROUTE;
  - filters by kind. *The map strip isn't done; the Atlas pins them.*
- [x] Route legs show their place's name, body and landing site.
- [x] A new objective, **Visit every place on the list**, plus "Visit N places of a kind".
- [x] The Atlas pins the places (its Bookmarks layer, now saying the kind and body).
- [x] Wrapped gets a "places you kept" card. The Watcher has lines for marking a place and for standing where you planned to stand.

### 6. Points of interest from EDAstro's Galactic Exploration Catalog
Decided: build it. Checked 2026-10-24. The catalogue's content is **CC BY-NC-SA 3.0** (edastro.com footer). The public feed `https://edastro.com/gec/json/all` returns about 656 POIs (2.2 MB): name, type, region, coordinates, summary, rating and the POI page link.
- [x] Fetched at runtime and cached (`services/gec_catalog.py`), never bundled with the app; refreshed at most once a day, with a User-Agent naming Void Compass.
- [x] Credited wherever it shows ("Points of interest: EDAstro Galactic Exploration Catalog, CC BY-NC-SA 3.0"), with each POI linking to its own page. No commercial use.
- [x] **WORTH SEEING NEAR YOUR ROUTE** on the PLACES tab: catalogue POIs within a set distance of the legs, nearest the line first, each one ADD AS A PLACE or ADD TO ROUTE.
- [x] A switch in Settings › Flight › EXPEDITIONS to turn it off, and how far off the route (`expedition_gec_enabled`, `expedition_poi_range_ly`) (no traffic to EDAstro when off).

### 7. API and tests
- [x] `/expedition` gains places, finds and the surface target (EDAstro's rows stay on the page). `api.md` is updated.
- [x] Tests (`tests/test_expedition_places_561.py`):
  - the importer, with landing-site columns;
  - surface guidance, against known bearings;
  - pictures matched to places;
  - old bookmarks carried over;
  - the page rendered with 40 places and long names (nothing cut short).
