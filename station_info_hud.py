"""Exploration-first station overlay built from Elite journal evidence.

The renderer consumes the station state captured by :mod:`dashboard` from
``Docked``/``Location`` events.  The model builder is intentionally independent
of Tk so journal examples can be validated without constructing a window.
"""
from application_runtime import OverlayWindowState
import re
from config import save_config
import overlay_chrome
import themes
_CHROMA = '#ff00ff'
WIDTH = 520
_CORE_SERVICES = (('REFUEL', ('refuel',)), ('REPAIR', ('repair',)), ('REARM', ('rearm',)), ('OUTFITTING', ('outfitting',)))
_EXPLORATION_SERVICES = (('UNIVERSAL CARTOGRAPHICS', ('exploration',)), ('VISTA GENOMICS', ('vistagenomics',)), ('SEARCH & RESCUE', ('searchrescue',)), ('COLONISATION', ('registeringcolonisation', 'colonisationconstruction')))
_SPECIAL_SERVICES = (('SHIPYARD', ('shipyard',)), ('TECH BROKER', ('techbroker',)), ('MATERIAL TRADER', ('materialtrader',)), ('BLACK MARKET', ('blackmarket',)), ('ENGINEER', ('engineer',)))
_STATION_TYPE_LABELS = {'asteroidbase': 'ASTEROID BASE', 'coriolis': 'CORIOLIS STARPORT', 'fleetcarrier': 'FLEET CARRIER', 'megaship': 'MEGASHIP', 'ocellus': 'OCELLUS STARPORT', 'orbis': 'ORBIS STARPORT', 'outpost': 'OUTPOST', 'planetaryconstructiondepot': 'SURFACE DEPOT', 'spaceconstructiondepot': 'ORBITAL DEPOT', 'surfacestation': 'SURFACE PORT'}

def _truncate(text, max_chars):
    text = str(text or '')
    return text if len(text) <= max_chars else text[:max_chars - 1] + '…'

def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)

def _display_name(value):
    """Turn a localised label or Frontier token into compact readable text."""
    text = str(value or '').strip()
    if not text:
        return ''
    if text.startswith('$') and text.endswith(';'):
        text = text[1:-1]
        text = re.sub('^(economy|government|stationtype)_', '', text, flags=re.I)
    text = text.replace('_', ' ')
    text = re.sub('(?<=[a-z])(?=[A-Z])', ' ', text)
    return ' '.join(text.split()).strip()

def _credits(value):
    value = max(0, _safe_int(value))
    if value >= 1000000000:
        return f'{value / 1000000000:.2f} B CR'
    if value >= 1000000:
        return f'{value / 1000000:.1f} M CR'
    if value >= 1000:
        return f'{value / 1000:.0f} K CR'
    return f'{value:,} CR'

def _service_keys(services):
    return {str(service or '').strip().casefold().replace('_', '') for service in services or () if service}

def _has_service(service_keys, aliases):
    return any((alias.casefold().replace('_', '') in service_keys for alias in aliases))

def _service_rows(definitions, service_keys):
    return [{'label': label, 'available': _has_service(service_keys, aliases)} for label, aliases in definitions]

def _economy_summary(economies, fallback=None):
    rows = []
    for economy in economies or ():
        if not isinstance(economy, dict):
            continue
        name = _display_name(economy.get('Name_Localised') or economy.get('Name'))
        if not name:
            continue
        proportion = economy.get('Proportion')
        try:
            proportion = float(proportion)
        except (TypeError, ValueError):
            proportion = None
        rows.append((name, proportion))
    rows.sort(key=lambda item: item[1] if item[1] is not None else -1, reverse=True)
    rows = rows[:3]
    valid_percentages = bool(rows) and all((value is not None and 0 <= value <= 1 for _, value in rows)) and (sum((value for _, value in rows)) <= 1.05)
    if valid_percentages:
        return ' · '.join((f'{name} {value * 100:.0f}%' for name, value in rows))
    if rows:
        return ' · '.join((name for name, _ in rows))
    return _display_name(fallback)

def _station_type_label(station_type):
    raw = str(station_type or '').strip()
    key = raw.casefold().replace(' ', '').replace('_', '')
    return _STATION_TYPE_LABELS.get(key) or _display_name(raw).upper() or 'STATION'

def _same_market_id(left, right):
    if left in (None, '') or right in (None, ''):
        return False
    try:
        return int(left) == int(right)
    except (TypeError, ValueError):
        return str(left).strip().casefold() == str(right).strip().casefold()

def build_station_model(dash):
    """Return a truthful, renderer-neutral station status card."""
    service_keys = _service_keys(getattr(dash, 'current_station_services', None))
    carrier = getattr(getattr(dash, 'carrier_tracker', None), 'carrier_data', None) or {}
    market_id = getattr(dash, 'current_station_market_id', None)
    is_personal_carrier = _same_market_id(market_id, carrier.get('carrier_id'))
    station_type = _station_type_label(getattr(dash, 'current_station_type', None))
    pads = getattr(dash, 'current_station_landing_pads', None) or {}
    pad_parts = []
    for key, short in (('Large', 'L'), ('Medium', 'M'), ('Small', 'S')):
        value = _safe_int(pads.get(key))
        if value:
            pad_parts.append(f'{short} {value}')
    distance = getattr(dash, 'current_station_dist_ls', None)
    try:
        distance_text = f'{float(distance):,.0f} Ls' if distance is not None else ''
    except (TypeError, ValueError):
        distance_text = ''
    faction = getattr(dash, 'current_station_faction', None) or {}
    authority_parts = []
    for value in (faction.get('name'), getattr(dash, 'current_station_government', None), getattr(dash, 'current_station_allegiance', None), faction.get('state')):
        label = _display_name(value)
        if label and label.casefold() != 'none' and (label.casefold() not in {item.casefold() for item in authority_parts}):
            authority_parts.append(label)
    state = getattr(dash, 'companion_state', None) or {}
    exploration_value = max(0, _safe_int(state.get('unsold_exploration_cr')))
    bio_value = max(0, _safe_int(state.get('unsold_bio_cr')))
    bio_bonus = max(0, _safe_int(state.get('unsold_bio_bonus_potential_cr')))
    bio_samples = max(0, _safe_int(state.get('unsold_bio_samples')))
    data_rows = []
    if exploration_value:
        data_rows.append({'label': 'EXPLORATION', 'value': _credits(exploration_value), 'available': 'exploration' in service_keys, 'service': 'CARTOGRAPHICS'})
    if bio_value:
        value = _credits(bio_value)
        if bio_bonus:
            value = f"{value.removesuffix(' CR')}–{_credits(bio_value + bio_bonus)}"
        data_rows.append({'label': f'BIOLOGY · {bio_samples} ANALYSES' if bio_samples else 'BIOLOGY', 'value': value, 'available': 'vistagenomics' in service_keys, 'service': 'VISTA'})
    station_state = _display_name(getattr(dash, 'current_station_state', None))
    type_parts = [station_type]
    if station_state and station_state.casefold() not in ('none', 'normal'):
        type_parts.append(station_state.upper())
    return {'station': getattr(dash, 'current_station_name', None) or 'UNKNOWN STATION', 'system': getattr(dash, 'current_sys', None) or 'UNKNOWN SYSTEM', 'type': ' · '.join(type_parts), 'badge': 'PERSONAL CARRIER' if is_personal_carrier else 'DOCKED', 'is_personal_carrier': is_personal_carrier, 'distance': distance_text, 'pads': ' · '.join(pad_parts), 'core_services': _service_rows(_CORE_SERVICES, service_keys), 'exploration_services': _service_rows(_EXPLORATION_SERVICES, service_keys), 'special_services': [row['label'] for row in _service_rows(_SPECIAL_SERVICES, service_keys) if row['available']], 'data_rows': data_rows, 'economies': _economy_summary(getattr(dash, 'current_station_economies', None), getattr(dash, 'current_station_economy', None)), 'authority': ' · '.join(authority_parts)}

class StationInfoHUD:

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._last_model = None
        self._hide_job = None
        self._visible = False
        self._docked_context = False
        self.win = OverlayWindowState(root)
        x = _safe_int(config.get('station_info_hud_x'), 30)
        y = _safe_int(config.get('station_info_hud_y'), 380)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self.win.withdraw()

    def show(self):
        if not self._docked_context:
            return False
        try:
            x = _safe_int(self.config.get('station_info_hud_x'), 30)
            y = _safe_int(self.config.get('station_info_hud_y'), 380)
            self.win.geometry(overlay_chrome.position_geometry(x, y))
            self.win.deiconify()
            self._visible = True
            return True
        except Exception:
            return False

    def hide(self):
        if self._hide_job:
            try:
                self.win.cancel(self._hide_job)
            except Exception:
                pass
            self._hide_job = None
        try:
            self.win.withdraw()
        except Exception:
            pass
        self._visible = False

    def _schedule_hide(self):
        if self._hide_job:
            try:
                self.win.cancel(self._hide_job)
            except Exception:
                pass
            self._hide_job = None
        if not self.config.get('station_info_auto_hide_enabled', False):
            return
        timeout_s = max(5, _safe_int(self.config.get('station_info_timeout_s'), 30))
        self._hide_job = self.win.call_later(timeout_s * 1000, self._auto_hide)

    def _auto_hide(self):
        self._hide_job = None
        self.hide()

    def on_docked(self, dash):
        self.reconcile(dash, present=True)

    def on_undocked(self):
        """Clear presentation authority while retaining the last station model."""
        self._docked_context = False
        self.hide()

    def apply_auto_hide_setting(self, dash, enabled):
        """Apply the live Station Link policy without waiting for a redock.

        The HTML settings surface can change this while the station card is
        already mapped.  Treat that as a fresh presentation: cancel any old
        countdown, keep the dock link visible, and only arm a new countdown
        when auto-hide is enabled.
        """
        self.config['station_info_auto_hide_enabled'] = bool(enabled)
        docked = bool(getattr(dash, 'current_docked', False))
        station = getattr(dash, 'current_station_name', None)
        self._docked_context = bool(docked and station)
        if not self._docked_context:
            self.hide()
            return False
        self.refresh(dash)
        self.show()
        self._schedule_hide()
        return True

    def reconcile(self, dash, present=False):
        """Bring the overlay into line with the settled journal dock state.

        ``present`` is reserved for a real docking/login transition.  Ordinary
        batches may refresh an already-visible card, but must not resurrect a
        card the commander deliberately auto-hid or restart its hide timer.
        """
        docked = bool(getattr(dash, 'current_docked', False))
        station = getattr(dash, 'current_station_name', None)
        self._docked_context = bool(docked and station)
        if not self._docked_context:
            self.hide()
            return False
        self.refresh(dash)
        if present:
            self.show()
            self._schedule_hide()
        return bool(self._visible)

    def refresh(self, dash):
        """Repaint live docked data without restarting the auto-hide timer."""
        model = build_station_model(dash)
        if model == self._last_model:
            return
        self._last_model = model
        self._redraw(model)

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        if self._last_model is not None:
            self._redraw(self._last_model)

    def _redraw(self, model):
        self._last_model = model
