import sys
import importlib.abc
class BlockTk(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('tkinter', '_tkinter')):
            raise RuntimeError('Tk imported by backend: ' + fullname)
sys.meta_path.insert(0, BlockTk())
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
import tempfile
import logging
from contextlib import nullcontext
errors=[]
class Errors(logging.Handler):
    def emit(self, record):
        if record.levelno >= logging.ERROR: errors.append(self.format(record))
logging.getLogger().addHandler(Errors())
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import config
import dashboard
from application_runtime import ApplicationRuntime
from html_overlay_runtime import HtmlOverlayRuntime

with tempfile.TemporaryDirectory() as folder:
    folder = Path(folder)
    values = config.load_config()
    values.update(journal_path=str(folder/'journals'), active_commander_name='Migration Test',
                  active_commander_profile='migration-test', active_commander_fid='FTEST',
                  automatic_profile_backups_enabled=False, screenshots_enabled=False,
                  eddn_enabled=False, edsm_enabled=False, galnet_enabled=False,
                  runtime_trace_enabled=False, last_app_version='5.4.2.6')
    (folder/'journals').mkdir()
    for key in ['overlay_enabled','cargo_overlay_enabled','carrier_overlay_enabled','prospector_overlay_enabled',
                'gravity_warning_overlay_enabled','station_info_overlay_enabled','survey_status_overlay_enabled',
                'toast_overlay_enabled','heartbeat_overlay_enabled','contact_scope_overlay_enabled']:
        values[key] = True
    for name in ['waypoints','specialists','adaptive_command','engineer_materials','companion_state','colonisation_data']:
        values[name+'_file']=str(folder/(name+'.json'))
    runtime=ApplicationRuntime()
    runtime._voidcompass_startup_splash = SimpleNamespace(_voidcompass_boot=SimpleNamespace(
        stop=lambda: None, set_runtime_status=lambda *args: None, _ready_emitted=True))
    with patch.object(config,'PROFILE_DIR',str(folder/'profiles')), patch.object(config,'CONFIG_FILE',str(folder/'config.json')), \
         patch.object(dashboard,'CONFIG_FILE',str(folder/'config.json')), patch.object(dashboard,'load_config',return_value=values), \
         (nullcontext() if '--renderers' in sys.argv else patch.object(HtmlOverlayRuntime,'_ensure_process')), patch.object(dashboard.MainDashboard,'check_updates'), \
         patch.object(dashboard.EDSMHandler,'queue_journal_event'), patch.object(dashboard.EDSMHandler,'queue_cargo_snapshot'), patch.object(dashboard.MainDashboard,'_restart_galnet_feed_schedule'), patch.object(dashboard.MainDashboard,'_start_eddn_market_upload'):
        config.save_active_profile_config(values)
        app=None
        try:
            app=dashboard.MainDashboard(runtime)
            runtime._voidcompass_app=app
            surfaces = runtime._voidcompass_html_overlay_runtime.surfaces
            expected = {'navigation'} | {
                spec[0] for attr, spec in app._HTML_OVERLAY_SPECS.items()
                if getattr(app, attr, None) is not None
            }
            assert expected <= set(surfaces), ('Missing startup renderers', expected - set(surfaces))
            assert not app.hud._html_window_payload()['visible']
            print('CONSTRUCTED WITHOUT TK; all created HUDs registered',flush=True)
            app.open_galaxy_map_page('http://127.0.0.1:9999')
            assert app.atlas._latest_snapshot
            print('ATLAS ready',flush=True)
            events=[{'event':'Location','StarSystem':'Sol','SystemAddress':1,'StarPos':[0,0,0], 'Docked':False},
                    {'event':'Scan','BodyName':'Sol A 1','BodyID':1,'SystemAddress':1,'PlanetClass':'Rocky body',
                     'Landable':True,'MassEM':1,'Radius':6371000,'SurfaceTemperature':250,'Materials':[{'Name':'iron','Percent':20}]},
                    {'event':'ProspectedAsteroid','Materials':[{'Name':'Gold','Proportion':12}], 'Remaining':100},
                    {'event':'Docked','StationName':'Test Carrier','StationType':'FleetCarrier','MarketID':123,'StarSystem':'Sol'},
                    {'event':'CarrierJump','Docked':True,'MarketID':123,'StationType':'FleetCarrier','StarSystem':'Achenar','SystemAddress':2,'StarPos':[1,2,3]}]
            for raw in events:
                raw['timestamp']='2026-09-08T00:00:00Z'
                event=app.watcher._normalize_event(raw)
                if event: app.process_event(event)
            app._apply_status_update({'Flags':1,'Flags2':0})
            print('JOURNAL REPLAY',app.current_sys,app._navigation_jump_phase,flush=True)
            for page in ['explore','planet-materials','profile','analytics','chronicle','mission','ground','mining','engineering','carrier','recon','achievements','ledger','settings']:
                result=app._html_workspace(page)
                assert result.get('ready'), (page,result.get('error'))
            app._finish_startup_presentation()
            assert app.hud._html_window_payload()['visible']
            assert app.hud._html_last_model['window']['visible']
            assert not runtime._voidcompass_startup_presentation_held
            assert not runtime._voidcompass_html_overlay_runtime.server._presentation_held
            assert runtime._voidcompass_html_overlay_runtime.server.window_manifest()['navigation']['window']['visible']

            def switch_profile():
                app._switch_commander_profile('Second Test', 'FTEST2')
                assert app.cmdr_name == 'Second Test' and app.atlas is None
                assert not getattr(app,'_navigation_carrier_schedule',None)
                print('PROFILE SWITCH isolated',flush=True)
                runtime.call_later(250, app.on_close)

            def present_overlay_examples():
                app.current_docked = False
                app.prospector_hud.update({'Materials':[{'Name':'Gold','Proportion':12}], 'Remaining':100})
                app.gravity_warning_hud.check_body('Test World', 5.0)
                app.survey_status_hud.resume(refresh=False)
                app.config['survey_status_show_all_bodies'] = True
                app.scan_items = [{'name':'Sol A 1','body_id':1,'planet_class':'Rocky body','landable':True,'bio_count':1}]
                app.survey_status_hud.update('Sol', 1, 2, app.scan_items, {})
                app.contact_scope_hud.resume(refresh=False)
                app.deep_space_contact_system = 'Sol'
                app.deep_space_contact_expected = 1
                app.deep_space_contacts = [{'name':'Notable Stellar Phenomena'}]
                app._refresh_contact_scope()
                app.toast_hud.push('Overlay check', 'Notification visibility', duration_s=30)
                app.on_planet = True
                app.current_latitude = 0.0
                app.current_longitude = 0.0
                app.current_heading = 0.0
                app.current_planet_radius = 1000000.0
                app.target_latlon_active = True
                app.target_lat, app.target_lon = 1.0, 1.0
                app.ground_popup_enabled = True
                app.config['ground_popup_enabled'] = True
                app.update_ground_target_ui()
                expected.add('ground')
                app._sync_html_overlay_windows()

            if '--renderers' in sys.argv:
                runtime.call_later(7500, present_overlay_examples)
            else:
                present_overlay_examples()

            def verify_renderers():
                surfaces=runtime._voidcompass_html_overlay_runtime.surfaces
                assert expected <= set(surfaces), expected - set(surfaces)
                missing=[name for name,surface in surfaces.items() if not surface.ready]
                assert not missing, missing
                for overlay_id in expected:
                    status = surfaces[overlay_id].host_status
                    assert status.get('visible') and not status.get('curtained'), (overlay_id, status)
                print('WEBVIEW HUDS registered, ready and visible:', ', '.join(sorted(expected)),flush=True)
                switch_profile()

            runtime.call_later(10000 if '--renderers' in sys.argv else 200,
                               verify_renderers if '--renderers' in sys.argv else switch_profile)
            runtime.call_later(15000,app.on_close)
            runtime.run()
            assert not errors, errors
            assert not any(name.startswith(('tkinter','_tkinter')) for name in sys.modules)
            print('CLOSED WITHOUT TK',flush=True)
        finally:
            if app is not None and not getattr(app,'_closing',False):
                runtime.call_later(250, app.on_close)
            overlay_runtime=getattr(runtime,'_voidcompass_html_overlay_runtime',None)
            if overlay_runtime: overlay_runtime.dispose()
            runtime.close()
