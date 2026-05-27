"""
BioHUD — transparent canvas overlay for exobiology & geology scanning.

Shows per-species sample progress (●●○), reward estimates, live distance
to next sample, DSS-confirmed genera, bio predictions, geo signal counts,
and scanned geological entries.

Display priority per body:
  1. Confirmed bio scans  — from ScanOrganic events (highest priority)
  2. DSS genera           — from SAASignalsFound (genus confirmed)
  3. Predictions          — from bio-criteria prediction engine
  4. Geological entries   — from CodexEntry events

Appears on the first ScanOrganic / DSS / prediction / FSSBodySignals event,
hides on jump.  Distance tracking uses Status.json lat/lon feed (~1 s).
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

# ── Colour palette ────────────────────────────────────────────────────────────
_COL_COMPLETE  = "#00cc44"   # completed bio species
_COL_DSS       = "#d4a017"   # DSS genus row (confirmed, species unknown)
_COL_PREDICT   = "#445566"   # predicted row (greyed)
_COL_BODY_LBL  = "#7d8891"   # inactive body header text
_COL_MUTED     = "#555555"   # completed row text
_COL_SEP       = "#1a2228"   # thin footer separator
_COL_BODY_SEP  = "#1e2c38"   # body-group separator bar
_COL_DIST_OK   = "#00cc44"   # distance cleared
_COL_DIST_WARN = COLOR_ORANGE
_COL_DIST_BAR  = "#1c2830"   # unfilled distance-bar track
_COL_CURR_BODY = "#00aaff"   # current body highlight (cyan)
_COL_GEO       = "#8fc08a"   # scanned geological entry text
_COL_GEO_CNT   = "#c8a84b"   # geo signal count badge

# Datamined minimum scan distances in metres, lower-cased genus key.
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
    r    = math.radians
    dlat = r(lat2 - lat1)
    dlon = r(lon2 - lon1)
    a    = (math.sin(dlat / 2) ** 2
            + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(dlon / 2) ** 2)
    return 2 * radius_m * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def _fmt_credits(value) -> str:
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
    # ── Layout constants ──────────────────────────────────────────────────────
    WIDTH    = 460
    HEADER_H = 50     # title + system/status line + separator
    BODY_H   = 22     # body-group header row
    ROW_H    = 22     # bio scan row
    DIST_H   = 14     # distance sub-row
    GEO_H    = 20     # geological entry row
    FOOTER_H = 30
    MIN_H    = 120

    # Scan-content column positions (scan rows, geo rows, etc.)
    INDENT   = 14          # left margin for all scan content
    DOTS_X   = 346         # start of progress dots  (●●○)
    REWARD_X = 400         # start of reward text
    TICK_X   = 448         # ✓ tick (right edge)

    def __init__(self, root, config):
        self.root   = root
        self.config = config

        # ── Per-system state ────────────────────────────────────────────────
        self._system_name     = ""
        self._current_body_id = None   # from ApproachBody

        # Confirmed bio scans: (body_id_or_name, species_lower) → scan dict
        self._scans: dict = {}

        # DSS genera per body: body_id → [{"genus_token", "genus_display"}, ...]
        self._dss_genera: dict[object, list] = {}

        # Bio predictions per body: body_id → [{"genus", "species", ...}, ...]
        self._predictions: dict[object, list] = {}

        # Body display names: body_id → str
        self._body_names: dict = {}

        # Signal counts per body
        self._bio_counts: dict = {}    # body_id → int
        self._geo_counts: dict = {}    # body_id → int

        # Scanned geological entries: body_id → [entry_name_str, ...]
        self._geo_scans: dict = {}

        # Sample positions for distance tracking
        self._sample_pos: dict = {}    # scan key → (lat, lon, radius_m)
        self._cur_pos: tuple | None = None

        # ── Transparent topmost window ──────────────────────────────────────
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

    # ── Lifecycle ─────────────────────────────────────────────────────────────

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

    def _has_content(self) -> bool:
        return bool(
            self._scans or self._dss_genera or self._predictions
            or self._bio_counts or self._geo_counts or self._geo_scans
        )

    # ── Data interface ─────────────────────────────────────────────────────────

    def on_system_change(self, system_name: str):
        self._system_name     = system_name or ""
        self._current_body_id = None
        self._scans.clear()
        self._dss_genera.clear()
        self._predictions.clear()
        self._body_names.clear()
        self._bio_counts.clear()
        self._geo_counts.clear()
        self._geo_scans.clear()
        self._sample_pos.clear()
        self._cur_pos = None
        self.hide()

    def on_approach_body(self, body_id, body_name: str):
        self._current_body_id = body_id
        if body_id is not None and body_name:
            self._body_names[body_id] = body_name
        self._redraw()
        if self._has_content():
            self.show()

    def on_leave_body(self):
        self._current_body_id = None
        self._redraw()

    def on_dss_genuses(self, body_id, body_name: str,
                       genuses: list, bio_count: int, geo_count: int = 0):
        """Called on SAASignalsFound."""
        if body_id is None:
            return
        if body_name:
            self._body_names[body_id] = body_name
        if bio_count:
            self._bio_counts[body_id] = bio_count
        if geo_count:
            self._geo_counts[body_id] = geo_count

        parsed = []
        for g in (genuses or []):
            token   = g.get("Genus") or ""
            display = g.get("Genus_Localised") or g.get("Genus_localised") or token
            if display.startswith("$") and "_Name;" in display:
                display = display.split("_Name;")[0].lstrip("$")
            if token or display:
                parsed.append({"genus_token": token, "genus_display": display})
        self._dss_genera[body_id] = parsed

        self._redraw()
        self.show()

    def on_predictions(self, body_id, body_name: str, predictions: list,
                       bio_count: int = 0, geo_count: int = 0):
        """Called after predict_for_body() runs or from FSSBodySignals.

        Shows even with an empty predictions list as long as bio_count or
        geo_count is > 0 — ensures any bio/geo planet shows up immediately
        on FSS scan.
        """
        if body_id is None or (not predictions and not bio_count and not geo_count):
            return
        if body_name:
            self._body_names[body_id] = body_name
        if predictions:
            self._predictions[body_id] = predictions
        if bio_count:
            self._bio_counts[body_id] = bio_count
        if geo_count:
            self._geo_counts[body_id] = geo_count
        if body_id not in self._dss_genera:
            self._redraw()
            if self._has_content():
                self.show()

    def on_geo_signals(self, body_id, body_name: str, geo_count: int):
        """Called when FSSBodySignals / SAASignalsFound reports geo signals."""
        if body_id is None or geo_count <= 0:
            return
        if body_name:
            self._body_names[body_id] = body_name
        self._geo_counts[body_id] = geo_count
        self._redraw()
        if self._has_content():
            self.show()

    def on_geo_scan(self, body_id, body_name: str, entry_name: str):
        """Called when a geological CodexEntry is scanned on-planet."""
        if body_id is None or not entry_name:
            return
        if body_name:
            self._body_names[body_id] = body_name
        entries = self._geo_scans.setdefault(body_id, [])
        if entry_name not in entries:
            entries.append(entry_name)
        self._redraw()
        if self._has_content():
            self.show()

    def on_scan_organic(self, body_id, body_name, species, genus,
                        sample_idx, max_samples, is_complete,
                        lat=None, lon=None, radius_m=None):
        if body_name and body_id is not None:
            self._body_names[body_id] = body_name

        key = (
            body_id if body_id is not None else (body_name or "?"),
            (species or genus or "unknown").lower(),
        )
        existing = self._scans.get(key, {})
        reward = existing.get("reward") or 0
        if not reward and _REWARD_CAT:
            reward = _REWARD_CAT.lookup(species, genus) or 0

        self._scans[key] = {
            "body_id":     body_id,
            "body_name":   body_name or (f"Body {body_id}" if body_id is not None else "?"),
            "species":     species or genus or "Unknown Organic",
            "genus":       genus or "",
            "sample_idx":  int(sample_idx or 1),
            "max_samples": int(max_samples or 3),
            "is_complete": bool(is_complete),
            "reward":      reward,
        }

        if lat is not None and lon is not None and radius_m and not is_complete:
            self._sample_pos[key] = (float(lat), float(lon), float(radius_m))
        elif is_complete:
            self._sample_pos.pop(key, None)

        self._redraw()
        self.show()

    def on_position_update(self, lat, lon, radius_m):
        if lat is None or lon is None or not radius_m:
            self._cur_pos = None
            return
        self._cur_pos = (float(lat), float(lon), float(radius_m))
        if self._sample_pos and self._scans:
            self._redraw()

    # ── Distance helpers ──────────────────────────────────────────────────────

    def _dist_for(self, key, entry) -> tuple:
        """Return (current_dist_m | None, min_dist_m)."""
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

    # ── Drag-to-move ──────────────────────────────────────────────────────────

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

    # ── Rendering helpers ─────────────────────────────────────────────────────

    def _text(self, x, y, text, fill, font, anchor="w"):
        self.canvas.create_text(x + 1, y + 1, text=text, fill="#000000",
                                font=font, anchor=anchor)
        self.canvas.create_text(x,     y,     text=text, fill=fill,
                                font=font, anchor=anchor)

    def _sample_dots(self, sample_idx, max_samples, is_complete) -> str:
        n    = int(max_samples or 3)
        done = n if is_complete else min(int(sample_idx or 1), n)
        return "●" * done + "○" * max(0, n - done)

    # ── Main redraw ───────────────────────────────────────────────────────────

    def _redraw(self):
        # ── Collect all body IDs with any data ────────────────────────────
        all_bodies: set = set()
        all_bodies.update(
            e["body_id"] for e in self._scans.values()
            if e.get("body_id") is not None
        )
        all_bodies.update(self._dss_genera.keys())
        for bid in self._predictions:
            if bid not in self._dss_genera:
                all_bodies.add(bid)
        # Bodies with known signal counts but no other data yet
        for bid in self._bio_counts:
            if bid not in self._dss_genera:
                all_bodies.add(bid)
        for bid in self._geo_counts:
            all_bodies.add(bid)
        for bid in self._geo_scans:
            all_bodies.add(bid)

        if not all_bodies:
            return

        # Sort: current body first, then ascending body_id
        def _body_sort_key(bid):
            if bid == self._current_body_id:
                return (0, 0)
            try:
                return (1, int(bid))
            except (TypeError, ValueError):
                return (1, 9_999_999)

        sorted_bodies = sorted(all_bodies, key=_body_sort_key)

        w        = self.WIDTH
        DOTS_X   = self.DOTS_X
        REWARD_X = self.REWARD_X
        TICK_X   = self.TICK_X
        INDENT   = self.INDENT

        # ── Build render-plan (rows list) to compute height first ─────────
        rows = []
        total_earned    = 0
        total_remaining = 0

        for bid in sorted_bodies:
            bname  = (self._body_names.get(bid)
                      or (f"Body {bid}" if bid is not None else "?"))
            bshort = _strip_system(self._system_name, bname)
            if len(bshort) > 22:
                bshort = bshort[:21] + "…"

            is_current = (bid == self._current_body_id)
            bio_count  = self._bio_counts.get(bid, 0)
            geo_count  = self._geo_counts.get(bid, 0)

            scanned_genus_lower = {
                e.get("genus", "").lower()
                for e in self._scans.values()
                if e.get("body_id") == bid and e.get("genus")
            }

            rows.append({
                "type":       "body_header",
                "label":      bshort,
                "is_current": is_current,
                "bio_count":  bio_count,
                "geo_count":  geo_count,
            })

            # ── Confirmed bio scans ────────────────────────────────────────
            body_scans = sorted(
                ((k, e) for k, e in self._scans.items() if e.get("body_id") == bid),
                key=lambda x: x[1].get("species", ""),
            )
            for key, entry in body_scans:
                done   = entry.get("is_complete", False)
                reward = entry.get("reward", 0)
                if done:
                    total_earned    += reward
                else:
                    total_remaining += reward

                dist_info = None
                if not done:
                    si = int(entry.get("sample_idx") or 1)
                    if si >= 1 and key in self._sample_pos:
                        dist_info = self._dist_for(key, entry)

                rows.append({
                    "type":      "scan",
                    "key":       key,
                    "entry":     entry,
                    "sp":        entry.get("species", "Unknown Organic"),
                    "done":      done,
                    "reward":    reward,
                    "dist_info": dist_info,
                })

            # ── DSS genera (unconfirmed by scan) ──────────────────────────
            dss_list = self._dss_genera.get(bid, [])
            for g in dss_list:
                genus_disp = g.get("genus_display", "")
                if any(genus_disp.lower() in gl for gl in scanned_genus_lower):
                    continue
                rows.append({"type": "dss_genus", "genus_display": genus_disp})

            # ── Unresolved signal count ────────────────────────────────────
            known_count = len(body_scans) + len(dss_list)
            if bio_count and known_count < bio_count:
                rows.append({"type": "unresolved", "count": bio_count - known_count})

            # ── Bio predictions ───────────────────────────────────────────
            if bid not in self._dss_genera:
                scanned_sp_lower = {e.get("species", "").lower() for _, e in body_scans}
                for p in self._predictions.get(bid, [])[:10]:
                    if p.get("species", "").lower() not in scanned_sp_lower:
                        rows.append({
                            "type":    "prediction",
                            "genus":   p.get("genus", ""),
                            "species": p.get("species", ""),
                        })

            # ── Geological entries scanned ────────────────────────────────
            for gentry in self._geo_scans.get(bid, []):
                rows.append({"type": "geo_scan", "name": gentry})

        # ── Compute total pixel height ────────────────────────────────────
        pxh = self.HEADER_H
        for r in rows:
            rt = r["type"]
            if rt == "body_header":
                pxh += self.BODY_H
            elif rt == "scan":
                pxh += self.ROW_H
                if r.get("dist_info") is not None:
                    pxh += self.DIST_H
            elif rt == "geo_scan":
                pxh += self.GEO_H
            else:
                pxh += self.ROW_H
        pxh += self.FOOTER_H + 6
        height = max(self.MIN_H, pxh)

        self.canvas.config(width=w, height=height)
        self.win.geometry(f"{w}x{height}")
        self.canvas.delete("all")

        # ── Background ────────────────────────────────────────────────────
        all_complete = (
            bool(self._scans)
            and all(e.get("is_complete") for e in self._scans.values())
        )
        border_col = _COL_COMPLETE if all_complete else COLOR_ACCENT
        self.canvas.create_rectangle(
            4, 4, w - 4, height - 4,
            fill="#010101", outline=border_col, width=2,
        )

        # ── Header ────────────────────────────────────────────────────────
        total_scans    = sum(1 for r in rows if r["type"] == "scan")
        complete_scans = sum(1 for r in rows if r["type"] == "scan" and r["done"])

        self._text(12, 15, "◉  EXOBIOLOGY & GEOLOGY",
                   border_col, ("Courier", 9, "bold"))

        sys_short = self._system_name
        if len(sys_short) > 30:
            sys_short = sys_short[:29] + "…"
        status_str = f"{complete_scans}/{total_scans} sampled" if total_scans else "scanning…"
        self._text(12, 32, f"{sys_short}  ·  {status_str}",
                   COLOR_TEXT, ("Courier", 8))

        sep_y = self.HEADER_H - 2
        self.canvas.create_line(4, sep_y, w - 4, sep_y, fill=border_col, width=1)

        y = self.HEADER_H + 2

        # ── Render rows ───────────────────────────────────────────────────
        for r in rows:
            rtype = r["type"]

            # ── Body group header ──────────────────────────────────────────
            if rtype == "body_header":
                is_curr   = r["is_current"]
                lbl_col   = _COL_CURR_BODY if is_curr else _COL_BODY_LBL
                prefix    = "▶ " if is_curr else "  "
                bshort    = r["label"]
                bio_c     = r["bio_count"]
                geo_c     = r["geo_count"]

                # Thin separator above body group
                self.canvas.create_line(
                    4, y, w - 4, y, fill=_COL_BODY_SEP, width=1,
                )
                # Planet name (left)
                self._text(10, y + 11,
                           f"{prefix}{bshort}",
                           lbl_col, ("Courier", 9, "bold"))

                # Signal count badge (right) — "2 bio · 3 geo"
                parts = []
                if bio_c:
                    parts.append(f"{bio_c} bio")
                if geo_c:
                    parts.append(f"{geo_c} geo")
                if parts:
                    badge = "  ·  ".join(parts)
                    # Choose badge colour: geo-only amber, bio-present accent
                    badge_col = COLOR_ACCENT if bio_c else _COL_GEO_CNT
                    self._text(w - 10, y + 11, badge,
                               badge_col, ("Courier", 8), anchor="e")

                y += self.BODY_H

            # ── Bio scan row ───────────────────────────────────────────────
            elif rtype == "scan":
                entry     = r["entry"]
                sp        = r["sp"]
                done      = r["done"]
                reward    = r["reward"]
                dist_info = r.get("dist_info")

                row_col = _COL_MUTED   if done else COLOR_TEXT
                rew_col = _COL_COMPLETE if done else COLOR_ORANGE
                dot_col = _COL_COMPLETE if done else COLOR_ACCENT

                sp_disp = sp if len(sp) <= 28 else sp[:27] + "…"
                self._text(INDENT, y + 5, sp_disp, row_col, ("Courier", 9))

                dots = self._sample_dots(
                    entry.get("sample_idx"), entry.get("max_samples"), done
                )
                self._text(DOTS_X, y + 5, dots, dot_col,
                           ("Courier", 10, "bold"))

                rew_txt = _fmt_credits(reward) if reward else "?"
                self._text(REWARD_X, y + 5, rew_txt, rew_col, ("Courier", 8))

                if done:
                    self._text(TICK_X, y + 5, "✓", _COL_COMPLETE,
                               ("Courier", 10, "bold"), anchor="e")

                y += self.ROW_H

                # Distance sub-row
                if dist_info is not None:
                    dist_m, min_m = dist_info
                    BAR_X   = INDENT
                    BAR_END = DOTS_X - 6
                    BAR_W   = BAR_END - BAR_X
                    bar_y   = y + 4

                    cleared = dist_m is not None and dist_m >= min_m
                    col     = _COL_DIST_OK if cleared else _COL_DIST_WARN

                    self.canvas.create_rectangle(
                        BAR_X, bar_y, BAR_END, bar_y + 5,
                        fill=_COL_DIST_BAR, outline="",
                    )
                    if dist_m is not None:
                        ratio   = min(1.0, dist_m / max(min_m, 1))
                        fill_px = max(2, int(BAR_W * ratio))
                        self.canvas.create_rectangle(
                            BAR_X, bar_y, BAR_X + fill_px, bar_y + 5,
                            fill=col, outline="",
                        )
                    dist_txt = (f"{int(dist_m)}m / {min_m}m" if dist_m is not None
                                else f"— / {min_m}m")
                    ok_txt = "  ✓ CLEAR" if cleared else ""
                    self._text(BAR_X, bar_y - 1, dist_txt, col, ("Courier", 7))
                    if ok_txt:
                        self._text(BAR_END, bar_y - 1, ok_txt, _COL_DIST_OK,
                                   ("Courier", 7), anchor="e")
                    y += self.DIST_H

            # ── DSS genus row (species unknown) ───────────────────────────
            elif rtype == "dss_genus":
                gd  = r["genus_display"]
                lbl = (gd if len(gd) <= 24 else gd[:23] + "…") + " ?"
                self._text(INDENT, y + 5, lbl, _COL_DSS,
                           ("Courier", 9, "italic"))
                self._text(DOTS_X, y + 5, "○○○", _COL_DSS,
                           ("Courier", 10))
                y += self.ROW_H

            # ── Unresolved signal count ────────────────────────────────────
            elif rtype == "unresolved":
                cnt = r["count"]
                msg = f"+ {cnt} unresolved signal{'s' if cnt != 1 else ''}"
                self._text(INDENT, y + 5, msg, _COL_DSS,
                           ("Courier", 8, "italic"))
                y += self.ROW_H

            # ── Bio prediction row ─────────────────────────────────────────
            elif rtype == "prediction":
                sp  = r["species"] or r["genus"]
                lbl = (sp if len(sp) <= 26 else sp[:25] + "…") + " ~"
                self._text(INDENT, y + 5, lbl, _COL_PREDICT,
                           ("Courier", 9, "italic"))
                y += self.ROW_H

            # ── Geological entry row ───────────────────────────────────────
            elif rtype == "geo_scan":
                name = r["name"]
                disp = name if len(name) <= 28 else name[:27] + "…"
                self._text(INDENT, y + 10, f"◈ {disp}", _COL_GEO,
                           ("Courier", 8))
                y += self.GEO_H

        # ── Footer ────────────────────────────────────────────────────────
        self.canvas.create_line(4, y + 2, w - 4, y + 2,
                                fill=_COL_SEP, width=1)
        self._text(INDENT, y + 18,
                   f"EARNED  {_fmt_credits(total_earned)}",
                   _COL_COMPLETE, ("Courier", 8))
        self._text(w // 2, y + 18,
                   f"REMAINING  {_fmt_credits(total_remaining)}",
                   COLOR_ORANGE, ("Courier", 8))
