import json
import os
import tempfile
import unittest

from voidcompass.exploration.expedition_manager import ExpeditionManager, OBJECTIVE_TEMPLATES


class ExpeditionManagerTests(unittest.TestCase):
    def test_long_campaign_templates_extend_goals_without_losing_progress(self):
        self.assertEqual(len(OBJECTIVE_TEMPLATES), 13)
        self.assertEqual(OBJECTIVE_TEMPLATES["galactic_circumnavigation"]["tier"], "Epic")

        with tempfile.TemporaryDirectory() as folder:
            manager = ExpeditionManager(os.path.join(folder, "expeditions.json"))
            expedition = manager.create("Long Survey", start_system="Sol")
            manager.apply_objective_template(expedition["id"], "deep_survey")
            manager.observe_event({
                "event": "FSSAllBodiesFound", "SystemName": "Alpha", "Count": 4,
            }, event_uid="campaign-fss-1")
            manager.observe_event({
                "event": "FSSAllBodiesFound", "SystemName": "Beta", "Count": 6,
            }, event_uid="campaign-fss-2")

            before = next(
                row for row in manager.active()["objectives"]
                if row["kind"] == "fss_system"
            )
            self.assertEqual((before["progress"], before["count"]), (2, 20))

            affected = manager.apply_objective_template(
                expedition["id"], "long_range_cartography",
            )
            after = next(
                row for row in manager.active()["objectives"]
                if row["kind"] == "fss_system"
            )
            self.assertEqual(len(affected), 5)
            self.assertEqual(after["id"], before["id"])
            self.assertEqual((after["progress"], after["count"]), (2, 200))
            self.assertEqual(after["template_tier"], "Extended")

    def test_sector_campaign_tracks_generic_recon_systems(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = ExpeditionManager(os.path.join(folder, "expeditions.json"))
            expedition = manager.create("Sector Campaign", start_system="Sol")
            manager.apply_objective_template(expedition["id"], "sector_mapping_campaign")

            manager.observe_recon("Alpha", score=82)
            recon = next(
                row for row in manager.active()["objectives"]
                if row["kind"] == "recon_system"
            )
            self.assertEqual((recon["progress"], recon["count"]), (1, 100))

    def test_named_expedition_spans_sessions_and_completes_verified_goals(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = ExpeditionManager(os.path.join(folder, "expeditions.json"))
            expedition = manager.create("Outer Rim Survey", start_system="Sol", destination="Beagle Point")
            manager.add_objective(expedition["id"], "reach_system", target="Alpha")
            manager.add_objective(expedition["id"], "fss_system", target="Alpha")
            manager.add_objective(expedition["id"], "dss_count", count=2)
            manager.add_objective(
                expedition["id"], "bio_species", target="Bacterium Cerbrus",
                system="Alpha", body="Alpha 2",
            )

            manager.observe_event({
                "timestamp": "2099-07-26T10:00:00Z", "event": "LoadGame",
            }, event_uid="load-1")
            result = manager.observe_event({
                "timestamp": "2099-07-26T10:10:00Z", "event": "FSDJump",
                "StarSystem": "Alpha", "JumpDist": 22.5,
            }, event_uid="jump-1")
            honk = manager.observe_event({
                "timestamp": "2099-07-26T10:11:00Z", "event": "FSSDiscoveryScan",
                "BodyCount": 3, "Progress": 1.0,
            }, context={"system": "Alpha"}, event_uid="honk-1")
            self.assertEqual(honk["completed"], [])
            fss = manager.observe_event({
                "timestamp": "2099-07-26T10:12:00Z", "event": "FSSAllBodiesFound",
                "SystemName": "Alpha", "Count": 3,
            }, event_uid="fss-1")
            self.assertEqual(fss["completed"], ["Complete system FSS: Alpha"])
            manager.observe_event({
                "timestamp": "2099-07-26T10:20:00Z", "event": "SAAScanComplete",
                "BodyName": "Alpha 1", "ProbesUsed": 4, "EfficiencyTarget": 5,
            }, context={"system": "Alpha"}, event_uid="dss-1")
            manager.observe_event({
                "timestamp": "2099-07-26T10:21:00Z", "event": "SAAScanComplete",
                "BodyName": "Alpha 2", "ProbesUsed": 6, "EfficiencyTarget": 5,
            }, context={"system": "Alpha"}, event_uid="dss-2")
            manager.observe_event({
                "timestamp": "2099-07-26T10:30:00Z", "event": "ScanOrganic",
                "ScanType": "Analyse", "Species_Localised": "Bacterium Cerbrus", "Body": 2,
            }, context={"system": "Alpha", "body": "Alpha 2"}, event_uid="bio-1")

            self.assertEqual(result["completed"], ["Reach system: Alpha"])
            active = manager.active()
            self.assertEqual(manager.progress(active), (4, 4))
            self.assertEqual(active["stats"]["sessions"], 2)
            self.assertEqual(active["stats"]["jumps"], 1)
            self.assertEqual(active["stats"]["distance_ly"], 22.5)
            self.assertEqual(active["stats"]["dss_efficient"], 1)
            self.assertEqual(active["stats"]["fss_scans"], 1)

            # Replay of the same journal record cannot inflate statistics.
            manager.observe_event({
                "timestamp": "2099-07-26T10:21:00Z", "event": "SAAScanComplete",
                "BodyName": "Alpha 2",
            }, context={"system": "Alpha"}, event_uid="dss-2")
            self.assertEqual(manager.active()["stats"]["dss_maps"], 2)

            # A semantically repeated scan with a different journal record is
            # still one mapped body, not extra objective progress.
            manager.observe_event({
                "timestamp": "2099-07-26T10:40:00Z", "event": "SAAScanComplete",
                "BodyName": "Alpha 2",
            }, context={"system": "Alpha"}, event_uid="dss-repeat")
            self.assertEqual(manager.active()["stats"]["dss_maps"], 2)

    def test_bookmarks_and_portable_plan_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            source = ExpeditionManager(os.path.join(folder, "source.json"))
            expedition = source.create("Photo Trail", start_system="Sol")
            source.add_objective(expedition["id"], "screenshot_count", count=3)
            bookmark = source.add_bookmark(
                "Photo", system="Alpha", title="Blue nebula",
                priority="High", tags=["photo", "nebula"], position=[1, 2, 3],
            )
            payload = source.export_payload(expedition["id"])

            # Profile bookmarks remain useful even while no named expedition
            # is active.
            source.set_status(expedition["id"], "paused")
            visit = source.observe_event({
                "timestamp": "2099-07-26T11:00:00Z", "event": "FSDJump",
                "StarSystem": "Alpha",
            }, event_uid="paused-bookmark-visit")
            self.assertEqual(visit["bookmarks_visited"], ["Blue nebula"])
            self.assertEqual(source.bookmarks(expedition["id"])[0]["status"], "visited")

            target = ExpeditionManager(os.path.join(folder, "target.json"))
            imported = target.import_payload(json.loads(json.dumps(payload)))

            self.assertNotEqual(imported["id"], expedition["id"])
            self.assertEqual(imported["status"], "paused")
            self.assertEqual(target.bookmarks(imported["id"])[0]["title"], bookmark["title"])
            self.assertEqual(target.waypoint_lines(imported["id"]), ["Sol", "Alpha"])


if __name__ == "__main__":
    unittest.main()
