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


def draw_chrome(canvas, width, height, accent=None, bracket_len=12, bg=_BG, tags=None,
                scanlines=True, scanline_step=3, scanline_color=_SCANLINE):
    """Draws background fill, scanline texture, tri-line stripe border, and
    corner brackets directly onto `canvas` at (0, 0, width, height).

    Pass `tags` (e.g. "bg") if the overlay needs to tag_lower() this behind
    other canvas items/embedded widgets (see colony_overlay.py).
    """
    # Resolve the active accent at draw time.  A COLOR_ACCENT default argument
    # would retain the startup theme even after live theme switching updates
    # this module's global.
    accent = accent or COLOR_ACCENT
    kwargs = {"tags": tags} if tags else {}
    canvas.create_rectangle(0, 0, width, height, fill=bg, outline="", **kwargs)
    if scanlines:
        for y in range(0, height, max(2, int(scanline_step))):
            canvas.create_line(0, y, width, y, fill=scanline_color, width=1, **kwargs)

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


def draw_crt_vignette(canvas, width, height, intensity="Subtle", tags=None):
    """Simulate dark CRT edge falloff with inexpensive inset border lines."""
    level = str(intensity or "Subtle").lower()
    layers = {"subtle": 2, "standard": 4, "strong": 6}.get(level, 2)
    colors = ("#020304", "#030507", "#04070a", "#05090d", "#060b10", "#070d13")
    kwargs = {"tags": tags} if tags else {}
    for inset in range(layers):
        canvas.create_rectangle(
            7 + inset, 7 + inset, width - 8 - inset, height - 8 - inset,
            outline=colors[min(inset, len(colors) - 1)], width=1, **kwargs,
        )


def draw_crt_noise(canvas, width, height, intensity="Subtle", tags=None):
    """Draw deterministic, very faint phosphor speckles behind HUD content."""
    level = str(intensity or "Subtle").lower()
    count = {"subtle": 10, "standard": 22, "strong": 38}.get(level, 10)
    kwargs = {"tags": tags} if tags else {}
    usable_w, usable_h = max(1, width - 24), max(1, height - 24)
    for index in range(count):
        # Fixed integer sequence: stable texture without a random dependency or
        # visible crawling whenever normal HUD data causes a redraw.
        x = 12 + ((index * 83 + 29) % usable_w)
        y = 12 + ((index * 47 + 17) % usable_h)
        color = "#0c151b" if index % 3 else "#101a20"
        canvas.create_line(x, y, x + (1 if index % 2 else 2), y, fill=color, width=1, **kwargs)
