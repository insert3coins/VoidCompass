"""5.5.2.3 Deep Space Contacts: rebuilt from the journal alone. Events here
are shaped like real ones from the commander's journals."""

from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit

from voidcompass.exploration.contact_scope import ContactLedger, classify

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
HOME, ELSEWHERE = 2862352402891, 5411121679880


def signal(name, kind, address=HOME, at="2026-10-04T10:00:00Z", **extra):
    return {"timestamp": at, "event": "FSSSignalDiscovered", "SystemAddress": address, "SignalName": name, "SignalType": kind, **extra}


def jump(address=HOME, name="Ega", at="2026-10-04T10:00:00Z", event="FSDJump", **extra):
    return {"timestamp": at, "event": event, "StarSystem": name, "SystemAddress": address, **extra}


def honk(non_body, address=HOME):
    return {"timestamp": "2026-10-04T10:00:30Z", "event": "FSSDiscoveryScan", "Progress": 0.4, "BodyCount": 9,
            "NonBodyCount": non_body, "SystemAddress": address, "SystemName": "Ega"}


def feed(ledger, *events):
    for raw in events:
        ledger.observe(raw["event"], raw)
    return ledger


class ClassifyTests(unittest.TestCase):
    def test_signal_types(self):
        self.assertEqual(classify(signal("HEART OF GOLD V4J-T6M", "FleetCarrier", IsStation=True))["kind"], "carrier",
                         "carriers are not stations")
        self.assertEqual(classify(signal("HEART OF GOLD V4J-T6M", "FleetCarrier"))["detail"], "V4J-T6M")
        self.assertEqual(classify(signal("SPACEZILLA | 2739", "SquadronCarrier", IsStation=True))["detail"], "2739")
        self.assertEqual(classify(signal("Monzon Vision", "StationONeilOrbis", IsStation=True))["label"], "Orbis starport")
        self.assertEqual(classify(signal("VEG-384 Demeter-class Cropper", "Megaship"))["kind"], "megaship")
        nav = classify(signal("$MULTIPLAYER_SCENARIO42_TITLE;", "NavBeacon", SignalName_Localised="Nav Beacon"))
        self.assertEqual((nav["kind"], nav["name"]), ("beacon", "Nav Beacon"))
        cz = classify(signal("$Warzone_PointRace_Low:#index=3;", "Combat", SignalName_Localised="Conflict Zone [Low Intensity]"))
        self.assertEqual((cz["kind"], cz["name"]), ("combat", "Conflict Zone [Low Intensity]"))
        self.assertEqual(classify(signal("$Fixed_Event_Life_Cloud;", "Codex", SignalName_Localised="Notable stellar phenomena"))["kind"], "phenomena")
        uss = classify(signal("$USS_HighGradeEmissions;", "USS", SignalName_Localised="Unidentified signal source",
                              USSType="$USS_Type_VeryValuableSalvage;", USSType_Localised="High grade emissions", ThreatLevel=0))
        self.assertEqual((uss["kind"], uss["name"]), ("uss", "High grade emissions"))
        self.assertEqual(classify(signal("Odd thing", "SomethingNew"))["kind"], "signal")


class LedgerTests(unittest.TestCase):
    def test_signals_logged_before_the_arrival_are_kept(self):
        ledger = feed(ContactLedger(), jump(ELSEWHERE, "Sol"))
        # The game logs Ega's stations and carriers just before its FSDJump.
        feed(ledger, signal("Vernadsky Hub", "StationCoriolis", IsStation=True),
             signal("HEART OF GOLD V4J-T6M", "FleetCarrier", IsStation=True))
        self.assertEqual(ledger.model(now=0)["system"] if ledger.model(now=0) else None, None,
                         "nothing shown for Sol, which has no signals of its own")
        feed(ledger, jump())
        model = ledger.model(now=0)
        self.assertEqual(model["system"], "Ega")
        self.assertEqual(model["named"], 2)
        self.assertEqual([row["name"] for row in model["rows"]], ["Vernadsky Hub"])
        self.assertEqual(model["carriers"]["names"], ["HEART OF GOLD V4J-T6M"])

    def test_relogged_signals_count_once_and_a_jump_starts_over(self):
        ledger = feed(ContactLedger(), jump(), *[signal("Liman Terminal", "Installation")] * 3,
                      signal("$Warzone_PointRace_Low:#index=3;", "Combat", SignalName_Localised="Conflict Zone [Low Intensity]"),
                      signal("$Warzone_PointRace_Low:#index=4;", "Combat", SignalName_Localised="Conflict Zone [Low Intensity]"))
        self.assertEqual(ledger.model(now=0)["named"], 3, "two zones of the same intensity are two contacts")
        feed(ledger, jump(ELSEWHERE, "Sol", at="2026-10-04T11:00:00Z"))
        self.assertIsNone(ledger.model(now=0))

    def test_same_system_relog_keeps_contacts(self):
        ledger = feed(ContactLedger(), jump(), signal("Liman Terminal", "Installation"))
        feed(ledger, jump(event="Location"))
        self.assertEqual(ledger.model(now=0)["named"], 1)

    def test_someone_elses_carrier_jump_is_not_ours(self):
        ledger = feed(ContactLedger(), jump(), signal("Liman Terminal", "Installation"))
        self.assertFalse(ledger.observe("CarrierJump", jump(ELSEWHERE, "Sol", event="CarrierJump", Docked=False)))
        self.assertEqual(ledger.model(now=0)["system"], "Ega")
        self.assertTrue(ledger.observe("CarrierJump", jump(ELSEWHERE, "Sol", event="CarrierJump", Docked=True)))
        self.assertIsNone(ledger.model(now=0))

    def test_honk_count_shows_what_the_fss_has_still_to_resolve(self):
        ledger = feed(ContactLedger(), jump(), honk(5), signal("HEART OF GOLD V4J-T6M", "FleetCarrier", IsStation=True),
                      signal("$MULTIPLAYER_SCENARIO42_TITLE;", "NavBeacon", SignalName_Localised="Nav Beacon"))
        model = ledger.model(now=0)
        self.assertEqual((model["expected"], model["named"], model["unresolved"], model["honked"]), (5, 2, 3, True))
        # A carrier arriving after the honk never makes the count negative.
        feed(ledger, *[signal(f"FC {i} ABC-{i:03d}", "FleetCarrier", IsStation=True) for i in range(6)])
        self.assertEqual(ledger.model(now=0)["unresolved"], 0)
        empty = feed(ContactLedger(), jump(), honk(0)).model(now=0)
        self.assertIsNone(empty, "a honk with no signals shows nothing")
        deep = feed(ContactLedger(), jump(), honk(4)).model(now=0)
        self.assertEqual((deep["named"], deep["unresolved"]), (0, 4), "signals the FSS has not resolved yet")

    def test_a_finished_body_scan_says_the_signals_need_the_fss(self):
        # Slatchio TU-W d2-2: 31 bodies, 9 signals, none named by the game.
        ledger = feed(ContactLedger(), jump(), honk(9))
        self.assertFalse(ledger.model(now=0)["bodies_done"])
        self.assertTrue(ledger.observe("FSSAllBodiesFound", {"event": "FSSAllBodiesFound", "SystemAddress": HOME, "Count": 31}))
        model = ledger.model(now=0)
        self.assertEqual((model["bodies_done"], model["named"], model["unresolved"]), (True, 0, 9))

    def test_uss_expire_and_carry_threat(self):
        start = "2026-10-04T10:00:00Z"
        ledger = feed(ContactLedger(), jump(), signal("$USS_DegradedEmissions;", "USS", at=start, USSType="$USS_Type_Salvage;",
                                                      USSType_Localised="Degraded emissions", ThreatLevel=0, TimeRemaining=600),
                      signal("$USS_Combat;", "USS", at=start, USSType="$USS_Type_Aftermath;", USSType_Localised="Combat aftermath",
                             ThreatLevel=3, TimeRemaining=1200))
        t0 = 1_791_108_000  # 2026-10-04T10:00:00Z
        model = ledger.model(now=t0 + 60)
        self.assertEqual(model["threat"], 3)
        self.assertEqual(model["rows"][0]["name"], "Combat aftermath", "the threat sorts first")
        self.assertEqual(model["timed"], 2)
        self.assertEqual(ledger.model(now=t0 + 900)["named"], 1, "the 10 minute one is gone")
        self.assertIsNone(ledger.model(now=t0 + 1300), "both gone from the game: nothing to show")

    def test_busy_systems_list_carriers_as_one_line(self):
        ledger = feed(ContactLedger(), jump(), *[signal(f"FC {i} ABC-{i:03d}", "FleetCarrier", IsStation=True) for i in range(30)],
                      *[signal(f"Base {i}", "Installation") for i in range(20)])
        model = ledger.model(now=0, max_rows=14)
        self.assertEqual((len(model["rows"]), model["more"]), (14, 6))
        self.assertEqual((model["carriers"]["count"], len(model["carriers"]["names"]), model["carriers"]["more"]), (30, 6, 24))
        self.assertEqual({group["kind"]: group["count"] for group in model["groups"]}, {"installation": 20, "carrier": 30})
        self.assertEqual(model["groups"][0]["name"], "INSTALLATIONS")


class MergeTests(unittest.TestCase):
    def test_alike_contacts_share_a_row_but_uss_do_not(self):
        zones = [signal(f"$Warzone_Powerplay_Med:#index={i};", "Combat", SignalName_Localised="Power Conflict Zone [Medium Intensity]")
                 for i in range(12)]
        uss = [signal("$USS_DegradedEmissions;", "USS", USSType_Localised="Degraded emissions", TimeRemaining=900,
                      at=f"2099-01-01T00:0{i}:00Z") for i in range(2)]
        model = feed(ContactLedger(), jump(), *zones, *uss).model(now=0)
        self.assertEqual(model["named"], 14)
        zone = next(row for row in model["rows"] if row["kind"] == "combat")
        self.assertEqual(zone["count"], 12)
        self.assertEqual(sum(1 for row in model["rows"] if row["kind"] == "uss"), 2)


class OverlayPageTests(unittest.TestCase):
    def test_page_follows_the_theme_and_never_clips_itself(self):
        css = (WEB / "contact_scope" / "styles.css").read_text(encoding="utf-8")
        rules = css.split("}", 1)[1]
        self.assertNotRegex(rules, r"#[0-9a-fA-F]{6}")
        self.assertIsNone(re.search(r"\.scope \{[^}]*clip-path", css), "clipping the page root paints grey corners")
        self.assertNotIn("<style", (WEB / "contact_scope" / "index.html").read_text(encoding="utf-8"))

    def test_renders_in_a_browser(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Playwright is not installed")
        ledger = feed(ContactLedger(), jump(), honk(6),
                      signal("Vernadsky Hub", "StationCoriolis", IsStation=True),
                      signal("$Warzone_PointRace_High:#index=1;", "Combat", SignalName_Localised="Conflict Zone [High Intensity]"),
                      signal("HEART OF GOLD V4J-T6M", "FleetCarrier", IsStation=True),
                      signal("$USS_Combat;", "USS", at="2099-01-01T00:00:00Z", USSType_Localised="Combat aftermath",
                             ThreatLevel=2, TimeRemaining=900))
        model = ledger.model(now=0)
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as exc:
                self.skipTest(f"Playwright Chromium is unavailable: {exc}")
            page = browser.new_page(viewport={"width": 420, "height": 300})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def serve(route, _request=None):
                path = WEB / urlsplit(route.request.url).path.lstrip("/")
                if path.name == "overlay-client.js":
                    route.fulfill(content_type="application/javascript", body=path.read_text(encoding="utf-8")
                                  + "\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: o => {"
                                  " window.__render = o.render; window.__height = o.contentHeight; }};")
                elif path.is_file():
                    route.fulfill(path=str(path))
                else:
                    route.fulfill(status=404, body="")

            page.route("http://scope.test/**", serve)
            page.goto("http://scope.test/contact_scope/index.html")
            page.wait_for_selector("#scope", state="attached")
            page.evaluate("m => __render({contacts: m, theme: {}, effects: {reduced_motion: true}})", model)
            self.assertEqual(page.locator("#system-name").inner_text(), "EGA")
            self.assertEqual(page.locator("#scope-tag").inner_text(), "THREAT 2")
            self.assertIn("4 NAMED · 2 TO RESOLVE IN THE FSS", page.locator("#resolution-text").inner_text())
            self.assertEqual(page.locator(".row").count(), 3)
            self.assertEqual(page.locator(".row").first.locator(".name").inner_text(), "Combat aftermath")
            self.assertIn("1 CARRIER", page.locator("#carriers-count").inner_text())
            self.assertEqual(" ".join(page.locator(".group.kind-station").inner_text().split()), "1 STATION")
            self.assertGreater(page.evaluate("__height()"), 100)
            page.evaluate("() => __render({contacts: null, theme: {}, effects: {}})")
            self.assertIn("empty", page.locator("#scope").get_attribute("class"))
            browser.close()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
