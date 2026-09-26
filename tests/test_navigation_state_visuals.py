"""Behavioral checks for the Navigation HUD's cockpit status plate.

Elite's cockpit reports state with a few notice styles and its own indicator
lamps. The HUD follows that: Python chooses the state and its family, and the
page shows the family's notice plus a measured instrument that only draws
journal-backed values. Each state's animated scene is covered separately in
test_navigation_scene.py. The browser portion reads the DOM, not screenshots,
so these tests run headlessly. Playwright remains an optional development
dependency.
"""

import json
from pathlib import Path
import time
import unittest
from urllib.parse import unquote, urlsplit

from voidcompass.core.application_runtime import ApplicationRuntime
from voidcompass.overlays.hud import TacticalHUD


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SHIP_ART = ROOT / "assets" / "images" / "ships"
FAMILIES = {"drive", "restrict", "alert", "planet", "scan", "dock", "vehicle", "panel", "flight"}

# Every label the state machine can put on the HUD, grouped as the cockpit
# would think of them.
LABELS = [
    "FLIGHT", "MULTICREW", "EXPLORATION", "FLIGHT ASSIST OFF", "SILENT RUNNING",
    "SUPERCRUISE", "TAXI", "SC ASSIST", "SCO OVERCHARGE", "FSD CHARGE", "HYPER CHARGE",
    "FSD INJECTION +50%", "FSD COOLDOWN", "HYPERSPACE", "JUMPING", "ARRIVAL",
    "INTERDICTION EVADED", "LOCAL ARRIVAL",
    "MAP", "GALAXY MAP", "SYSTEM MAP", "POWER MAP", "ORRERY", "CODEX",
    "FSS", "DSS", "DSS EFFICIENT 4/6", "DSS COMPLETE 4/6", "PHENOMENA",
    "TARGET LOCK", "SYSTEM TARGET", "BODY TARGET", "SIGNAL TARGET", "TARGET CLEARED",
    "ORBITAL APPROACH", "ORBITAL DEPARTURE", "SURFACE APPROACH", "SURFACE DEPARTURE",
    "SURFACE HOLD", "GLIDE", "LANDED", "SURFACE STATION", "SETTLEMENT",
    "SRV", "SCARAB", "SCORPION", "RHINO", "NOMAD", "HANDBRAKE", "TURRET VIEW",
    "DRIVE ASSIST", "ONFOOT", "FIGHTER",
    "STATION VICINITY", "CARRIER VICINITY", "DOCK REQUEST", "PAD 07 CLEARED",
    "DOCK DENIED", "DOCK CANCELLED", "DOCK TIMEOUT", "DOCK ASSIST", "DOCKED",
    "AFMU REPAIR",
    "CARRIER PREPARING", "CARRIER LOCKDOWN", "CARRIER TRANSIT", "CARRIER ARRIVAL",
    "CARRIER DECK",
    "SCARAB DEPLOY", "FIGHTER DEPLOY", "SHIP DEPART", "SCARAB RECOVERY",
    "BOARDING SCORPION", "SCARAB CONTROL", "MULTICREW LINK", "CREW RETURN",
    "ASTEROID FIELD", "MASS LOCK", "SIGNAL LOCK", "SIGNAL DROP", "SIGNAL THREAT 4",
    "UNIDENTIFIED", "CAPITAL SHIP",
    "INTERDICTION", "INTERDICTED", "COMBAT", "HEAVY COMBAT", "SRV THREAT",
    "HEAT CRITICAL", "SUIT OXYGEN LOW", "SUIT HEALTH LOW", "EXTREME COLD",
    "SUIT COLD", "EXTREME HEAT", "SUIT HEAT", "JET CONE DAMAGE", "SYSTEM REBOOT",
    "LEFT PANEL", "RIGHT PANEL", "COMMS", "ROLE PANEL", "SERVICES",
]


def hud_state(label, **dynamics):
    """One state exactly as Python publishes it for this label."""
    motion = TacticalHUD._navigation_motion_profile(label)
    return {
        "label": label,
        "motion": motion,
        "color": TacticalHUD._state_color(TacticalHUD.__new__(TacticalHUD), label),
        "category": TacticalHUD._navigation_category(label, motion),
        "vehicle": {"ship_symbol": "diamondbackxl", "ship_type": "DiamondBackXL",
                    "ship_name": "Wandering Star", "surface": ""},
        "dynamics": {"in_main_ship": True, "analysis_mode": True, **dynamics},
    }


def hud_snapshot(state, layout="standard", scale=1.0, reduced=True, **extra):
    hops = [
        {"name": "COL 285 SECTOR AB-C D14-7", "completed": True, "star_class": "K", "scoopable": True},
        {"name": "SYNUEFE XR-H D11-102", "current": True, "star_class": "G", "scoopable": True},
        {"name": "PLAA AEC IZ-N C20-1", "next": True, "star_class": "F", "scoopable": True},
        {"name": "PLAA AEC OI-S B5-2", "star_class": "L", "scoopable": False},
    ]
    snapshot = {
        "schema": 1, "layout": layout,
        "theme": {"text_scale": scale},
        "effects": {"reduced_motion": reduced, "crt": True, "opacity": 1},
        "state": state,
        "system": {"name": "SYNUEFE XR-H D11-102", "star_class": "G",
                   "region": "REGION 18 // INNER ORION SPUR", "arrival_epoch": time.time() - 90},
        "route": {"active": True, "source": "neutron", "target": "PLAA AEC IZ-N C20-1",
                  "next_star": {"star_class": "F", "scoopable": True}, "fuel_endurance_jumps": 6,
                  "leg_distance": "48.7 LY", "remaining_distance": "412.9 LY",
                  "progress_percent": 25, "hops": hops},
        "survey": {"state": "live", "scanned": 7, "total": 16, "total_known": True,
                   "percent": 43.75, "tone": "#ff7a18",
                   "signals": {"bio": 4, "geo": 2, "mining": 0, "valuable": 1}},
        "metrics": {"fuel": {"value": "71%", "color": "#4ee59b", "percent": 71},
                    "bio": {"value": "1/4"}, "traffic": {"value": "0 / 3 / 41"}},
        "context": {"primary": "NEUTRON ROUTE // 412.9 LY LEFT", "primary_color": "#00d1ff",
                    "secondary": "FUEL CHECK AT NEXT STAR", "traffic": "TRAFFIC 0/3/41"},
        "window": {"visible": True},
    }
    snapshot.update(extra)
    return snapshot


class NavigationStatePresentationTests(unittest.TestCase):
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

    def test_every_state_belongs_to_one_notice_family(self):
        for label in LABELS:
            with self.subTest(label=label):
                motion = TacticalHUD._navigation_motion_profile(label)
                self.assertIn(TacticalHUD._navigation_category(label, motion), FAMILIES)
        expected = {
            "SUPERCRUISE": "drive", "FSD CHARGE": "drive", "HYPERSPACE": "drive",
            "CARRIER TRANSIT": "drive", "INTERDICTION EVADED": "drive",
            # An armed boost is good news, not a restriction like mass lock.
            "FSD INJECTION +50%": "drive",
            "MASS LOCK": "restrict", "ASTEROID FIELD": "restrict", "CAPITAL SHIP": "restrict",
            "SIGNAL THREAT 4": "alert", "INTERDICTION": "alert", "HEAT CRITICAL": "alert",
            "SUIT OXYGEN LOW": "alert", "SYSTEM REBOOT": "alert",
            "GLIDE": "planet", "LANDED": "planet", "SURFACE STATION": "planet",
            "FSS": "scan", "GALAXY MAP": "scan", "BODY TARGET": "scan",
            # A targeted signal source is a target, not a signal lock.
            "SIGNAL TARGET": "scan",
            "DOCKED": "dock", "PAD 07 CLEARED": "dock", "DOCK DENIED": "dock",
            "SRV": "vehicle", "ONFOOT": "vehicle", "FIGHTER": "vehicle",
            # Someone else's ship: its lamps are not the commander's.
            "TAXI": "vehicle", "MULTICREW": "vehicle",
            "LEFT PANEL": "panel", "FLIGHT": "flight", "SILENT RUNNING": "flight",
        }
        for label, family in expected.items():
            with self.subTest(label=label):
                motion = TacticalHUD._navigation_motion_profile(label)
                self.assertEqual(TacticalHUD._navigation_category(label, motion), family)

    def test_event_notices_report_only_what_the_state_cannot(self):
        notice = TacticalHUD._navigation_event_notice
        honk = notice({"seq": 4, "kind": "honk", "tone": "accent", "duration": 1.5,
                       "body_count": 16})
        self.assertEqual((honk["text"], honk["detail"], honk["tone"]),
                         ("SYSTEM SCAN", "16 BODIES", "accent"))
        self.assertGreaterEqual(honk["duration"], 2.4, "a notice must stay readable")
        first = notice({"seq": 5, "kind": "first_discovery", "tone": "green",
                        "body_name": "Synuefe XR-H d11-102 A 3"}, "SYNUEFE XR-H D11-102")
        self.assertEqual((first["text"], first["detail"]), ("FIRST DISCOVERY", "A 3"))
        warning = notice({"seq": 6, "kind": "warning", "event": "HullDamage", "tone": "orange"})
        self.assertEqual((warning["text"], warning["tone"]), ("HULL DAMAGE", "red"))
        # Jumps, docking, vehicles and interdictions already change the state.
        for kind in ("arrival", "dock", "vehicle_deploy", "interdiction", "supercruise_enter"):
            with self.subTest(kind=kind):
                self.assertIsNone(notice({"seq": 7, "kind": kind}))
        self.assertIsNone(notice({"kind": "honk"}), "no sequence, nothing to show")
        self.assertIsNone(notice(None))

    def test_model_carries_family_notice_lamps_fuel_and_scaled_window(self):
        root = ApplicationRuntime()
        try:
            hud = TacticalHUD(root, {"overlay_text_scale_percent": 150})
            try:
                hud.update(
                    "SYNUEFE XR-H D11-102", "", 0, 7, 16, None, {},
                    nav_context={
                        "current": "SYNUEFE XR-H D11-102", "flight_state": "SUPERCRUISE",
                        "fuel_percent": 70.6,
                        "ship_config": {
                            "in_main_ship": True, "silent_running": True,
                            "flight_assist_off": True, "overheating": False,
                            "srv_handbrake": False, "supercruise_assist": False,
                        },
                        "journal_event": {"seq": 3, "kind": "body_scan", "tone": "accent",
                                          "duration": 1.1},
                    },
                )
                model = hud._html_last_model
                self.assertEqual(model["state"]["category"], "drive")
                self.assertEqual(model["state"]["notice"]["text"], "BODY SCANNED")
                # Every pulse also reaches the scene, as a one-shot accent.
                self.assertEqual((model["state"]["event_sequence"], model["state"]["event_kind"],
                                  model["state"]["event_tone"]), (3, "body_scan", "accent"))
                dynamics = model["state"]["dynamics"]
                self.assertTrue(dynamics["silent_running"] and dynamics["flight_assist_off"])
                self.assertIn("srv_handbrake", dynamics)
                self.assertEqual(model["metrics"]["fuel"]["percent"], 71)
                self.assertEqual(model["metrics"]["fuel"]["value"], "71%")
                # 150% text is a 150% instrument, never clipped type.
                self.assertEqual((model["window"]["width"], model["window"]["height"]), (750, 489))
                self.assertEqual(hud._html_window_size, (750, 489))
                self.assertEqual(model["theme"]["text_scale"], 1.5)
            finally:
                hud.win.destroy()
        finally:
            root.close()


class NavigationStatusPlateBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f"Playwright Chromium is unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def open(self, width=500, height=326):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))

        def serve(route, _request=None):
            path = unquote(urlsplit(route.request.url).path)
            if path.startswith("/ship-art/"):
                target = SHIP_ART / path[len("/ship-art/"):]
            else:
                target = WEB / path.lstrip("/")
            if target.is_file():
                route.fulfill(path=str(target))
            else:
                route.fulfill(status=404, body="")

        page.route("http://state.test/**", serve)
        # No token: the page renders only what each test hands it.
        page.goto("http://state.test/navigation_hud/index.html")
        return page

    def render(self, page, snapshot):
        page.evaluate("snapshot => render(snapshot)", snapshot)

    def plate(self, page):
        return page.evaluate("""() => ({
          instrument: dom.instrument.dataset.instrument,
          supercharged: dom.instrument.classList.contains('supercharged'),
          readout: dom['instrument-readout'].textContent,
          markerHidden: dom['instrument-marker'].hidden,
          marker: parseFloat(dom['instrument-marker'].style.left),
          tag: dom['state-tag'].textContent,
          label: dom['state-label'].textContent,
          category: dom.hud.dataset.category,
          lamps: [...dom.lamps.children].map((lamp) => lamp.textContent),
          lampTones: [...dom.lamps.children].map((lamp) => lamp.className),
        })""")

    def test_each_family_gets_one_instrument_fed_only_by_journal_values(self):
        page = self.open()
        cases = [
            (hud_state("SUPERCRUISE"), {"instrument": "flow", "tag": "FSD",
                                        "label": "SUPERCRUISE", "readout": ""}),
            (hud_state("SUPERCRUISE", neutron_boost=True, neutron_boost_value=4),
             {"instrument": "flow", "supercharged": True, "readout": "SUPERCHARGED ×4.0"}),
            (hud_state("FSD CHARGE"), {"instrument": "flow", "label": "FSD CHARGING"}),
            (hud_state("HYPERSPACE"), {"instrument": "flow"}),
            (hud_state("FSD COOLDOWN"), {"instrument": "flow"}),
            (hud_state("CARRIER TRANSIT"), {"instrument": "flow", "tag": "CARRIER"}),
            (hud_state("GLIDE", altitude_m=18400, vertical_mps=310, gravity_g=.42),
             {"instrument": "altimeter", "tag": "PLANETARY",
              "readout": "ALT 18.4 KM  ▼ 310 M/S  0.42 G", "markerHidden": False}),
            # No altitude in the journal: no altimeter, and nothing invented.
            (hud_state("SURFACE APPROACH", altitude_m=None), {"instrument": "idle", "readout": ""}),
            (hud_state("LANDED", gravity_g=.42), {"instrument": "idle", "readout": "0.42 G"}),
            (hud_state("FSS", scan_percent=.44), {"instrument": "scan", "tag": "SENSORS", "readout": "44%"}),
            (hud_state("DSS"), {"instrument": "idle"}),
            (hud_state("GALAXY MAP"), {"instrument": "idle", "tag": "MAP"}),
            (hud_state("INTERDICTION"), {"instrument": "alert", "tag": "WARNING"}),
            (hud_state("MASS LOCK"), {"instrument": "lock", "tag": "CAUTION", "label": "MASS LOCKED"}),
            (hud_state("DOCKED"), {"instrument": "idle", "tag": "DOCKING"}),
            (hud_state("PAD 07 CLEARED"), {"label": "DOCKING GRANTED · PAD 07"}),
            (hud_state("FLIGHT"), {"instrument": "idle", "tag": "SHIP", "label": "NORMAL SPACE"}),
            (hud_state("ONFOOT"), {"instrument": "idle", "tag": "SUIT", "label": "ON FOOT"}),
        ]
        for state, expected in cases:
            with self.subTest(label=state["label"], dynamics=state["dynamics"]):
                self.render(page, hud_snapshot(state))
                plate = self.plate(page)
                for key, value in expected.items():
                    self.assertEqual(plate[key], value, key)
        # The altimeter reads a log scale from 10 m to 200 km.
        self.render(page, hud_snapshot(hud_state("GLIDE", altitude_m=1000)))
        self.assertAlmostEqual(self.plate(page)["marker"], 46.5, delta=.1)
        # Danger is always red, whatever colour the state machine suggested.
        self.render(page, hud_snapshot(hud_state("INTERDICTION")))
        tones = page.evaluate("""() => [dom.hud.style.getPropertyValue('--state'),
          getComputedStyle(document.documentElement).getPropertyValue('--red').trim()]""")
        self.assertEqual(tones[0], tones[1])

    def test_lamps_light_only_engaged_systems_and_never_repeat_the_notice(self):
        page = self.open()
        self.render(page, hud_snapshot(hud_state(
            "SUPERCRUISE", landing_gear=True, hardpoints_deployed=True, fuel_scooping=True,
            shields_known=True, shields_up=False,
        )))
        plate = self.plate(page)
        self.assertEqual(plate["lamps"], ["ANALYSIS", "SHIELDS DOWN", "HARDPOINTS", "GEAR", "FUEL SCOOPING"])
        self.assertIn("tone-danger", plate["lampTones"][1])
        self.render(page, hud_snapshot(hud_state("SILENT RUNNING", silent_running=True, analysis_mode=False)))
        self.assertEqual(self.plate(page)["lamps"], ["COMBAT"])
        # Without Status.json flags there is no ship state to guess at.
        self.render(page, hud_snapshot(hud_state("SUPERCRUISE", in_main_ship=False)))
        self.assertEqual(self.plate(page)["lamps"], [])
        self.render(page, hud_snapshot(hud_state("SRV", srv_handbrake=True, night_vision=True)))
        self.assertEqual(self.plate(page)["lamps"], ["HANDBRAKE", "NIGHT VISION"])
        self.render(page, hud_snapshot(hud_state("HANDBRAKE", srv_handbrake=True)))
        self.assertEqual(self.plate(page)["lamps"], [])
        self.render(page, hud_snapshot(hud_state("ONFOOT", night_vision=True)))
        self.assertEqual(self.plate(page)["lamps"], [])

    def test_fuel_gauge_and_event_notices(self):
        page = self.open()
        state = hud_state("SUPERCRUISE", fuel_scooping=True)
        self.render(page, hud_snapshot(state))
        fuel = page.evaluate("""() => ({
          lit: dom['fuel-cells'].querySelectorAll('i.lit').length,
          cells: dom['fuel-cells'].children.length,
          text: dom['metric-fuel'].textContent,
          scooping: dom['fuel-gauge'].classList.contains('scooping'),
        })""")
        self.assertEqual(fuel, {"lit": 8, "cells": 10, "text": "71%", "scooping": True})
        unknown = hud_snapshot(hud_state("SUPERCRUISE"))
        unknown["metrics"]["fuel"] = {"value": "--", "percent": None}
        self.render(page, unknown)
        self.assertEqual(page.evaluate("""() => [dom['fuel-cells'].querySelectorAll('i.lit').length,
          dom['metric-fuel'].textContent, dom['fuel-gauge'].classList.contains('unknown')]"""), [0, "--", True])

        scan = dict(state, notice={"seq": 5, "text": "BODY SCANNED", "detail": "", "tone": "accent", "duration": 1})
        self.render(page, hud_snapshot(scan))
        self.assertEqual(page.evaluate("""() => [dom['event-notice'].textContent,
          dom['event-notice'].classList.contains('showing')]"""), ["BODY SCANNED", True])
        # Snapshots repeat a live pulse until it expires; it must not restart.
        page.evaluate("dom['event-notice'].classList.remove('showing')")
        self.render(page, hud_snapshot(scan))
        self.assertFalse(page.evaluate("dom['event-notice'].classList.contains('showing')"))
        first = dict(state, notice={"seq": 6, "text": "FIRST DISCOVERY", "detail": "A 3", "tone": "green", "duration": 1})
        self.render(page, hud_snapshot(first))
        self.assertEqual(page.evaluate("""() => [dom['event-notice'].textContent,
          dom['event-notice'].style.getPropertyValue('--event-tone')]"""), ["FIRST DISCOVERY · A 3", "var(--green)"])
        page.wait_for_function("!dom['event-notice'].classList.contains('showing')", timeout=3000)

    def test_warnings_flash_and_reduced_motion_stops_every_animation(self):
        page = self.open()
        self.render(page, hud_snapshot(hud_state("INTERDICTION"), reduced=False))
        self.assertTrue(page.evaluate("document.querySelector('.notice').getAnimations().length > 0"))
        self.render(page, hud_snapshot(hud_state("FSD CHARGE"), reduced=False))
        self.assertTrue(page.evaluate("navigationScene.running"), "the state's scene animates")
        self.assertFalse(page.evaluate("document.querySelector('.notice').getAnimations()"
                                       ".some((animation) => animation.animationName === 'warning-flash')"))
        # A hidden overlay pauses its looping animations and its scene rather
        # than spending frames on them (a one-shot transition may finish).
        self.render(page, hud_snapshot(hud_state("FSD CHARGE"), reduced=False, window={"visible": False}))
        self.assertTrue(page.evaluate("""() => {
          const loops = document.getAnimations().filter((animation) => animation instanceof CSSAnimation);
          return loops.length > 0 && loops.every((animation) => animation.playState === 'paused');
        }"""))
        self.assertFalse(page.evaluate("navigationScene.running"))
        self.render(page, hud_snapshot(hud_state("INTERDICTION"), reduced=True))
        self.assertEqual(page.evaluate("document.getAnimations().length"), 0)
        self.assertFalse(page.evaluate("navigationScene.running"))

    def test_every_state_fits_both_layouts_at_normal_and_larger_text(self):
        long_labels = [
            "PAD 07 CLEARED", "SC ASSIST", "SURFACE DEPARTURE", "ORBITAL DEPARTURE",
            "CARRIER PREPARING", "SUIT OXYGEN LOW", "SIGNAL THREAT 4", "BOARDING SCORPION",
            "HEAT CRITICAL", "DSS EFFICIENT 4/6", "FSD INJECTION +50%",
        ]
        for layout, width, height in (("standard", 500, 326), ("expanded", 620, 342)):
            for scale in (1, 1.5):
                page = self.open(round(width * scale), round(height * scale))
                for label in long_labels:
                    state = hud_state(label, landing_gear=True, hardpoints_deployed=True,
                                      cargo_scoop=True, night_vision=True, fuel_scooping=True,
                                      altitude_m=18400, vertical_mps=310, gravity_g=.42)
                    state["notice"] = {"seq": len(label), "text": "FIRST DISCOVERY",
                                       "detail": "SYNUEFE XR-H D11-102 A 3", "tone": "green", "duration": 3}
                    snapshot = hud_snapshot(state, layout=layout, scale=scale)
                    snapshot["system"]["name"] = "PLAA AEC IZ-N C20-1 AB 12 C"
                    with self.subTest(layout=layout, scale=scale, label=label):
                        self.render(page, snapshot)
                        failures = page.evaluate("""() => {
                          const failures = [];
                          const box = (node) => node.getBoundingClientRect();
                          const root = document.documentElement;
                          if (root.scrollWidth > innerWidth + 1 || root.scrollHeight > innerHeight + 1)
                            failures.push('page scrolls');
                          const hud = box(dom.hud);
                          if (Math.abs(hud.width - innerWidth) > 1 || Math.abs(hud.height - innerHeight) > 1)
                            failures.push('instrument does not fill its window');
                          const sections = ['.status-plate', '.location', '.route-block',
                            '.survey-block', '.context-rail'].map((selector) => box(document.querySelector(selector)));
                          sections.forEach((section, index) => {
                            if (section.top < -.5 || section.bottom > innerHeight + .5) failures.push(`section ${index} outside`);
                            if (index && sections[index - 1].bottom > section.top + .5) failures.push(`section ${index} overlaps`);
                          });
                          const inside = (inner, outer, name) => {
                            const a = box(inner), b = box(outer);
                            if (!a.width && !a.height) return;  // Not rendered (e.g. an empty readout).
                            if (a.left < b.left - .5 || a.right > b.right + .5 || a.top < b.top - .5 || a.bottom > b.bottom + .5)
                              failures.push(`${name} escapes`);
                          };
                          inside(dom['state-label'], dom.notice, 'state label');
                          inside(dom['event-notice'], dom.notice, 'event notice');
                          inside(dom.notice, document.querySelector('.status-plate'), 'notice');
                          inside(dom.lamps, document.querySelector('.systems-row'), 'lamps');
                          inside(dom['fuel-gauge'], document.querySelector('.systems-row'), 'fuel');
                          inside(dom['vehicle-image'], document.querySelector('.holo-bay'), 'ship art');
                          inside(dom['instrument-readout'], dom.instrument, 'readout');
                          return failures;
                        }""")
                        self.assertEqual(failures, [])

    def test_ship_hologram_keeps_catalogue_art_and_names_the_vessel(self):
        page = self.open()
        read = """() => ({src: dom['vehicle-image'].getAttribute('src') || '',
          type: dom['vehicle-type'].textContent, name: dom['vehicle-name'].textContent,
          empty: dom['vehicle-display'].classList.contains('empty')})"""
        self.render(page, hud_snapshot(hud_state("SUPERCRUISE")))
        self.assertEqual(page.evaluate(read), {
            "src": "/ship-art/DiamondBack%20Explorer.png", "type": "DIAMONDBACK EXPLORER",
            "name": "WANDERING STAR", "empty": False})
        page.wait_for_function("dom['vehicle-image'].complete && dom['vehicle-image'].naturalWidth > 0")
        srv = hud_state("SCARAB")
        srv["vehicle"]["surface"] = "SCARAB"
        self.render(page, hud_snapshot(srv))
        self.assertEqual(page.evaluate(read)["src"], "/ship-art/SRV%20Scarab.png")
        self.assertEqual(page.evaluate(read)["name"], "", "an SRV has no ship name")
        self.render(page, hud_snapshot(hud_state("ONFOOT")))
        self.assertEqual(page.evaluate(read)["src"], "/ship-art/Commander%20On%20Foot.png")
        unknown = hud_state("SUPERCRUISE")
        unknown["vehicle"] = {"ship_symbol": "not_a_ship", "ship_type": "", "ship_name": ""}
        self.render(page, hud_snapshot(unknown))
        self.assertEqual(page.evaluate(read)["src"], "")
        self.assertTrue(page.evaluate(read)["empty"])


if __name__ == "__main__":
    unittest.main()
