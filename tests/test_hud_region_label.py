import unittest
from application_runtime import ApplicationRuntime
from hud import TacticalHUD
from galactic_regions import region_names

class HudRegionLabelTests(unittest.TestCase):
    def test_region_model_preserves_long_names_in_both_html_layouts(self):
        root = ApplicationRuntime()
        try:
            for compact in (False, True):
                view = TacticalHUD(root, {'hud_compact_mode': compact})
                name = max(region_names(), key=len)
                view.update('Sol', '', 0, 0, 0, None, {}, nav_context={'region':{'id':1,'name':name,'crossed':True}})
                self.assertIn(name.upper(), view._html_last_model['system']['region'].upper())
                self.assertFalse(hasattr(view, 'canvas'))
                view.win.destroy()
        finally:
            root.close()
