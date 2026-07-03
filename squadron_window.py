"""
squadron_window.py - Squadron tracker for VoidCompass.

Uses journal SquadronStartup/promotion events for commander-local state and
optionally attempts the Frontier website squadron info endpoint by tag.
"""

import json
import os
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox
from urllib.parse import urlencode

import requests

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, CONFIG_FILE
from version import APP_VERSION

SQUADRON_STATE_FILE = "squadron_state.json"
SQUADRON_INFO_URL = "https://api.orerve.net/2.0/website/squadron/info"

_RANK_LABELS = {
    0: "Rookie",
    1: "Agent",
    2: "Officer",
    3: "Senior Officer",
    4: "Leader",
}


def load_squadron_state(path=None) -> dict:
    path = path or os.path.join(os.getcwd(), SQUADRON_STATE_FILE)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_squadron_state(state: dict, path=None):
    path = path or os.path.join(os.getcwd(), SQUADRON_STATE_FILE)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state or {}, f, indent=2)
    except Exception:
        pass


def squadron_rank_label(rank):
    try:
        idx = int(rank)
    except Exception:
        return str(rank or "Unknown")
    return f"{_RANK_LABELS.get(idx, 'Rank')} ({idx})"


def fetch_squadron_info(tag, platform="PC", timeout=12):
    tag = str(tag or "").strip()
    platform = str(platform or "PC").strip().upper() or "PC"
    if not tag:
        return {"ok": False, "status": None, "error": "Enter a squadron tag first."}

    headers = {
        "Accept": "application/json",
        "User-Agent": f"VoidCompass/{APP_VERSION}",
    }
    try:
        response = requests.get(
            SQUADRON_INFO_URL,
            params={"platform": platform, "tag": tag},
            headers=headers,
            timeout=timeout,
        )
    except Exception as exc:
        return {"ok": False, "status": None, "error": str(exc)}

    try:
        payload = response.json()
    except Exception:
        payload = {"raw": response.text[:2000]}

    if response.status_code == 401:
        return {
            "ok": False,
            "status": 401,
            "error": "Frontier squadron info requires website OAuth; local journal data is still available.",
            "payload": payload,
        }
    if response.status_code >= 400:
        return {
            "ok": False,
            "status": response.status_code,
            "error": payload.get("message") if isinstance(payload, dict) else response.reason,
            "payload": payload,
        }
    return {"ok": True, "status": response.status_code, "payload": payload}


class SquadronWindow:
    UI_BG = "#080a0d"
    UI_PANEL = "#12161b"
    UI_PANEL_2 = "#171d23"
    UI_BORDER = "#26313a"
    UI_MUTED = "#7d8891"
    UI_DIM = "#4e5962"
    UI_FAIL = "#ff5c5c"
    UI_OK = "#21d189"
    UI_FONT = ("Segoe UI", 9)
    UI_FONT_BOLD = ("Segoe UI", 9, "bold")
    UI_MONO = ("Consolas", 9)
    UI_MONO_BOLD = ("Consolas", 10, "bold")

    def __init__(self, root, config: dict, state: dict, save_callback):
        self.root = root
        self.config = config
        self.state = state
        self.save_callback = save_callback
        self._fetching = False

        self.win = tk.Toplevel(root)
        self.win.title("VOID COMPASS // SQUADRON")
        self.win.configure(bg=self.UI_BG)
        self.win.geometry(config.get("squadron_window_geometry", "760x520"))
        self.win.resizable(True, True)
        self.win.minsize(620, 400)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self.refresh()

    def is_open(self) -> bool:
        try:
            return bool(self.win and self.win.winfo_exists())
        except Exception:
            return False

    def lift(self):
        try:
            self.win.lift()
            self.win.focus_force()
        except Exception:
            pass

    def refresh(self):
        if not self.is_open():
            return
        self._render_local()
        self._render_remote()

    def _action_button(self, parent, text, command, accent=False, muted=False):
        bg = COLOR_ACCENT if accent else parent.cget("bg")
        fg = "black" if accent else (self.UI_DIM if muted else COLOR_TEXT)
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=COLOR_ACCENT if accent else self.UI_PANEL_2,
            activeforeground="black" if accent else COLOR_TEXT,
            font=self.UI_FONT_BOLD,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
        )

    def _build_ui(self):
        hdr = tk.Frame(self.win, bg="#0c1014", height=46)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(
            hdr,
            text="SQUADRON",
            font=("Segoe UI", 13, "bold"),
            fg=COLOR_ACCENT,
            bg="#0c1014",
        ).pack(side=tk.LEFT, padx=14, pady=8)
        self.status_lbl = tk.Label(hdr, text="", fg=self.UI_DIM, bg="#0c1014", font=self.UI_MONO)
        self.status_lbl.pack(side=tk.RIGHT, padx=14)

        body = tk.Frame(self.win, bg=self.UI_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left = tk.Frame(body, bg=self.UI_PANEL, width=260)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.pack_propagate(False)

        tk.Label(left, text="LOCAL JOURNAL", font=self.UI_FONT_BOLD, fg=COLOR_ORANGE, bg=self.UI_PANEL).pack(anchor="w", padx=12, pady=(12, 4))
        self.local_name = self._value_row(left, "Name")
        self.local_rank = self._value_row(left, "Your Rank")
        self.local_tag = self._value_row(left, "Lookup Tag")
        self.local_updated = self._value_row(left, "Updated")

        tk.Frame(left, bg=self.UI_BORDER, height=1).pack(fill=tk.X, padx=12, pady=12)
        tk.Label(left, text="FRONTIER LOOKUP", font=self.UI_FONT_BOLD, fg=COLOR_ORANGE, bg=self.UI_PANEL).pack(anchor="w", padx=12, pady=(0, 6))
        tk.Label(left, text="Squadron Tag", font=("Segoe UI", 8, "bold"), fg=self.UI_DIM, bg=self.UI_PANEL).pack(anchor="w", padx=12)
        self.tag_entry = tk.Entry(left, bg="#0b0f13", fg=COLOR_TEXT, insertbackground=COLOR_ACCENT, relief=tk.FLAT, font=self.UI_MONO)
        self.tag_entry.pack(fill=tk.X, padx=12, pady=(2, 8), ipady=4)
        tk.Label(left, text="Platform", font=("Segoe UI", 8, "bold"), fg=self.UI_DIM, bg=self.UI_PANEL).pack(anchor="w", padx=12)
        self.platform_var = tk.StringVar(value=str(self.state.get("platform") or self.config.get("squadron_platform") or "PC").upper())
        self.platform_menu = tk.OptionMenu(left, self.platform_var, "PC", "XBOX", "PS4")
        self.platform_menu.config(bg=self.UI_PANEL_2, fg=COLOR_TEXT, activebackground=self.UI_PANEL_2, activeforeground=COLOR_ACCENT, relief=tk.FLAT, bd=0, highlightthickness=0)
        self.platform_menu["menu"].config(bg=self.UI_PANEL_2, fg=COLOR_TEXT)
        self.platform_menu.pack(fill=tk.X, padx=12, pady=(2, 10))
        self._action_button(left, "Refresh Squadron Info", self.refresh_remote, accent=True).pack(fill=tk.X, padx=12)

        right = tk.Frame(body, bg=self.UI_PANEL)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(right, text="DETAILS", font=self.UI_FONT_BOLD, fg=COLOR_ORANGE, bg=self.UI_PANEL).pack(anchor="w", padx=12, pady=(12, 4))
        self.detail_text = tk.Text(
            right,
            bg="#0b0f13",
            fg=COLOR_TEXT,
            font=self.UI_MONO,
            relief=tk.FLAT,
            highlightthickness=0,
            wrap=tk.WORD,
            padx=10,
            pady=8,
        )
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.detail_text.config(state=tk.DISABLED)

    def _value_row(self, parent, label):
        tk.Label(parent, text=label.upper(), font=("Segoe UI", 8, "bold"), fg=self.UI_DIM, bg=self.UI_PANEL).pack(anchor="w", padx=12, pady=(8, 0))
        value = tk.Label(parent, text="-", font=self.UI_MONO_BOLD, fg=COLOR_TEXT, bg=self.UI_PANEL, anchor="w", wraplength=230, justify=tk.LEFT)
        value.pack(fill=tk.X, padx=12)
        return value

    def _set_status(self, text, fg=None):
        self.status_lbl.config(text=text, fg=fg or self.UI_DIM)

    def _render_local(self):
        name = self.state.get("squadron_name") or "No squadron detected"
        rank = squadron_rank_label(self.state.get("current_rank")) if self.state.get("current_rank") is not None else "-"
        tag = self.state.get("lookup_tag") or self.state.get("tag") or self.config.get("squadron_lookup_tag") or ""
        updated = self._format_ts(self.state.get("last_updated"))
        self.local_name.config(text=name)
        self.local_rank.config(text=rank)
        self.local_tag.config(text=tag or "-")
        self.local_updated.config(text=updated or "-")
        if not self.tag_entry.get().strip() and tag:
            self.tag_entry.insert(0, tag)

    def _render_remote(self):
        lines = []
        remote = self.state.get("remote_info")
        remote_error = self.state.get("remote_error")
        if remote:
            lines.extend(self._format_payload(remote))
            self._set_status("Remote info loaded", self.UI_OK)
        elif remote_error:
            lines.append(f"Remote lookup: {remote_error}")
            lines.append("")
            lines.append("The local journal still reports your squadron name and rank. Frontier's website squadron info endpoint may require an authenticated website/OAuth session.")
            self._set_status("Remote unavailable", self.UI_FAIL)
        else:
            lines.append("No remote lookup loaded yet.")
            lines.append("")
            lines.append("Enter a squadron tag and refresh. If Frontier requires OAuth, the window will keep showing local journal data.")
            self._set_status("Local only", self.UI_DIM)
        self._set_details("\n".join(lines))

    def _format_payload(self, payload):
        if not isinstance(payload, dict):
            return [str(payload)]
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        preferred = [
            "name", "tag", "id", "squadronId", "platform", "memberCount",
            "member_count", "ownerName", "leaderName", "factionName",
            "powerName", "allegiance", "language", "created", "description",
            "public_comms", "acceptingApplications",
        ]
        lines = []
        seen = set()
        for key in preferred:
            if key in data:
                lines.append(f"{self._label(key)}: {self._value(data.get(key))}")
                seen.add(key)
        for key in sorted(k for k in data.keys() if k not in seen and not isinstance(data.get(k), (dict, list))):
            lines.append(f"{self._label(key)}: {self._value(data.get(key))}")
        nested = {k: v for k, v in data.items() if isinstance(v, (dict, list))}
        if nested:
            lines.append("")
            lines.append("Raw nested data:")
            lines.append(json.dumps(nested, indent=2)[:4000])
        return lines or [json.dumps(payload, indent=2)[:4000]]

    @staticmethod
    def _label(key):
        text = str(key).replace("_", " ")
        out = []
        for char in text:
            if out and char.isupper() and out[-1].islower():
                out.append(" ")
            out.append(char)
        return "".join(out).strip().title()

    @staticmethod
    def _value(value):
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if value is None:
            return "-"
        return str(value)

    @staticmethod
    def _format_ts(value):
        if not value:
            return ""
        try:
            return datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(value)

    def _set_details(self, text):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", text)
        self.detail_text.config(state=tk.DISABLED)

    def refresh_remote(self):
        if self._fetching:
            return
        tag = self.tag_entry.get().strip()
        platform = self.platform_var.get().strip().upper() or "PC"
        self.state["lookup_tag"] = tag
        self.state["platform"] = platform
        self.config["squadron_lookup_tag"] = tag
        self.config["squadron_platform"] = platform
        self.save_callback(self.state)
        self._render_local()
        self._fetching = True
        self._set_status("Refreshing...", COLOR_ORANGE)
        query = urlencode({"platform": platform, "tag": tag})
        self._set_details(f"Fetching {SQUADRON_INFO_URL}?{query}")

        def worker():
            result = fetch_squadron_info(tag, platform)
            self.win.after(0, lambda: self._apply_remote_result(result))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_remote_result(self, result):
        self._fetching = False
        self.state["last_remote_lookup"] = time.time()
        if result.get("ok"):
            self.state["remote_info"] = result.get("payload")
            self.state["remote_error"] = ""
        else:
            self.state["remote_error"] = result.get("error") or f"HTTP {result.get('status')}"
            self.state["remote_info"] = result.get("payload") if result.get("payload") else None
        self.save_callback(self.state)
        self.refresh()
        if result.get("ok"):
            messagebox.showinfo(
                "Squadron Lookup",
                "Squadron info loaded successfully.",
                parent=self.win,
            )
        else:
            messagebox.showwarning(
                "Squadron Lookup",
                self.state.get("remote_error") or "Squadron lookup failed.",
                parent=self.win,
            )

    def _on_close(self):
        try:
            self.config["squadron_window_geometry"] = self.win.geometry()
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass
