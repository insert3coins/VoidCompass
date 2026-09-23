import unittest

from voidcompass.dashboard.html_dashboard_host import DashboardHost


class _Window:
    def __init__(self):
        self.scripts = []
        self.results = iter(("pending", "ready"))

    def evaluate_js(self, script):
        self.scripts.append(script)
        return next(self.results)


class DashboardBootHandoffTests(unittest.TestCase):
    def test_native_host_waits_for_browser_hold_and_only_requests_recovery(self):
        host = DashboardHost("http://127.0.0.1:8765/?token=test")
        host.window = _Window()

        host._service_boot_release(True, False, 100.0)
        host._service_boot_release(False, False, 101.0)
        host._service_boot_release(False, False, 107.9)
        self.assertEqual(host.window.scripts, [])

        host._service_boot_release(False, False, 108.1)
        self.assertEqual(len(host.window.scripts), 1)
        self.assertIn("voidcompass:boot-recover", host.window.scripts[0])
        self.assertNotIn("classList.add('ready')", host.window.scripts[0])
        self.assertNotIn("hidden=true", host.window.scripts[0])

        host._service_boot_release(False, False, 108.5)
        self.assertEqual(len(host.window.scripts), 1)
        host._service_boot_release(False, False, 109.2)
        self.assertTrue(host.boot_released)
        self.assertEqual(len(host.window.scripts), 2)

        host._service_boot_release(True, False, 110.0)
        self.assertFalse(host.boot_released)
        self.assertEqual(host.boot_release_started_at, 0.0)


if __name__ == "__main__":
    unittest.main()
