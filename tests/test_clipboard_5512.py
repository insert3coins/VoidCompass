"""5.5.12: copying the next system (and everything else) reaches the
clipboard even when another program is holding it for a moment, and says
in the Event Feed when it couldn't."""

import ctypes
import os
import threading
import time
import unittest
from types import SimpleNamespace

from voidcompass.core.native_services import copy_text


def read_clipboard():
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.GetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    for _ in range(40):
        if user32.OpenClipboard(None):
            break
        time.sleep(.025)
    try:
        handle = user32.GetClipboardData(13)
        if not handle:
            return None
        pointer = kernel32.GlobalLock(handle)
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def hold_clipboard(seconds, ready):
    user32 = ctypes.windll.user32
    if user32.OpenClipboard(None):
        ready.set()
        time.sleep(seconds)
        user32.CloseClipboard()
    else:
        ready.set()


@unittest.skipUnless(os.name == "nt", "the Windows clipboard")
class ClipboardTests(unittest.TestCase):
    def setUp(self):
        try:
            self.before = read_clipboard()
        except Exception:
            self.before = None

    def tearDown(self):
        if self.before is not None:
            copy_text(self.before)

    def test_it_lands_on_the_clipboard(self):
        copy_text("Colonia")
        self.assertEqual(read_clipboard(), "Colonia")

    def test_another_program_holding_it_for_a_moment(self):
        ready = threading.Event()
        holder = threading.Thread(target=hold_clipboard, args=(.15, ready))
        holder.start()
        ready.wait(2)
        copy_text("Sagittarius A*")
        holder.join()
        self.assertEqual(read_clipboard(), "Sagittarius A*")

    def test_held_too_long_says_so(self):
        ready = threading.Event()
        holder = threading.Thread(target=hold_clipboard, args=(.4, ready))
        holder.start()
        ready.wait(2)
        with self.assertRaises(OSError) as caught:
            copy_text("Beagle Point", attempts=2, wait_s=.01)
        holder.join()
        self.assertIn("busy", str(caught.exception))


class FeedbackTests(unittest.TestCase):
    def deck(self, fails=False):
        from voidcompass.dashboard.dashboard_core_mixin import DashboardCoreMixin
        from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin

        class Deck(DashboardCoreMixin, HtmlDashboardMixin):
            pass

        deck = Deck.__new__(Deck)
        deck.feed = []
        deck.add_event_feed_entry = lambda tag, message, severity="INFO", copy_text=None, url=None: deck.feed.append((tag, message, severity))

        def copy(value):
            if fails:
                raise OSError("the clipboard is busy: another program has it open")
            deck.copied = value
        deck.root = SimpleNamespace(copy_text=copy)
        return deck

    def test_a_copy_says_it_worked(self):
        deck = self.deck()
        deck._dashboard_next_destination = lambda: "Colonia"
        self.assertTrue(deck._dashboard_copy_next())
        self.assertEqual(deck.copied, "Colonia")
        self.assertEqual(deck.feed[-1], ("ROUTE", "Copied next system: Colonia", "INFO"))

    def test_a_failed_copy_says_why(self):
        deck = self.deck(fails=True)
        deck._dashboard_next_destination = lambda: "Colonia"
        self.assertFalse(deck._dashboard_copy_next())
        tag, message, severity = deck.feed[-1]
        self.assertEqual((tag, severity), ("CLIPBOARD", "FAIL"))
        self.assertIn("busy", message)

    def test_nothing_to_copy(self):
        deck = self.deck()
        deck._dashboard_next_destination = lambda: None
        self.assertFalse(deck._dashboard_copy_next())
        self.assertEqual(deck.feed[-1][2], "WARN")


if __name__ == "__main__":
    unittest.main()
