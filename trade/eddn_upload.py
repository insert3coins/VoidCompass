"""Best-effort EDDN commodity publisher for local Market.json snapshots."""

import gzip
import json
import os
import threading
from datetime import datetime, timezone

import requests

from version import APP_VERSION

UPLOAD_URL = "https://eddn.edcd.io:4430/upload/"
SCHEMA = "https://eddn.edcd.io/schemas/commodity/3"
SOFTWARE_NAME = "VoidCompass"
MAX_AGE_S = 120


def _symbol(raw):
    text = str(raw or "").strip()
    if not text:
        return ""
    if text.startswith("$") and text.endswith(";"):
        text = text[1:-1]
    lower = text.lower()
    for suffix in ("_name", "_name_localised"):
        if lower.endswith(suffix):
            lower = lower[: -len(suffix)]
            break
    return lower


def _epoch(value):
    if not value:
        return None
    text = str(value).strip().replace(" ", "T").replace("Z", "+00:00")
    if text.endswith("+00"):
        text += ":00"
    try:
        return int(datetime.fromisoformat(text).timestamp())
    except (TypeError, ValueError):
        return None


def _now_epoch():
    return int(datetime.now(timezone.utc).timestamp())


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_int(value, default=0):
    try:
        if value == "":
            return value
        return int(value)
    except Exception:
        return default


def _clean_bool(value):
    if isinstance(value, bool):
        return value
    return None


class EddnUploader:
    def __init__(self):
        self._lock = threading.Lock()
        self._last_key = None
        self.enabled = os.environ.get("VC_EDDN_UPLOAD", "1") != "0"
        self.uploads = 0
        self.last_upload_at = None
        self.last_error = None
        self._log_callback = None

    def set_enabled(self, enabled):
        with self._lock:
            self.enabled = bool(enabled)

    def set_log_callback(self, callback):
        with self._lock:
            self._log_callback = callback

    def stats(self):
        with self._lock:
            return {
                "enabled": self.enabled,
                "uploads": self.uploads,
                "last_upload_at": self.last_upload_at,
                "last_error": self.last_error,
            }

    def _emit(self, message, severity="INFO"):
        with self._lock:
            callback = self._log_callback
        if callback:
            try:
                callback("EDDN", message, severity)
            except Exception:
                pass

    def maybe_publish(self, market, commander, context=None):
        with self._lock:
            enabled = self.enabled
        if not enabled or not isinstance(market, dict):
            return
        market_id = market.get("MarketID")
        timestamp = market.get("timestamp")
        if not market_id or not timestamp or "Items" not in market:
            return
        updated = _epoch(timestamp)
        if not updated or _now_epoch() - updated > MAX_AGE_S:
            return
        key = (market_id, timestamp)
        with self._lock:
            if key == self._last_key:
                return
            self._last_key = key
        threading.Thread(target=self._publish, args=(market, commander, context or {}), name="eddn-upload", daemon=True).start()

    def _publish(self, market, commander, context=None):
        context = context or {}
        commodities = []
        for item in market.get("Items") or []:
            name = _symbol(item.get("Name"))
            if not name:
                continue
            # Match EDMC/EDDN conventions: station-illegal goods and
            # non-marketable items (limpets etc.) must not be published.
            if str(item.get("Legality") or "").strip():
                continue
            category = str(item.get("Category") or "").lower()
            if "nonmarketable" in category or name.lower() == "drones":
                continue
            commodity = {
                "name": name,
                "meanPrice": _clean_int(item.get("MeanPrice", 0)),
                "buyPrice": _clean_int(item.get("BuyPrice", 0)),
                "stock": _clean_int(item.get("Stock", 0)),
                "stockBracket": _clean_int(item.get("StockBracket", 0)),
                "sellPrice": _clean_int(item.get("SellPrice", 0)),
                "demand": _clean_int(item.get("Demand", 0)),
                "demandBracket": _clean_int(item.get("DemandBracket", 0)),
            }
            flags = item.get("StatusFlags")
            if isinstance(flags, list):
                clean_flags = [str(flag) for flag in flags if str(flag or "").strip()]
                if clean_flags:
                    commodity["statusFlags"] = clean_flags
            commodities.append(commodity)
        commodities.sort(key=lambda item: item["name"])
        header = {
            "uploaderID": commander or "unknown",
            "softwareName": SOFTWARE_NAME,
            "softwareVersion": APP_VERSION,
            "gameversion": str(context.get("gameversion") or ""),
            "gamebuild": str(context.get("gamebuild") or ""),
        }
        message = {
            "systemName": market.get("StarSystem"),
            "stationName": market.get("StationName"),
            "marketId": market.get("MarketID"),
            "timestamp": market.get("timestamp"),
            "commodities": commodities,
        }
        station_type = market.get("StationType") or context.get("station_type")
        if station_type:
            message["stationType"] = str(station_type)
        carrier_access = market.get("CarrierDockingAccess") or context.get("carrier_docking_access")
        if carrier_access:
            message["carrierDockingAccess"] = str(carrier_access)
        for key in ("horizons", "odyssey"):
            value = _clean_bool(market.get(key.capitalize()))
            if value is None:
                value = _clean_bool(context.get(key))
            if value is not None:
                message[key] = value
        envelope = {
            "$schemaRef": SCHEMA,
            "header": header,
            "message": message,
        }
        try:
            body = gzip.compress(json.dumps(envelope).encode("utf-8"))
            resp = requests.post(
                UPLOAD_URL,
                data=body,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Content-Encoding": "gzip",
                    "User-Agent": f"{SOFTWARE_NAME}/{APP_VERSION}",
                },
                timeout=20,
            )
            with self._lock:
                if resp.status_code == 200:
                    self.uploads += 1
                    self.last_upload_at = _utc_now_iso()
                    self.last_error = None
                    error = None
                else:
                    self.last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
                    error = self.last_error
            station = market.get("StationName") or "unknown station"
            system = market.get("StarSystem") or "unknown system"
            if error:
                self._emit(f"Upload failed: {error}", "WARN")
            else:
                self._emit(f"Uploaded market data: {station} / {system}", "INFO")
        except requests.RequestException as exc:
            with self._lock:
                self.last_error = str(exc)[:200]
                error = self.last_error
            self._emit(f"Upload failed: {error}", "WARN")


UPLOADER = EddnUploader()
