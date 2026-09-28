"""The music library: playlists of files wherever they live, and their tags.

Music plays from where it already is; the library remembers each file once
and playlists list them in order. These tests hold tag reading (ID3 and
Vorbis comments, covers embedded or kept beside the files, a file name when
there are no tags), M3U/M3U8 import (relative paths, file:// URLs, #EXTINF
hints, old encodings, what gets skipped) and export, adding folders in name
order, playlist editing, and the library surviving a restart.
"""

import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from voidcompass.services.music_library import (
    TAG_VERSION, MusicLibrary, _loudness, folder_cover, is_audio, parse_m3u, read_tags, tags_from_name,
    track_id, write_m3u,
)


def picture_bytes(colour=(200, 90, 20), size=400, kind="PNG"):
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (size, size), colour).save(buffer, kind)
    return buffer.getvalue()


def make_wav(path, seconds=1.0, **tags):
    """A short silent WAV, with ID3 tags (and a cover) when asked."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * int(8000 * seconds))
    if tags:
        from mutagen.id3 import APIC, TALB, TCON, TDRC, TIT2, TPE1, TRCK
        from mutagen.wave import WAVE
        audio = WAVE(str(path))
        audio.add_tags()
        for frame, key in ((TIT2, "title"), (TPE1, "artist"), (TALB, "album"), (TCON, "genre"),
                           (TDRC, "year"), (TRCK, "number")):
            if tags.get(key):
                audio.tags.add(frame(encoding=3, text=str(tags[key])))
        if tags.get("cover"):
            audio.tags.add(APIC(encoding=3, mime="image/png", type=3, desc="Cover", data=picture_bytes()))
        if tags.get("replaygain"):
            from mutagen.id3 import TXXX
            audio.tags.add(TXXX(encoding=3, desc="replaygain_track_gain", text=tags["replaygain"]))
        audio.save()
    return path


def make_flac(path, seconds=3, **tags):
    """A FLAC that is only its header and tags: enough for tag reading."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rate, channels, bits = 44100, 2, 24
    packed = (rate << 44) | ((channels - 1) << 41) | ((bits - 1) << 36) | (rate * seconds)
    info = struct.pack(">HH", 4096, 4096) + b"\x00" * 6 + packed.to_bytes(8, "big") + b"\x00" * 16
    path.write_bytes(b"fLaC" + bytes([0x80]) + len(info).to_bytes(3, "big") + info)
    from mutagen.flac import FLAC, Picture
    audio = FLAC(str(path))
    audio.add_tags()
    for key in ("title", "artist", "album", "date", "genre", "tracknumber", "albumartist",
                "replaygain_track_gain"):
        if tags.get(key):
            audio[key] = str(tags[key])
    if tags.get("cover"):
        picture = Picture()
        picture.type, picture.mime, picture.data = 3, "image/jpeg", picture_bytes(kind="JPEG")
        audio.add_picture(picture)
    audio.save()
    return path


class TagTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def test_file_names_stand_in_for_missing_tags(self):
        self.assertEqual(tags_from_name("03 - Jean-Michel Jarre - Oxygene Pt 4.mp3"),
                         {"title": "Oxygene Pt 4", "artist": "Jean-Michel Jarre", "number": "3"})
        self.assertEqual(tags_from_name("C:/music/Ambient_Drift.flac"),
                         {"title": "Ambient Drift", "artist": "", "number": ""})
        self.assertTrue(is_audio("x.MP3") and is_audio("y.opus") and not is_audio("z.txt"))
        self.assertEqual(track_id("C:/Music/A.mp3"), track_id("C:/Music/./A.mp3"))

    def test_id3_tags_length_and_cover(self):
        path = make_wav(self.root / "a.wav", seconds=2, title="Equinoxe 5", artist="Jarre", album="Equinoxe",
                        genre="Electronic", year="1978", number="5/8", cover=True)
        tags = read_tags(path)
        self.assertEqual({key: tags[key] for key in ("title", "artist", "album", "genre", "year", "number")},
                         {"title": "Equinoxe 5", "artist": "Jarre", "album": "Equinoxe", "genre": "Electronic",
                          "year": "1978", "number": "5"})
        self.assertAlmostEqual(tags["duration"], 2.0, places=1)
        self.assertTrue(tags["cover"].startswith(b"\x89PNG"))
        self.assertTrue(tags["format"].startswith("WAV"))

    def test_vorbis_comments_and_embedded_pictures(self):
        path = make_flac(self.root / "b.flac", seconds=3, title="Aurora", albumartist="Solar Fields",
                         album="Movements", date="2009-03-10", tracknumber="07", genre="Ambient", cover=True)
        tags = read_tags(path)
        self.assertEqual((tags["title"], tags["artist"], tags["album_artist"], tags["year"], tags["number"]),
                         ("Aurora", "Solar Fields", "Solar Fields", "2009", "7"))
        self.assertAlmostEqual(tags["duration"], 3.0, places=1)
        self.assertEqual(tags["format"], "FLAC · 44.1 kHz · 24-bit")
        self.assertTrue(tags["cover"].startswith(b"\xff\xd8"))

    def test_loudness_comes_from_replaygain_or_r128_tags(self):
        # ReplayGain brings a track to -18 LUFS, so -7.25 dB means -10.75 LUFS.
        tagged = read_tags(make_wav(self.root / "c.wav", title="Loud", replaygain="-7.25 dB"))
        self.assertEqual(tagged["loudness"], -10.75)
        flac = read_tags(make_flac(self.root / "d.flac", title="Quiet", replaygain_track_gain="+3.50 dB"))
        self.assertEqual(flac["loudness"], -21.5)
        # Opus: R128_TRACK_GAIN is 1/256 dB against -23 LUFS.
        opus = {"r128_track_gain": ["-2048"]}
        self.assertEqual(_loudness(opus, set(opus), opus), -15.0)
        self.assertIsNone(read_tags(make_wav(self.root / "e.wav", title="Plain"))["loudness"])
        self.assertIsNone(_loudness({"replaygain_track_gain": ["loud"]}, {"replaygain_track_gain"}))

    def test_a_file_without_tags_keeps_its_name(self):
        tags = read_tags(make_wav(self.root / "Vangelis - Rachel's Song.wav"))
        self.assertEqual((tags["title"], tags["artist"], tags["cover"]), ("Rachel's Song", "Vangelis", None))

    def test_a_cover_beside_the_files_is_found(self):
        track = make_wav(self.root / "album" / "01.wav")
        self.assertIsNone(folder_cover(track))
        (self.root / "album" / "Folder.JPG").write_bytes(picture_bytes(kind="JPEG"))
        self.assertEqual(folder_cover(track).name, "Folder.JPG")


class PlaylistFileTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def test_m3u_resolves_relative_paths_urls_and_hints(self):
        album = self.root / "album"
        first, second = make_wav(album / "one.wav"), make_wav(album / "deeper" / "two.wav")
        third = make_wav(self.root / "elsewhere" / "three.wav")
        (album / "set.m3u").write_text("\n".join([
            "#EXTM3U", "#EXTINF:125,Artist One - First Song", "one.wav",
            "deeper\\two.wav" if os.name == "nt" else "deeper/two.wav",
            third.as_uri(), "http://radio.example/stream", "missing.wav", "notes.txt",
        ]), encoding="utf-8")
        entries, skipped = parse_m3u(album / "set.m3u")
        self.assertEqual([Path(entry["path"]) for entry in entries], [first, second, third])
        self.assertEqual((entries[0]["title"], entries[0]["artist"], entries[0]["duration"]),
                         ("First Song", "Artist One", 125.0))
        self.assertEqual(skipped, {"streams": 1, "missing": 1, "unsupported": 1})

    def test_older_m3u_files_in_the_windows_code_page_still_read(self):
        make_wav(self.root / "Café.wav")
        (self.root / "old.m3u").write_bytes("#EXTM3U\nCafé.wav\n".encode("cp1252"))
        entries, _ = parse_m3u(self.root / "old.m3u")
        self.assertEqual([Path(entry["path"]).name for entry in entries], ["Café.wav"])

    def test_export_writes_an_extended_m3u8_that_reads_back(self):
        track = make_wav(self.root / "x.wav")
        out = self.root / "out.m3u8"
        write_m3u(out, [{"path": str(track), "title": "Song", "artist": "Band", "duration": 61.4}])
        self.assertEqual(out.read_text(encoding="utf-8").splitlines(),
                         ["#EXTM3U", "#EXTINF:61,Band - Song", str(track)])
        entries, _ = parse_m3u(out)
        self.assertEqual((Path(entries[0]["path"]), entries[0]["title"]), (track, "Song"))


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.library = MusicLibrary(self.root / "library")
        self.addCleanup(self.library.wait_idle)

    def tracks_of(self, library, playlist_id):
        payload = library.payload()
        listed = next(item for item in payload["playlists"] if item["id"] == playlist_id)["tracks"]
        return [payload["tracks"][key]["title"] for key in listed]

    def test_playlists_are_made_filled_edited_and_kept(self):
        first = self.library.create_playlist("Deep Space")
        self.library.create_playlist("deep space")
        self.assertEqual([item["name"] for item in self.library.payload()["playlists"]],
                         ["Deep Space", "deep space 2"])
        folder = self.root / "tunes"
        make_wav(folder / "10 - b.wav")
        make_wav(folder / "2 - a.wav")
        make_wav(folder / "sub" / "1 - c.wav")
        (folder / "readme.txt").write_text("not music")
        files = self.library.expand([folder])
        # Numbers count as numbers (2 before 10); subfolders follow.
        self.assertEqual([Path(file).name for file in files], ["2 - a.wav", "10 - b.wav", "1 - c.wav"])
        self.assertEqual(self.library.add_files(first, files), 3)
        self.assertTrue(self.library.wait_idle())
        self.assertEqual(self.tracks_of(self.library, first), ["a", "b", "c"])
        self.assertTrue(self.library.move_track(first, 2, 0))
        self.assertEqual(self.library.remove_tracks(first, [1, "x", 99]), 1)
        self.assertTrue(self.library.rename_playlist(first, "  Drift  "))
        again = MusicLibrary(self.root / "library")
        self.assertEqual(again.playlist(first)["name"], "Drift")
        self.assertEqual(self.tracks_of(again, first), ["c", "b"])
        # A track no playlist lists any more is forgotten.
        self.assertTrue(again.delete_playlist(first))
        self.assertEqual(again.payload()["tracks"], {})

    def test_music_is_never_copied_only_remembered(self):
        playlist = self.library.create_playlist("P")
        source = make_wav(self.root / "far" / "away" / "song.wav")
        self.library.add_files(playlist, [source])
        self.assertTrue(self.library.wait_idle())
        key = self.library.payload()["playlists"][0]["tracks"][0]
        self.assertEqual(self.library.track_file(key), source)
        stored = [path.name for path in (self.root / "library").rglob("*") if path.is_file()]
        self.assertNotIn("song.wav", stored)

    def test_imports_name_a_playlist_after_the_file_and_read_covers(self):
        make_flac(self.root / "set" / "a.flac", title="Aurora", artist="Solar Fields", cover=True)
        make_wav(self.root / "set" / "b.wav")
        (self.root / "set" / "cover.png").write_bytes(picture_bytes((20, 90, 200)))
        (self.root / "set" / "Night Drive.m3u8").write_text("#EXTM3U\na.flac\nb.wav\nhttps://x/y\n", encoding="utf-8")
        result = self.library.import_m3u(self.root / "set" / "Night Drive.m3u8")
        self.assertEqual((result["added"], result["streams"]), (2, 1))
        self.assertTrue(self.library.wait_idle())
        payload = self.library.payload()
        self.assertEqual(payload["playlists"][0]["name"], "Night Drive")
        first, second = payload["playlists"][0]["tracks"]
        self.assertEqual((payload["tracks"][first]["title"], payload["tracks"][first]["art"]), ("Aurora", True))
        self.assertTrue(payload["tracks"][second]["art"], "the folder's cover stands in")
        self.assertTrue(self.library.overlay_art(first).startswith("data:image/jpeg;base64,"))
        self.assertIsNone(self.library.track_file("0" * 16))
        self.assertIsNone(self.library.art_file("../../secret"))

    def test_missing_files_are_marked_and_rechecked(self):
        playlist = self.library.create_playlist("P")
        source = make_wav(self.root / "gone.wav")
        self.library.add_files(playlist, [source])
        self.assertTrue(self.library.wait_idle())
        key = self.library.payload()["playlists"][0]["tracks"][0]
        self.assertFalse(self.library.payload()["tracks"][key]["missing"])
        source.unlink()
        self.library.recheck_files()
        self.assertTrue(self.library.payload()["tracks"][key]["missing"])
        self.assertIsNone(self.library.track_file(key))

    def test_the_player_can_correct_a_length_it_measured(self):
        playlist = self.library.create_playlist("P")
        self.library.add_files(playlist, [make_wav(self.root / "a.wav")])
        self.assertTrue(self.library.wait_idle())
        key = self.library.payload()["playlists"][0]["tracks"][0]
        self.assertFalse(self.library.set_duration(key, 1.2), "within half a second is not news")
        self.assertTrue(self.library.set_duration(key, 42))
        self.assertFalse(self.library.set_duration(key, "nonsense"))
        stored = json.loads((self.root / "library" / "library.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["tracks"][key]["duration"], 42)

    def test_the_player_remembers_loudness_it_measured_but_a_tag_wins(self):
        playlist = self.library.create_playlist("P")
        self.library.add_files(playlist, [make_wav(self.root / "a.wav", title="A"),
                                          make_wav(self.root / "b.wav", title="B", replaygain="-4 dB")])
        self.assertTrue(self.library.wait_idle())
        plain, tagged = self.library.playlist(playlist)["tracks"]
        tracks = self.library.payload()["tracks"]
        self.assertEqual((tracks[plain]["loudness"], tracks[tagged]["loudness"]), (None, -14.0))
        self.assertEqual(tracks[tagged]["loudness_source"], "tag")
        self.assertTrue(self.library.set_loudness(plain, -8.4))
        self.assertFalse(self.library.set_loudness(plain, -8.5), "within 0.3 LU is not news")
        self.assertFalse(self.library.set_loudness(plain, -90), "not a real loudness")
        self.assertFalse(self.library.set_loudness(tagged, -6), "the file's own tag is kept")
        stored = json.loads((self.root / "library" / "library.json").read_text(encoding="utf-8"))
        self.assertEqual((stored["tracks"][plain]["loudness"], stored["tracks"][plain]["loudness_source"]),
                         (-8.4, "measured"))

    def test_tracks_read_before_loudness_tags_are_read_again(self):
        playlist = self.library.create_playlist("P")
        self.library.add_files(playlist, [make_wav(self.root / "a.wav", title="A", replaygain="-2 dB")])
        self.assertTrue(self.library.wait_idle())
        # As a library saved by the previous version would have it.
        file = self.root / "library" / "library.json"
        stored = json.loads(file.read_text(encoding="utf-8"))
        for track in stored["tracks"].values():
            track["tagged"] = True
            track.pop("loudness", None)
            track.pop("loudness_source", None)
        file.write_text(json.dumps(stored), encoding="utf-8")
        reopened = MusicLibrary(self.root / "library")
        self.addCleanup(reopened.wait_idle)
        self.assertTrue(reopened.wait_idle())
        track = next(iter(reopened.payload()["tracks"].values()))
        self.assertEqual(track["loudness"], -16.0)
        self.assertEqual(next(iter(reopened._tracks.values()))["tagged"], TAG_VERSION)


if __name__ == "__main__":
    unittest.main()
