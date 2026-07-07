import json
import os
import re
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime

from config import COLOR_ACCENT, COLOR_BG, COLOR_GREEN, COLOR_ORANGE, COLOR_TEXT, save_config
from mining_data import MiningDataStore, normalize_material_name, normalize_ring_type, search_spansh_rings

MINING_SESSIONS_FILE = "mining_sessions.json"


def load_mining_sessions_json(path=None):
    """Load all saved sessions from the JSON file. Returns a list ordered newest-first."""
    path = path or MINING_SESSIONS_FILE
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def save_mining_sessions_json(sessions, path=None):
    """Persist the sessions list to the JSON file (newest-first)."""
    path = path or MINING_SESSIONS_FILE
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


MINING_MATERIALS = {
    "Alexandrite",
    "Benitoite",
    "Bromellite",
    "Grandidierite",
    "Low Temperature Diamonds",
    "Monazite",
    "Musgravite",
    "Osmium",
    "Painite",
    "Palladium",
    "Platinum",
    "Rhodplumsite",
    "Serendibite",
    "Tritium",
    "Void Opals",
}


MATERIAL_ALIASES = {
    "lowtemperaturediamond": "Low Temperature Diamonds",
    "low temperature diamond": "Low Temperature Diamonds",
    "low temperature diamonds": "Low Temperature Diamonds",
    "low temp diamonds": "Low Temperature Diamonds",
    "low temp. diamonds": "Low Temperature Diamonds",
    "opal": "Void Opals",
    "void opal": "Void Opals",
    "void opals": "Void Opals",
    "painite": "Painite",
    "platinum": "Platinum",
    "tritium": "Tritium",
    "alexandrite": "Alexandrite",
    "benitoite": "Benitoite",
    "bromellite": "Bromellite",
    "grandidierite": "Grandidierite",
    "monazite": "Monazite",
    "musgravite": "Musgravite",
    "osmium": "Osmium",
    "palladium": "Palladium",
    "rhodplumsite": "Rhodplumsite",
    "serendibite": "Serendibite",
}


def _clean_name(value):
    text = normalize_material_name(value)
    text = re.sub(r"\s*\([^)]*\)", "", text).strip()
    if text.lower().startswith("material content"):
        text = text[len("material content"):].strip(": ")
    return MATERIAL_ALIASES.get(text.lower(), text.title())


def _fmt_pct(value):
    try:
        value = float(value)
    except Exception:
        return "-"
    text = f"{value:.1f}"
    if text.endswith(".0"):
        text = text[:-2]
    return f"{text}%"


def _event_time(raw):
    stamp = raw.get("timestamp") if isinstance(raw, dict) else None
    if not stamp:
        return datetime.now().strftime("%H:%M:%S")
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).strftime("%H:%M:%S")
    except Exception:
        return datetime.now().strftime("%H:%M:%S")


def _ring_body_name(full_body_name, system_name):
    body = str(full_body_name or "").strip()
    system = str(system_name or "").strip()
    if system and body.lower().startswith(system.lower()):
        body = body[len(system):].strip()
    return " ".join(body.split()) or full_body_name or "-"


class MiningWindow:
    def __init__(self, root, config, get_current_system=None, get_cargo_capacity=None, get_current_coords=None):
        self.root = root
        self.config = config
        self.get_current_system = get_current_system or (lambda: "---")
        self.get_cargo_capacity = get_cargo_capacity or (lambda: 0)
        self.get_current_coords = get_current_coords or (lambda: None)

        self.win = tk.Toplevel(root)
        self.win.title("VOID COMPASS // MINING")
        self.win.geometry(self.config.get("mining_geometry", "980x680"))
        self.win.configure(bg=COLOR_BG)
        self.win.protocol("WM_DELETE_WINDOW", self.on_close)

        self.session_active = False
        self.session_started_at = None
        self.prospected_count = 0
        self.core_count = 0
        self.mined_tons = {}
        self.material_stats = {}
        self.latest_prospector = "Waiting for prospector data."
        self.cargo_inventory = []
        self.cargo_capacity = int(self.get_cargo_capacity() or 0)
        self.current_system = self.get_current_system() or "---"
        self.current_body = "-"
        self.ring_metadata = {}
        self.hotspots = {}
        self.missions = {}
        self.last_status_cargo = None
        self.mining_sessions_file = self.config.get("mining_sessions_file", MINING_SESSIONS_FILE)
        self.data_store = MiningDataStore(self.config.get("mining_db_file"))
        self.session_id = None
        self._json_sessions = load_mining_sessions_json(self.mining_sessions_file)   # in-memory list, newest-first
        self._json_session_key = None                        # started_at key for current session
        self.search_results = []
        self.search_running = False

        self._build_style()
        self._build_layout()
        self._refresh_bookmarks()
        self._refresh_sessions()
        self._tick()

    def _build_style(self):
        self.style = ttk.Style(self.win)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self.style.configure("Mining.TNotebook", background=COLOR_BG, borderwidth=0)
        self.style.configure(
            "Mining.TNotebook.Tab",
            background="#10161c",
            foreground=COLOR_TEXT,
            padding=(12, 6),
            font=("Segoe UI", 9, "bold"),
        )
        self.style.map(
            "Mining.TNotebook.Tab",
            background=[("selected", "#17232c")],
            foreground=[("selected", COLOR_ACCENT)],
        )
        self.style.configure(
            "Mining.Treeview",
            background="#090c10",
            foreground=COLOR_TEXT,
            fieldbackground="#090c10",
            borderwidth=0,
            rowheight=22,
            font=("Consolas", 9),
        )
        self.style.configure(
            "Mining.Treeview.Heading",
            background="#121920",
            foreground=COLOR_ACCENT,
            font=("Segoe UI", 8, "bold"),
        )

    def _build_layout(self):
        header = tk.Frame(self.win, bg="#0c1014")
        header.pack(fill=tk.X, padx=12, pady=(12, 8))
        tk.Label(
            header,
            text="MINING CONTROL",
            bg="#0c1014",
            fg=COLOR_ACCENT,
            font=("Segoe UI", 14, "bold"),
        ).pack(side=tk.LEFT, padx=12, pady=10)
        self.session_label = tk.Label(
            header,
            text="SESSION: IDLE",
            bg="#0c1014",
            fg=COLOR_ORANGE,
            font=("Consolas", 10, "bold"),
        )
        self.session_label.pack(side=tk.LEFT, padx=20)
        self.start_btn = self._button(header, "Start Session", self.start_session, accent=True)
        self.start_btn.pack(side=tk.RIGHT, padx=(6, 12), pady=9)
        self.stop_btn = self._button(header, "Stop", self.stop_session)
        self.stop_btn.pack(side=tk.RIGHT, padx=6, pady=9)
        self.reset_btn = self._button(header, "Reset", self.reset_session)
        self.reset_btn.pack(side=tk.RIGHT, padx=6, pady=9)

        self.notebook = ttk.Notebook(self.win, style="Mining.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self._build_session_tab()
        self._build_prospector_tab()
        self._build_cargo_tab()
        self._build_hotspots_tab()
        self._build_missions_tab()
        self._build_reports_tab()

    def _button(self, parent, text, command, accent=False):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=COLOR_ACCENT if accent else "#121920",
            fg="black" if accent else COLOR_TEXT,
            activebackground=COLOR_ACCENT if accent else "#1a2630",
            activeforeground="black" if accent else COLOR_TEXT,
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
        )

    def _panel(self, parent):
        return tk.Frame(parent, bg="#11161c", highlightbackground="#26313a", highlightthickness=1, bd=0)

    def _metric(self, parent, title, value="-"):
        frame = self._panel(parent)
        tk.Label(frame, text=title, bg="#11161c", fg="#7d8891", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
        label = tk.Label(frame, text=value, bg="#11161c", fg=COLOR_TEXT, font=("Consolas", 13, "bold"), anchor="w")
        label.pack(fill=tk.X, padx=10, pady=(2, 8))
        return frame, label

    def _tree(self, parent, columns):
        tree = ttk.Treeview(parent, columns=[key for key, _label, _width in columns], show="headings", style="Mining.Treeview")
        for key, label, width in columns:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor=tk.W)
        scroll = tk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    def _build_session_tab(self):
        tab = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(tab, text="Session")

        metrics = tk.Frame(tab, bg=COLOR_BG)
        metrics.pack(fill=tk.X, padx=2, pady=(2, 10))
        for col in range(4):
            metrics.grid_columnconfigure(col, weight=1)
        _, self.system_metric = self._metric(metrics, "SYSTEM", self.current_system)
        _, self.cargo_metric = self._metric(metrics, "CARGO", "0/0 t")
        _, self.prospected_metric = self._metric(metrics, "PROSPECTED", "0")
        _, self.mined_metric = self._metric(metrics, "MINED", "0 t")
        self.system_metric.master.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.cargo_metric.master.grid(row=0, column=1, sticky="ew", padx=6)
        self.prospected_metric.master.grid(row=0, column=2, sticky="ew", padx=6)
        self.mined_metric.master.grid(row=0, column=3, sticky="ew", padx=(6, 0))

        body = tk.Frame(tab, bg=COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True)
        left = self._panel(body)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        right = self._panel(body)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        tk.Label(left, text="MATERIAL STATS", bg="#11161c", fg=COLOR_ACCENT, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=8)
        tree_frame = tk.Frame(left, bg="#11161c")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.material_tree = self._tree(tree_frame, [
            ("material", "Material", 180),
            ("hits", "Hits", 60),
            ("avg", "Avg", 70),
            ("best", "Best", 70),
            ("latest", "Latest", 70),
        ])

        tk.Label(right, text="MINED CARGO", bg="#11161c", fg=COLOR_ACCENT, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=8)
        mined_frame = tk.Frame(right, bg="#11161c")
        mined_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.mined_tree = self._tree(mined_frame, [
            ("commodity", "Commodity", 220),
            ("tons", "Tons", 90),
        ])

    def _build_prospector_tab(self):
        tab = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(tab, text="Prospector")
        latest = self._panel(tab)
        latest.pack(fill=tk.X, padx=2, pady=(2, 10))
        tk.Label(latest, text="LATEST PROSPECTOR", bg="#11161c", fg=COLOR_ACCENT, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
        self.latest_label = tk.Label(latest, text=self.latest_prospector, bg="#11161c", fg=COLOR_TEXT, font=("Consolas", 11), anchor="w", justify=tk.LEFT, wraplength=900)
        self.latest_label.pack(fill=tk.X, padx=10, pady=10)

        history = self._panel(tab)
        history.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))
        tk.Label(history, text="PROSPECTOR HISTORY", bg="#11161c", fg=COLOR_ACCENT, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=8)
        frame = tk.Frame(history, bg="#11161c")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.prospector_tree = self._tree(frame, [
            ("time", "Time", 80),
            ("content", "Content", 120),
            ("remaining", "Remaining", 90),
            ("materials", "Materials", 520),
            ("core", "Core", 160),
        ])

    def _build_cargo_tab(self):
        tab = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(tab, text="Cargo")
        frame = self._panel(tab)
        frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        tk.Label(frame, text="LIVE CARGO", bg="#11161c", fg=COLOR_ACCENT, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=8)
        tree_frame = tk.Frame(frame, bg="#11161c")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.cargo_tree = self._tree(tree_frame, [
            ("name", "Name", 300),
            ("count", "Count", 90),
            ("mining", "Mining", 90),
        ])

    def _build_hotspots_tab(self):
        tab = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(tab, text="Hotspots")
        frame = self._panel(tab)
        frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        tk.Label(frame, text="HOTSPOT FINDER", bg="#11161c", fg=COLOR_ACCENT, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(8, 4))

        controls = tk.Frame(frame, bg="#11161c")
        controls.pack(fill=tk.X, padx=10, pady=(0, 8))
        tk.Label(controls, text="Material", bg="#11161c", fg="#7d8891", font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(controls, text="Ring", bg="#11161c", fg="#7d8891", font=("Segoe UI", 8, "bold")).grid(row=0, column=1, sticky="w", padx=(8, 0))
        tk.Label(controls, text="Source", bg="#11161c", fg="#7d8891", font=("Segoe UI", 8, "bold")).grid(row=0, column=2, sticky="w", padx=(8, 0))
        tk.Label(controls, text="Range LY", bg="#11161c", fg="#7d8891", font=("Segoe UI", 8, "bold")).grid(row=0, column=3, sticky="w", padx=(8, 0))

        materials = ["All"] + sorted(MINING_MATERIALS)
        self.hotspot_material_var = tk.StringVar(value="Platinum")
        self.hotspot_ring_var = tk.StringVar(value="All")
        self.hotspot_source_var = tk.StringVar(value="Both")
        self.hotspot_range_var = tk.StringVar(value="300")
        ttk.Combobox(controls, textvariable=self.hotspot_material_var, values=materials, width=24, state="readonly").grid(row=1, column=0, sticky="ew")
        ttk.Combobox(controls, textvariable=self.hotspot_ring_var, values=["All", "Metallic", "Metal Rich", "Rocky", "Icy"], width=14, state="readonly").grid(row=1, column=1, sticky="ew", padx=(8, 0))
        ttk.Combobox(controls, textvariable=self.hotspot_source_var, values=["Both", "Local", "Spansh"], width=10, state="readonly").grid(row=1, column=2, sticky="ew", padx=(8, 0))
        tk.Entry(controls, textvariable=self.hotspot_range_var, width=8, bg="#090c10", fg=COLOR_TEXT, insertbackground=COLOR_ACCENT, relief=tk.FLAT).grid(row=1, column=3, sticky="ew", padx=(8, 0), ipady=4)
        self._button(controls, "Search", self.search_hotspots, accent=True).grid(row=1, column=4, padx=(10, 0))
        self._button(controls, "Bookmark", self.bookmark_selected_hotspot).grid(row=1, column=5, padx=(6, 0))
        self._button(controls, "Import DB", self.import_elitemining_db).grid(row=1, column=6, padx=(6, 0))
        controls.grid_columnconfigure(0, weight=1)

        self.hotspot_status_label = tk.Label(frame, text="Local discoveries from journal scans appear here. Use Import DB for an EliteMining user_data.db, or Source=Spansh for live search.", bg="#11161c", fg="#7d8891", font=("Consolas", 8), anchor="w")
        self.hotspot_status_label.pack(fill=tk.X, padx=10, pady=(0, 6))

        tree_frame = tk.Frame(frame, bg="#11161c")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.hotspot_tree = self._tree(tree_frame, [
            ("system", "System", 180),
            ("body", "Ring", 180),
            ("material", "Material", 180),
            ("count", "Signals", 70),
            ("ring_type", "Ring Type", 100),
            ("distance", "LY", 70),
            ("ls", "LS", 70),
            ("overlap", "Overlap", 80),
            ("res", "RES", 80),
        ])

    def _build_missions_tab(self):
        tab = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(tab, text="Missions")
        frame = self._panel(tab)
        frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        tk.Label(frame, text="ACTIVE MINING MISSIONS", bg="#11161c", fg=COLOR_ACCENT, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=8)
        tree_frame = tk.Frame(frame, bg="#11161c")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.mission_tree = self._tree(tree_frame, [
            ("id", "Mission ID", 100),
            ("commodity", "Commodity", 180),
            ("progress", "Progress", 120),
            ("destination", "Destination", 220),
            ("expires", "Expires", 170),
        ])

    def _build_reports_tab(self):
        tab = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(tab, text="History")

        top = tk.Frame(tab, bg=COLOR_BG)
        top.pack(fill=tk.BOTH, expand=True)
        left = self._panel(top)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 6), pady=2)
        right = self._panel(top)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 2), pady=2)

        session_header = tk.Frame(left, bg="#11161c")
        session_header.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(session_header, text="SESSION HISTORY", bg="#11161c", fg=COLOR_ACCENT, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self._button(session_header, "Generate Report", self.generate_selected_report).pack(side=tk.RIGHT)
        session_frame = tk.Frame(left, bg="#11161c")
        session_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.session_tree = self._tree(session_frame, [
            ("started", "Started", 165),
            ("system", "System", 175),
            ("prospected", "Prospected", 90),
            ("tons", "Tons", 70),
            ("cargo", "Cargo", 260),
            ("status", "Status", 130),
        ])

        bookmark_header = tk.Frame(right, bg="#11161c")
        bookmark_header.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(bookmark_header, text="BOOKMARKS", bg="#11161c", fg=COLOR_ACCENT, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self._button(bookmark_header, "Refresh", self._refresh_bookmarks).pack(side=tk.RIGHT)
        bookmark_frame = tk.Frame(right, bg="#11161c")
        bookmark_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.bookmark_tree = self._tree(bookmark_frame, [
            ("system", "System", 160),
            ("body", "Ring", 180),
            ("material", "Material", 150),
            ("created", "Created", 150),
        ])

    def is_open(self):
        try:
            return bool(self.win and self.win.winfo_exists())
        except Exception:
            return False

    def lift(self):
        self.win.deiconify()
        self.win.lift()

    def on_close(self):
        self._save_current_session_progress()
        self.config["mining_geometry"] = self.win.geometry()
        try:
            save_config(self.config)
        except Exception:
            pass
        self.win.destroy()

    def start_session(self):
        self.session_active = True
        self.session_started_at = time.time()
        started_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        self.session_id = self.data_store.create_session(
            started_at,
            self.current_system,
            self.current_body,
        )
        self.prospected_count = 0
        self.core_count = 0
        self.mined_tons = {}
        self.material_stats = {}
        # Create the JSON record for this session
        self._json_session_key = started_at
        record = {
            "started_at": started_at,
            "ended_at": None,
            "system_name": self.current_system,
            "body_name": self.current_body,
            "prospected_count": 0,
            "core_count": 0,
            "mined_tons": {},
            "material_stats": {},
            "in_progress": True,
        }
        self._json_sessions.insert(0, record)
        save_mining_sessions_json(self._json_sessions, self.mining_sessions_file)
        self._refresh_all()

    def stop_session(self):
        self.session_active = False
        self._finish_current_session()
        self._refresh_all()

    def reset_session(self):
        if self.session_active:
            self._finish_current_session()
        self.session_active = False
        self.session_started_at = None
        self.session_id = None
        self._json_session_key = None
        self.prospected_count = 0
        self.core_count = 0
        self.mined_tons = {}
        self.material_stats = {}
        self.latest_prospector = "Waiting for prospector data."
        self._clear_tree(self.prospector_tree)
        self._refresh_all()

    def process_event(self, event):
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, lambda e=event: self.process_event(e))
            return
        if not self.is_open():
            return
        raw = event.get("raw", event)
        ev = event.get("type") or raw.get("event")
        data = event.get("data", raw)

        if ev == "Loadout":
            self.cargo_capacity = int(data.get("cargo_capacity") or raw.get("CargoCapacity") or self.cargo_capacity or 0)
        elif ev in ("Location", "FSDJump"):
            new_sys = data.get("star_system") or raw.get("StarSystem") or self.current_system
            if new_sys != self.current_system and self.session_active:
                # Jumped to a new system — auto-stop the active session
                self.session_active = False
                self._finish_current_session()
            self.current_system = new_sys
            self.current_body = raw.get("Body") or self.current_body
        elif ev == "Scan":
            self._process_scan(raw)
        elif ev == "SAASignalsFound":
            self._process_saa_signals(raw)
        elif ev == "ProspectedAsteroid":
            self._process_prospector(raw)
        elif ev == "MiningRefined":
            self._process_refined(raw)
        elif ev == "Cargo":
            self._apply_cargo_event(raw)
        elif ev == "MissionAccepted":
            self._process_mission_accepted(raw)
        elif ev in ("MissionCompleted", "MissionAbandoned", "MissionFailed"):
            mission_id = raw.get("MissionID")
            if mission_id in self.missions:
                self.missions.pop(mission_id, None)
        elif ev == "CargoDepot":
            self._process_cargo_depot(raw)

        self._refresh_all()

    def update_cargo(self, inventory, capacity=None):
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, lambda i=list(inventory or []), c=capacity: self.update_cargo(i, c))
            return
        self.cargo_inventory = list(inventory or [])
        if capacity:
            self.cargo_capacity = int(capacity)
        self._refresh_all()

    def update_status(self, status):
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, lambda s=dict(status or {}): self.update_status(s))
            return
        try:
            if status.get("CargoCapacity") is not None:
                self.cargo_capacity = int(status.get("CargoCapacity") or self.cargo_capacity or 0)
            if status.get("Cargo") is not None:
                self.last_status_cargo = int(status.get("Cargo") or 0)
        except Exception:
            pass
        self._refresh_all()

    def _process_scan(self, raw):
        system = raw.get("StarSystem") or self.current_system
        distance = raw.get("DistanceFromArrivalLS")
        for ring in raw.get("Rings", []) or []:
            name = ring.get("Name")
            if not name:
                continue
            ring_class = str(ring.get("RingClass") or "").replace("eRingClass_", "")
            ring_class = normalize_ring_type(ring_class) or "-"
            body = _ring_body_name(name, system)
            self.ring_metadata[(system, body)] = {
                "ring_type": ring_class or "-",
                "distance": distance,
            }

    def _process_saa_signals(self, raw):
        body_name = raw.get("BodyName") or ""
        if "ring" not in body_name.lower():
            return
        system = raw.get("StarSystem") or self.current_system
        body = _ring_body_name(body_name, system)
        meta = self.ring_metadata.get((system, body), {})
        for signal in raw.get("Signals", []) or []:
            material = _clean_name(signal.get("Type") or signal.get("Type_Localised"))
            count = int(signal.get("Count") or 0)
            if not material or count <= 0:
                continue
            self.hotspots[(system, body, material)] = {
                "system": system,
                "body": body,
                "material": material,
                "count": count,
                "ring_type": meta.get("ring_type", "-"),
                "distance": meta.get("distance"),
            }
            self.data_store.upsert_hotspot(
                {
                    "system_name": system,
                    "body_name": body,
                    "material_name": material,
                    "hotspot_count": count,
                    "ring_type": meta.get("ring_type"),
                    "ls_distance": meta.get("distance"),
                    "data_source": "Journal",
                    "scan_date": raw.get("timestamp"),
                }
            )

    def _process_prospector(self, raw):
        materials = []
        material_values = {}
        for item in raw.get("Materials", []) or []:
            name = _clean_name(item.get("Name_Localised") or item.get("Name"))
            if not name:
                continue
            try:
                pct = float(item.get("Proportion") or item.get("Percent") or 0)
            except Exception:
                pct = 0.0
            if pct <= 1 and item.get("Proportion") is not None:
                pct *= 100.0
            materials.append(f"{name} {_fmt_pct(pct)}")
            material_values[name] = pct

        core = _clean_name(raw.get("MotherlodeMaterial_Localised") or raw.get("MotherlodeMaterial"))
        remaining = raw.get("Remaining")
        content = raw.get("Content_Localised") or raw.get("Content") or "-"
        if isinstance(content, str) and content.startswith("$"):
            content = _clean_name(content)

        if not self.session_active:
            # Auto-start a session on the first prospector limpet fired
            self.start_session()

        if self.session_active:
            self.prospected_count += 1
            if core:
                self.core_count += 1
            for name, pct in material_values.items():
                stats = self.material_stats.setdefault(name, [])
                stats.append(float(pct))
            self._save_current_session_progress()

        remaining_text = _fmt_pct(remaining) if remaining is not None else "-"
        materials_text = ", ".join(materials) if materials else "-"
        core_text = core or "-"
        self.latest_prospector = f"{_event_time(raw)} | Remaining {remaining_text} | {materials_text}"
        if core:
            self.latest_prospector += f" | Core: {core}"

        self.prospector_tree.insert(
            "",
            0,
            values=(_event_time(raw), content, remaining_text, materials_text, core_text),
        )
        self._trim_tree(self.prospector_tree, 200)

        if self.session_active and materials:
            self.notebook.select(1)

    def _process_refined(self, raw):
        name = _clean_name(raw.get("Type_Localised") or raw.get("Type"))
        if self.session_active and name:
            self.mined_tons[name] = self.mined_tons.get(name, 0) + 1
            self._save_current_session_progress()

    def _apply_cargo_event(self, raw):
        inventory = raw.get("Inventory")
        if isinstance(inventory, list):
            self.cargo_inventory = inventory
        if raw.get("Count") is not None and raw.get("Type"):
            name = _clean_name(raw.get("Type_Localised") or raw.get("Type"))
            count = int(raw.get("Count") or 0)
            self.cargo_inventory = [{"Name_Localised": name, "Count": count}]

    def _process_mission_accepted(self, raw):
        mission_id = raw.get("MissionID")
        if not mission_id:
            return
        commodity = _clean_name(raw.get("Commodity_Localised") or raw.get("Commodity"))
        mission_name = str(raw.get("Name") or "")
        if commodity and ("mining" in mission_name.lower() or commodity in MINING_MATERIALS):
            amount = int(raw.get("Count") or raw.get("Amount") or 0)
            self.missions[mission_id] = {
                "id": mission_id,
                "commodity": commodity,
                "required": amount,
                "delivered": 0,
                "destination": raw.get("DestinationStation") or raw.get("DestinationSystem") or "-",
                "expires": raw.get("Expiry") or "-",
            }

    def _process_cargo_depot(self, raw):
        mission_id = raw.get("MissionID")
        mission = self.missions.get(mission_id)
        if not mission:
            return
        delivered = raw.get("Delivered")
        if delivered is None:
            delivered = raw.get("ItemsDelivered")
        try:
            mission["delivered"] = int(delivered or mission.get("delivered", 0))
        except Exception:
            pass

    def _refresh_all(self):
        self._refresh_metrics()
        self._refresh_materials()
        self._refresh_mined()
        self._refresh_cargo()
        self._refresh_hotspots()
        self._refresh_missions()

    def _refresh_metrics(self):
        elapsed = "IDLE"
        if self.session_active and self.session_started_at:
            seconds = int(time.time() - self.session_started_at)
            elapsed = f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
        self.session_label.config(text=f"SESSION: {elapsed}")
        self.system_metric.config(text=str(self.current_system or "---").upper())

        cargo_total = self._cargo_total()
        capacity = self.cargo_capacity or int(self.get_cargo_capacity() or 0)
        self.cargo_metric.config(text=f"{cargo_total}/{capacity} t" if capacity else f"{cargo_total} t")
        self.prospected_metric.config(text=f"{self.prospected_count} ({self.core_count} core)")
        self.mined_metric.config(text=f"{sum(self.mined_tons.values())} t")
        self.latest_label.config(text=self.latest_prospector)

    def _refresh_materials(self):
        self._clear_tree(self.material_tree)
        for name, values in sorted(self.material_stats.items()):
            if not values:
                continue
            avg = sum(values) / len(values)
            self.material_tree.insert("", tk.END, values=(name, len(values), _fmt_pct(avg), _fmt_pct(max(values)), _fmt_pct(values[-1])))

    def _refresh_mined(self):
        self._clear_tree(self.mined_tree)
        for name, tons in sorted(self.mined_tons.items()):
            self.mined_tree.insert("", tk.END, values=(name, tons))

    def _refresh_cargo(self):
        self._clear_tree(self.cargo_tree)
        for item in sorted(self.cargo_inventory, key=lambda i: _clean_name(i.get("Name_Localised") or i.get("Name"))):
            name = _clean_name(item.get("Name_Localised") or item.get("Name"))
            count = int(item.get("Count") or 0)
            mining = "YES" if name in MINING_MATERIALS else ""
            self.cargo_tree.insert("", tk.END, values=(name or "-", count, mining))

    def _refresh_hotspots(self):
        self._clear_tree(self.hotspot_tree)
        rows = self.search_results or [
            {
                "system_name": h["system"],
                "body_name": h["body"],
                "material_name": h["material"],
                "hotspot_count": h["count"],
                "ring_type": h.get("ring_type"),
                "ls_distance": h.get("distance"),
                "distance_ly": None,
                "overlap_tag": None,
                "res_tag": None,
                "data_source": "Journal",
            }
            for h in sorted(self.hotspots.values(), key=lambda x: (x["system"], x["body"], x["material"]))
        ]
        for item in rows:
            distance = item.get("distance_ly")
            try:
                distance = f"{float(distance):.1f}"
            except Exception:
                distance = "-"
            ls_distance = item.get("ls_distance")
            try:
                ls_distance = f"{float(ls_distance):.0f}"
            except Exception:
                ls_distance = "-"
            self.hotspot_tree.insert(
                "",
                tk.END,
                values=(
                    item.get("system_name") or item.get("system") or "-",
                    item.get("body_name") or item.get("body") or "-",
                    item.get("material_name") or item.get("material") or "-",
                    item.get("hotspot_count") or item.get("count") or 0,
                    item.get("ring_type") or "-",
                    distance,
                    ls_distance,
                    item.get("overlap_tag") or item.get("overlap") or "",
                    item.get("res_tag") or item.get("res") or "",
                ),
            )

    def _refresh_missions(self):
        self._clear_tree(self.mission_tree)
        for mission in sorted(self.missions.values(), key=lambda m: str(m.get("expires", ""))):
            required = int(mission.get("required") or 0)
            delivered = int(mission.get("delivered") or 0)
            progress = f"{delivered}/{required}" if required else str(delivered)
            self.mission_tree.insert(
                "",
                tk.END,
                values=(mission.get("id"), mission.get("commodity"), progress, mission.get("destination"), mission.get("expires")),
            )

    def _refresh_bookmarks(self):
        if not hasattr(self, "bookmark_tree"):
            return
        self._clear_tree(self.bookmark_tree)
        for item in self.data_store.list_bookmarks():
            self.bookmark_tree.insert(
                "",
                tk.END,
                values=(
                    item.get("system_name") or "-",
                    item.get("body_name") or "-",
                    item.get("material_name") or "",
                    item.get("created_at") or "",
                ),
            )

    def _refresh_sessions(self):
        if not hasattr(self, "session_tree"):
            return
        self._clear_tree(self.session_tree)
        for i, session in enumerate(self._json_sessions):
            tons = sum(session.get("mined_tons", {}).values()) if isinstance(session.get("mined_tons"), dict) else (session.get("mined_tons") or 0)
            status = "▶ IN PROGRESS" if session.get("in_progress") else (session.get("ended_at") or "")
            cargo_str = ", ".join(f"{v}t {k}" for k, v in sorted(session.get("mined_tons", {}).items()) if v) if isinstance(session.get("mined_tons"), dict) else ""
            self.session_tree.insert(
                "",
                tk.END,
                iid=str(i),
                values=(
                    session.get("started_at") or "",
                    session.get("system_name") or "",
                    session.get("prospected_count") or 0,
                    f"{tons} t",
                    cargo_str or "-",
                    status,
                ),
            )

    def search_hotspots(self):
        if self.search_running:
            return
        self.search_running = True
        self.hotspot_status_label.config(text="Searching hotspots...")
        material = self.hotspot_material_var.get()
        ring_type = self.hotspot_ring_var.get()
        source = self.hotspot_source_var.get()
        try:
            max_distance = float(self.hotspot_range_var.get())
        except Exception:
            max_distance = None
        try:
            reference_coords = self.get_current_coords()
        except Exception:
            reference_coords = None

        def worker():
            results = []
            errors = []
            try:
                if source in ("Local", "Both"):
                    results.extend(
                        self.data_store.search_hotspots(
                            material=material,
                            ring_type=ring_type,
                            reference_coords=reference_coords,
                            max_distance=max_distance if reference_coords else None,
                        )
                    )
                if source in ("Spansh", "Both"):
                    try:
                        results.extend(
                            search_spansh_rings(
                                self.current_system if self.current_system != "---" else None,
                                material=material,
                                ring_type=ring_type,
                                max_results=150,
                            )
                        )
                    except Exception as exc:
                        errors.append(f"Spansh: {exc}")
            finally:
                self.root.after(0, lambda: self._finish_hotspot_search(results, errors))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_hotspot_search(self, results, errors):
        self.search_running = False
        self.search_results = results
        self._refresh_hotspots()
        suffix = f" ({'; '.join(errors)})" if errors else ""
        self.hotspot_status_label.config(text=f"Found {len(results)} hotspot/ring rows.{suffix}")

    def bookmark_selected_hotspot(self):
        selection = self.hotspot_tree.selection()
        if not selection:
            return
        values = self.hotspot_tree.item(selection[0], "values")
        if len(values) < 3:
            return
        system, body, material = values[0], values[1], values[2]
        self.data_store.add_bookmark(system, body, material)
        self._refresh_bookmarks()
        self.hotspot_status_label.config(text=f"Bookmarked {system} / {body} / {material}.")

    def import_elitemining_db(self):
        path = filedialog.askopenfilename(
            parent=self.win,
            title="Import EliteMining user_data.db",
            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            count = self.data_store.import_elitemining_user_db(path)
            self.hotspot_status_label.config(text=f"Imported {count} EliteMining hotspot rows into {self.data_store.db_path}.")
            messagebox.showinfo("Import Complete", f"Imported {count} hotspot rows.")
        except Exception as exc:
            messagebox.showerror("Import Failed", str(exc))

    def _finish_current_session(self):
        if not self.session_id:
            return
        summary = self._current_session_summary()
        summary["ended_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        self.data_store.finish_session(self.session_id, summary)
        self._update_json_session(ended_at=summary["ended_at"], in_progress=False)
        self.session_id = None
        self.session_started_at = None
        self._json_session_key = None
        self._refresh_sessions()

    def _current_session_summary(self):
        return {
            "ended_at": None,
            "system_name": self.current_system,
            "body_name": self.current_body,
            "prospected_count": self.prospected_count,
            "core_count": self.core_count,
            "mined_tons": sum(self.mined_tons.values()),
            "cargo_json": json.dumps(self.mined_tons, sort_keys=True),
            "material_json": json.dumps(self.material_stats, sort_keys=True),
            "report_path": None,
        }

    def _update_json_session(self, ended_at=None, in_progress=True):
        """Keep the in-memory JSON list in sync and flush to disk."""
        if not self._json_session_key:
            return
        for rec in self._json_sessions:
            if rec.get("started_at") == self._json_session_key:
                rec["system_name"] = self.current_system
                rec["body_name"] = self.current_body
                rec["prospected_count"] = self.prospected_count
                rec["core_count"] = self.core_count
                rec["mined_tons"] = dict(self.mined_tons)
                # Summarise material stats: store avg/best/count per material
                mat_summary = {}
                for name, values in self.material_stats.items():
                    if values:
                        mat_summary[name] = {
                            "hits": len(values),
                            "avg": round(sum(values) / len(values), 1),
                            "best": round(max(values), 1),
                        }
                rec["material_stats"] = mat_summary
                rec["in_progress"] = in_progress
                if ended_at:
                    rec["ended_at"] = ended_at
                break
        save_mining_sessions_json(self._json_sessions, self.mining_sessions_file)

    def _save_current_session_progress(self):
        if not self.session_active or not self.session_id:
            return
        self.data_store.update_session(self.session_id, self._current_session_summary())
        self._update_json_session(in_progress=True)
        self._refresh_sessions()

    def generate_selected_report(self):
        selection = self.session_tree.selection()
        if not selection:
            return
        iid = selection[0]
        try:
            idx = int(iid)
            session = self._json_sessions[idx]
        except (ValueError, IndexError):
            return
        # Convert JSON session to the format _write_session_report expects
        mined_tons = session.get("mined_tons") or {}
        if not isinstance(mined_tons, dict):
            mined_tons = {}
        mat_stats = session.get("material_stats") or {}
        # Re-expand summarised stats into lists for the HTML writer
        material_json_expanded = {k: [v.get("best", 0)] * v.get("hits", 1) for k, v in mat_stats.items()} if mat_stats else {}
        report_session = {
            "id": session.get("started_at", ""),
            "started_at": session.get("started_at", ""),
            "ended_at": session.get("ended_at", ""),
            "system_name": session.get("system_name", ""),
            "body_name": session.get("body_name", ""),
            "prospected_count": session.get("prospected_count", 0),
            "core_count": session.get("core_count", 0),
            "mined_tons": sum(mined_tons.values()),
            "cargo_json": json.dumps(mined_tons),
            "material_json": json.dumps(material_json_expanded),
        }
        path = self._write_session_report(report_session)
        self._refresh_sessions()
        messagebox.showinfo("Report Generated", path)

    def _write_session_report(self, session):
        reports_dir = os.path.abspath(os.path.join("Reports", "Mining"))
        os.makedirs(reports_dir, exist_ok=True)
        filename = f"mining_session_{session.get('id')}.html"
        path = os.path.join(reports_dir, filename)
        try:
            cargo = json.loads(session.get("cargo_json") or "{}")
        except Exception:
            cargo = {}
        try:
            materials = json.loads(session.get("material_json") or "{}")
        except Exception:
            materials = {}
        max_cargo = max([int(v) for v in cargo.values()] or [1])
        cargo_rows = "\n".join(
            f"<tr><td>{name}</td><td>{tons}</td><td><div class=\"bar\"><span style=\"width:{(int(tons) / max_cargo) * 100:.1f}%\"></span></div></td></tr>"
            for name, tons in sorted(cargo.items())
        )
        material_rows = []
        for name, values in sorted(materials.items()):
            if not values:
                continue
            avg = sum(float(v) for v in values) / len(values)
            best = max(values)
            material_rows.append(
                f"<tr><td>{name}</td><td>{len(values)}</td><td>{avg:.1f}%</td><td>{best:.1f}%</td>"
                f"<td><div class=\"bar\"><span style=\"width:{min(float(best), 100.0):.1f}%\"></span></div></td></tr>"
            )
        html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Void Compass Mining Session {session.get('id')}</title>
  <style>
    body {{ background:#080a0d; color:#e0e0e0; font-family:Segoe UI, Arial, sans-serif; margin:32px; }}
    h1, h2 {{ color:#00d1ff; }}
    table {{ border-collapse:collapse; width:100%; margin:12px 0 28px; }}
    th, td {{ border:1px solid #26313a; padding:8px 10px; text-align:left; }}
    th {{ background:#121920; color:#ff7100; }}
    .metric {{ display:inline-block; background:#11161c; border:1px solid #26313a; padding:12px 16px; margin:0 10px 10px 0; }}
    .bar {{ width:100%; height:10px; background:#10161c; border:1px solid #26313a; }}
    .bar span {{ display:block; height:10px; background:#00d1ff; }}
  </style>
</head>
<body>
  <h1>Mining Session {session.get('id')}</h1>
  <div class="metric">Started: {session.get('started_at') or ''}</div>
  <div class="metric">Ended: {session.get('ended_at') or ''}</div>
  <div class="metric">System: {session.get('system_name') or ''}</div>
  <div class="metric">Prospected: {session.get('prospected_count') or 0}</div>
  <div class="metric">Core: {session.get('core_count') or 0}</div>
  <div class="metric">Mined Tons: {session.get('mined_tons') or 0}</div>
  <h2>Cargo</h2>
  <table><tr><th>Commodity</th><th>Tons</th><th>Chart</th></tr>{cargo_rows}</table>
  <h2>Prospector Materials</h2>
  <table><tr><th>Material</th><th>Hits</th><th>Average</th><th>Best</th><th>Chart</th></tr>{''.join(material_rows)}</table>
</body>
</html>
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return path

    def _cargo_total(self):
        if self.cargo_inventory:
            return sum(int(item.get("Count") or 0) for item in self.cargo_inventory)
        return int(self.last_status_cargo or 0)

    @staticmethod
    def _clear_tree(tree):
        children = tree.get_children()
        if children:
            tree.delete(*children)

    @staticmethod
    def _trim_tree(tree, max_items):
        children = tree.get_children()
        if len(children) > max_items:
            tree.delete(*children[max_items:])

    def _tick(self):
        if not self.is_open():
            return
        self._refresh_metrics()
        self.win.after(1000, self._tick)
