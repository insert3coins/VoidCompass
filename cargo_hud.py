"""Compact, theme-aware cargo manifest overlay."""
from application_runtime import OverlayWindowState
import math
from config import save_config
import overlay_chrome
import themes
WIDTH = 360
MIN_HEIGHT = 148
MAX_ROWS = 14
VEHICLE_CARGO_CAPACITIES = {'SCARAB': 4, 'SCORPION': 2, 'RHINO': 72}

def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)

def _cargo_name(item):
    value = str(item.get('Name_Localised') or item.get('Name') or 'Unknown').strip()
    if value.startswith('$'):
        value = value[1:]
    if value.endswith(';'):
        value = value[:-1]
    return value.replace('_name', '').replace('_', ' ').title() or 'Unknown'

def _cargo_owner(vessel='Ship', vehicle_name=''):
    """Return stable journal and presentation labels for the active cargo hold."""
    vessel_text = str(vessel or 'Ship').strip()
    vessel_key = vessel_text.casefold()
    if vessel_key == 'ship':
        return ('Ship', 'SHIP')
    if vessel_key == 'srv':
        vehicle = str(vehicle_name or 'SRV').strip().upper()
        if vehicle not in {'NOMAD', 'SCARAB', 'SCORPION', 'RHINO', 'SRV'}:
            vehicle = 'SRV'
        return ('SRV', vehicle)
    return (vessel_text or 'Unknown', str(vehicle_name or vessel_text or 'UNKNOWN').strip().upper())

def cargo_capacity_for(vessel='Ship', vehicle_name='', ship_capacity=0):
    """Resolve a capacity without ever leaking the ship hold into an SRV."""
    vessel, owner = _cargo_owner(vessel, vehicle_name)
    if vessel == 'Ship':
        return max(0, _integer(ship_capacity))
    return max(0, _integer(VEHICLE_CARGO_CAPACITIES.get(owner, 0)))

def build_cargo_model(inventory, capacity=0, vessel='Ship', vehicle_name=''):
    """Normalise Cargo.json inventory and expose mission/stolen distinctions."""
    stacks = {}
    for item in inventory or []:
        if not isinstance(item, dict):
            continue
        name = _cargo_name(item)
        count = max(0, _integer(item.get('Count')))
        if not count:
            continue
        key = name.casefold()
        row = stacks.setdefault(key, {'name': name, 'count': 0, 'mission': 0, 'stolen': 0})
        row['count'] += count
        if item.get('MissionID') not in (None, '', 0, '0'):
            row['mission'] += count
        row['stolen'] += min(count, max(0, _integer(item.get('Stolen'))))
    rows = sorted(stacks.values(), key=lambda row: row['name'].casefold())
    total = sum((row['count'] for row in rows))
    vessel, owner = _cargo_owner(vessel, vehicle_name)
    capacity_value = cargo_capacity_for(vessel, owner, capacity)
    utilisation = None
    if capacity_value:
        utilisation = max(0.0, min(1.0, total / capacity_value))
    return {'rows': rows, 'total': total, 'capacity': capacity_value, 'free': max(0, capacity_value - total) if capacity_value else None, 'utilisation': utilisation, 'mission': sum((row['mission'] for row in rows)), 'stolen': sum((row['stolen'] for row in rows)), 'vessel': vessel, 'owner': owner, 'hold_key': f'{vessel.casefold()}:{owner.casefold()}', 'capacity_known': bool(capacity_value)}

class CargoHUD:

    def __init__(self, root, config):
        self.win = OverlayWindowState(root)
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._last_inventory = []
        self._last_capacity = 0
        self._last_vessel = 'Ship'
        self._last_vehicle_name = ''
        self._last_render_key = None
        self._html_render_model = build_cargo_model([], 0, 'Ship', '')
        self._height = MIN_HEIGHT
        self._save_job = None
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        default_x = screen_width - WIDTH - 20
        default_y = screen_height // 2 - 200
        x = self._safe_int(self.config.get('cargo_hud_x'), default_x)
        y = self._safe_int(self.config.get('cargo_hud_y'), default_y)
        self._desired_pos = (x, y)
        self.win.geometry(overlay_chrome.position_geometry(x, y, WIDTH, self._height))
        self.win.call_later(0, self._apply_initial_position)
        self.win.call_later(250, self._apply_initial_position)
        self.win.call_later(700, self._apply_initial_position)
        self.update([], 0)

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except Exception:
            return int(default)

    def _apply_initial_position(self):
        try:
            x, y = self._desired_pos
            self.win.geometry(overlay_chrome.position_geometry(x, y, WIDTH, self._height))
        except Exception:
            pass

    def _write_config(self):
        save_config(self.config)

    def _schedule_config_save(self):
        if self._save_job:
            try:
                self.win.cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.win.call_later(250, self._flush_scheduled_save)

    def _flush_scheduled_save(self):
        self._save_job = None
        try:
            self._write_config()
        except Exception:
            pass

    def update(self, inventory, capacity=0, vessel='Ship', vehicle_name=''):
        inventory = list(inventory or [])
        self._last_inventory = list(inventory)
        self._last_capacity = capacity
        self._last_vessel = vessel
        self._last_vehicle_name = vehicle_name
        model = build_cargo_model(inventory, capacity, vessel, vehicle_name)
        self._html_render_model = model
        render_key = repr(model)
        if render_key == self._last_render_key:
            return
        self._last_render_key = render_key
        shown = model['rows'][:MAX_ROWS]
        overflow = model['rows'][MAX_ROWS:]
        row_count = max(1, len(shown)) + (1 if overflow else 0)
        self._height = max(MIN_HEIGHT, 116 + row_count * 21 + 28)
        x, y = self._desired_pos

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        self._last_render_key = None
        self.update(self._last_inventory, self._last_capacity, self._last_vessel, self._last_vehicle_name)
