"""Behavioral checks for the Navigation HUD's journal-driven state instrument.

The browser portion inspects canvas pixels, not screenshots, so these tests can
run headlessly alongside the regular unittest suite. Playwright remains an
optional development dependency.
"""

from pathlib import Path
import unittest
from urllib.parse import urlsplit

from voidcompass.overlays.hud import TacticalHUD


WEB = Path(__file__).resolve().parents[1] / "web"


class NavigationStateVisualTests(unittest.TestCase):
    def test_journal_labels_keep_distinct_visual_motion_families(self):
        expected = {
            "FLIGHT": "flight",
            "SUPERCRUISE": "supercruise",
            "FSD CHARGE": "fsd_charge",
            "HYPERSPACE": "jump",
            "FSS": "scanner",
            "ORBITAL APPROACH": "orbital_approach",
            "GLIDE": "glide",
            "LANDED": "landed",
            "DOCKED": "docked",
            "INTERDICTION": "combat",
            "ONFOOT": "on_foot",
            "CARRIER TRANSIT": "carrier_transit",
        }
        for label, motion in expected.items():
            with self.subTest(label=label):
                self.assertEqual(TacticalHUD._navigation_motion_profile(label), motion)

    def test_indicator_renders_distinct_state_silhouettes_and_honors_reduced_motion(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Playwright is not installed")

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except Exception as exc:
                self.skipTest(f"Playwright Chromium is unavailable: {exc}")
            try:
                page = browser.new_page(viewport={"width": 620, "height": 342})

                def serve(route):
                    path = WEB / urlsplit(route.request.url).path.lstrip("/")
                    if path.is_file():
                        route.fulfill(path=str(path))
                    else:
                        route.fulfill(status=404, body="")

                page.route("http://state.test/**", serve)
                page.goto("http://state.test/navigation_hud/index.html")
                result = page.evaluate("""() => {
                  const indicator = stateIndicator;
                  indicator.running = false;
                  const cases = [
                    ['flight', 'FLIGHT'], ['supercruise', 'SUPERCRUISE'],
                    ['fsd_charge', 'FSD CHARGE'], ['jump', 'HYPERSPACE'],
                    ['scanner', 'FSS'], ['orbital_approach', 'ORBITAL APPROACH'],
                    ['glide', 'GLIDE'], ['landed', 'LANDED'],
                    ['docked', 'DOCKED'], ['combat', 'INTERDICTION'],
                    ['on_foot', 'ONFOOT'], ['carrier_transit', 'CARRIER TRANSIT'],
                  ];
                  const signatures = {};
                  for (const [motion, label] of cases) {
                    indicator.update({motion, label, color: '#607584', reduced: true});
                    indicator.draw(performance.now());
                    const g = indicator.responseGeometry(indicator.geometry());
                    const ratio = indicator.ratio;
                    const pixels = indicator.ctx.getImageData(
                      Math.ceil(g.left * ratio), Math.ceil(g.top * ratio),
                      Math.floor((g.right - g.left) * ratio),
                      Math.floor((g.bottom - g.top) * ratio)).data;
                    let hash = 2166136261, visible = 0;
                    for (let index = 3; index < pixels.length; index += 4) {
                      const alpha = pixels[index];
                      if (alpha > 10) visible++;
                      hash = Math.imul(hash ^ alpha, 16777619) >>> 0;
                    }
                    signatures[label] = {hash, visible};
                  }
                  indicator.update({motion: 'flight', label: 'FLIGHT', reduced: false});
                  indicator.update({motion: 'jump', label: 'HYPERSPACE', reduced: false,
                    eventSequence: 1, eventKind: 'route_set'});
                  const transitionStarted = Boolean(indicator.previous);
                  const eventStarted = indicator.eventKind === 'route_set' && indicator.eventStarted > 0;
                  indicator.update({motion: 'jump', label: 'HYPERSPACE', reduced: true});
                  return {signatures, transitionStarted, eventStarted,
                    reducedClearedTransition: !indicator.previous && !indicator.transitionImage};
                }""")
                signatures = result["signatures"]
                self.assertTrue(all(value["visible"] > 0 for value in signatures.values()))
                self.assertEqual(len({value["hash"] for value in signatures.values()}), len(signatures))
                self.assertTrue(result["transitionStarted"])
                self.assertTrue(result["eventStarted"])
                self.assertTrue(result["reducedClearedTransition"])

                page.set_viewport_size({"width": 430, "height": 326})
                geometry_failures = page.evaluate("""() => {
                  const failures = [];
                  stateIndicator.resize();
                  const labels = [
                    ['arrival', 'INTERDICTION EVADED'],
                    ['carrier_preparing', 'CARRIER PREPARING'],
                    ['flight_assist_off', 'FLIGHT ASSIST OFF'],
                    ['suit_hazard', 'SUIT OXYGEN LOW'],
                    ['fsd_lock', 'FSD INJECTION 100%'],
                    ['scanner', 'DSS EFFICIENT 7/7'],
                    ['station', 'STATION VICINITY'],
                    ['vehicle_board', 'BOARDING SCORPION'],
                  ];
                  for (const scale of [1.5, 2]) {
                    for (const [motion, label] of labels) {
                      render({schema: 1, layout: 'standard', theme: {text_scale: scale},
                        effects: {reduced_motion: true}, state: {motion, label}});
                      const core = document.querySelector('.state-core').getBoundingClientRect();
                      const instrument = document.querySelector('.state-instrument').getBoundingClientRect();
                      const canvas = document.getElementById('state-canvas').getBoundingClientRect();
                      const text = document.getElementById('state-label');
                      const range = document.createRange();
                      range.selectNodeContents(text);
                      const glyphs = range.getBoundingClientRect();
                      const responseLeft = canvas.left + stateIndicator.responseGeometry(
                        stateIndicator.geometry()).left;
                      // The centre label must stay inside its own protected
                      // aperture, with a gap before the canvas response bay.
                      if (glyphs.width <= 0 || glyphs.left < core.left + 3
                          || glyphs.right > core.right - 3
                          || glyphs.right > responseLeft - 4
                          || glyphs.top < instrument.top || glyphs.bottom > instrument.bottom) {
                        failures.push({label, scale, glyphs: {left: glyphs.left,
                          right: glyphs.right, top: glyphs.top, bottom: glyphs.bottom},
                          core: {left: core.left, right: core.right}, responseLeft});
                      }
                    }
                  }
                  return failures;
                }""")
                self.assertEqual(geometry_failures, [], geometry_failures)

                # Compare the right-hand canvas bay at rest, using alpha only:
                # a different label or theme colour cannot make two scenes
                # appear distinct to this check.
                right_bay_groups = page.evaluate("""() => {
                  const indicator = stateIndicator;
                  const groups = {
                    travel: [
                      ['supercruise', 'SUPERCRUISE'], ['supercruise', 'TAXI'],
                      ['supercruise_assist', 'SC ASSIST'],
                      ['supercruise_overcharge', 'SCO OVERCHARGE'],
                      ['fsd_charge', 'FSD CHARGE'],
                      ['fsd_charge', 'HYPER CHARGE'],
                      ['fsd_lock', 'FSD INJECTION +50%'],
                      ['fsd_cooldown', 'FSD COOLDOWN'],
                      ['jump', 'HYPERSPACE'], ['jump', 'JUMPING'],
                      ['arrival', 'ARRIVAL'], ['arrival', 'INTERDICTION EVADED'],
                      ['local_arrival', 'LOCAL ARRIVAL'],
                    ],
                    maps: [
                      ['map', 'MAP'], ['map', 'GALAXY MAP'],
                      ['map', 'SYSTEM MAP'], ['map', 'POWER MAP'],
                      ['map', 'ORRERY'], ['map', 'CODEX'],
                    ],
                    scans: [
                      ['scanner', 'FSS'], ['scanner', 'DSS'],
                      ['scanner', 'DSS EFFICIENT 4/6'],
                      ['scanner', 'DSS COMPLETE 4/6'],
                    ],
                    surface: [
                      ['orbital_approach', 'ORBITAL APPROACH'],
                      ['orbital_departure', 'ORBITAL DEPARTURE'],
                      ['surface_approach', 'SURFACE APPROACH'],
                      ['surface_departure', 'SURFACE DEPARTURE'],
                      ['surface_hold', 'SURFACE HOLD'],
                      ['glide', 'GLIDE'], ['landed', 'LANDED'],
                    ],
                    vehicles: [
                      ['surface_vehicle', 'SRV'],
                      ['surface_vehicle', 'SCARAB'],
                      ['surface_vehicle', 'SCORPION'],
                      ['surface_vehicle', 'RHINO'],
                      ['surface_vehicle', 'NOMAD'],
                      ['on_foot', 'ONFOOT'],
                    ],
                    docking: [
                      ['station', 'STATION VICINITY'],
                      ['docking_clearance', 'DOCK REQUEST'],
                      ['docking_clearance', 'PAD 07 CLEARED'],
                      ['docking_denied', 'DOCK DENIED'],
                      ['docking_denied', 'DOCK CANCELLED'],
                      ['docking_denied', 'DOCK TIMEOUT'],
                      ['docked', 'DOCKED'],
                      ['surface_station', 'SURFACE STATION'],
                      ['settlement_area', 'SETTLEMENT'],
                    ],
                    carrier: [
                      ['carrier_preparing', 'CARRIER PREPARING'],
                      ['carrier_lockdown', 'CARRIER LOCKDOWN'],
                      ['carrier_transit', 'CARRIER TRANSIT'],
                      ['carrier_arrival', 'CARRIER ARRIVAL'],
                      ['carrier_deck', 'CARRIER DECK'],
                      ['station', 'CARRIER VICINITY'],
                    ],
                    handoff: [
                      ['vehicle_deploy', 'SCARAB DEPLOY'],
                      ['vehicle_deploy', 'SCORPION DEPLOY'],
                      ['vehicle_deploy', 'RHINO DEPLOY'],
                      ['vehicle_deploy', 'NOMAD DEPLOY'],
                      ['vehicle_deploy', 'FIGHTER DEPLOY'],
                      ['vehicle_deploy', 'SHIP DEPART'],
                      ['vehicle_board', 'SCARAB RECOVERY'],
                      ['vehicle_switch', 'SCARAB CONTROL'],
                      ['vehicle_switch', 'SCORPION CONTROL'],
                      ['vehicle_switch', 'RHINO CONTROL'],
                      ['vehicle_switch', 'NOMAD CONTROL'],
                      ['vehicle_switch', 'FIGHTER CONTROL'],
                    ],
                    target: [
                      ['target_lock', 'TARGET LOCK'],
                      ['target_lock', 'SYSTEM TARGET'],
                      ['target_lock', 'BODY TARGET'],
                      ['target_lock', 'SIGNAL TARGET'],
                      ['target_lock', 'TARGET CLEARED'],
                    ],
                    contacts: [
                      ['asteroid_field', 'ASTEROID FIELD'],
                      ['fsd_lock', 'MASS LOCK'],
                      ['fsd_lock', 'SIGNAL LOCK'],
                      ['fsd_lock', 'SIGNAL DROP'],
                      ['fsd_lock', 'SIGNAL THREAT 4'],
                      ['combat', 'INTERDICTION'],
                      ['combat', 'INTERDICTED'],
                      ['combat', 'COMBAT'],
                      ['heavy_combat', 'HEAVY COMBAT'],
                      ['srv_threat', 'SRV THREAT'],
                      ['unknown_contact', 'UNIDENTIFIED'],
                      ['capital_contact', 'CAPITAL SHIP'],
                    ],
                    cockpit: [
                      ['flight', 'FLIGHT'],
                      ['flight', 'MULTICREW'],
                      ['fighter', 'FIGHTER'],
                      ['flight_assist_off', 'FLIGHT ASSIST OFF'],
                      ['silent_running', 'SILENT RUNNING'],
                      ['left_panel', 'LEFT PANEL'],
                      ['right_panel', 'RIGHT PANEL'],
                      ['comms_panel', 'COMMS'],
                      ['role_panel', 'ROLE PANEL'],
                      ['station_services', 'SERVICES'],
                      ['maintenance', 'AFMU REPAIR'],
                      ['system_reboot', 'SYSTEM REBOOT'],
                      ['heat_critical', 'HEAT CRITICAL'],
                      ['suit_hazard', 'SUIT OXYGEN LOW'],
                      ['suit_hazard', 'SUIT HEALTH LOW'],
                      ['suit_hazard', 'EXTREME COLD'],
                      ['suit_hazard', 'SUIT COLD'],
                      ['suit_hazard', 'EXTREME HEAT'],
                      ['suit_hazard', 'SUIT HEAT'],
                      ['jet_cone_damage', 'JET CONE DAMAGE'],
                    ],
                  };
                  const signatures = {};
                  for (const [group, cases] of Object.entries(groups)) {
                    signatures[group] = [];
                    for (const [motion, label] of cases) {
                      indicator.update({motion, label, color: '#607584', reduced: true});
                      indicator.draw(performance.now());
                      const g = indicator.responseGeometry(indicator.geometry());
                      const ratio = indicator.ratio;
                      const pixels = indicator.ctx.getImageData(
                        Math.ceil(g.left * ratio), Math.ceil(g.top * ratio),
                        Math.floor((g.right - g.left) * ratio),
                        Math.floor((g.bottom - g.top) * ratio)).data;
                      let hash = 2166136261, visible = 0;
                      for (let index = 3; index < pixels.length; index += 4) {
                        const alpha = pixels[index];
                        if (alpha > 10) visible++;
                        hash = Math.imul(hash ^ alpha, 16777619) >>> 0;
                      }
                      signatures[group].push({label, key: indicator.key(indicator.state),
                        hash, visible});
                    }
                  }
                  // Exercise animated paths as well as their reduced-motion
                  // silhouettes. This catches state-only canvas exceptions.
                  for (const cases of Object.values(groups)) {
                    for (const [motion, label] of cases) {
                      indicator.update({motion, label, color: '#607584', reduced: false});
                      indicator.previous = null;
                      indicator.transitionImage = null;
                      indicator.draw(performance.now() + 900);
                    }
                  }
                  return signatures;
                }""")
                for group, entries in right_bay_groups.items():
                    with self.subTest(group=group):
                        self.assertTrue(all(entry["visible"] > 0 for entry in entries))
                        self.assertEqual(
                            len({entry["hash"] for entry in entries}), len(entries),
                            entries,
                        )
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
