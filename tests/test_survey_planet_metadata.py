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

    def test_compact_mode_keeps_all_routine_scans_when_fss_count_is_full(self):
        first = {
            'body_id': 3, 'name': 'Testia A 3', 'planet_class': 'Rocky body',
            'scan_timestamp': '2026-09-23T08:00:00Z',
        }
        next_scan = {
            'body_id': 4, 'name': 'Testia A 4', 'planet_class': 'Icy body',
            'scan_timestamp': '2026-09-23T08:01:00Z',
        }
        before = build_survey_model('Testia', [first], scanned=4, total=4)
        after = build_survey_model('Testia', [next_scan, first], scanned=4, total=4)
        self.assertEqual([row['name'] for row in before['rows']], ['Testia A 3'])
        self.assertEqual([row['name'] for row in after['rows']],
                         ['Testia A 4', 'Testia A 3'])
        self.assertTrue(after['rows'][0]['recent_scan'])
        self.assertFalse(after['rows'][0]['priority'])
        self.assertFalse(after['rows'][0]['expanded'])
        self.assertFalse(after['rows'][1]['expanded'])
        self.assertNotEqual(_survey_render_key(before), _survey_render_key(after))

        rescanned = dict(next_scan, scan_timestamp='2026-09-23T08:02:00Z')
        after_rescan = build_survey_model(
            'Testia', [rescanned, first], scanned=4, total=4,
        )
        self.assertNotEqual(_survey_render_key(after),
                            _survey_render_key(after_rescan))

        all_bodies = build_survey_model(
            'Testia', [next_scan, first], scanned=4, total=4,
            show_all_bodies=True,
        )
        self.assertEqual({row['name'] for row in all_bodies['rows']},
                         {'Testia A 3', 'Testia A 4'})
        self.assertTrue(all(row['expanded'] for row in all_bodies['rows']))

    def test_focused_routine_planet_remains_visible_after_scan(self):
        ordinary = {
            'body_id': 5, 'name': 'Testia A 5', 'planet_class': 'Rocky body',
        }
        model = build_survey_model('Testia', [ordinary], focused_body_id=5)
        self.assertEqual(model['mode'], 'body')
        self.assertEqual(model['body']['name'], 'Testia A 5')

    def test_each_survey_filter_marks_a_scanned_planet_as_detailed(self):
        for field, value in (('bio_count', 1), ('geo_count', 1),
                             ('landable', True), ('mining_count', 1)):
            with self.subTest(field=field):
                scan = {
                    'body_id': 6, 'name': 'Testia A 6',
                    'planet_class': 'Rocky body', field: value,
                }
                row = build_survey_model('Testia', [scan])['rows'][0]
                self.assertTrue(row['priority'])
                self.assertFalse(row['expanded'])
                if field == 'landable':
                    self.assertTrue(row['landable_known'])

    def test_non_landable_scan_stays_routine_and_can_expand(self):
        scan = {
            'body_id': 7, 'name': 'Testia A 7',
            'planet_class': 'Rocky body', 'landable': False,
        }
        compact = build_survey_model('Testia', [scan])['rows'][0]
        expanded = build_survey_model('Testia', [scan], show_all_bodies=True)['rows'][0]
        self.assertTrue(compact['landable_known'])
        self.assertFalse(compact['priority'])
        self.assertFalse(compact['expanded'])
        self.assertFalse(expanded['priority'])
        self.assertTrue(expanded['expanded'])

    def test_sampling_distance_and_clearance_publish_new_render(self):
        model = {
            'mode': 'system', 'system': 'Testia', 'rows': [],
            'sampling': {
                'species': 'Bacterium Sample', 'progress': 2,
                'min_distance_m': 240, 'colony_m': 500, 'clear': False,
            },
        }
        moved = copy.deepcopy(model)
        moved['sampling']['min_distance_m'] = 260
        self.assertNotEqual(_survey_render_key(model), _survey_render_key(moved))
        ready = copy.deepcopy(moved)
        ready['sampling'].update(min_distance_m=530, clear=True)
        self.assertNotEqual(_survey_render_key(moved), _survey_render_key(ready))


if __name__ == '__main__':
    unittest.main()
