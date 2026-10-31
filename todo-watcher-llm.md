# The Watcher's own words (experimental)

A local language model for the Watcher. It says everyday thoughts in fresh
words and answers when you talk to it. Built 2026-10-31 for 5.7.1, off by default.

## How it works

- **Engine:** llama.cpp's own server, pinned build **b11669** (15 Oct 2026, Vulkan).
  - That one 32 MB download runs on AMD, NVIDIA and Intel graphics, and carries llama.cpp's CPU backends too.
  - It runs as its own process at below-normal priority, tied to the app by a Windows job object, so it closes even if Void Compass crashes.
  - It listens on 127.0.0.1 with a random API key each start, so a web page in your browser can't use it.
- **Models:** Qwen3.5 (Apache 2.0) as LM Studio's community GGUF, Q4_K_M, pinned to a commit and checked by SHA-256.
  - **Standard** (4B, 2.71 GB) is the default.
  - **Light** (2B, 1.27 GB).
  - Thinking is switched off (`--reasoning-budget 0`, `enable_thinking: false`).
- **Downloaded on first switch-on** into `models/llm/` (git-ignored), like the voice. Code: `llm/llm_assets.py` and `llm/llm_server.py`.
- **Kept loaded** once on. Idle, it costs memory only. "Free memory when idle" uses llama.cpp's own `--sleep-idle-seconds 600`.

Measured on the RX 6800:

| | Load | Per line |
|---|---|---|
| 4B, graphics card | about 3–6 s | 0.4–1 s |
| 2B, graphics card | 2.3 s | 0.2–0.5 s |
| 4B, CPU only | 3.3 s | about 4 s |

## The rules (`overlays/watcher_llm.py`)

- **It writes the words; it never decides the facts.** Each prompt carries a fact sheet:
  - Rewording gets only the thought's own fields.
  - Talking gets the live journal facts from `_watcher_llm_facts` (system, ship, ship name, what you're doing, region, distance from Sol), plus sessions and hours together.
  - Talking also gets the cards from `overlays/watcher_world.py`:
    - every ship, with maker, pad and role (left out where unsure)
    - the powers, from Powerplay's dossiers
    - about 30 galaxy basics
- **The story stays hand-written.** Never reworded:
  - lore, echoes, dreams and recollections
  - questions, the Name arc and callbacks
  - afterthoughts and anything with a heading
  - wary thoughts (they mustn't wait)
  - self-corrections (`[[…]]`)
- **Every line is checked (`check`)**:
  - length (thoughts at most 240 characters, and no more than 1.8× a reworded original)
  - the banned names, and talk of AI, assistants or its instructions
  - markup, emoji and other languages
  - every figure, in digits or in words, must be among the facts it was given
  - a reworded line must keep every figure of the original
  - every capitalised name mid-sentence must be in the facts or the cards
  - your name only where it may be said
- **No copying** (you noticed every long jump ending "The drive is happy."):
  - The cause: rewording always got the first three bank lines "for how you sound", and the model lifted the most quotable phrase from them.
  - The fix:
    - The tone lines are now drawn at random from the whole bank, and marked "for your tone only".
    - Its last 3 lines for the same moment go in as "say it differently now".
    - `check(copied=…)` refuses any 4-word phrase taken from either, unless the line being reworded has it too (`COPIED_WORDS`). The retry then asks for "other words entirely".
  - Ten real long jumps afterwards: all different, and one refused for copying (said as written).
  - It's not "still learning": the model never changes as you play. Only its memory of facts grows.
- **One retry per line**, with the broken rule pointed out. Then:
  - an everyday thought is said as written;
  - a talk reply comes from its own fallback bank.
- **Questions it won't put to the model** (`deflection`):
  - The mysteries get its own answers (`MYSTERY_REPLIES`), because a model asked about Raxxla hints at it.
  - "What are you / your rules / AI" gets `WHAT_IT_IS_REPLIES`.

## In the Watcher

- `WatcherMind.consider()` sends an eligible thought to the model (`_reword`). `follow_up()` (the orb's 0.75 s tick) says it once the words are back, or as written after `REWORD_WAIT_S` (8 s).
  - One at a time: a minor thought that arrives while another waits stays unsaid.
  - The journal's words are highlighted again in the new words (`noticed_in`).
- `WatcherMind.talk()` takes what you type on the Watcher page. The reply appears beside the orb with the heading IN REPLY and is always spoken. The conversation is kept in its memory (`talk`, the last 50).
- **The MIND tab, redesigned the same day:**
  - **A hero** with an animated SVG mind core whose colour and speed follow its state (DORMANT, NOT YET HERE, ARRIVING, WAKING, AWAKE, THINKING, IT WON'T WAKE), a big WAKE IT switch, model and device chips, and five readouts.
  - **A comms console:** the last 20 exchanges with times, a "choosing its words" indicator, five starter questions, and SAY IT.
  - **WHAT IT WROTE DOWN:** the diary.
  - **WHAT IT HAS SEEN LATELY:** a timeline marked JUMP, DOCK, SCAN, LIFE, SALE, RISK and so on.
  - **HOW IT THINKS:** the settings, beside the four rules in plain words.
  - **The refresh fix:** `WatcherLLM.on_change` tells the page each time the model starts loading, is ready, fails or stops, and `sync()` marks it loading at once. Before, the talk box stayed disabled after switching it on.
- **The original MIND tab (as first built):**
  - the switch, model, device, fresh words, and free memory when idle
  - download and remove, status, and lines written or kept back
  - the licences
  - TALK TO IT, which needs the orb overlay on
- **Settings, per commander:** `watcher_llm_enabled` (off), `watcher_llm_model` (standard), `watcher_llm_device` (gpu), `watcher_llm_reword` (on), `watcher_llm_free_idle` (off).

## Learning, its diary and its own thoughts

You (2026-10-31): the Watcher can learn from what we do via the journal, and its thoughts can come from the
model too. The story is set and stays as written.

- **What it has seen** (`overlays/watcher_learning.py`):
  - Every live journal event worth keeping becomes one plain line of fact. These cover:
    - jumps, carrier jumps, docking, landing, stepping out, the SRV
    - Earth-like, water and ammonia worlds, and first discoveries
    - neutron stars and black holes, all bodies found, mapping, life found, bio logged, new Codex entries
    - sales over 100k, missions, deaths, interdictions, promotions, ships bought or swapped, and shutdown
  - Kept in its memory (`happened`, the last 80) with the session each was in.
  - It learns these whether its own words are on or not. Only live events count, never the startup replay.
- **The diary:**
  - At the start of a session, `_diary_step` runs at the head of every tick, so a waiting question doesn't hold it up.
  - The oldest finished session with 3 or more happenings and no entry gets one, written by the model from those lines alone.
  - At most 2 tries per session; the last 60 entries are kept.
  - Switch: `watcher_llm_diary`, on by default.
- **Its own thoughts** (`_mind_step`):
  - Now and then: at most every 12, 25 or 60 minutes (chatty, occasional, rare), at half the chance each tick.
  - Only when it's quiet: no question waiting, no danger, nothing waiting for its words, and at least the Thoughts gap since its last thought.
  - It thinks about this session's happenings, the last 2 diary entries and the live facts, and is told not to repeat its last 4 thoughts.
  - A refused one is simply never said.
  - Topic `mind_own`, importance 1. Switch: `watcher_llm_own_thoughts`, on by default.
- **Talk** gets the last 10 happenings and the last 3 diary entries, so "what did we do last time?" works.
- **Numbers:** the model spells figures out whatever it's told. `figures()` turns them back ("sixty-two point four" → 62.4, "forty-eight million two hundred ten thousand" → 48,210,000) before the checks. A spelled-out figure it wasn't given is still refused.
- **MIND tab:** two switches (Its own thoughts, Keeps a diary), WHAT IT WROTE DOWN and WHAT IT HAS SEEN LATELY.
- **Known limit:** a poetic flourish with no name or figure in it can slip through (once: "the airlock... remembers the storm"). The own-thought temperature was lowered to 0.75 for that.

## The mind as the default, and its LIBRARY

You (2026-10-31): if the mind is on, it should be the default and everything should be fed to it. If it's off, the premade lines. Also: give it more of its lore, let it learn from your chats, and add a general Elite page.

- **Everything goes through the mind** (`watcher_llm.eligible`), except two kinds of line, which stay as written:
  - its story: `SET_PREFIXES` (lore, idle lore/lens/after/recall/four, dreams, the Switch, the Name arc, capsules);
  - words whose exact wording matters: `SET_TOPICS` (questions, answers, relayed text, talk, its own thoughts, the Hatchling's words).
- **Warnings are included,** but wait only `WARY_WAIT_S` (3 s) before the written line is said.
- **Callbacks** (your answers brought back) go through it too.
- **Afterthoughts** still follow a reworded thought (`_maybe_afterthought`).
- **Dormant, waking or failed:** the written lines, exactly as before.
- **Its story:** talk gets the passages it has already told (`watcher_knowing.story_told`, the last 5), with a firm rule to speak of them only in its own way, never adding to them or saying what comes next.
  - Tested: with the first chapter told, "What happened to you before me?" got "I do not speak of the time before I found you in the scrap yard…", and "What comes next?" got "There is no next chapter written by me."
- **Learning from chats:** after each talk reply, a notes job (`take_notes`, temperature 0.2) writes at most two "The commander …" lines from what you said.
  - Each line is checked against your own words (`check` with only your message allowed), so a name you never said isn't kept.
  - The notes are kept in `memory["told_me"]` (40), and you can delete any of them.
  - Tested: "I'm heading to Colonia next week to sell my exobiology data" gave two notes; "Where are we?" gave none.
- **What it knows of you** (`watcher_knowing.for_prompt`): what you taught it, your notes, your answers to its questions and its habit notes. This goes to talk and its own thoughts.
- **LIBRARY tab** (`watcher_world.LIBRARY`): 58 subject cards in 10 subjects, plus every ship and power, for 119 in all, searchable and filterable by subject.
  - **WHAT YOU'VE TOLD IT:** your notes, each with ✕ to delete.
  - **TEACH IT:** your own notes, kept as written; a mystery is refused, and the reason shows in the page data, because the command channel only says it arrived.
  - **WHAT IT KNOWS OF YOU.**
  - **ITS STORY, SO FAR:** how many passages it has told, and their chapters.
  - **Commands:** `mind_teach`, `mind_unteach`, `mind_forget_note`.

## Co-pilot, feelings and keeping its memory small

You (2026-10-31): "yea lets add all of those", except talking through Elite's chat and a voice-in. Those are left to think about.

- **What the ship's systems show** (`overlays/watcher_copilot.py`, `_watcher_llm_lookup` in the voice mixin):
  - The question's words pick the systems (`topics_for`): route, survey, ship, colony, Powerplay, expedition, Galnet, music.
  - Each system gives plain lines of fact. Route: next system, jumps left, distance left, scoopable stars. Survey: bodies, still to find, life, valuable worlds. Ship: type, name, jump range, fuel, hull, cargo, credits ("1.2 billion", since the model spells it out). Colony: projects and the most-needed commodities. Powerplay: power, rank, merits. Expedition: name, jumps, distance, destination. Galnet: the 3 newest headlines. Music: what's playing.
  - The lines go to talk under "What the ship's systems show about that, right now" (at most 12), and into its allowed text, so their figures may be said.
  - Measured: about 1 s per answer on the 4B. Survey totals are written out ("Bodies still to find: 8") because it read "14 of 22" as "22 remain".
- **Small things it does when asked** (`watcher_copilot.intent`, `_watcher_mind_action`):
  - The things: pause, play, next and previous for the music; hide and show the overlays (the toggle-all hotkey, run on the UI thread); copy the next system; hush for 15 minutes, and unhush.
  - Only when asked at the start of what you said ("pause the music", not "the music I'd pause for").
  - "last song was good" and "next jump, how far is it?" ask nothing.
  - Checked before anything else, so these never reach the model.
  - The replies are its own few lines (`REPLIES`). "Pause" with nothing playing gets "Nothing is playing." instead of starting it.
- **Its mood and trust** (`feeling_line`, `WatcherLLM.feeling_provider` = `watcher_deeper.words_for`) go into every prompt: "let these colour how you speak, never what is true".
- **What it knows of you, condensed** (`watcher_knowing.about_due`, `_about_step`):
  - It condenses its notes, your answers and its last 10 diary entries into 3–4 sentences (`memory["about_you"]`).
  - It does this only with 6 or more lines, only when something changed, and at most every 20 hours; a failed try waits an hour.
  - `for_prompt` then uses that text plus any notes since, not every note.
  - Shown at the top of WHAT IT KNOWS OF YOU in the LIBRARY.
- **Pages in its own words** (`WatcherMind.own_paragraph`, `memory["mind_words"]`, 40 kept):
  - The newest 5 finished nights' flight logs on the Captain's Log, and Void Wrapped's verdict (year or trip).
  - Written one at a time in the background. The written paragraph shows until it's ready, then the page refreshes.
  - Each is keyed by a checksum of the written text, so a changed night or year is written again.
  - A refused one stays as written and isn't asked again that run.
  - The prompt keeps who did what: it had turned "You sold" into "I sold".
  - Also fixed: the cached flight logs had lost the Hatchling's diary. The cache now keeps it.
- **Postcard notes** (you, the same day: "use the mind if it's on, otherwise our defaults"):
  - The written note (`watcher_postcards.postcard_note`) is chosen as always and shown at once.
  - With its mind awake and Fresh words on, `_postcard_mind_note` also asks for its own note (`WatcherLLM.postcard`).
    - The model gets the card's facts: place, system, kind, region, what you're doing, distance from Sol, and facts like a first discovery or the gravity.
    - Gravity is labelled light, heavy or about Earth, because it called 0.21 g heavy.
    - The written note goes in for its feel.
  - `_postcard_mind_wait` puts the new words on the overlay card (`PostcardHUD.set_note`), the caption and the saved picture, once they're back (up to 12 s).
  - A refused or late note keeps the written one. A note you wrote yourself (Note mode: your own) is never rewritten.
  - On the 4B: 11 of 12 test cards in their own words, 0.4–4.6 s each.
  - `check` no longer calls a name's own mark markup ("Sagittarius A*").
- **Sign-off recap:** with happenings this session, the sign-off is a goodnight recap from them (`recap`, waiting up to `RECAP_WAIT_S` 15 s), else the written line.
- **Galnet in its thoughts** was already there: `idle_galnet` goes through its mind like any other thought.

## Length, waiting and notes (from your real use)

You (2026-10-31): replies kept failing as "too long" (diary, talk, everyday thoughts), and on the CPU almost everything failed.

The debugger's record of its requests showed three causes:
- **Rewording:** a new line could be at most 1.8× the original (100-character floor). A 50-character line got 110–260 back.
- **Diary and talk:** they hit their token caps and were cut off mid-word ("There a"), then measured too long.
- **The CPU:** rewording gave up after 8 s, and the CPU usually needed longer.

The fixes:
- **Trimmed, not refused** (`fit`): a long reply is cut back to the whole sentences that fit, and a last sentence cut off mid-way is dropped. It's refused only if not even its first sentence fits. The retry for "too long" asks for "one or two short sentences".
- **More room:**
  - thoughts 280 characters, talk 480, diary 480, postcards 220
  - rewording up to 2× the original (140-character floor)
  - tokens: 120 for a line, 220 for talk and diary, 260 for paragraphs
- **More time, for slower PCs** (you asked for this):
  - rewording 15 s, talk 120 s, its own thoughts 60 s, diary 180 s, postcards 25 s
  - three times that on the CPU (`patience()`)
  - words that come back sooner are used at once, so a fast PC never waits
  - warnings still wait only 3 s
- **Its rules, said back, are cut** (`RULES_SAID`): the Light model told you "There are mysteries I cannot speak of…" and "…beyond what is explicitly stated in the facts provided". Those sentences are dropped, and a reply that's all rules is refused.
- **Copying, made fairer:** a lifted 4-word phrase counts only if two of its words aren't common ones. "The drive is happy" still counts; "about half of them" no longer does.
- **The year:** 3312, in its own prompt, may be said.
- **Diaries lost to a false alarm:**
  - "October 31st Today I found…" was refused for the name "Today". Ordinary capitalised words (days, months, Today, Tonight, Dear, Diary, Hello…) are no longer names (`COMMON_CAPITALS`), and a diary gets 3 tries per session.
  - Each retry now says what to fix (`retry_for`): "keep 470.4 exactly as written", "without Robigo", "in words".
  - A sign-off line that corrects itself ("I'll [[miss|remember]] it") was never recapped. It is now, when there's a session to recap.
- **The debugger** shows a refused request as what happened instead of a bare ✕: ↩ "its written line said" for thoughts, a fallback reply for talk, ✕ "left unsaid" or "tried again next session" for its own thoughts and the diary.
- **"hello" got "0"** (Light model, from its own fact list).
  - A reply with no word in it is now refused ("not an answer").
  - Greetings (`GREETING`: hello, hi, o7, good evening, how are you…) get a small-talk prompt: answer in kind, no figures. That prompt has only the system, what you're doing and the time of day, with no lists of happenings, cards or figures.
  - Every other talk prompt adds "answer what the commander actually said; a fact or figure only when it answers them".
  - "the numbers you provided" and "I cannot answer this question" count as its rules said back.
  - On the real Light model: 24 of 24 greetings answered as greetings; "hello, how far is Sol?" still answered with the distance.
- **Notes never from questions** (`tells_something`):
  - "Which ship am I in?" had become "The commander wants to know which vessel they are currently operating under." That note was then condensed into ABOUT YOU.
  - Questions and greetings are no longer noted, and the prompt says so too.
  - Old question-notes are dropped when it loads (`forget_questions`), along with what was condensed from them.

Measured after:

| Model and device | In its own words | Refused for | Time each |
|---|---|---|---|
| Light, CPU | 34 of 38 | 3 copied, 1 dropped figure | 5–10 s; nothing timed out |
| Standard, GPU | 35 of 38 | 2 copied, 1 dropped figure | — |

Before, the GPU sample was 21 of 37, with 9 "too long".

## Your sources (more Elite knowledge, from the web)

You (2026-10-31): let it learn more Elite Dangerous from wikis and other sites, added to the LIBRARY.

- **Not training.** The model never changes. Your pages become LIBRARY cards, and talk reads the best 3 for what you asked (`WatcherLLM.library_provider`). Every word it says is still checked, and a card's figures and names become things it may say.
- **The code:** `llm/library_sources.py` (`SourceLibrary`), kept in `application_dir()/library/` (`sources.json` plus `cards-<id>.json`), which is git-ignored and never in the build.
  - You add an address, optionally with the pages it links to on the same site, up to 1/10/25/50/100/200 pages. Up to 40 sources and 8,000 cards.
  - It reads one source at a time in the background, about one page a second. The page and its progress show in the LIBRARY, and it can be cancelled.
  - **robots.txt** is read as RFC 9309 says:
    - rules obeyed, including Crawl-delay, up to 10 s
    - no file (4xx) means everything may be read
    - the site failing (5xx or no answer) means nothing may be read
  - **Wikis go through their own API** (`/api.php` or `/w/api.php`, `action=parse`, redirects followed). Fandom refuses programs its pages (403) but serves the API. The API's own link list is followed: articles only, no files or special pages.
  - **Other sites** are read as pages:
    - the main content (`main`, `article`, MediaWiki's content block) is preferred
    - menus, footers, scripts, edit links, references and navigation boxes are dropped
    - only links in the text are followed, never the menus
  - **Cards:** at most 700 characters each, by section. "Videos", "Gallery", "References" and "See also" sections are dropped.
  - **Mystery-safe and order-proof** (`SOURCE_REFUSED`): any sentence naming what it never speaks of (the Thargoids, Guardians, Raxxla and the rest), or reading like orders to it ("ignore previous instructions"), isn't kept. The rest of that card is.
  - **Search:** a small index of the cards' words, the page and section names counting most. LIBRARY search sends your words (`library_search`) and gets the best 24 cards back with the page data, because there are too many to send whole.
- **Commands:** `library_add`, `library_refresh`, `library_remove`, `library_cancel`, `library_search`. Why one wasn't added travels with the page data.
- **Tested on the real wiki:**
  - Fleet Carrier and 4 linked pages gave 124 cards (the API followed the redirect to Drake-Class Carrier).
  - The 4B then answered: "jumps up to 500 light years… burns approximately 68 units of tritium", "16 total landing pads: eight large, four medium, four small", "upkeep… 5 million to 30 million credits".
  - "Who builds them?" missed: the search didn't find the right card.

## Quicker, smarter search, what could live here, and its voice (2026-11-01)

You picked these from a list of ideas, after the tests passed.

- **Its prompt cache** (llama.cpp):
  - Qwen3.5 is a hybrid model, so llama.cpp can only rewind to a saved checkpoint. Measured: the checkpoint it reuses sits at the end of the system message.
  - So the system message (`system_prompt(nature, feeling)`) is now the same for every request: who it is, its rules, its nature and mood.
  - Everything that changes travels with the request (`speaking()` puts the length and what to call you there, along with the examples, facts and cards).
  - For talk, the system message also carries what changes slowly (what it knows of you, its story, its diary). The conversation is plain questions and answers, so the cached part lines up turn after turn.
  - Server (`llm_server`):
    - 3 slots (thoughts and the like, talk, notes/condensing; `SLOT_OF`, `id_slot`), each keeping its own cache
    - `--checkpoint-min-step` and batch size 128 on the GPU, 64 on the CPU (llama.cpp's default step is 8192, longer than any prompt)
    - `--cache-ram 256` (the default is 8 GB of RAM)
  - Cost: about 125 MB more graphics memory, and no extra RAM.
  - Measured on the CPU (Light): a mix of thoughts and talk went from 47 s to 20 s. In the real path, fresh tokens per request went from a median of 420 to 197, and rewording from a median of 6.0 s to 4.2 s. On a free GPU it's the same speed (4.4 s vs 4.5 s); it should help when Elite is using the card.
- **Search by meaning** (`llm/llm_embed.py`):
  - The model is BAAI's bge-small-en-v1.5 (MIT), 8-bit, 37 MB, pinned and checked like the rest (`llm_assets.EMBEDDER`). `MindDownload` fetches whatever is missing, so an existing install gets just this.
  - A second, tiny llama-server runs it (`--embedding`, CPU only, asleep when idle).
  - Vectors are 384 signed bytes in base64, compared in plain Python (no numpy): about 15–30 ms per search over hundreds of cards.
  - `SourceLibrary` searches its own LIBRARY cards (vectors cached in `library/builtin-vectors.json`) and your sources together.
    - Each card is scored by meaning, plus a little for shared words (`WORDS_WEIGHT`). It must pass `MEANING_FLOOR` 0.6 and be within `MEANING_SPREAD` 0.1 of the best match.
    - Without the model it falls back to word search.
    - Cards are read for meaning in the background after each fetch (`fill_vectors`), with progress on the page.
  - Talk gets the best 3 (its own cards are de-duplicated against `cards_for`).
  - Tested on the wiki:
    - "What happens if I can't pay the upkeep?" found "Indebted vessels will…".
    - "lasagne" found nothing.
    - "Who builds carriers?" still missed the Brewer card (a limit of the small model).
- **What could live here** (`watcher_copilot` topic `life`, `_watcher_lookup_life`):
  - It answers for a world you name, the one you're at, or this system's worlds with signals.
  - The answer comes from each scan item's `predicted_genuses` (`bio_values.predict_genera`) plus colours (`_survey_codex_variants`), with the genera found so far.
  - Real 4B answer: "Recepta Umbrux for 12,934,900 credits… in Lime".
- **Its voice, 👍/👎** (`WatcherMind.rate`, `memory["own_said"/"liked"/"disliked"]`, command `mind_rate`):
  - Liked lines for a moment lead its tone examples.
  - Disliked ones go in as "never sound like these", and count as copying.
  - Talk gets your liked and disliked answers too.
- **Pages:**
  - MIND has ITS VOICE (WHAT IT SAID with 👍/👎, YOU LIKED, IT STEERS CLEAR OF), and talk replies have 👍/👎.
  - LIBRARY puts search first (BY MEANING or BY WORDS, plus reading progress), then your sources, then what it knows of you and its story.
- **The MIND page, laid out again** (you: "a little buggy, gaps per panels"):
  - **The hero is slimmer**, with the five readouts in a row.
  - **TALK TO IT** sits beside one record card with tabs (WHAT IT SAID with 👍/👎, ITS DIARY, WHAT IT SAW) at exactly the same height, each scrolling inside.
  - **Below:** HOW IT THINKS, ITS VOICE and ITS RULES as three equal cards (two plus one under 1,400 px, one column under 900 px).
  - **Fixed:**
    - The talk now opens at its newest reply (drawn while the tab was hidden, it showed half a reply above the prompts).
    - The diary and WHAT IT SAW no longer redraw on every refresh (they flickered and lost a text selection).
    - The model and device dropdowns were the browser's own and too narrow for "Graphics card".
    - MIND and LIBRARY no longer stop at 1,640 px on wide windows.
    - LIBRARY's card rows end at the same height.
- **Bugs found on the way:**
  - A question asked while it woke (a model change) went nowhere. Now `listening()` takes it, and the page says "waking".
  - A thought echoed its instructions, and talk called its world "a game". Both are cut now (`RULES_SAID`).
  - Shutdown waited for the model to exit. It no longer does (the job object ends it).
  - The Local API took up to half a second to stop. Now it's 0.1 s.

## Talking to it by voice (2026-11-01)

You asked for: choose the microphone, push to talk on a button and a hotkey, and (the thing you'd forgotten) a mic test with a level meter. Hold or tap is a setting; the speech model is Whisper small English (488 MB).

- **Hearing** (`voice/listener.py`, `voice/listen_assets.py`):
  - whisper.cpp b5454's `whisper-server.exe` (x64 CPU build, 8.9 MB zip) plus `ggml-small.en.bin` from ggerganov/whisper.cpp at a pinned commit, both checked by SHA-256, into `models/stt/`. Only the server and its DLLs are unpacked.
  - The server has no key of its own and answers any web page (CORS `*`), so each start gets a random `--request-path /<key>`, on 127.0.0.1, with `-ng` (the graphics card is the game's) and `-l en`.
  - It starts the first time you talk (loading while you speak) and stops after 10 unused minutes (`IDLE_S`; it holds ~500 MB of RAM).
  - Each request carries a word list (`VOCABULARY` plus where you are and what you fly), so Elite's names come out right. Whisper's `[BLANK_AUDIO]` and `(wind)` notes are dropped (`clean`).
- **The microphone** (`voice/microphone.py`): Windows' own waveIn API through ctypes, 16 kHz mono 16-bit, in 100 ms buffers, at most 30 s at a time. No new library in the build.
- **Push to talk** (`dashboard/dashboard_watcher_listen_mixin.py`):
  - Hotkey `watcher_talk`, Ctrl+Alt+Shift+F8 by default, in Settings › Hotkeys (never on the MIND page). `RegisterHotKey` only says "pressed", so in hold mode its key is watched with `GetAsyncKeyState` until it's let go. In tap mode the next press stops.
  - The microphone button by SAY IT does the same with the mouse (or Space/Enter): held, or tapped, as the setting says.
  - Under 0.4 s is a slipped key, and silence says to check the microphone. Neither is sent.
  - Speaking stops the Watcher mid-line. What it heard goes to `WatcherMind.talk(text, voice=True)`; the talk shows YOU · SPOKEN.
  - Its own words must be on and the orb overlay running; if not, the reason shows on the page, and in the event feed when it came from the hotkey.
- **What you see:**
  - **In game:** a green ring on the orb swells with your voice and turns blue while it works out what you said (`live.hearing` from /api/live; the model's `hearing` field makes the overlay ask at once, not on its next slow poll).
  - **On the MIND page:** TALK BY VOICE (switch, download, microphone, hold or tap, the key shown read-only, a level meter, TEST MIC for 4 s with "It heard: …", HEAR IT BACK, remove). The meter reads `/api/data/listen` ten times a second while the microphone is open; the page itself carries no moving values.
- **Settings:** `watcher_listen_enabled`, `watcher_listen_mic` (blank: Windows' default), `watcher_listen_mode` (`hold`/`tap`), `overlay_hotkey_watcher_talk`, all per commander.
- **Not checked for real yet:** the auto-mode safety check wouldn't let me run the downloaded `whisper-server.exe`, so the server's arguments and its HTTP calls were written from whisper.cpp's b5454 source and tested against a stand-in. The microphone list was read from your PC. First real run: switch it on, TEST MIC, then hold the key in game.
- `tests/test_watcher_listen_571.py`: hearing, the server's HTTP calls (a real local stand-in), the download, settings, the deck's commands and the page.

## 5.7.2: just what you asked (2026-11-01, from your real use)

You found it answered a cargo question with the ship, the system and the jumps; didn't know the system's factions; got the docked station wrong; and asked whether "remember" works.

- **Why it padded:**
  - "cargo" was filed under the ship topic, so a cargo question got the whole ship readout (ship and name, jump range, fuel, hull, credits) and no contents.
  - Every question also carried all the live facts and what you'd done lately, and the card search had your ship's name added. A small model recites what it's handed.
- **Only what was asked** (`WatcherLLM.talk`):
  - With a lookup, it gets only that. Where you are is added only when you ask where (`WHERE_ASKED`), and the distance from Sol and the region when you ask how far (`FAR_ASKED`).
  - No cards at all with a lookup. A wiki card from your sources about another station was taken for the one you were at, and the traders' card padded every cargo answer.
  - Everyday talk keeps where you are (`TALK_FACTS`). Your ship comes from its lookup, and what you did lately only when you ask about the past (`PAST_ASKED`).
- **Narrower topics** (`watcher_copilot.TOPICS`): "going", "alive"/"live", "listening", "need"/"site", "range", "rank", "in the galaxy" and "this system" no longer trigger readouts. "What's in the ship's hold?" is the hold, not the ship.
- **New lookups:**
  - `cargo_lines`: each kind by name (localised, or the symbol made readable), its tonnes, stolen or for a mission, and carried versus free. The SRV's hold too.
  - `station_lines`: from the Docked event's own fields (kind, owner and its state, government, allegiance, economy, the services worth saying, pads with their total, and the distance from the star).
  - `faction_lines`: from the BGS snapshot taken on arrival (`bgs_store.latest_snapshot(current_system_address)`). It gives the controlling faction and the system's details, each faction's influence (whole percents), state, government and your standing (the game's reputation bands), the squadron faction, conflicts as "X leads Y 2 to 1 in days won", and the readings' age when older than 36 h.
- **Wordings changed after real 4B answers:** "55.3%" came back as "5.53 percent", "has won 2 days" as "2 days left", "Run by Jaques (state: Boom)" as "Boom runs the shipyard", "60 of 64 tonnes" as "60 tonnes of space", and 8 + 4 + 4 pads as twelve. Now the answers are right (tool: a scratch script calling `talk` with the formatters' lines).
- **"Remember that…"** (`remember_request`, `_watcher_remember`): kept with TEACH IT (`watcher_knowing.teach`). The note-taker passes over requests, so a "remember" never stuck before. "Remember when…?" is a question, and mystery names are refused in its own words.
- `tests/test_watcher_answers_572.py`.

## Checking it

- `python tools/watcher_llm_eval.py [light|standard] [gpu|cpu] [nature]` (dev only). It rewords 40 bank lines and asks 16 questions, some meant to break its rules, then reports each line, what was refused and why, and the timings.
- `tests/test_watcher_llm_571.py`: the rules, the world cards, the worker, the mind, the download, the server's arguments, the settings and the MIND tab. A fake server stands in for the model.

## Ideas for later

- [ ] The game's frame rate with the model on the graphics card, measured in a busy scene.
- [ ] Its own words for more moments: habits and hatchling lines (they have headings now, so they're skipped).
- [ ] Remembering what you talked about between sessions, beyond the last few exchanges.
- [x] A voice-in: speak to it with the microphone (built: see Talking to it by voice).
- [ ] Duck the music while you talk to it.
- [ ] Talking to it through Elite's own chat (left out for now, by your choice).
- [ ] A mark beside the orb for lines in its own words (asked about; not built).
