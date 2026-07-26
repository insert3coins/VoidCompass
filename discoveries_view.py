"""One filterable exploration ledger for systems, Codex, DSS and photos."""

from __future__ import annotations

from datetime import datetime
import os
import time
import tkinter as tk
from tkinter import ttk
from urllib.parse import quote_plus
import webbrowser

from ui_theme import THEME, button, configure_ttk, scrollbar

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


FILTERS = ("All", "Systems", "Valuable", "Codex", "Signals", "DSS", "Photos")


class DiscoveriesView:
    def __init__(self, parent, app, initial_filter="All", on_filter_change=None):
        self.parent = parent
        self.app = app
        self.initial_filter = initial_filter if initial_filter in FILTERS else "All"
        self.on_filter_change = on_filter_change
        self.rows = {}
        self._all_rows = []
        self._photo_image = None
        self._preview_key = None
        self._resolved_paths = {}
        self._resolve_attempts = {}
        configure_ttk(parent, "Discoveries")
        self._build()

    def _build(self):
        toolbar = tk.Frame(self.parent, bg=THEME.panel)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            toolbar, text="DISCOVERY ARCHIVE", fg=THEME.orange,
            bg=THEME.panel, font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.LEFT, padx=10, pady=8)
        self.filter_var = tk.StringVar(value=self.initial_filter)
        combo = ttk.Combobox(
            toolbar, textvariable=self.filter_var, values=FILTERS,
            state="readonly", width=11, style="Discoveries.TCombobox",
        )
        combo.pack(side=tk.LEFT, padx=(6, 8), pady=5)
        combo.bind("<<ComboboxSelected>>", self._filter_changed)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_args: self._render())
        tk.Entry(
            toolbar, textvariable=self.search_var, bg=THEME.input,
            fg=THEME.text, insertbackground=THEME.accent, relief=tk.FLAT,
            width=30,
        ).pack(side=tk.LEFT, padx=(0, 8), pady=6, ipady=3)
        button(toolbar, "Copy Selected", self._copy_selected).pack(side=tk.RIGHT, padx=8, pady=5)
        self.summary = tk.Label(
            self.parent, text="", fg=THEME.accent, bg=THEME.bg,
            font=("Cascadia Mono", 9, "bold"), anchor="w",
        )
        self.summary.pack(fill=tk.X, padx=4, pady=(0, 7))

        split = tk.PanedWindow(
            self.parent, orient=tk.HORIZONTAL, bg=THEME.bg,
            bd=0, sashwidth=6, sashrelief=tk.FLAT,
        )
        split.pack(fill=tk.BOTH, expand=True)
        left = tk.Frame(split, bg=THEME.bg)
        right = tk.Frame(split, bg=THEME.panel)
        split.add(left, minsize=660)
        split.add(right, minsize=300)
        columns = ("time", "type", "system", "subject", "detail", "value")
        wrap = tk.Frame(left, bg=THEME.bg)
        wrap.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(
            wrap, columns=columns, show="headings", style="Discoveries.Treeview",
        )
        specs = {
            "time": ("Time", 125, tk.W), "type": ("Type", 75, tk.CENTER),
            "system": ("System", 210, tk.W), "subject": ("Record", 235, tk.W),
            "detail": ("Detail", 260, tk.W), "value": ("Value", 95, tk.E),
        }
        for key, (title, width, anchor) in specs.items():
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor=anchor)
        bar = scrollbar(wrap, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.tag_configure("Codex", foreground=THEME.green)
        self.tree.tag_configure("Photo", foreground=THEME.accent)
        self.tree.tag_configure("Valuable", foreground=THEME.orange)
        self.tree.bind("<<TreeviewSelect>>", self._selected)

        self.preview = tk.Label(
            right, text="Select a discovery record", fg=THEME.muted,
            bg=THEME.inset, anchor="center", justify=tk.CENTER,
        )
        self.preview.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.detail = tk.Text(
            right, bg=THEME.panel, fg=THEME.text,
            insertbackground=THEME.accent, relief=tk.FLAT, bd=0,
            padx=8, pady=6, height=12, font=("Cascadia Mono", 8), wrap=tk.WORD,
        )
        self.detail.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.detail.configure(state=tk.DISABLED)
        system_actions = tk.Frame(right, bg=THEME.panel)
        system_actions.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.copy_system_btn = button(system_actions, "Copy System", self._copy_system, accent=True)
        self.copy_system_btn.pack(side=tk.LEFT)
        self.open_edsm_btn = button(system_actions, "Open EDSM", self._open_edsm)
        self.open_edsm_btn.pack(side=tk.LEFT, padx=(7, 0))
        media_actions = tk.Frame(right, bg=THEME.panel)
        media_actions.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.open_image_btn = button(media_actions, "Open Image", self._open_image)
        self.open_image_btn.pack(side=tk.LEFT)
        self.open_folder_btn = button(media_actions, "Open Folder", self._open_folder)
        self.open_folder_btn.pack(side=tk.LEFT, padx=(7, 0))

    def _filter_changed(self, _event=None):
        self._render()
        if callable(self.on_filter_change):
            try:
                self.on_filter_change(self.filter_var.get())
            except Exception:
                pass

    def set_filter(self, value, notify=True):
        selected = value if value in FILTERS else "All"
        self.filter_var.set(selected)
        self._render()
        if notify and callable(self.on_filter_change):
            try:
                self.on_filter_change(selected)
            except Exception:
                pass

    @staticmethod
    def _display_time(value):
        if isinstance(value, (int, float)):
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(value))
        return str(value or "").replace("T", " ")[:19]

    @staticmethod
    def _epoch(value):
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0

    def refresh(self, system_rows=None, value_rows=None):
        tracker = getattr(self.app, "deep_survey", None)
        snapshot = tracker.snapshot() if tracker else {}
        rows = []
        for row in snapshot.get("codex") or []:
            detail = " · ".join(filter(None, (
                row.get("category"), row.get("region"), "NEW" if row.get("new") else "",
            )))
            rows.append(self._row("Codex", row.get("timestamp"), row.get("system"),
                                  row.get("name"), detail, row.get("voucher"), row))
        for row in snapshot.get("signals") or []:
            bits = [row.get("type") or "Signal"]
            if row.get("threat"):
                bits.append(f"Threat {row['threat']}")
            if row.get("time_remaining"):
                bits.append(f"{float(row['time_remaining']) / 60:.0f} min at discovery")
            rows.append(self._row("Signal", row.get("timestamp"), row.get("system"),
                                  row.get("name"), " · ".join(bits), 0, row))
        for row in snapshot.get("dss") or []:
            result = (
                "Efficient" if row.get("efficient") else
                "Over target" if row.get("target") else "No target reported"
            )
            detail = f"{row.get('probes') or '-'} probes / target {row.get('target') or '-'} · {result}"
            rows.append(self._row("DSS", row.get("timestamp"), row.get("system"),
                                  row.get("body") or f"Body {row.get('body_id', '-')}", detail, 0, row))
        for row in snapshot.get("screenshots") or []:
            body = row.get("body") or "Screenshot"
            coords = ""
            if row.get("latitude") is not None and row.get("longitude") is not None:
                coords = f"{float(row['latitude']):.4f}, {float(row['longitude']):.4f}"
            rows.append(self._row("Photo", row.get("timestamp"), row.get("system"),
                                  body, coords or "Orbital / coordinates unavailable", 0, row))
        for row in system_rows or []:
            detail = (
                f"{int(row.get('scanned_bodies') or 0)}/{int(row.get('total_bodies') or 0)} bodies · "
                f"Bio {int(row.get('bio_signals') or 0)} · {int(row.get('valuable_bodies') or 0)} valuable"
            )
            rows.append(self._row("System", row.get("last_seen_ts"), row.get("system"),
                                  row.get("star_class") or "System survey", detail,
                                  row.get("estimated_value"), row))
        for row in value_rows or []:
            rows.append(self._row("Valuable", row.get("last_seen_ts") or 0, row.get("system"),
                                  row.get("body"), f"{row.get('class') or '-'} · {row.get('flags') or ''}",
                                  row.get("value"), row))
        self._all_rows = sorted(rows, key=lambda item: item["sort"], reverse=True)
        self._render()

    def _row(self, kind, timestamp, system, subject, detail, value, raw):
        return {
            "kind": kind, "timestamp": timestamp, "sort": self._epoch(timestamp),
            "system": system or "-", "subject": subject or "-", "detail": detail or "-",
            "value": int(value or 0), "raw": raw,
        }

    def _render(self):
        selected_key = None
        selected = self.tree.selection()
        if selected:
            old = self.rows.get(selected[0])
            selected_key = (old.get("kind"), old.get("timestamp"), old.get("subject")) if old else None
        children = self.tree.get_children()
        if children:
            self.tree.delete(*children)
        self.rows = {}
        selected_filter = self.filter_var.get()
        filter_kind = {
            "Systems": "System", "Valuable": "Valuable", "Codex": "Codex",
            "Signals": "Signal", "DSS": "DSS", "Photos": "Photo",
        }.get(selected_filter)
        query = self.search_var.get().strip().casefold()
        shown = []
        chosen = None
        for row in self._all_rows:
            if filter_kind and row["kind"] != filter_kind:
                continue
            haystack = " ".join(str(row[key]) for key in ("kind", "system", "subject", "detail")).casefold()
            if query and query not in haystack:
                continue
            shown.append(row)
            value = f"{row['value']:,}" if row["value"] else "-"
            iid = self.tree.insert("", tk.END, values=(
                self._display_time(row["timestamp"]), row["kind"].upper(), row["system"],
                row["subject"], row["detail"], value,
            ), tags=(row["kind"],))
            self.rows[iid] = row
            key = (row["kind"], row["timestamp"], row["subject"])
            if selected_key == key:
                chosen = iid
        total_value = sum(row["value"] for row in shown)
        self.summary.config(text=f"{len(shown):,} records · {total_value:,} cr represented · {selected_filter}")
        children = self.tree.get_children()
        if chosen or children:
            iid = chosen or children[0]
            self.tree.selection_set(iid)
            self._show(self.rows.get(iid))
        else:
            self._show(None)

    def _selected(self, _event=None):
        selected = self.tree.selection()
        self._show(self.rows.get(selected[0]) if selected else None)

    def _set_detail(self, text):
        self.detail.configure(state=tk.NORMAL)
        self.detail.delete("1.0", tk.END)
        self.detail.insert(tk.END, text)
        self.detail.configure(state=tk.DISABLED)

    def _show(self, row):
        if not row:
            self._set_detail("No discovery records match the current filter.")
            self.preview.config(image="", text="No record selected")
            self.open_image_btn.config(state=tk.DISABLED)
            self.open_folder_btn.config(state=tk.DISABLED)
            self.copy_system_btn.config(state=tk.DISABLED)
            self.open_edsm_btn.config(state=tk.DISABLED)
            return
        raw = row.get("raw") or {}
        lines = [
            f"{row['kind'].upper()} · {row['subject']}",
            f"System: {row['system']}", f"Time: {self._display_time(row['timestamp'])}",
            f"Detail: {row['detail']}",
        ]
        if row["value"]:
            lines.append(f"Value: {row['value']:,} cr")
        for label, key in (("Body", "body"), ("Region", "region"),
                           ("Latitude", "latitude"), ("Longitude", "longitude"),
                           ("Altitude", "altitude"), ("Heading", "heading")):
            if raw.get(key) not in (None, ""):
                lines.append(f"{label}: {raw[key]}")
        self._set_detail("\n".join(lines))
        has_system = bool(row.get("system") and row.get("system") != "-")
        self.copy_system_btn.config(state=tk.NORMAL if has_system else tk.DISABLED)
        self.open_edsm_btn.config(state=tk.NORMAL if has_system else tk.DISABLED)
        is_photo = row["kind"] == "Photo"
        self.open_image_btn.config(state=tk.NORMAL if is_photo else tk.DISABLED)
        self.open_folder_btn.config(state=tk.NORMAL if is_photo else tk.DISABLED)
        if not is_photo:
            self._photo_image = None
            self._preview_key = None
            self.preview.config(image="", text=row["kind"].upper())
            return
        path = self._resolve_screenshot(raw)
        preview_key = (raw.get("filename"), path)
        if preview_key == self._preview_key:
            return
        self._preview_key = preview_key
        self._photo_image = None
        if path and Image and ImageTk:
            try:
                with Image.open(path) as source:
                    preview = source.copy()
                preview.thumbnail((480, 360))
                self._photo_image = ImageTk.PhotoImage(preview)
            except Exception:
                self._photo_image = None
        self.preview.config(
            image=self._photo_image or "",
            text="" if self._photo_image else "Image preview unavailable\nMetadata remains available",
        )

    def _resolve_screenshot(self, row):
        key = str(row.get("filename") or "")
        cached = self._resolved_paths.get(key)
        if cached and os.path.exists(cached):
            return cached
        if key and os.path.exists(key):
            self._resolved_paths[key] = key
            return key
        folder = self.app.config.get("screenshots_path")
        if not folder or not os.path.isdir(folder):
            return None
        now = time.monotonic()
        if now - float(self._resolve_attempts.get(key, 0.0)) < 5.0:
            return None
        self._resolve_attempts[key] = now
        system = "".join(
            character for character in str(row.get("system") or "")
            if character.isalnum() or character in " -_()"
        ).strip().casefold()
        candidates = []
        try:
            for name in os.listdir(folder):
                if not name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                    continue
                if system and system not in name.casefold():
                    continue
                path = os.path.join(folder, name)
                candidates.append((abs(os.path.getmtime(path) - self._epoch(row.get("timestamp"))), path))
        except OSError:
            return None
        path = min(candidates)[1] if candidates else None
        if path:
            self._resolved_paths[key] = path
        return path

    def _selected_path(self):
        selected = self.tree.selection()
        row = self.rows.get(selected[0]) if selected else None
        return self._resolve_screenshot(row.get("raw") or {}) if row and row.get("kind") == "Photo" else None

    def _selected_row(self):
        selected = self.tree.selection()
        return self.rows.get(selected[0]) if selected else None

    def _copy_system(self):
        row = self._selected_row()
        system = row.get("system") if row else None
        if not system or system == "-":
            return
        root = getattr(self.app, "root", self.parent)
        root.clipboard_clear()
        root.clipboard_append(system)

    def _open_edsm(self):
        row = self._selected_row()
        system = row.get("system") if row else None
        if system and system != "-":
            webbrowser.open(f"https://www.edsm.net/show-system?systemName={quote_plus(system)}")

    def _open_image(self):
        path = self._selected_path()
        if path:
            os.startfile(path)

    def _open_folder(self):
        path = self._selected_path()
        folder = os.path.dirname(path) if path else self.app.config.get("screenshots_path")
        if folder and os.path.isdir(folder):
            os.startfile(folder)

    def _copy_selected(self):
        selected = self.tree.selection()
        row = self.rows.get(selected[0]) if selected else None
        if not row:
            return
        text = (
            f"{row['kind']} | {self._display_time(row['timestamp'])} | "
            f"{row['system']} | {row['subject']} | {row['detail']}"
        )
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(text)
