# Nova — the sixth companion

Select **Nova** in the companion switcher. She appears on the deck's **BRIDGE**, in the floating Companion overlay (enable it in **Overlay Studio**) and on the boot screen when she is selected at startup.

## Who she is

N.O.V.A. stands for **Navigation, Observation & Vessel Assistance**. She began as an experimental successor to the ordinary COVAS: an assistant that would notice patterns, anticipate a pilot's needs and help before being asked. The project lost its funding before its final evaluation, the research station closed and her data core went into storage. Years later a restored build was released to independent commanders, and she came aboard yours through a station's tech services, to find five minds already on the bus.

She is intelligent, observant, curious, friendly and now and then playful. Human choices puzzle her: a detour to look at a world, a destination picked for its beauty, a discovery with no reward. She asks about them rather than judging. Her two styles are **Playful** (warm, curious, with an understated sense of humour) and **Assistant** (crisp and helpful), chosen under her commentary setting.

She is a full officer, like Aster, Axiom, Meridian and Lyra:

- **Her own words** for every event the others speak about: arrivals, scans, biology, mining, the Rhino, routes, docking, combat, the law, missions, carriers, Powerplay, squadrons and the quiet hours. Remarkable worlds, the Codex, life on the surface and complete systems interest her most.
- **TALK**: greetings, what she can do, every ship command and lookup the others answer. Say "hello Nova", or her name before a command.
- **Her story, *The Unfinished Build***: eight chapters, 48 entries, recovered from her development logs as you fly. The chapters open with hyperspace jumps, bodies scanned, exploration data sold, organisms analysed, dockings and long jumps, and every gate has a time alternative. Echoes stir on real journal events. One request comes after Chapter VII: take her to the heart of the galaxy.
- **The user profile**: she learns your name the way the others do.
- **Keepsakes**: postcard notes in her hand, Captain's Log paragraphs, overnight notes and a share code friends can meet.
- **The crew**: the others each have a passage about her arrival, she has her own account of meeting each of them, and she takes part in the Night Watch, debriefs, handovers, crew banter and off-watch remarks. She has no default duty on the **watch rota**; give her any duty on the companion page.
- **Crew Orders**: two kinds of her own, both about looking properly: log three new Codex entries out past the bubble, and take a picture of a remarkable world in the system you're in. Her Order File is *Page Eleven*.
- **Achievements**: four of her own (Activation, Page Eleven, Every View Kept, The View from the Middle). Full Crew now needs all six companions, and The Watch Rota needs all 48 crew passages.

## Her voice

Nova speaks with the **Cori** British-English Piper voice, `en_GB-cori-medium.onnx` and its `.onnx.json`, in [models/nova](../models/nova/README.md). It is the piper-voices v1.0.0 build, trained on Cori Samuel's public-domain LibriVox recordings. The newer Cori in the piper-voices main branch needs Piper 1.5, which the app's engine predates.

A source checkout with those files present only fetches the shared Piper engine; elsewhere the app downloads her pair from this project's GitHub (`models/nova/`) and checks it against the recorded sizes and SHA-256 hashes. She has her own receipt, so installing or removing her voice leaves the other companions' voices alone. Turn her voice on, test it, and set its level, speed and volume in her **VOICE** tab.

## Her display

Nova isn't built from 3D geometry like the others. She is an illustrated face projected inside the same instrument housing, from sprite sheets in `web/assets/nova/` (made from the frames in `assets/companions/nova` by `tools/make_nova_frames.py`).

- **Her bezel** is pearl-silver, with a lit ring at each side like the rings at her temples and a four-point star at the top.
- **States**: idle, listening, working, charging and alert each have their own loop. Going to alert, she looks surprised first.
- **Speaking**: her mouth follows the playback level of her own voice, through nine mouth positions, closing in the pauses, with a blink over her eyes now and then. Microphone input and queued text never move it.
- **Moods**: a pleased thought brings a warm smile (or delight), curious a curious look, wary a thoughtful one and downcast a reassuring one. Each plays once, then she returns to rest.
- **Projection**: faint scan lines, a slow band of light in her colours, and, rarely, a flicker.

Fixed focus keeps her still in the frame. Idle animation Off parks the loop. Reduced motion holds a still face (a mood's peak while it lasts) and closes her mouth. Hidden displays stop rendering.

## Appearance

**Overlay Studio → Companion** offers the shared display controls:

- Sizes: **54, 72, 96, 144, 192 and 256 px**.
- **Nova ice**: ice blue `#8fd8ff` with pearl `#e6ecff` highlights. Theme accent, Ice cyan and Brass are also available. Her face keeps its own colours; the bezel, lights and projection follow the palette.
- Fixed, Tracking or Expressive focus; Calm, Standard or Lively animation; idle animation; and the shared frame rate.

Size, focus, idle animation and liveliness are shared by the whole crew. Her colour, voice and commentary settings are her own, per commander profile.

## Local API

Nova has the same capabilities as the other officers: `thought`, `poke`, `answer`, `book`, `story`, `name`, `voice`, `postcards`, `share_code` and `meet`. Her voice model is reported as "Nova voice".

## Resources and packaging

Her sheets total about 4 MB and are served from the deck's own assets (with CORS for sandboxed pages, like the renderer modules). Her model files must be pushed to the project's GitHub under `models/nova/` for other installs to download them.
