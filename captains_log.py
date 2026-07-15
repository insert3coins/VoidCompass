"""Bounded, per-commander expedition chronicle built from Elite journals."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime


MAX_SESSIONS = 250
MAX_HIGHLIGHTS = 180
TRACKED_EVENTS = {
    "LoadGame", "Shutdown", "FSDJump", "CarrierJump", "CodexEntry", "ScanOrganic",
    "Screenshot", "MarketBuy", "MarketSell", "SellExplorationData",
    "MultiSellExplorationData", "SellOrganicData", "Died",
}


def _stamp(raw):
    return str((raw or {}).get("timestamp") or datetime.utcnow().isoformat(timespec="seconds") + "Z")


class CaptainsLog:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.data = {"sessions": [], "seen": [], "imported_files": {}}
        self.load()
        self._seen_set = set(self.data.get("seen") or [])

    def switch(self, path):
        with self.lock:
            self.path = path
            self.data = {"sessions": [], "seen": [], "imported_files": {}}
            self.load()
            self._seen_set = set(self.data.get("seen") or [])

    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except Exception:
            pass

    def save(self):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            pass

    def sessions(self):
        with self.lock:
            return list(reversed(self.data.get("sessions") or []))

    def _session(self, raw, create=True):
        sessions = self.data.setdefault("sessions", [])
        if sessions and not sessions[-1].get("ended"):
            return sessions[-1]
        if not create:
            return None
        session = {
            "started": _stamp(raw), "ended": None,
            "commander": raw.get("Commander") or "", "ship": raw.get("Ship_Localised") or raw.get("Ship") or "",
            "start_system": raw.get("StarSystem") or "", "end_system": raw.get("StarSystem") or "",
            "jumps": 0, "distance_ly": 0.0, "codex": 0, "bio_analyses": 0, "screenshots": 0,
            "trade_bought": 0, "trade_sold": 0, "trade_profit": 0,
            "exploration_sales": 0, "biology_sales": 0, "deaths": 0, "highlights": [],
        }
        sessions.append(session)
        self.data["sessions"] = sessions[-MAX_SESSIONS:]
        return session

    @staticmethod
    def _event_key(raw):
        return "|".join(str(raw.get(k) or "") for k in (
            "timestamp", "event", "StarSystem", "BodyName", "Species", "Filename", "MarketID", "Type"
        ))

    def _highlight(self, session, raw, kind, title, detail=""):
        rows = session.setdefault("highlights", [])
        rows.append({"timestamp": _stamp(raw), "kind": kind, "title": title, "detail": detail})
        session["highlights"] = rows[-MAX_HIGHLIGHTS:]

    def process_event(self, raw, save=True):
        if not isinstance(raw, dict):
            return False
        ev = raw.get("event")
        if ev not in TRACKED_EVENTS:
            return False
        key = self._event_key(raw)
        with self.lock:
            seen = self.data.setdefault("seen", [])
            if key in self._seen_set:
                return False
            seen.append(key)
            self._seen_set.add(key)
            if len(seen) > 6000:
                self.data["seen"] = seen[-6000:]
                self._seen_set = set(self.data["seen"])

            if ev == "LoadGame":
                current = self._session(raw, create=False)
                if current:
                    current["ended"] = _stamp(raw)
                session = self._session(raw, create=True)
                self._highlight(session, raw, "SESSION", "Flight session started", session.get("ship") or "")
            else:
                session = self._session(raw, create=True)

            changed = True
            if ev in ("FSDJump", "CarrierJump"):
                system = raw.get("StarSystem") or "Unknown system"
                session["jumps"] += 1
                session["distance_ly"] = round(float(session.get("distance_ly") or 0) + float(raw.get("JumpDist") or 0), 2)
                session["end_system"] = system
                self._highlight(session, raw, "JUMP", f"Arrived in {system}", f"{float(raw.get('JumpDist') or 0):.1f} ly")
            elif ev == "CodexEntry":
                name = raw.get("Name_Localised") or raw.get("Name") or "Codex discovery"
                session["codex"] += 1
                self._highlight(session, raw, "CODEX", name, raw.get("Category_Localised") or "")
            elif ev == "ScanOrganic" and str(raw.get("ScanType") or "").lower() == "analyse":
                name = raw.get("Species_Localised") or raw.get("Species") or raw.get("Genus_Localised") or "Biological analysis"
                session["bio_analyses"] += 1
                self._highlight(session, raw, "BIO", name, raw.get("BodyName") or "")
            elif ev == "Screenshot":
                session["screenshots"] += 1
                detail = raw.get("Body") or raw.get("System") or raw.get("Filename") or ""
                self._highlight(session, raw, "PHOTO", "Screenshot captured", detail)
            elif ev == "MarketBuy":
                session["trade_bought"] += int(raw.get("TotalCost") or 0)
            elif ev == "MarketSell":
                sale = int(raw.get("TotalSale") or 0)
                cost = int(raw.get("AvgPricePaid") or 0) * int(raw.get("Count") or 0)
                session["trade_sold"] += sale
                session["trade_profit"] += sale - cost
            elif ev in ("SellExplorationData", "MultiSellExplorationData"):
                value = int(raw.get("TotalEarnings") or raw.get("TotalSale") or 0)
                session["exploration_sales"] += value
                self._highlight(session, raw, "SALE", "Exploration data sold", f"{value:,} cr")
            elif ev == "SellOrganicData":
                value = int(raw.get("TotalEarnings") or 0)
                if not value:
                    value = sum(int(row.get("Value") or 0) + int(row.get("Bonus") or 0) for row in (raw.get("BioData") or []))
                session["biology_sales"] += value
                self._highlight(session, raw, "SALE", "Biological data sold", f"{value:,} cr")
            elif ev == "Died":
                session["deaths"] += 1
                self._highlight(session, raw, "LOSS", "Ship destroyed")
            elif ev == "Shutdown":
                session["ended"] = _stamp(raw)
                self._highlight(session, raw, "SESSION", "Flight session ended", session.get("end_system") or "")
            elif ev not in ("LoadGame",):
                changed = False

            if save and changed:
                self.save()
            return changed

    def import_journals(self, journal_path):
        if not journal_path or not os.path.isdir(journal_path):
            return 0
        count = 0
        rebuilt = CaptainsLog("")
        files = sorted(
            os.path.join(journal_path, name) for name in os.listdir(journal_path)
            if name.startswith("Journal.") and name.endswith(".log")
        )
        imported = self.data.setdefault("imported_files", {})
        for path in files:
            try:
                signature = f"{os.path.getsize(path)}:{int(os.path.getmtime(path))}"
            except OSError:
                signature = ""
            name = os.path.basename(path)
            if signature and imported.get(name) == signature:
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    for line in handle:
                        try:
                            if rebuilt.process_event(json.loads(line), save=False):
                                count += 1
                        except Exception:
                            continue
            except Exception:
                continue
            if signature:
                imported[name] = signature
                imported[name] = signature
        with self.lock:
            # Parsing happens in an isolated model so live journal callbacks can
            # continue safely while history is imported. Live sessions win when
            # both sources contain the same LoadGame timestamp.
            merged = {
                str(row.get("started") or ""): row
                for row in rebuilt.data.get("sessions") or []
            }
            merged.update({
                str(row.get("started") or ""): row
                for row in self.data.get("sessions") or []
            })
            self.data["sessions"] = sorted(
                merged.values(), key=lambda row: str(row.get("started") or "")
            )[-MAX_SESSIONS:]
            self.data["seen"] = list(dict.fromkeys(
                (rebuilt.data.get("seen") or []) + (self.data.get("seen") or [])
            ))[-6000:]
            self._seen_set = set(self.data["seen"])
            self.data["imported_files"] = dict(list(imported.items())[-400:])
            self.save()
        return count

    @staticmethod
    def markdown(session):
        if not session:
            return ""
        lines = [
            f"# Captain's Log — {session.get('started', '')[:10]}", "",
            f"- Route: {session.get('start_system') or 'Unknown'} → {session.get('end_system') or 'Unknown'}",
            f"- Jumps: {session.get('jumps', 0)} ({float(session.get('distance_ly') or 0):.1f} ly)",
            f"- Discoveries: {session.get('codex', 0)} Codex, {session.get('bio_analyses', 0)} biological analyses",
            f"- Sales: {int(session.get('exploration_sales') or 0):,} cr exploration, {int(session.get('biology_sales') or 0):,} cr biology",
            "", "## Chronicle", "",
        ]
        for row in session.get("highlights") or []:
            suffix = f" — {row.get('detail')}" if row.get("detail") else ""
            lines.append(f"- {row.get('timestamp', '')[11:19]} [{row.get('kind')}] {row.get('title')}{suffix}")
        return "\n".join(lines)
