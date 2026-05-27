"""
BioHUD — transparent canvas overlay for exobiology scanning.

Shows per-species sample progress (●●○), reward estimates, live distance
to next sample, and system totals for the current system.

Appears on the first ScanOrganic event, stays visible while incomplete
scans remain, and clears on system jump.

Distance tracking:
  Each time a sample is taken the player's lat/lon is recorded.  The
  Status.json position feed (via on_position_update) keeps current_pos
  fresh so the distance bar updates every ~1 s while on the surface.
  Minimum scan distances are per-genus (datamined values).
"""

import json
import math
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
_COL_COMPLETE  = "#00cc44"   # completed species / tick
_COL_BODY_LBL  = "#7d8891"   # body label prefix
_COL_MUTED     = "#555555"   # muted text (completed row)
_COL_SEP       = "#1a2228"   # separator lines
_COL_DIST_OK   = "#00cc44"   # distance cleared (green)
_COL_DIST_WARN = COLOR_ORANGE # distance not yet cleared (orange)
_COL_DIST_BAR  = "#1c2830"   # unfilled bar track

# Datamined minimum scan distances in metres, keyed by first word of
# species name (genus), lower-cased.  Default 100 m for anything not listed.
_MIN_DIST_M: dict[str, int] = {
    "aleoida":    150,
    "bacterium":  500,
    "cactoida":   300,
    "clypeus":    150,
    "concha":     150,
    "electricae": 1000,
    "fonticulua": 500,
    "frutexa":    150,
    "fungoida":   300,
    "osseus":     800,
    "recepta":    150,
    "stratum":    500,
    "tubus":      800,
    "tussock":    200,
}
_DEFAULT_MIN_DIST = 100


def _min_dist_for(species: str) -> int:
    genus = (species or "").split()[0].lower()
    return _MIN_DIST_M.get(genus, _DEFAULT_MIN_DIST)


def _surface_dist_m(lat1, lon1, lat2, lon2, radius_m) -> float:
    """Great-circle distance between two lat/lon points on a sphere."""
    r    = math.radians
    dlat = r(lat2 - lat1)
    dlon = r(lon2 - lon1)
    a    = (math.sin(dlat / 2) ** 2
            + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(dlon / 2) ** 2)
    return 2 * radius_m * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def _fmt_credits(value) -> str:
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


def _strip_system(system_name, body_name) -> str:
    """Remove system-name prefix from body name: 'Sol 3' → '3'."""
    b = str(body_name or "")
    s = str(system_name or "")
    if s and b.startswith(s):
        suffix = b[len(s):].strip()
        return suffix or b
    return b


class BioHUD:
    WIDTH    = 400   # fixed overlay width
    ROW_H    = 22    # height per species row
    DIST_H   = 14    # height of distance sub-row (shown for active samples)
    HEADER_H = 50    # header section height
    FOOTER_H = 32    # footer totals height
    MIN_H    = 110   # minimum window height

    def __init__(self, root, config):
        self.root   = root
        self.config = config

        # Species state: key = (body_id_or_name, species_lower) → dict
        self._entries: dict = {}
        # Position when each sample was taken: key → (lat, lon, radius_m)
        self._sample_pos: dict = {}
        # Current player position from Status.json
        self._cur_pos: tuple | None = None   # (lat, lon, radius_m)

        self._system_name = ""

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

        self.canvas.bind("<Button-1>",        self._drag_start)
        self.canvas.bind("<B1-Motion>",       self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)

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

    def on_system_change(self, system_name: str):
        """Call on FSDJump / Location / CarrierJump."""
        self._entries.clear()
        self._sample_pos.clear()
        self._cur_pos  = None
        self._system_name = system_name or ""
        self.hide()

    def on_scan_organic(self, body_id, body_name, species, genus,
                        sample_idx, max_samples, is_complete,
                        lat=None, lon=None, radius_m=None):
        """Call on each ScanOrganic event.

        lat/lon/radius_m are the player's surface position at sample time;
        pass None when not on a planet surface.
        """
        key = (
            body_id if body_id is not None else (body_name or "?"),
            (species or genus or "unknown").lower(),
        )
        existing = self._entries.get(key, {})

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

        # Record position for distance tracking (only when we have real coords
        # and the scan is not already complete — no point tracking after done).
        if lat is not None and lon is not None and radius_m and not is_complete:
            self._sample_pos[key] = (float(lat), float(lon), float(radius_m))
        elif is_complete:
            # Clear saved position once complete — no more distance needed.
            self._sample_pos.pop(key, None)

        self._redraw()
        self.show()

    def on_position_update(self, lat, lon, radius_m):
        """Call on every Status.json tick while on a planet surface.

        Triggers a lightweight distance-only redraw if there are active
        (incomplete) entries with saved sample positions.
        """
        if lat is None or lon is None or not radius_m:
            self._cur_pos = None
            return
        self._cur_pos = (float(lat), float(lon), float(radius_m))
        # Only bother redrawing if there's something with distance to show.
        if self._sample_pos and self._entries:
            self._redraw()

    # ── Distance helpers ──────────────────────────────────────────────────

    def _dist_for(self, key, entry) -> tuple[float | None, int]:
        """Return (current_dist_m, min_dist_m) for an entry, or (None, min)."""
        min_d = _min_dist_for(entry.get("species", ""))
        sp    = self._sample_pos.get(key)
        cur   = self._cur_pos
        if sp is None or cur is None:
            return None, min_d
        try:
            d = _surface_dist_m(sp[0], sp[1], cur[0], cur[1], cur[2])
        except Exception:
            return None, min_d
        return d, min_d

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
        self.canvas.create_text(x + 1, y + 1, text=text, fill="#000000",
                                font=font, anchor=anchor)
        self.canvas.create_text(x,     y,     text=text, fill=fill,
                                font=font, anchor=anchor)

    def _sample_dots(self, sample_idx, max_samples, is_complete) -> str:
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

        # Pre-compute which entries need a distance sub-row so height is known.
        dist_rows: dict = {}   # entry index → (dist_m | None, min_m)
        for i, e in enumerate(entries):
            if e.get("is_complete"):
                continue
            si = int(e.get("sample_idx") or 1)
            if si < 1:
                continue
            key = (
                e["body_id"] if e.get("body_id") is not None else e.get("body_name", "?"),
                e.get("species", "").lower(),
            )
            d, min_d = self._dist_for(key, e)
            # Show the bar as long as we have a saved sample position.
            if key in self._sample_pos:
                dist_rows[i] = (d, min_d)

        w = self.WIDTH
        n_dist = len(dist_rows)
        total_content = (len(entries) * self.ROW_H) + (n_dist * self.DIST_H)
        height = max(self.MIN_H, self.HEADER_H + total_content + self.FOOTER_H + 8)

        self.canvas.config(width=w, height=height)
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
        self._text(12, 33, f"{sys_short}  ·  {complete}/{total} complete",
                   COLOR_TEXT, ("Courier", 8))

        sep_y = self.HEADER_H - 2
        self.canvas.create_line(4, sep_y, w - 4, sep_y, fill=border_col, width=1)

        y = self.HEADER_H + 4

        # Column x-positions
        BODY_W   = 42
        DOTS_X   = w - 112
        REWARD_X = w - 68
        TICK_X   = w - 14

        prev_body = object()

        for i, entry in enumerate(entries):
            body_id   = entry.get("body_id")
            body_name = entry.get("body_name", "")
            body_key  = body_id if body_id is not None else body_name

            if body_key != prev_body and prev_body is not object():
                self.canvas.create_line(
                    BODY_W + 4, y - 1, w - 6, y - 1,
                    fill=_COL_SEP, width=1,
                )
            prev_body = body_key

            sp       = entry.get("species", "Unknown Organic")
            dots     = self._sample_dots(
                entry.get("sample_idx"), entry.get("max_samples"), entry.get("is_complete")
            )
            reward   = entry.get("reward", 0)
            rew_txt  = _fmt_credits(reward) if reward else "?"
            done     = entry.get("is_complete", False)
            row_col  = _COL_MUTED   if done else COLOR_TEXT
            rew_col  = _COL_COMPLETE if done else COLOR_ORANGE
            dot_col  = _COL_COMPLETE if done else COLOR_ACCENT

            # Body label
            body_short = _strip_system(self._system_name, body_name)
            if len(body_short) > 6:
                body_short = body_short[:5] + "…"
            self._text(BODY_W - 4, y + 5, body_short, _COL_BODY_LBL,
                       ("Courier", 8), anchor="e")

            # Species name
            sp_display = sp if len(sp) <= 22 else sp[:21] + "…"
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

            # ── Distance sub-row ─────────────────────────────────────────
            if i in dist_rows:
                dist_m, min_m = dist_rows[i]

                BAR_X   = BODY_W + 4
                BAR_END = DOTS_X - 4
                BAR_W   = BAR_END - BAR_X
                BAR_H   = 5
                bar_y   = y + 4

                cleared = dist_m is not None and dist_m >= min_m
                col     = _COL_DIST_OK if cleared else _COL_DIST_WARN

                # Bar track
                self.canvas.create_rectangle(
                    BAR_X, bar_y, BAR_END, bar_y + BAR_H,
                    fill=_COL_DIST_BAR, outline="",
                )
                # Bar fill
                if dist_m is not None:
                    ratio   = min(1.0, dist_m / max(min_m, 1))
                    fill_px = max(2, int(BAR_W * ratio))
                    self.canvas.create_rectangle(
                        BAR_X, bar_y, BAR_X + fill_px, bar_y + BAR_H,
                        fill=col, outline="",
                    )

                # Distance label
                if dist_m is not None:
                    dist_txt = f"{int(dist_m)}m / {min_m}m"
                    ok_txt   = "  ✓ CLEAR" if cleared else ""
                else:
                    dist_txt = f"—  / {min_m}m"
                    ok_txt   = ""

                self._text(BAR_X,   bar_y - 1, dist_txt, col, ("Courier", 7))
                if ok_txt:
                    self._text(BAR_END, bar_y - 1, ok_txt, _COL_DIST_OK,
                               ("Courier", 7), anchor="e")

                y += self.DIST_H

        # ── Footer ───────────────────────────────────────────────────────
        self.canvas.create_line(4, y + 2, w - 4, y + 2, fill=_COL_SEP, width=1)

        earned    = sum(e.get("reward", 0) for e in entries if e.get("is_complete"))
        remaining = sum(e.get("reward", 0) for e in entries if not e.get("is_complete"))

        self._text(10,     y + 18, f"EARNED  {_fmt_credits(earned)}",
                   _COL_COMPLETE, ("Courier", 8))
        self._text(w // 2, y + 18, f"REMAINING  {_fmt_credits(remaining)}",
                   COLOR_ORANGE,  ("Courier", 8))
