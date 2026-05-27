"""
BioHUD — transparent canvas overlay for exobiology scanning.

Shows per-species sample progress (●●○), reward estimates, and system
totals for the current system.  Appears on the first ScanOrganic event,
stays visible while incomplete scans remain, and clears on system jump.

Follows the same rendering pattern as ProspectorHUD and ScanHUD.
"""

import json
import tkinter as tk

from config import CONFIG_FILE, COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE

try:
    from srvsurvey_rewards import load_bio_reward_catalog
    _REWARD_CAT = load_bio_reward_catalog()
except Exception:
    _REWARD_CAT = None

# Transparent chroma-key colour (must never appear in content)
_CHROMA = "#ff00ff"

# Colours
_COL_COMPLETE  = "#00cc44"   # completed species text / tick
_COL_DOTS_DONE = "#00cc44"   # filled sample dot
_COL_DOTS_OPEN = "#333333"   # unfilled dot track
_COL_BODY_LBL  = "#7d8891"   # body label prefix
_COL_MUTED     = "#555555"   # muted text (completed row)
_COL_SEP       = "#1a2228"   # separator lines


def _fmt_credits(value):
    """Compact credit display: 5_270_000 → '5.27M'."""
    v = int(value or 0)
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.2f}B"
    if v >= 1_000_000:
        s = f"{v / 1_000_000:.2f}".rstrip("0").rstrip(".")
        return f"{s}M"
    if v >= 1_000:
        s = f"{v / 1_000:.1f}".rstrip("0").rstrip(".")
        return f"{s}K"
    return str(v)


def _strip_system(system_name, body_name):
    """Remove system-name prefix from body name: 'Sol 3' → '3'."""
    b = str(body_name or "")
    s = str(system_name or "")
    if s and b.startswith(s):
        suffix = b[len(s):].strip()
        return suffix or b
    return b


class BioHUD:
    WIDTH     = 400   # fixed overlay width
    ROW_H     = 22    # height per species row
    HEADER_H  = 50    # header section height
    FOOTER_H  = 32    # footer totals height
    MIN_H     = 110   # minimum window height

    def __init__(self, root, config):
        self.root   = root
        self.config = config

        # State
        self._system_name = ""
        # key: (body_id_or_name, species) → entry dict
        self._entries: dict = {}

        # ── Transparent topmost window ────────────────────────────────────
        self.win = tk.Toplevel(root)
        self.win.attributes(
            "-topmost", True,
            "-transparentcolor", _CHROMA,
            "-toolwindow", True,
        )
        self.win.overrideredirect(True)
        self.win.config(bg=_CHROMA)

        self.canvas = tk.Canvas(
            self.win,
            width=self.WIDTH, height=self.MIN_H,
            bg=_CHROMA, highlightthickness=0,
        )
        self.canvas.pack()

        # Drag bindings
        self.canvas.bind("<Button-1>",       self._drag_start)
        self.canvas.bind("<B1-Motion>",      self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)

        # Restore saved position
        x = int(config.get("bio_hud_x", 30))
        y = int(config.get("bio_hud_y", 400))
        self.win.geometry(f"+{x}+{y}")

        self._force_topmost()
        self.win.withdraw()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def _force_topmost(self):
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        ms = max(2000, int(self.config.get("overlay_topmost_refresh_ms", 12000) or 12000))
        self.win.after(ms, self._force_topmost)

    def show(self):
        try:
            x = int(self.config.get("bio_hud_x", 30))
            y = int(self.config.get("bio_hud_y", 400))
            self.win.geometry(f"+{x}+{y}")
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.win.lift()
        except Exception:
            pass

    def hide(self):
        try:
            self.win.withdraw()
        except Exception:
            pass

    # ── Data interface ────────────────────────────────────────────────────

    def on_system_change(self, system_name):
        """Call on FSDJump / Location / CarrierJump.  Clears all data and hides."""
        self._entries.clear()
        self._system_name = system_name or ""
        self.hide()

    def on_scan_organic(self, body_id, body_name, species, genus,
                        sample_idx, max_samples, is_complete):
        """Call on each ScanOrganic event.

        Upserts the entry and redraws.  Shows the overlay if hidden.
        """
        key = (
            body_id if body_id is not None else (body_name or "?"),
            (species or genus or "unknown").lower(),
        )
        existing = self._entries.get(key, {})

        # Reward lookup — keep previously resolved value if already known.
        reward = existing.get("reward") or 0
        if not reward and _REWARD_CAT:
            reward = _REWARD_CAT.lookup(species, genus) or 0

        self._entries[key] = {
            "body_id":     body_id,
            "body_name":   body_name or (f"Body {body_id}" if body_id is not None else "?"),
            "species":     species or genus or "Unknown Organic",
            "genus":       genus or "",
            "sample_idx":  int(sample_idx or 1),
            "max_samples": int(max_samples or 3),
            "is_complete": bool(is_complete),
            "reward":      reward,
        }

        self._redraw()
        self.show()

    # ── Drag-to-move ──────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._dx = event.x
        self._dy = event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + (event.x - self._dx)
        y = self.win.winfo_y() + (event.y - self._dy)
        self.win.geometry(f"+{x}+{y}")

    def _drag_end(self, event):
        self.config["bio_hud_x"] = self.win.winfo_x()
        self.config["bio_hud_y"] = self.win.winfo_y()
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass

    # ── Rendering ─────────────────────────────────────────────────────────

    def _text(self, x, y, text, fill, font, anchor="w"):
        """Draw text with a 1-px drop-shadow for readability on any background."""
        self.canvas.create_text(x + 1, y + 1, text=text, fill="#000000",
                                font=font, anchor=anchor)
        self.canvas.create_text(x,     y,     text=text, fill=fill,
                                font=font, anchor=anchor)

    def _sample_dots(self, sample_idx, max_samples, is_complete):
        """Return dot string, e.g. '●●○' for 2/3."""
        n    = int(max_samples or 3)
        done = n if is_complete else min(int(sample_idx or 1), n)
        return "●" * done + "○" * max(0, n - done)

    def _redraw(self):
        if not self._entries:
            return

        entries = sorted(
            self._entries.values(),
            key=lambda e: (
                e.get("body_id") if e.get("body_id") is not None else 10_000_000,
                e.get("species", ""),
            ),
        )

        w      = self.WIDTH
        n_rows = len(entries)
        height = max(self.MIN_H,
                     self.HEADER_H + n_rows * self.ROW_H + self.FOOTER_H + 8)

        self.canvas.config(width=w, height=height)
        # Size only — position is managed by show() and _drag_move().
        self.win.geometry(f"{w}x{height}")
        self.canvas.delete("all")

        # ── Background & border ───────────────────────────────────────────
        complete_all = all(e.get("is_complete") for e in entries)
        border_col   = _COL_COMPLETE if complete_all else COLOR_ACCENT
        self.canvas.create_rectangle(
            4, 4, w - 4, height - 4,
            fill="#010101", outline=border_col, width=2,
        )

        # ── Header ───────────────────────────────────────────────────────
        total    = len(entries)
        complete = sum(1 for e in entries if e.get("is_complete"))

        self._text(12, 16, "◉  EXOBIOLOGY", border_col, ("Courier", 10, "bold"))

        sys_short = self._system_name
        if len(sys_short) > 30:
            sys_short = sys_short[:29] + "…"
        sub = f"{sys_short}  ·  {complete}/{total} complete"
        self._text(12, 33, sub, COLOR_TEXT, ("Courier", 8))

        sep_y = self.HEADER_H - 2
        self.canvas.create_line(4, sep_y, w - 4, sep_y, fill=border_col, width=1)

        y = self.HEADER_H + 4

        # ── Column layout ─────────────────────────────────────────────────
        # [body_lbl 40px] [species name ~200px] [dots ~40px] [reward ~55px] [✓ 12px]
        BODY_W    = 42
        DOTS_X    = w - 112
        REWARD_X  = w - 68
        TICK_X    = w - 14

        # ── Species rows ──────────────────────────────────────────────────
        prev_body = object()   # sentinel

        for entry in entries:
            body_id   = entry.get("body_id")
            body_name = entry.get("body_name", "")
            body_key  = body_id if body_id is not None else body_name

            # Subtle separator when body changes
            if body_key != prev_body and prev_body is not object():
                self.canvas.create_line(
                    BODY_W + 4, y - 1, w - 6, y - 1,
                    fill=_COL_SEP, width=1,
                )
            prev_body = body_key

            sp        = entry.get("species", "Unknown Organic")
            dots      = self._sample_dots(
                entry.get("sample_idx"), entry.get("max_samples"), entry.get("is_complete")
            )
            reward    = entry.get("reward", 0)
            rew_txt   = _fmt_credits(reward) if reward else "?"
            done      = entry.get("is_complete", False)
            row_col   = _COL_MUTED   if done else COLOR_TEXT
            rew_col   = _COL_COMPLETE if done else COLOR_ORANGE
            dot_col   = _COL_COMPLETE if done else COLOR_ACCENT

            # Body label (right-justified, short)
            body_short = _strip_system(self._system_name, body_name)
            if len(body_short) > 6:
                body_short = body_short[:5] + "…"
            self._text(BODY_W - 4, y + 5, body_short, _COL_BODY_LBL,
                       ("Courier", 8), anchor="e")

            # Species name (truncated to fit)
            max_sp_chars = 22
            sp_display   = sp if len(sp) <= max_sp_chars else sp[:max_sp_chars - 1] + "…"
            self._text(BODY_W + 4, y + 5, sp_display, row_col, ("Courier", 9))

            # Sample dots
            self._text(DOTS_X, y + 5, dots, dot_col, ("Courier", 10, "bold"))

            # Reward
            self._text(REWARD_X, y + 5, rew_txt, rew_col, ("Courier", 8))

            # Complete tick
            if done:
                self._text(TICK_X, y + 5, "✓", _COL_COMPLETE,
                           ("Courier", 10, "bold"), anchor="e")

            y += self.ROW_H

        # ── Footer ───────────────────────────────────────────────────────
        self.canvas.create_line(4, y + 2, w - 4, y + 2, fill=_COL_SEP, width=1)

        earned    = sum(e.get("reward", 0) for e in entries if e.get("is_complete"))
        remaining = sum(e.get("reward", 0) for e in entries if not e.get("is_complete"))

        self._text(10,   y + 18, f"EARNED  {_fmt_credits(earned)}",
                   _COL_COMPLETE, ("Courier", 8))
        self._text(w // 2, y + 18, f"REMAINING  {_fmt_credits(remaining)}",
                   COLOR_ORANGE,   ("Courier", 8))
