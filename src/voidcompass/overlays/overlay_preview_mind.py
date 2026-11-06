"""A silent companion shell while its writing and voice are still pending."""
from voidcompass.core import companions
from voidcompass.overlays.watcher_mind import WatcherMind


class OverlayPreviewMind(WatcherMind):
    def __init__(self, memory_path=None, config=None, **kwargs):
        self.identity = companions.identity(config)
        super().__init__(memory_path, companions.settings(config or {}, self.identity), **kwargs)

    def _quiet(self, *args, **kwargs):
        return None

    consider = note = tick = observe = learn = load_game = session_start = _quiet
    remember = poke = find_voice = ask = answer = pending_question = relay = _quiet
    say_after = uplink_answer = meet = share_card = follow_up = _quiet

    def talk(self, text, voice=False):
        return False

    def story_marks(self):
        return {}

    def story_progress(self):
        return {"identity": self.identity, "told": 0, "total": 0}

    def voice_stage(self):
        return 0

    def memories_page(self, now=None):
        return []

    def name_page(self):
        return {"pending": True, "known": "", "nickname": "", "spoken": "", "story": None}
