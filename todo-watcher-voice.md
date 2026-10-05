# TODO: The Watcher speaks

Parked idea, to come back to. Give The Watcher (the heartbeat orb) a voice: a calm, weary, quietly unimpressed robot that comments on your flying now and then. It has watched every jump of your career, and none of them impressed it.

The joke is in the spirit of Hitchhiker's depressed robot, but **The Watcher is our own character**. Never use the name Marvin, and never quote Douglas Adams.

## Ground rules

- [ ] **Opt-in, off by default.** The README promises feedback is "quiet on purpose", and that stays true unless someone switches the voice on. Update the README line ("no voice and no AI chatter") when this ships.
- [ ] **No AI and no cloud.** Templated lines only, spoken by a model running on the user's PC.
- [ ] **Real figures only.** Any number it says comes from the journal; never invent telemetry.
- [ ] **Rare, not chatty.** Rate-limited, and it speaks only at moments that matter.

## Voice (text to speech)

Windows' built-in TTS is out: it sounds bad.

- [ ] **Engine: Kokoro-82M via `kokoro-onnx`** (Apache-2.0). Good quality and faster than real time on CPU.
  - Try the British male voices first (`bm_george`, `bm_lewis`; check the names).
  - Fallback: **Piper**, which is smaller and faster but more robotic. Its maintained fork is GPL-3, which is fine for us.
  - Avoid `edge-tts` (unofficial use of Microsoft's online service) and Coqui XTTS (non-commercial licence).
- [ ] **Don't bundle the model.** Download it the first time the voice is switched on (about 90 MB int8), checked by SHA-256 the way the updater checks releases (`core/updater.py`).
- [ ] Check how much `onnxruntime` adds to the onefile exe (roughly 15–50 MB), and whether it's worth loading only when the voice is on.
- [ ] Add licences to `THIRD_PARTY_NOTICES.md`: Kokoro, the voice pack, onnxruntime, kokoro-onnx.

## Sounding weary

Post-process in the deck's Web Audio, no special model needed.

- [ ] Pitch down 10–15% and slow slightly (`playbackRate` of about 0.88 does both).
- [ ] Add a gentle low-pass filter and a faint ring-modulator shimmer ("metallic but tired").
- [ ] Add longer pauses before the punchline, and maybe an occasional synthesized sigh.
- [ ] Cache the audio for fixed lines; synthesize lines with numbers in them on the fly.

## The orb speaks

- [ ] While a line plays, the eye's glow and iris follow the voice's loudness. Reuse the music player's live-levels approach (see the Music Player and Heartbeat memory notes). The orb itself is drawn in `web/assets/heartbeat-orb.js`.
- [ ] The Watcher reacts visually to everything as it does now, and speaks only occasionally.

## What it says

- [ ] Hook into the heartbeat classifier (`heartbeat_events.py`): it already sorts every journal event into kinds, so the voice just picks a line for some of them.
- [ ] Rate limit: at most one remark every few minutes, plus a chattiness setting.
- [ ] Start with about five moments:
  - **Jump into an empty or worthless system:** "Nothing here. I could have told you that. I watch, you know."
  - **Low fuel:** "Fuel at eight percent. I'd panic, but I find it so tiring."
  - **Interdicted:** "Someone wants your cargo. I'd say I'm surprised, but I've seen your flying."
  - **First footfall:** "First footfall. Nobody has ever stood here before. I can see why."
  - **Long session or docking after a long trip:** "Four hours. I've been watching the whole time. Not that anyone asked."
- [ ] Later candidates: a big exobiology or cartography payout ("Thirty-one million credits. I suppose you'll want me to be happy about that."), death, rebuy, a long route plotted, a jumponium haul.
- [ ] Keep two or three variants per moment so it doesn't repeat itself.
- [ ] Quiet during replay and the first-run history scan. It only speaks about live events.

## Settings

Per the Studio/Settings split, this goes in Settings, not Overlay Studio.

- [ ] Add a **Watcher voice** on/off switch, plus a chattiness level (rare / sometimes / talkative) and a volume.
- [ ] Register the new settings in the `config.py` `PROFILE_*` tuples and defaults.
- [ ] A **Test voice** button that downloads the model if needed and says one line.

## Prototype first

Build the smallest version that shows whether the voice lands before building it properly:

- [ ] Kokoro with one voice, the weary effect, and the eye lighting up with the speech.
- [ ] About five event lines and the on/off switch.
- [ ] Then decide: keep Kokoro or try Piper, settle the voice and effect, and choose which moments it should speak at.
