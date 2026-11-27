"""Nova's Prologue (5.8.6.1): the deck's side of how she comes aboard.

It's Lyra's alone. Nova starts locked; her voice can be fetched from her
button in the companion picker, and once it's on disk, Lyra (on watch, in
play) notices and finds the archive. Arriving at the installation in LFT 1748
starts the rest: she connects, recovers and installs the software, a few
seconds apart, and Nova takes the watch. The other companions never notice
any of it, and nothing moves while Lyra is off watch.

How far it has gone is kept per commander (config ``nova_prologue``). A
commander who already had Nova aboard before the Prologue existed keeps her.
"""

from __future__ import annotations

import logging
import os
import time

from voidcompass.core import companions
from voidcompass.core.config import get_active_profile, get_profile_file
from voidcompass.overlays import nova_prologue as prologue
from voidcompass.voice import voice_assets

PLAY_GAP_S = 300.0        # five minutes without a journal event isn't play (AFK)
LINE_WAIT_S = 900.0       # how long her lines wait for a quiet moment
HEADING = "LYRA · PROLOGUE"
TELLER = "lyra"


class DashboardPrologueMixin:
    # -- its state ------------------------------------------------------------------
    def _prologue_state(self):
        state = self.config.get("nova_prologue")
        state = dict(state) if isinstance(state, dict) else {}
        try:
            profile = get_active_profile(self.config)
        except Exception:
            profile = None
        if getattr(self, "_prologue_profile", object()) != profile:
            self._prologue_profile = profile
            if "state" not in state:
                # Asked once per commander: Nova already aboard from before her
                # Prologue stays. Never again after (a reset leaves her memory file).
                met = self._prologue_met_before(profile)
                state = {**state, "state": "installed", "met_before": True} if met else {**state, "state": ""}
                self._prologue_write(state)
            state, moved = prologue.revised(state)
            if moved:
                self._prologue_write(state)
            self._prologue_sync_lock(state)
        return state

    def _prologue_met_before(self, profile):
        """Nova aboard before her Prologue: on watch, or with a memory of her own."""
        if companions.identity(self.config) == "nova":
            return True
        try:
            path = get_profile_file(profile, "nova_memory.json") if profile else None
            return bool(path) and os.path.exists(path)
        except Exception:
            return False

    def _prologue_write(self, state):
        self.config["nova_prologue"] = dict(state)
        try:
            self._persist_config()
        except Exception:
            logging.debug("Nova's Prologue not saved", exc_info=True)

    def _prologue_restart(self):
        """RESET on Nova's page: she leaves the ship and her Prologue starts
        over. Her voice stays, so Lyra, on watch, notices it again."""
        state = {"state": "", "restarted": round(time.time(), 1), "revision": prologue.REVISION}
        self._prologue_write(state)
        self._prologue_sync_lock(state)
        if companions.identity(self.config) == "nova":
            self._companion_switch(TELLER)
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    def _prologue_locked(self, selected):
        return selected == "nova" and self._prologue_state().get("state") != "installed"

    def _prologue_sync_lock(self, state=None):
        state = self._prologue_state() if state is None else state
        if state.get("state") == "installed":
            companions.LOCKED.discard("nova")
        else:
            companions.LOCKED.add("nova")

    # -- her voice, fetched while she's locked ---------------------------------------------
    def _prologue_voice_ready(self):
        try:
            return bool(voice_assets.installed(model="nova"))
        except Exception:
            return False

    def _prologue_voice_download(self):
        """Fetch Nova's voice from her locked button. False while another
        voice is downloading (they share the engine)."""
        if not self._prologue_locked("nova") or self._prologue_voice_ready():
            return False
        other = getattr(self, "_watcher_voice_download", None)
        if other is not None and other.running():
            return False
        download = getattr(self, "_prologue_download", None)
        if download is not None and download.running():
            return True
        download = voice_assets.VoiceDownload(model="nova")
        self._prologue_download = download

        def done(state):
            if state.get("stage") == "done":
                # Fetched on purpose: she'll speak once she's aboard.
                self.config["nova_voice_enabled"] = True
                try:
                    self._persist_config()
                except Exception:
                    logging.debug("Nova's voice setting not saved", exc_info=True)
            post = getattr(self, "_ui_post", None)
            work = lambda: self._schedule_html_dashboard_publish(immediate=True)
            if callable(post):
                post(work, key="prologue-voice-download")
            else:
                work()

        started = download.start(done)
        self._prologue_voice_progress()
        return started is not False

    def _prologue_voice_progress(self):
        download = getattr(self, "_prologue_download", None)
        if download is None or getattr(self, "_closing", False):
            return
        self._schedule_html_dashboard_publish(immediate=True)
        call_later = getattr(getattr(self, "root", None), "call_later", None)
        if download.running() and callable(call_later):
            call_later(700, self._prologue_voice_progress)

    def _prologue_locked_view(self):
        """For the picker: who isn't aboard, and how far Nova's voice has got."""
        if not self._prologue_locked("nova"):
            return {}
        download = getattr(self, "_prologue_download", None)
        state = download.state() if download is not None else {}
        return {"nova": {"voice": self._prologue_voice_ready(), "stage": str(state.get("stage") or "idle"),
                         "done": int(state.get("done") or 0), "total": int(state.get("total") or 0)}}

    # -- telling it -------------------------------------------------------------------
    def _prologue_mind(self):
        return getattr(getattr(self, "heartbeat_hud", None), "mind", None)

    def _prologue_lyra(self):
        """Lyra's mind while she's on watch; None otherwise (nobody else notices)."""
        mind = self._prologue_mind()
        if companions.identity(self.config) != TELLER or getattr(mind, "identity", "") != TELLER:
            return None
        return mind

    @staticmethod
    def _prologue_playing(mind):
        if getattr(mind, "_session_start", None) is None:
            return False
        last = getattr(mind, "_last_event_at", None)
        try:
            return last is not None and mind.clock() - float(last) <= PLAY_GAP_S
        except Exception:
            return False

    def _prologue_quiet(self, mind):
        if getattr(mind, "_in_danger", False) or getattr(mind, "_crew_queue", None):
            return False
        busy = getattr(self, "_banter_voice_busy", None)
        try:
            return not (callable(busy) and busy())
        except Exception:
            return True

    def _prologue_scene(self, state, key, mind, now=None):
        """Lyra's lines for one scene, queued in order; the scene kept as told."""
        now = time.time() if now is None else now
        if mind is not None and callable(getattr(mind, "crew_say", None)):
            for line in prologue.LINES[key]:
                mind.crew_say(TELLER, line, heading=HEADING, topic="nova_prologue", wait=LINE_WAIT_S)
        state.setdefault("scenes", {})[key] = round(now, 1)

    def _prologue_tick(self, now=None):
        now = time.time() if now is None else now
        state = self._prologue_state()
        self._prologue_sync_lock(state)
        stage = state.get("state") or ""
        if stage == "installed":
            if state.get("on_watch"):
                # Retry until the watch changes hands (a voice download holds it).
                if companions.identity(self.config) == "nova" or self._companion_switch("nova"):
                    state.pop("on_watch", None)
                    self._prologue_write(state)
            return
        lyra = self._prologue_lyra()
        if lyra is None:
            return
        if stage == "":
            # She notices Nova's voice aboard, in play, at a quiet moment.
            if self._prologue_voice_ready() and self._prologue_playing(lyra) and self._prologue_quiet(lyra):
                self._prologue_scene(state, "found", lyra, now)
                state["state"] = "found"
                self._prologue_write(state)
                self._schedule_html_dashboard_publish(immediate=True)
            return
        # She's working: each scene follows the last once she's finished
        # speaking and its pause has passed.
        if stage in prologue.NEXT:
            if not self._prologue_quiet(lyra):
                self._prologue_hush = None
                return
            if getattr(self, "_prologue_hush", None) is None:
                self._prologue_hush = now
                return
            following, pause = prologue.NEXT[stage]
            if now - self._prologue_hush >= pause:
                self._prologue_hush = None
                self._prologue_scene(state, following, lyra, now)
                state["state"] = following
                self._prologue_write(state)
                self._schedule_html_dashboard_publish(immediate=True)
            return
        if stage == "installing" and self._prologue_quiet(lyra):
            # Installation complete, said: Nova takes the watch.
            state.update(state="installed", on_watch=True)
            self._prologue_write(state)
            self._prologue_sync_lock(state)
            try:
                self._toast_on_main("SYSTEM", prologue.SYSTEM_MESSAGE, duration=10)
            except Exception:
                logging.debug("Nova's install message skipped", exc_info=True)
            if self._companion_switch("nova"):
                state.pop("on_watch", None)
                self._prologue_write(state)

    # -- the journal --------------------------------------------------------------------
    def _prologue_observe(self, event, raw, startup_replay=False):
        if startup_replay or getattr(self, "batch_mode", False) or not isinstance(raw, dict):
            return
        try:
            self._prologue_event(str(event or raw.get("event") or ""), raw)
        except Exception:
            logging.debug("Nova's Prologue skipped [%s]", event, exc_info=True)

    def _prologue_event(self, event, raw):
        state = self._prologue_state()
        if state.get("state") != "found":
            return
        lyra = self._prologue_lyra()
        if lyra is None:
            return
        system = raw.get("StarSystem") or getattr(self, "current_sys", "")
        name = prologue.installation_name(event, raw, system)
        if name:
            seen = list(state.get("installations") or ())
            if name not in seen:
                state["installations"] = (seen + [name])[-10:]
                self._prologue_write(state)
            return
        moved = prologue.step(state, event, raw, system)
        if not moved:
            return
        self._prologue_hush = None
        self._prologue_scene(state, moved, lyra)
        state["state"] = moved
        self._prologue_write(state)
        self._schedule_html_dashboard_publish(immediate=True)

    # -- the companion page -------------------------------------------------------------
    def _prologue_told(self, state):
        """The scenes told, in order; Scene 4's two parts as one."""
        scenes = state.get("scenes") or {}
        told = []
        for key in prologue.ORDER:
            if key not in scenes:
                continue
            if told and told[-1]["title"] == prologue.TITLES[key]:
                told[-1]["lines"] += list(prologue.LINES[key])
                continue
            told.append({"key": key, "title": prologue.TITLES[key], "lines": list(prologue.LINES[key]), "at": scenes[key]})
        return told

    def _prologue_hello(self):
        """Whether Nova has said hello (Scene 5, her Entry 01, which ends the
        Prologue and opens Chapter I); None when she isn't on watch to ask."""
        mind = self._prologue_mind()
        story = getattr(mind, "_progress", None)
        if getattr(mind, "identity", "") != "nova" or story is None:
            return None
        return story.order[0] in story.told(mind.memory)

    def _prologue_page(self):
        """The BRIDGE card: on Lyra's page while it's under way, then on
        Nova's ("Initializing") until her first words. None otherwise."""
        state = self._prologue_state()
        stage = state.get("state") or ""
        if not stage or state.get("met_before"):
            return None
        if stage == "installed":
            if self._prologue_hello() is not False:
                return None
            return {"title": prologue.TITLE, "state": stage, "told": self._prologue_told(state),
                    "initializing": prologue.SYSTEM_MESSAGE}
        if companions.identity(self.config) != TELLER:
            return None
        return {"title": prologue.TITLE, "state": stage, "told": self._prologue_told(state),
                "objective": prologue.OBJECTIVES.get(stage, ""),
                "system": prologue.SYSTEM if stage == "found" else ""}

    def _prologue_chapter(self):
        """Nova's book opens with her Prologue, as Lyra told it."""
        state = self._prologue_state()
        if state.get("met_before"):
            return None
        told = self._prologue_told(state)
        if not told:
            return None
        rows = [{"id": f"prologue:{row['key']}", "text": " ".join(row["lines"]), "at": row["at"], "entry": 0, "label": "",
                 "title": row["title"], "place": None} for row in told]
        return {"numeral": "P", "title": prologue.TITLE.split(" · ", 1)[-1], "book": 1, "begun": True,
                # It ends with her first words, Chapter I's opening entry.
                "complete": "installing" in (state.get("scenes") or {}) and bool(self._prologue_hello()), "told": rows,
                "told_count": len(rows), "total": len(dict.fromkeys(prologue.TITLES.values())), "about": "", "account": "", "narrator": "LYRA",
                "prologue": True}

    def _prologue_lore(self, lore):
        """Nova's story page with her Prologue first and how she grows."""
        if not isinstance(lore, dict) or lore.get("identity") != "nova":
            return lore
        chapter = self._prologue_chapter()
        if chapter:
            lore = {**lore, "chapters": [chapter, *(lore.get("chapters") or ())]}
        return {**lore, "guide": dict(prologue.GETTING_TO_KNOW, activities=list(prologue.GETTING_TO_KNOW["activities"]))}
