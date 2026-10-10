"""5.5.3.4: the Navigation HUD said SURFACE DEPARTURE after a restart with no
surface anywhere near. A Location login names the nearest body even out in
space; that tracked a planet, supercruise from there counted as leaving it,
and nothing after (dropping at a star, docking, undocking) let it go. The
shapes below are the commander's real journal events."""

from pathlib import Path
import unittest

from voidcompass.dashboard.dashboard import _location_surface_focus

ROOT = Path(__file__).resolve().parents[1]

# 2026-10-10: logged in 4,379 ls out, near a planet but not at it.
IN_SPACE = {"event": "Location", "Docked": False, "Taxi": False, "Body": "Wregoe BB-G b52-4 AB 2",
            "BodyID": 17, "BodyType": "Planet", "DistFromStarLS": 4379.014203}
# 2026-01-30: logged in in an SRV on the surface.
IN_SRV = {"event": "Location", "Docked": False, "InSRV": True, "Body": "Rendezvous Point 3 c", "BodyID": 35,
          "BodyType": "Planet", "Latitude": -29.968599, "Longitude": -103.394638}
# 2026-07-03: logged in on foot on the surface: no coordinates.
ON_FOOT = {"event": "Location", "Docked": False, "OnFoot": True, "Body": "HIP 97950 ABC 2 k", "BodyID": 9,
           "BodyType": "Planet", "DistFromStarLS": 2455.858156}


class LocationFocusTests(unittest.TestCase):
    def test_out_in_space_tracks_no_planet(self):
        self.assertEqual(_location_surface_focus("Location", IN_SPACE, {}), (None, ""))

    def test_on_the_surface_tracks_it(self):
        self.assertEqual(_location_surface_focus("Location", IN_SRV, {}), (35, "Rendezvous Point 3 c"))
        self.assertEqual(_location_surface_focus("Location", ON_FOOT, {}), (9, "HIP 97950 ABC 2 k"),
                         "on foot the game leaves out the coordinates")
        landed = {**IN_SRV, "InSRV": False}
        self.assertEqual(_location_surface_focus("Location", landed, {})[0], 35)

    def test_docked_or_another_event_tracks_nothing(self):
        self.assertEqual(_location_surface_focus("Location", {**IN_SRV, "Docked": True}, {}), (None, ""))
        self.assertEqual(_location_surface_focus("FSDJump", IN_SRV, {}), (None, ""))


class ClearingTests(unittest.TestCase):
    def test_arriving_or_docking_ends_a_departure(self):
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        exit_branch = source.split('elif ev == "SupercruiseExit":', 1)[1].split("elif ev ==", 1)[0]
        self.assertIn("self._surface_departure_active = False", exit_branch)
        self.assertIn('== "star"', exit_branch, "dropping at a star lets go of the planet")
        docked_branch = source.split('elif ev == "Docked":', 1)[1].split("elif ev ==", 1)[0]
        self.assertIn("self._surface_departure_active = False", docked_branch)


if __name__ == "__main__":
    unittest.main()
