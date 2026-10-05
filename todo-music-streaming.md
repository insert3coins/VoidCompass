# TODO: Spotify and YouTube in the Music player

Commanders have asked for Spotify and YouTube in the Music player alongside their local files. The rule: **we never download their music.** It plays through the services' own players, and our player is the place you see it and control it, along with the Music Player overlay.

Things marked **verify** need checking before we rely on them.

## Ground rules

- [ ] **No downloading or ripping.** No yt-dlp, no saving audio, no pulling audio out of video. Both services forbid it, and so do we.
- [ ] **Follow each service's terms:**
  - YouTube: its player stays visible (never hidden or audio-only), and we never block ads.
  - Spotify: show its logo and name where its content appears, and link back to it.
- [ ] **Real levels only.** The visualiser shows real audio levels or nothing; never fake ones (see "Levels" below).
- [ ] **Opt-in.** Each source is switched on in Settings › Integrations, registered in the `config.py` `PROFILE_*` tuples, and off by default apart from part 1.
- [ ] **Keys and tokens stay on the user's PC**, in their profile, like the Raven Colonial key.
- [ ] Local files keep working exactly as now (`html_music.py`, `music_library.py`, `web/dashboard/music.js`, `web/music_player`).

## 1. Now playing from any app (do this first)

Windows already knows what every media app is playing: the panel you get from the volume keys. Python can read it and control it through the WinRT media session API (`GlobalSystemMediaTransportControlsSessionManager`).

- [ ] Read the title, artist, album, cover art, position and length, and whether it's playing, from **any** app: the Spotify desktop app, YouTube or YouTube Music in a browser, Apple Music, foobar2000, and so on.
- [ ] Control it: play, pause, next, previous, and seek where the app allows it.
- [ ] Show it in our Music page as a source ("Playing in Spotify") and on the Music Player overlay.
- [ ] No accounts, keys or downloads, and it works for Spotify Free too. It covers most of what people are asking for on its own.
- [ ] **Verify** which Python package to use: `winrt-Windows.Media.Control` (pywinrt) or `winsdk`. Check that it packages cleanly with PyInstaller onefile, and how much it adds to the exe.
- [ ] When several apps are playing, pick Windows' "current" session, and let the user choose another.

## 2. YouTube, played in our Music page

Use YouTube's **official embedded player** (the IFrame Player API) inside the Music page. This is allowed: it's what embedding is for.

- [ ] Paste a video or playlist link to play it. A playlist ID loads through the player API with no API key.
- [ ] Get titles and thumbnails from YouTube's oEmbed endpoint, which needs no key.
- [ ] **Saved YouTube playlists:** the user's own list of links, kept with their local playlists, so local and YouTube items can share a queue.
- [ ] The video panel stays visible, as YouTube's terms require; make it a neat panel in the Music page, not a hidden player. The overlay shows the title and controls only.
- [ ] Control it (play, pause, skip, seek, volume) from our controls through the player API.
- [ ] **Verify** that embeds work from our local deck server. YouTube refuses embeds with no referrer or origin (error 153), so we may need to pass `origin` and set the referrer policy.
- [ ] Some videos have embedding switched off by their owner. Show that clearly and offer "open on YouTube".
- [ ] Search inside the app is optional. The YouTube Data API needs a key and has a daily quota, so it would use the user's own key. Leave it out of the first version: pasting links is enough.

## 3. Spotify

Two routes; do A first.

**A. Spotify Connect control, through the Spotify Web API.**
- [ ] Browse your playlists, liked songs and albums in our Music page, and start any of them playing on one of your Spotify devices (the desktop app, your phone, anything that supports Connect).
- [ ] Control playback (play, pause, skip, seek, volume, shuffle, repeat, choose the device) from our controls and the overlay.
- [ ] Sign-in uses OAuth with PKCE and a loopback redirect, so there's no client secret in the app. Keep the refresh token in the user's profile.
- [ ] **Verify Spotify's current developer rules:**
  - Since 2025, new apps stay in "development mode" (a small allow-listed set of users), and the extended quota is only for large businesses. So each user will probably have to create their own free Spotify developer app and paste its client ID into Settings. That's how other hobby apps handle it; write a short how-to.
  - Playback control endpoints need Spotify Premium. Reading what's playing may work on Free; **verify**.
- [ ] Spotify's audio still comes out of the Spotify app; we're the remote. Part 1 already shows it on the overlay, so A adds browsing and choosing what plays.

**B. Playing Spotify inside our app (later, if possible).**
- [ ] The Spotify Web Playback SDK makes the deck itself a Spotify device. It needs Premium and Widevine DRM in the browser engine.
- [ ] **Verify** whether WebView2 supports Widevine. Historically it didn't; if it still doesn't, drop B. The same question applies to Spotify's embed player: logged-in embeds play full tracks only with DRM, and otherwise give 30-second previews.

## Levels for the visualiser

Today's live levels come from our own `<audio>` playback. Music playing in another app (part 1 or Spotify) isn't ours to measure directly.

- [ ] **Option:** measure what's playing on the PC with WASAPI loopback capture of the output device, using only the levels and never recording or saving audio. **Verify** the package and its PyInstaller packaging.
- [ ] Better: Windows' per-process loopback capture (Windows 10 2004 and later) can measure just Spotify or just the browser, leaving out game sound. **Verify** the effort; it's a step up.
- [ ] For the YouTube embed, we can't read audio from inside the iframe; the same loopback approach is the only way.
- [ ] Until then, the visualiser shows a quiet idle state for outside sources, never fake bars.

## Settings

- [ ] **Settings › Integrations:**
  - "Show music from other apps": part 1, the one source on by default, since it's local and only reads what Windows already shows.
  - "YouTube in the Music player"
  - "Spotify" with its client ID, Connect and Disconnect.
- [ ] Music Player overlay options for the new sources (cover art, source badge) go in **Overlay Studio** only, per the Studio vs Settings split.

## Finishing

- [ ] Tests:
  - media session parsing, with the WinRT layer faked
  - YouTube link and playlist parsing
  - the Spotify PKCE flow and token refresh, with replies faked
  - nothing connects unless switched on
- [ ] Add YouTube, Spotify and the Windows media session to the README's integrations list.
- [ ] Add Spotify's and YouTube's terms and branding notes, and any new package licences, to `THIRD_PARTY_NOTICES.md`.
- [ ] Mini-readme entry; the version is the user's call.

## Suggested order

1. Part 1, any app's now playing and controls: quick, keyless, and it already answers "Spotify and YouTube" for most people.
2. Part 2, YouTube embedded in the Music page.
3. Part 3A, browsing and controlling Spotify, once the developer rules are confirmed.
4. Levels through loopback capture.
5. Part 3B, only if WebView2 supports Widevine.
