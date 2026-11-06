# Lyra — robot overlay preview

Select **Lyra** in the companion switcher, then enable the Companion overlay in **Overlay Studio**. She appears on the deck’s **BRIDGE**, in the floating overlay, and on the boot screen when selected at startup.

Lyra is a female robot inspired by the supplied robot reference: a rounded pearl shell, recessed dark visor, cyan ring optics, small antenna fins, a smiling mechanical mouth and illuminated chest armour. Her forehead is plain: **no logo, lettering or badge**. The reference background is not included.

## A real 3D display

[lyra-robot.js](../web/assets/lyra-robot.js) builds the robot from Three.js geometry. The shell has openings for the convex visor and mouth, with separate lenses, ear housings, neck joints, shoulders and antennae. Lighting and reflections shade the curved surfaces. No portrait plane, generated image, external character mesh or model download is used.

The head and optics follow the shared attention system. Idle animation adds blinks, gentle head movement, antenna movement and chest-light pulses. Her own inner halo has three illuminated arcs travelling around a metal track, an opposing stream of small lights and a gentle three-dimensional tilt. It sits behind the robot, brightens with activity and follows her Studio palette and animation controls. The shared outer instrument frame provides contrast over bright scenery, with transparent outer corners.

The jaw is deformed by the shared playback-amplitude signal, opening the mouth during speech and closing during silence. Microphone input and queued text do not move the mouth. This is amplitude-driven articulation, not phoneme lip sync. **Lyra’s voice is not integrated yet**, so mouth movement is currently exercised with simulated playback during validation; normal use remains silent.

## Appearance

**Overlay Studio → Companion** offers the existing display controls:

- Sizes: **54, 72, 96, 144, 192 and 256 px**. The chosen size carries across companion switches.
- **Lyra aurora**: cyan `#74ddff` with rose `#ec9fdb` accents. Theme accent, Ice cyan and Brass are also available. The shell stays pearl while the optics, lights and instrument frame follow the palette.
- Fixed, Tracking or Expressive focus; Calm, Standard or Lively animation; idle animation; and the shared frame rate.
- Existing position, opacity and caption-layout controls remain shared. Lyra’s palette, focus, motion and liveliness stay with her commander profile.

Fixed focus centres her attention while keeping idle effects. Idle animation Off parks the display between activity; journal events and warning states can still wake it. Reduced motion pauses continuous animation and closes the mouth. Hidden displays stop rendering. Switching disposes the old renderer, geometry, materials and generated reflection map.

## Pending content

This addition is **overlay only**. Lyra has no registered app Piper voice, app voice download, greetings, command replies, story, commander-name introduction, postcard writing or crew dialogue yet. Her page marks these features as pending and disables unavailable controls. Selecting her does not substitute the Watcher’s voice or another persona’s writing.

The user selected the **GLaDOS-style robotic female Piper voice** on 7 November 2026. The verified `glados.onnx`/`glados.onnx.json` pair is stored directly under [models/lyra](../models/lyra/README.md), with source attribution, hashes and a [working speech sample](../models/lyra/samples/glados.wav). The other voice candidates have been removed. App integration will be handled by the user; Lyra remains silent in the app until that work is completed.

She is excluded from the existing four companions’ story, crew chatter and automatic rota assignments. Choose her manually to preview her display; the existing rota still follows its normal manual-choice hold if enabled. Use [todo-heartbeat.md](../todo-heartbeat.md) for the later voice and story work.

The Local API lists Lyra and permits selection, with capabilities `["overlay"]`. Her story progress is zero and her voice model is null. Dialogue/story operations return an unsupported-capability response. Existing companions retain their own capabilities.

## Resources and packaging

The robot reuses the bundled Three.js r185 renderer, shared motion, colour, frame and speech-level adapters. Its local JavaScript module is registered in the dashboard static allowlist and sandbox CORS list. Existing recursive `web/` and `docs/` build packaging includes the display and these instructions. It makes no external asset requests.

The earlier human-portrait prototype was superseded by the robot on **7 November 2026**. Its generated portrait and downloaded human mesh are not runtime dependencies or bundled robot assets.
