# 5.7.7 plan: a fifth companion

Noted 7 November 2026, at bedtime. This is a starting point for tomorrow; nothing is decided yet.

## Fix first: the watch rota still looks broken (5.7.6)

Seen live on 6 November, 23:16 to 23:22. The app was on the new exe, with the rota on (docked: Aster, flight: Meridian, deep space from 5,000 ly).

What the memories show:
- 23:20:59: the Watcher handed over to Meridian.
- 23:21:24: Meridian handed over to Aster, 15 seconds after docking at 23:21:09. That's too soon for the rota, so it was most likely a manual pick.
- 23:21:29: Aster handed back to Meridian.

The likely cause: picking a companion yourself holds it for 30 minutes, with no sign of that anywhere, so trying the rota by hand switches it off. Its waits (45 seconds to settle, at least 3 minutes between changes) also make it feel dead.

- [ ] **Show the rota's state on the companion page.** For example: "Rota: docked, Aster takes over in 30 s", "Holding your pick until 23:51" (with a button to release it now), or "Next change allowed in 2 min".
- [ ] **Rethink the hold.** Perhaps hold your pick only until the duty changes, not for a fixed 30 minutes, or make it shorter.
- [ ] **Waits per duty.** Docked could swap after about 10 seconds; scanning keeps the longer wait. Review the 3-minute gap between changes.
- [ ] **Watch it live.** Use the debugger (Local API /debug, verbose), and add a debug line for each rota decision: duty, who's wanted, and why not yet. Then a clean run with no manual picks: dock, FSS, plot a route, fly.
- [ ] **Blank duty settings.** Duty settings never chosen are saved as "" and fall back to the defaults. Confirm the dropdowns show the default, not a blank.

## Why

The watch rota has five duties but only four companions, so Axiom holds two (scanning, and working a planet's surface). A fifth companion would take the surface work: on foot, the SRV, the Rhino and its rigs, the Rhino survey, exobiology sampling, settlements and dropships.

## Decide first

- [ ] **Who they are:** a field specialist for the ground, an engineer, a pilot, or something else. Settle their character, how they speak, and how their plain and voiced styles differ.
- [ ] **Their name,** and a pronunciation the voice can say.
- [ ] **The Night Watch:** its last scene says "five of us standing watch now. One of us doesn't talk" (the ship's chronometer). Either adjust that ending, or have the newcomer arrive after it, as a sixth presence aboard.
- [ ] **Their voice:** a Piper model. It must be one we can host on our GitHub, as with the others.
- [ ] **Their display:** an animated Three.js display, like the particle and portrait displays.
- [ ] **Which release:** 5.7.7 (5.7.6 is nearly ready), and its title.

## Build (each officer in 5.7.4 needed all of this)

- [ ] **Persona:** a lines module, mind and companion_personas entry, and an identity in `companions.IDENTITIES`. Register their settings (thoughts, voice, display, size, humour) in the PROFILE_* tuples.
- [ ] **Lines for every topic,** at least 9 per topic with 4 plain. Merge their persona banks into:
  - route_lines, survey_report, rhino_lines and rhino_survey_lines, mining_talk;
  - ship_life, docking_talk, life_events (all five groups), squadron_talk;
  - officer_habits and talk_replies.
- [ ] **Talk:** 50 greetings and 10 "what can you do" rundowns, plus their command replies; Aster's test needs at least 4 per outcome.
- [ ] **Story:** an 8-chapter story, plus a "Coming Aboard" account in crew_lore. That raises the total, which moves when The Night Watch unlocks.
- [ ] **Crew features:**
  - crew_voices (off-watch remarks and asking them by name);
  - crew_debrief (expedition lines and log postscripts);
  - handovers;
  - their lines in crew_story scenes;
  - Void Wrapped's crew card (`void_wrapped.CREW`);
  - the watch rota's `CREW`, with their default duty: surface;
  - the boot screen, the companion switcher, the Local API and `/companion`.
- [ ] **Voice:** the Piper model download and pronunciation respellings, checked with `piper --debug`.
- [ ] **Tests:**
  - the depth tests for every bank;
  - the no-repeat rules, and Watcher lines unique after `plain_text`;
  - the companion page;
  - rota defaults.

## Until then

The rota's dropdowns already let any companion take the surface duty, or "Whoever's on watch" leaves it alone.
