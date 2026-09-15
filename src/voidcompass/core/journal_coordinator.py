"""Central ingestion and distribution for Elite Dangerous journal data.

``JournalWatcher`` remains responsible for reading and normalising files.  This
coordinator is the application's single boundary around that reader: consumers
subscribe here instead of being wired directly to filesystem callbacks.
"""

from __future__ import annotations

from collections import defaultdict
import logging
import threading
from typing import Callable

from voidcompass.core.journal_watcher import JournalWatcher


JournalCallback = Callable[[dict], object]
BatchCallback = Callable[[list[dict]], object]
DispatchCallback = Callable[..., object]


class JournalCoordinator:
    """Own one journal reader and distribute its output to app consumers.

    Journal events retain their original order.  A consumer may provide a
    batch handler for efficient startup replay; consumers without one receive
    every event in that batch individually.  Companion JSON snapshots use
    named channels and may be safely coalesced by the UI dispatcher.
    """

    SNAPSHOT_CHANNELS = frozenset({
        "cargo", "nav_route", "status", "market", "ship_locker",
    })

    def __init__(
        self,
        journal_path,
        *,
        trace_callback=None,
        config=None,
        dispatch: DispatchCallback | None = None,
        watcher: JournalWatcher | None = None,
    ):
        self._dispatch = dispatch
        self._lock = threading.RLock()
        self._journal_consumers: list[tuple[JournalCallback, BatchCallback | None]] = []
        self._snapshot_consumers: dict[str, list[tuple[Callable, str | None]]] = defaultdict(list)
        self._watcher = watcher or JournalWatcher(
            journal_path,
            trace_callback=trace_callback,
            config=config,
        )
        # This is deliberately the only callback registration on the physical
        # watcher.  Every downstream feature receives data through this hub.
        self._watcher.register_callback(
            event_cb=self._publish_event,
            batch_cb=self._publish_batch,
            cargo_cb=lambda data, vessel="Ship": self._publish_snapshot(
                "cargo", data, vessel,
            ),
            nav_cb=lambda data: self._publish_snapshot("nav_route", data),
            status_cb=lambda data: self._publish_snapshot("status", data),
            market_cb=lambda data: self._publish_snapshot("market", data),
            ship_locker_cb=lambda data: self._publish_snapshot("ship_locker", data),
        )

    @property
    def reader(self) -> JournalWatcher:
        """Return the owned reader for diagnostics and parser-level helpers."""
        return self._watcher

    def subscribe_journal(
        self,
        event_callback: JournalCallback,
        *,
        batch_callback: BatchCallback | None = None,
    ) -> Callable[[], None]:
        """Subscribe to normalised journal events and return an unsubscribe hook."""
        if not callable(event_callback):
            raise TypeError("event_callback must be callable")
        subscription = (event_callback, batch_callback)
        with self._lock:
            self._journal_consumers.append(subscription)

        def unsubscribe():
            with self._lock:
                if subscription in self._journal_consumers:
                    self._journal_consumers.remove(subscription)

        return unsubscribe

    def subscribe_snapshot(
        self,
        channel: str,
        callback: Callable,
        *,
        dispatch_key: str | None = None,
    ) -> Callable[[], None]:
        """Subscribe to one companion JSON source and return an unsubscribe hook."""
        channel = str(channel or "").strip().casefold()
        if channel not in self.SNAPSHOT_CHANNELS:
            raise ValueError(f"Unknown journal snapshot channel: {channel or '<empty>'}")
        if not callable(callback):
            raise TypeError("callback must be callable")
        subscription = (callback, dispatch_key)
        with self._lock:
            self._snapshot_consumers[channel].append(subscription)

        def unsubscribe():
            with self._lock:
                consumers = self._snapshot_consumers[channel]
                if subscription in consumers:
                    consumers.remove(subscription)

        return unsubscribe

    def _deliver(self, callback: Callable, *args, key: str | None = None):
        if callable(self._dispatch):
            try:
                return self._dispatch(callback, *args, key=key)
            except Exception:
                logging.exception("Journal coordinator could not queue a consumer")
                return False
        try:
            callback(*args)
            return True
        except Exception:
            logging.exception("Journal coordinator consumer failed")
            return False

    def _journal_subscriptions(self):
        with self._lock:
            return tuple(self._journal_consumers)

    def _publish_event(self, event):
        for event_callback, _batch_callback in self._journal_subscriptions():
            self._deliver(event_callback, event)

    def _publish_batch(self, events):
        batch = list(events or ())
        for event_callback, batch_callback in self._journal_subscriptions():
            if callable(batch_callback):
                self._deliver(batch_callback, list(batch))
                continue
            for event in batch:
                self._deliver(event_callback, event)

    def _publish_snapshot(self, channel, *args):
        with self._lock:
            subscriptions = tuple(self._snapshot_consumers.get(channel, ()))
        for callback, dispatch_key in subscriptions:
            self._deliver(callback, *args, key=dispatch_key)

    # Keep the historic ``app.watcher`` surface compatible while callers are
    # migrated to ``app.journal``.  Lifecycle calls, state reads and parser
    # helpers are delegated to the same owned JournalWatcher.
    def __getattr__(self, name):
        return getattr(self._watcher, name)

    @property
    def config(self):
        return self._watcher.config

    @config.setter
    def config(self, value):
        self._watcher.config = value

    @property
    def journal_path(self):
        return self._watcher.journal_path

    @journal_path.setter
    def journal_path(self, value):
        self._watcher.journal_path = value

    @property
    def last_journal(self):
        return self._watcher.last_journal

    @last_journal.setter
    def last_journal(self, value):
        self._watcher.last_journal = value

    @property
    def file_pos(self):
        return self._watcher.file_pos

    @file_pos.setter
    def file_pos(self, value):
        self._watcher.file_pos = value
