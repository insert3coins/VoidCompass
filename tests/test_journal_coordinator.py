import unittest

from voidcompass.core.journal_coordinator import JournalCoordinator


class _FakeWatcher:
    def __init__(self):
        self.config = {"source": "test"}
        self.journal_path = "journals"
        self.last_journal = None
        self.file_pos = 0
        self.callbacks = {}

    def register_callback(self, **callbacks):
        self.callbacks = callbacks

    def start(self):
        return "started"


class JournalCoordinatorTests(unittest.TestCase):
    def test_one_reader_registration_feeds_journal_and_snapshot_consumers(self):
        reader = _FakeWatcher()
        queued = []

        def dispatch(callback, *args, key=None):
            queued.append(key)
            callback(*args)

        coordinator = JournalCoordinator(
            "ignored", watcher=reader, dispatch=dispatch,
        )
        events = []
        batches = []
        cargo = []
        coordinator.subscribe_journal(events.append, batch_callback=batches.append)
        coordinator.subscribe_snapshot(
            "cargo", lambda rows, vessel: cargo.append((rows, vessel)),
            dispatch_key="journal:cargo",
        )

        reader.callbacks["event_cb"]({"type": "Location"})
        reader.callbacks["batch_cb"]([{"type": "Scan"}, {"type": "FSDJump"}])
        reader.callbacks["cargo_cb"]([{"Name": "Tritium"}], "Ship")

        self.assertEqual(events, [{"type": "Location"}])
        self.assertEqual(len(batches), 1)
        self.assertEqual([row["type"] for row in batches[0]], ["Scan", "FSDJump"])
        self.assertEqual(cargo, [([{"Name": "Tritium"}], "Ship")])
        self.assertEqual(queued, [None, None, "journal:cargo"])
        self.assertIs(coordinator.reader, reader)

    def test_batch_falls_back_to_ordered_events_for_simple_consumers(self):
        reader = _FakeWatcher()
        coordinator = JournalCoordinator("ignored", watcher=reader)
        received = []
        coordinator.subscribe_journal(lambda event: received.append(event["sequence"]))

        reader.callbacks["batch_cb"]([
            {"sequence": 1}, {"sequence": 2}, {"sequence": 3},
        ])

        self.assertEqual(received, [1, 2, 3])

    def test_unsubscribe_and_compatibility_proxy_do_not_create_another_reader(self):
        reader = _FakeWatcher()
        coordinator = JournalCoordinator("ignored", watcher=reader)
        received = []
        unsubscribe = coordinator.subscribe_snapshot("status", received.append)

        reader.callbacks["status_cb"]({"Flags": 1})
        unsubscribe()
        reader.callbacks["status_cb"]({"Flags": 2})
        coordinator.journal_path = "new-journals"
        coordinator.config = {"source": "updated"}

        self.assertEqual(received, [{"Flags": 1}])
        self.assertEqual(reader.journal_path, "new-journals")
        self.assertEqual(reader.config, {"source": "updated"})
        self.assertEqual(coordinator.start(), "started")

    def test_unknown_snapshot_channel_is_rejected(self):
        coordinator = JournalCoordinator("ignored", watcher=_FakeWatcher())
        with self.assertRaises(ValueError):
            coordinator.subscribe_snapshot("mystery", lambda _data: None)


if __name__ == "__main__":
    unittest.main()
