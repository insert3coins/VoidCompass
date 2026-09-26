"""Errors logged anywhere in the app reach the crash report.

The packaged app has no console, so logging's default stderr handler writes
nowhere. A UI callback failure in a real session left only a failure count in
the runtime trace; its traceback was lost. The crash reporter now keeps
logged errors, and caps repeats so a persistent fault cannot flood the file.
"""

import io
import logging
import unittest
from unittest.mock import patch

from voidcompass.core import crash_reporter


class LoggedErrorsTests(unittest.TestCase):
    def setUp(self):
        self.report = io.StringIO()
        self.handler = crash_reporter._LoggedErrors()
        self.logger = logging.getLogger("voidcompass.tests.logged_errors")
        self.logger.propagate = False
        self.logger.addHandler(self.handler)
        self.addCleanup(self.logger.removeHandler, self.handler)

    def test_a_logged_exception_keeps_its_traceback(self):
        with patch.object(crash_reporter, "_CRASH_FILE", self.report):
            try:
                raise ValueError("bad callback")
            except ValueError:
                self.logger.exception("Application dispatcher callback failed: %s", "_apply")
            self.logger.warning("PERF SPIKE [screenshot.process_folder] 41.0 ms")
        text = self.report.getvalue()
        self.assertIn("[logged error]", text)
        self.assertIn("Application dispatcher callback failed: _apply", text)
        self.assertIn("Traceback (most recent call last)", text)
        self.assertIn("ValueError: bad callback", text)
        self.assertNotIn("PERF SPIKE", text, "warnings stay out of the crash report")

    def test_a_persistent_fault_is_tallied_rather_than_repeated(self):
        with patch.object(crash_reporter, "_CRASH_FILE", self.report), \
                patch("voidcompass.core.crash_reporter.time.monotonic", return_value=100.0) as clock:
            for _ in range(10):
                self.logger.error("Watcher Error: %s", "journal folder unavailable")
            self.assertEqual(self.report.getvalue().count("Watcher Error"), 3)
            clock.return_value = 161.0
            self.logger.error("Watcher Error: %s", "journal folder unavailable")
        text = self.report.getvalue()
        self.assertEqual(text.count("Watcher Error"), 4)
        self.assertIn("(7 repeats not shown)", text)

    def test_nothing_is_written_without_an_open_report(self):
        with patch.object(crash_reporter, "_CRASH_FILE", None):
            self.logger.error("Cache rebuild failed")
        self.assertEqual(self.report.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
