# Overlay fit fix (5.5.3.9.1)

5.6.8 delivery: the shared host sends each page a snapshot/revision envelope,
including while its window is hidden. Measurements carry the page generation,
layout revision and a monotonic measurement number. Only measurements for the
current model and layout update the server's height and shapes; a shapes-only
report preserves the last height. Window geometry changes invalidate layout
readiness. DOM layout can be acknowledged without waiting for a hidden
animation frame; resize and font completion remeasure the current view.
`fitToWindow` and `designHeight` below keep their existing units and scaling.

How to fix an overlay that cuts off its text or its bottom rows, at large text or on a PC with odd Windows scaling.

Already fixed: **Cargo, Prospector, Planet Materials, Station Link.**
Fixed earlier, in their own way: Nav HUD (fits its zoom to the window), Toasts (wrap and measure).

Nav HUD (5.6.8): Small text scales every small-type token as well as raising the minimum font size, so labels already above the floor also grow from Large to Larger. The window widens to fit. Its fitted design width is the layout width (500 standard, 620 legacy expanded) × label width / 500 (label widths 500 / 540 / 580). Python window sizing and the browser fit use the same ratio.

## Symptoms

- **Bottom rows missing.** The header says 5 stacks, but only 3 show. Seen on the user's own PC at 100% text size.
- **Labels cut with "…"** even at 100% (for example "SHIP CARGO H…", "5 STACKS · 1…").
- **At 150% or 200% text:** names and values cut short, labels running into their values, columns squeezed.

## The two causes

1. **The page is drawn at another scale than its window was sized for.**
   - The app sizes a window as design size × text size × monitor scale.
   - WebView2 sometimes draws the page at a different scale. Possible reasons: a Windows scaling setting the app can't see, or a window sized against the other monitor.
   - The page then lays out narrower than designed, so text is cut.
   - The height it reports comes out too small, so the window is too short and the last rows fall off.
2. **Fixed-pixel sizes in the overlay's CSS.**
   - Fonts grow with `--scale`, but columns written in plain px (`grid-template-columns: 48px 1fr 112px`) don't.
   - Text then gets squeezed and ellipsised at large text sizes.

## The fix, step by step

### 1. app.js: fit to the window and report the height in design units

The shared helpers live in `web/assets/overlay-client.js`:
- `VoidCompassOverlay.fitToWindow(root, designWidth, effects)` zooms the page down when its window is narrower than designed, and refits on resize.
- `VoidCompassOverlay.designHeight(root, minimum)` reports the height as it would be at the design width.

In the overlay's `render()`, call the fit straight after `applyTheme`:

```js
VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, snapshot.effects || {});
VoidCompassOverlay.fitToWindow(root, 520, snapshot.effects || {});   // 520 = design width
```

Then replace the overlay's own height measuring:

```js
function contentHeight() {
  return VoidCompassOverlay.designHeight(root, 330);   // 330 = the window's min height
}
```

Take the **design width** and **min height** from the overlay's Python `_dimensions`: the numbers that get multiplied by the text scale. For example, `html_station_overlay.py` has `520 * scale` and `330 * scale`.

| Overlay | Design width | Min height |
|---|---|---|
| Cargo | 410 | 190 |
| Prospector | 400 | 180 |
| Planet Materials | 440 | 190 |
| Station Link | 520 | 330 |

### 2. styles.css: let the layout grow with the text

- **Fixed-px columns:** scale them, for example `calc(76px * var(--scale))`. Use `max-content` where a column holds a short label.
- **Fixed-px icon or glyph sizes** (width, height, inset): scale them too.
- **Text that can be long** (names, values, services): remove `white-space:nowrap` and `text-overflow:ellipsis`, and add `overflow-wrap:anywhere` so it wraps instead.
- **Tiles in a row** that hold values like "L 9 · M 18 · S 17": `grid-template-columns: repeat(N, auto)` sizes each tile to its content, so the value doesn't wrap mid-number.
- **Scale columns, not min-heights.** Scaled min-heights make the page too tall for its max height (Planet Materials broke that way).

### 3. Test it

Add the overlay to `OVERLAYS` in `tests/test_overlay_text_fit_5539.py` as (page folder, snapshot key, model, design width, min height, max height). The model comes from its `build_*_model`. Two tests then cover it:
- `test_nothing_cut_off_at_large_text`: 100%, 150% and 200% in the window the app gives it.
- `test_fits_a_window_drawn_at_another_scale`: page drawn at 1.25 and 1.5 against its window. No text cut, nothing below the window.

**Gotcha:** a test that replaces `window.VoidCompassOverlay` wholesale needs `fitToWindow` and `designHeight` in its stub, or the page throws. For example, `test_planet_materials_overlay_visuals.py`.

Run the fit tests, then the whole suite:

```
python -m unittest tests.test_overlay_text_fit_5539
python -m unittest discover -s tests -t .
```

## Checking an overlay by eye

Copy the render script pattern from the fit test:
- Serve `web/`, append the startPolling stub to `overlay-client.js`, and call `renderIt(...)` with a realistic model.
- Size the viewport to `design × scale / drawn`.
- Take a screenshot at 100%, at 200%, and at drawn 1.25.

Good test data: long names such as "Shinrarta Dezhra Jameson Memorial" and "Low Temperature Diamonds", and enough rows to fill the overlay.
