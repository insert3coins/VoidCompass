# Lyra — the fifth companion

Select **Lyra** in the companion switcher. She appears on the deck’s **BRIDGE**, in the floating Companion overlay (enable it in **Overlay Studio**) and on the boot screen when selected at startup.

## Who she is

Lyra was a ship’s computer. Her first commander was a very good pilot who flew too far, ran out of fuel and was lost. A passing cargo ship had an empty memory chip in its hold, and Lyra jumped aboard. That is how she came to be yours.

She is bright, exact and fond of full tanks. She checks the fuel first, plots the way home before the way out, and says goodnight to the ship when you log off. Her two styles are **Bright** (warm, with a robot’s dry humour) and **System** (terse readings), chosen under her commentary setting.

She is a full officer, like Aster, Axiom and Meridian:

- **Her own words** for every event the others speak about: arrivals, scans, biology, mining, the Rhino, routes, docking, combat, the law, missions, carriers, Powerplay, squadrons and the quiet hours. Fuel matters more to her than to most: scooping, low fuel and SRV fuel are her particular interests.
- **TALK**: greetings, what she can do, every ship command and lookup the others answer. Say “hello Lyra” or her name before a command.
- **Her story, “The Empty Chip”**: eight chapters, told over active service, with echoes that stir on real journal events. One request comes after Chapter III: take her to a star nobody has discovered.
- **The registry field**: she learns your name the way the others do.
- **Keepsakes**: postcard notes in her hand, Captain’s Log paragraphs, overnight logs and a share code friends can meet.
- **The crew**: the others each have a passage about her arrival, she has her own account of meeting each of them, she takes part in the Night Watch scenes, debriefs and handovers, and she is on the **watch rota** with **ordinary flight** as her default duty.
- **Achievements**: four of her own (Power On, Full Tanks, Every Gauge Read, Uncharted). Full Crew now needs all five companions, and The Watch Rota needs all 35 crew passages.

## Her voice

Lyra speaks with the GLaDOS-style female robot Piper voice, `glados.onnx` and `glados.onnx.json` in [models/lyra](../models/lyra/README.md). A source checkout with those files present only fetches the shared Piper engine; elsewhere the app downloads her pair from this project’s GitHub (`models/lyra/`) and checks it against the recorded sizes and SHA-256 hashes. She has her own receipt, so installing or removing her voice leaves the other companions’ voices alone. Turn her voice on, test it, and set its level, speed and volume in her **VOICE** tab.

## A face that moves

[lyra-robot.js](../web/assets/lyra-robot.js) builds her from real Three.js geometry: a pearl shell with a convex visor, ring optics, ear housings, antenna fins, neck joints and illuminated chest armour. Her forehead is plain: **no logo, lettering or badge**.

- **Speaking:** her jaw opens with the playback level of her voice and closes in the pauses. Microphone input and queued text never move it.
- **Expressions:** her face wears the mood of what she is saying. Pleased thoughts widen her smile, squint her optics and lift her fins. Wary ones flatten the smile, widen her eyes and sweep the fins back. Downcast ones turn the smile into a frown, lower her gaze and droop the fins. Curious ones tilt her head and make one lens larger than the other. Danger (low fuel, overheating or a threat) shows worry whatever she is saying. When the thought goes, her face settles back to rest.
- **Idle:** blinks, gentle head and fin movement, chest-light pulses and her own inner halo of travelling arcs.

Fixed focus keeps her head still; the expression still shows in her face. Idle animation Off parks the display once her face has settled. Reduced motion changes expressions at once instead of easing, closes the mouth and pauses continuous animation. Hidden displays stop rendering.

## Appearance

**Overlay Studio → Companion** offers the shared display controls:

- Sizes: **54, 72, 96, 144, 192 and 256 px**.
- **Lyra aurora**: cyan `#74ddff` with rose `#ec9fdb` accents. Theme accent, Ice cyan and Brass are also available. The shell stays pearl while the optics, lights and frame follow the palette.
- Fixed, Tracking or Expressive focus; Calm, Standard or Lively animation; idle animation; and the shared frame rate.

Size, focus, idle animation and liveliness are shared by the whole crew: set them once and every companion uses them. Her colour is her own, as are her voice and commentary settings, per commander profile.

## Local API

Lyra has the same capabilities as the other officers: `thought`, `poke`, `answer`, `book`, `story`, `name`, `voice`, `postcards`, `share_code` and `meet`. Her voice model is reported as “Lyra voice”.

## Resources and packaging

The robot reuses the bundled Three.js r185 renderer and the shared motion, colour, frame and speech-level adapters. It makes no external asset requests. Her model files must be pushed to the project’s GitHub under `models/lyra/` for other installs to download them.
