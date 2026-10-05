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

## What it says: semi-alive, never a jukebox

The Watcher must not feel like one fixed line per event. If it says the same thing twice, the illusion breaks. So it **remembers what it has said, notices patterns, and builds its lines from parts**. There's still no AI: it's all templates, rules and the commander's real journal, so it stays predictable, private and true.

### It remembers

- [ ] **A memory per commander profile** (`watcher_memory.json`, saved like other profile files). It records:
  - every line it has spoken, with when and why
  - what it has commented on: topics and the specific things, such as a system, a station, a body or a commodity
  - running counts it can bring up later: interdictions today, deaths this week, jumps this session, the longest silence
- [ ] **Never the same line twice within a long window** (days, not minutes). Each topic also gets its own cooldown, so three interdictions in an hour don't get three interdiction remarks.
- [ ] **Never the same subject twice:** once it has said something about a system, a body or a station, it doesn't comment on that one again, unless something new happens there.
- [ ] **It knows when it already spoke.** When a topic comes back, it says something different, or brings up last time:
  - First interdiction: "Someone wants your cargo."
  - The second today: "Again. That's twice since lunch, if I ate lunch."
  - The third: it says nothing. Then, later: "I've stopped commenting on the interdictions. You've stopped avoiding them."
- [ ] **It can stay silent on purpose.** Choosing not to speak is part of the character. A rare "…" line, or a sigh after a long quiet, says more than a fourth remark.

### It builds lines from parts

- [ ] **Lines are built from pieces, not stored whole:** an opener, then the observation (with real figures), then sometimes an aside. Each piece has many variants, and the memory rules out recent ones. A handful of pieces makes hundreds of distinct lines.
  - Openers: "Hm." / "Well." / "Noted." / "There it is." / nothing at all.
  - Observation: "{fuel} percent fuel." / "Interdicted by {pilot}." / "{system}: {bodies} bodies and not one of them interesting."
  - Asides, used sparingly: "I'd panic, but I find it so tiring." / "Not that anyone asked." / "I'll make a note. I make a lot of notes."
- [ ] **The real figures make it specific:** the system's name, the number of bodies, the credits, the time since the last dock, the commander's own records ("your longest jump this week"). The same event never sounds the same twice, because the facts differ.
- [ ] **Numbers spoken naturally:** "thirty-one million", not "31,204,553". Round where a person would.

### It notices patterns, not just events

- [ ] **Streaks and trends, worked out from the journal and its memory:**
  - the fifth empty system in a row
  - three sales at the same station
  - a long session getting longer
  - credits going down all evening
  - the first jump after a long break ("Back. It's been eleven days. I counted.")
- [ ] **Callbacks to earlier remarks:** "Remember that 'worthless' system on Tuesday? Still worthless. I checked." Use them sparingly, and only when they're true.
- [ ] **Milestones from the commander's own record:** their 1,000th jump, first visit to a new region, a personal best payout. It speaks once each, because it remembers.

### Its mood drifts

- [ ] **A slow mood that changes its choice of words, not the facts.** It's built from the session: length, how many remarks it has made, good and bad events.
  - weary (the default)
  - grudgingly impressed after a big payout
  - quietly smug after a death it "saw coming"
  - almost warm late in a long session
- [ ] **It warms up and winds down:** quieter in the first minutes of a session, and a dry sign-off at the end ("Shutting down. Don't worry about me.").

### Rules that keep it bearable

- [ ] **Hook into the heartbeat classifier** (`heartbeat_events.py`): it already sorts every journal event into kinds. The voice adds memory and rules on top.
- [ ] **A rate limit with a budget:** at most one remark every few minutes, and a per-session allowance set by chattiness (rare / sometimes / talkative). Important moments (low fuel, hull damage) can borrow from the budget; trivia can't.
- [ ] **Never during danger chatter:** it stays quiet while the game is busy (combat, landing, docking request); a remark waits for a calm moment or is dropped.
- [ ] **Quiet during replay** and the first-run history scan. It only speaks about live events.
- [ ] **A "say that again" and a "not that one" control:** replay the last line, or retire a line or topic the commander dislikes, which the memory then honours.

### Starting moments

Each one is a topic with pieces, not a fixed line. Examples of what each could produce:

- **Arriving somewhere empty or worthless:** "Nothing here. I could have told you that. I watch, you know."
- **Low fuel:** "Eight percent fuel. I'd panic, but I find it so tiring."
- **Interdicted:** "Someone wants your cargo. I'd say I'm surprised, but I've seen your flying."
- **First footfall:** "First footfall. Nobody has ever stood here before. I can see why."
- **Long session, or docking after a long trip:** "Four hours. I've been watching the whole time. Not that anyone asked."
- **Later:** big exobiology or cartography payouts ("Thirty-one million credits. I suppose you'll want me to be happy about that."), death, rebuy, a long route plotted, a jumponium haul, trading runs (with the Trading tab's figures), BGS work.

### Writing the lines

- [ ] **Keep the line pieces in a data file** (for example `data/watcher_lines.json`), not in code. They're grouped by topic, with tags for mood and for which facts each piece needs. That makes adding lines, or reviewing the tone, easy.
- [ ] **Aim for at least 6–10 variants per piece** for every launch topic, so the "never repeat" rules have room.
- [ ] **A test that builds lines thousands of times** across simulated sessions and checks:
  - no exact repeats within the window
  - every `{fact}` is filled from real data
  - nothing comes out over the length limit

## Settings

Per the Studio/Settings split, this goes in Settings, not Overlay Studio.

- [ ] Add a **Watcher voice** on/off switch, plus a chattiness level (rare / sometimes / talkative) and a volume.
- [ ] Register the new settings in the `config.py` `PROFILE_*` tuples and defaults.
- [ ] A **Test voice** button that downloads the model if needed and says one line.

## Prototype first

Build the smallest version that shows whether the voice lands before building it properly:

- [ ] Kokoro with one voice, the weary effect, and the eye lighting up with the speech.
- [ ] The memory and line-building from the start, even with only a few topics. "Doesn't repeat itself" is the point, so the prototype has to show it.
- [ ] About five topics (with several pieces each) and the on/off switch.
- [ ] Then decide: keep Kokoro or try Piper, settle the voice and effect, and choose which moments it should speak at.
