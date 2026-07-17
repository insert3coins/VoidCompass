"""Shared native Tk theme and components for the Void Compass application UI.

This module is intentionally independent from the HUD/overlay modules.  The main
dashboard and its tool windows use it; chroma-key overlays retain their compact,
purpose-built styling.
"""

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk

import themes as _themes


@dataclass(frozen=True)
class Palette:
    bg: str = "#070b10"
    panel: str = "#0d141c"
    panel_alt: str = "#111b25"
    panel_raised: str = "#16222d"
    header: str = "#0a1017"
    input: str = "#091018"
    inset: str = "#0a1118"
    border: str = "#243746"
    border_soft: str = "#192a36"
    selection: str = "#12313c"
    accent: str = "#00d1ff"
    orange: str = "#ff8a3d"
    text: str = "#dcebf3"
    muted: str = "#91a8b7"
    dim: str = "#607584"
    green: str = "#54e39a"
    yellow: str = "#f5c76d"
    red: str = "#ff6b70"


# Built from the active commander profile's theme, resolved once at startup
# (themes.py). Theme changes apply on the next launch.
THEME = Palette(**_themes.normalize_theme(_themes.ACTIVE_PALETTE))

# Older native panels predate the shared palette and still contain a small set
# of repeated dark shell colors.  Treat them as semantic tokens when a window
# is first painted or the profile theme changes.  Overlays never call
# ``apply_window`` and therefore retain their purpose-built chroma palettes.
_LEGACY_COLOR_SLOTS = {
    "#050505": "inset",
    "#050607": "inset",
    "#070a0e": "bg",
    "#090c10": "input",
    "#090d12": "input",
    "#0b0e12": "inset",
    "#0b0f13": "inset",
    "#0c1014": "header",
    "#0d1317": "panel",
    "#0d1318": "panel",
    "#0e1318": "panel",
    "#10151a": "panel",
    "#10161c": "panel",
    "#111111": "input",
    "#11161c": "panel",
    "#121920": "panel_alt",
    "#17232c": "panel_raised",
    "#1a2228": "panel_raised",
    "#1a2430": "panel_raised",
    "#26313a": "border",
    "#12313c": "selection",
    "#ff9a3c": "orange",
    "#ff9a4d": "orange",
    "#ff7777": "red",
    "#ff5c5c": "red",
    "#ff4d4d": "red",
    "#21d189": "green",
    "#62d66f": "green",
    "#00ff99": "green",
}

FONT_UI = ("Segoe UI", 9)
FONT_UI_BOLD = ("Segoe UI", 9, "bold")
FONT_TITLE = ("Bahnschrift SemiCondensed", 14, "bold")
FONT_DISPLAY = ("Bahnschrift SemiCondensed", 10, "bold")
FONT_MONO = ("Cascadia Mono", 9)
FONT_MONO_BOLD = ("Cascadia Mono", 9, "bold")


def apply_window(window, *, background=None):
    """Apply application defaults to a root or Toplevel without touching overlays."""
    window.configure(bg=background or THEME.bg)
    window.option_add("*Font", FONT_UI)
    _configure_native_options(window)
    _configure_shared_ttk(window)
    try:
        window.after_idle(lambda target=window: _apply_legacy_theme(target))
    except Exception:
        pass


def _legacy_theme_mapping(palette=None):
    palette = palette or {key: getattr(THEME, key) for key in _themes.THEME_KEYS}
    mapping = {
        color: palette[key]
        for color, key in _LEGACY_COLOR_SLOTS.items()
    }
    defaults = _themes.BUILTIN_THEMES[_themes.DEFAULT_THEME_NAME]
    for key in _themes.THEME_KEYS:
        mapping[str(defaults[key]).lower()] = palette[key]
    return mapping


def _apply_legacy_theme(window):
    try:
        if window.winfo_exists():
            _walk_widgets(window, _legacy_theme_mapping())
    except Exception:
        pass


_CONFIGURED_TTK_PREFIXES = set()


def _configure_native_options(window):
    """Theme native controls that otherwise inherit Windows' light defaults."""
    options = {
        "*insertBackground": THEME.accent,
        "*selectBackground": THEME.selection,
        "*selectForeground": THEME.text,
        "*Listbox.background": THEME.inset,
        "*Listbox.foreground": THEME.text,
        "*Listbox.highlightBackground": THEME.border,
        "*Listbox.highlightColor": THEME.accent,
        "*Text.background": THEME.inset,
        "*Text.foreground": THEME.text,
        "*Text.highlightBackground": THEME.border,
        "*Entry.background": THEME.input,
        "*Entry.foreground": THEME.text,
        "*Spinbox.background": THEME.input,
        "*Spinbox.foreground": THEME.text,
        "*Spinbox.buttonBackground": THEME.panel_raised,
        "*Checkbutton.background": THEME.bg,
        "*Checkbutton.foreground": THEME.text,
        "*Checkbutton.activeBackground": THEME.panel_alt,
        "*Checkbutton.activeForeground": THEME.accent,
        "*Checkbutton.selectColor": THEME.input,
        "*Radiobutton.background": THEME.bg,
        "*Radiobutton.foreground": THEME.text,
        "*Radiobutton.activeBackground": THEME.panel_alt,
        "*Radiobutton.activeForeground": THEME.accent,
        "*Radiobutton.selectColor": THEME.input,
        "*Scale.background": THEME.bg,
        "*Scale.foreground": THEME.text,
        "*Scale.troughColor": THEME.inset,
        "*Menu.background": THEME.panel,
        "*Menu.foreground": THEME.text,
        "*Menu.activeBackground": THEME.selection,
        "*Menu.activeForeground": THEME.text,
        "*TCombobox*Listbox.background": THEME.input,
        "*TCombobox*Listbox.foreground": THEME.text,
        "*TCombobox*Listbox.selectBackground": THEME.selection,
        "*TCombobox*Listbox.selectForeground": THEME.text,
    }
    for pattern, value in options.items():
        try:
            window.option_add(pattern, value)
        except tk.TclError:
            pass


def _configure_shared_ttk(window):
    """Install dark/profile-aware defaults for every unprefixed ttk widget."""
    style = ttk.Style(window)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=THEME.bg, foreground=THEME.text, font=FONT_UI)
    style.configure("TFrame", background=THEME.bg)
    style.configure("TLabel", background=THEME.bg, foreground=THEME.text)
    style.configure("TLabelframe", background=THEME.bg, foreground=THEME.text,
                    bordercolor=THEME.border, lightcolor=THEME.border,
                    darkcolor=THEME.border, relief="flat")
    style.configure("TLabelframe.Label", background=THEME.bg,
                    foreground=THEME.orange, font=FONT_DISPLAY)
    style.configure("TButton", background=THEME.panel_raised,
                    foreground=THEME.text, bordercolor=THEME.border,
                    lightcolor=THEME.border, darkcolor=THEME.border,
                    padding=(9, 5), relief="flat", font=FONT_DISPLAY)
    style.map(
        "TButton",
        background=[("pressed", THEME.selection), ("active", THEME.panel_alt),
                    ("disabled", THEME.panel)],
        foreground=[("pressed", THEME.accent), ("active", THEME.accent),
                    ("disabled", THEME.dim)],
    )
    for control in ("TCheckbutton", "TRadiobutton"):
        style.configure(control, background=THEME.bg, foreground=THEME.text,
                        indicatorbackground=THEME.input,
                        indicatorforeground=THEME.accent)
        style.map(
            control,
            background=[("active", THEME.panel_alt)],
            foreground=[("active", THEME.accent), ("disabled", THEME.dim)],
            indicatorbackground=[("selected", THEME.accent),
                                 ("active", THEME.selection)],
        )
    for control in ("TEntry", "TSpinbox"):
        style.configure(control, fieldbackground=THEME.input,
                        background=THEME.panel_raised, foreground=THEME.text,
                        bordercolor=THEME.border, lightcolor=THEME.border,
                        darkcolor=THEME.border, insertcolor=THEME.accent,
                        arrowcolor=THEME.accent)
        style.map(
            control,
            fieldbackground=[("disabled", THEME.panel), ("readonly", THEME.input)],
            foreground=[("disabled", THEME.dim), ("readonly", THEME.text)],
            bordercolor=[("focus", THEME.accent)],
        )
    style.configure("TCombobox", fieldbackground=THEME.input,
                    background=THEME.panel_raised, foreground=THEME.text,
                    arrowcolor=THEME.accent, bordercolor=THEME.border,
                    lightcolor=THEME.border, darkcolor=THEME.border)
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", THEME.input), ("disabled", THEME.panel)],
        background=[("readonly", THEME.panel_raised), ("active", THEME.panel_alt)],
        foreground=[("readonly", THEME.text), ("disabled", THEME.dim)],
        arrowcolor=[("disabled", THEME.dim), ("active", THEME.accent)],
        bordercolor=[("focus", THEME.accent)],
    )
    style.configure("TNotebook", background=THEME.bg, borderwidth=0)
    style.configure("TNotebook.Tab", background=THEME.panel,
                    foreground=THEME.muted, padding=(13, 7),
                    borderwidth=0, font=FONT_DISPLAY)
    style.map(
        "TNotebook.Tab",
        background=[("selected", THEME.panel_raised), ("active", THEME.panel_alt)],
        foreground=[("selected", THEME.accent), ("active", THEME.text)],
    )
    style.configure("Treeview", background=THEME.inset, foreground=THEME.text,
                    fieldbackground=THEME.inset, borderwidth=0,
                    rowheight=25, font=FONT_MONO)
    style.configure("Treeview.Heading", background=THEME.panel_raised,
                    foreground=THEME.orange, relief="flat", borderwidth=0,
                    font=FONT_DISPLAY)
    style.map("Treeview", background=[("selected", THEME.selection)],
              foreground=[("selected", THEME.text)])
    style.map("Treeview.Heading", background=[("active", THEME.panel_alt)],
              foreground=[("active", THEME.accent)])
    style.configure("TPanedwindow", background=THEME.bg)
    style.configure("TSeparator", background=THEME.border)
    style.configure("TScale", background=THEME.bg, troughcolor=THEME.inset)
    for axis in ("Horizontal", "Vertical"):
        style.configure(f"{axis}.TProgressbar", background=THEME.accent,
                        troughcolor=THEME.inset, bordercolor=THEME.inset,
                        lightcolor=THEME.accent, darkcolor=THEME.accent,
                        thickness=9)
    _configure_scrollbar_styles(style, "")
    return style


def configure_ttk(window, prefix="Void"):
    """Create consistently named notebook, tree, input, and scrollbar styles."""
    _CONFIGURED_TTK_PREFIXES.add(prefix)
    style = _configure_shared_ttk(window)

    style.configure(f"{prefix}.TNotebook", background=THEME.bg, borderwidth=0)
    style.configure(
        f"{prefix}.TNotebook.Tab",
        background=THEME.panel,
        foreground=THEME.muted,
        padding=(13, 7),
        borderwidth=0,
        font=FONT_DISPLAY,
    )
    style.map(
        f"{prefix}.TNotebook.Tab",
        background=[("selected", THEME.panel_raised), ("active", THEME.panel_alt)],
        foreground=[("selected", THEME.accent), ("active", THEME.text)],
    )
    style.configure(
        f"{prefix}.Treeview",
        background=THEME.inset,
        foreground=THEME.text,
        fieldbackground=THEME.inset,
        borderwidth=0,
        rowheight=25,
        font=FONT_MONO,
    )
    style.configure(
        f"{prefix}.Treeview.Heading",
        background=THEME.panel_raised,
        foreground=THEME.orange,
        relief="flat",
        borderwidth=0,
        font=FONT_DISPLAY,
    )
    style.map(
        f"{prefix}.Treeview",
        background=[("selected", THEME.selection)],
        foreground=[("selected", THEME.text)],
    )
    style.map(
        f"{prefix}.Treeview.Heading",
        background=[("active", THEME.panel_alt)],
        foreground=[("active", THEME.accent)],
    )
    style.configure(
        f"{prefix}.TCombobox",
        fieldbackground=THEME.input,
        background=THEME.panel_raised,
        foreground=THEME.text,
        arrowcolor=THEME.accent,
        bordercolor=THEME.border,
        lightcolor=THEME.border,
        darkcolor=THEME.border,
    )
    style.map(
        f"{prefix}.TCombobox",
        fieldbackground=[("readonly", THEME.input), ("disabled", THEME.panel)],
        background=[("readonly", THEME.panel_raised), ("active", THEME.panel_alt)],
        foreground=[("readonly", THEME.text), ("disabled", THEME.dim)],
        arrowcolor=[("disabled", THEME.dim), ("active", THEME.accent)],
        bordercolor=[("focus", THEME.accent)],
    )
    _configure_scrollbar_styles(style, prefix)
    return style


def _configure_scrollbar_styles(style, prefix="Void"):
    vertical = f"{prefix}.Vertical.TScrollbar" if prefix else "Vertical.TScrollbar"
    horizontal = f"{prefix}.Horizontal.TScrollbar" if prefix else "Horizontal.TScrollbar"
    style.layout(vertical, [
        ("Vertical.Scrollbar.trough", {
            "sticky": "ns",
            "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})],
        }),
    ])
    style.layout(horizontal, [
        ("Horizontal.Scrollbar.trough", {
            "sticky": "ew",
            "children": [("Horizontal.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})],
        }),
    ])
    for name in (vertical, horizontal):
        style.configure(
            name,
            background=THEME.border,
            troughcolor=THEME.inset,
            bordercolor=THEME.inset,
            lightcolor=THEME.border,
            darkcolor=THEME.border,
            relief="flat",
            borderwidth=0,
            gripcount=0,
            width=9,
        )
        style.map(
            name,
            background=[("pressed", THEME.accent), ("active", THEME.accent)],
            lightcolor=[("pressed", THEME.accent), ("active", THEME.accent)],
            darkcolor=[("pressed", THEME.accent), ("active", THEME.accent)],
        )


def scrollbar(parent, *, orient=tk.VERTICAL, command=None, prefix="Void", **kwargs):
    """Square, arrowless themed scrollbar used throughout application pages."""
    style = ttk.Style(parent)
    _configure_scrollbar_styles(style, prefix)
    axis = "Vertical" if orient in (tk.VERTICAL, "vertical") else "Horizontal"
    return ttk.Scrollbar(
        parent,
        orient=orient,
        command=command,
        style=f"{prefix}.{axis}.TScrollbar",
        **kwargs,
    )


def panel(parent, *, background=None, border=None, accent=False, **kwargs):
    """A bordered content card matching the native VoidCompass panel shell."""
    frame = tk.Frame(
        parent,
        bg=background or THEME.panel,
        highlightbackground=border or THEME.border,
        highlightthickness=1,
        bd=0,
        **kwargs,
    )
    if accent:
        tk.Frame(frame, bg=THEME.accent, height=2).pack(fill=tk.X)
    else:
        # Native equivalent of the web cards' holographic top seam and corner
        # brackets.  place() keeps the decoration out of widget layout.
        tk.Frame(frame, bg=THEME.accent, height=1).place(x=0, y=0, relwidth=.46)
    corner = border or THEME.accent
    tk.Frame(frame, bg=corner, width=14, height=2).place(x=-1, y=-1)
    tk.Frame(frame, bg=corner, width=2, height=14).place(x=-1, y=-1)
    tk.Frame(frame, bg=corner, width=14, height=2).place(relx=1.0, x=-13, y=-1)
    tk.Frame(frame, bg=corner, width=2, height=14).place(relx=1.0, x=-1, y=-1)
    return frame


def header(parent, title, subtitle=None, *, height=58):
    """Create the shared application/tool-window masthead."""
    bar = tk.Frame(parent, bg=THEME.header, height=height)
    bar.pack_propagate(False)
    titles = tk.Frame(bar, bg=THEME.header)
    titles.pack(side=tk.LEFT, fill=tk.Y, padx=14)
    tk.Label(
        titles, text=title, bg=THEME.header, fg=THEME.accent,
        font=FONT_TITLE, anchor="w",
    ).pack(anchor="w", pady=(9 if subtitle else 15, 0))
    if subtitle:
        tk.Label(
            titles, text=subtitle, bg=THEME.header, fg=THEME.dim,
            font=("Cascadia Mono", 8), anchor="w",
        ).pack(anchor="w", pady=(1, 0))
    return bar


def section_label(parent, text, *, foreground=None, background=None):
    return tk.Label(
        parent,
        text=text,
        bg=background or parent.cget("bg"),
        fg=foreground or THEME.orange,
        font=FONT_DISPLAY,
        anchor="w",
    )


def button(parent, text, command, *, accent=False, muted=False, danger=False, **kwargs):
    if accent:
        bg, fg = THEME.accent, THEME.bg
    elif danger:
        bg, fg = THEME.panel_raised, THEME.red
    else:
        bg, fg = THEME.panel_raised, THEME.dim if muted else THEME.text
    padx = kwargs.pop("padx", 10)
    pady = kwargs.pop("pady", 5)
    widget = tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=THEME.accent if accent else THEME.panel_alt,
        activeforeground=THEME.bg if accent else THEME.accent,
        relief=tk.FLAT,
        bd=0,
        padx=padx,
        pady=pady,
        font=FONT_DISPLAY,
        cursor="hand2",
        **kwargs,
    )
    widget._theme_resting_bg = bg
    widget._theme_resting_fg = fg

    def _hover(_event):
        if str(widget.cget("state")) != tk.DISABLED:
            widget.configure(
                bg=THEME.accent if accent else THEME.panel_alt,
                fg=THEME.bg if accent else (THEME.red if danger else THEME.accent),
            )

    def _leave(_event):
        if str(widget.cget("state")) != tk.DISABLED:
            widget.configure(
                bg=getattr(widget, "_theme_resting_bg", bg),
                fg=getattr(widget, "_theme_resting_fg", fg),
            )

    widget.bind("<Enter>", _hover, add="+")
    widget.bind("<Leave>", _leave, add="+")
    return widget


def subtab_button(parent, text, command, *, selected=False, **kwargs):
    """Compact page-local navigation button with an orange active underline."""
    wrap = tk.Frame(parent, bg=parent.cget("bg"))
    control = button(wrap, text, command, muted=not selected, padx=11, pady=6, **kwargs)
    control.pack(fill=tk.X)
    underline = tk.Frame(wrap, bg=THEME.orange if selected else parent.cget("bg"), height=2)
    underline.pack(fill=tk.X)
    control._theme_underline = underline
    return wrap, control


def entry(parent, **kwargs):
    return tk.Entry(
        parent,
        bg=THEME.input,
        fg=THEME.text,
        insertbackground=THEME.accent,
        selectbackground=THEME.selection,
        selectforeground=THEME.text,
        relief=tk.FLAT,
        highlightbackground=THEME.border,
        highlightcolor=THEME.accent,
        highlightthickness=1,
        font=FONT_MONO,
        **kwargs,
    )


class ThemedWindowMixin:
    """Compatibility tokens plus components for existing native tool windows."""

    UI_BG = THEME.bg
    UI_PANEL = THEME.panel
    UI_PANEL_2 = THEME.panel_alt
    UI_BORDER = THEME.border
    UI_MUTED = THEME.muted
    UI_DIM = THEME.dim
    UI_OK = THEME.green
    UI_WARN = THEME.yellow
    UI_FAIL = THEME.red
    UI_FONT = FONT_UI
    UI_FONT_BOLD = FONT_UI_BOLD
    UI_BOLD = FONT_UI_BOLD
    UI_FONT_TITLE = FONT_TITLE
    UI_MONO = FONT_MONO
    UI_MONO_BOLD = FONT_MONO_BOLD
    UI_MONO_B = FONT_MONO_BOLD

    def _theme_window(self, window=None, prefix=None):
        target = window or getattr(self, "win", None) or getattr(self, "root", None)
        apply_window(target)
        return configure_ttk(target, prefix or self.__class__.__name__.removesuffix("Window"))

    def _panel(self, parent, bg=None, border=None, **kwargs):
        return panel(parent, background=bg, border=border, **kwargs)

    def _section_label(self, parent, text, fg=None, bg=None):
        return section_label(parent, text, foreground=fg, background=bg)

    def _action_button(self, parent, text, command, accent=False, muted=False, danger=False, **kwargs):
        return button(parent, text, command, accent=accent, muted=muted, danger=danger, **kwargs)


class EmbeddedPage(tk.Frame):
    """Frame with the small window-manager API used by legacy tool windows.

    This lets a tool build the same controls inside the dashboard without
    duplicating its UI or pretending the embedded page is a separate window.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=THEME.bg, **kwargs)
        self._page_title = ""

    def title(self, value=None):
        if value is not None:
            self._page_title = value
        return self._page_title

    def geometry(self, value=None):
        if value is not None:
            return ""
        return f"{self.winfo_width()}x{self.winfo_height()}"

    def minsize(self, *_args):
        return None

    def resizable(self, *_args):
        return None

    def protocol(self, *_args):
        return None

    def attributes(self, *_args):
        return None

    def deiconify(self):
        return None

    def lift(self, above_this=None):
        self.tkraise(above_this)

    def focus_force(self):
        self.focus_set()


def window_surface(parent, *, embedded=False):
    """Return either an embedded application page or a real native Toplevel."""
    return EmbeddedPage(parent) if embedded else tk.Toplevel(parent)


# ---------------------------------------------------------------------------
# Live re-theming
#
# Every themed color in the app comes from one palette, so a theme switch is
# a color-for-color substitution: mutate THEME in place (widgets built later
# pick it up), rebind the value-imported module constants (COLOR_*/UI_*), and
# walk the live widget tree remapping any option whose current color is in
# the old palette. Chroma-key overlays are safe by construction — their
# transparent key and hand-tuned greys are not palette colors, so the walker
# never touches them; their accent-colored elements redraw from the swapped
# module globals on their next update.
# ---------------------------------------------------------------------------

_WIDGET_COLOR_OPTIONS = (
    "background", "foreground", "activebackground", "activeforeground",
    "highlightbackground", "highlightcolor", "selectbackground",
    "selectforeground", "insertbackground", "disabledforeground",
    "troughcolor", "selectcolor", "readonlybackground",
)
_CANVAS_ITEM_OPTIONS = ("fill", "outline", "activefill", "activeoutline")


def _remap_widget(widget, mapping):
    for option in _WIDGET_COLOR_OPTIONS:
        try:
            current = str(widget.cget(option))
        except Exception:
            continue
        new = mapping.get(current.lower())
        if new:
            try:
                widget.configure({option: new})
            except Exception:
                pass
    for attr in ("_theme_resting_bg", "_theme_resting_fg"):
        value = getattr(widget, attr, None)
        if isinstance(value, str) and value.lower() in mapping:
            setattr(widget, attr, mapping[value.lower()])
    if isinstance(widget, tk.Canvas):
        try:
            for item in widget.find_all():
                for option in _CANVAS_ITEM_OPTIONS:
                    try:
                        current = str(widget.itemcget(item, option))
                    except Exception:
                        continue
                    new = mapping.get(current.lower())
                    if new:
                        try:
                            widget.itemconfigure(item, {option: new})
                        except Exception:
                            pass
        except Exception:
            pass


def _walk_widgets(widget, mapping):
    _remap_widget(widget, mapping)
    try:
        children = widget.winfo_children()
    except Exception:
        return
    for child in children:
        _walk_widgets(child, mapping)


def apply_theme_live(root, theme_name, palette):
    """Switch the running app to `palette` without a restart."""
    import sys as _sys
    import themes as _th

    palette = _th.normalize_theme(palette)
    mapping = {}
    for key in _th.THEME_KEYS:
        old = str(getattr(THEME, key)).lower()
        new = palette[key]
        if old != new.lower() and old not in mapping:
            mapping[old] = new
    # Panels created from older hard-coded shell colors still follow live
    # themes.  This also covers a page opened after the commander selected a
    # non-default palette but before its first idle paint.
    for old, new in _legacy_theme_mapping(palette).items():
        if old != str(new).lower() and old not in mapping:
            mapping[old] = new
    # Overlay constants may predate THEME (config.COLOR_* seeds) — map those too.
    try:
        import config as _cfg
        for attr, key in (("COLOR_BG", "bg"), ("COLOR_PANEL", "panel"), ("COLOR_ACCENT", "accent"),
                          ("COLOR_ORANGE", "orange"), ("COLOR_TEXT", "text"), ("COLOR_GREEN", "green")):
            old = str(getattr(_cfg, attr, "")).lower()
            if old and old != palette[key].lower() and old not in mapping:
                mapping[old] = palette[key]
    except Exception:
        pass

    # Overlay chrome also draws a derived dim accent around its bright border.
    # Include that color in the live canvas remap so open overlays change
    # immediately instead of retaining their old dim stripes until a redraw.
    try:
        import overlay_chrome as _chrome
        old_accent = str(getattr(_chrome, "COLOR_ACCENT", ""))
        if old_accent:
            old_dim = _chrome.dim_color(old_accent).lower()
            new_dim = _chrome.dim_color(palette["accent"])
            if old_dim != new_dim.lower() and old_dim not in mapping:
                mapping[old_dim] = new_dim
    except Exception:
        pass

    # 1. The live palette: widgets built from now on use the new colors.
    for key in _th.THEME_KEYS:
        object.__setattr__(THEME, key, palette[key])
    _th.ACTIVE_THEME_NAME = theme_name
    _th.ACTIVE_PALETTE = dict(palette)

    if not mapping:
        return

    # 2. Value-bound copies: every loaded module's ALL-CAPS string constants
    # that hold an old palette color (COLOR_*, UI_*, module-level aliases).
    for module in list(_sys.modules.values()):
        module_vars = getattr(module, "__dict__", None)
        if not isinstance(module_vars, dict):
            continue
        for name, value in list(module_vars.items()):
            if name.isupper() and isinstance(value, str) and value.lower() in mapping:
                try:
                    setattr(module, name, mapping[value.lower()])
                except Exception:
                    pass
    for name in dir(ThemedWindowMixin):
        if name.startswith("UI_"):
            value = getattr(ThemedWindowMixin, name)
            if isinstance(value, str) and value.lower() in mapping:
                setattr(ThemedWindowMixin, name, mapping[value.lower()])

    # 3. Everything already on screen.
    try:
        _walk_widgets(root, mapping)
    except Exception:
        pass

    # 4. ttk styles (notebooks, trees, scrollbars) under every prefix used so far.
    for prefix in list(_CONFIGURED_TTK_PREFIXES):
        try:
            configure_ttk(root, prefix)
        except Exception:
            pass
    try:
        _configure_native_options(root)
        _configure_shared_ttk(root)
    except Exception:
        pass
