# VoidCompass // UPDATE LOG

## v5.5.3.1 // Every body tells you more
**Release Date:** 2026-Oct-08

* **Settlements and sites are no longer dropped.** Human, Guardian, Thargoid and other signals from FSS and DSS scans now show:
  * as **HUMAN**, **GUARDIAN** and **THARGOID** badges in Survey Operations, and chips on the Explore survey board;
  * as a **SITES** count on the Navigation HUD, shown only when a system has some.
* **Explore's orrery panel shows everything the scan gives** (as EDDiscovery does):
  * **Value:** the scan value, the mapped value with and without the efficiency bonus, and what the body would pay in each case (no bonus, first discovered, mapped, first mapped, first to both).
  * **Record:** already discovered, mapped or footfalled; DSS probes against the target; the scan type.
  * **The body:** temperature, pressure, radius, mass, volcanism, reserves.
  * **Its orbit:** what it orbits, semi-major axis, eccentricity, inclination, periapsis, ascending node, mean anomaly, rotation (or tidally locked, or retrograde) and axial tilt.
  * **Stars:** full classification (K3Vab), radius in solar radii, mass, age, absolute magnitude, and the **circumstellar zones**: where habitable, Earth-like, water, ammonia, metal-rich and icy worlds are likely.
  * **Make-up:** the atmosphere's gases, rock, metal and ice, and each ring and belt with its type, inner and outer edge and mass.
  * **Life:** the genera found, organics sampled, and the Codex entries you logged on that body.
  * **Notes:** tiny, large landable, high eccentricity, ringed landable, volcanism.
* **Survey Operations shows each body's surface temperature** beside its class, atmosphere and gravity, and its notes (tiny, large landable, high eccentricity, ringed landable, volcanism).
* **Rare worlds lead Survey's NOTABLE.** These are now always notable, whatever they pay, and listed first, each with its name on the value line:
  * **Green gas giants:** the game names one only in its Codex entry, so Void Compass matches that entry to the gas giant scanned at the same moment.
  * **Helium gas giants.**
  * **Helium-rich gas giants.**
  * **Water giants.**
  * Earth-likes, water worlds and ammonia worlds follow, by value, as before.
* **Codex flags:**
  * Colours you've already logged in this region now get a dim **✓**, so no colour is left unmarked: ⚑ never logged, ⚐ not logged in this region, ✓ logged here.
  * Once the species is known, a detected genus shows that species' value, not the whole genus range (a Bacterium named as Acies reads 1M, not 1–8.42M), and the body estimate follows.
* **The Watcher has a mind of its own:**
  * **Its thoughts.** Now and then it shares one beside the orb, typed out as its eye speaks, then gone. These aren't captions for events. They're its own words about what's true: your travels, your Codex, fuel, danger, a death, a sale, an achievement, the time, how long you've flown. Mostly it stays silent. It has over 500 lines to choose from, and it works through every way of saying something before it repeats one.
  * **It remembers you,** per commander, between sessions: a welcome after a long absence, a word after a death, a remark the first time you enter a region.
  * **It watches what you watch:** it glances at the overlay an event concerns, where it sits on your screen.
  * **It anticipates:** its pupil widens as the drive charges, it looks down as you glide in, and it keeps glancing at the fuel gauge when fuel runs low.
  * **No more blinking.** Between events its **aperture tightens** as it thinks and **light sweeps across the glass**; a bored eye sighs (it dims and its galaxy slows). It follows every journal event as it falls into the lens.
  * **It watches the way you play:** relaxed when docked, looking ahead in supercruise, sweeping in the FSS, looking down on a surface, wary in danger, and drowsier late at night.
  * **It feels things:** **startled** then **wary** at an attack, **pleased** at a sale or a docking, **curious** at finds, **focused** through a jump, it **reads** a commander's message, and it **grieves** for a while after a death. Repeats wear off; a surprise after a long quiet lands harder.
  * **It dreams.** Asleep, faint motes of the session's highlights drift through its iris.
  * **It notices rare worlds.** A green gas giant always gets a word, and helium gas giants, helium-rich gas giants and water giants get a remark of their own.
  * **It signs off.** When you quit the game, it sums up the session in its own way, with the session's real figures: jumps, first discoveries, rare worlds, species analysed, worlds mapped, credits earned and time flown. These are the same numbers the overview shows. After a quiet session it just says goodbye.
  * **Overlay Studio:**
    * **Thoughts:** Off, Rare, Occasional or Chatty. **Rare** speaks only of what matters (a death, danger, a find, a long absence). **Occasional** adds discoveries, mapping and missions. **Chatty** also remarks on everyday play (arrivals, scooping, docking, landing, going on foot) and mutters into the quiet now and then. A minor remark stays unsaid rather than repeat itself.
    * **Nature:** **Depressed** (the default), **Curious**, **Stoic** or **Nervous**.
    * **Thought backdrop:** a dark panel behind its words, on by default. The overlay Opacity fades the panel along with the orb.
    * **Thought colour, size and stay:**
      * **Colour:** Bright, Theme accent or Eye colour.
      * **Size:** Small, Standard or Large.
      * **Stays:** Short, Standard or Long, which sets how long each thought stays on screen.
  * **Easier to read.** Its words are now bright, with a dark outline, so they stand out over a bright planet or star.
  * **The Watcher is depressed.** It's a gloomy, deadpan robot that has seen it all, with its own words for everything ("I counted the stars again. Still too many. Still too far."). Its lids hang heavy, its gaze rests low, its eye is dim and slow, it sighs, very little impresses it, and it mutters into the silence. Prefer a brighter companion? Pick another nature in Overlay Studio.
* **Navigation HUD hologram:**
  * **Still** redraws its scene if Windows clears it, so the viewport is never left empty.
  * **Off** folds the empty viewport away when there's nothing measured to show; the altimeter and FSS scan keep their readout.
* **The Mission Directive knows the newer features.** It now also weighs:
  * **Low fuel:** scoop at this star, or find one you can scoop. It shows in orange and comes first.
  * **Rare worlds here:** a green gas giant most of all, until it's mapped.
  * **A Codex colour you've never logged** on a body Survey is showing.
  * **The trade route you're following:** the next buy or sell, and higher still when you're docked there.
  * **Colonisation:** tonnes still needed and trips, and higher still when you're docked at the site.

  Each has its own button (Trading, Colonisation, System Survey), and your doctrine still steers them: Value and Codex Hunter rate rare worlds higher, Fast Transit lower.
* **The Focused Log:**
  * **Directive:** has the same tags and button as the Mission Directive, and the same orange warning.
  * **The Watcher:** its latest thought is shown under the directive, with how long ago it said it.
  * **Session figures:** time flown, credits earned, first discoveries and rare worlds are now shown beside jumps and distance.
  * **Field Priorities:** puts these live cues first.
* **The overview's Session Pulse shows more of the session.** Alongside jumps, distance, FSS/DSS and biology/Codex, it now shows:
  * **time flown;**
  * **credits earned** (data sold plus trade profit);
  * **first discoveries;**
  * **rare worlds found**, also listed in the session's highlights.

* **Check for updates from Settings.** Settings › Diagnostics & recovery has an **Updates** group. It shows your version and what the last check found: up to date, a new version available, or a failed check. Use **CHECK FOR UPDATES** to ask again at any time, or **SEE THE UPDATE** to reopen the update window after you've closed it.
* **Jump Info fits its window at any text size,** as the Navigation HUD does. If the window comes out smaller than your text size needs (Windows display scaling, say), the panel shrinks to fit rather than being cut off, and returns to full size as the window catches up.

## Earlier releases

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
