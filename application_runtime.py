"""Single-owner Python event loop and renderer window metadata.

No GUI toolkit is loaded by this module. Worker threads submit callbacks;
application state is changed serially by the thread running ``run``.
"""
from __future__ import annotations

import heapq
import itertools
import logging
import re
import threading
import time
from types import SimpleNamespace


class ApplicationRuntime:
    def __init__(self):
        self._condition = threading.Condition()
        self._pending = []
        self._callbacks = {}
        self._ids = itertools.count(1)
        self._closed = False
        self._owner = threading.get_ident()
        self._shutdown_callbacks = []
        self._voidcompass_startup_presentation_held = True
        self._voidcompass_html_dashboard_enabled = True

    def call_later(self, milliseconds, callback, *args):
        if not callable(callback):
            raise TypeError("A scheduled callback must be callable")
        with self._condition:
            if self._closed:
                return None
            token = next(self._ids)
            self._callbacks[token] = (callback, args)
            heapq.heappush(self._pending, (time.monotonic() + max(0, milliseconds) / 1000, token))
            self._condition.notify()
            return token

    def cancel(self, token):
        with self._condition:
            self._callbacks.pop(token, None)
            self._condition.notify()

    def on_shutdown(self, callback):
        self._shutdown_callbacks.append(callback)

    def run(self):
        self._owner = threading.get_ident()
        while True:
            with self._condition:
                while not self._closed:
                    while self._pending and self._pending[0][1] not in self._callbacks:
                        heapq.heappop(self._pending)
                    if not self._pending:
                        self._condition.wait()
                        continue
                    due, token = self._pending[0]
                    delay = due - time.monotonic()
                    if delay > 0:
                        self._condition.wait(delay)
                        continue
                    heapq.heappop(self._pending)
                    callback, args = self._callbacks.pop(token)
                    break
                else:
                    return
            try:
                callback(*args)
            except Exception:
                handler = getattr(self, "report_callback_exception", None)
                if handler:
                    import sys
                    handler(*sys.exc_info())
                logging.exception("Application callback failed: %s", getattr(callback, '__name__', callback))

    def close(self):
        with self._condition:
            if self._closed:
                return
            self._closed = True
            self._callbacks.clear()
            self._pending.clear()
            self._condition.notify_all()
        for callback in reversed(self._shutdown_callbacks):
            try:
                callback()
            except Exception:
                logging.exception("Application shutdown callback failed")

    @property
    def is_owner_thread(self):
        return threading.get_ident() == self._owner

    def winfo_screenwidth(self):
        from native_services import screen_size
        return screen_size()[0]

    def winfo_screenheight(self):
        from native_services import screen_size
        return screen_size()[1]

    def copy_text(self, text):
        from native_services import copy_text
        return copy_text(text)


class OverlayWindowState:
    """Desired WebView window state; never creates an OS window or a widget.

    Existing controllers use geometry/state accessors while HTML hosts own
    the actual native windows. Destruction is explicit and observable.
    """
    def __init__(self, runtime, width=400, height=200, x=100, y=100):
        self.master = runtime
        self.width, self.height, self.x, self.y = width, height, x, y
        self.visible = True
        self.closed = False
        self._destroy_callbacks = []
        self._jobs = set()

    def geometry(self, value=None):
        if value is None:
            return f"{self.width}x{self.height}{self.x:+d}{self.y:+d}"
        size = re.fullmatch(r'(\d+)x(\d+)', value)
        if size:
            self.width, self.height = map(int, size.groups())
            return
        match = re.fullmatch(r"(?:(\d+)x(\d+))?([+-]-?\d+)([+-]-?\d+)", value)
        if not match:
            raise ValueError(f"Invalid window geometry: {value}")
        width, height, x, y = match.groups()
        if width:
            self.width, self.height = int(width), int(height)
        self.x, self.y = int(x.replace('+-', '-')), int(y.replace('+-', '-'))

    def state(self):
        return 'normal' if self.visible and not self.closed else 'withdrawn'

    def withdraw(self):
        self.visible = False

    def deiconify(self):
        if not self.closed:
            self.visible = True

    def winfo_exists(self):
        return not self.closed

    def winfo_x(self):
        return self.x

    def winfo_y(self):
        return self.y

    def winfo_width(self):
        return self.width

    def winfo_height(self):
        return self.height

    def call_later(self, milliseconds, callback, *args):
        if self.closed:
            return None
        holder = []
        def invoke():
            self._jobs.discard(holder[0])
            if not self.closed:
                callback(*args)
        token = self.master.call_later(milliseconds, invoke)
        holder.append(token)
        self._jobs.add(token)
        return token

    def cancel(self, token):
        self._jobs.discard(token)
        self.master.cancel(token)

    def on_destroy(self, callback):
        self._destroy_callbacks.append(callback)

    def destroy(self):
        if self.closed:
            return
        self.closed = True
        self.visible = False
        for token in tuple(self._jobs):
            self.cancel(token)
        for callback in self._destroy_callbacks:
            callback(SimpleNamespace(widget=self))
