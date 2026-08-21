"""HTML/WebGL Galactic Atlas host and profile-aware data bridge.

The former Tk/Pillow renderer has been retired. This module owns only the
small native launch surface, the immutable exploration snapshot sent to the
browser, and validated commands returned by the HTML atlas.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math
from pathlib import Path
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser

from explorer_fieldcraft import sector_grid
from exploration_intelligence import route_context
from galactic_map_server import GalacticMapServer
from galactic_regions import X0, Z0, SOURCE_SCALE, SOURCE_SIZE, find_region, region_fills, region_geometry
from ui_theme import THEME, button


ANNOTATION_TYPES = (
    "Note", "Danger", "Region of Interest", "Survey Target", "Waypoint",
)
LAYER_NAMES = (
    "Regions", "Travel", "Planned", "Return", "Sectors", "Valuable", "Biology",
    "Codex", "Photos", "Recon", "Revisit", "Bookmarks", "Annotations",
)
VIEW_MODES = ("Galactic Atlas", "Route Focus", "Current Vicinity")
SCOPES = ("All History", "Current Session", "Active Expedition")
GALACTIC_CENTRE = (0.0, 0.0, 25899.0)
GALAXY_RADIUS_LY = 51500.0
MAP_ORIENTATION = "galactic-north-up-east-right-v2"
MAX_ROUTE_POINTS = 5000
STATIC_ROOT = Path("web") / "galactic_map"
ATLAS_ASSET = Path("Images") / "Galaxy" / "voidcompass-galactic-atlas.png"


def _resource_path(relative_path):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


def _position(value):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    try:
        return tuple(float(value[index]) for index in range(3))
    except (TypeError, ValueError):
        return None


def _row_epoch(row):
    value = (row or {}).get("timestamp")
    try:
        return datetime.fromisoformat(str(value or "").replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _bounded_text(value, limit):
    return str(value or "").strip()[:limit]


def _sample_rows(rows, limit=MAX_ROUTE_POINTS):
    rows = list(rows or [])
    if limit <= 1:
        return rows[-1:] if rows else []
    if len(rows) <= limit:
        return rows
    last = len(rows) - 1
    return [rows[round(index * last / (limit - 1))] for index in range(limit)]


def _theme_payload():
    return {
        key: str(getattr(THEME, key))
        for key in (
            "bg", "panel", "panel_alt", "panel_raised", "header", "input",
            "inset", "border", "border_soft", "selection", "accent", "orange",
            "text", "muted", "dim", "green", "yellow", "red",
        )
    }


def galactic_region_payload():
    """Return the complete static region mesh consumed by Three.js."""
    segments, labels = region_geometry(16)
    fills = region_fills(32)
    return {
        "extent": {
            "x": X0,
            "z": Z0,
            "size": SOURCE_SIZE * SOURCE_SCALE,
            "centre": list(GALACTIC_CENTRE),
            "radius": GALAXY_RADIUS_LY,
        },
        "segments": [list(row[:4]) for row in segments],
        "fills": [list(row) for row in fills],
        "labels": [
            {
                "id": int(row["id"]), "name": str(row["name"]),
                "position": list(row["position"]),
                "weight": int(row.get("cells") or 0),
            }
            for row in labels
        ],
    }


class ExpeditionMapView:
    """Native launch surface and live bridge for the browser Galactic Atlas."""

    def __init__(self, parent, app, open_record_callback=None):
        self.parent = parent
        self.app = app
        self.open_record_callback = open_record_callback
        self.config = getattr(app, "config", None) or {}
        self._system_rows = []
        self._value_rows = []
        self._latest_snapshot = {}
        self._annotations = []
        self._view_state = self._normalise_view_state(
            self.config.get("explore_map_view_state")
        )
        self._focus_request = None
        self._focus_sequence = 0
        self._disposed = False
        self._opened_once = False
        self._status_job = None
        self._browser_commands = queue.SimpleQueue()
        self._server_status_hint = (0, 0.0)
        self._build()
        self.server = GalacticMapServer(
            _resource_path(STATIC_ROOT), _resource_path(ATLAS_ASSET),
            command_callback=self._queue_browser_command,
            regions_provider=galactic_region_payload,
            status_callback=self._server_status_changed,
        )
        self.refresh()
        self._schedule_status_tick()

    def _build(self):
        shell = tk.Frame(
            self.parent, bg=THEME.bg,
            highlightthickness=1, highlightbackground=THEME.border,
        )
        shell.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        header = tk.Frame(shell, bg=THEME.header, height=62)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header, text="GALACTIC ATLAS // WEBGL COMMAND VIEW",
            fg=THEME.orange, bg=THEME.header,
            font=("Bahnschrift SemiCondensed", 15, "bold"), anchor="w",
        ).pack(side=tk.LEFT, padx=18)
        self.connection_badge = tk.Label(
            header, text="LOCAL SERVER", fg=THEME.dim, bg=THEME.header,
            font=("Cascadia Mono", 8, "bold"),
        )
        self.connection_badge.pack(side=tk.RIGHT, padx=18)

        body = tk.Frame(shell, bg=THEME.panel)
        body.pack(fill=tk.BOTH, expand=True)
        visual = tk.Canvas(
            body, bg=THEME.inset, height=220, highlightthickness=0, bd=0,
        )
        visual.pack(fill=tk.X, padx=18, pady=(18, 12))
        visual.bind(
            "<Configure>",
            lambda event: self._draw_launch_visual(visual, event.width, event.height),
        )
        content = tk.Frame(body, bg=THEME.panel)
        content.pack(fill=tk.BOTH, expand=True, padx=24, pady=(4, 18))
        tk.Label(
            content, text="THE GALAXY NOW RENDERS ON YOUR GPU",
            fg=THEME.accent, bg=THEME.panel,
            font=("Bahnschrift SemiCondensed", 13, "bold"), anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            content,
            text=(
                "Void Compass remains the private journal and profile backend. The complete atlas opens "
                "in your browser from a loopback-only address; no map data is uploaded and no internet "
                "connection is required."
            ),
            fg=THEME.muted, bg=THEME.panel, justify=tk.LEFT, wraplength=820,
            font=("Segoe UI", 10), anchor="w",
        ).pack(fill=tk.X, pady=(5, 16))

        facts = tk.Frame(content, bg=THEME.panel)
        facts.pack(fill=tk.X)
        for column, (title, detail) in enumerate((
            ("THREE-DIMENSIONAL", "Actual Elite XYZ positions, vertical structure and camera tilt"),
            ("LIVE", "Journal, route, profile and theme changes stream into the open atlas"),
            ("OFFLINE", "Bundled Three.js, Milky Way art and all 42 Codex regions"),
        )):
            card = tk.Frame(
                facts, bg=THEME.panel_alt,
                highlightthickness=1, highlightbackground=THEME.border_soft,
            )
            card.grid(
                row=0, column=column, sticky="nsew",
                padx=(0 if column == 0 else 6, 0),
            )
            facts.columnconfigure(column, weight=1)
            tk.Label(
                card, text=title, fg=THEME.orange, bg=THEME.panel_alt,
                font=("Cascadia Mono", 8, "bold"), anchor="w",
            ).pack(fill=tk.X, padx=11, pady=(9, 3))
            tk.Label(
                card, text=detail, fg=THEME.muted, bg=THEME.panel_alt,
                font=("Segoe UI", 8), justify=tk.LEFT, wraplength=245, anchor="w",
            ).pack(fill=tk.X, padx=11, pady=(0, 10))

        self.current_label = tk.Label(
            content, text="CURRENT POSITION // WAITING FOR JOURNAL STATE",
            fg=THEME.text, bg=THEME.panel,
            font=("Cascadia Mono", 9, "bold"), anchor="w",
        )
        self.current_label.pack(fill=tk.X, pady=(18, 2))
        self.status_label = tk.Label(
            content, text="Preparing local Galactic Atlas…",
            fg=THEME.dim, bg=THEME.panel,
            font=("Cascadia Mono", 8), anchor="w",
        )
        self.status_label.pack(fill=tk.X)
        actions = tk.Frame(content, bg=THEME.panel)
        actions.pack(fill=tk.X, pady=(16, 0))
        button(
            actions, "OPEN / REOPEN ATLAS", self.open_browser, accent=True,
        ).pack(side=tk.LEFT)
        button(actions, "FOCUS CURRENT", self._focus_current).pack(side=tk.LEFT, padx=(7, 0))
        button(actions, "PUBLISH LIVE DATA", self.refresh).pack(side=tk.LEFT, padx=(7, 0))

    def _draw_launch_visual(self, canvas, width, height):
        canvas.delete("all")
        width = max(240, int(width))
        height = max(120, int(height))
        cx, cy = width * 0.5, height * 0.5
        radius = min(width * 0.34, height * 0.42)
        for scale, colour in (
            (1.0, THEME.border), (0.72, THEME.border_soft), (0.42, THEME.dim),
        ):
            r = radius * scale
            canvas.create_oval(
                cx - r * 2.2, cy - r, cx + r * 2.2, cy + r, outline=colour,
            )
        for index in range(9):
            angle = index * math.tau / 9.0
            x = cx + math.cos(angle) * radius * (1.1 + (index % 3) * 0.25)
            y = cy + math.sin(angle) * radius * 0.55
            colour = THEME.orange if index == 2 else THEME.accent if index % 2 else THEME.muted
            canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill=colour, outline="")
        canvas.create_line(
            cx - radius * 1.8, cy, cx + radius * 1.8, cy,
            fill=THEME.border_soft,
        )
        canvas.create_line(
            cx, cy - radius * 0.75, cx, cy + radius * 0.75,
            fill=THEME.border_soft,
        )
        canvas.create_text(
            cx, cy, text="VOID COMPASS // HTML GALACTIC ATLAS",
            fill=THEME.accent, font=("Cascadia Mono", 10, "bold"),
        )

    @staticmethod
    def _normalise_annotations(rows):
        output = []
        for index, row in enumerate(rows or ()):
            if not isinstance(row, dict):
                continue
            position = _position(row.get("position"))
            if position is None:
                continue
            category = _bounded_text(row.get("category") or "Note", 40)
            if category not in ANNOTATION_TYPES:
                category = "Note"
            output.append({
                "id": _bounded_text(row.get("id") or f"legacy-{index}", 100),
                "category": category,
                "title": _bounded_text(row.get("title") or category, 120),
                "note": _bounded_text(row.get("note"), 2000),
                "system": _bounded_text(row.get("system"), 120),
                "position": list(position),
                "created": _bounded_text(row.get("created"), 80),
            })
        return output

    def _normalise_view_state(self, state):
        state = state if isinstance(state, dict) else {}
        layers = {name: name != "Return" for name in LAYER_NAMES}
        for name, enabled in (state.get("layers") or {}).items():
            if name in layers:
                layers[name] = bool(enabled)
        mode = str(state.get("mode") or "Galactic Atlas")
        if mode not in VIEW_MODES:
            mode = "Galactic Atlas"
        scope = str(
            state.get("scope") or self.config.get("explore_map_scope") or "All History"
        )
        if scope not in SCOPES:
            scope = "All History"
        camera = state.get("camera") if isinstance(state.get("camera"), dict) else {}
        orientation_matches = state.get("orientation") == MAP_ORIENTATION
        position = _position(camera.get("position")) if orientation_matches else None
        target = _position(camera.get("target")) if orientation_matches else None
        try:
            depth_scale = max(1.0, min(20.0, float(state.get("depth_scale", 4.0))))
        except (TypeError, ValueError):
            depth_scale = 4.0
        return {
            "renderer": "webgl", "orientation": MAP_ORIENTATION,
            "mode": mode, "scope": scope, "layers": layers,
            "camera": {
                "position": list(position) if position else None,
                "target": list(target) if target else None,
            },
            "depth_scale": depth_scale,
            "top_down": bool(state.get("top_down", False)) if orientation_matches else False,
        }

    def apply_view_state(self, state):
        self._view_state = self._normalise_view_state(state)
        if hasattr(self, "server"):
            self.refresh()

    def view_state(self):
        return dict(self._view_state)

    def _persist_view_state(self):
        self.config["explore_map_view_state"] = dict(self._view_state)
        self.config["explore_map_scope"] = self._view_state.get("scope", "All History")
        persist = getattr(self.app, "_persist_config", None)
        if callable(persist):
            persist()

    def _persist_annotations(self):
        self.config["explore_map_annotations"] = [dict(row) for row in self._annotations]
        persist = getattr(self.app, "_persist_config", None)
        if callable(persist):
            persist()

    @staticmethod
    def _light_route_row(row):
        position = _position(row.get("pos"))
        if position is None:
            return None
        return {
            "system": _bounded_text(row.get("system"), 120),
            "pos": list(position),
            "timestamp": _bounded_text(row.get("timestamp"), 80),
            "jump_dist": round(float(row.get("jump_dist") or 0.0), 3),
            "star_class": _bounded_text(row.get("star_class"), 40),
            "fss_complete": bool(row.get("fss_complete")),
        }

    def _build_markers(self, survey_snapshot, bookmarks, positions):
        markers = []

        def add(layer, kind, system="", subject="", detail="", position=None, **extra):
            position_value = _position(position) or positions.get(str(system or "").casefold())
            if position_value is None:
                return
            row = {
                "layer": layer, "kind": kind,
                "system": _bounded_text(system, 120),
                "subject": _bounded_text(subject or kind, 160),
                "detail": _bounded_text(detail, 500),
                "position": list(position_value),
            }
            row.update(extra)
            markers.append(row)

        grouped_values = defaultdict(list)
        for row in self._value_rows:
            if row.get("system"):
                grouped_values[str(row["system"])].append(row)
        for system, rows in grouped_values.items():
            top = max(rows, key=lambda row: int(row.get("value") or 0))
            add(
                "Valuable", "Valuable", system,
                top.get("body") or f"{len(rows)} valuable worlds",
                f"{len(rows)} retained · top {int(top.get('value') or 0):,} cr",
            )
        for row in self._system_rows:
            signals = int(row.get("bio_signals") or 0)
            if signals:
                add(
                    "Biology", "System", row.get("system"), "Biological survey",
                    f"{signals} biological signal{'s' if signals != 1 else ''}",
                )

        def grouped(rows):
            output = defaultdict(list)
            for row in rows or ():
                if isinstance(row, dict) and row.get("system"):
                    output[str(row["system"])].append(row)
            return output

        for system, rows in grouped(survey_snapshot.get("codex")).items():
            add(
                "Codex", "Codex", system, rows[-1].get("name") or "Codex records",
                f"{len(rows)} Codex record(s)",
            )
        for system, rows in grouped(survey_snapshot.get("screenshots")).items():
            add(
                "Photos", "Photo", system, rows[-1].get("body") or "Screenshot",
                f"{len(rows)} screenshot(s)",
            )
        for row in survey_snapshot.get("candidates") or ():
            add(
                "Recon", "Recon", row.get("system"), "Recon candidate",
                f"{int(row.get('score') or 0)}/100 {row.get('grade') or ''}",
            )
        for row in survey_snapshot.get("revisit_queue") or ():
            add(
                "Revisit", "Revisit", row.get("system"), "Unfinished exploration",
                row.get("detail") or "Worthwhile survey work remains",
                position=row.get("position"),
            )
        for row in bookmarks:
            add(
                "Bookmarks", "Bookmark", row.get("system"),
                row.get("title") or row.get("kind") or "Bookmark",
                " · ".join(filter(None, (
                    str(row.get("priority") or ""), ", ".join(row.get("tags") or []),
                ))),
                position=row.get("position"), bookmark_id=row.get("id"),
            )
        for row in self._annotations:
            add(
                "Annotations", "Annotation", row.get("system"), row.get("title"),
                row.get("note") or row.get("category"), position=row.get("position"),
                annotation_id=row.get("id"), category=row.get("category"),
                note=row.get("note"),
            )

        manager = getattr(self.app, "expedition_manager", None)
        active = manager.active() if manager else None
        plan = (active or {}).get("sector_plan")
        if isinstance(plan, dict) and plan.get("center"):
            grid = sector_grid(
                survey_snapshot.get("route_points") or (), plan.get("center"),
                plan.get("radius_ly", 500), plan.get("cell_size_ly", 100),
            )
            cells = list(grid.get("cells") or [])
            important = [row for row in cells if row.get("status") != "untouched"]
            untouched = [row for row in cells if row.get("status") == "untouched"]
            allowance = max(0, 140 - len(important))
            if allowance and len(untouched) > allowance:
                untouched = _sample_rows(untouched, allowance)
            for row in important + untouched[:allowance]:
                status = str(row.get("status") or "untouched")
                add(
                    "Sectors", "Sector", "",
                    f"{plan.get('name') or 'Expedition sector'} · cell {row.get('id')}",
                    f"{status.title()} · {int(row.get('surveyed_systems') or 0)}/"
                    f"{int(row.get('visited_systems') or 0)} visited systems FSS complete",
                    position=row.get("position"), status=status,
                    cell_size=float(
                        grid.get("cell_size_ly") or plan.get("cell_size_ly") or 100
                    ),
                )
        return markers

    def _build_snapshot(self):
        tracker = getattr(self.app, "deep_survey", None)
        survey = tracker.snapshot() if tracker else {}
        raw_route = [
            row for row in survey.get("route_points") or ()
            if isinstance(row, dict) and _position(row.get("pos")) is not None
        ]
        route = [
            light for row in _sample_rows(raw_route)
            if (light := self._light_route_row(row)) is not None
        ]
        positions = {
            str(row.get("system") or "").casefold(): tuple(row["pos"])
            for row in route if row.get("system")
        }
        current_system = _bounded_text(getattr(self.app, "current_sys", ""), 120)
        current_position = _position(getattr(self.app, "current_coords", None))
        if current_position is not None and current_system:
            positions[current_system.casefold()] = current_position

        manager = getattr(self.app, "expedition_manager", None)
        bookmarks = list(manager.bookmarks() if manager else [])
        for row in bookmarks:
            position = _position(row.get("position"))
            if position is not None and row.get("system"):
                positions[str(row["system"]).casefold()] = position
        self._annotations = self._normalise_annotations(
            self.config.get("explore_map_annotations")
        )
        planned_context = route_context(self.app)
        planned = []
        for row in planned_context.get("planned") or ():
            position = _position(row.get("pos"))
            if position is None:
                continue
            planned.append({
                "system": _bounded_text(row.get("system"), 120),
                "pos": list(position), "source": _bounded_text(row.get("source"), 30),
                "visited": bool(row.get("visited")),
            })
            if row.get("system"):
                positions[str(row["system"]).casefold()] = position
        markers = self._build_markers(survey, bookmarks, positions)

        active = manager.active() if manager else None
        active_stats = (active or {}).get("stats") or {}
        active_systems = [str(value) for value in active_stats.get("systems") or []]
        region = find_region(*current_position) if current_position else None
        total_ly = sum(float(row.get("jump_dist") or 0.0) for row in route)
        unique_systems = len({row.get("system") for row in route if row.get("system")})
        profile = _bounded_text(self.config.get("active_commander_profile"), 160)
        commander = _bounded_text(
            self.config.get("active_commander_name") or getattr(self.app, "cmdr_name", ""),
            120,
        )
        ship = getattr(self.app, "cmdr_ship", None)
        ship = ship if isinstance(ship, dict) else {}
        return {
            "schema": 1,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "profile": {"id": profile, "commander": commander},
            "theme": _theme_payload(),
            "reduced_motion": bool(self.config.get("reduced_motion_enabled", False)),
            "view_state": self._view_state,
            "current": {
                "system": current_system,
                "position": list(current_position) if current_position else None,
                "region": {
                    "id": int(region[0]), "name": str(region[1]),
                } if region else None,
                "ship": _bounded_text(
                    ship.get("ship_name") or ship.get("ship_localised") or ship.get("ship"),
                    100,
                ),
            },
            "summary": {
                "systems": unique_systems, "distance_ly": round(total_ly, 1),
                "markers": len(markers), "annotations": len(self._annotations),
                "regions": 42,
            },
            "session": {
                "started_epoch": float(getattr(self.app, "session_start_ts", 0.0) or 0.0),
            },
            "expedition": {
                "id": (active or {}).get("id"), "name": (active or {}).get("name"),
                "started": (active or {}).get("started"),
                "start_system": (active or {}).get("start_system"),
                "systems": active_systems,
            } if active else None,
            "route": route,
            "planned": planned,
            "route_context": {
                key: planned_context.get(key)
                for key in (
                    "on_route", "off_route", "nearest_system",
                    "nearest_distance_ly", "next_system", "remaining",
                )
            },
            "markers": markers,
            "annotations": self._annotations,
            "focus_request": self._focus_request,
        }

    def refresh(self, system_rows=None, value_rows=None):
        if self._disposed:
            return
        if system_rows is not None:
            self._system_rows = list(system_rows or [])
        if value_rows is not None:
            self._value_rows = list(value_rows or [])
        try:
            snapshot = self._build_snapshot()
        except Exception as exc:
            self.status_label.config(
                text=f"Atlas data preparation failed: {exc}", fg=THEME.red,
            )
            return
        self._latest_snapshot = snapshot
        self.server.publish(snapshot)
        current = snapshot.get("current") or {}
        region = current.get("region") or {}
        current_text = current.get("system") or "POSITION UNKNOWN"
        if region.get("name"):
            current_text += (
                f" // REGION {int(region.get('id') or 0):02d} {region['name'].upper()}"
            )
        self.current_label.config(text=f"CURRENT POSITION // {current_text}")
        summary = snapshot.get("summary") or {}
        self.status_label.config(
            text=(
                f"Published {int(summary.get('systems') or 0):,} retained systems, "
                f"{int(summary.get('markers') or 0):,} intelligence markers and "
                f"{int(summary.get('annotations') or 0):,} commander annotations"
            ),
            fg=THEME.dim,
        )

    def focus_system(self, system):
        wanted = str(system or "").strip().casefold()
        if not wanted:
            return False
        snapshot = self._latest_snapshot or {}
        row = next((
            row for row in snapshot.get("route") or ()
            if str(row.get("system") or "").casefold() == wanted
        ), None)
        if row is None:
            row = next((
                marker for marker in snapshot.get("markers") or ()
                if str(marker.get("system") or "").casefold() == wanted
            ), None)
        position = _position((row or {}).get("pos") or (row or {}).get("position"))
        if position is None:
            return False
        self._focus_sequence += 1
        self._focus_request = {
            "id": self._focus_sequence, "system": _bounded_text(system, 120),
            "position": list(position),
        }
        self.refresh()
        return True

    def _focus_current(self):
        current = (
            (self._latest_snapshot.get("current") or {})
            if self._latest_snapshot else {}
        )
        position = _position(current.get("position"))
        if position is None:
            return
        self._focus_sequence += 1
        self._focus_request = {
            "id": self._focus_sequence,
            "system": current.get("system") or "Current position",
            "position": list(position),
        }
        self.refresh()
        self.open_browser()

    def open_browser(self):
        if self._disposed:
            return
        self._opened_once = True
        self.status_label.config(
            text="Opening the live Galactic Atlas in your browser…", fg=THEME.accent,
        )
        threading.Thread(
            target=lambda: webbrowser.open_new_tab(self.server.url),
            name="galactic-atlas-launch", daemon=True,
        ).start()

    def on_shown(self):
        if self._disposed:
            return
        self.refresh()
        stale = time.monotonic() - float(self.server.last_client_seen or 0.0) > 10.0
        if not self._opened_once or (not self.server.client_count and stale):
            self.open_browser()

    def has_live_browser(self, grace_seconds=20.0):
        """Return whether an opened browser atlas still consumes snapshots.

        The HTML atlas is independent of the native GALACTIC workspace after
        launch.  Keep publishing while its event stream is connected, with a
        short grace period for Chromium reconnects and background-tab stalls.
        """
        if self._disposed or not self._opened_once or not hasattr(self, "server"):
            return False
        clients, seen = self._server_status_hint
        if clients > 0:
            return True
        return bool(
            seen
            and time.monotonic() - float(seen) <= max(0.0, float(grace_seconds))
        )

    def _queue_browser_command(self, payload):
        if self._disposed or not isinstance(payload, dict):
            return False
        self._browser_commands.put(dict(payload))
        return True

    def _drain_browser_commands(self):
        """Apply browser work only from Tk's owning UI thread."""
        for _index in range(64):
            try:
                payload = self._browser_commands.get_nowait()
            except queue.Empty:
                break
            self._handle_browser_command(payload)

    def _handle_browser_command(self, payload):
        if self._disposed:
            return
        action = str(payload.get("action") or "")
        if action in {"ready", "heartbeat"}:
            self.connection_badge.config(text="ATLAS CONNECTED", fg=THEME.green)
            return
        if action == "save_view":
            self._view_state = self._normalise_view_state(payload.get("state"))
            self._persist_view_state()
            return
        if action == "annotation_upsert":
            raw = payload.get("annotation")
            if not isinstance(raw, dict):
                return
            position = _position(raw.get("position"))
            if position is None:
                return
            category = _bounded_text(raw.get("category") or "Note", 40)
            if category not in ANNOTATION_TYPES:
                category = "Note"
            annotation_id = _bounded_text(raw.get("id"), 100) or f"map-{time.time_ns():x}"
            row = {
                "id": annotation_id, "category": category,
                "title": _bounded_text(raw.get("title") or category, 120),
                "note": _bounded_text(raw.get("note"), 2000),
                "system": _bounded_text(raw.get("system"), 120),
                "position": list(position),
                "created": _bounded_text(raw.get("created"), 80)
                or datetime.now().astimezone().isoformat(),
            }
            self._annotations = [
                item for item in self._annotations if item.get("id") != annotation_id
            ] + [row]
            self.config["explore_map_annotations"] = [
                dict(item) for item in self._annotations
            ]
            self._persist_annotations()
            feed = getattr(self.app, "add_event_feed_entry", None)
            if callable(feed):
                feed("MAP", f"Annotation saved: {row['title']}", severity="INFO")
            self.refresh()
            return
        if action == "annotation_delete":
            annotation_id = _bounded_text(payload.get("id"), 100)
            existing = next((
                row for row in self._annotations if row.get("id") == annotation_id
            ), None)
            if existing is None:
                return
            self._annotations = [
                row for row in self._annotations if row.get("id") != annotation_id
            ]
            self.config["explore_map_annotations"] = [
                dict(item) for item in self._annotations
            ]
            self._persist_annotations()
            feed = getattr(self.app, "add_event_feed_entry", None)
            if callable(feed):
                feed(
                    "MAP", f"Annotation deleted: {existing.get('title') or 'Map mark'}",
                    severity="INFO",
                )
            self.refresh()
            return
        if action == "open_record":
            record = payload.get("record")
            if isinstance(record, dict) and callable(self.open_record_callback):
                self.open_record_callback({
                    key: record.get(key)
                    for key in (
                        "kind", "system", "subject", "detail", "bookmark_id",
                        "annotation_id", "category", "position",
                    )
                })

    def _server_status_changed(self, clients, seen):
        self._server_status_hint = (int(clients or 0), float(seen or 0.0))

    def _update_connection_badge(self):
        if self._disposed:
            return
        clients, seen = self._server_status_hint
        recent = time.monotonic() - seen < 12.0
        if clients or recent:
            self.connection_badge.config(text="ATLAS CONNECTED", fg=THEME.green)
        else:
            self.connection_badge.config(text="LOCAL SERVER READY", fg=THEME.accent)

    def _schedule_status_tick(self):
        if self._disposed:
            return
        self._drain_browser_commands()
        self._update_connection_badge()
        try:
            self._status_job = self.parent.after(250, self._schedule_status_tick)
        except tk.TclError:
            self._status_job = None

    def dispose(self):
        self._disposed = True
        if self._status_job is not None:
            try:
                self.parent.after_cancel(self._status_job)
            except tk.TclError:
                pass
        self._status_job = None
        if hasattr(self, "server"):
            self.server.stop_async()
