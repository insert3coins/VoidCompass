"""Scan-backed planet metadata for Survey Operations' illustrated cards."""

import copy
import unittest

from voidcompass.overlays.survey_status_hud import build_survey_model, _survey_render_key


class SurveyPlanetMetadataTests(unittest.TestCase):
    def _scan(self):
        return {
            'body_id': 2,
            'name': 'Testia A 2',
            'planet_class': 'Water world',
            'atmosphere_type': 'Thin oxygen atmosphere',
            'rings': [{'RingClass': 'eRingClass_MetalRich'}],
            'bio_count': 1,
            'organic_scans': {},
            'genuses': [],
        }

    def test_system_and_notable_rows_use_the_same_scan_facts(self):
        model = build_survey_model('Testia', [self._scan()])
        self.assertEqual(model['mode'], 'system')
        row = model['rows'][0]
        for card in (row, row['notable']):
            self.assertEqual(card['designation'], 'A 2')
            self.assertEqual(card['class_label'], 'Water world')
            self.assertEqual(card['atmosphere_label'], 'Thin oxygen atmosphere')
            self.assertEqual(card['ring_count'], 1)

    def test_focused_body_keeps_visual_metadata(self):
        model = build_survey_model('Testia', [self._scan()], focused_body_id=2)
        self.assertEqual(model['mode'], 'body')
        self.assertEqual(model['body']['designation'], 'A 2')
        self.assertEqual(model['body']['class_label'], 'Water world')
        self.assertEqual(model['body']['atmosphere_label'], 'Thin oxygen atmosphere')
        self.assertEqual(model['body']['ring_count'], 1)

    def test_signal_only_body_does_not_invent_class_or_rings(self):
        model = build_survey_model(
            'Testia', [], body_signals={2: {'body_name': 'Testia A 2', 'bio': 1}},
        )
        row = model['rows'][0]
        self.assertEqual(row['designation'], 'A 2')
        self.assertEqual(row['class_label'], '')
        self.assertEqual(row['atmosphere_label'], '')
        self.assertIsNone(row['ring_count'])

    def test_scanned_empty_ring_list_is_known_zero(self):
        scan = self._scan()
        scan['rings'] = []
        self.assertEqual(build_survey_model('Testia', [scan])['rows'][0]['ring_count'], 0)

    def test_render_key_notices_planet_fact_changes(self):
        original = build_survey_model('Testia', [self._scan()])
        for field, value in (('class_label', 'Ammonia world'),
                             ('atmosphere_label', 'No atmosphere'),
                             ('ring_count', 2),
                             ('first_footfall', True)):
            changed = copy.deepcopy(original)
            changed['rows'][0][field] = value
            self.assertNotEqual(_survey_render_key(original), _survey_render_key(changed), field)


if __name__ == '__main__':
    unittest.main()
