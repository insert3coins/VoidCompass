"""Survey queue choices must survive restart without leaking between commanders."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from voidcompass.core import config as app_config


class SurveyQueuePersistenceTests(unittest.TestCase):
    def test_choices_are_saved_in_the_active_profile_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profiles = root / "profiles"
            settings_file = root / "config.json"
            with (patch.object(app_config, "PROFILE_DIR", str(profiles)),
                  patch.object(app_config, "CONFIG_FILE", str(settings_file)),
                  patch.object(app_config, "detect_elite_journal_path", return_value="")):
                settings = app_config.load_config()
                self.assertEqual(settings["stellar_survey_queue_state"], {})

                app_config.apply_profile_config(settings, "alpha")
                alpha_choices = {"Sol": {"pinned": ["body:1"], "skipped": [], "completed": []}}
                settings["stellar_survey_queue_state"] = alpha_choices
                app_config.save_config(settings)
                self.assertNotIn("stellar_survey_queue_state", json.loads(settings_file.read_text()))
                self.assertEqual(json.loads((profiles / "alpha" / app_config.PROFILE_CONFIG_NAME).read_text())
                                 ["stellar_survey_queue_state"], alpha_choices)

                restarted = app_config.load_config()
                self.assertEqual(restarted["stellar_survey_queue_state"], alpha_choices)
                app_config.apply_profile_config(restarted, "bravo")
                self.assertEqual(restarted["stellar_survey_queue_state"], {})
                restarted["stellar_survey_queue_state"] = {
                    "Achenar": {"pinned": [], "skipped": ["body:3"], "completed": []},
                }
                app_config.save_config(restarted)
                app_config.apply_profile_config(restarted, "alpha")
                self.assertEqual(restarted["stellar_survey_queue_state"], alpha_choices)


if __name__ == "__main__":
    unittest.main()
