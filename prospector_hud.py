"""Theme-aware prospector analysis overlay for mining journal events."""
from application_runtime import OverlayWindowState
from config import save_config
import overlay_chrome
import themes
_CHROMA = '#ff00ff'
_CONTENT = {'high': ('HIGH', 'green'), 'medium': ('MED', 'yellow'), 'med': ('MED', 'yellow'), 'low': ('LOW', 'dim')}

def _content_info(raw):
    """Return (display label, theme tone) for the asteroid content field."""
    value = (raw.get('Content_Localised') or raw.get('Content') or '').lower()
    value = value.replace('$asteroidmaterialcontent_', '').replace(';', '').strip()
    if 'high' in value:
        return _CONTENT['high']
    if 'med' in value:
        return _CONTENT['medium']
    if 'low' in value:
        return _CONTENT['low']
    return (value.upper() or 'UNKNOWN', 'text')

def _mining_type(raw):
    value = (raw.get('MiningType_Localised') or raw.get('MiningType') or '').lower()
    value = value.replace('$asteroidtype_', '').replace(';', '').strip()
    return value.title() or 'Asteroid'

def _clean_token(value):
    value = str(value or '').strip()
    if value.startswith('$'):
        value = value[1:]
    if value.endswith(';'):
        value = value[:-1]
    return value.title()

def _mat_name(item):
    return _clean_token(item.get('Name_Localised') or item.get('Name'))

def _core_name(raw):
    value = raw.get('MotherlodeMaterial_Localised') or raw.get('MotherlodeMaterial')
    return _clean_token(value) or None

def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)

def build_prospector_model(raw, refined=None):
    """Normalise one ProspectedAsteroid event for any future renderer."""
    raw = raw if isinstance(raw, dict) else {}
    materials = []
    for item in raw.get('Materials') or []:
        if not isinstance(item, dict):
            continue
        name = _mat_name(item)
        if not name:
            continue
        proportion = max(0.0, _as_float(item.get('Proportion')))
        materials.append({'name': name, 'proportion': round(proportion, 1)})
    materials.sort(key=lambda item: item['proportion'], reverse=True)
    refined_rows = []
    for name, count in (refined or {}).items():
        tonnes = max(0, int(_as_float(count)))
        if name and tonnes:
            refined_rows.append({'name': str(name), 'tonnes': tonnes})
    refined_rows.sort(key=lambda item: (-item['tonnes'], item['name'].lower()))
    remaining = raw.get('Remaining')
    remaining_value = None if remaining is None else max(0.0, _as_float(remaining))
    content_label, content_tone = _content_info(raw)
    core_material = _core_name(raw)
    return {'mining_type': _mining_type(raw), 'content_label': content_label, 'content_tone': content_tone, 'remaining': remaining_value, 'core_material': core_material, 'materials': materials, 'refined': refined_rows, 'refined_total': sum((item['tonnes'] for item in refined_rows))}

class ProspectorHUD:
    WIDTH = 380
    MAX_MATERIALS = 10
    _MAT_H = 21
    _MIN_H = 146

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._last_raw = None
        self._refined = {}
        self._hide_job = None
        self._html_render_model = build_prospector_model({}, {})
        self.win = OverlayWindowState(root)
        screen_h = root.winfo_screenheight()
        x = int(config.get('prospector_hud_x', 30))
        y = int(config.get('prospector_hud_y', max(30, screen_h - 320)))
        self._desired_pos = (x, y)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self.win.withdraw()

    def show(self):
        try:
            x = int(self.config.get('prospector_hud_x', 30))
            y = int(self.config.get('prospector_hud_y', 600))
            self._desired_pos = (x, y)
            self.win.geometry(overlay_chrome.position_geometry(x, y))
            self.win.deiconify()
        except Exception:
            pass

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

    def _schedule_hide(self):
        if self._hide_job:
            try:
                self.win.cancel(self._hide_job)
            except Exception:
                pass
        timeout_s = max(5, int(self.config.get('prospector_hud_timeout_s') or 45))
        self._hide_job = self.win.call_later(timeout_s * 1000, self._auto_hide)

    def _auto_hide(self):
        self._hide_job = None
        self.hide()

    def update(self, raw):
        self._last_raw = raw
        self._refined = {}
        self._redraw()
        self.show()
        self._schedule_hide()

    def add_refined(self, material):
        if not material or not self._last_raw:
            return
        material = _clean_token(material)
        self._refined[material] = self._refined.get(material, 0) + 1
        self._redraw()

    def _redraw(self):
        self._html_render_model = build_prospector_model(self._last_raw or {}, self._refined)

    def apply_theme(self, palette=None):
        """Apply the active commander palette without moving the overlay."""
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        self._redraw()
