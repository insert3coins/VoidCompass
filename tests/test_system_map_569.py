"""System architecture, native graphics and live journal handoff (5.6.9).

The System Map is Explore & Survey's SYSTEM MAP tab. Beyond the worlds themselves
it marks where you are and Elite's target, stations, settlements and carriers,
your saved sites and expedition stops, ring hotspots and your survey; it predicts
eclipses and day and night on locked worlds, shows the sky from a surface, keeps
moons and neighbours apart in the overview, and loads its surfaces quickly."""
import copy
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
from voidcompass.dashboard.html_system_map import HtmlSystemMapMixin
from voidcompass.exploration.system_map import AU_M, SystemMapCatalogue, journal_body, merge_system
from voidcompass.services import spansh
from tests.test_dashboard_overview_visuals import overview_state
from tests.test_explore_survey_visuals import SCAN_ITEMS, SYSTEM, workspace_data, snapshot_state

ROOT = Path(__file__).resolve().parents[1]
ADDRESS = '18446744073709551001'


def map_data():
    scans = [dict(row, radius=3_500_000, mass=.2, surface_temp=210) for row in SCAN_ITEMS]
    scans[0].update(radius=450_000_000, mass=.7, surface_temp=4800)
    scans[3]['rings'] = [{'Name': 'A ring', 'RingClass': 'eRingClass_Icy', 'InnerRad': 6_000_000, 'OuterRad': 11_000_000}]
    scans[4].update(radius=9_000_000, mass=2, surface_temp=285, atmosphere_type='Oxygen', surface_pressure=101325)
    return {'profile_key': 'system-map-test', 'system': merge_system(SYSTEM, ADDRESS, scans, expected=9),
            'catalogue': {'status': 'ready', 'detail': 'Spansh catalogue linked. Your journal scans take priority.'}}


def orbit_system():
    """A small deterministic system: a ringed planet with a locked moon in the star's plane
    (an eclipse every orbit), a second moon, a neighbour and a body with only part of its orbit."""
    epoch = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    plane = dict(orbitalEccentricity=0, orbitalInclination=0, ascendingNode=0, argOfPeriapsis=0, meanAnomaly=0,
                 timestamps={'meanAnomaly': epoch}, axialTilt=0)
    body = lambda body_id, name, kind, **fields: {'bodyId': body_id, 'name': f'Orbit {name}', 'type': kind, **fields}
    public = {'name': 'Orbit', 'id64': ADDRESS, 'stations': [
        {'id': 1, 'name': 'Orbit Port', 'type': 'Coriolis Starport', 'distanceToArrival': 499.0,
         'updateTime': epoch.replace('T', ' ').replace('Z', '+00'), 'market': {'commodities': ['huge']}}], 'bodies': [
        body(0, 'A', 'Star', subType='G (White-Yellow) Star', spectralClass='G2', solarRadius=1, solarMasses=1, mainStar=True, distanceToArrival=0),
        body(1, '1', 'Planet', subType='Rocky body', radius=6371, parents=[{'Star': 0}], semiMajorAxis=1, orbitalPeriod=365.25,
             distanceToArrival=499, rings=[{'name': 'Orbit 1 A Ring', 'type': 'Icy', 'innerRadius': 9e6, 'outerRadius': 1.6e7}], **plane,
             stations=[{'name': 'Rim Hub', 'type': 'Surface Settlement', 'latitude': 5, 'longitude': 10, 'market': {'x': 1}}]),
        body(2, '1 a', 'Planet', subType='Icy body', radius=1700, parents=[{'Planet': 1}, {'Star': 0}], semiMajorAxis=.0005, orbitalPeriod=1,
             rotationalPeriod=1, rotationalPeriodTidallyLocked=True, isLandable=True, distanceToArrival=499, **plane),
        body(3, '1 b', 'Planet', subType='Rocky body', radius=900, parents=[{'Planet': 1}, {'Star': 0}], semiMajorAxis=.001, orbitalPeriod=3,
             distanceToArrival=499, **plane),
        body(4, '2', 'Planet', subType='High metal content world', radius=5000, parents=[{'Star': 0}], semiMajorAxis=1.08, orbitalPeriod=410,
             distanceToArrival=539, **{**plane, 'meanAnomaly': 40}),
        body(5, '3', 'Planet', subType='Rocky body', radius=3000, parents=[{'Star': 0}], semiMajorAxis=2, orbitalPeriod=1000, distanceToArrival=998)]}
    system = merge_system('Orbit', ADDRESS, [], public=public)
    system['bodies'][1]['rings'][0]['hotspots'] = [{'material': 'Painite', 'count': 2}]
    system['you'] = {'state': 'FLIGHT', 'body': 'Orbit 1 a', 'body_id': 2, 'docked': False, 'landed': True, 'on_foot': False, 'srv': False,
                     'station': None, 'lat': 10.0, 'lon': 20.0, 'altitude_m': 0}
    system['places'] = [{'kind': 'site', 'label': 'Ice field', 'body': 'Orbit 1 a', 'lat': -15.0, 'lon': 60.0},
                        {'kind': 'stop', 'label': 'Survey the neighbour', 'body': 'Orbit 2', 'lat': None, 'lon': None, 'reached': False}]
    system['carriers'] = [{'name': 'Test Carrier', 'callsign': 'X1X-2YZ', 'body': 'Orbit 2'}]
    system['target'] = {'body_id': 4, 'name': 'Orbit 2'}
    for row in system['bodies']:
        if row['bodyId'] == 2:
            row['_survey'] = {'scanned': True, 'mapped': False, 'bio': 2, 'geo': 0, 'wasDiscovered': False}
    return system


def map_state():
    state = overview_state()
    state.update(app={'version': '5.6.9'}, boot={'active': False}, onboarding={'active': False})
    state['profile']['key'] = 'system-map-test'
    state['flight']['system'] = SYSTEM
    state['system_map'] = map_data()
    state['workspace'] = {'page': 'system-map', 'ready': True, 'data': state['system_map']}
    return state


class ArchitectureTests(unittest.TestCase):
    def test_journal_units_and_phase_epoch_are_converted_once(self):
        body = journal_body({'body_id': 7, 'name': 'Test 7', 'semi_major_axis': AU_M,
                             'orbital_period': 86400, 'radius': 6_000_000, 'mass': 2,
                             'mean_anomaly': 37, 'scan_timestamp': '2026-10-29T00:00:00Z', 'axial_tilt': .4})
        self.assertEqual((body['semiMajorAxis'], body['orbitalPeriod'], body['radius']), (1, 1, 6000))
        self.assertEqual(body['meanAnomaly'], 37)
        self.assertEqual(body['timestamps']['meanAnomaly'], '2026-10-29T00:00:00Z')
        self.assertEqual(body['axialTilt'], .4)

    def test_public_bodies_do_not_become_personal_discoveries_and_scans_win(self):
        public = {'name': 'Test', 'id64': int(ADDRESS), 'bodies': [
            {'bodyId': 0, 'name': 'Test A', 'type': 'Star'},
            {'bodyId': 1, 'name': 'Test 1', 'type': 'Planet', 'radius': 1000, 'stations': [{'market': {'commodities': ['huge']}}]},
            {'bodyId': 2, 'name': 'Test 2', 'type': 'Planet', 'radius': 2000}]}
        result = merge_system('Test', ADDRESS, [{'body_id': 1, 'name': 'Test 1', 'radius': 3_000_000,
                              'dss_complete': True, 'bio_count': 2, 'was_discovered': False}], public=public)
        by_id = {row['bodyId']: row for row in result['bodies']}
        self.assertEqual(by_id[1]['radius'], 3000)
        self.assertEqual(by_id[1]['_source'], 'journal+spansh')
        self.assertTrue(by_id[1]['_survey']['mapped'])
        self.assertFalse(by_id[1]['_survey']['wasDiscovered'])
        self.assertFalse(by_id[2]['_survey']['scanned'])
        self.assertNotIn('stations', by_id[1], 'market dumps never enter the render snapshot')
        self.assertEqual(result['id64'], ADDRESS, '64-bit system identifiers stay exact')
        self.assertNotIn('_source', public['bodies'][0], 'the shared public cache is immutable')

    def test_a_different_system_or_ship_location_cannot_leak_bodies(self):
        other = {'name': 'Previous', 'id64': ADDRESS, 'bodies': [{'bodyId': 9, 'name': 'Previous 9'}]}
        result = merge_system('Current', ADDRESS, [{'body_id': 1, 'system_address': '42'}], public=other)
        self.assertEqual(result['bodies'], [])
        other['name'] = 'Current'
        other['id64'] = '43'
        self.assertEqual(merge_system('Current', ADDRESS, [], public=other)['bodies'], [])

    def test_a_partial_scan_keeps_the_public_phase_and_epoch_together(self):
        public = {'name': 'Test', 'id64': ADDRESS, 'bodies': [{'bodyId': 1, 'name': 'Test 1', 'type': 'Planet',
            'parents': [{'Star': 0}], 'semiMajorAxis': 1, 'orbitalPeriod': 10, 'ascendingNode': 0, 'orbitalInclination': 0, 'argOfPeriapsis': 0,
            'meanAnomaly': 70, 'timestamps': {'meanAnomaly': '2026-01-01T00:00:00Z'}}]}
        body = merge_system('Test', ADDRESS, [{'body_id': 1, 'name': 'Test 1', 'mean_anomaly': 0}], public=public)['bodies'][0]
        self.assertEqual(body['meanAnomaly'], 70)
        self.assertEqual(body['timestamps']['meanAnomaly'], '2026-01-01T00:00:00Z')
        self.assertTrue(body['_resolved'])

    def test_missing_epoch_is_unresolved_and_barycentres_remain_in_the_graph(self):
        rows = [{'body_id': 0, 'is_star': True}, {'body_id': 1, 'name': 'Test 1', 'parents': [{'Null': 3}],
                 'semi_major_axis': AU_M, 'orbital_period': 86400, 'mean_anomaly': 90, 'ascending_node': 0}]
        result = merge_system('Test', ADDRESS, rows, [{'body_id': 3, 'parents': [{'Star': 0}]}])
        self.assertFalse(result['bodies'][1]['_resolved'])
        self.assertEqual(result['bodies'][2]['type'], 'Barycentre')

    def test_spansh_body_fetch_retains_architecture_separately_from_market_helpers(self):
        public = {'name': 'Test', 'bodies': [{'bodyId': 0}]}
        with patch.object(spansh, '_call', return_value={'system': public}) as call:
            self.assertEqual(spansh.system_body_dump('Test', ADDRESS), public)
        self.assertEqual(call.call_args.args, ('GET', f'dump/{ADDRESS}'))
        self.assertEqual(call.call_args.kwargs['timeout'], 30)

    def test_signal_only_journal_rows_are_not_marked_as_completed_scans(self):
        body = journal_body({'body_id': 1, 'name': 'Test 1', 'signal_only': True, 'bio_count': 2})
        self.assertFalse(body['_survey']['scanned'])
        self.assertEqual(body['_survey']['bio'], 2)

    def test_stations_are_trimmed_settlements_kept_and_partial_orbits_approximate(self):
        system = orbit_system()
        station = system['stations'][0]
        self.assertEqual(station['name'], 'Orbit Port')
        self.assertNotIn('market', station, 'market dumps never enter the render snapshot')
        bodies = {row['bodyId']: row for row in system['bodies']}
        self.assertEqual(bodies[1]['surfaceStations'], [{'name': 'Rim Hub', 'type': 'Surface Settlement', 'latitude': 5, 'longitude': 10}])
        self.assertFalse(bodies[5]['_resolved'])
        self.assertTrue(bodies[5]['_approx'], 'a parent and a distance: placed approximately')
        self.assertFalse(bodies[2]['_approx'])


class CatalogueTests(unittest.TestCase):
    def test_requests_are_nonblocking_coalesced_and_isolated_between_systems(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def fetch(name, address):
            calls.append(name)
            entered.set()
            release.wait(5)
            return {'name': name, 'id64': address, 'bodies': []}
        catalogue = SystemMapCatalogue(fetch=fetch)
        try:
            self.assertEqual(catalogue.request('Test', ADDRESS)['status'], 'loading')
            self.assertTrue(entered.wait(1))
            for _ in range(4):
                self.assertEqual(catalogue.request('Test', ADDRESS)['status'], 'loading')
            self.assertEqual(calls, ['Test'])
            other = catalogue.request('Other', '42')
            self.assertEqual(other['system'], {})
        finally:
            release.set()
        deadline = time.monotonic() + 2
        while catalogue.inflight and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertEqual(catalogue.request('Test', ADDRESS)['system']['name'], 'Test')
        self.assertEqual(catalogue.request('Other', '42')['system']['name'], 'Other')

    def test_failure_keeps_cached_bodies_and_backs_off(self):
        now = [100.0]
        catalogue = SystemMapCatalogue(fetch=lambda *args: (_ for _ in ()).throw(spansh.SpanshError('offline')), clock=lambda: now[0])
        key = ('test', ADDRESS)
        catalogue.entries[key] = {'system': {'name': 'Test', 'bodies': [{'bodyId': 0}]}, 'next': 0}
        catalogue._load(key, 'Test')
        result = catalogue.request('Test', ADDRESS)
        self.assertEqual(result['status'], 'cached')
        self.assertEqual(len(result['system']['bodies']), 1)
        self.assertEqual(catalogue.entries[key]['next'], 160)
        self.assertFalse(catalogue.inflight)

    def test_mixin_reconciles_current_journals_with_a_pending_public_request(self):
        class Deck(HtmlSystemMapMixin):
            config = {}
            current_sys = 'Test'
            current_system_address = ADDRESS
            scan_items = [{'body_id': 0, 'name': 'Test A', 'is_star': True}]
            def _html_local_body_target(self):
                return None
        deck = Deck()
        class Catalogue:
            def request(self, *args):
                return {'status': 'loading', 'detail': 'Linking Spansh', 'system': {}}
        deck._system_map_catalogue = Catalogue()
        first = deck._html_system_map_workspace()
        self.assertEqual(first['system']['name'], 'Test')
        self.assertEqual(first['system']['bodies'][0]['_source'], 'journal')
        deck.current_sys = 'New'
        deck.current_system_address = '42'
        deck.scan_items = [{'body_id': 0, 'name': 'New A', 'is_star': True}]
        self.assertEqual(deck._html_system_map_workspace()['system']['bodies'][0]['name'], 'New A')

    def test_mixin_adds_where_you_are_your_places_carriers_hotspots_and_materials(self):
        class Sites:
            def rows(self):
                return [{'body': 'Test 1', 'name': 'Bio patch', 'latitude': 1.5, 'longitude': -2},
                        {'body': 'Elsewhere 1', 'name': 'Not here', 'latitude': 0, 'longitude': 0}]
        class Expeditions:
            def active(self):
                return {'name': 'Trip', 'legs': [{'system': 'Test', 'body': 'Test 2', 'note': 'Land here'}, {'system': 'Far', 'body': ''}]}
        class Carriers:
            def carriers(self):
                return [{'name': 'Mine', 'callsign': 'AAA-111', 'system': 'test', 'body': 'Test 1'}, {'name': 'Away', 'system': 'Far'}]
        class Mining:
            def hotspots_in(self, name):
                return [{'body_name': 'Test 1 A Ring', 'material_name': 'Painite', 'hotspot_count': 3, 'ring_type': 'Metallic'}]
        class Deck(HtmlSystemMapMixin):
            config = {}
            current_sys, current_system_address = 'Test', ADDRESS
            current_docked, current_station_name, current_station_type, current_station_dist_ls = True, 'Port', 'Outpost', 12.5
            current_body_name, current_body_id, hud_flight_state = 'Test 1', 1, 'DOCKED'
            scan_items = [{'body_id': 0, 'name': 'Test A', 'is_star': True},
                          {'body_id': 1, 'name': 'Test 1', 'planet_class': 'Rocky body', 'radius': 2e6,
                           'rings': [{'Name': 'Test 1 A Ring', 'RingClass': 'eRingClass_Metalic', 'InnerRad': 3e6, 'OuterRad': 5e6}],
                           'materials': [{'Name': 'iron', 'Percent': 20.5}, {'Name': 'nickel', 'Percent': 15}]}]
            expedition_manager, carrier_tracker = Expeditions(), Carriers()
            def _html_local_body_target(self):
                return None
            def _planet_materials_store(self):
                return Sites()
            def _html_mining_store(self):
                return Mining()
        deck = Deck()
        class Catalogue:
            def request(self, *args):
                return {'status': 'ready', 'detail': '', 'system': {}}
        deck._system_map_catalogue = Catalogue()
        system = deck._html_system_map_workspace()['system']
        self.assertTrue(system['you']['docked'])
        self.assertEqual((system['you']['body_id'], system['you']['station']), (1, {'name': 'Port', 'type': 'Outpost', 'dist_ls': 12.5}))
        self.assertEqual([place['label'] for place in system['places']], ['Bio patch', 'Land here'])
        self.assertEqual(system['carriers'], [{'name': 'Mine', 'callsign': 'AAA-111', 'body': 'Test 1'}])
        planet = next(row for row in system['bodies'] if row['bodyId'] == 1)
        self.assertEqual(planet['rings'][0]['hotspots'], [{'material': 'Painite', 'count': 3}])
        self.assertEqual(planet['_facts']['materials'][0], {'name': 'Iron', 'percent': 20.5})


class LoadAndRingFixTests(unittest.TestCase):
    def test_surfaces_compile_quickly_bake_on_a_budget_and_rings_hold_still(self):
        materials = (ROOT/'web/dashboard/system-map/materials.js').read_text('utf-8')
        # Windows' D3D compiler unrolls constant loops: bounded by a uniform, the bake shader
        # compiles in about 5 s instead of 24.
        self.assertNotIn('for (int o = 0; o < 10; o++) { if (o >= oct) break;', materials)
        self.assertIn('o < min(oct, uLoop)', materials)
        # The bakes draw into a render target, so that is the variant warmed (no second, blocking compile).
        baker = materials[materials.index('class SurfaceBaker'):]
        self.assertLess(baker.index('setRenderTarget(warm)'), baker.index('compileAsync'))
        self.assertIn('this.maxBudget', baker, 'a pixel budget per frame, not eight rows')
        # A star in the ring plane must not flip each pixel between lit and unlit faces every frame.
        self.assertNotIn('camSide * ld >= 0.0 ?', materials)
        scene = (ROOT/'web/dashboard/system-map/scene.js').read_text('utf-8')
        warm = scene[scene.index('  warmUp(){'):scene.index('  setData(')]
        self.assertLess(warm.index('setRenderTarget(this.renderTarget)'), warm.index('compileAsync'))


class SystemMapBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True, args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def open(self, width=1600, height=1000):
        self.state = map_state()
        self.server = HtmlDashboardServer(ROOT/'web/dashboard', image_root=ROOT/'assets/images', command_callback=lambda _: True)
        self.addCleanup(self.server.stop)
        self.server.publish(self.state)
        self.context = self.browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce')
        self.addCleanup(self.context.close)
        page = self.context.new_page()
        self.errors = []
        page.on('pageerror', lambda e: self.errors.append(str(e)))
        page.on('console', lambda m: self.errors.append(m.text) if m.type == 'error' else None)
        self.addCleanup(lambda: self.assertEqual(self.errors, []))
        source = (ROOT/'web/dashboard/app.js').read_text('utf-8') + '\nwindow.__mapTest={showPage,renderDashboard(data){model=data;renderDashboard(data);},systemMapState};\n'
        page.route('**/app.js', lambda r: r.fulfill(content_type='text/javascript', body=source))
        page.goto(self.server.url)
        page.wait_for_function('() => !!window.__mapTest')
        page.wait_for_function('(name)=>document.querySelector("#sm-system")?.textContent===name', arg=SYSTEM)
        page.evaluate("() => {document.getElementById('boot').hidden=true;document.body.classList.add('ready');window.__mapTest.showPage('system-map');}")
        page.wait_for_function('() => window.__mapTest.systemMapState().frames>2', timeout=20000)
        return page

    def publish(self, page):
        self.server.publish(self.state)
        page.wait_for_timeout(200)

    def test_real_three_renderer_body_details_and_live_updates_keep_the_camera(self):
        page = self.open()
        self.assertEqual(page.evaluate('window.__mapTest.systemMapState().renderer'), 'three')
        page.locator('[data-sm-body="3"]').click()
        page.wait_for_function('() => window.__mapTest.systemMapState().selected===3')
        self.assertIn('Icy', page.locator('#sm-detail').inner_text())
        before = page.evaluate("() => {window.__mapCanvas=document.querySelector('#sm-stage canvas');return window.__mapTest.systemMapState().camera;}")
        self.state['system_map']['system']['bodies'][3]['_survey']['bio'] = 9
        added = copy.deepcopy(self.state['system_map']['system']['bodies'][2])
        added.update(bodyId=99, name=f'{SYSTEM} NEW SCAN')
        self.state['system_map']['system']['bodies'].append(added)
        self.publish(page)
        page.wait_for_function("() => document.querySelector('#sm-detail').textContent.includes('9 BIOLOGICAL')")
        self.assertEqual(page.evaluate('window.__mapTest.systemMapState().camera'), before)
        self.assertTrue(page.evaluate("window.__mapCanvas===document.querySelector('#sm-stage canvas')"))
        self.assertEqual(page.evaluate('window.__mapTest.systemMapState().bodies'), 8)

    def test_hidden_page_receives_new_system_without_rendering_frames(self):
        page = self.open()
        page.evaluate("window.__mapTest.showPage('overview')")
        frames = page.evaluate('window.__mapTest.systemMapState().frames')
        self.state['system_map']['system'].update(name='NEW JOURNAL SYSTEM', id64='42')
        self.state['system_map']['system']['bodies'][0]['name'] = 'NEW JOURNAL SYSTEM A'
        self.publish(page)
        page.wait_for_function("() => window.__mapTest.systemMapState().system==='NEW JOURNAL SYSTEM'")
        self.assertEqual(page.evaluate('window.__mapTest.systemMapState().frames'), frames)
        page.evaluate("window.__mapTest.showPage('system-map')")
        page.wait_for_function(f'() => window.__mapTest.systemMapState().frames>{frames}')
        from playwright.sync_api import expect
        expect(page.locator('#sm-system')).to_have_text('NEW JOURNAL SYSTEM')

    def test_scale_time_layers_and_unknown_positions_are_explicit(self):
        page = self.open()
        page.locator('[data-sm="scale"]').click()
        self.assertTrue(page.evaluate('window.__mapTest.systemMapState().trueScale'))
        page.locator('[data-sm="orbits"]').click()
        self.assertEqual(page.locator('[data-sm="orbits"]').get_attribute('aria-pressed'), 'false')
        page.locator('#sm-speed').select_option('0')
        page.wait_for_function("() => !document.querySelector('#sm-clock').textContent.includes('LIVE')")
        before = page.locator('#sm-clock').inner_text()
        page.locator('[data-sm="forward"]').click()
        page.wait_for_function('(before)=>document.querySelector("#sm-clock").textContent!==before', arg=before)
        page.locator('[data-sm="live"]').click()
        page.wait_for_function("() => document.querySelector('#sm-clock').textContent.includes('LIVE')")
        self.state['system_map']['system']['bodies'][2]['_resolved'] = False
        self.publish(page)
        page.locator('[data-sm-body="2"]').click()
        self.assertIn('Position unresolved', page.locator('#sm-detail').inner_text())
        self.assertFalse(page.evaluate('window.__mapTest.systemMapState().trueScale'))

    def test_explore_opens_the_chosen_body_in_the_new_tab(self):
        page = self.open()
        state = snapshot_state()
        state.update(profile=self.state['profile'], system_map=self.state['system_map'], boot={'active': False})
        state['workspace'] = {'page': 'explore', 'ready': True, 'data': workspace_data()}
        page.evaluate('state=>window.__mapTest.renderDashboard(state)', state)
        page.evaluate("window.__mapTest.showPage('explore')")
        page.locator('#explore-tab-system').click()
        page.locator('#body-workboard .body-row[data-body-id="4"] .body-select').click()
        page.locator('.body-more-actions [data-system-map-body]').click()
        page.wait_for_selector('[data-page-name="explore"].active #explore-view-map:not([hidden])')
        page.wait_for_function('() => window.__mapTest.systemMapState().selected===4')
        self.assertIn(f'{SYSTEM} B 1', page.locator('#sm-detail').inner_text())
        self.assertEqual(page.locator('#system-orrery-canvas').count(), 0)

    def test_expanded_map_and_large_text_remain_usable(self):
        page = self.open()
        page.locator('[data-sm="expand"]').click()
        self.assertFalse(page.locator('.sm-hierarchy').is_visible())
        self.assertTrue(page.locator('[data-sm="live"]').is_visible())
        page.locator('[data-sm="expand"]').click()
        for width, height in ((1280, 800), (960, 700), (600, 800)):
            page.set_viewport_size({'width': width, 'height': height})
            page.evaluate("async()=>{const text=await import('/text-size.js');text.applyTextSize(135,13);}")
            page.wait_for_timeout(80)
            report = page.evaluate("""()=>({wide:document.querySelector('.pages').scrollWidth-document.querySelector('.pages').clientWidth,
                stage:document.querySelector('#sm-stage').getBoundingClientRect().height,
                clock:document.querySelector('#sm-clock').getBoundingClientRect().width})""")
            self.assertLessEqual(report['wide'], 2, (width, report))
            self.assertGreater(report['stage'], 150)

    def open_orbit(self):
        page = self.open()
        self.state['system_map']['system'] = orbit_system()
        self.publish(page)
        page.wait_for_function("() => window.__mapTest.systemMapState().system==='Orbit' && window.__mapTest.systemMapState().you===2")
        return page

    def test_the_map_is_a_tab_of_explore(self):
        page = self.open()
        self.assertEqual(page.locator('.nav-item[data-page="system-map"]').count(), 0)
        self.assertEqual(page.locator('[data-page-name="system-map"]').count(), 0)
        self.assertEqual(page.locator('#explore-tab-map').get_attribute('aria-selected'), 'true')
        self.assertTrue(page.locator('[data-page-name="explore"].active #explore-view-map #system-map-workspace').is_visible())
        self.assertEqual(page.locator('#explore-orrery').count(), 0, 'the old orrery area is gone')
        # Another Explore tab stops the frames but keeps the scene, warm, for coming back.
        page.locator('#explore-tab-system').click()
        page.wait_for_function('() => !window.__mapTest.systemMapState().active')
        self.assertEqual(page.evaluate('window.__mapTest.systemMapState().renderer'), 'three')

    def test_you_the_target_stations_carriers_and_places_are_marked(self):
        page = self.open_orbit()
        state = page.evaluate('window.__mapTest.systemMapState()')
        self.assertEqual((state['you'], state['target']), (2, 4))
        placed = {row['name']: row['body'] for row in state['placed']}
        self.assertEqual(placed['Orbit Port'], 1, 'placed at the body that was at its reported distance')
        self.assertEqual(placed['Test Carrier X1X-2YZ'], 4)
        self.assertIn('LANDED · 1 a', page.locator('#sm-you').text_content())
        page.locator('[data-sm-body="1"]').click()
        detail = page.locator('#sm-detail').inner_text()
        for text in ('Orbit Port', 'Rim Hub', 'Painite ×2', 'FROM YOU'):
            self.assertIn(text, detail)
        page.locator('#sm-you').click()
        page.wait_for_function('() => window.__mapTest.systemMapState().selected===2')
        detail = page.locator('#sm-detail').inner_text()
        self.assertIn('YOU ARE HERE', detail)
        self.assertIn('Ice field', detail)

    def test_eclipses_and_day_and_night_on_a_locked_moon(self):
        page = self.open_orbit()
        page.locator('[data-sm-body="2"]').click()
        page.wait_for_function("() => document.querySelector('#sm-detail').textContent.includes('DAY & NIGHT')", timeout=20000)
        detail = page.locator('#sm-detail').inner_text()
        self.assertIn('ECLIPSES', detail)
        self.assertRegex(detail, r'1 · (TOTAL|\d+% COVERED)', 'the planet eclipses the star once an orbit')
        self.assertRegex(detail, r'Ice field\s+(DAY|NIGHT) · STAR -?\d+° · (SETS|RISES) IN')

    def test_overview_keeps_families_apart_and_partial_orbits_are_approximate(self):
        page = self.open_orbit()
        layout = page.evaluate('window.__mapTest.systemMapState().layout')
        self.assertLess(layout['2'], layout['3'], 'moons keep their order')
        self.assertGreater(layout['4'] - layout['1'], layout['3'], "the neighbour sits outside the planet's moons")
        self.assertIn('≈', page.locator('[data-sm-body="5"]').text_content())
        page.locator('[data-sm-body="5"]').click()
        self.assertIn('Approximate', page.locator('#sm-detail').inner_text())

    def test_sky_view_survey_layer_quality_and_labels(self):
        page = self.open_orbit()
        page.locator('[data-sm-body="1"]').click()
        page.locator('[data-sm="surface"]').click()
        page.wait_for_function('() => window.__mapTest.systemMapState().surface')
        self.assertTrue(page.locator('#sm-surface').is_visible())
        self.assertGreater(page.locator('#sm-surface-target option').count(), 1)
        page.locator('[data-sm="surface-exit"]').click()
        page.wait_for_function('() => !window.__mapTest.systemMapState().surface')
        page.locator('[data-sm="survey"]').click()
        page.locator('[data-sm-filter="landable"]').click()
        self.assertEqual(page.evaluate('window.__mapTest.systemMapState().survey'), {'on': True, 'filter': 'landable'})
        self.assertGreater(page.locator('.sm-body.dimmed').count(), 0)
        self.assertEqual(page.locator('.sm-body:not(.dimmed)[data-sm-body="2"]').count(), 1)
        page.locator('#sm-quality').select_option('low')
        self.assertEqual(page.evaluate('window.__mapTest.systemMapState().quality'), 'low')
        page.locator('[data-sm="fit"]').click()
        page.wait_for_timeout(500)
        outside = page.evaluate("""() => {const s=document.querySelector('#sm-stage').getBoundingClientRect();
          return [...document.querySelectorAll('#sm-stage .sm-label:not([hidden])')].filter(l=>{const r=l.getBoundingClientRect();
            return r.right>s.right+1||r.left<s.left-1;}).map(l=>l.textContent);}""")
        self.assertEqual(outside, [], 'labels stay inside the map')

    def test_switching_commander_releases_the_old_scene_and_view_preferences(self):
        page = self.open()
        page.locator('[data-sm="orbits"]').click()
        page.locator('[data-sm="expand"]').click()
        page.evaluate("() => {window.__oldMapCanvas=document.querySelector('#sm-stage canvas');}")
        self.state['profile']['key'] = 'another-commander'
        self.state['system_map']['profile_key'] = 'another-commander'
        self.state['system_map']['system'].update(name='OTHER COMMANDER SYSTEM', id64='42')
        self.state['workspace']['page'] = 'overview'
        self.publish(page)
        page.wait_for_function("() => !window.__oldMapCanvas.isConnected")
        page.evaluate("window.__mapTest.showPage('system-map')")
        page.wait_for_function("() => window.__mapTest.systemMapState().system==='OTHER COMMANDER SYSTEM'")
        self.assertEqual(page.locator('[data-sm="orbits"]').get_attribute('aria-pressed'), 'true')
        self.assertEqual(page.locator('[data-sm="expand"]').get_attribute('aria-pressed'), 'false')


if __name__ == '__main__':
    unittest.main()
