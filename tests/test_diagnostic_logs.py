import json
import os
from pathlib import Path
import tempfile
import unittest

from voidcompass.core.diagnostic_logs import prepare_log, resolve_log_path
from voidcompass.core.runtime_trace import RuntimeTrace


class DiagnosticLogTests(unittest.TestCase):
    def test_bare_names_resolve_into_logs_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            expected = Path(folder) / "logs" / "runtime_trace.log"
            self.assertEqual(
                Path(resolve_log_path("runtime_trace.log", "runtime_trace.log", folder)),
                expected,
            )

    def test_legacy_root_log_is_archived_during_migration(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            legacy = base / "runtime_trace.log"
            current = base / "logs" / "runtime_trace.log"
            legacy.write_text("previous run", encoding="utf-8")

            prepare_log(current, legacy_paths=(legacy,), keep=10)

            archives = list(current.parent.glob("runtime_trace.*.log"))
            self.assertFalse(legacy.exists())
            self.assertEqual(len(archives), 1)
            self.assertEqual(archives[0].read_text(encoding="utf-8"), "previous run")

    def test_archive_family_is_bounded_to_ten_previous_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            current = Path(folder) / "logs" / "crash_report.log"
            current.parent.mkdir(parents=True)
            for index in range(14):
                current.write_text(f"run {index}", encoding="utf-8")
                os.utime(current, (1_700_000_000 + index, 1_700_000_000 + index))
                prepare_log(current, keep=10)
            archives = list(current.parent.glob("crash_report.*.log"))
            self.assertEqual(len(archives), 10)
            self.assertTrue(any(path.read_text(encoding="utf-8") == "run 13" for path in archives))
            self.assertFalse(any(path.read_text(encoding="utf-8") == "run 0" for path in archives))

    def test_runtime_trace_archives_then_starts_a_fresh_current_log(self):
        with tempfile.TemporaryDirectory() as folder:
            current = Path(folder) / "logs" / "runtime_trace.log"
            current.parent.mkdir(parents=True)
            current.write_text("old trace", encoding="utf-8")

            trace = RuntimeTrace(current, enabled=True)
            trace.start()

            payload = json.loads(current.read_text(encoding="utf-8"))
            archives = list(current.parent.glob("runtime_trace.*.log"))
            self.assertEqual(payload["type"], "trace_start")
            self.assertEqual(len(archives), 1)
            self.assertEqual(archives[0].read_text(encoding="utf-8"), "old trace")


if __name__ == "__main__":
    unittest.main()
