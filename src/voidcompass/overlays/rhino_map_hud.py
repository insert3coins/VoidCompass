"""Rhino Map (5.5.18): the ground round you while you work the Rhino, in an
overlay of its own. It took over the Galaxy Minimap in 5.5.17; now the
minimap stays the galaxy and this one shows only while there's ground to map
(surface_map.wants_surface): in the Rhino, or while your rigs are out. The
model is surface_map.build_surface_map; web/rhino_map draws it."""

from voidcompass.core.overlay_registry import overlay_text_scale
from voidcompass.overlays.colony_needs_hud import ColonyNeedsHUD, _integer
from voidcompass.overlays.galaxy_minimap_hud import DEFAULT_SIZE, SIZES


def rhino_map_size(config):
    size = _integer((config or {}).get("rhino_map_size"), DEFAULT_SIZE)
    return size if size in SIZES else DEFAULT_SIZE


def rhino_map_text_scale(config):
    return overlay_text_scale(config, "rhino_map_hud")


class RhinoMapHUD(ColonyNeedsHUD):
    """Native window proxy for the Rhino Map page: shown while it has ground to map."""

    def update(self, model):
        # The page fits itself to its window from its design size (overlayfix.md).
        return super().update({**model, "size": rhino_map_size(self.config)} if model else None)

    def _position(self):
        return (_integer(self.config.get("rhino_map_hud_x"), 300),
                _integer(self.config.get("rhino_map_hud_y"), 600))
