from pathlib import Path
import unittest

from voidcompass.core.paths import project_root, resource_path
from voidcompass.core.version import APP_VERSION
from tools.version_sync import validate_version_sync


ROOT = Path(__file__).resolve().parents[1]


class ProjectStructure545Tests(unittest.TestCase):
    def test_release_version_and_project_root(self):
        self.assertFalse(validate_version_sync(ROOT), APP_VERSION)
        self.assertEqual(project_root(), ROOT)

    def test_feature_packages_and_launcher_exist(self):
        package_root = ROOT / "src" / "voidcompass"
        for name in (
            "core", "dashboard", "overlays", "engineering",
            "exploration", "mining", "powerplay", "services",
        ):
            self.assertTrue((package_root / name / "__init__.py").is_file(), name)
        self.assertTrue((ROOT / "VoidCompass.py").is_file())

    def test_runtime_assets_resolve_from_structured_directories(self):
        self.assertEqual(resource_path("web"), ROOT / "web")
        self.assertTrue(resource_path("assets", "images", "ships").is_dir())
        self.assertTrue(resource_path("data", "codexRef.json").is_file())

    def test_production_modules_no_longer_fill_repository_root(self):
        allowed = {"VoidCompass.py"}
        root_modules = {path.name for path in ROOT.glob("*.py")}
        self.assertEqual(root_modules, allowed)


if __name__ == "__main__":
    unittest.main()
