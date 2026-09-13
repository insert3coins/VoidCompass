import threading
import unittest
from pathlib import Path
from application_runtime import ApplicationRuntime, OverlayWindowState
from dashboard import MainDashboard
from ui_dispatcher import ApplicationDispatcher
from version import APP_VERSION

class ApplicationRuntimeTests(unittest.TestCase):
    def test_cross_thread_work_is_serial_and_cancelled_work_never_runs(self):
        loop = ApplicationRuntime()
        observed = []
        token = loop.call_later(0, lambda: observed.append('cancelled'))
        loop.cancel(token)
        def worker():
            loop.call_later(0, lambda: observed.append(threading.get_ident()))
            loop.call_later(0, loop.close)
        thread = threading.Thread(target=worker)
        thread.start(); thread.join()
        loop.run()
        self.assertEqual(observed, [threading.get_ident()])
        self.assertIsNone(loop.call_later(0, lambda: None))

    def test_window_disposal_cancels_timers_and_notifies_renderer(self):
        loop=ApplicationRuntime()
        window=OverlayWindowState(loop)
        observed=[]
        window.call_later(0,lambda:observed.append('expired'))
        window.on_destroy(lambda event:observed.append(event.widget))
        window.destroy();window.destroy()
        loop.call_later(0,loop.close);loop.run()
        self.assertEqual(observed,[window])

    def test_dispatcher_preserves_events_and_coalesces_snapshots(self):
        loop=ApplicationRuntime();dispatcher=ApplicationDispatcher(loop);observed=[]
        dispatcher.post(observed.append,'old',key='status')
        dispatcher.post(observed.append,'jump')
        dispatcher.post(observed.append,'new',key='status')
        loop.call_later(40,loop.close);loop.run()
        self.assertEqual(observed,['new','jump'])
        self.assertEqual(dispatcher.stats()['failures'],0)


class AboutPageTests(unittest.TestCase):
    def test_about_page_identifies_the_release_and_creator(self):
        root = Path(__file__).resolve().parents[1]
        index = (root / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        script = (root / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertEqual(APP_VERSION, "5.4.3.4")
        self.assertIn('id="about-matrix-canvas"', index)
        self.assertIn("Copyright © 2026 insert3coins", index)
        self.assertIn('data-target="license"', index)
        self.assertIn('data-target="documentation"', index)
        self.assertIn('data-target="notices"', index)
        self.assertIn("function startAboutMatrix()", script)


class RhinoCargoTransferTests(unittest.TestCase):
    @staticmethod
    def dashboard(ship_rows):
        dashboard = MainDashboard.__new__(MainDashboard)
        dashboard.current_cargo_vessel = "Ship"
        dashboard.current_cargo_inventory = list(ship_rows)
        dashboard.current_cargo_tons = dashboard._cargo_inventory_total(ship_rows)
        dashboard.cargo_capacity = 322
        dashboard.current_in_srv = True
        dashboard.current_in_fighter = False
        dashboard.current_vehicle_name = "RHINO"
        dashboard._last_surface_vehicle_name = "RHINO"
        dashboard._cargo_inventory_by_hold = {}
        dashboard.cargo_hud = None
        dashboard._refresh_html_workspace = lambda: None
        dashboard._refresh_cargo_consumers()
        return dashboard

    def test_transfer_to_mothership_updates_both_holds_before_docking(self):
        dashboard = self.dashboard([{"Name": "gold", "Count": 12}])
        dashboard.current_cargo_inventory = [
            {"Name": "platinum", "Count": 61, "Stolen": 0},
        ]
        dashboard.current_cargo_tons = 61
        dashboard._cargo_inventory_by_hold["SRV:RHINO"] = list(
            dashboard.current_cargo_inventory
        )

        changed = dashboard._apply_rhino_cargo_transfer({
            "Transfers": [{
                "Type": "platinum", "Count": 61, "Direction": "toship",
            }],
        })

        self.assertTrue(changed)
        self.assertEqual(dashboard.current_cargo_inventory, [])
        self.assertEqual(dashboard.current_cargo_tons, 0)
        self.assertEqual(
            dashboard._cargo_inventory_total(
                dashboard._cargo_inventory_by_hold["Ship"]
            ),
            73,
        )

    def test_transfer_to_rhino_debits_ship_but_carrier_transfer_is_ignored(self):
        dashboard = self.dashboard([{"Name": "platinum", "Count": 20}])
        self.assertTrue(dashboard._apply_rhino_cargo_transfer({
            "Transfers": [{
                "Type": "platinum", "Count": 7, "Direction": "tosrv",
            }],
        }))
        self.assertEqual(dashboard.current_cargo_tons, 7)
        self.assertEqual(
            dashboard._cargo_inventory_by_hold["Ship"],
            [{"Name": "platinum", "Count": 13}],
        )
        self.assertFalse(dashboard._apply_rhino_cargo_transfer({
            "Transfers": [{
                "Type": "platinum", "Count": 5, "Direction": "tocarrier",
            }],
        }))
