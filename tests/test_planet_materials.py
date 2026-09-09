import tempfile
import sqlite3
from contextlib import closing
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from planet_materials import PlanetMaterialsStore
from dashboard import MainDashboard
from hud import TacticalHUD


class PlanetMaterialsTests(unittest.TestCase):
    def test_legacy_database_migrates_and_retains_scan_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sites.db'
            with closing(sqlite3.connect(path)) as db, db:
                db.execute('CREATE TABLE sites (id INTEGER PRIMARY KEY, system TEXT, body TEXT, name TEXT, latitude REAL, longitude REAL, materials TEXT, notes TEXT, updated_at TEXT)')
                db.execute("INSERT INTO sites VALUES (1,'Sol','Moon','Old',0,0,'Ruby','','old')")
            store = PlanetMaterialsStore(path)
            row = store.rows()[0]
            self.assertEqual(row['body_details'], {})
            row.update(body_details={'system':'Sol','body':'Moon','class':'Rocky body',
                'materials':[{'name':'Iron','percent':18.2}]}, density='High')
            store.save(row)
            saved = PlanetMaterialsStore(path).rows()[0]
            self.assertEqual(saved['body_details'], row['body_details'])
            self.assertEqual(saved['density'], 'High')
            with self.assertRaises(ValueError):
                store.save({**row, 'body':'Mars'})

    def test_live_position_captures_matching_scan_and_disables_off_planet(self):
        app = MainDashboard.__new__(MainDashboard)
        app.config = {}
        app.current_sys = 'Sol'
        app.current_body_name = 'Moon'
        app.current_latitude = 0
        app.current_longitude = -180
        app.on_planet = True
        app._planet_materials_store = lambda: SimpleNamespace(rows=lambda: [])
        app.scan_items = [dict(name='Mars', materials={'carbon':12}),
            dict(name='Moon', planet_class='Rocky body', materials={'iron':18.2})]
        current = app._html_planet_materials_workspace()['current_position']
        self.assertEqual(current['latitude'], 0)
        self.assertEqual(current['longitude'], -180)
        self.assertEqual(current['body_details']['materials'][0]['name'], 'iron')
        app.on_planet = False
        self.assertIsNone(app._html_planet_materials_workspace()['current_position'])

    def test_edit_reopen_delete_and_profile_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'one' / 'planet_materials.db'
            store = PlanetMaterialsStore(path)
            data = dict(system='Sol', body='Moon', name='Site 1', latitude=0,
                        longitude=-180, materials='Diamond, Osmium', notes='Dense')
            site_id = store.save(data)
            data.update(id=site_id, latitude=90, longitude=180, materials='Ruby')
            store.save(data)
            reopened = PlanetMaterialsStore(path)
            self.assertEqual(reopened.rows()[0]['materials'], 'Ruby')
            other = PlanetMaterialsStore(Path(folder) / 'two' / 'planet_materials.db')
            self.assertEqual(other.rows(), [])
            self.assertFalse(other.delete(site_id))
            self.assertEqual(len(reopened.rows()), 1)
            self.assertTrue(reopened.delete(site_id))
            self.assertEqual(reopened.rows(), [])

    def test_coordinate_validation_does_not_write_invalid_data(self):
        with tempfile.TemporaryDirectory() as folder:
            store = PlanetMaterialsStore(Path(folder) / 'sites.db')
            data = dict(system='Sol', body='Moon', name='Site', materials='Iron', latitude=0, longitude=0)
            for key, value in [('latitude', 91), ('longitude', -181), ('latitude', 'nan'),
                               ('longitude', 'inf'), ('latitude', ''), ('latitude', None)]:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    store.save({**data, key: value})
            self.assertEqual(store.rows(), [])

    def test_stale_profile_command_is_rejected(self):
        dashboard = MainDashboard.__new__(MainDashboard)
        dashboard.config = {}
        with patch('html_dashboard.get_active_profile', return_value='new'):
            self.assertFalse(dashboard._handle_html_workspace_command({
                'page': 'planet-materials', 'operation': 'save', 'profile_key': 'old'}))


class CarrierPreparationTests(unittest.TestCase):
    def make_dashboard(self):
        dashboard = MainDashboard.__new__(MainDashboard)
        dashboard._commander_aboard_carrier = lambda data: data.get('aboard', True)
        dashboard.update_hud = lambda: None
        dashboard.batch_mode = False
        return dashboard

    def schedule(self, seconds, **extra):
        return dict(status='jumping', jump_destination='Sol', jump_departure_time=(
            datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(), **extra)

    def test_phases_cancellation_disembark_and_stale_schedule(self):
        dashboard = self.make_dashboard()
        for seconds, expected in [(900, 'carrier_preparing'), (120, 'carrier_lockdown'), (-1, 'carrier_transit')]:
            self.assertTrue(dashboard._sync_navigation_carrier_transit(self.schedule(seconds)))
            self.assertEqual(dashboard._navigation_jump_phase, expected)
            context = dashboard._navigation_fsd_readiness_context()
            self.assertEqual(context['state'], expected)
            state = TacticalHUD._state_text(TacticalHUD.__new__(TacticalHUD), {'fsd_readiness': context})
            self.assertIn(state, {'CARRIER PREPARING', 'CARRIER LOCKDOWN', 'CARRIER TRANSIT'})
        dashboard._sync_navigation_carrier_transit({'status': 'idle'})
        self.assertEqual(dashboard._navigation_jump_phase, '')
        dashboard._sync_navigation_carrier_transit(self.schedule(120))
        dashboard._sync_navigation_carrier_transit(self.schedule(120, aboard=False))
        self.assertEqual(dashboard._navigation_jump_phase, '')
        self.assertFalse(dashboard._sync_navigation_carrier_transit(self.schedule(-300)))
        self.assertEqual(dashboard._navigation_jump_phase, '')

    def test_arrival_remains_confirmed_and_readable(self):
        dashboard = self.make_dashboard()
        delays = []
        dashboard.root = SimpleNamespace(call_later=lambda delay, callback: delays.append(delay), cancel=lambda job: None)
        dashboard._set_navigation_jump_phase('carrier_arrival')
        self.assertEqual(delays[-1], 12000)
        dashboard._sync_navigation_carrier_transit(self.schedule(-1))
        self.assertEqual(dashboard._navigation_jump_phase, 'carrier_arrival')
        dashboard._sync_navigation_carrier_transit({'status': 'idle'})
        self.assertEqual(dashboard._navigation_jump_phase, 'carrier_arrival')


class CarrierJournalOrderingTests(unittest.TestCase):
    def make_dashboard(self):
        app = MainDashboard.__new__(MainDashboard)
        app.update_hud = lambda: None
        app.batch_mode = False
        app.current_docked = True
        app.current_on_foot = False
        app.current_station_type = 'FleetCarrier'
        app.current_station_market_id = 22
        departure = (datetime.now(timezone.utc) + timedelta(seconds=601)).isoformat()
        rows = [dict(carrier_id=11, carrier_type='FleetCarrier', status='jumping', jump_departure_time=departure, jump_destination='Sol'),
                dict(carrier_id=22, carrier_type='SquadronCarrier', status='jumping', jump_departure_time=departure, jump_destination='Achenar')]
        app.carrier_tracker = SimpleNamespace(carriers=lambda: rows)
        return app, rows

    def test_tracks_aboard_squadron_despite_personal_updates(self):
        app, rows = self.make_dashboard()
        app._sync_navigation_carrier_transit(rows[0])
        self.assertEqual(app._navigation_jump_target, 'Achenar')
        context = app._navigation_fsd_readiness_context()
        self.assertEqual(context['carrier_schedule']['carrier_id'],22)
        text, _ = TacticalHUD._context_presentation({'fsd_readiness':context})
        self.assertIn('SQUADRON · JUMP IN 10:', text)
        app.current_docked = False
        app.current_on_foot = True
        self.assertTrue(app._commander_aboard_carrier(rows[1]))
        app.on_planet = True
        self.assertFalse(app._commander_aboard_carrier(rows[1]))
        self.assertNotEqual(app._navigation_fsd_readiness_context()['state'], 'carrier_preparing')

    def test_location_waits_for_aboard_jump_confirmation(self):
        app, rows = self.make_dashboard()
        rows[1]['jump_departure_time'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        app._sync_navigation_carrier_transit(rows[0])
        self.assertEqual(app._navigation_jump_phase, 'carrier_transit')
        app._observe_navigation_jump_event('CarrierLocation', {'CarrierID':11,'StarSystem':'Achenar'}, {})
        self.assertEqual(app._navigation_jump_phase, 'carrier_transit')
        app._observe_navigation_jump_event('CarrierLocation', {'CarrierID':22,'StarSystem':'Achenar'}, {})
        self.assertEqual(app._navigation_jump_phase, 'carrier_transit')
        rows[1]['status']='cooldown'
        rows[1]['jump_destination']=''
        app._sync_navigation_carrier_transit(rows[0])
        self.assertEqual(app._navigation_jump_phase, 'carrier_transit')
        app._observe_navigation_jump_event('CarrierJump', {'MarketID':22,'StarSystem':'Achenar',
            'Docked':True,'StationType':'FleetCarrier'}, {})
        self.assertEqual(app._navigation_jump_phase, 'carrier_arrival')
        app._observe_navigation_jump_event('Undocked', {}, {})
        self.assertEqual(app._navigation_jump_phase, '')
        app._observe_navigation_jump_event('CarrierLocation', {'CarrierID':22,'StarSystem':'Achenar'}, {})
        self.assertEqual(app._navigation_jump_phase, '')

    def test_overdue_transit_waits_for_journal_and_cancel_is_scoped(self):
        app, rows = self.make_dashboard()
        rows[1]['jump_departure_time'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        app._sync_navigation_carrier_transit(rows[1])
        rows[1]['jump_departure_time'] = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
        app._sync_navigation_carrier_transit(rows[0])
        self.assertEqual(app._navigation_jump_phase, 'carrier_transit')
        app._observe_navigation_jump_event('CarrierJumpCancelled', {'CarrierID':11}, {})
        self.assertEqual(app._navigation_jump_phase, 'carrier_transit')
        app._observe_navigation_jump_event('CarrierJumpCancelled', {'CarrierID':22}, {})
        self.assertEqual(app._navigation_jump_phase, '')
        self.assertEqual(app._navigation_carrier_schedule, {})

    def test_tracker_cooldown_at_departure_still_enters_transit(self):
        app, rows = self.make_dashboard()
        app._sync_navigation_carrier_transit(rows[1])
        rows[1]['jump_departure_time'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        rows[1]['status'] = 'cooldown'
        app._sync_navigation_carrier_transit(rows[1])
        self.assertEqual(app._navigation_jump_phase, 'carrier_transit')
