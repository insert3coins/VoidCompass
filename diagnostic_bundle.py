"""Create a privacy-redacted support archive without raw commander data."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import platform
import re
import sys
import zipfile


SENSITIVE_KEY_PARTS = (
    "api", "key", "token", "secret", "password", "webhook", "fid",
    "commander_name", "cmdr_name", "commander_profile",
)


def _redact_path(text):
    text = re.sub(r"(?i)C:\\Users\\[^\\\s\"']+", r"C:\\Users\\<redacted>", str(text))
    text = re.sub(r"(?i)([\\/]profiles[\\/])[^\\/\s\"']+", r"\1<redacted>", text)
    text = re.sub(r"(?i)(FID[\"'=:\s]+)[A-Za-z0-9_-]+", r"\1<redacted>", text)
    return text


def _redact_value(key, value):
    lowered = str(key).casefold()
    if lowered in {"commander_profiles", "profiles"}:
        return "<redacted>" if value else value
    if any(part in lowered for part in SENSITIVE_KEY_PARTS):
        return "<redacted>" if value not in (None, "", False) else value
    if isinstance(value, dict):
        return {str(k): _redact_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(key, item) for item in value]
    if isinstance(value, str):
        return _redact_path(value)
    return value


def _journal_event_index(journal_path, limit=250):
    folder = Path(journal_path) if journal_path else None
    if not folder or not folder.is_dir():
        return []
    files = sorted(folder.glob("Journal.*.log"), key=lambda item: item.stat().st_mtime)
    if not files:
        return []
    rows = []
    try:
        for line in files[-1].read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            rows.append({"timestamp": event.get("timestamp"), "event": event.get("event")})
    except OSError:
        return []
    return rows


def create_support_bundle(base_dir, config, version, *, health=None, profile_key=None):
    base = Path(base_dir).resolve()
    logs = base / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = logs / f"VoidCompass-support-{stamp}.zip"
    manifest = {
        "void_compass_version": str(version),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packaged": bool(getattr(sys, "frozen", False)),
        "profile": "<redacted>" if profile_key else None,
        "health": health or {},
    }
    profile_dir = base / "profiles" / str(profile_key or "")
    if profile_dir.is_dir():
        manifest["profile_files"] = [
            {"name": item.name, "bytes": item.stat().st_size,
             "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat(timespec="seconds")}
            for item in sorted(profile_dir.iterdir()) if item.is_file()
        ]
    safe_config = _redact_value("config", dict(config or {}))
    journal_index = _journal_event_index((config or {}).get("journal_path"))
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        archive.writestr("config.redacted.json", json.dumps(safe_config, indent=2))
        archive.writestr("journal-events.redacted.json", json.dumps(journal_index, indent=2))
        for path in sorted(logs.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True):
            if not path.is_file() or path == target or path.suffix.lower() == ".zip":
                continue
            if not (path.name.startswith("runtime_trace") or path.name.startswith("crash_report")):
                continue
            try:
                content = _redact_path(path.read_text(encoding="utf-8", errors="replace"))
                archive.writestr(f"logs/{path.name}", content)
            except OSError:
                pass
    return target
