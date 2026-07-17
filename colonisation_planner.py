import tkinter as tk
from tkinter import ttk

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config
from ui_theme import THEME, ThemedWindowMixin, apply_window, button, configure_ttk, scrollbar, window_surface

COLOR_ACCENT = THEME.accent
COLOR_ORANGE = THEME.orange
COLOR_TEXT = THEME.text


class ColonisationPlanner(ThemedWindowMixin):

    def __init__(self, root, app, embedded=False):
        self.root = root
        self.app = app
        self.config = app.config
        self.rows = []
        self.embedded = embedded
        self.win = window_surface(root, embedded=embedded)
        self.win.title("Colonisation Planner")
        self.win.geometry(self.config.get("colonisation_planner_geometry", "900x560"))
        apply_window(self.win)
        self.win.minsize(720, 420)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()
        self.refresh()

    def is_open(self):
        try:
            return bool(self.win and self.win.winfo_exists())
        except Exception:
            return False

    def lift(self):
        self.win.lift()
        self.win.focus_force()

    def _build(self):
        header = tk.Frame(self.win, bg="#0c1014", height=48)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="COLONISATION PROJECT PLANNER", font=("Segoe UI", 13, "bold"), fg=COLOR_ACCENT, bg="#0c1014").pack(side=tk.LEFT, padx=14)
        self.summary = tk.Label(header, text="", font=("Consolas", 8), fg=self.UI_MUTED, bg="#0c1014")
        self.summary.pack(side=tk.RIGHT, padx=14)

        controls = tk.Frame(self.win, bg=self.UI_BG)
        controls.pack(fill=tk.X, padx=10, pady=(10, 6))
        self._button(controls, "Refresh", self.refresh).pack(side=tk.LEFT)
        self._button(controls, "Copy Shopping List", self._copy, accent=True).pack(side=tk.LEFT, padx=(8, 0))

        style = configure_ttk(self.win, "Planner")
        style.configure("Planner.Treeview", background="#0b0f13", foreground=COLOR_TEXT, fieldbackground="#0b0f13", rowheight=24, borderwidth=0)
        style.configure("Planner.Treeview.Heading", background=self.UI_PANEL, foreground=COLOR_ORANGE, relief="flat", font=("Segoe UI", 8, "bold"))
        style.map("Planner.Treeview", background=[("selected", "#12313c")], foreground=[("selected", COLOR_TEXT)])

        frame = tk.Frame(self.win, bg=self.UI_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        cols = ("commodity", "remaining", "required", "delivered", "projects")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", style="Planner.Treeview")
        for col, label, width, anchor in (
            ("commodity", "Commodity", 240, tk.W),
            ("remaining", "Remaining", 110, tk.E),
            ("required", "Required", 110, tk.E),
            ("delivered", "Delivered", 110, tk.E),
            ("projects", "Projects", 300, tk.W),
        ):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor=anchor)
        scroll = scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _button(self, parent, text, cmd, accent=False):
        return button(parent, text, cmd, accent=accent)

    def refresh(self):
        totals = {}
        active_projects = 0
        for project in self.app.colonisation_projects.values():
            if project.get("complete") or project.get("failed"):
                continue
            active_projects += 1
            project_name = project.get("system_name") or project.get("body_name") or "Unknown"
            for res in project.get("resources") or []:
                name = res.get("display") or res.get("name") or "Unknown"
                required = int(res.get("required") or 0)
                delivered = min(int(res.get("provided") or 0), required)
                remaining = max(0, required - delivered)
                if remaining <= 0:
                    continue
                entry = totals.setdefault(name, {"commodity": name, "remaining": 0, "required": 0, "delivered": 0, "projects": set()})
                entry["remaining"] += remaining
                entry["required"] += required
                entry["delivered"] += delivered
                entry["projects"].add(project_name)
        self.rows = sorted(totals.values(), key=lambda row: (-row["remaining"], row["commodity"].lower()))
        for item_id in self.tree.get_children():
            self.tree.delete(item_id)
        for row in self.rows:
            self.tree.insert("", tk.END, values=(row["commodity"], f"{row['remaining']:,}", f"{row['required']:,}", f"{row['delivered']:,}", ", ".join(sorted(row["projects"])[:4])))
        self.summary.config(text=f"{active_projects} active projects | {sum(r['remaining'] for r in self.rows):,} tons remaining")

    def _copy(self):
        lines = ["Colonisation shopping list"]
        for row in self.rows:
            lines.append(f"{row['commodity']}: {row['remaining']:,}")
        if len(lines) == 1:
            lines.append("(nothing remaining)")
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))

    def _on_close(self):
        self.config["colonisation_planner_geometry"] = self.win.geometry()
        save_config(self.config)
        self.win.destroy()
