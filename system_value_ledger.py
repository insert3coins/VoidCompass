import json
import tkinter as tk
from tkinter import ttk

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config
from ui_theme import THEME, ThemedWindowMixin, apply_window, configure_ttk, window_surface

COLOR_ACCENT = THEME.accent
COLOR_ORANGE = THEME.orange
COLOR_TEXT = THEME.text


class SystemValueLedger(ThemedWindowMixin):

    def __init__(self, root, app, embedded=False):
        self.root = root
        self.app = app
        self.config = app.config
        self.rows = []
        self.embedded = embedded
        self.win = window_surface(root, embedded=embedded)
        self.win.title("System Value Ledger")
        self.win.geometry(self.config.get("value_ledger_geometry", "980x620"))
        apply_window(self.win)
        self.win.minsize(780, 460)
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
        tk.Label(header, text="SYSTEM VALUE LEDGER", font=("Segoe UI", 13, "bold"), fg=COLOR_ACCENT, bg="#0c1014").pack(side=tk.LEFT, padx=14)
        self.summary = tk.Label(header, text="", font=("Consolas", 8), fg=self.UI_MUTED, bg="#0c1014")
        self.summary.pack(side=tk.RIGHT, padx=14)

        controls = tk.Frame(self.win, bg=self.UI_BG)
        controls.pack(fill=tk.X, padx=10, pady=(10, 6))
        tk.Label(controls, text="Filter", fg=self.UI_MUTED, bg=self.UI_BG, font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._render())
        tk.Entry(controls, textvariable=self.filter_var, bg="#0b0f13", fg=COLOR_TEXT, insertbackground=COLOR_ACCENT, relief=tk.FLAT, width=34).pack(side=tk.LEFT, padx=(8, 10), ipady=4)
        self._button(controls, "Refresh", self.refresh).pack(side=tk.LEFT)
        self._button(controls, "Copy Summary", self._copy_summary, accent=True).pack(side=tk.LEFT, padx=(8, 0))

        style = configure_ttk(self.win, "Ledger")
        style.theme_use("default")
        style.configure("Ledger.Treeview", background="#0b0f13", foreground=COLOR_TEXT, fieldbackground="#0b0f13", rowheight=24, borderwidth=0)
        style.configure("Ledger.Treeview.Heading", background=self.UI_PANEL, foreground=COLOR_ORANGE, relief="flat", font=("Segoe UI", 8, "bold"))
        style.map("Ledger.Treeview", background=[("selected", "#12313c")], foreground=[("selected", COLOR_TEXT)])

        frame = tk.Frame(self.win, bg=self.UI_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        cols = ("system", "body", "class", "value", "mapped", "flags")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", style="Ledger.Treeview")
        widths = {"system": 190, "body": 230, "class": 180, "value": 95, "mapped": 75, "flags": 160}
        labels = {"system": "System", "body": "Body", "class": "Class", "value": "Est. Value", "mapped": "Mapped", "flags": "Flags"}
        for col in cols:
            self.tree.heading(col, text=labels[col], command=lambda c=col: self._sort(c))
            self.tree.column(col, width=widths[col], anchor=tk.W if col not in ("value", "mapped") else tk.E)
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _button(self, parent, text, cmd, accent=False):
        return tk.Button(parent, text=text, command=cmd, bg=COLOR_ACCENT if accent else self.UI_PANEL, fg="black" if accent else COLOR_TEXT, activebackground=COLOR_ACCENT if accent else "#1a2430", activeforeground="black" if accent else COLOR_ACCENT, relief=tk.FLAT, bd=0, padx=10, pady=5, font=("Segoe UI", 8, "bold"), cursor="hand2")

    def _valuable(self, item):
        planet = item.get("planet_class") or item.get("class") or ""
        return bool(item.get("terraformable") or planet in ("Earthlike body", "Water world", "Ammonia world") or int(item.get("dss_reward") or item.get("reward") or 0) >= 500000)

    def _flag_text(self, item):
        flags = []
        if item.get("terraformable"):
            flags.append("Terraformable")
        if item.get("was_discovered") is False:
            flags.append("First discovered")
        if item.get("first_footfall"):
            flags.append("First footfall")
        if item.get("landable"):
            flags.append("Landable")
        return ", ".join(flags)

    def refresh(self):
        rows = []
        try:
            with self.app.db_lock:
                cur = self.app.conn.execute("SELECT system_name, data_json FROM scan_hud_items")
                for system, payload in cur.fetchall():
                    try:
                        item = json.loads(payload)
                    except Exception:
                        continue
                    if not isinstance(item, dict) or item.get("is_star"):
                        continue
                    if not self._valuable(item):
                        continue
                    value = int(item.get("dss_reward") if item.get("dss_complete") else item.get("reward") or 0)
                    rows.append({
                        "system": system,
                        "body": item.get("full_name") or item.get("name") or "",
                        "class": item.get("planet_class") or item.get("class") or "",
                        "value": value,
                        "mapped": "Yes" if item.get("dss_complete") or item.get("was_mapped") else "No",
                        "flags": self._flag_text(item),
                    })
        except Exception:
            rows = []
        self.rows = sorted(rows, key=lambda row: row["value"], reverse=True)
        self._render()

    def _render(self):
        for item_id in self.tree.get_children():
            self.tree.delete(item_id)
        query = (self.filter_var.get() or "").strip().lower()
        shown = []
        for row in self.rows:
            haystack = " ".join(str(v) for v in row.values()).lower()
            if query and query not in haystack:
                continue
            shown.append(row)
            self.tree.insert("", tk.END, values=(row["system"], row["body"], row["class"], f"{row['value']:,}", row["mapped"], row["flags"]))
        total = sum(row["value"] for row in shown)
        self.summary.config(text=f"{len(shown)} bodies | {total:,} cr")

    def _sort(self, col):
        reverse = True if col == "value" else False
        self.rows.sort(key=lambda row: row[col], reverse=reverse)
        self._render()

    def _copy_summary(self):
        lines = ["System Value Ledger"]
        for row in self.rows[:40]:
            lines.append(f"{row['system']} | {row['body']} | {row['class']} | {row['value']:,} cr | {row['flags']}")
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))

    def _on_close(self):
        self.config["value_ledger_geometry"] = self.win.geometry()
        save_config(self.config)
        self.win.destroy()
