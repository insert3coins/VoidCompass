"""Shared SrvSurvey-style chrome for chroma-key canvas overlays.

Draws a tri-line accent stripe border (dim/bright/dim), corner brackets,
and a faint scanline background texture — the same technique used in the
redesigned navigation HUD (hud.py). Any overlay's redraw method can call
draw_chrome(canvas, width, height) as its first drawing call to pick up
the same visual language.
"""

import os

from config import COLOR_ACCENT

_BG = "#010101"
_SCANLINE = "#0a0f14"


def position_geometry(x, y, width=None, height=None):
    """Build an absolute Tk geometry string for any virtual-screen quadrant.

    ``+{x}+{y}`` produces invalid ``+-120`` fragments for monitors to the
    left or above the primary display.  Explicit signs keep Studio positions
    portable across the complete virtual desktop.
    """
    prefix = ""
    if width is not None and height is not None:
        prefix = f"{max(1, int(width))}x{max(1, int(height))}"
    return f"{prefix}{int(round(float(x))):+d}{int(round(float(y))):+d}"


def scaled_font(font, config):
    """Scale a Tk tuple font for the commander's overlay readability setting."""
    try:
        percent = max(75, min(200, int(float((config or {}).get("overlay_text_scale_percent", 100)))))
    except (TypeError, ValueError):
        percent = 100
    if percent == 100 or not isinstance(font, (tuple, list)) or len(font) < 2:
        return font
    try:
        size = int(font[1])
    except (TypeError, ValueError):
        return font
    scaled = max(6, round(abs(size) * percent / 100))
    if size < 0:
        scaled = -scaled
    return tuple([font[0], scaled, *font[2:]])


def configure_overlay_window(window, chroma="#ff00ff"):
    """Apply the strongest portable borderless/topmost overlay treatment.

    Windows supports Tk's chroma-key and tool-window flags. Tk on Linux does
    not, so X11/XWayland receives an opaque near-black background rather than
    failing construction or displaying a magenta rectangle.
    """
    background = chroma if os.name == "nt" else _BG
    # Every overlay is constructed while the startup bootloader owns the
    # presentation. Make new Toplevels fully transparent before Tk gets an
    # idle opportunity to map them; Dashboard releases the curtain only after
    # journal/history recovery and saved-position restoration are complete.
    master = getattr(window, "master", None)
    startup_held = bool(
        getattr(master, "_voidcompass_startup_presentation_held", False)
    )
    if startup_held:
        try:
            window.attributes("-alpha", 0.0)
            window._voidcompass_startup_held = True
        except Exception:
            pass
    try:
        if os.name == "nt":
            window.attributes(
                "-topmost", True,
                "-transparentcolor", chroma,
                "-toolwindow", True,
            )
        else:
            window.attributes("-topmost", True)
    except Exception:
        try:
            window.attributes("-topmost", True)
        except Exception:
            pass
    try:
        window.overrideredirect(True)
    except Exception:
        pass
    window.config(bg=background)
    return background


def dim_color(hexcolor, factor=0.35):
    hexcolor = hexcolor.lstrip("#")
    r, g, b = int(hexcolor[0:2], 16), int(hexcolor[2:4], 16), int(hexcolor[4:6], 16)
    return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"


def draw_chrome(canvas, width, height, accent=None, bracket_len=12, bg=_BG, tags=None,
                scanlines=True, scanline_step=3, scanline_color=_SCANLINE):
    """Draws background fill, scanline texture, tri-line stripe border, and
    corner brackets directly onto `canvas` at (0, 0, width, height).

    Pass `tags` (e.g. "bg") if the overlay needs to tag_lower() this behind
    other canvas items.
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
