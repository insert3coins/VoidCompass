"""Shared native Tk theme and components for the Void Compass application UI.

This module is intentionally independent from the HUD/overlay modules.  The main
dashboard and its tool windows use it; chroma-key overlays retain their compact,
purpose-built styling.
"""

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk


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


THEME = Palette()

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
    window.option_add("*insertBackground", THEME.accent)
    window.option_add("*selectBackground", THEME.selection)
    window.option_add("*selectForeground", THEME.text)


def configure_ttk(window, prefix="Void"):
    """Create consistently named notebook, tree, input, and scrollbar styles."""
    style = ttk.Style(window)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

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
    _configure_scrollbar_styles(style, prefix)
    return style


def _configure_scrollbar_styles(style, prefix="Void"):
    vertical = f"{prefix}.Vertical.TScrollbar"
    horizontal = f"{prefix}.Horizontal.TScrollbar"
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
