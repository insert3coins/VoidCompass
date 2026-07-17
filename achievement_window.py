import os
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from config import save_config
from ui_theme import FONT_MONO, THEME, ThemedWindowMixin, apply_window, configure_ttk, scrollbar, window_surface


class AchievementWindow(ThemedWindowMixin):
    def __init__(self, root, app, engine, embedded=False):
        self.root = root
        self.app = app
        self.engine = engine
        self.config = app.config
        self.embedded = embedded
        self._closing = False
        self._snapshot = {}
        self._items = {}
        self._category_vars = {}
        self._tree_generation = 0
        self._tree_insert_job = None
        self.win = window_surface(root, embedded=embedded)
        self.win.title("Achievements")
        self.win.geometry(self.config.get("achievement_window_geometry", "1080x700"))
        self.win.minsize(880, 560)
        apply_window(self.win)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()
        self.refresh()

    def is_open(self):
        try:
            return bool(not self._closing and self.win and self.win.winfo_exists())
        except Exception:
            return False

    def _button(self, parent, text, command, accent=False, muted=False):
        return self._action_button(parent, text, command, accent=accent, muted=muted)

    def _build(self):
        header = tk.Frame(self.win, bg=THEME.header, height=76)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        title_box = tk.Frame(header, bg=THEME.header)
        title_box.pack(side=tk.LEFT, fill=tk.Y, padx=14)
        tk.Label(
            title_box,
            text="ACHIEVEMENTS",
            font=("Segoe UI", 16, "bold"),
            fg=THEME.accent,
            bg=THEME.header,
            anchor="w",
        ).pack(anchor="w", pady=(12, 0))
        self.header_subtitle = tk.Label(
            title_box,
            text="Elite career milestones // commander profile",
            font=("Consolas", 8),
            fg=self.UI_MUTED,
            bg=THEME.header,
            anchor="w",
        )
        self.header_subtitle.pack(anchor="w", pady=(2, 0))
        self.header_status = tk.Label(
            header,
            text="",
            font=("Consolas", 9, "bold"),
            fg=THEME.text,
            bg=THEME.header,
            justify=tk.RIGHT,
        )
        self.header_status.pack(side=tk.RIGHT, padx=14)

        summary = tk.Frame(self.win, bg=self.UI_BG)
        summary.pack(fill=tk.X, padx=10, pady=(10, 8))
        self.summary_unlocked = self._summary_card(summary, "UNLOCKED", THEME.accent)
        self.summary_points = self._summary_card(summary, "POINTS", self.UI_OK)
        self.summary_progress = self._summary_card(summary, "COMPLETION", THEME.orange)
        self.summary_recent = self._summary_card(summary, "LATEST", "#a5b4fc")

        style = configure_ttk(self.win, "Achievements")
        style.configure("Achievements.TNotebook", background=self.UI_BG, borderwidth=0)
        style.configure(
            "Achievements.TNotebook.Tab",
            background=self.UI_PANEL,
            foreground=THEME.text,
            padding=(14, 7),
            borderwidth=0,
        )
        style.map(
            "Achievements.TNotebook.Tab",
            background=[("selected", self.UI_PANEL_2)],
            foreground=[("selected", THEME.accent)],
        )
        style.configure(
            "Achievements.Treeview",
            background="#0b0f13",
            foreground=THEME.text,
            fieldbackground="#0b0f13",
            rowheight=25,
            borderwidth=0,
            # Monospace matches the app's other data tables (ui_theme uses
            # FONT_MONO for Treeviews) and keeps the progress bars, percentages
            # and counters aligned in their column.
            font=FONT_MONO,
        )
        style.configure(
            "Achievements.Treeview.Heading",
            background=self.UI_PANEL,
            foreground=THEME.orange,
            relief="flat",
            font=("Segoe UI", 8, "bold"),
        )
        style.map(
            "Achievements.Treeview",
            background=[("selected", "#12313c")],
            foreground=[("selected", THEME.text)],
        )

        self.tabs = ttk.Notebook(self.win, style="Achievements.TNotebook")
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._build_catalogue_tab()
        self._build_settings_tab()

    def _summary_card(self, parent, title, accent):
        card = tk.Frame(parent, bg=self.UI_PANEL, highlightbackground=self.UI_BORDER, highlightthickness=1)
        card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Frame(card, bg=accent, height=2).pack(fill=tk.X)
        tk.Label(
            card, text=title, fg=THEME.orange, bg=self.UI_PANEL,
            font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(fill=tk.X, padx=10, pady=(7, 0))
        value = tk.Label(
            card, text="-", fg=THEME.text, bg=self.UI_PANEL,
            font=("Consolas", 10, "bold"), anchor="w", height=2,
        )
        value.pack(fill=tk.X, padx=10, pady=(2, 7))
        return value

    def _build_catalogue_tab(self):
        tab = tk.Frame(self.tabs, bg=self.UI_BG)
        self.tabs.add(tab, text="Catalogue")

        toolbar = tk.Frame(tab, bg=self.UI_BG)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._populate_tree())
        search = tk.Entry(
            toolbar,
            textvariable=self.search_var,
            bg=THEME.input,
            fg=THEME.text,
            insertbackground=THEME.accent,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.UI_BORDER,
            highlightcolor=THEME.accent,
            font=("Segoe UI", 9),
            width=28,
        )
        search.pack(side=tk.LEFT, ipady=4)

        self.category_var = tk.StringVar(value="All categories")
        self.status_var = tk.StringVar(value="All achievements")
        self.category_menu = self._option_menu(toolbar, self.category_var, ["All categories"])
        self.category_menu.pack(side=tk.LEFT, padx=(8, 0))
        self.status_menu = self._option_menu(
            toolbar,
            self.status_var,
            ["All achievements", "Unlocked", "Locked", "Enabled packs", "Disabled packs"],
        )
        self.status_menu.pack(side=tk.LEFT, padx=(8, 0))
        self.category_var.trace_add("write", lambda *_: self._populate_tree())
        self.status_var.trace_add("write", lambda *_: self._populate_tree())
        self._button(toolbar, "Refresh", self.refresh).pack(side=tk.RIGHT)

        content = tk.Frame(tab, bg=self.UI_BG)
        content.pack(fill=tk.BOTH, expand=True)
        left = tk.Frame(content, bg=self.UI_BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = tk.Frame(
            content,
            bg=self.UI_PANEL,
            highlightbackground=self.UI_BORDER,
            highlightthickness=1,
            width=300,
        )
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        right.pack_propagate(False)

        columns = ("status", "title", "category", "progress", "points")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", style="Achievements.Treeview")
        headings = {
            "status": ("STATE", 72, tk.CENTER),
            "title": ("ACHIEVEMENT", 285, tk.W),
            "category": ("CATEGORY", 120, tk.W),
            "progress": ("PROGRESS", 250, tk.W),
            "points": ("PTS", 55, tk.E),
        }
        for column, (title, width, anchor) in headings.items():
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, minwidth=45, anchor=anchor, stretch=column == "title")
        scroll = scrollbar(left, orient=tk.VERTICAL, command=self.tree.yview,
                           prefix="Achievements")
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.tag_configure("unlocked", foreground=self.UI_OK)
        self.tree.tag_configure("disabled", foreground=self.UI_DIM)
        self.tree.bind("<<TreeviewSelect>>", self._on_selected)

        tk.Frame(right, bg=THEME.accent, height=2).pack(fill=tk.X)
        self.detail_icon = tk.Label(
            right, text="★", fg=THEME.accent, bg=self.UI_PANEL,
            font=("Segoe UI Emoji", 26), anchor="w",
        )
        self.detail_icon.pack(fill=tk.X, padx=12, pady=(12, 0))
        self.detail_title = tk.Label(
            right, text="Select an achievement", fg=THEME.text, bg=self.UI_PANEL,
            font=("Segoe UI", 12, "bold"), anchor="w", justify=tk.LEFT, wraplength=270,
        )
        self.detail_title.pack(fill=tk.X, padx=12, pady=(2, 0))
        self.detail_meta = tk.Label(
            right, text="", fg=THEME.orange, bg=self.UI_PANEL,
            font=("Consolas", 8, "bold"), anchor="w", justify=tk.LEFT,
        )
        self.detail_meta.pack(fill=tk.X, padx=12, pady=(4, 0))
        self.detail_bar = tk.Canvas(
            right, height=14, bg=self.UI_PANEL, highlightthickness=0, bd=0,
        )
        self.detail_bar.pack(fill=tk.X, padx=12, pady=(8, 0))
        self.detail_bar.bind("<Configure>", lambda _e: self._draw_detail_bar())
        self._detail_progress = None
        self.detail_text = tk.Text(
            right, bg=self.UI_PANEL, fg=THEME.text, insertbackground=THEME.accent,
            relief=tk.FLAT, bd=0, padx=12, pady=10, font=("Segoe UI", 9), wrap=tk.WORD,
        )
        self.detail_text.pack(fill=tk.BOTH, expand=True)
        self.detail_text.configure(state=tk.DISABLED)
        actions = tk.Frame(right, bg=self.UI_PANEL)
        actions.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.unlock_button = self._button(actions, "Unlock", self._manual_unlock, accent=True)
        self.unlock_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.reset_button = self._button(actions, "Reset", self._reset_selected)
        self.reset_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

    def _build_settings_tab(self):
        tab = tk.Frame(self.tabs, bg=self.UI_BG)
        self.tabs.add(tab, text="Configuration")
        left = tk.Frame(tab, bg=self.UI_BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = tk.Frame(tab, bg=self.UI_BG, width=330)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right.pack_propagate(False)

        general = self._section(left, "Achievement Settings")
        self.enabled_var = tk.BooleanVar(value=self.config.get("achievements_enabled", True))
        self.notifications_var = tk.BooleanVar(value=self.config.get("achievement_notifications_enabled", True))
        self._check_row(general, "Track achievement progress", self.enabled_var)
        self._check_row(general, "Show live unlocks in the Toast HUD", self.notifications_var)
        tk.Label(
            general,
            text="Progress and category choices are stored separately for each commander profile.",
            bg=self.UI_PANEL,
            fg=self.UI_MUTED,
            font=("Segoe UI", 8),
            justify=tk.LEFT,
            anchor="w",
            wraplength=580,
        ).pack(fill=tk.X, padx=12, pady=(2, 10))
        self._button(general, "Save Achievement Settings", self._save_settings, accent=True).pack(
            fill=tk.X, padx=12, pady=(0, 12)
        )

        packs = self._section(left, "Category Packs")
        pack_canvas = tk.Canvas(packs, bg=self.UI_PANEL, highlightthickness=0, height=285)
        pack_scroll = tk.Scrollbar(packs, orient=tk.VERTICAL, command=pack_canvas.yview)
        self.pack_frame = tk.Frame(pack_canvas, bg=self.UI_PANEL)
        pack_window = pack_canvas.create_window((0, 0), window=self.pack_frame, anchor="nw")
        pack_canvas.configure(yscrollcommand=pack_scroll.set)
        pack_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0), pady=(2, 12))
        pack_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=(2, 12))
        self.pack_frame.bind("<Configure>", lambda _e: pack_canvas.configure(scrollregion=pack_canvas.bbox("all")))
        pack_canvas.bind("<Configure>", lambda e: pack_canvas.itemconfigure(pack_window, width=e.width))

        tools = self._section(right, "Profile Tools")
        self._button(tools, "Test Unlock Toast", self._test_unlock_toast, accent=True).pack(fill=tk.X, padx=12, pady=(4, 6))
        self._button(tools, "Import Old State", self._import_legacy_state).pack(fill=tk.X, padx=12, pady=(4, 6))
        self._button(tools, "Rebuild from Journals", self._rebuild_history).pack(fill=tk.X, padx=12, pady=6)
        self._button(tools, "Reset All Progress", self._reset_all).pack(fill=tk.X, padx=12, pady=(6, 12))
        tk.Label(
            tools,
            text=(
                "Import accepts state.json from either old Elite Achievements version and merges unlocks/progress. "
                "Rebuild reads the configured Elite journal folder silently, without replaying old toasts."
            ),
            bg=self.UI_PANEL,
            fg=self.UI_MUTED,
            font=("Segoe UI", 8),
            justify=tk.LEFT,
            anchor="w",
            wraplength=285,
        ).pack(fill=tk.X, padx=12, pady=(0, 12))

        status = self._section(right, "Operation Status")
        self.operation_status = tk.Label(
            status,
            text="Ready",
            bg=self.UI_PANEL,
            fg=THEME.accent,
            font=("Consolas", 9, "bold"),
            justify=tk.LEFT,
            anchor="nw",
            wraplength=285,
            height=6,
        )
        self.operation_status.pack(fill=tk.X, padx=12, pady=(5, 12))

    def _section(self, parent, title):
        section = tk.Frame(parent, bg=self.UI_PANEL, highlightbackground=self.UI_BORDER, highlightthickness=1)
        section.pack(fill=tk.X, pady=(0, 10))
        tk.Frame(section, bg=THEME.accent, height=2).pack(fill=tk.X)
        tk.Label(
            section, text=title.upper(), fg=THEME.orange, bg=self.UI_PANEL,
            font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(9, 5))
        return section

    def _check_row(self, parent, text, variable):
        check = tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            bg=self.UI_PANEL,
            fg=THEME.text,
            activebackground=self.UI_PANEL,
            activeforeground=THEME.accent,
            selectcolor=THEME.input,
            font=("Segoe UI", 9),
            anchor="w",
            highlightthickness=0,
        )
        check.pack(fill=tk.X, padx=10, pady=3)
        return check

    def _option_menu(self, parent, variable, values):
        menu = tk.OptionMenu(parent, variable, *values)
        menu.config(
            bg=self.UI_PANEL_2, fg=THEME.text, activebackground=self.UI_PANEL_2,
            activeforeground=THEME.accent, relief=tk.FLAT, bd=0,
            highlightthickness=1, highlightbackground=self.UI_BORDER,
            font=("Segoe UI", 8), width=16,
        )
        menu["menu"].config(bg=self.UI_PANEL_2, fg=THEME.text)
        return menu

    def _rebuild_category_menu(self, categories):
        menu = self.category_menu["menu"]
        menu.delete(0, tk.END)
        for value in ["All categories"] + list(categories):
            menu.add_command(label=value, command=lambda choice=value: self.category_var.set(choice))
        if self.category_var.get() not in ["All categories"] + list(categories):
            self.category_var.set("All categories")

    def _rebuild_pack_checks(self, categories, disabled):
        for child in self.pack_frame.winfo_children():
            child.destroy()
        self._category_vars = {}
        for index, category in enumerate(categories):
            variable = tk.BooleanVar(value=category not in disabled)
            self._category_vars[category] = variable
            check = tk.Checkbutton(
                self.pack_frame,
                text=category,
                variable=variable,
                bg=self.UI_PANEL,
                fg=THEME.text,
                activebackground=self.UI_PANEL,
                activeforeground=THEME.accent,
                selectcolor=THEME.input,
                font=("Segoe UI", 9),
                anchor="w",
                highlightthickness=0,
            )
            check.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 16), pady=2)
        self.pack_frame.grid_columnconfigure(0, weight=1)
        self.pack_frame.grid_columnconfigure(1, weight=1)

    @staticmethod
    def _progress_text(progress):
        if not progress:
            return "-"
        current = progress.get("current", 0)
        target = progress.get("target", 0)
        if isinstance(current, float) and current.is_integer():
            current = int(current)
        if isinstance(target, float) and target.is_integer():
            target = int(target)
        return f"{current:,} / {target:,}" if isinstance(current, (int, float)) and isinstance(target, (int, float)) else f"{current} / {target}"

    @staticmethod
    def _progress_fraction(progress, unlocked=False):
        """0.0-1.0, or None when the achievement has no measurable progress
        (flag-type achievements are all-or-nothing)."""
        if unlocked:
            return 1.0
        if not progress:
            return None
        current = progress.get("current", 0)
        target = progress.get("target", 0)
        if not isinstance(current, (int, float)) or not isinstance(target, (int, float)):
            return None
        if target <= 0:
            return None
        return max(0.0, min(1.0, current / target))

    _BAR_CELLS = 12

    @classmethod
    def _progress_cell(cls, progress, unlocked=False):
        """Treeview cells can't hold widgets, so the in-tree bar is drawn with
        block characters: '[####------]  32%  32 / 100'.

        Uses ━/─ rather than █/░: the shaded block renders as unreadable mush
        at the tree's font size, while the heavy/light lines stay crisp.
        """
        fraction = cls._progress_fraction(progress, unlocked)
        if fraction is None:
            return "-"
        filled = int(round(fraction * cls._BAR_CELLS))
        bar = "━" * filled + "─" * (cls._BAR_CELLS - filled)
        cell = f"{bar} {fraction * 100:3.0f}%"
        # Flag-type achievements have no counter to show alongside the bar.
        if progress:
            cell = f"{cell}  {cls._progress_text(progress)}"
        return cell

    def _draw_detail_bar(self):
        canvas = getattr(self, "detail_bar", None)
        if canvas is None:
            return
        canvas.delete("all")
        fraction = self._detail_progress
        if fraction is None:
            return
        width = max(canvas.winfo_width(), 1)
        height = int(canvas.cget("height"))
        canvas.create_rectangle(
            0, 3, width, height - 3, fill=THEME.input, outline=THEME.border,
        )
        if fraction > 0:
            fill = THEME.green if fraction >= 1.0 else THEME.accent
            canvas.create_rectangle(
                0, 3, max(2, int(width * fraction)), height - 3, fill=fill, outline=fill,
            )

    def refresh(self):
        if not self.is_open():
            return
        self._snapshot = self.engine.snapshot()
        achievements = self._snapshot.get("achievements", [])
        self._items = {str(item.get("id")): item for item in achievements if item.get("id")}
        unlocked = self._snapshot.get("unlocked", 0)
        total = self._snapshot.get("total", 0)
        points = self._snapshot.get("totalPoints", 0)
        percent = (unlocked / total * 100.0) if total else 0.0
        recent = sorted(
            (item for item in achievements if item.get("unlockedAt")),
            key=lambda item: item.get("unlockedAt") or "",
            reverse=True,
        )
        self.summary_unlocked.config(text=f"{unlocked:,} / {total:,}")
        self.summary_points.config(text=f"{points:,}")
        self.summary_progress.config(text=f"{percent:.1f}%")
        self.summary_recent.config(text=(recent[0].get("title") if recent else "No unlocks yet"))
        active = "ACTIVE" if self._snapshot.get("enabled") else "PAUSED"
        self.header_status.config(text=f"{active}\n{len(self._snapshot.get('categories', []))} CATEGORY PACKS")
        self._rebuild_category_menu(self._snapshot.get("categories", []))
        self._rebuild_pack_checks(
            self._snapshot.get("categories", []), set(self._snapshot.get("disabledCategories", []))
        )
        self.enabled_var.set(bool(self.config.get("achievements_enabled", True)))
        self.notifications_var.set(bool(self.config.get("achievement_notifications_enabled", True)))
        self._populate_tree()

    def _populate_tree(self):
        if not hasattr(self, "tree"):
            return
        self._tree_generation += 1
        generation = self._tree_generation
        if self._tree_insert_job is not None:
            try:
                self.win.after_cancel(self._tree_insert_job)
            except Exception:
                pass
            self._tree_insert_job = None
        selected = self.tree.selection()
        selected_id = selected[0] if selected else None
        self.tree.delete(*self.tree.get_children())
        query = self.search_var.get().strip().lower()
        category = self.category_var.get()
        status = self.status_var.get()
        rows = list(self._items.values())
        rows.sort(key=lambda item: (str(item.get("category") or ""), str(item.get("title") or "")))
        filtered = []
        for item in rows:
            if category != "All categories" and item.get("category") != category:
                continue
            if query and query not in " ".join(
                str(item.get(key) or "").lower() for key in ("title", "desc", "category", "id")
            ):
                continue
            if status == "Unlocked" and not item.get("unlocked"):
                continue
            if status == "Locked" and item.get("unlocked"):
                continue
            if status == "Enabled packs" and item.get("disabled"):
                continue
            if status == "Disabled packs" and not item.get("disabled"):
                continue
            filtered.append(item)
        self._insert_tree_batch(filtered, 0, selected_id, generation)

    def _insert_tree_batch(self, rows, start, selected_id, generation):
        if generation != self._tree_generation or not self.is_open():
            return
        end = min(start + 120, len(rows))
        for item in rows[start:end]:
            state = "OFF" if item.get("disabled") else ("DONE" if item.get("unlocked") else "LOCKED")
            tags = ("disabled",) if item.get("disabled") else (("unlocked",) if item.get("unlocked") else ())
            self.tree.insert(
                "",
                tk.END,
                iid=str(item.get("id")),
                values=(
                    state,
                    f"{item.get('icon') or '★'}  {item.get('title') or item.get('id')}",
                    item.get("category") or "-",
                    self._progress_cell(item.get("progress"), bool(item.get("unlocked"))),
                    f"{int(item.get('points') or 0):,}",
                ),
                tags=tags,
            )
        if end < len(rows):
            self._tree_insert_job = self.win.after(
                1,
                lambda: self._insert_tree_batch(rows, end, selected_id, generation),
            )
            return
        self._tree_insert_job = None
        if selected_id and self.tree.exists(selected_id):
            self.tree.selection_set(selected_id)
            self.tree.see(selected_id)
        elif self.tree.get_children():
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self._show_detail(first)

    def _on_selected(self, _event=None):
        selected = self.tree.selection()
        if selected:
            self._show_detail(selected[0])

    def _show_detail(self, achievement_id):
        item = self._items.get(str(achievement_id))
        if not item:
            return
        self.detail_icon.config(text=item.get("icon") or "★")
        self.detail_title.config(text=item.get("title") or achievement_id)
        state = "PACK DISABLED" if item.get("disabled") else ("UNLOCKED" if item.get("unlocked") else "LOCKED")
        self.detail_meta.config(text=f"{state}  //  {item.get('category') or '-'}  //  {int(item.get('points') or 0):,} PTS")
        unlocked_at = item.get("unlockedAt")
        if unlocked_at:
            try:
                unlocked_at = datetime.fromisoformat(unlocked_at.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
        self._detail_progress = self._progress_fraction(item.get("progress"), bool(item.get("unlocked")))
        self._draw_detail_bar()
        body = [item.get("desc") or "No description.", "", f"Progress: {self._progress_text(item.get('progress'))}"]
        if unlocked_at:
            body.append(f"Unlocked: {unlocked_at}")
        body.extend(["", f"ID: {item.get('id')}"])
        self.detail_text.configure(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", "\n".join(body))
        self.detail_text.configure(state=tk.DISABLED)
        self.unlock_button.configure(state=tk.DISABLED if item.get("unlocked") else tk.NORMAL)
        self.reset_button.configure(state=tk.NORMAL if item.get("unlocked") else tk.DISABLED)

    def _selected_id(self):
        selected = self.tree.selection()
        return selected[0] if selected else None

    def _manual_unlock(self):
        achievement_id = self._selected_id()
        if achievement_id and self.engine.manual_unlock(achievement_id, notify=True):
            self.refresh()

    def _reset_selected(self):
        achievement_id = self._selected_id()
        item = self._items.get(str(achievement_id))
        if not item:
            return
        if not messagebox.askyesno("Reset achievement", f"Reset '{item.get('title')}' and its progress?", parent=self.win):
            return
        self.engine.reset_achievement(achievement_id)
        self.refresh()

    def _save_settings(self):
        disabled = sorted(category for category, variable in self._category_vars.items() if not variable.get())
        self.config["achievements_enabled"] = bool(self.enabled_var.get())
        self.config["achievement_notifications_enabled"] = bool(self.notifications_var.get())
        self.config["achievements_disabled_categories"] = disabled
        save_config(self.config)
        self.engine.set_options(enabled=self.enabled_var.get(), disabled_categories=disabled)
        self.operation_status.config(text=f"Saved\n{len(disabled)} category packs disabled")
        self.app.add_event_feed_entry("ACHIEVEMENT", "Achievement settings saved", severity="INFO")
        self.refresh()

    def _import_legacy_state(self):
        default_dir = os.path.abspath(os.path.join(os.getcwd(), "..", "Elite Achievements"))
        path = filedialog.askopenfilename(
            parent=self.win,
            title="Import old achievement state",
            initialdir=default_dir if os.path.isdir(default_dir) else os.getcwd(),
            filetypes=(("Achievement state", "state.json"), ("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            result = self.engine.import_legacy_state(path)
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc), parent=self.win)
            return
        self.operation_status.config(
            text=f"Import complete\n{result['unlocked']} legacy unlocks read\n{result['totalUnlocked']} total unlocked"
        )
        self.refresh()

    def _test_unlock_toast(self):
        if not self.config.get("achievement_notifications_enabled", True) or not getattr(self.app, "toast_hud", None):
            messagebox.showwarning(
                "Achievement toast",
                "Enable both achievement notifications here and Toast Notifications under Settings > Overlays first.",
                parent=self.win,
            )
            return
        unlocked = self.engine.process_event({"event": "_meta", "action": "test_toast"}, notify=True)
        if not unlocked:
            messagebox.showinfo(
                "Achievement toast",
                "The test achievement is already unlocked. Reset 'Signal Test' in the catalogue to fire it again.",
                parent=self.win,
            )
        self.refresh()

    def _rebuild_history(self):
        journal_dir = self.config.get("journal_path")
        if not journal_dir or not os.path.isdir(journal_dir):
            messagebox.showwarning("Journal folder", "Set a valid journal path in Settings first.", parent=self.win)
            return
        if not messagebox.askyesno(
            "Rebuild achievement history",
            "Re-derive progress from every journal file on disk?\n\n"
            "Existing unlocks are kept — including imported and manually granted "
            "ones that these journals can no longer prove. Counters only ever move "
            "up. Rebuilt unlocks stay silent (no toasts).\n\n"
            "To wipe everything instead, use Reset All.",
            parent=self.win,
        ):
            return
        self.operation_status.config(text="Starting journal rebuild...")

        def progress(done, total, filename):
            try:
                self.win.after(0, lambda: self.operation_status.config(text=f"Rebuilding journals\n{done:,} / {total:,} files\n{filename}"))
            except Exception:
                pass

        def work():
            try:
                result = self.engine.rebuild_history(journal_dir, progress_callback=progress)
            except Exception as exc:
                self.win.after(0, lambda: messagebox.showerror("Rebuild failed", str(exc), parent=self.win))
                return

            def complete():
                preserved = result.get("preserved", 0)
                kept = f"\n{preserved:,} kept from before the rebuild" if preserved else ""
                self.operation_status.config(
                    text=(
                        f"Rebuild complete\n{result['files']:,} files / {result['events']:,} events\n"
                        f"{result['unlocked']:,} achievements unlocked{kept}"
                    )
                )
                self.refresh()
                self.app.add_event_feed_entry(
                    "ACHIEVEMENT",
                    f"History rebuild complete: {result['unlocked']:,} unlocked",
                    severity="INFO",
                )

            self.win.after(0, complete)

        threading.Thread(target=work, name="achievement-history-rebuild", daemon=True).start()

    def _reset_all(self):
        if not messagebox.askyesno(
            "Reset all achievements",
            "Delete all achievement unlocks and progress for this commander?",
            parent=self.win,
        ):
            return
        self.engine.reset_all()
        self.operation_status.config(text="All progress reset for this commander")
        self.refresh()

    def _on_close(self):
        try:
            self.config["achievement_window_geometry"] = self.win.geometry()
            save_config(self.config)
        except Exception:
            pass
        if self.embedded:
            self.win.pack_forget()
            self.app.show_dashboard_page()
        else:
            self._closing = True
            self.win.destroy()
