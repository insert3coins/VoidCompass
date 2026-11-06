# 5.7.6 plan

Chosen 6 November 2026. Starts once 5.7.5 is committed: then bump the version
(the user names its title) and work through these. Per the batch rule, tests
come after each part is built.

## 1. The crew, together

- [x] **Automatic watch rota (optional, off by default).** The companion on watch follows what you're doing:
  - Axiom for FSS, mapping and surface biology;
  - Meridian on a plotted route;
  - Aster when docked or trading;
  - the Watcher in deep, quiet space.
  It needs a settle time, so short stops don't flip it, and it uses the existing handovers. Add a Settings switch (profile setting, registered in the `PROFILE_*` tuples) and a manual override that holds your pick for the session.
- [x] **Crew debriefs.** Before an expedition sets out, each companion gives one line on the plan: Meridian on fuel and jumps, Axiom on survey value, Aster on logistics, the Watcher gloomily. After a session where you switched companions, the Captain's Log is signed by each companion that stood a watch.
- [x] **A shared ensemble story.** It unlocks once all four have told *Coming Aboard*: a short story where real events bring out several voices in turn. Same pacing rules as the other stories; no names from sealed chapters.
- [x] **Crew stats in Void Wrapped.** Who you flew with most, each companion's hours, its favourite moment.

## 2. Overlay performance (todo-overlay-backend.md)

**Skipped this round** (you, 2026-11-06: "think we can skip the overlay usage this round"). Still parked in todo-overlay-backend.md.

Parts 0 and 1 are built (5.7.1). Now:
- [ ] **Part 2:** the frame cap covers CSS animations too (`frame-cap.js` steps them on paced frames; `data-frame-cap="native"` opts out). Fix Station's `inset` keyframes (lays out every frame) and review other layout or paint keyframes.
- [ ] **Part 3:** fewer wake-ups and resends.
- [ ] **Part 4:** one fit for every overlay (no more overlayfix.md by hand).
- [ ] **Part 5:** Nav HUD hologram cost (your call on the trade-offs).
- [ ] **Still to check:** OBS window capture through a cloak and uncloak; the map-glance grace period (about 4 s).
- [ ] **Measure** with `tools/overlay_bench.py` before and after: CPU per overlay, and show/hide spread.

## 3. Rhino survey tools (after EDSMT; see the Rhino map memory)

- [x] **Survey sweep:** the centre plus a border; sweep circles at the 2 km scanner range; coverage % of the area driven.
- [x] **Rig placement planner:** spacing (78 m), the 3.5 km warning, the legal spot nearest you, a suggested pattern.
- [x] **Best patch:** where refining pulses clustered richest (pulses only; never invent deposit data).
- [x] Show them on the Rhino map, the Rig Tracker and the Mining page, plus companion lines where useful.

## 4. TALK and the officers' statistics

- [x] **TALK answers more:**
  - the nearest station (with services) and the distance to a named system;
  - your materials (count of a named material, totals by grade);
  - mission details (where to, reward, time left) and community goals.
  Each needs a lookup topic and an example question tested.
- [x] **Officer habit summaries** (`habit_flight`, `habit_scans`, `habit_cargo`, `habit_combat`, `habit_trade`, `habit_style`): give Aster, Axiom and Meridian the same depth as the rest, at least 9 lines (4 plain). Every line must keep to the fields its template provides.

## Release checks (every version)

- [ ] Full test suite; rebuild the exe and start it once; patch notes in mini-readme; Discord post.
