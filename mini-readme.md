# VoidCompass // UPDATE LOG

## v5.5.17 // One Overlay to Rule Them All
**Release Date:** 23 OCT 3312 *(Galactic Standard Time)*

### Navigation HUD

* **The Navigation HUD can be your only overlay.** Set *Pages* in Overlay Studio › Navigation HUD and its lower half becomes a page for what you're doing:
  * **NAV:** the route and survey, as before.
  * **JUMP:** the next system while the drive charges.
  * **SURVEY:** what's worth a look while you scan.
  * **PLANET:** gravity, your compass target, samples and materials.
  * **RHINO:** six rig dials pointing at your rigs, the next one to collect, and both holds.
  * **MINING:** the rock you just prospected and what you've refined.
  * **COMBAT:** your target's shields, hull, rank and bounty, plus kills and threats.
  * **STATION / COLONY / CARRIER / TRADE / POWER:** where you're docked, what a site needs, your carrier, your trade route and Powerplay.

  *Auto* follows what you're doing; *Manual* stays on the page you choose. Two hotkeys: *page mode* (auto or manual) and *next page*, and each says what it did on the HUD itself. The overlays a page covers stay off while the pages are on (their own settings are kept, and Studio marks them *IN THE NAV HUD*). Switch each page on or off.
* **The page key goes round every page** you've switched on, not only those with something on them now. A quiet page says what it's waiting for, and the tabs show every page in the round: the ones with nothing on them now are a dim dot.
* **The Navigation HUD sizes itself.** One layout now (the compact one), and it grows to fit: a fuller page, or larger *Small text*, makes it taller instead of cutting text off. *Large* and *Larger* small text also widen it, so the ship's name and the labels have room. Page text is bigger too.
* **The Navigation HUD knows where you are.** New scenes:
  * **Docked:** a station's interior (down its length to the slot, ships leaving), an outpost's open pad on its truss arm, a fleet carrier's deck, or a planetary port.
  * **On foot:** the concourse (its window on the hangar, shopfronts, people about), the hangar (walking to the lift under your ship), a carrier's deck, or out on a planet. The label says CONCOURSE, HANGAR or CARRIER DECK.
  * **FSD cooldown:** the drive ring vents its heat segment by segment while a gauge fills round it.
  * **Rhino:** your rigs standing on the ground with their beacons and lasers, the scanner pinging out, and ore sparkling up from the drill into the hopper.
* **Five more scenes redone:** inside the station (its wall curving overhead with the city's lights, your ship flying in to its lit pad), the map (a holo-table with a route being plotted), the Codex (its four kinds of discovery and a specimen under the scanner), AFMU repair (the module list mending one by one) and system reboot (the ring and power pips coming back), and a planetary port with its ring of pads, ships landing and leaving.
* **Combat page, sharper:** your target follows the scanner (pilot, then shields and hull, then faction, bounty and subsystem), starts afresh on a new target even of the same type, drops a subsystem you let go, names ships the journal leaves unnamed (Mandalay, Anaconda...), and treats WantedEnemy as wanted.
* **Pages show it all:** lists on the HUD's pages (the next system's facts, bodies worth a look, threats, materials) show every row instead of "+4 MORE", and the HUD grows to fit; only past ten rows does it say how many more.
* **A tip, once:** pages are off until you switch them on, so a little after starting the HUD says where to find them (Overlay Studio › Navigation HUD › Pages). It doesn't say it again.

### Rhino mining

* **The Rhino map.** Drive the Rhino on a planet and the Galaxy Minimap becomes a map of the ground round you: your trail, the ship, your rigs with their HERE rings, the next rig to collect (with a line to it), and amber spots where your drill has refined. It glides smoothly as you drive, turns with you or keeps north up, and stays up whenever your rigs are out, on foot or back in the ship. Set it in Overlay Studio › Galaxy Minimap: *in the Rhino*, *in any SRV or on foot*, or *never*.
* **Rhino mining helpers**
  * **Spacing rings:** a ring round each rig (78 m by default), red when you're too close to put down another and green when you're clear.
  * **RIG HERE:** a pin at the nearest spot clear of every rig.
  * **Lost-rig warning:** a warning when a rig is getting too far behind (3.5 km by default, as the game destroys it at 5 km), on the map and the HUD, and a toast once a trip.
  * **COLLECT:** shows on a rig that's had its two minutes.
  * **Scanner range:** the scanner's 2 km reach drawn round you.

  Set the spacing and the warning distance in Overlay Studio › Rig Tracker.
* **Rigs in the order you placed them.** NEXT (on the Rig Tracker, the Rhino map, the HUD's Rhino page and the Mining page) is the next rig in the order you put them down, not the nearest.
* **Rigs the game takes back are forgotten:** past 5 km, or once you leave the planet. Old rigs no longer bring up the Rhino map as you land on a later visit.
* **What a planet's ground tends to hold, for the Rhino.**
  * **Survey page:** a RHINO chip on landable bodies worth the trip (IRIDIUM on a metal-rich world, MONAZITE on rocky magma), and MINE n once mining sites are found. Hover for the likely materials.
  * **Navigation HUD:** the Survey page notes RHINO and mining sites on bodies worth a look; the Planet page lists the ground's three best materials and how many mining sites the body has.
  * **Mining page:** *Rhino prospects in this system*, every landable body with its likely materials, mining sites found first, then by what its best material is likely worth a tonne.

### Music

* **The Music page, made over like Spotify:** your library on the left, the open list under a big header with a play button, what's playing on the right with up next, and the player along the bottom.
  * **Long mixes resume:** any track over 20 minutes carries on where you left it (*FROM START* plays it from the beginning).
  * **The track list:** click to select (Ctrl and Shift for more), drag to reorder, and sort by title, artist, plays, date added or length. *PLAY NEXT*, *ADD TO QUEUE*, *ADD TO* and *MOVE TO* another playlist, and *LOCATE* a file that's moved (the rest of its folder is found too).
  * **For you:** *Recently added*, *Most played*, *Never played* and *Long mixes*, plus *Recently played* with the system you were in.
  * **Visualizer looks:** the button by *LEVEL* on the player bar opens a list of twelve. *Classic:* Bars, Peaks (falling caps), Mirror and LED (a dot-matrix meter). *Flowing:* Wave (the sound's own waveform), Horizon (a smooth skyline), Aurora (ribbons for bass, mids and treble), Waterfall (the spectrum scrolling past) and Shockwave (a ring on every beat). *Elite:* **Scanner**, your ship's scanner with a contact on a stalk for every band (red when it's loud, like a hostile), and **Witchspace**, the jump tunnel, rushing faster as the music gets louder. Or *Off*.
  * **Follow the game** has its own place in the library, and keys work on the page: Space plays or pauses, ← → seek, Shift+← → skip, Delete removes, Ctrl+F finds.
* **The Music Player overlay, made over.** Five new skins replace the ten: *Command Deck*, *Cockpit HUD* (Elite orange, with lit-block meters), *Glass* (your cover, blurred, behind frosted glass), *Vinyl* (a turning record, its tonearm travelling across the track) and *Minimal*. If your skin has gone, the overlay switches to Command Deck.
  * **Nothing on top of the visualizer:** the track, the visualizer, progress and up next each have their own lane.
  * **Shuffle and repeat** show as small icons.
  * **Up next:** the next track or the next three, set in Overlay Studio › Music Player. Queued tracks are marked QUEUED.
  * **Follow the game:** shows the scene the music is playing for (DOCKED, DEEP SPACE, COMBAT...).
  * **Long mixes** say LONG MIX, and while paused, where they carry on from, marked on the progress bar too.

### Also

* **Hotkeys A to Z.** Settings › Hotkeys lists every shortcut in alphabetical order.
* **Explore & Survey stays still:** it redrew itself every second or so, losing your place and fighting the scroll. It now redraws only when something on it changes.

## Earlier releases

* **v5.5.16** (21 OCT 3312) — Systems at a Glance: the Navigation HUD's ship systems as a fixed strip of cockpit icons (lit when on, warnings in red in front), so nothing beside the fuel bar gets cut off.
* **v5.5.15** — The Anaconda Mk II: the new ship on the Navigation HUD (and a large pad for Trading), and nothing drawn behind your ship's picture on the HUD any more.
* **v5.5.14** — Every Site in Sight: Planetary Operations' ALL SITES (every saved site, grouped by planet, with FIND, from anywhere) and a Studio setting for how close counts as HERE on the Rig Tracker.
* **v5.5.13** — Smooth Ground: the Planetary page no longer lags the deck while you're on a planet (each refresh read your whole exobiology history three times; now it reads only the planet you're on, and a refresh went from about 560 ms to under 20 ms).
* **v5.5.12** — Mining & Planetary, Rebuilt: a new Mining page for asteroids and the Rhino (live run, ring and Rhino-ground search, selling, your whole mining record), Planetary Operations as one page (compass, a new surface map, exobiology with sample distances and values, saved sites), the Watcher knowing your vehicles by name and talking mining, SRV fuel tracked properly everywhere, COPY NEXT that survives a busy clipboard, and an auto-copy switch on the Command Deck.
* **v5.5.11** — Holds in Sight: the Rig Tracker shows how full the Rhino's hold and your ship's are (with a Studio switch), the Watcher knows Rhino mining from asteroid mining and stops repeating Galnet's top story, your ship's kept hold belongs to its ship across restarts, and `/rigs` includes the holds.
* **v5.5.10** — Your Journey, Told Back: Void Wrapped (your year as animated cards, combat and the everyday included, saved as pictures, refreshable), the Flight Recorder (replay any session on the Atlas, with the music you played), the Rig Tracker overlay for Rhino mining (Ctrl+Alt+1–6), the music diary, a radius for Sell cargo, flight logs that know where a session began, and `/rigs`, `/wrapped` and `/recorder` in the Local API.
* **v5.5.9** — Quieter Inara: each piece of state (every ship, suit loadout, mission and ship locker category) is sent to Inara once and only again when it changes, so a whole session sends about 60 events instead of 263, and a restart mid-session sends nothing new.
* **v5.5.8** — Waypoints by Wire: Explore & Survey's ROUTE tab in the Local API (add, mark visited, rename, move and remove waypoints; return-later places to waypoints or put aside; import the last plotted neutron route), with the deck following at once, and Stream Deck keys in the API docs.
* **v5.5.7** — The Watcher, Refined: a sharper, smoother Watcher (a star for a pupil, a galaxy of light, glass with depth, springier glances, its own frame rate), about 2,500 new lines, and words for fights in the ship and on foot; the Local API (no key, local pages only, a proper docs page with OBS, Discord, BGS and Windows PowerShell guides; every record on its own endpoint; exploration events with values; read-only BGS); API thoughts spoken when the voice is on; and Inara no longer resent the same data after a restart.
* **v5.5.6** — Steady Buttons: buttons no longer blink or lose clicks when a page refreshes (no fade-in on newly drawn buttons, Explore & Survey's unchanged panels kept, and no redraw while a button is held).
* **v5.5.5** — Every Word Its Size: each overlay's own text size in Overlay Studio; postcard text sizes (lettering, note, details); delete postcards to the Recycle Bin; editing a postcard into your theme keeps its angle and name; MAKE EDITABLE finds screenshots for commanders far from UTC, and postcards restored without their picture get it back; and a fix for the postcard studio's previews locking the system up.
* **v5.5.4** — Can you hear me? (and over things): the Watcher speaks in HAL 9000's voice (Piper, downloaded on first use) and finds it over its first hour (The Switch), learns how you play, and knows your home system; achievements in their own overlay; Inara sync, checked against its API docs, sending every commander event it takes; carriers you can remove; time capsules shared by code or file and a Time Capsules vault; Postcards rebuilt (album, studio with live preview, your own themes, a postmark, and every postcard editable, older ones too); Constellation v2 (a sky chart, designations, the night behind each star, an almanac, saved pictures on its own page); a Tools page; Explore & Survey and the Exploration Archive as one page; Updates on its own Settings page.
* **v5.5.3.9.3** — The Rhino's Mothership: the Cargo overlay's SHIP CARGO card shows your mothership's total cargo and the space left as you unload the Rhino, and knows your ship's capacity and hold after a restart.
* **v5.5.3.9.1** — Overlays That Fit: Prospector, Cargo and Planet Materials columns grow with the text size; they and Station Link fit the window they really get at any Windows scaling, so no rows go missing and long names wrap.
* **v5.5.3.9** — The Watcher, Chapter 3: Book Three, What Was Put There (seven chapters over about a year, darker musings headed The Seat, two new achievements); hints on the Watcher page for locked chapters and echoes; Reset the Watcher (with Are you sure?, its old memory kept as a copy); the Watcher on earth-likes, water, ammonia and terraformable worlds; pictures open where you are in Screenshots and Postcards.
* **v5.5.3.8** — Music that flies with you (a playlist, or a song of its own, for docked, space, deep space, surface and combat, faded across as the game changes, quieter in hyperspace); flight logs for every session in the Captain's Log (trail, figures, best moments, postcards, its star, field discoveries grouped, and a closing word from the Watcher), the Captain's Log tidied into one list of nights; postcard lettering (Greetings from, Wish you were here, your own words or none); morning, afternoon and evening said as they were.
* **v5.5.3.7** — Keepsakes: the Galaxy Minimap overlay (session trail, plotted route and your whole Spansh trip, region names, views and a view hotkey, time capsule marks) and the Postcards overlay ("Greetings from…", journal facts, the Watcher's note, four styles, saved as pictures); new Postcards, Screenshots, Time Capsules (with Not before… and On this day) and Constellation pages, each with its own settings; favourites; the Watcher keeps postcards, hands back capsules and names your constellations; the Galactic Atlas replay pauses and stops; OneDrive screenshot folders and a sync-safe PNG converter; Overlay Studio's list in alphabetical order.
* **v5.5.3.6** — Trading › Market searches one system after another reliably (late replies no longer land under a newer search, and a market from another system clears); the Market view laid out side by side, the search and its stations beside the market you opened.
* **v5.5.3.5** — The Watcher's past: a long story in two books that unfolds over your hours together, echoes stirred by real things in your game, an afterword, a chapter reader on its page and four achievements; every thought headed (a memory, an echo), typed in its nature's own way, with the journal words it noticed picked out; Thought side, its own text size and heading options in Overlay Studio, its words kept on screen and never clipped; its memory saved at the game's sign-off and when Void Compass closes; the Watcher page laid out again; corner-bracket buttons across the deck; Sell cargo by distance; Market's system search moved to the top.
* **v5.5.3.4.1** — Overlays see-through again in Windows dark mode (they now draw through Windows' compositor, avoiding Microsoft WebView2's dark background), with a Classic windows fallback in Overlay Studio; overlays never pull Void Compass in front of the game.
* **v5.5.3.4** — Trade routes from a whole system (the best few stations tried and compared); what a system's own stations pay in Find commodity and Sell cargo; any station's market from the Market view; the Navigation HUD no longer stuck on SURFACE DEPARTURE; the command deck no longer freezes after a slow start; the Dark box fix switch stays on.
* **v5.5.3.3.1** — A Dark box fix for PCs where overlays show dark boxes or corners (seen with a GTX 1660 Super): every overlay window cut to what it draws; the logs say which renderer each overlay uses.
* **v5.5.3.3** — Ten skins for the music player overlay; each overlay can have its own opacity; the heartbeat orb's window cut to a circle, so it never shows a black square.
* **v5.5.3.2** — The Watcher: its own idle chatter about what is really around you, natures with their own voices, memory of places, records and anniversaries, a poke hotkey, a bond that grows, a page on the deck, soft effects and a richer look; notifications show everything at any text size; trading searches 10–40 times faster.
* **v5.5.3.1** — Settlement and site signals; EDDiscovery-style body facts in Explore's orrery; rare worlds lead Survey's NOTABLE (green gas giants paired from the Codex); the Watcher's own thoughts, memory and depressed nature, with 500+ lines, rare-world remarks and a sign-off; thought backdrop, colour, size and stay; check for updates in Settings; Session Pulse with time flown, earnings, firsts and rare worlds; the Mission Directive and Focused Log know fuel, rare worlds, Codex colours, trade routes and colonisation.
* **v5.5.3** — Codex flags on by default and smarter; Galnet's real story dates; loadouts imported as they are in game; achievement trigger fixes; Jump Info on the jump press; high-value bodies after biology; exobiology value and first-footfall bonus counted; body discoverers and EDSM traffic on Explore; Navigation HUD Full/Still/Off; The Watcher's idle life; cargo in alphabetical order.
* **v5.5.2.9** — Survey Operations' Codex flags per colour, like SrvSurvey's: each species with the colours it will show and a flag on each colour you lack.
* **v5.5.2.8** — Commander Record covers Odyssey on foot: suit and loadout with real grades, on-foot record, exobiology career, backpack and ship locker; the ship locker no longer overwrites the backpack.
* **v5.5.2.7** — Overlays grow with the text size in both directions, overlays show up to date when they appear (Survey's first planet after a jump), and the Navigation HUD always fits its window.
* **v5.5.2.6** — New Trading tab with Spansh routes, loop routes, selling your cargo, finding any commodity, station markets and your profit history with charts; and the Trade Route overlay.
* **v5.5.2.5** — Install updates from inside Void Compass: downloaded and checked from GitHub, swapped in on a restart, with your settings and profiles kept and the old version put back if anything goes wrong.
* **v5.5.2.4.1** — Surface gravity fixed for worlds under about 0.5 G (shown ten times too heavy, which also skewed species predictions and set off false gravity warnings); BGS Refresh from EDSM gets fresh data; conflicts listed newest first.
* **v5.5.2.4** — New BGS tab: every faction in every system you visit, tracking and alerts, conflicts, any system looked up on EDSM, influence charts, your work per tick with a Discord report, and a guide to the states.
* **v5.5.2.3** — Deep Space Contact Scope rebuilt from the journal alone: signals named by type, nothing missed on arrival, honk counts, expiring unidentified signals, and busy systems kept readable.
* **v5.5.2.2** — Commanders renamed in game keep their profile and history under the new name.
* **v5.5.2.1** — Colonisation's System Planner with Raven Colonial's own model, a station identifier, uploading your scans, Where to Buy, project stats, assignments, fleet carrier tools, Nexus plans, Raven stats and new Construction Needs options.
* **v5.5.2** — New Colonisation tab with Raven Colonial: projects, the site you are docked at, fleet carriers, system sites and your journal's construction record; the Construction Needs overlay; and Raven Colonial in Settings > Integrations.
* **v5.5.1.9** — Fixed grey blocks at the corners of most overlays, and between stacked notifications, when overlay opacity was below 100%.
* **v5.5.1.8** — Jump Info redesigned to match the Navigation HUD (and its body counts removed), its corner blocks fixed, and overlay opacity and frame rate now applied straight after a restart.
* **v5.5.1.7** — Overlay opacity now fades each overlay window through Windows itself, so it works on every graphics card.
* **v5.5.1.6** — Overlay switches in the command deck header, Codex flags for Survey Operations, and a fix for finished system surveys showing one body still to go.
* **v5.5.1.5** — Jump Info overlay, overlays hide on the maps (each can opt out), Overlay Studio layout mode, who discovered the system on the Navigation HUD, and switches for the surface and mapped signal notifications.
* **v5.5.1.4** — Fixed Overlay Studio merging every monitor into one wide display, and the command deck reopening in the wrong place on monitors with different Windows scaling.
* **v5.5.1.3** — Text size, smallest text and overlay text size in Settings > Appearance, a working Command deck scale, overlays sized for Windows display scaling, survey overlay fixes, an overlay frame-rate setting, and new installs picking up the commander and their whole history.
* **v5.5.1.2** — OBS can capture each cockpit overlay on its own with Window Capture ("Windows 10 (1903 and up)" method), while the overlays stay off the taskbar and out of Alt-Tab.
* **v5.5.1.1** — Rebuilt the first-time setup into four steps (Welcome, Journal link, Cockpit, Launch), with a live check of the journal folder that shows your journals, commander, ship and last system, and a theme picker that previews each theme as you click it.
* **v5.4.9.9** — Rebuilt the Ship Workshop: a Build Planner with a hangar of builds, a hull drawing that lights the slot you fit, the distributor's pips, a loadout board, a module dock and every performance figure at once; and Engineering with your fleet, what is engineered on each ship, the material locker, the engineers and a new blueprint reference.
* **v5.4.9.8** — Added Music, a local player with playlists, loudness levelling, OBS capture and a Music Player overlay; rebuilt the Galactic Atlas as a regions map of your whole journey and Powerplay Operations around the weekly cycle; and fixed the command deck going blank or dropping its page in long sessions.
* **v5.4.9.7** — Rebuilt Settings as one screen that saves as you go, added the Galnet Ticker overlay with CRT and glitch effects, rebuilt the Navigation HUD's state scenes as solid 3D holograms with stars shaped by their class, switched the Rhino coverage map off, and fixed overlays sometimes not appearing at startup.
* **v5.4.9.6** — Rebuilt the Journal Heartbeat as a HAL 9000-style watcher orb that reacts to every journal event, rebuilt the startup screen around the same eye with an FSD countdown into the deck, added Navigation HUD typeface and text settings, and fixed the HUD's on-foot portrait.
* **v5.4.9.5** — Brought back an animated hologram for every Navigation HUD state with journal event effects, rebuilt Gravity Warning and Overlay Studio (one display at a time), made Survey Operations hold still at or below its rotation threshold, and fixed hidden overlays reloading after five minutes.
* **v5.4.9.4** — Rebuilt Survey Operations around one spotlight world on a single clock, split Explore & Survey into three views with a unified Survey Board, rebuilt the Navigation HUD as a cockpit status panel and Planet Waypoint Navigation as a surface compass, and fixed startup stalling when the dashboard was minimised.
