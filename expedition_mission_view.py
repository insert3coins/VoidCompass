"""Single-page Expedition Mission Control workspace."""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from expedition_manager import OBJECTIVE_KINDS
from ui_theme import THEME, button, configure_ttk, scrollbar


PRIORITIES = ("Critical", "High", "Normal", "Low")


class ExpeditionMissionView:
    def __init__(self, parent, app, on_change=None, copy_report_callback=None):
        self.parent = parent
        self.app = app
        self.manager = app.expedition_manager
        self.on_change = on_change
        self.copy_report_callback = copy_report_callback
        self.expedition_rows = {}
        self.objective_rows = {}
        self.bookmark_rows = {}
        self.selected_expedition_id = None
        configure_ttk(parent, "Mission")
        self._build()
        # Mission Control may be restored while its parent notebook is still
        # hidden. Populate it now instead of waiting for a later tab-change
        # event to provide its first usable view.
        self.refresh()

    def on_shown(self):
        """Refresh saved expedition state whenever Mission Control is shown."""
        self.refresh(self.selected_expedition_id)

    def _build(self):
        toolbar = tk.Frame(self.parent, bg=THEME.panel)
        toolbar.pack(fill=tk.X, pady=(0, 7))
        tk.Label(
            toolbar, text="EXPEDITION MISSION CONTROL", fg=THEME.orange,
            bg=THEME.panel, font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.LEFT, padx=10, pady=8)
        button(toolbar, "NEW", self._new_expedition, accent=True).pack(side=tk.LEFT, padx=(4, 6), pady=5)
        self.status_btn = button(toolbar, "PAUSE / RESUME", self._toggle_status)
        self.status_btn.pack(side=tk.LEFT, padx=(0, 6), pady=5)
        button(toolbar, "COMPLETE", self._complete_expedition).pack(side=tk.LEFT, padx=(0, 6), pady=5)
        button(toolbar, "IMPORT JSON", self._import_json).pack(side=tk.RIGHT, padx=(0, 8), pady=5)
        button(toolbar, "EXPORT JSON", self._export_json).pack(side=tk.RIGHT, padx=(0, 6), pady=5)
        button(toolbar, "COPY WAYPOINTS", self._copy_waypoints).pack(side=tk.RIGHT, padx=(0, 6), pady=5)
        if callable(self.copy_report_callback):
            button(toolbar, "COPY REPORT", self._copy_report).pack(side=tk.RIGHT, padx=(0, 6), pady=5)

        self.summary = tk.Label(
            self.parent, text="", fg=THEME.accent, bg=THEME.inset,
            font=("Cascadia Mono", 9, "bold"), anchor="w", padx=10, pady=7,
            highlightbackground=THEME.border, highlightthickness=1,
        )
        self.summary.pack(fill=tk.X, pady=(0, 7))
        self.metrics = tk.Label(
            self.parent, text="", fg=THEME.muted, bg=THEME.bg,
            font=("Cascadia Mono", 8), anchor="w",
        )
        self.metrics.pack(fill=tk.X, padx=4, pady=(0, 6))

        split = tk.PanedWindow(
            self.parent, orient=tk.HORIZONTAL, bg=THEME.bg, bd=0,
            sashwidth=6, sashrelief=tk.FLAT,
        )
        split.pack(fill=tk.BOTH, expand=True)
        left = tk.Frame(split, bg=THEME.bg)
        right = tk.Frame(split, bg=THEME.bg)
        split.add(left, minsize=310)
        split.add(right, minsize=620)

        self._section_heading(left, "EXPEDITIONS")
        self.expedition_tree = self._tree(
            left, ("status", "name", "progress", "route"), {
                "status": ("State", 75, tk.CENTER), "name": ("Expedition", 180, tk.W),
                "progress": ("Goals", 65, tk.CENTER), "route": ("Route", 220, tk.W),
            }, height=14,
        )
        self.expedition_tree.bind("<<TreeviewSelect>>", self._expedition_selected)
        left_actions = tk.Frame(left, bg=THEME.bg)
        left_actions.pack(fill=tk.X, pady=(6, 0))
        button(left_actions, "ACTIVATE", self._activate_selected, accent=True).pack(side=tk.LEFT)
        button(left_actions, "DELETE", self._delete_expedition, danger=True).pack(side=tk.LEFT, padx=(6, 0))

        right_split = tk.PanedWindow(
            right, orient=tk.VERTICAL, bg=THEME.bg, bd=0,
            sashwidth=6, sashrelief=tk.FLAT,
        )
        right_split.pack(fill=tk.BOTH, expand=True)
        objectives = tk.Frame(right_split, bg=THEME.bg)
        bookmarks = tk.Frame(right_split, bg=THEME.bg)
        right_split.add(objectives, minsize=225)
        right_split.add(bookmarks, minsize=225)

        objective_head = tk.Frame(objectives, bg=THEME.panel)
        objective_head.pack(fill=tk.X, pady=(0, 5))
        self._section_heading(objective_head, "OBJECTIVES", packed=False).pack(side=tk.LEFT)
        button(objective_head, "ADD", self._add_objective, accent=True).pack(side=tk.RIGHT, padx=6, pady=5)
        button(objective_head, "TOGGLE", self._toggle_objective).pack(side=tk.RIGHT, pady=5)
        button(objective_head, "REMOVE", self._remove_objective).pack(side=tk.RIGHT, padx=6, pady=5)
        self.objective_tree = self._tree(
            objectives, ("status", "objective", "progress", "target", "mode"), {
                "status": ("State", 72, tk.CENTER), "objective": ("Objective", 280, tk.W),
                "progress": ("Progress", 78, tk.CENTER), "target": ("Context", 230, tk.W),
                "mode": ("Mode", 70, tk.CENTER),
            }, height=8,
        )
        self.objective_tree.tag_configure("complete", foreground=THEME.green)
        self.objective_tree.tag_configure("pending", foreground=THEME.orange)

        bookmark_head = tk.Frame(bookmarks, bg=THEME.panel)
        bookmark_head.pack(fill=tk.X, pady=(0, 5))
        self._section_heading(bookmark_head, "BOOKMARKS & REVISIT TARGETS", packed=False).pack(side=tk.LEFT)
        button(bookmark_head, "ADD CURRENT", self._add_current_bookmark, accent=True).pack(side=tk.RIGHT, padx=6, pady=5)
        button(bookmark_head, "EDIT", self._edit_bookmark).pack(side=tk.RIGHT, pady=5)
        button(bookmark_head, "VISITED", self._toggle_bookmark).pack(side=tk.RIGHT, padx=6, pady=5)
        button(bookmark_head, "REMOVE", self._remove_bookmark).pack(side=tk.RIGHT, pady=5)
        self.bookmark_tree = self._tree(
            bookmarks, ("priority", "type", "title", "location", "tags", "status"), {
                "priority": ("Priority", 70, tk.CENTER), "type": ("Type", 80, tk.CENTER),
                "title": ("Bookmark", 210, tk.W), "location": ("Location", 240, tk.W),
                "tags": ("Tags", 150, tk.W), "status": ("State", 75, tk.CENTER),
            }, height=8,
        )
        self.bookmark_tree.tag_configure("Critical", foreground=THEME.red)
        self.bookmark_tree.tag_configure("High", foreground=THEME.orange)
        self.bookmark_tree.tag_configure("visited", foreground=THEME.green)

    @staticmethod
    def _section_heading(parent, text, packed=True):
        label = tk.Label(
            parent, text=text, fg=THEME.orange, bg=parent.cget("bg"),
            font=("Segoe UI", 8, "bold"), anchor="w", padx=8, pady=7,
        )
        if packed:
            label.pack(fill=tk.X)
        return label

    @staticmethod
    def _tree(parent, columns, specs, height=8):
        wrap = tk.Frame(parent, bg=THEME.bg)
        wrap.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(
            wrap, columns=columns, show="headings", height=height,
            style="Mission.Treeview",
        )
        for key in columns:
            title, width, anchor = specs[key]
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor=anchor)
        bar = scrollbar(wrap, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=bar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    def _changed(self):
        self.refresh(self.selected_expedition_id)
        if callable(self.on_change):
            self.on_change()

    def refresh(self, select_id=None):
        wanted = select_id or self.selected_expedition_id
        active = self.manager.active()
        if not wanted and active:
            wanted = active.get("id")
        for iid in self.expedition_tree.get_children():
            self.expedition_tree.delete(iid)
        self.expedition_rows = {}
        selected_iid = None
        for expedition in self.manager.expeditions():
            complete, total = self.manager.progress(expedition)
            route = " → ".join(filter(None, (
                expedition.get("start_system"), expedition.get("destination") or expedition.get("end_system"),
            ))) or "Route not set"
            iid = self.expedition_tree.insert("", tk.END, values=(
                str(expedition.get("status") or "-").upper(), expedition.get("name") or "Unnamed",
                f"{complete}/{total}", route,
            ), tags=(str(expedition.get("status") or ""),))
            self.expedition_rows[iid] = expedition
            if expedition.get("id") == wanted:
                selected_iid = iid
        children = self.expedition_tree.get_children()
        if selected_iid or children:
            selected_iid = selected_iid or children[0]
            self.expedition_tree.selection_set(selected_iid)
            self.selected_expedition_id = self.expedition_rows[selected_iid].get("id")
        else:
            self.selected_expedition_id = None
        self._render_selected()

    def _expedition_selected(self, _event=None):
        selected = self.expedition_tree.selection()
        expedition = self.expedition_rows.get(selected[0]) if selected else None
        self.selected_expedition_id = expedition.get("id") if expedition else None
        self._render_selected()

    def _render_selected(self):
        expedition = self.manager.get(self.selected_expedition_id) if self.selected_expedition_id else None
        for tree in (self.objective_tree, self.bookmark_tree):
            children = tree.get_children()
            if children:
                tree.delete(*children)
        self.objective_rows = {}
        self.bookmark_rows = {}
        if not expedition:
            all_bookmarks = self.manager.bookmarks()
            self.summary.config(text=(
                f"No expedition selected · {len(all_bookmarks)} profile bookmark(s) remain available"
            ))
            self.metrics.config(text="Named expeditions retain verified statistics across every game session.")
            self.status_btn.config(text="PAUSE / RESUME", state=tk.DISABLED)
            self._insert_bookmarks(all_bookmarks)
            return
        stats = expedition.get("stats") or {}
        complete, total = self.manager.progress(expedition)
        self.summary.config(text=(
            f"{expedition.get('name')} · {str(expedition.get('status')).upper()} · "
            f"{complete}/{total} objectives · {len(stats.get('systems') or []):,} systems · "
            f"{int(stats.get('jumps') or 0):,} jumps · {float(stats.get('distance_ly') or 0):,.1f} ly"
        ))
        self.metrics.config(text=(
            f"SESSIONS {int(stats.get('sessions') or 0)}  ·  "
            f"FSS {int(stats.get('fss_scans') or 0)}  ·  DSS {int(stats.get('dss_maps') or 0)} "
            f"({int(stats.get('dss_efficient') or 0)} efficient)  ·  "
            f"BIO {int(stats.get('bio_analyses') or 0)}  ·  CODEX {int(stats.get('codex') or 0)}  ·  "
            f"PHOTOS {int(stats.get('screenshots') or 0)}  ·  RECON {int(stats.get('recon') or 0)}"
        ))
        self.status_btn.config(
            text="PAUSE" if expedition.get("status") == "active" else "RESUME",
            state=tk.NORMAL if expedition.get("status") != "completed" else tk.DISABLED,
        )
        for objective in expedition.get("objectives") or []:
            context = " · ".join(filter(None, (
                objective.get("target"), objective.get("system"), objective.get("body"),
            ))) or "-"
            progress = f"{int(objective.get('progress') or 0)}/{max(1, int(objective.get('count') or 1))}"
            iid = self.objective_tree.insert("", tk.END, values=(
                str(objective.get("status") or "pending").upper(), objective.get("title") or "Objective",
                progress, context, "AUTO" if objective.get("automatic") else "MANUAL",
            ), tags=(str(objective.get("status") or "pending"),))
            self.objective_rows[iid] = objective
        self._insert_bookmarks(self.manager.bookmarks(expedition.get("id")))

    def _insert_bookmarks(self, bookmarks):
        for bookmark in bookmarks:
            location = " · ".join(filter(None, (bookmark.get("system"), bookmark.get("body")))) or "-"
            tags = ", ".join(bookmark.get("tags") or []) or "-"
            bookmark_tags = [str(bookmark.get("priority") or "Normal")]
            if bookmark.get("status") == "visited":
                bookmark_tags.append("visited")
            iid = self.bookmark_tree.insert("", tk.END, values=(
                bookmark.get("priority") or "Normal", bookmark.get("kind") or "POI",
                bookmark.get("title") or "Bookmark", location, tags,
                str(bookmark.get("status") or "pending").upper(),
            ), tags=tuple(bookmark_tags))
            self.bookmark_rows[iid] = bookmark

    def _selected_expedition(self):
        return self.manager.get(self.selected_expedition_id) if self.selected_expedition_id else None

    def _selected_objective(self):
        selected = self.objective_tree.selection()
        return self.objective_rows.get(selected[0]) if selected else None

    def _selected_bookmark(self):
        selected = self.bookmark_tree.selection()
        return self.bookmark_rows.get(selected[0]) if selected else None

    def _new_expedition(self):
        dialog = self._dialog("New Expedition", "560x470")
        fields = {}
        for label, key, default in (
            ("NAME", "name", ""),
            ("DESTINATION", "destination", ""),
            ("RETURN SYSTEM", "return_system", ""),
        ):
            tk.Label(dialog, text=label, fg=THEME.muted, bg=THEME.bg, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=18, pady=(12, 3))
            entry = tk.Entry(dialog, bg=THEME.input, fg=THEME.text, insertbackground=THEME.accent, relief=tk.FLAT)
            entry.insert(0, default)
            entry.pack(fill=tk.X, padx=18, ipady=5)
            fields[key] = entry
        tk.Label(dialog, text="PURPOSE / DESCRIPTION", fg=THEME.muted, bg=THEME.bg, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=18, pady=(12, 3))
        description = tk.Text(dialog, bg=THEME.input, fg=THEME.text, insertbackground=THEME.accent, relief=tk.FLAT, height=5, wrap=tk.WORD)
        description.pack(fill=tk.BOTH, expand=True, padx=18)

        def create():
            expedition = self.manager.create(
                fields["name"].get(), description.get("1.0", tk.END).strip(),
                start_system=getattr(self.app, "current_sys", ""),
                destination=fields["destination"].get(),
                return_system=fields["return_system"].get(),
            )
            self.selected_expedition_id = expedition.get("id")
            dialog.destroy()
            self._changed()

        button(dialog, "START EXPEDITION", create, accent=True).pack(pady=14)
        fields["name"].focus_set()

    def _add_objective(self):
        expedition = self._selected_expedition()
        if not expedition:
            return
        dialog = self._dialog("Add Expedition Objective", "570x610")
        label_to_kind = {label: key for key, label in OBJECTIVE_KINDS.items()}
        kind_var = tk.StringVar(value=OBJECTIVE_KINDS["reach_system"])
        self._field_label(dialog, "OBJECTIVE TYPE")
        ttk.Combobox(
            dialog, textvariable=kind_var, values=tuple(label_to_kind), state="readonly",
            style="Mission.TCombobox",
        ).pack(fill=tk.X, padx=18, ipady=3)
        entries = {}
        for label, key, default in (
            ("TARGET / SPECIES / CATEGORY / REGION", "target", ""),
            ("SYSTEM CONTEXT (OPTIONAL)", "system", ""),
            ("BODY CONTEXT (OPTIONAL)", "body", ""),
            ("TARGET COUNT", "count", "1"),
        ):
            self._field_label(dialog, label)
            entry = tk.Entry(dialog, bg=THEME.input, fg=THEME.text, insertbackground=THEME.accent, relief=tk.FLAT)
            entry.insert(0, default or "")
            entry.pack(fill=tk.X, padx=18, ipady=5)
            entries[key] = entry
        self._field_label(dialog, "NOTES")
        notes = tk.Text(dialog, bg=THEME.input, fg=THEME.text, insertbackground=THEME.accent, relief=tk.FLAT, height=5, wrap=tk.WORD)
        notes.pack(fill=tk.BOTH, expand=True, padx=18)
        tk.Label(
            dialog,
            text="Automatic objectives advance only when the Elite journal reports their matching fact.",
            fg=THEME.muted, bg=THEME.bg, font=("Cascadia Mono", 8), wraplength=520,
        ).pack(fill=tk.X, padx=18, pady=(9, 0))

        def add():
            self.manager.add_objective(
                expedition["id"], label_to_kind.get(kind_var.get(), "manual"),
                target=entries["target"].get(), system=entries["system"].get(),
                body=entries["body"].get(), count=entries["count"].get(),
                notes=notes.get("1.0", tk.END).strip(),
            )
            dialog.destroy()
            self._changed()

        button(dialog, "ADD OBJECTIVE", add, accent=True).pack(pady=14)

    def _add_current_bookmark(self):
        expedition = self._selected_expedition()
        if not expedition:
            return
        self._bookmark_dialog(expedition["id"])

    def _bookmark_dialog(self, expedition_id, bookmark=None):
        bookmark = bookmark or {}
        dialog = self._dialog("Edit Bookmark" if bookmark else "Add Bookmark", "560x590")
        entries = {}
        for label, key, default in (
            ("TYPE", "kind", bookmark.get("kind") or "System"),
            ("SYSTEM", "system", bookmark.get("system") or getattr(self.app, "current_sys", "")),
            ("BODY", "body", bookmark.get("body") or getattr(self.app, "current_body_name", "")),
            ("TITLE", "title", bookmark.get("title") or ""),
            ("TAGS (COMMA SEPARATED)", "tags", ", ".join(bookmark.get("tags") or [])),
        ):
            self._field_label(dialog, label)
            entry = tk.Entry(dialog, bg=THEME.input, fg=THEME.text, insertbackground=THEME.accent, relief=tk.FLAT)
            entry.insert(0, default or "")
            entry.pack(fill=tk.X, padx=18, ipady=5)
            entries[key] = entry
        self._field_label(dialog, "PRIORITY")
        priority = tk.StringVar(value=bookmark.get("priority") or "Normal")
        ttk.Combobox(dialog, textvariable=priority, values=PRIORITIES, state="readonly", style="Mission.TCombobox").pack(fill=tk.X, padx=18)
        self._field_label(dialog, "NOTES")
        notes = tk.Text(dialog, bg=THEME.input, fg=THEME.text, insertbackground=THEME.accent, relief=tk.FLAT, height=5, wrap=tk.WORD)
        notes.insert("1.0", bookmark.get("notes") or "")
        notes.pack(fill=tk.BOTH, expand=True, padx=18)

        def save():
            tags = [value.strip() for value in entries["tags"].get().split(",") if value.strip()]
            if bookmark:
                self.manager.update_bookmark(
                    bookmark["id"], title=entries["title"].get(), priority=priority.get(),
                    tags=tags, notes=notes.get("1.0", tk.END).strip(),
                )
            else:
                self.manager.add_bookmark(
                    entries["kind"].get(), system=entries["system"].get(),
                    body=entries["body"].get(), title=entries["title"].get(),
                    priority=priority.get(), tags=tags,
                    notes=notes.get("1.0", tk.END).strip(),
                    position=getattr(self.app, "current_coords", None),
                    source="mission-control", expedition_id=expedition_id,
                )
            dialog.destroy()
            self._changed()

        button(dialog, "SAVE BOOKMARK", save, accent=True).pack(pady=14)

    def _dialog(self, title, geometry):
        dialog = tk.Toplevel(self.parent)
        dialog.title(title)
        dialog.geometry(geometry)
        dialog.configure(bg=THEME.bg)
        dialog.transient(self.parent.winfo_toplevel())
        dialog.grab_set()
        return dialog

    @staticmethod
    def _field_label(parent, text):
        tk.Label(parent, text=text, fg=THEME.muted, bg=THEME.bg, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=18, pady=(11, 3))

    def _toggle_status(self):
        expedition = self._selected_expedition()
        if expedition:
            status = "paused" if expedition.get("status") == "active" else "active"
            self.manager.set_status(expedition["id"], status)
            self._changed()

    def _activate_selected(self):
        expedition = self._selected_expedition()
        if expedition and expedition.get("status") != "completed":
            self.manager.set_status(expedition["id"], "active")
            self._changed()

    def _complete_expedition(self):
        expedition = self._selected_expedition()
        if expedition and messagebox.askyesno(
            "Complete Expedition", f"Mark {expedition.get('name')} complete?", parent=self.parent,
        ):
            self.manager.set_status(expedition["id"], "completed")
            self._changed()

    def _delete_expedition(self):
        expedition = self._selected_expedition()
        if expedition and messagebox.askyesno(
            "Delete Expedition", f"Delete {expedition.get('name')} and its linked bookmarks?", parent=self.parent,
        ):
            self.manager.delete(expedition["id"])
            self.selected_expedition_id = None
            self._changed()

    def _toggle_objective(self):
        objective = self._selected_objective()
        if objective and self.selected_expedition_id:
            self.manager.toggle_objective(self.selected_expedition_id, objective["id"])
            self._changed()

    def _remove_objective(self):
        objective = self._selected_objective()
        if objective and self.selected_expedition_id:
            self.manager.remove_objective(self.selected_expedition_id, objective["id"])
            self._changed()

    def _edit_bookmark(self):
        bookmark = self._selected_bookmark()
        if bookmark:
            self._bookmark_dialog(bookmark.get("expedition_id"), bookmark=bookmark)

    def _toggle_bookmark(self):
        bookmark = self._selected_bookmark()
        if bookmark:
            status = "pending" if bookmark.get("status") == "visited" else "visited"
            self.manager.update_bookmark(bookmark["id"], status=status)
            self._changed()

    def _remove_bookmark(self):
        bookmark = self._selected_bookmark()
        if bookmark:
            self.manager.remove_bookmark(bookmark["id"])
            self._changed()

    def _copy_waypoints(self):
        expedition = self._selected_expedition()
        if not expedition:
            return
        names = self.manager.waypoint_lines(expedition["id"])
        if not names:
            return
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append("\n".join(names))

    def _copy_report(self):
        if self.selected_expedition_id and callable(self.copy_report_callback):
            self.copy_report_callback(self.selected_expedition_id)

    def _export_json(self):
        expedition = self._selected_expedition()
        if not expedition:
            return
        safe = "".join(character if character.isalnum() or character in "-_" else "_" for character in expedition.get("name") or "expedition")
        path = filedialog.asksaveasfilename(
            parent=self.parent, title="Export Expedition Plan",
            initialfile=f"{safe}.void-expedition.json", defaultextension=".json",
            filetypes=(("VoidCompass expedition", "*.json"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(self.manager.export_payload(expedition["id"]), handle, indent=2, ensure_ascii=False)
        except OSError as exc:
            messagebox.showerror("Export Expedition", str(exc), parent=self.parent)

    def _import_json(self):
        path = filedialog.askopenfilename(
            parent=self.parent, title="Import Expedition Plan",
            filetypes=(("VoidCompass expedition", "*.json"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                expedition = self.manager.import_payload(json.load(handle))
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror("Import Expedition", str(exc), parent=self.parent)
            return
        self.selected_expedition_id = expedition.get("id")
        self._changed()

    def open_bookmark(self, bookmark_id):
        bookmark = next((row for row in self.manager.bookmarks() if row.get("id") == bookmark_id), None)
        if bookmark:
            self.refresh(bookmark.get("expedition_id"))
            for iid, row in self.bookmark_rows.items():
                if row.get("id") == bookmark_id:
                    self.bookmark_tree.selection_set(iid)
                    self.bookmark_tree.see(iid)
                    break
