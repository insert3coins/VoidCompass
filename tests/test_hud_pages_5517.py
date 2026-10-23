"""5.5.17: one overlay for everything. With pages on, the Navigation HUD's
lower half changes with what you're doing, built from the same facts as the
separate overlays, which can stay off while the HUD shows them."""

from pathlib import Path
import time
import unittest
from unittest.mock import Mock

from tests.test_navigation_state_visuals import NavigationStatusPlateBrowserTests, hud_snapshot, hud_state
from voidcompass.core import config as config_module
from voidcompass.core.application_runtime import ApplicationRuntime
from voidcompass.core.overlay_registry import OVERLAY_HOTKEY_SPECS
from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.dashboard.dashboard_hud_pages_mixin import DashboardHudPagesMixin
from voidcompass.overlays import hud_pages as hp
from voidcompass.overlays.hud import TacticalHUD
from voidcompass.overlays.rig_tracker import hold_row

ROOT = Path(__file__).resolve().parents[1]
ALL = list(hp.PAGES)


class OptionTests(unittest.TestCase):
    def test_off_until_switched_on(self):
        options = hp.pages_options({})
        self.assertEqual((options["mode"], options["takeover"]), ("off", True))
        self.assertEqual(hp.pages_options({"hud_pages": "manual"})["mode"], "manual")
        self.assertEqual(hp.covered_overlays({"hud_pages": "manual"}), hp.covered_overlays({"hud_pages": "auto"}))
        self.assertEqual(options["enabled"], ALL)
        self.assertNotIn("mining", hp.pages_options({"hud_page_mining": False})["enabled"])

    def test_the_overlays_it_covers_stay_off_while_on(self):
        self.assertEqual(hp.covered_overlays({}), set())
        covered = hp.covered_overlays({"hud_pages": "auto"})
        self.assertTrue({"rig_tracker_hud", "prospector_hud", "station_info_hud", "jump_info_hud", "ground_popup"} <= covered)
        self.assertNotIn("galaxy_minimap_hud", covered, "the minimap and music stay their own")
        self.assertNotIn("music_player_hud", covered)
        self.assertEqual(hp.covered_overlays({"hud_pages": "auto", "hud_pages_takeover": False}), set())
        self.assertNotIn("rig_tracker_hud", hp.covered_overlays({"hud_pages": "auto", "hud_page_rhino": False}))

    def test_settings_saved_per_commander_and_in_studio(self):
        for key in ("hud_pages", "hud_pages_takeover", *(f"hud_page_{page}" for page in ALL[1:]),
                    "overlay_hotkey_hud_page_next", "overlay_hotkey_hud_pages_mode"):
            self.assertIn(key, config_module.PROFILE_SETTINGS)
        page = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = page.split('<section data-studio-settings="hud">', 1)[1].split("</section>", 1)[0]
        for marker in ('data-studio-setting="hud_pages"', '<option value="manual">',
                       'data-overlay-option="hud_pages_takeover"', 'data-overlay-option="hud_page_combat"'):
            self.assertIn(marker, section)
        self.assertNotIn("Compact layout", section, "one layout now, sized to its content")
        actions = {spec[0] for spec in OVERLAY_HOTKEY_SPECS}
        self.assertTrue({"hud_page_next", "hud_pages_mode"} <= actions)
        self.assertFalse({"hud_page_auto", "hud_pages_toggle", "navigation_layout"} & actions, "two page keys, no more")


class PickTests(unittest.TestCase):
    def pick(self, motion, category="flight", **facts):
        return hp.pick_page({"motion": motion, "category": category}, facts, ALL)

    def test_the_page_follows_what_you_do(self):
        self.assertEqual(self.pick("supercruise"), "nav")
        self.assertEqual(self.pick("fsd_charge", "drive", has_jump=True), "jump")
        self.assertEqual(self.pick("scanner", "scan"), "survey")
        self.assertEqual(self.pick("glide", "planet"), "planet")
        self.assertEqual(self.pick("surface_vehicle", "vehicle", on_planet=True, in_rhino=True), "rhino")
        self.assertEqual(self.pick("surface_vehicle", "vehicle", on_planet=True), "planet")
        self.assertEqual(self.pick("asteroid_field", "restrict"), "mining")
        self.assertEqual(self.pick("flight", prospecting=True), "mining")
        self.assertEqual(self.pick("combat", "alert"), "combat")
        self.assertEqual(self.pick("docked", "dock", docked=True), "station")
        self.assertEqual(self.pick("docked", "dock", docked=True, at_colony=True), "colony")
        self.assertEqual(self.pick("docked", "dock", docked=True, on_own_carrier=True), "carrier")
        self.assertEqual(self.pick("supercruise", trading=True), "trade")

    def test_only_pages_switched_on_and_with_something_to_show(self):
        self.assertEqual(hp.pick_page({"motion": "combat"}, {}, [page for page in ALL if page != "combat"]), "nav")
        self.assertEqual(self.pick("fsd_charge", "drive", has_jump=False), "nav")

    def test_the_page_hotkey_goes_round_and_back(self):
        available = ["nav", "survey", "planet", "mining"]
        self.assertEqual(hp.next_page("planet", "planet", available), "mining")
        self.assertEqual(hp.next_page("mining", "planet", available), "nav")
        self.assertEqual(hp.next_page("survey", "planet", available), "planet", "round to the automatic page")


class BuilderTests(unittest.TestCase):
    def blocks(self, page):
        return [block["type"] for block in page["blocks"]]

    def test_jump(self):
        page = hp.jump_page({"phase": "charging", "system": "Colonia", "star": {"label": "SCOOPABLE", "tone": "green"},
                             "route": {"hop": 2, "hops": 5, "remaining": 3, "jump_ly": 48.2, "total_ly": 190.0, "destination": "Colonia"},
                             "lines": [{"tone": "text", "items": [{"label": "TRAFFIC 24H", "value": "3"}]}]})
        self.assertEqual((page["title"], page["blocks"][0]["value"], page["tone"]), ("FRAME SHIFT CHARGING", "48.2 LY", "green"))
        self.assertEqual(self.blocks(page), ["hero", "stats", "list"])
        self.assertIsNone(hp.jump_page(None))

    def test_rhino(self):
        model = {"slots": [{"slot": 1, "tracked": True, "distance_m": 85.0, "relative": 30, "here": False, "nearest": True},
                           {"slot": 2, "tracked": True, "distance_m": 12.0, "here": True}, {"slot": 3, "tracked": False}],
                 "order": [1]}
        page = hp.rhino_page(model, [hold_row("RHINO", 72, 72)], signals=2)
        dials = page["blocks"][0]["items"]
        self.assertEqual([dial["state"] for dial in dials], ["next", "here", "empty"])
        block = lambda kind: next(item for item in page["blocks"] if item["type"] == kind)
        self.assertEqual(block("bars")["items"][0]["tone"], "red", "a full hold")
        self.assertIn(("COLLECT NEXT", "RIG 1"), [(item["label"], item["value"]) for item in block("stats")["items"]])
        self.assertIn("TOO CLOSE TO RIG 2", block("note")["text"], "rig 2 is 12 m off: no room for another")

    def test_mining(self):
        page = hp.mining_page({"content_label": "HIGH CONTENT", "content_tone": "green", "remaining": 100.0, "core_material": "",
                               "materials": [{"name": "Platinum", "proportion": 30.0}], "refined": [{"name": "Platinum", "tonnes": 4}]},
                              {"total": 10, "capacity": 64, "free": 54, "capacity_known": True})
        self.assertEqual(self.blocks(page), ["hero", "bars", "bars", "stats"])
        self.assertIsNone(hp.mining_page(None, None))

    def test_combat(self):
        page = hp.combat_page({"ship": "Python", "pilot": "Kai", "rank": "Elite", "legal_status": "Wanted", "bounty": 400000,
                               "shields": 50.0, "hull": 75.0}, {"active": True, "kills": 3, "bounty_cr": 900000}, None)
        self.assertEqual(page["blocks"][0]["tone"], "red")
        self.assertEqual([item["label"] for item in page["blocks"][1]["items"]], ["SHIELDS", "HULL"])
        self.assertIsNone(hp.combat_page(None, None, None))

    def test_planet_station_colony_carrier_trade_powerplay(self):
        planet = hp.planet_page("X 1", {"short_body": "1", "details": {"gravity": 4.2}}, {"state": "OK", "label": "Vein", "distance_m": 2500,
                                "heading_delta": 20, "direction": "RIGHT 20°"}, None, None, 3.0)
        self.assertEqual((planet["tone"], planet["blocks"][1]["type"], planet["blocks"][1]["distance"]), ("red", "compass", "2.5 KM"))
        station = hp.station_page({"station": "Jameson Memorial", "pads": "L 8", "type": "ORBIS", "core_services": [{"label": "Refuel", "available": True}]})
        self.assertEqual(station["blocks"][0]["title"], "Jameson Memorial")
        colony = hp.colony_page({"header": "Site", "remaining": 900, "trips": 4, "groups": [{"rows": [{"name": "Steel", "need": 500, "ship": 100}]}]})
        self.assertEqual(colony["blocks"][1]["items"][0]["ratio"], .2)
        carrier = hp.carrier_page({"name": "Void Ark", "callsign": "X9Z-1TT", "fuel": 500.0, "fuel_capacity": 1000.0, "fuel_ratio": .5})
        self.assertEqual(carrier["blocks"][0]["value"], "X9Z-1TT")
        trade = hp.trade_page({"done": False, "hop": 1, "hops": 3, "phase": "buy", "action": "Buy 720 t Gold", "station": "A",
                               "system": "B", "distance": 12.0, "expected": 2_000_000, "profit": 0, "warnings": []})
        self.assertEqual(trade["blocks"][0]["value"], "2.0 M CR")
        self.assertIsNone(hp.powerplay_page({"active": False}))

    def test_lists_show_it_all_as_the_hud_grows(self):
        facts = [{"label": f"FACT {n}", "value": str(n)} for n in range(8)]
        page = hp.jump_page({"phase": "charging", "system": "X", "route": {}, "lines": [{"tone": "text", "items": facts}]})
        listing = next(block for block in page["blocks"] if block["type"] == "list")
        self.assertEqual((len(listing["items"]), listing["more"]), (8, 0), "no +4 MORE: the HUD grows to fit")
        crowded = hp.listing([(f"ROW {n}", "", "", "text") for n in range(14)])
        self.assertEqual((len(crowded["items"]), crowded["more"]), (hp.LIST_ROWS, 14 - hp.LIST_ROWS))

    def test_empty_blocks_are_left_out(self):
        page = hp.station_page({"station": "S", "authority": ""})
        self.assertEqual(self.blocks(page), ["hero"], "no empty note, no empty service list")


class HudTests(unittest.TestCase):
    def test_the_hud_carries_the_page_and_grows_to_fit(self):
        root = ApplicationRuntime()
        try:
            hud = TacticalHUD(root, {"hud_pages": "auto", "hud_compact_mode": False})
            try:
                self.assertEqual(hud._target_dimensions(), (500, 326), "compact is the only layout")
                server = Mock()
                server.rendered_content_height.return_value = 410
                hud._html_bridge = Mock(runtime=Mock(server=server))
                self.assertEqual(hud._target_dimensions(), (500, 410), "the window follows the page's height")
                server.rendered_content_height.return_value = 9999
                self.assertEqual(hud._target_dimensions()[1], TacticalHUD.MAX_DESIGN_HEIGHT)
                server.rendered_content_height.return_value = 200
                self.assertEqual(hud._target_dimensions()[1], 326, "never smaller than designed")
                hud._html_bridge = None
                for labels, width in (("large", 540), ("larger", 580)):
                    hud.config["hud_label_size"] = labels
                    self.assertEqual(hud._target_dimensions(), (width, 326), "larger small text gets a wider plate")
                hud.config["hud_text_scale_percent"] = 150
                self.assertEqual(hud._target_dimensions(), (870, 489), "and the text size scales it all")
                hud.config.update(hud_label_size="standard", hud_text_scale_percent=0)
                hud.update("SOL", "", 0, 0, 0, None, {})
                self.assertTrue(hud.set_pages({"active": "nav", "page": None}))
                self.assertFalse(hud.set_pages({"active": "nav", "page": None}), "the same page twice is no change")
                self.assertEqual(hud._html_last_model["pages"]["active"], "nav")
            finally:
                hud.win.destroy()
        finally:
            root.close()


class Deck(DashboardHudPagesMixin):
    _overlay_enabled = MainDashboard._overlay_enabled

    def __init__(self, config=None):
        self.config = {"overlay_enabled": True, **(config or {})}
        self.current_in_srv = False


class DeckTests(unittest.TestCase):
    def test_covered_overlays_stay_off_and_keep_their_setting(self):
        deck = Deck({"cargo_overlay_enabled": True, "hud_pages": "auto"})
        self.assertFalse(deck._overlay_enabled("cargo_hud"))
        self.assertTrue(deck._overlay_enabled("hud"))
        deck.config["hud_pages"] = "off"
        self.assertTrue(deck._overlay_enabled("cargo_hud"))
        deck.config.update(hud_pages="auto", overlay_enabled=False)
        self.assertTrue(deck._overlay_enabled("cargo_hud"), "with the HUD off there's nothing to cover for")

    def test_target_and_prospect_from_the_journal(self):
        deck = Deck()
        deck._hud_pages_observe("ShipTargeted", {"TargetLocked": True, "Ship": "python", "ScanStage": 0})
        deck._hud_pages_observe("ShipTargeted", {"TargetLocked": True, "Ship": "python", "ScanStage": 3, "PilotName_Localised": "Kai",
                                                 "ShieldHealth": 40.5, "HullHealth": 90, "Bounty": 1200, "LegalStatus": "Wanted"})
        self.assertEqual({key: deck._hud_target.get(key) for key in ("ship", "pilot", "shields", "hull", "bounty", "legal_status")},
                         {"ship": "Python", "pilot": "Kai", "shields": 40.5, "hull": 90.0, "bounty": 1200.0, "legal_status": "Wanted"})
        deck._hud_pages_observe("ShipTargeted", {"TargetLocked": False})
        self.assertIsNone(deck._hud_target)
        deck._hud_pages_observe("ProspectedAsteroid", {"Materials": [], "Content": "$AsteroidMaterialContent_High;"})
        deck._hud_pages_observe("MiningRefined", {"Type_Localised": "Platinum"})
        self.assertEqual(deck._hud_prospect["refined"], {"Platinum": 1})
        deck._hud_pages_observe("ShipTargeted", {"TargetLocked": True, "Ship": "eagle"}, startup_replay=True)
        self.assertIsNone(deck._hud_target, "nothing from the startup replay")


class HotkeyTests(unittest.TestCase):
    """Two page keys: the mode (auto, following you, or manual), and the next
    page. Each says what it did on the HUD itself."""

    def deck(self, mode="off"):
        deck = Deck({"hud_pages": mode})
        deck.flashes, deck.feed = [], []
        deck.hud = Mock()
        deck.hud._html_last_model = {"state": {"motion": "supercruise", "category": "drive"}}
        deck.hud.flash = lambda text, detail="", tone="accent": deck.flashes.append((text, detail))
        deck._persist_config = lambda: None
        deck._hud_pages_apply_settings = lambda: None
        deck._schedule_html_dashboard_publish = lambda **_kwargs: None
        deck.add_event_feed_entry = lambda *args, **kwargs: deck.feed.append(args)
        deck._hud_pages_facts = lambda: {"docked": False}
        deck._hud_pages_available = lambda facts: ["nav", "survey", "planet"]
        deck._tick_hud_pages = lambda reschedule=True: None
        deck._hud_page_build = lambda page: {"id": page, "blocks": []}
        return deck

    def test_the_tabs_show_every_page_in_the_round(self):
        deck = self.deck("manual")
        deck._hud_pages_manual = "combat"
        deck.config["hud_page_powerplay"] = False
        payload = deck._hud_pages_payload()
        self.assertEqual([tab["id"] for tab in payload["tabs"]], [page for page in hp.PAGES if page != "powerplay"],
                         "every page switched on, in the page key's order")
        empty = {tab["id"] for tab in payload["tabs"] if tab["empty"]}
        self.assertNotIn("survey", empty)
        self.assertIn("combat", empty, "nothing on it now: a dim pip (the HUD still names the page you're on)")

    def test_a_tip_once_while_the_pages_are_off(self):
        from voidcompass.dashboard import dashboard_hud_pages_mixin as mixin
        deck = self.deck("off")
        deck.toast_hud = Mock()
        self.assertFalse(deck._hud_pages_tip(), "the clock starts")
        self.assertFalse(deck._hud_pages_tip(), "not straight away")
        deck._hud_pages_tip_clock -= mixin.TIP_DELAY_S + 1
        self.assertTrue(deck._hud_pages_tip())
        self.assertIn("Overlay Studio › Navigation HUD › Pages", deck.toast_hud.push.call_args.args[1])
        self.assertTrue(deck.config["hud_pages_tip_shown"])
        self.assertFalse(deck._hud_pages_tip(), "only once")
        self.assertIn("hud_pages_tip_shown", config_module.PROFILE_SETTINGS)
        other = self.deck("auto")
        other.toast_hud = Mock()
        other._hud_pages_tip_clock = time.monotonic() - mixin.TIP_DELAY_S - 1
        self.assertFalse(other._hud_pages_tip(), "no tip when they're already on")

    def test_the_mode_key_goes_between_auto_and_manual(self):
        deck = self.deck()
        self.assertTrue(deck._hud_pages_mode_key())
        self.assertEqual(deck.config["hud_pages"], "auto", "off: on, following you")
        self.assertEqual(deck.flashes[-1], ("PAGES · AUTO", "FOLLOWING YOU · NAV"))
        deck._hud_pages_mode_key()
        self.assertEqual(deck.config["hud_pages"], "manual")
        self.assertEqual(deck.flashes[-1][0], "PAGES · MANUAL")
        deck._hud_pages_mode_key()
        self.assertEqual(deck.config["hud_pages"], "auto")

    def test_next_page_chooses_and_stays(self):
        deck = self.deck("auto")
        deck._hud_page_next()
        self.assertEqual(deck.config["hud_pages"], "manual", "choosing a page is manual")
        self.assertEqual(deck.flashes[-1], ("PAGE · JUMP", "MANUAL"))
        # Round every page switched on, with or without something on it now.
        for _ in range(len(hp.PAGES) - 1):
            deck._hud_page_next()
        self.assertEqual([text.split(" · ")[1] for text, _detail in deck.flashes],
                         [hp.LABELS[page] for page in hp.PAGES[1:]] + ["NAV"])
        self.assertEqual(deck._hud_pages_payload()["active"], "nav")
        deck.config["hud_page_combat"] = False
        for _ in range(len(hp.PAGES)):
            deck._hud_page_next()
        self.assertNotIn("PAGE · COMBAT", [text for text, _detail in deck.flashes[-len(hp.PAGES):]],
                         "a page switched off is skipped")

    def test_a_chosen_page_with_nothing_on_it_says_so(self):
        deck = self.deck("manual")
        deck._hud_page_build = lambda page: None
        deck._hud_pages_manual = "combat"
        payload = deck._hud_pages_payload()
        self.assertEqual((payload["active"], payload["mode"]), ("combat", "manual"))
        self.assertEqual(payload["page"]["blocks"][0]["text"], "TARGET A SHIP TO FILL IT")


class PageRenderTests(unittest.TestCase):
    """The page in the HUD: over the route and survey, and never cut off."""

    setUpClass = classmethod(NavigationStatusPlateBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(NavigationStatusPlateBrowserTests.tearDownClass.__func__)
    open = NavigationStatusPlateBrowserTests.open
    render = NavigationStatusPlateBrowserTests.render

    def page_snapshot(self, page, active="rhino", mode="auto"):
        snapshot = hud_snapshot(hud_state("RHINO"))
        snapshot["pages"] = {"active": active, "auto": active, "mode": mode,
                             "tabs": [{"id": "nav", "label": "NAV"}, {"id": "rhino", "label": "RHINO"}], "page": page}
        return snapshot

    def rhino(self):
        model = {"slots": [{"slot": n, "tracked": n < 4, "distance_m": 40.0 * n, "relative": 30 * n, "here": n == 2} for n in range(1, 7)],
                 "order": [1, 3]}
        return hp.rhino_page(model, [hold_row("RHINO", 23, 72), hold_row("SHIP", 160, 256)], signals=4)

    def test_a_page_takes_the_route_and_survey_rows(self):
        page = self.open()
        self.render(page, self.page_snapshot(self.rhino()))
        state = page.evaluate("""() => ({paged: dom.hud.classList.contains('paged'), panel: !dom['page-panel'].hidden,
          route: getComputedStyle(dom['route-block']).display, dials: document.querySelectorAll('.pg-dial').length,
          next: document.querySelectorAll('.pg-dial.next').length, tab: document.querySelector('.page-tabs i.on').textContent,
          over: dom['page-body'].scrollHeight - dom['page-body'].clientHeight})""")
        self.assertEqual(state, {"paged": True, "panel": True, "route": "none", "dials": 6, "next": 1, "tab": "RHINO", "over": 0})
        self.render(page, self.page_snapshot(None, active="nav"))
        self.assertTrue(page.evaluate("dom['page-panel'].hidden && getComputedStyle(dom['route-block']).display !== 'none'"))

    def test_too_much_for_the_page_drops_from_the_end(self):
        page = self.open()
        crowded = hp._page("survey", "SYSTEM SURVEY", hp.hero("SURVEY", "7 / 16"),
                           hp.listing([(f"Body {n}", "", "1 CR", "text") for n in range(40)], rows=40), hp.note("LAST", "dim"))
        self.render(page, self.page_snapshot(crowded, active="survey"))
        result = page.evaluate("""() => ({over: dom['page-body'].scrollHeight - dom['page-body'].clientHeight,
          rows: [...document.querySelectorAll('.pg-list li')].filter((li) => !li.hidden).length,
          note: !document.querySelector('.pg-note') || document.querySelector('.pg-note').hidden})""")
        self.assertLessEqual(result["over"], 1)
        self.assertTrue(0 < result["rows"] < 40)
        self.assertTrue(result["note"], "the last block goes first")

    def test_a_page_key_flashes_on_the_hud(self):
        page = self.open()
        snapshot = self.page_snapshot(self.rhino())
        snapshot["flash"] = {"seq": 1, "text": "PAGES ON", "detail": "FOLLOWING YOU · RHINO", "tone": "green",
                             "duration": 2.6, "at": time.time()}
        self.render(page, snapshot)
        self.assertEqual(page.inner_text("#event-notice"), "PAGES ON · FOLLOWING YOU · RHINO")
        self.assertTrue(page.evaluate("dom['event-notice'].classList.contains('showing')"))
        snapshot["flash"] = {**snapshot["flash"], "seq": 2, "at": time.time() - 60}
        page.evaluate("dom['event-notice'].classList.remove('showing')")
        self.render(page, snapshot)
        self.assertFalse(page.evaluate("dom['event-notice'].classList.contains('showing')"), "an old one isn't shown again")

    def test_the_hud_says_how_tall_it_needs_to_be(self):
        page = self.open()
        self.render(page, self.page_snapshot(None, active="nav"))
        self.assertEqual(page.evaluate("designHeight()"), 326, "the classic HUD at its designed height")
        planet = hp.planet_page("X 1", {"short_body": "1", "details": {"gravity": .3},
                                        "materials": [{"name": f"Mat {n}", "percent": 10.0} for n in range(4)]},
                                {"state": "OK", "label": "Vein", "distance_m": 900, "heading_delta": 10, "direction": "RIGHT"},
                                {"species": "Bacterium", "progress": 1, "colony_m": 500, "clear": False, "min_distance_m": 90}, .3, 3.0)
        self.render(page, self.page_snapshot(planet, active="planet"))
        self.assertGreater(page.evaluate("designHeight()"), 326, "a fuller page grows it")
        # 5.5.18: icons, not words: a circling arrow for auto, a pin for manual.
        mode = "() => [dom['page-mode'].dataset.mode, !!dom['page-mode'].querySelector('svg'), dom['page-mode'].textContent]"
        self.assertEqual(page.evaluate(mode), ["auto", True, ""])
        self.render(page, self.page_snapshot(planet, active="planet", mode="manual"))
        self.assertEqual(page.evaluate(mode), ["manual", True, ""])
        self.assertTrue(page.evaluate("dom['page-mode'].classList.contains('pinned')"))


if __name__ == "__main__":
    unittest.main()
