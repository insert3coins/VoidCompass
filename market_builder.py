import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from config import COLOR_ACCENT, COLOR_BG, COLOR_ORANGE, COLOR_TEXT
from trade import marketdb, seed


if "--trade-seed-worker" in sys.argv:
    raise SystemExit(seed.run_worker(sys.argv[1:]))


class MarketBuilderApp:
    UI_PANEL = "#12161b"
    UI_PANEL_2 = "#171d23"
    UI_BORDER = "#26313a"
    UI_MUTED = "#7d8891"
    UI_WARN = "#ff9a3c"
    UI_FAIL = "#ff5c5c"
    UI_OK = "#21d189"

    @staticmethod
    def _duration(seconds):
        if seconds is None:
            return "--"
        try:
            seconds = max(0, int(seconds))
        except Exception:
            return "--"
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h:d}:{m:02d}:{s:02d}"
        return f"{m:d}:{s:02d}"

    def __init__(self, root):
        self.root = root
        self.root.title("Void Compass Market Builder")
        self.root.geometry("620x360")
        self.root.configure(bg=COLOR_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.poll_after = None
        self.include_carriers = tk.BooleanVar(value=False)
        self.low_impact = tk.BooleanVar(value=True)
        self.keep_dump = tk.BooleanVar(value=False)
        self._db_info = {}
        self._db_info_loading = False
        self._db_info_last = 0.0
        self._build()
        self.refresh()
        self.poll()

    def _build(self):
        header = tk.Frame(self.root, bg="#0c1014", height=62)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header,
            text="MARKET BUILDER",
            fg=COLOR_ACCENT,
            bg="#0c1014",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", padx=14, pady=(10, 0))
        tk.Label(
            header,
            text="Spansh nightly dump -> local trade database",
            fg=self.UI_MUTED,
            bg="#0c1014",
            font=("Consolas", 8),
        ).pack(anchor="w", padx=14)

        panel = tk.Frame(self.root, bg=self.UI_PANEL, highlightbackground=self.UI_BORDER, highlightthickness=1)
        panel.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        tk.Frame(panel, bg=COLOR_ACCENT, height=2).pack(fill=tk.X)

        self.status = tk.Label(
            panel,
            text="Checking...",
            fg=COLOR_TEXT,
            bg=self.UI_PANEL,
            justify=tk.LEFT,
            anchor="nw",
            font=("Consolas", 9),
        )
        self.status.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        self.progress = ttk.Progressbar(panel, mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X, padx=12, pady=(0, 12))

        row = tk.Frame(panel, bg=self.UI_PANEL)
        row.pack(fill=tk.X, padx=12, pady=(0, 12))
        self.build_btn = self._button(row, "Build Database", self.start_build, accent=True)
        self.build_btn.pack(side=tk.LEFT)
        tk.Checkbutton(row, text="Low impact", variable=self.low_impact, bg=self.UI_PANEL, fg=COLOR_TEXT, selectcolor=self.UI_PANEL_2, activebackground=self.UI_PANEL).pack(side=tk.LEFT, padx=10)
        tk.Checkbutton(row, text="Include carriers", variable=self.include_carriers, bg=self.UI_PANEL, fg=COLOR_TEXT, selectcolor=self.UI_PANEL_2, activebackground=self.UI_PANEL).pack(side=tk.LEFT, padx=10)
        tk.Checkbutton(row, text="Keep dump", variable=self.keep_dump, bg=self.UI_PANEL, fg=COLOR_TEXT, selectcolor=self.UI_PANEL_2, activebackground=self.UI_PANEL).pack(side=tk.LEFT, padx=10)

    def _button(self, parent, text, command, accent=False):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=COLOR_ACCENT if accent else self.UI_PANEL_2,
            fg="black" if accent else COLOR_TEXT,
            activebackground=COLOR_ORANGE if accent else self.UI_PANEL,
            activeforeground="black" if accent else COLOR_ACCENT,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=6,
            font=("Segoe UI", 8, "bold"),
        )

    def start_build(self):
        if not messagebox.askyesno(
            "Build Market Database",
            "Download the Spansh populated galaxy dump and rebuild the local market database?\n\n"
            "The existing market database remains available until the new one is ready.",
            parent=self.root,
        ):
            return
        ok = seed.SEEDER.start(
            include_carriers=self.include_carriers.get(),
            keep_dump=self.keep_dump.get(),
            polite=self.low_impact.get(),
        )
        if not ok:
            messagebox.showwarning("Market Builder", "A market database build is already running.", parent=self.root)
        self.refresh()

    def refresh(self):
        progress = seed.SEEDER.progress()
        phase = progress.get("phase")
        running = phase in ("starting", "downloading", "importing", "indexing")
        if not running:
            self._refresh_db_info_async()
        info = dict(self._db_info)
        if phase in ("starting", "downloading", "importing", "indexing"):
            self.build_btn.configure(state=tk.DISABLED)
        else:
            self.build_btn.configure(state=tk.NORMAL, text="Rebuild Database" if info.get("ready") else "Build Database")

        if phase == "downloading":
            done = progress.get("downloaded_mb") or 0
            total = progress.get("total_mb") or 0
            pct = int(done * 100 / total) if total else 0
            self.progress.configure(mode="determinate", value=pct)
            phase_text = f"Downloading Spansh dump: {done} / {total} MB ({pct}%)"
            rate_text = f"{(progress.get('rate', 0) or 0) / 1_000_000:.1f} MB/s"
        elif phase == "importing":
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
            phase_text = f"Importing: {progress.get('systems_done', 0):,} systems, {progress.get('stations_done', 0):,} station markets"
            rate_text = f"{progress.get('rate', 0):.1f} systems/s"
        elif phase == "indexing":
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
            phase_text = "Creating trade search indexes..."
            rate_text = "index build"
        elif phase == "starting":
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
            phase_text = "Starting worker process..."
            rate_text = "--"
        else:
            try:
                self.progress.stop()
            except Exception:
                pass
            self.progress.configure(mode="determinate", value=100 if info.get("ready") else 0)
            if phase == "error":
                phase_text = f"Build failed: {progress.get('error')}"
            elif phase == "done":
                phase_text = "Build complete."
            else:
                phase_text = "Idle."
            rate_text = "--"

        timing_text = ""
        if running:
            timing_text = (
                f"Elapsed: {self._duration(progress.get('elapsed_s'))} | "
                f"ETA: {self._duration(progress.get('eta_s'))} | "
                f"Rate: {rate_text}\n"
            )

        self.status.configure(
            text=(
                f"{phase_text}\n\n"
                f"Mode: {'low impact' if progress.get('polite', True) else 'fast'}\n"
                f"{timing_text}"
                f"Current DB: {info.get('stations', 0):,} stations | {info.get('commodity_rows', 0):,} price rows | {info.get('db_size_mb', 0)} MB"
                f"{' (refreshing)' if self._db_info_loading else ''}\n"
                f"Seeded: {info.get('seeded_at') or 'not yet'}\n"
                f"Path: {info.get('db_path') or marketdb.DB_PATH}"
            ),
            fg=self.UI_FAIL if phase == "error" else COLOR_TEXT,
        )

    def _refresh_db_info_async(self, min_interval=5.0):
        now = time.monotonic()
        if self._db_info_loading or (now - self._db_info_last) < min_interval:
            return
        self._db_info_loading = True

        def worker():
            info = {}
            try:
                conn = marketdb.connect()
                try:
                    info = marketdb.status(conn)
                finally:
                    conn.close()
            except Exception:
                pass

            def apply():
                self._db_info = info
                self._db_info_last = time.monotonic()
                self._db_info_loading = False

            try:
                self.root.after(0, apply)
            except Exception:
                self._db_info_loading = False

        threading.Thread(target=worker, name="market-builder-status", daemon=True).start()

    def poll(self):
        self.refresh()
        self.poll_after = self.root.after(1200, self.poll)

    def on_close(self):
        if self.poll_after:
            try:
                self.root.after_cancel(self.poll_after)
            except Exception:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    app = MarketBuilderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
