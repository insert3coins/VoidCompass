# Removing the Watcher's mind (the local language model)

Implemented 2026-11-02; regression run completed. The local model costs too much memory and
graphics card on your PC and on other commanders' PCs, so it comes out with
its API parts. The Watcher goes back to its written lines. Voice commands,
ship commands and plain answers stay, since none of them need the model.

## Completion and validation

- Local LLM modules, model controls, MIND/LIBRARY and the model-only API route are removed. TALK stays, with a Settings › Voice setup reminder, as requested in the follow-up.
- Whisper, Piper, written thoughts/story, commands, plain lookups and the uplink remain. Silent/short recordings also release the warmed speech model after the idle period.
- Old generated memory stays on disk; identifiable generated lines are filtered from the displayed log/conversation. Only `models/llm` is cleaned at updated startup.
- Every command now has an editable action sequence in Settings › Voice, including galaxy/system maps and panel open/close actions. Vehicle-specific sequences are separate. Controller-only map actions still need keyboard bindings in Elite, or a sequence using other bound actions.
- 276 focused regression tests passed. The full suite ran 2,429 tests in about 20 minutes, with no errors or skips. One obsolete exact-text assertion for tab migration was fixed; its Watcher/browser rerun passed all 24 relevant tests.
- Two native WebView tests still fail in the full run and isolated rerun: concurrent overlay controller readiness (`test_composition_host_55341`) and hidden-window delivery readiness (`test_overlay_delivery_568`). They are not changed by this task.
- Live Elite key presses and a real microphone/Whisper executable were not exercised; those checks use stand-ins.

## What goes and what stays

**Goes:**
- llama.cpp and Qwen3.5. `models/llm` takes **3.9 GB** on your PC.
- The Watcher page's MIND and LIBRARY tabs.
- The mind's Local API route.
- Everything the model wrote:
  - reworded everyday thoughts and its own thoughts
  - the diary, notes from talks, and "about you" summaries
  - goodnight recaps
  - the flight-log and Void Wrapped paragraphs
- These settings: "Its own words for everything", "Its own thoughts", "Keeps a diary", "Free memory when idle", plus the model and device choices.

**Stays:**
- Everything the Watcher says from its written lines.
- Its voice (Piper).
- Voice commands (Whisper).
- **The orb's animation when you talk to it.** None of it touches the model:
  - The hearing ring pulses with your voice while the talk key is held (`hud.set_hearing` feeds `live.hearing` and `showHearing` in `web/heartbeat/app.js`).
  - It does a "thinking" flicker while Whisper works out what you said (`orb.think` on the "hearing" stage).
  - The reply appears beside the orb as a thought and is spoken if the voice is on.
- Ship, overlay and music commands.
- Plain answers from the ship's systems.
- The uplink: Spansh prices, spoken as a plain answer.

## Decisions (adopted for this implementation)

1. **"Remove the API" means only the mind's part.** That's `GET /api/v1/watcher/mind` and the model's entry in the `/debug` state. The rest of the Local API, including the other `/watcher` routes, stays.
2. **Keep voice-in (Whisper).** Voice commands run on it.
   - It's about 500 MB, runs only while you're talking, and shuts down after 10 quiet minutes.
   - Its engine class (`ListenServer`) is built on the model's `LlmServer`, so `llm/llm_server.py` moves into `voice/` instead of being deleted.
3. **The talk box stays, as a commands box.** One small TALK tab replaces MIND and LIBRARY. It holds the conversation, typing, the mic button by SAY IT, and example commands.
4. **Delete `models/llm` automatically** the first time the updated app starts, with a one-line notice in the event feed. Otherwise anyone who tried the mind keeps up to about 4 GB they can't use. Leave `models/stt` (Whisper) and `models/hal9000` (Piper) alone.
5. **Leave the mind's saved memory in commanders' save files.** That's diary entries, notes, what you taught it, 👍/👎 votes and the lines it said in its own words.
   - It's no longer shown or used, and nothing is deleted.
   - "Remember that…" goes too, since only the model ever read those facts (`_watcher_remember`, `watcher_copilot.remember_request`).
6. **Release notes (5.7.3, unreleased):**
   - Remove the bullets "The Watcher's mind in the Local API" and "Its mind, off from the model list".
   - Reword "Commands with its mind off" to say there's no mind at all.
   - Add one bullet saying the mind is gone and why.
   - The name "Uplink" still fits, since the uplink works without the model, but the version name is the user's call.

## The work, in order

### 1. The Watcher (`overlays/watcher_mind.py`)
- `talk()` always takes the plain path (5.7.3): a command, then the ship's answer (`_plain_answer`), then the "plain" reply.
- Remove `_talk_job` and the "waiting on the model" state.
- `uplink_answer()` uses `watcher_copilot.plain_answer(lines)`.
- Remove everything that uses `self.llm`. There are 11 call sites:
  - rewording (`_llm_pending`, `REWORD_WAIT_S`)
  - its own thoughts
  - the sign-off recap (`llm.recap`)
  - the diary (`_diary_pending`)
  - notes from talks (`_notes_pending`, `take_notes`)
  - "about you" (`_about_pending`, `llm.condense`)
  - `own_paragraph`
  - votes on its own words (`_votes`, `_said_in_own_words`, `own_said`)
- Keep `_reply`, `say_after`, the talk history, `action_provider` and `lookup_provider`.
- Keep `follow_up()`. The heartbeat HUD uses it, and it isn't part of the mind.

### 2. Modules
- **Delete:**
  - `llm/llm_assets.py`, `llm/llm_embed.py`, `llm/library_sources.py`, `llm/__init__.py`
  - `overlays/watcher_llm.py`, `overlays/watcher_world.py`, `overlays/watcher_knowing.py`, `overlays/watcher_learning.py`
  - `tools/watcher_llm_eval.py`
- **Move:** `llm/llm_server.py` becomes `voice/local_server.py`, a local engine on a random port with a key. Update `voice/listener.py` to import it.
- **Before deleting each module,** grep for readers outside the mind:
  - `watcher_learning` feeds WHAT IT SAW, which goes with the MIND tab, and the sign-off recap.
  - `watcher_knowing.forget_questions` runs when `WatcherMind` loads.
  - `watcher_field`'s docstring mentions `watcher_llm.SET_PREFIXES`.
- **Keep `overlays/watcher_copilot.py`**: the lookups, `topics_for`, the commands, `REPLIES`, `PLAIN_QUESTION` and `plain_answer`. Drop the parts only the model used, such as the uplink wording tuned for it and `remember_request`.

### 3. The deck
- **`dashboard/dashboard_watcher_voice_mixin.py`:**
  - Remove `_watcher_llm`, `_watcher_sources`, `_watcher_mind_needs_download` and the mind's download (`_watcher_mind_downloader`, `_start_download`, `_progress`, `_downloaded`).
  - Remove `_html_watcher_mind`, `_html_watcher_library` and `_watcher_own_words`.
  - Remove the operations `mind_toggle`, `mind_settings`, `mind_download`, `mind_cancel`, `mind_remove`, `mind_teach`, `mind_unteach`, `mind_forget_note`, `mind_rate` and `library_*`.
  - Keep `mind_talk` and `mind_forget`, perhaps renamed `talk` and `talk_forget`.
  - Keep the `_watcher_lookup_*` functions and `_watcher_mind_action`.
  - Rename `_watcher_llm_lookup` to `_watcher_lookup`.
  - The `_watcher_mind_watch` publishing still serves talk replies.
- **`dashboard/dashboard_flight_log_mixin.py`** (`_flight_log_own_words`) **and `dashboard/dashboard_journey_mixin.py`** (`_wrapped_own_words`): keep their written paragraphs only.
- **`dashboard/dashboard_watcher_listen_mixin.py`:** replace `_watcher_llm_facts()` with a small helper that gives Whisper its name hints: system, ship name, ship, nearby body and station.

### 4. The API
- **`dashboard/dashboard_api_mixin.py`:** remove `api_watcher_mind`, the `llm` entry in the `/debug` state (around line 220), and the `llm_assets` and `llm_server` imports.
- **`services/local_api.py`:** remove the `GET /watcher/mind` route and `api_watcher_mind` from `PROVIDER_CALLS`.
- **`api.md`:** remove the `/watcher/mind` row and the "What `GET /api/v1/watcher/mind` holds" section. The API docs page is built from `api.md`, which must list every route.
- **The dev debugger** (`tools/debug/web/debugger.js`): remove the mind panel (`renderMind`) and the `llama-server.exe` process name.

### 5. The page
- **`web/dashboard/watcher.js` and `watcher.css`:**
  - Remove the MIND and LIBRARY tabs, their panels, wiring and renderers (`mindPanel`, `renderMind`, `libraryPanel`, `renderLibrary` and friends) and their styles.
  - Add a TALK tab, carrying over from the MIND page: the conversation (`watcher-talk-log`), the text box, the mic button (`wireHear` and `renderHear`), and command examples in place of `MIND_PROMPTS`.
- **The flight log and Void Wrapped:** remove the "IN ITS OWN WORDS" marks.
- **Settings › Voice (`app.js`):** reword the notes that mention "its own mind" (`SETTINGS_GROUP_NOTES["TALK BY VOICE"]`).

### 6. Settings and cleanup
- **`core/config.py`:** remove `watcher_llm_enabled`, `_reword`, `_free_idle`, `_own_thoughts`, `_diary`, `_model` and `_device` from the `PROFILE_*` tuples and both defaults blocks. Drop them from saved configs when they load.
- **First start after the update:** remove `models/llm` (llama.cpp engine, Qwen models, the search model), with a one-line feed notice saying how much space it freed.
- **The updater:** check that its manifest (`core/updater.py`, only manifest files are replaced) lists no model files.

### 7. Docs and notes
- Update `mini-readme.md` (5.7.3), as in decision 6.
- Delete `todo-watcher-llm.md`, or mark it historical.
- Update the memory notes: `project_watcher_llm_571` (removed), `project_watcher_voice_in_571` and `project_ship_commands_573` (no mind), and the MEMORY.md index.

### 8. Tests (last, when the whole batch is done)
- **Delete:** `test_watcher_llm_571`, `test_watcher_mind_api_573`, `test_library_sources_571`.
- **Trim:**
  - `test_watcher_mind_tools_571`: keep the life lookups, drop the library search and votes.
  - `test_watcher_answers_572`: keep the lookups, drop the model wording.
  - `test_watcher_uplink_573`: plain answer.
  - `test_watcher_listen_571`: new imports.
- **Add:**
  - Talking with no model at all: commands, plain answers, the "plain" reply.
  - No `voidcompass.llm` import or `watcher_llm` reference anywhere in `src`.
  - The `models/llm` cleanup.
  - A Watcher page with a TALK tab and no MIND or LIBRARY.
  - Talking by voice still drives the orb: the hearing ring, the thinking flicker, and a reply beside the orb. The existing `test_the_orb_shows_it_listening` and the listen tests must still pass.
  - Old saves and configs that still carry mind keys load cleanly. Try a copy of a real profile.
- **Then the full suite**, about 25 minutes.

## Size

About 3,500 lines of Python come out:
- the `llm` package, about 1,230 lines
- `watcher_llm`, 970
- `watcher_world`, `watcher_knowing` and `watcher_learning`, about 660
- much of the voice mixin

Most of the MIND and LIBRARY page code and styles go too.
