import unittest

from system_info_hud import SystemInfoHUD


class SystemInfoHudModelTests(unittest.TestCase):
    def test_system_rows_do_not_repeat_notable_body_tags(self):
        hud = SystemInfoHUD.__new__(SystemInfoHUD)
        hud._system = "Test System"
        hud._star_class = "G"
        hud._body_count = 8
        hud._scanned_count = 4
        hud._bio_total = 2
        hud._edsm_info = {}
        hud._spansh = {
            "star_classes": ["G"],
            "planet_count": 7,
            "landable_count": 3,
            "counts": {"starport": 0, "outpost": 0, "settlement": 0, "fc": 0},
            "services": {"mat_trader": False, "tech_broker": False, "engineer": False},
            # Older cached structures may still contain this field; System Info
            # must ignore it now that Survey Status owns notable bodies.
            "spansh_notable": ["Earthlike", "Water World", "Terraformable"],
        }

        text = "\n".join(row[0] for row in hud._build_rows())

        self.assertIn("TEST SYSTEM", text)
        self.assertIn("4 Scanned", text)
        self.assertNotIn("Earthlike", text)
        self.assertNotIn("Water World", text)
        self.assertNotIn("Terraformable", text)


if __name__ == "__main__":
    unittest.main()
