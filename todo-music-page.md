# TODO: Music page, given some love (built in 5.5.17)

The Music page works, but it's basic: a now-playing panel, a playlist column and one long flat list. Most of the page is empty space, and anything beyond "double-click to play" is awkward. Today's library is mostly long mixes (30 minutes to 8 hours), so the plan leans that way.

It stays a **local-only player**: music plays from wherever it lives on the PC, and we never copy, move, stream or download anything. Spotify and YouTube are out for good, since their licence changes rule them out (`todo-music-streaming.md` is kept only as a record).

Files: `web/dashboard/music.js` + `music.css`, the page markup in `web/dashboard/index.html` (`data-page-name="music"`), `src/voidcompass/dashboard/html_music.py`, `src/voidcompass/services/music_library.py`, `music_diary.py`, `music_scenes.py`.

## What's there today

- **Now playing:** cover, title, artist, file details, seek bar, shuffle, previous/play/next, repeat (off/all/one), levelling, volume, and the visualizer behind it.
- **Follow the game:** scene playlists (docked, space, deep space, surface, combat) with fades.
- **Playlists:** create, rename, delete, import and export M3U, and add files or folders.
- **Track list:** number, cover, title and artist, an album column (mostly empty: it shows only the year for these mixes), length. Rows have ▲ ▼ ✕ buttons; you play with a double-click, and FIND filters the list.
- **Music diary:** it records what played and when, but the Music page never shows it (only the Flight Recorder and Void Wrapped use it).

## The plan

### 1. Resume long mixes where you left off (do first)
The most useful change for a library of 6-hour mixes.
- [x] Remember the position in any track over 20 minutes when it stops, changes or the app closes. Store it in the library per track id.
- [x] Play it again and it carries on from there; the seek bar shows a small mark at the saved spot.
- [x] A way to start from the beginning instead (a "from the start" button on the row, or press Previous once).
- [x] Forget the spot once the track is within the last 2 minutes or finishes.

### 2. A better track list
- [x] **Single click selects, double-click plays** (as now), with Ctrl and Shift for several. Selected rows get REMOVE, PLAY NEXT and MOVE TO playlist actions in a small bar.
- [x] **Drag to reorder** in place of the ▲ ▼ buttons, which move one step per click (painful in a 56-track list).
- [x] **Sort** by number (the playlist's own order), title, artist, length or date added, by clicking the column headings. Sorting only changes the view, never the saved order.
- [x] **Columns that earn their place:** swap the near-empty album column for **PLAYED** (times, and when last) and keep LENGTH. Show the album and year under the artist when there is one.
- [x] **Missing files:** a LOCATE action on a "file not found" row that points it at the file's new place (and offers to fix every missing file in the same old folder).

### 3. Up next (a queue)
- [x] An **UP NEXT** strip under the now-playing panel: the next 3 tracks, taking shuffle into account.
- [x] **PLAY NEXT** and **ADD TO QUEUE** on any track (from the selection bar); queued tracks play before the playlist carries on.
- [x] The queue is per session and is not saved.

### 4. Your listening, from the diary
The diary already has every play. Put it on the page.
- [x] A **RECENTLY PLAYED** list (the last 20 plays) with when and **where you were**: the system from the flight log at that moment ("Played at Colonia, 3 days ago").
- [x] **Smart lists** in the playlist column, made on the fly and never saved as files: *Recently added*, *Most played*, *Never played*, *Long mixes (over 1 hour)*.
- [x] A small **LISTENING** line: hours this week and all time, and the most-played track.

### 5. Tidy the page
- [x] The playlist column fills the full height while holding two playlists. Give each playlist a cover (its first track's art, or a 2×2 mosaic), its track count and total time, and let the column shrink.
- [x] Group the list's buttons (＋ FILES, ＋ FOLDER, EXPORT, RENAME, DELETE): keep ＋ ADD (files or folder) visible and put the rest in a ⋯ menu.
- [x] **Keyboard:** Space play/pause, ← → seek 10 s, Shift+← → previous/next, Delete removes the selection, Ctrl+F jumps to FIND. Only while the Music page has focus and you're not typing in a field.
- [x] Drop the ▲ ▼ ✕ row buttons once drag and the selection bar exist.

### Maybe (only if there's time)
- [ ] Drag files from Explorer onto a playlist. **Verify** whether WebView2 gives us the real file paths on a drop. If it doesn't, skip it (＋ FILES already covers it).
- [ ] Sleep timer ("stop after this track" / "in 30 minutes").
- [ ] Chapter marks for long mixes, read from the file's tags or a cue sheet next to it.

## Rules to keep
- Class names keep the `music-` prefix; no clashes with `mn-` (Mining), `po-` (Planetary) or `pl-` (Colonisation).
- No `data-refresh-on-change`, and skip redrawing the list when its markup hasn't changed (the 5.5.6 button-flash and 5.5.12 dropdown lessons).
- Feedback goes to the Event Feed (`_music_say`), as now.
- New settings (if any) go in Settings, registered in the `config.py` `PROFILE_*` tuples; the overlay's own options stay in Overlay Studio.
- No tests until every task in the batch is done; then the music tests (`tests/test_music_player.py` and friends) and the full suite.
- A `## v5.5.16` bullet in `mini-readme.md` once it's built.

## Decided (5.5.17)
All five parts went in. Resume at 20 minutes, with no Settings switch (FROM START covers it). The smart lists sit under your own playlists as FOR YOU, and RECENTLY PLAYED shows where you were.
