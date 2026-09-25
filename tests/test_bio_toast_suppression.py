"""Exobiology progress belongs in Survey Operations, not duplicate toasts."""

import unittest
from unittest.mock import Mock

from voidcompass.dashboard.dashboard import MainDashboard


class BioToastSuppressionTests(unittest.TestCase):
    def test_live_biology_samples_and_analysis_do_not_toast(self):
        app = MainDashboard.__new__(MainDashboard)
        app.is_first_load = False
        app._push_live_toast = Mock()

        for scan_type in ("Log", "Sample", "Analyse"):
            with self.subTest(scan_type=scan_type):
                app._handle_live_journal_toast(
                    "ScanOrganic", {"ScanType": scan_type},
                    {"scan_type": scan_type, "species": "Bacterium Aurasus"},
                )

        app._push_live_toast.assert_not_called()

    def test_distinct_codex_discovery_still_toasts(self):
        app = MainDashboard.__new__(MainDashboard)
        app.is_first_load = False
        app._push_live_toast = Mock()

        app._handle_live_journal_toast(
            "CodexEntry", {"Name_Localised": "Bacterium Aurasus"},
            {"category": "Biology", "name": "Bacterium Aurasus"},
        )

        app._push_live_toast.assert_called_once_with(
            "CODEX DISCOVERY", "Biology: Bacterium Aurasus", "success", 15,
        )


if __name__ == "__main__":
    unittest.main()
