# Overlay backend: quicker, lighter, all at once

The goal, in your words: make the overlays "quicker, less cpu hungry (note we
pritty good already there)", and show and hide them "not one at a time, but
all at once as needed, while keeping their data/renewing them when they are
hidden or on screen".

**Status (2026-10-30):**
- **Part 0 and Part 1 are built, in 5.7.1:** overlays come and go together.
- **5.7.1 also adds a "Hide in menus" option** (see the end of this file).
- **Parts 2, 3 and 5 are parked.** You said the CPU is fine as it is ("its not that hungry on cpu"), so they're kept here only in case that changes.
- **Part 4** (one fit for all) is still open.

## Where we are (measured 2026-10-30)

`tools/overlay_bench.py` measured this (see "Measuring" below). It ran the real
overlay host (visual hosting) with nine real overlay pages and the models from
the text-fit tests, on the RX 6800 at 100 Hz, with the 30 fps cap.

| | Result |
|---|---|
| Show all 9 | 49–75 ms from the first window to the last (5–7 frames at 100 Hz) |
| Hide all 9 | 32–35 ms from the first window to the last |
| One host pass over every overlay | 0.7 ms median |
| Showing one window | about 6 ms; ShowWindow alone is 3.5 ms |
| Hiding one window | about 4 ms |
| 9 visible, data not changing | 106% of one core: GPU 60%, pages 45%, our host 0.3% |
| 9 hidden | 2–4% in all |
| Nav HUD updated 10×/s | 20 host passes a second (two per update); host 4.7% |
| Data while hidden | still delivered; pages showed the current data when revealed |

Each overlay shown alone, data not changing (CPU % of one core):

| Overlay | Total | GPU | Page | Why |
|---|---|---|---|---|
| Nav HUD | 37 | 21 | 15 | Three.js hologram, plus 14 endless CSS animations |
| Station | 17 | 7 | 9 | `station-lock` animates `inset`, so the page lays out every frame |
| Prospector | 16 | 13 | 2 | rock-scan, core-pulse |
| Hatchling | 14 | 5 | 8 | pet animation |
| Rhino map | 11 | 7 | 2 | "here" pulse |
| Cargo | 9 | 7 | 1 | hold-orbit, hold-core, empty-breathe |
| Rig tracker | 3 | 0 | 1 | |
| Planet Materials | 2 | 0 | 1 | |
| Expedition | 2 | 0 | 1 | |

What this tells us:
- The host loop is already cheap, and hidden overlays already cost almost nothing.
- **The one-at-a-time look:** windows are shown in turn, and every ShowWindow
  synchronously wakes that window's WebView2 (WM_SHOWWINDOW sets
  `controller.IsVisible`).
- **The CPU:** it goes into drawing visible overlays, and much of that drawing
  ignores our frame cap. `frame-cap.js` only paces `requestAnimationFrame`;
  endless CSS animations run at the monitor's full refresh rate (100 Hz here,
  144 or 240 Hz on many PCs).

## Part 0: a spike before Part 1 (DONE)

**Result:** nine real composition windows, timed from the screen itself (screen capture via BitBlt).
- **Pages keep drawing while cloaked**, at the full 100 fps. Chromium's occlusion tracker doesn't pause them, so no browser flag is needed.
- **Uncloaking all nine** puts them on screen in about 1 ms, with 0 ms spread, showing current content.
- **ShowWindow from hidden** shows nothing for 42–66 ms, while each page draws its first frame. In the app that came on top of about 6 ms per window applied one by one, with heavier pages slower to draw, hence the pop-in.
- **Not tested yet:** OBS.

The questions it answered:

- [ ] Does a **cloaked** overlay window (DWMWA_CLOAK) keep drawing once it's shown?
  - Chromium's native-window occlusion tracker treats cloaked windows as hidden, and may stop drawing them.
  - If it does stop, start WebView2 with `--disable-features=CalculateNativeWinOcclusion`. This goes in `CoreWebView2EnvironmentOptions.AdditionalBrowserArguments`; today `composition_host.py:422` passes `None` for the options.
- [ ] Does uncloaking show the page's current frame straight away, with no blank or stale frame?
- [ ] Do OBS window captures (WGC) of an overlay survive a cloak and uncloak? Is a cloaked overlay still listed?

`tools/overlay_bench.py` already counts a cloaked window as off screen (`on_screen()` reads DWMWA_CLOAKED).

## Part 1: show and hide all at once (BUILT, 5.7.1)

**As built:**
- **Host** (`html_overlay_host.py`):
  - `_WindowController._apply_composed` does the per-window half of a pass.
  - `_OverlayHost._settle` does the group half: the deferred real hides, then the group uncloak.
- **Constants:** `HOLD_DRAWN_S` = 10 s, `REVEAL_WAIT_S` = 0.3 s and `FIRST_REVEAL_WAIT_S` = 1 s (a page's first show after startup). A page that never sends the painted signal counts as drawn once its wait runs out.
- **Held windows:** the server marks an overlay hidden by a map or menu with `held` (true when it would otherwise be showing).
- **Painted signal:** pages opened with `&painted=1` (visual hosting only) post `"voidcompass.painted"` two frames after they become visible. `CompositionWindow._on_web_message` records it.
- **A held window that was already drawing comes back at once**, without waiting for its latest model to be confirmed.
- **A page never shown before doesn't draw under a cloak** (the cause wasn't found; the spike's plain pages did draw). So the first time, a window is *veiled* instead: `SetLayeredWindowAttributes` alpha 0, uncloaked. Every page is drawn once, veiled, as soon as it's ready, then goes under its cloak or really hides (`warming` in `_apply_composed`; the warmed step in `_settle`).
- **The boot screen preload** (your idea): behind the boot screen (`presentation_held`), overlays due to show are held drawn under their cloaks for as long as it's up, and come up together the moment it lifts.
- **The frame cap:** `frame-cap.js` drops a throttled wait when the page is shown again (`VoidCompassFrameCap.wake`). The painted signal uses the browser's own frame (`VoidCompassFrameCap.frame`). The host asks for the signal (`window.__voidcompassPainted()`) as it shows a window.
- **Classic windows** are unchanged.
- **Tests:** `tests/test_overlay_cloak_menus_571.py`.

Today `_OverlayHost._apply_manifest` (`html_overlay_host.py:945`) runs
`_WindowController.apply` window by window. Each window's ShowWindow or hide
happens inside its own apply, so nine windows step onto the screen over 5–7 frames.

The idea is to split the cheap part (deciding what to do) from the slow part
(mapping windows), and use DWM cloaking for the moment the user sees.

**Hide:**
- [ ] Gather every overlay leaving the screen in this pass, and cloak them all in one runtime call. The cloak is about a microsecond each, so they all vanish in the same frame.
- [ ] Then do the slow real hide (SW_HIDE, then move to -32000), where nobody sees it. WM_SHOWWINDOW still sets `IsVisible` false, so the page stops drawing and costs nothing, as now.
- [ ] Map hides (`set_overrides(hidden=…)`, GuiFocus 6/7/8): hold the real hide for a grace period (about 4 s). A quick look at the map then brings overlays back instantly, with no redraw wait.
  - The server marks the reason in the window spec (for example `"hold": "map"`), so the host knows which hides may wait.

**Show:**
- [ ] Gather every overlay arriving on screen in this pass as one group.
- [ ] Prepare each while cloaked: set its style, move it to its real position, then ShowWindow. `IsVisible` becomes true, so the page draws its current data off screen.
- [ ] Wait until every page in the group has drawn: render_current (as today), plus one painted frame.
  - The painted frame comes from `overlay-client.js`, which posts a "painted" web message from a double requestAnimationFrame after it becomes visible.
  - Cap the wait at about 250 ms.
- [ ] Uncloak the whole group in one runtime call. A page that missed the cap uncloaks on its own as soon as it's ready, instead of holding the others back.
- [ ] This covers every "many at once" moment: the boot curtain lifting (presentation_held), a map closing, layout mode, docking, and the header's OVERLAYS switch.

**Plumbing:**
- [ ] `composition_host.py`: `CompositionRuntime.cloak(hwnds, on)`. It runs DwmSetWindowAttribute(DWMWA_CLOAK = 13) for the whole list in one call on the runtime thread. Windows lets a process cloak only its own windows; the host owns these.
- [ ] `_WindowController.apply` returns what it wants (show, hide or stay), and `_apply_manifest` runs the hides and shows as groups.
- [ ] The visibility drift check (`_windows_visibility`) and the `visible` status sent to the server mean **on screen**: mapped and not cloaked.
- [ ] In composition hosting, `_restore_all_transparency` → `_apply_webview_transparency` does nothing; it measured 0.002 ms because these windows have no WinForms control. Keep it for classic windows only.
- [ ] Classic windows (`overlay_classic_windows`) keep today's path.

**Expected:** 32–75 ms spread → about one frame. Hidden overlays still cost nothing once the real hide is done.

## Part 2: the frame cap covers CSS animations too (PARKED)

Today `web/assets/frame-cap.js` wraps `requestAnimationFrame` only. Endless CSS
animations are drawn by the browser at the monitor's rate, whatever the
cap is set to.

These overlays have endless CSS animations:

| Overlay | Count | | Overlay | Count |
|---|---|---|---|---|
| navigation_hud | 14 | | galnet_ticker | 5 |
| survey | 7 | | cargo | 3 |
| jump_info | 5 | | prospector, carrier, ground, toast | 2 each |
| music_player | 5 | | colony_needs, galaxy_minimap, gravity, heartbeat, rhino_map, station | 1 each |

- [ ] In `frame-cap.js`, catch CSS animations as they start (`animationstart` in the capture phase, plus a `document.getAnimations()` sweep at load and whenever the cap changes).
  - Pause each one, then on each paced frame set its `currentTime` from its own start time.
  - With the cap at 0, set them all playing again.
  - Forget an animation when it's cancelled or finished, or when its element leaves the page.
- [ ] Respect CSS that pauses its own animations. A WAAPI `pause()` overrides `animation-play-state` from then on, so check the element's computed `animation-play-state` before stepping it, and skip paused ones.
- [ ] Opt-out for motion that must stay smooth: `data-frame-cap="native"` on an element (or an ancestor) leaves its animations at the browser's rate.
  - Check the Galnet ticker's roll and scroll, and the music title marquee and vinyl spin; these may need the opt-out.
  - The per-overlay frame rate in the Studio (`frame_rate_by_overlay`) still lets someone raise one overlay.
- [ ] Station: `web/station/styles.css:87` `@keyframes station-lock { 50% { inset:9px; opacity:.42; } }` changes `inset`, so the page lays out every frame. Use `transform: scale(…)`, which looks the same and doesn't lay out.
- [ ] Look over the other keyframes for layout or paint properties (`inset`, `width`, `height`, `box-shadow`, `background`) and move them to `transform` or `opacity` where the look allows.
- [ ] Later, not now: the command deck has its own endless animations (`overview.css` 11, `styles.css` 7, and others). It isn't drawn over the game, so it's lower priority.

**Expected (estimate):** at 100 Hz, the CSS-driven overlays (Prospector, Cargo,
Station, Rhino, Survey, Jump Info, Ticker) draw about 3× less, and more on
faster monitors.

## Part 3: fewer wake-ups and resends (PARKED)

**One update wakes the host twice:**
- [ ] `publish()` bumps `_window_revision`, so the host wakes and delivers.
- [ ] Then the page confirms it drew, which flips `render_current`, and `html_overlay_server.py:589` (`if before != after`) bumps it again for a second full pass.
- [ ] Wake the host for that confirmation only when it matters:
  - the overlay's content height or shapes changed, or
  - the host is holding that overlay's reveal (shown requested, but not yet on screen).
- **Expected:** 20 → 10 passes a second at 10 updates a second; host about 4.7% → 2%.

**Every overlay's full data is re-sent every 2 seconds:**
- [ ] The host's `seen` list forgets a delivery after 2.0 s (`html_overlay_host.py:824`), and `_deliver` re-posts after 2.0 s (`html_overlay_host.py:1028`).
- [ ] So at idle, about every 2 s, every overlay's whole snapshot goes round again:
  - the server decodes it (`json.loads` in `delivery()`, `html_overlay_server.py:353`) and encodes it into the reply;
  - the host decodes it and encodes it again for PostWebMessageAsJson;
  - every page parses it once more, hidden ones included.
- [ ] Keep `seen` until the page's generation or revision changes. Once the page has confirmed that revision (`rendered_revision >= revision`), send nothing more.
- [ ] Keep a slow safety resend (about every 10 s) only for pages that haven't confirmed. Resend straight away after a navigation or reload, which changes the generation.
- [ ] Health changes (frame rate, layout mode, title) still go out at once; they're part of the delivery key.
- **Must keep:** hidden pages still get every new revision the moment it's published. That's the "keep their data while hidden" part, and only duplicate resends go.

**Maybe, measure first:**
- [ ] Send only the overlays that changed in each `/api/windows` reply (a delta). A pass is already 0.7 ms, so do it only if the main app's side shows up in a profile.

## Part 4: one fit for every overlay (no more overlayfix.md by hand)

`overlay-client.js` has `fitToWindow` (line 338) and `designHeight` (line 351),
but each page has to call them with its own design width. That's a number
Python already knows (each overlay's `_dimensions`, for example Station's
`520 * scale` and `330 * scale`).

Already fitted (12): cargo, expedition, ground, hatchling, jump_info,
navigation_hud, planet-materials-overlay, prospector, rhino_map, rig_tracker,
station, toast.

Not fitted yet (12): carrier, colony_needs, contact_scope, galaxy_minimap,
galnet_ticker, gravity, heartbeat, music_player, postcards, powerplay-overlay,
survey, trade_route.

- [ ] Python sends each overlay's design size with its data (for example `effects.design = {width, min_height}`), from the same numbers `_dimensions` uses.
- [ ] `overlay-client.js` applies `fitToWindow` and reports `designHeight` on its own whenever a delivery carries a design size, unless the page opts out (`<body data-fit="self">`).
- [ ] Audit the 12 that aren't fitted:
  - The ones that likely just need it: carrier, colony_needs, contact_scope, gravity, postcards, powerplay-overlay, survey, trade_route.
  - Ones that size themselves and likely opt out: heartbeat (round orb), galnet_ticker, music_player skins, galaxy_minimap.
  - The Nav HUD and toasts already fit in their own way, so they opt out too.
- [ ] Add every fitted overlay to `OVERLAYS` in `tests/test_overlay_text_fit_5539.py`.
- [ ] Remove the per-page `fitToWindow` calls once the shared one does the job.
- [ ] `page_url` (`html_overlay_host.py:844`) is a 24-branch `if`/`elif` chain. Make it one `PAGES` table that `tests/test_overlay_checklist.py` reads too. The 5.5.18 bug, where a missing template hid every later overlay, is this kind of slip.
- [ ] `overlayfix.md` then becomes a short history note.

## Part 5: Nav HUD hologram (PARKED, your call)

The biggest single cost: 37% of a core with nothing changing (GPU 21%, page 15%).

- [ ] Its Three.js renderer (`web/navigation_hud/scene-three.js:1964`) is made with `preserveDrawingBuffer: true` and `antialias: true`.
  - preserveDrawingBuffer costs a copy every frame.
  - Find out why it was set, and drop it if nothing reads the canvas back (check the showcase and screenshot tools).
- [ ] Draw the 3D scene only on frames where something in it moves. Check how many full-window passes the hologram shader makes.
- [ ] Its 14 endless CSS animations are covered by Part 2.
- The look must not change. You want the hologram, with no 2D fallback.

## What stays as it is

- One window per overlay, not one big window: each must stay capturable in OBS on its own.
- The host pass (0.7 ms), `monitor_scale` (0.016 ms a call) and the visibility drift check (0.035 ms a call) are fine.
- Hidden means really hidden: WM_SHOWWINDOW → `IsVisible` false stops the page drawing. Part 1 only adds the cloak in front of it.
- Data goes to hidden pages directly (`post_message`, which the page's throttled timers can't delay).
- Classic windows keep today's behaviour.

## Order of work

1. [ ] Part 0, the spike: it decides how Part 1 is built.
2. [ ] Part 3: small, low risk, easy to measure.
3. [ ] Part 2, with the Station fix.
4. [ ] Part 1.
5. [ ] Part 4.
6. [ ] Part 5, if you want it.
7. [ ] Rerun the bench and write the "after" numbers below. Then run the full suite once the whole batch is done, not before. Then the release notes.

## Tests

Existing tests that will need a look:
- `test_overlay_batch_and_boot_568`
- `test_overlay_reveal_current`
- `test_overlay_delivery_568`
- `test_overlay_hidden_heartbeat`
- `test_overlay_layout_and_map_hiding`
- `test_overlay_startup_restore`
- `test_overlay_checklist`
- `test_overlay_text_fit_5539`
- `overlay_animation_smoke.py`

New tests:
- [ ] A group reveal uncloaks in one call, and a late page joins after the cap.
- [ ] A map hide cloaks now and really hides after the grace period. A quick return skips the real hide.
- [ ] A render confirmation wakes the host only when a reveal is waiting, or the height or shapes changed.
- [ ] Nothing is re-sent once a page has confirmed. The safety resend still happens for a page that never confirms. Hidden pages still get every new revision.
- [ ] frame-cap.js (Playwright): CSS animations move only on paced frames. One paused by CSS stays paused. `data-frame-cap="native"` is left alone. A cap of 0 puts everything back.
- [ ] Auto-fit is applied from the design size, and `data-fit="self"` opts out.

## Measuring

```
python tools/overlay_bench.py <label>          # show/hide spread, CPU per process, host step timings
python tools/overlay_bench.py <label> --cost   # CPU of each overlay shown on its own
```

- Results go to `temp/overlay_bench/<label>.json`, and the host's pass timings to `<label>_passes.json`.
- The nine test windows appear in the top-left of the screen while it runs.
- It's dev only, like `tools/journal_watch.py`, and never released.

## Open questions

- Which version does this go into?
- Part 5: touch the Nav HUD or not?
- Map grace period: is 4 s right?
- Is an opt-out for the ticker and marquee motion OK, or should they be paced too?

## After

Part 1 in 5.7.1, measured with `tools/overlay_bench.py boot` (spread from the first window to the last):

| | Before | After |
|---|---|---|
| Boot screen lifts (show all 9) | 72–75 ms | 0 ms (all on screen 3 ms after it lifts) |
| Map closes (show all 9) | 49 ms | 0 ms (on screen 3 ms after) |
| Map opens (hide all 9) | 32 ms | 3 ms |
| Hide all 9 | 34 ms | 7 ms |
| Show all 9 again | 59–71 ms | 0–2 ms (all at about 0.1 s, once each page has drawn its latest model) |
| 9 visible, idle | 106% | about the same (not part of this work) |
| Host passes per update | 2 | 2 (Part 3, parked) |

## Hide in menus (5.7.1)

- **The setting:** Overlay Studio › All overlays › **Hide in menus** (`overlay_hide_in_menus`, off by default, per profile). Each overlay can opt out in the inspector (`overlay_menu_keep_visible`). Construction Needs is kept by default, because it's made for station services and the right panel.
- **What counts as a menu:**
  - Status.json GuiFocus 1–4 (the ship panels), 5 (station services) and 11 (the Codex).
  - The journal's Music track for the screens with no GuiFocus: MainMenu, CQCMenu, FleetCarrier_Managment (the game's own spelling), GalacticPowers and Squadrons. Any other track, LoadGame or Shutdown ends it. This comes from the journal, so it can lag by up to about a second.
- **What the game can't tell us:** it writes nothing when the pause (Esc) menu opens, so that one isn't covered.
- **The pause menu is PARKED** (you, 2026-10-30: "lets not worry about the pause", and keep it out of the build). What was learned, in case it comes back:
  - **Signals that might mark it:** the mouse pointer (showing, freed from the window) or the keys that open it. Reading or hooking the game itself is ruled out (Frontier's terms).
  - **The keys:**
    - Esc on the keyboard and Start on a controller open it; no preset binds either.
    - The `Pause` action is an extra binding: P in 23 of Frontier's 29 presets, nothing in 5, and a joystick button in one.
    - `StartPreset.4.start` names a preset per control section, and they can be mixed (yours: ConsoleX360, Custom, KeyboardMouseOnly).
  - **Finding Frontier's presets** for any install: the running game's folder, Windows' installed-programs list (the standalone client), Steam libraries, Epic, then Frontier's default folders.
  - **Dev tools only, never built:** `tools/elite_bindings.py` (the reader) and `tools/pause_probe.py`. The probe has `keys`, `selftest` (presses Esc itself and takes screenshots), `watch` (Scroll Lock marks) and `report`. Delete both if not wanted.
- **Code:** `HtmlOverlayStudioMixin._in_game_menu` and `_observe_menu_music`. It shares `_apply_map_overlay_hiding`, so menus get the same cloaked, all-at-once hiding as the maps.
