"""Profile-aware marker used to recognise an unclean previous shutdown."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time


class ProfileSessionGuard:
    def __init__(self, path, version):
        self.path = Path(path)
        self.version = str(version)
        self.previous = self._read()
        self.unclean = bool(self.previous)
        self._open()

    def _read(self):
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _open(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(self.path.name + ".tmp")
            temporary.write_text(json.dumps({
                "pid": os.getpid(), "started_at": time.time(), "version": self.version,
            }, indent=2), encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError:
            pass

    def switch(self, path):
        self.close()
        self.path = Path(path)
        self.previous = self._read()
        self.unclean = bool(self.previous)
        self._open()

    def close(self):
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def description(self):
        if not self.unclean:
            return ""
        started = self.previous.get("started_at")
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(started)) if started else "an unknown time"
        return f"Recovered an unfinished Void Compass session started at {when}."
