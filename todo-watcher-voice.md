# TODO: The Watcher speaks

> **On hold (2026-10-10): no voice.** The Watcher stays text only; there's already plenty going on. Don't start this unless it's asked for again. If it is, the choices already made are: Piper as the engine, a separate engine download, Alan (`en_GB-alan-medium`) as the default voice, and a Voice level setting.

Parked idea, to come back to. Give The Watcher (the heartbeat orb) a voice: a calm, weary, quietly unimpressed robot that comments on your flying now and then. It has watched every jump of your career, and none of them impressed it.

The joke is in the spirit of Hitchhiker's depressed robot, but **The Watcher is our own character**. Never use the name Marvin, and never quote Douglas Adams.

## The voice lab (built, for testing)

A standalone test bench is in [`Voice/`](Voice/README.md), outside the app. It has:
- Kokoro on this PC, the weary effect, and the piece cache with joining
- a small line builder and spoken numbers
- a listening page with sliders, timings and a benchmark
- an orb that follows the voice

**First results (5 Oct 2026, with Elite Dangerous running):**
- **`fp32` runs at a real-time factor of about 0.6:** faster than real time, a pass.
- **`int8` runs at about 4.7, around 11 times slower on this CPU.** So "int8, 90 MB" below is wrong for live use; plan on `fp32` (about 325 MB).
- **First sound with nothing cached is about 0.9 s** against the 300 ms goal. Every piece has a fixed cost of about 0.8 s, mostly phonemising and model start-up, so short pieces don't help on their own.
- **From the cache, first sound is about 12 ms.** Caching and generating ahead aren't optional: they are what makes live work.
- **About 23–30% of the CPU while speaking, and about 700 MB of memory.** Whether the game's frame rate holds still needs watching.
- **kokoro-onnx 0.4.7 sends `speed` with the wrong type** to these model files; `Voice/engine.py` works around it.

**Piper, tried the same day (game running):**
- **About 13 times faster than Kokoro:** a one-word piece takes about 50–80 ms, the median first sound is about 60 ms (a pass, with nothing cached), and the real-time factor is about 0.07.
- **Half the memory (about 330 MB), with a 63 MB model** instead of 325 MB.
- **It sounds more robotic,** which may fit The Watcher. **The choice now comes down to how it sounds:** compare `Voice/out/compare/`.
- **If Piper sounds right,** it makes live speech easy: no fixed-cost problem, a small download, and the cache becomes a bonus rather than a necessity. Its code is GPL-3 (fine for us), but check the chosen voice's own licence.

**Next in the lab:**
- Cut the fixed cost per piece: phonemise once, keep the espeak process warm, and batch pieces.
- Try `fp16` and DirectML on the GPU.
- Measure with the cache warmed up.

## The engine: Piper, with downloadable voices

**Decided (5 Oct 2026): Piper is the long-term engine.** Kokoro sounds more natural, but Piper meets the live budget with room to spare, and its voices are downloadable models, which gives commanders a choice.

**Why Piper:**
- **Speed:** first sound in about 60 ms, at about 0.07 of real time, with the game running.
- **Lighter:** about 330 MB of memory, and about 63 MB per medium voice.
- **Its code (piper1-gpl) is GPL-3,** matching ours.

**The voice catalogue:** Piper publishes `voices.json` (HuggingFace `rhasspy/piper-voices`).
- 177 voices, 38 of them English (en_GB and en_US), in low, medium and high quality.
- Each file is listed with its size and MD5 (and HuggingFace gives its SHA-256).
- Multi-speaker models (VCTK, LibriTTS) hold many voices in one file, chosen by speaker number.

To do:

- [ ] **Pick The Watcher's default voice by ear** (start with `en_GB-alan-medium` and `en_GB-northern_english_male-medium`; compare in `Voice/out/compare/`) and tune the weary effect for it.
- [ ] **A voice picker in Settings:** a list from the catalogue showing language, accent, quality, size and a **Preview**. Choosing a voice downloads it, checked against the catalogue's digest (the way `core/updater.py` checks releases), into the app folder. Removing a voice frees the space.
- [ ] **Only voices we've vetted.** Each Piper voice is trained on a dataset with its own licence (in its `MODEL_CARD`), and some may not allow every use. Keep a short allow-list of checked voices in the app, rather than offering the whole catalogue blindly. Credit each shipped voice's dataset in `THIRD_PARTY_NOTICES.md`.
- [ ] **Multi-speaker models:** for VCTK or LibriTTS, the picker lists their speakers by number with previews, since one download gives many voices.
- [ ] **The effect suits the voice:** pitch and speed can differ per voice, so each voice keeps its own sound settings, with The Watcher's chain on top. The cache key already includes the voice.
- [ ] **Changing voice changes the cache:** pieces are cached per voice; switching voices starts fresh, and the old voice's pieces are cleared after a while, or when the voice is removed.
- [ ] **Kokoro stays in the lab** as the "more natural" comparison. Only revisit it if a faster Kokoro (GPU, or a newer smaller model) ever meets the budget.

## Ground rules

- [ ] **Opt-in, off by default.** The README promises feedback is "quiet on purpose", and that stays true unless someone switches the voice on. Update the README line ("no voice and no AI chatter") when this ships.
- [ ] **No AI writing the lines, and no cloud.** The words always come from our templates and the journal.
- [ ] **Live first, pre-recorded only as a last resort.** The Watcher's voice is generated **live, quickly, on the commander's PC while they play** (see "The voice: live, during gameplay"). Only if live doesn't work out (too slow, or it costs the game frame rate) do we fall back to a voice pack generated once here and shipped as recordings (see "Last resort: a pre-recorded voice pack").
- [ ] **Real figures only.** Any number it says comes from the journal; never invent telemetry.
- [ ] **Rare, not chatty.** Rate-limited, and it speaks only at moments that matter.

## Our voice generator (dev tool, never shipped)

Our own script, run on this PC, that makes The Watcher's voice. It's where the voice, effect and speed are worked out for the live engine. If live doesn't work out, it also builds the pre-recorded pack, from the line data to finished clips to the release zip. It lives in `tools/watcher_voice/`, and nothing in it goes into the app or the release.

### Setup

- [ ] **Its own requirements:** `requirements-voice.txt` with pinned versions:
  - `kokoro-onnx`
  - `onnxruntime`
  - `numpy`
  - `soundfile` (libsndfile 1.2 or newer writes Ogg Opus)
  - `pyloudnorm`
  - maybe `scipy` for the filters
  
  It installs into a separate `.venv-voice`, so the app's own environment and build stay clean.
- [ ] **A `setup` command** that downloads the Kokoro model and voices file once, checks them against pinned SHA-256s, and keeps them in `tools/watcher_voice/models/`, which is gitignored.
- [ ] **Everything generated goes under `build/voice/`,** which is gitignored. Only the inputs are tracked:
  - the line data
  - the pronunciation list
  - the review decisions
  - the voice settings

### Commands

One script, `python -m tools.watcher_voice <command>`:

- [ ] **`say "text"`:** speak any sentence with the current voice and effect, and play it. For trying out wording and tone quickly.
- [ ] **`bench`:** the live-voice benchmark for the decision gate. It speaks a set of real Watcher lines and reports:
  - the delay to first sound and the real-time factor
  - CPU and memory use
  - results per engine (Kokoro CPU, Kokoro DirectML, Piper) and per thread count

  Run it with Elite Dangerous open, and save the results to compare between PCs.
- [ ] **`render`** (for the pack, last resort): generate every clip the line data needs.
  - **Incremental:** each clip is keyed by a hash of its text, the voice, the speed and the effect settings, so only new or changed clips are rendered again.
  - `--topic interdiction` renders just one topic.
  - `--takes 3` makes several takes of each clip, varied slightly in speed and pause so they don't sound identical.
- [ ] **`numbers`** (for the pack): build the spoken-number vocabulary (zero to nineteen, the tens, hundred, thousand, million, billion, point, percent, units, and the rounded forms like "about thirty"). It also checks that the number speaker in the app can say every figure it might need with those clips.
- [ ] **`review`:** open the listening page (below) and save what was decided.
- [ ] **`pack`** (last resort):
  - take the approved takes only
  - write `manifest.json` (clip id, file, text, length, takes, pack version, voice and settings used)
  - zip them as `VoidCompass-WatcherVoice-vN.zip`
  - write the `.sha256`
  - refuse to build if any line piece has no approved clip
- [ ] **`check`:** the same coverage check the app's test runs, from the dev side. It also lists clips that are too long, too quiet or clipped.

### Making it sound like The Watcher

- [ ] **Voice settings in one tracked file** (`tools/watcher_voice/voice.json`): which Kokoro voice (try the British male voices `bm_george` and `bm_lewis` first; check the names), the speed, and the effect settings. A pack records the settings it was made with, so it can be made again exactly.
- [ ] **The weary effect, done in Python** so it's baked into the clips:
  - pitch down 10–15% and slow slightly (resampling)
  - a gentle low-pass filter
  - a faint ring-modulator shimmer
  - a touch of room reverb
  
  The values are tuned by ear with `say`.
- [ ] **A pronunciation list** (`tools/watcher_voice/pronounce.json`) for Elite's words and anything the voice gets wrong: Thargoid, Frame Shift, Sagittarius A*, Guardian, jumponium, CMDR. Text is rewritten before it's spoken ("Sag A star"), so those words come out right.
- [ ] **Pauses and emphasis from the text:** commas, full stops and "…" give pauses. A small markup in the line data (for example `[pause 400]`, or `*word*` for a slower word) is turned into silence or a slower speed for that piece, so the punchline lands.
- [ ] **Clean clips:**
  - trim silence at the ends, leaving a short tail
  - even out loudness across every clip (one target, measured with `pyloudnorm`)
  - a soft fade at the edges so joins don't click
  - the clipping and length checks
- [ ] **Small files:** Ogg Opus at a speech bitrate (about 32–48 kbps, mono), which WebView2 plays natively.

### The listening page

- [ ] **A local HTML page** made by `review`. It lists every clip by topic, with its text, takes, length and loudness, and plays:
  - each take, to keep it or reject it
  - **sample joined lines,** built the same way the app joins clips (crossfades, gaps, shared reverb), with made-up figures, so the joins are judged in context
- [ ] **Decisions are saved** to `tools/watcher_voice/review.json` (tracked): approved and rejected takes, and notes such as "too fast" or "wrong stress". `render` makes new takes for anything rejected; `pack` only uses approved ones.

### Releasing a pack (last resort only)

- [ ] **Bump the pack version** when the line data or the voice changes. The app records which pack version its line data needs.
- [ ] **Upload the zip and its `.sha256`** as their own assets on the GitHub release, next to the app zip, like the app's own release files.
- [ ] **Credit the voice in the pack** (a `NOTICE` in the zip) and in `THIRD_PARTY_NOTICES.md`. Confirm first that Kokoro's model and voice licences let us distribute audio made with them.

### Tests for the generator

- [ ] **Unit tests for the parts that aren't audio:**
  - text clean-up and the pronunciation list
  - the pause markup
  - the cache keys (same input means no re-render)
  - the number vocabulary covering every figure
  - the manifest
  - the coverage check
- [ ] **No audio rendering in the normal test suite,** because it's slow and needs the model. A `render --dry-run` lists what would be made instead.

## The voice: live, during gameplay

The Watcher speaks lines made **at that moment**, generated on the commander's own PC in well under a second. Then it can say anything the templates can build, including names ("Shinrarta Dezhra again?"), exact figures and lines no recording could hold.

### Steps, with a decision gate

1. **Make the generator fast:** the dev tool's `say` and `render` (next section) are the test bed. Get the voice and effect right, then make them quick. **Done in the lab: Piper is fast.**
2. **Benchmark with Elite Dangerous running,** on this PC and on a modest one: delay to first sound, speed, CPU and memory, and the game's frame rate with and without it.
3. **The decision gate.** Live ships if:
   - the first sound comes within about 300 ms of the moment
   - lines are spoken faster than real time
   - there's no noticeable frame-rate loss on a typical gaming PC
4. **It passes:** build the live engine into the app (below).
5. **It doesn't, after a fair try** (including a smaller voice like Piper, and generating ahead): fall back to the pre-recorded pack, the last resort.

### What live needs

- [ ] **One voice, shared:** the effect chain (pitch, filter, shimmer, room) and the pronunciation list are one module, used by both the dev generator and the app's live engine. If the pack is ever needed, it sounds identical.
- [ ] **A speed budget:** the first sound within about 300 ms of the moment, and the whole line spoken faster than real time. **Piper meets it** (about 60 ms, real-time factor about 0.07, with the game running; see the voice lab). Keep measuring on modest PCs.
- [ ] **A warm engine:** a background worker process that loads the model once and stays ready, at low priority with few threads, so it never competes with the game. It's started only when the voice is on.
- [ ] **Streaming:** speak sentence by sentence (or in chunks), so the first words play while the rest is still being made.
- [ ] **Generating ahead:** use the quiet moments the game gives us.
  - While the frame shift drive charges, and in witch space, prepare the likely arrival lines for the next system: its name is already known from `FSDTarget`.
  - While docking, prepare the station lines.

  By the time the moment comes, the audio is ready.
- [ ] **Caching: once a piece is spoken, it's never made again.** The Watcher never repeats a whole line, so whole lines are rarely reused. Their **pieces** are reused constantly: openers, asides, numbers, units, and the names of systems and stations you go back to. So the cache works at the piece level:
  - **Every piece generated live is saved** as a small Ogg Opus file in the app folder (`voices/watcher/cache/`). Next time, it's played straight from disk, with no generating.
  - **Keyed by everything that shapes the sound:** a hash of the text, the voice, the speed, the effect settings and the engine version. Changing the voice or the effect makes new clips; the old ones are cleared out.
  - **Lines are joined from cached and new pieces,** with the same crossfades and shared room as the pack would use. A line can be part cached ("Back again at", "for the", "time"), part live (the station's name, the count).
  - **Shared across commander profiles:** it's the same voice. The Watcher's *memory* of what it said stays per profile.
  - **Warm-up:** when the voice is first switched on, the engine quietly generates the most common pieces in the background (openers, asides, the number vocabulary, units), so the first sessions already lean on the cache.
  - **A size limit** (for example 200 MB, adjustable), dropping the clips least recently used first; plus "Clear voice cache" in Settings.
  - **It grows into a personal voice pack:** over time, most of what The Watcher says comes from the cache, and the live engine only works on what's new. That's the best of both plans, and it also keeps the CPU cost falling the longer someone plays.
  - **Measure it:** the in-game readout shows how much of each line came from the cache, which feeds the decision gate too.
- [ ] **Never late, never wrong:** a line that isn't ready in time is dropped, not delayed. The Watcher never speaks about something that's already over.
- [ ] **Measure it in game:** a debug readout of generation time, delay to first sound, and the worker's CPU and memory, taken during real play.
- [ ] **The voice is downloaded** the first time the voice is switched on (The Watcher's default Piper voice, about 63 MB), checked against the catalogue's digest the way `core/updater.py` checks releases, and kept in the app folder. It's not in the release zip, so commanders who never use the voice don't download it. Other voices come from the voice picker.
- [ ] **Keep the engine out of the main exe:** Piper and `onnxruntime` add roughly 15–50 MB. Better to ship them in a separately downloaded voice engine (a small worker exe, plus Piper's espeak-ng data), so the main app stays lean, with voices downloaded on top.
- [ ] **Licences** in `THIRD_PARTY_NOTICES.md`: Piper (GPL-3), espeak-ng (GPL-3), onnxruntime (MIT), and each shipped voice's dataset licence.
- [ ] **A slow PC:** if a commander's PC can't keep up (measured, not guessed), The Watcher speaks less (only important moments, generated ahead) rather than late. If the pack ever exists, it's the fallback there too.

## Last resort: a pre-recorded voice pack

Only if the live voice doesn't pass the decision gate (above). The same voice and effect are generated once here by our generator and shipped as recordings, and the app only plays audio files. Everything below is kept ready for that case.

**What it gives up:** names in speech, exact figures beyond the number vocabulary, and lines nobody recorded. **What it gains:**
- No model download (about 90 MB) and no `onnxruntime` in the exe.
- No speech work on the commander's PC.
- Every clip is the same quality, and we can hand-pick the best of several takes for each line.
- The weary effect can be applied once, here, and tuned by ear.

### What gets recorded

A fully pre-recorded voice can't say anything it wasn't given, so lines are built from **clips joined at play time**:

- [ ] **Pieces:** every opener, aside and fixed observation from `data/watcher_lines.json`, each its own clip (or several takes of it).
- [ ] **Observations with a gap,** recorded in parts around the gap. For "{fuel} percent fuel.", that's the number, then "percent fuel." Keep the gaps at the end or the start of a phrase where possible, so the joins land at natural pauses.
- [ ] **A spoken-number vocabulary:**
  - zero to nineteen, the tens, hundred, thousand, million, billion
  - "point", "percent"
  - units: light years, credits, tonnes, hours, minutes, days
  - common rounded forms, recorded whole: "about thirty", "nearly a hundred", "over a million"
  
  With these, any rounded figure can be spoken ("thirty-one million credits").
- [ ] **No proper names in speech, until the live voice.** System, station, body and pilot names are endless and can't be recorded ahead (the live engine will say them). Lines say "this system", "that station", "your pursuer", and the **name shows in a caption** under the orb while it speaks. Write lines that work without the name; a few generic ones ("another one of those") cover the rest.
- [ ] **Breaths, sighs and "…" silences** as clips of their own, so silence and sighs are part of the performance.
- [ ] **Several takes of the most common pieces** (openers, "percent", the numbers) in slightly different deliveries, picked at random. That stops the same tiny clip giving the game away.

### Making the pack

Done by our own voice generator, a dev tool described in full in the next section. It turns `data/watcher_lines.json` into a reviewed, versioned voice pack.

### Shipping and installing it

- [ ] **A separate download,** not in the main release zip, so commanders who never turn the voice on don't download it. Publish it as its own asset on the GitHub release: `VoidCompass-WatcherVoice-v1.zip`, plus its `.sha256`. Expect roughly 10–30 MB, depending on how many clips and takes there are.
- [ ] **Downloaded the first time the voice is switched on,** checked against GitHub's digest and the `.sha256` the way `core/updater.py` checks releases, then unpacked into the app folder (`voices/watcher/`).
- [ ] **The pack has its own version.** The app knows which pack version its line data needs; when new lines ship, it offers the newer pack. The in-app updater could also fetch it on update when the voice is on.
- [ ] **Every line piece must have its clip:** a test checks `data/watcher_lines.json` against the pack manifest, so a line the pack can't say never gets picked; the app quietly skips it.

## Sounding weary

The effect is the shared module (see "Making it sound like The Watcher"): applied live by the engine, or baked into the clips if we ever ship the pack. In the app:

- [ ] Longer pauses before a punchline come from the joining: the player puts a short gap of the right length between clips.
- [ ] **Join clips cleanly in the deck's Web Audio:** short crossfades at the joins, a light shared reverb over the whole line so the pieces sound like one room, and the volume setting.

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
  - Observation: "{fuel} percent fuel." / "Interdicted again." / "{bodies} bodies here, and not one of them interesting." (Names go in the caption, not the speech.)
  - Asides, used sparingly: "I'd panic, but I find it so tiring." / "Not that anyone asked." / "I'll make a note. I make a lot of notes."
- [ ] **The real figures make it specific:** the number of bodies, the credits, the time since the last dock, the commander's own records ("your longest jump this week"), with the system or station name in the caption. The same event never sounds the same twice, because the facts differ.
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
- [ ] A **Test voice** button that downloads the voice engine and the chosen voice if needed and says one line. It also reports how fast this PC generates speech, so the commander knows what to expect.
- [ ] The **voice picker** (see "The engine: Piper, with downloadable voices").

## Prototype first

Build the smallest version that shows whether the voice lands, and whether live is fast enough:

- [ ] The generator's `say` command with the voice and the weary effect, used to settle how The Watcher sounds.
- [ ] A live worker in the app speaking about five topics (with several pieces each), built by the memory and line-building rules, with the eye lighting up with the speech and the name in the caption. "Doesn't repeat itself" is the point, so the prototype has to show it.
- [ ] The benchmark with Elite Dangerous running, and the decision gate: ship live, or (last resort) make the pre-recorded pack with the same generator.
