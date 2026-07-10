"""Shared SrvSurvey-style chrome for chroma-key canvas overlays.

Draws a tri-line accent stripe border (dim/bright/dim), corner brackets,
and a faint scanline background texture — the same technique used in the
redesigned navigation HUD (hud.py). Any overlay's redraw method can call
draw_chrome(canvas, width, height) as its first drawing call to pick up
the same visual language.
"""

from config import COLOR_ACCENT

_BG = "#010101"
_SCANLINE = "#0a0f14"


def dim_color(hexcolor, factor=0.35):
    hexcolor = hexcolor.lstrip("#")
    r, g, b = int(hexcolor[0:2], 16), int(hexcolor[2:4], 16), int(hexcolor[4:6], 16)
    return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"


def draw_chrome(canvas, width, height, accent=COLOR_ACCENT, bracket_len=12, bg=_BG, tags=None):
    """Draws background fill, scanline texture, tri-line stripe border, and
    corner brackets directly onto `canvas` at (0, 0, width, height).

    Pass `tags` (e.g. "bg") if the overlay needs to tag_lower() this behind
    other canvas items/embedded widgets (see colony_overlay.py).
    """
    kwargs = {"tags": tags} if tags else {}
    canvas.create_rectangle(0, 0, width, height, fill=bg, outline="", **kwargs)
    for y in range(0, height, 3):
        canvas.create_line(0, y, width, y, fill=_SCANLINE, width=1, **kwargs)

    dim = dim_color(accent)
    for y, c in ((3, dim), (4, accent), (5, dim)):
        canvas.create_line(4, y, width - 4, y, fill=c, width=1, **kwargs)
    for y, c in ((height - 6, dim), (height - 5, accent), (height - 4, dim)):
        canvas.create_line(4, y, width - 4, y, fill=c, width=1, **kwargs)
    canvas.create_line(2, 2, 2, height - 2, fill=dim, width=1, **kwargs)
    canvas.create_line(width - 2, 2, width - 2, height - 2, fill=dim, width=1, **kwargs)

    for x0, y0, dx, dy in ((3, 3, 1, 1), (width - 3, 3, -1, 1), (3, height - 3, 1, -1), (width - 3, height - 3, -1, -1)):
        canvas.create_line(x0, y0, x0 + dx * bracket_len, y0, fill=accent, width=2, **kwargs)
        canvas.create_line(x0, y0, x0, y0 + dy * bracket_len, fill=accent, width=2, **kwargs)
