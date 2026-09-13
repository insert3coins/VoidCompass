from pathlib import Path
import unittest

from engineering_companion import _portrait, reference_catalogues
from html_dashboard_server import HtmlDashboardServer
from powerplay_operations import POWER_DOSSIERS
from release_packager import PUBLIC_RUNTIME_IMAGE_DOCUMENTS, validate_runtime_images
from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]
POWERPLAY_PORTRAITS = {
    "aisling_duval": "aisling_duval.jpg",
    "archon_delaine": "archon_delaine.png",
    "arissa_lavigny_duval": "arissa_lavigny_duval.png",
    "denton_patreus": "denton_patreus.jpg",
    "edmund_mahon": "edmund_mahon.png",
    "felicia_winters": "felicia_winters.png",
    "jerome_archer": "jerome_archer.webp",
    "li_yong_rui": "li_yong_rui.png",
    "nakato_kaine": "nakato_kaine.webp",
    "pranav_antal": "pranav_antal.png",
    "yuri_grom": "yuri_grom.webp",
    "zemina_torval": "zemina_torval.png",
}


class AuthenticPeopleAssetTests(unittest.TestCase):
    def test_release_version_is_544(self):
        self.assertEqual(APP_VERSION, "5.4.4")

    def test_people_provenance_is_allowed_in_release_image_tree(self):
        self.assertIn("Images/people/README.md", PUBLIC_RUNTIME_IMAGE_DOCUMENTS)
        validated = validate_runtime_images(ROOT)
        self.assertIn("Images/people/README.md", validated)

    def test_every_catalogued_engineer_has_a_local_portrait(self):
        for name in reference_catalogues()["unlocks"]:
            url = _portrait(name)
            self.assertTrue(url.startswith("images/people/engineers/"), name)
            relative = Path(url).relative_to("images")
            self.assertTrue((ROOT / "Images" / relative).is_file(), (name, url))

    def test_current_powerplay_roster_has_local_portraits(self):
        catalogue = {row["slug"]: row["portrait"] for row in POWER_DOSSIERS}
        for slug, filename in POWERPLAY_PORTRAITS.items():
            self.assertTrue(
                (ROOT / "Images" / "people" / "powerplay" / filename).is_file(),
                slug,
            )
            self.assertEqual(catalogue.get(slug), filename)

    def test_dashboard_serves_only_descendants_of_the_image_root(self):
        server = HtmlDashboardServer(
            ROOT / "web" / "dashboard", image_root=ROOT / "Images",
        )
        try:
            portrait = server._static_path(
                "/images/people/engineers/felicity_farseer.jpg"
            )
            self.assertEqual(
                portrait,
                (ROOT / "Images" / "people" / "engineers" /
                 "felicity_farseer.jpg").resolve(),
            )
            self.assertIsNone(server._static_path("/images/../version.py"))
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
