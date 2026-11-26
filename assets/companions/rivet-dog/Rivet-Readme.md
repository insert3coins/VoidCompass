# Rivet · VoidCompass dog companion

## Preview

Extract this ZIP, then open `assets/companions/rivet-dog/preview.html` in a browser. The preview starts at the 144 px HUD size. Use the clip picker to play any of the 25 animations. The preview starts on the first Signature move. In Mouth opening, move the slider and press **Blink now** to try live speech and blinking together.

## Manual placement

Copy the two folders below into the corresponding locations under your VoidCompass / SurveyAnalysis project root.

| Relative project folder | Contents |
| --- | --- |
| `assets/companions/rivet-dog/` | Source manifest, 1,386 full-head 512 × 512 transparent PNG frames, 11 cropped blink patches, outer ring artwork and offline preview |
| `web/assets/rivet-dog/` | 21 sprite sheets with 256 × 256 cells, a cropped eye sheet and the runtime index `rivet-dog.json` |

Use `rivet-dog` when registering Rivet as a new companion. The stock Nova loader points explicitly to its own asset directory and index. For this companion, point the portrait renderer at `web/assets/rivet-dog/rivet-dog.json` and resolve its sprite sheets in the same folder. The preview runs directly after extraction. App registration is a separate manual step.

## Playback

The 23 shared clips follow Nova’s original timing, hold frames and canvas sizes. The two additional signature clips have dedicated source sequences and runtime sheets. The display sizes are 54, 72, 96, 144, 192 and 256 px. Direction labels refer to the viewer’s screen.

- **Speaking** and **Speaking with a blink** are timed source sequences. For live voice levels, drive the runtime `mouth-levels` sheet from 0 through 8 and overlay `blink-layer.webp` using the rectangle in the runtime index.
- **Goodnight** holds frame 71. **Downcast** and **Wary** hold frame 22. **Glance left** and **Glance right** hold frame 16. Frame numbers start at zero.
- **Nod** and **Head shake** play once and settle back at center. Both have runtime sheets.
- The portrait sequences, blink patches and runtime sheets contain the pet on transparency. VoidCompass can draw its own animated ring around the pet. The offline preview starts with the pet alone. Select **Show outer ring** to display the separate `outer-ring.png` artwork and its animated markers behind the pet.
