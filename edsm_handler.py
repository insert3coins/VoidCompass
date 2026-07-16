import json
import os
import threading
import requests
import logging
import re
import html
import time
from version import APP_VERSION

_EDSM_CREDIT_EVENTS = frozenset({
    "BuyExplorationData", "BuyMicroResources", "BuyTradeData",
    "CancelTaxi", "CommunityGoalReward", "CrewHire",
    "EngineerContribution", "FetchRemoteModule", "LoadGame",
    "MarketBuy", "MarketSell", "MissionAbandoned", "MissionCompleted",
    "MissionFailed", "ModuleBuy", "ModuleBuyAndStore", "ModuleRetrieve",
    "ModuleSell", "ModuleSellRemote", "ModuleTransfer", "NpcCrewPaidWage",
    "PayBounties", "PayFines", "PayLegacyFines", "PowerplaySalary",
    "RedeemVoucher", "RefuelAll", "RefuelPartial", "Repair", "RepairAll",
    "RestockVehicle", "Resurrect", "SearchAndRescue", "SellDrones",
    "SellExplorationData", "SellMicroResources", "SellShipOnRebuy",
    "MultiSellExplorationData",
    "ShipyardBuy", "ShipyardSell", "ShipyardTransfer",
})

# Events EDSM discards — matches the list served by api-journal-v1/discard.
# Keeping these client-side avoids sending noise and saves round-trips.
_EDSM_DISCARD_EVENTS = frozenset({
    "AfmuRepairs", "AppliedToSquadron", "ApproachBody",
    "AsteroidCracked", "BookDropship", "CancelDropship",
    "CapShipBond", "CargoTransfer", "CarrierBankTransfer",
    "CarrierBuy", "CarrierCrewServices", "CarrierDecommission",
    "CarrierDepositFuel", "CarrierDockingPermission", "CarrierFinance",
    "CarrierJumpCancelled", "CarrierJumpRequest", "CarrierModulePack",
    "CarrierNameChange", "CarrierStats", "CarrierTradeOrder",
    "ChangeCrewRole", "ClearSavedGame", "CockpitBreached",
    "CollectItems", "ColonisationConstructionDepot",
    "ColonisationContribution", "Commander", "Continued", "Coriolis",
    "CreateSuitLoadout", "CrewLaunchFighter", "CrewMemberJoins",
    "CrewMemberQuits", "CrewMemberRoleChange", "DataScanned",
    "DatalinkScan", "DatalinkVoucher", "DisbandedSquadron",
    "DiscoveryScan", "Disembark", "DockFighter", "DockSRV",
    "DropItems", "DropshipDeploy", "EDDCommodityPrices", "EDDItemSet",
    "EDShipyard", "Embark", "EndCrewSession", "EngineerApply",
    "EngineerLegacyConvert", "EscapeInterdiction", "FSSBodySignals",
    "FSSSignalDiscovered", "FactionKillBond", "FighterDestroyed",
    "FighterRebuilt", "FileHeader", "Fileheader", "FuelScoop",
    "HeatDamage", "HeatWarning", "HullDamage", "InvitedToSquadron",
    "JetConeBoost", "JetConeDamage", "JoinedSquadron",
    "KickCrewMember", "LaunchDrone", "LaunchFighter", "LaunchSRV",
    "LeaveBody", "LoadoutEquipModule", "MassModuleStore",
    "MaterialDiscovered", "ModuleArrived", "ModuleInfo",
    "NavBeaconScan", "NewCommander", "PVPKill", "PowerplayMerits",
    "ProspectedAsteroid", "RebootRepair", "RepairDrone",
    "ReservoirReplenished", "SAASignalsFound", "SRVDestroyed",
    "ScanBaryCentre", "ScanOrganic", "Scanned",
    "SharedBookmarkToSquadron", "ShieldState", "ShipArrived",
    "ShipTargeted", "SquadronCreated", "SquadronStartup",
    "StartJump", "SuitLoadout", "SupercruiseDestinationDrop",
    "SupercruiseEntry", "SupercruiseExit", "SwitchSuitLoadout",
    "ShutDown", "Shutdown",
    "Music", "Screenshot",
    "ReceiveText", "SendText",
    "DockingRequested", "DockingGranted", "DockingDenied",
    "DockingCancelled", "DockingTimeout",
    "Market", "Shipyard", "Outfitting",
    "StoredModules", "StoredShips",
    "ModuleBuy", "ModuleSell", "ModuleRetrieve", "ModuleStore",
    "ModuleSwap", "ModuleTransfer",
    "ShipyardBuy", "ShipyardNew", "ShipyardSell", "ShipyardSwap", "ShipyardTransfer",
    "Bounty", "RedeemVoucher", "CrimeVictim",
    "PowerplayCollect", "PowerplayDeliver", "PowerplayDefect", "PowerplayEnlist",
    "PowerplayFastTrack", "PowerplayJoin", "PowerplayLeave", "PowerplaySalary",
    "PowerplayVote", "PowerplayVoucher",
    "NpcCrewRank", "NpcCrewPaidWage", "CrewAssign", "CrewFire", "CrewHire",
    "Passengers", "PassengerManifest",
    "MissionAccepted", "MissionCompleted", "MissionFailed",
    "MissionAbandoned", "MissionRedirected",
    "CargoTransfer",
    "NavRoute", "NavRouteClear",
    "Status",
    "Mining_Refined", "Cargo", "EjectCargo",
}) - _EDSM_CREDIT_EVENTS

_BATCH_SIZE = 50          # send when queue reaches this many events
_FLUSH_INTERVAL_S = 5     # flush this many seconds after the last queued event
_RETRY_DELAYS = [30, 60, 120, 300]  # backoff (seconds) after consecutive send failures


class EDSMHandler:
    def __init__(self, config):
        self.config = config
        self.status = "ACTIVE"
        self._http_limiter = threading.BoundedSemaphore(6)
        self._session = requests.Session()

        self._queue_lock = threading.Lock()
        self._flush_timer = None
        self._retry_count = 0
        self._profile_generation = 0
        self._log_callback = None
        self._db_conn = None
        self._db_lock = None
        self._game_version = self.config.get("edsm_game_version", "")
        self._game_build = self.config.get("edsm_game_build", "")
        self._missing_game_version_warned = False

    def set_log_callback(self, callback):
        """Wire up a function(tag, msg, severity) to post feed entries on upload."""
        self._log_callback = callback

    def set_db(self, conn, lock):
        """Wire up the shared DB connection. Call this after init_db()."""
        self._db_conn = conn
        self._db_lock = lock
        with self._db_lock:
            count = self._db_conn.execute("SELECT COUNT(*) FROM edsm_queue").fetchone()[0]
        if count > 0:
            logging.info(f"EDSM: {count} unsent event(s) found from last session")
            if self._log_callback:
                self._log_callback("EDSM", f"Recovered {count} unsent event(s) from last session", "WARN")
            self._arm_flush(immediate=True)

    def prepare_profile_switch(self):
        """Invalidate queued background work before the outgoing DB is closed."""
        with self._queue_lock:
            self._profile_generation += 1
            if self._flush_timer is not None:
                try:
                    self._flush_timer.cancel()
                except Exception:
                    pass
                self._flush_timer = None
            self._retry_count = 0

    def switch_profile(self, config, conn, lock):
        """Move uploads and cached credentials to a new commander database."""
        self.prepare_profile_switch()
        self.config = config
        self._game_version = str(config.get("edsm_game_version") or "")
        self._game_build = str(config.get("edsm_game_build") or "")
        self._missing_game_version_warned = False
        self.set_db(conn, lock)

    def set_game_version(self, game_version, game_build):
        """Record the live Elite game version/build required by EDSM uploads."""
        if game_version:
            self._game_version = str(game_version)
            self.config["edsm_game_version"] = self._game_version
        if game_build:
            self._game_build = str(game_build)
            self.config["edsm_game_build"] = self._game_build
        if self._game_version and self._game_build:
            self._missing_game_version_warned = False

    def is_credit_event(self, event_name):
        return event_name in _EDSM_CREDIT_EVENTS

    # ------------------------------------------------------------------
    # Upload queue helpers
    # ------------------------------------------------------------------

    def queue_journal_event(self, raw_event, system_name=None, system_coords=None, system_address=None):
        """Persist a journal event to the DB queue for upload to EDSM."""
        if not self._db_conn:
            return
        if not self.config.get("edsm_upload_enabled"):
            return
        if not self.config.get("edsm_cmdr_name", "").strip():
            return
        if not self.config.get("edsm_api_key", "").strip():
            return
        if not self._game_version or not self._game_build:
            if self._log_callback and not self._missing_game_version_warned:
                self._missing_game_version_warned = True
                self._log_callback("EDSM", "Upload skipped: game version/build not detected yet", "WARN")
            return

        ev_name = raw_event.get("event", "")
        if ev_name in _EDSM_DISCARD_EVENTS:
            return

        if ev_name in ("FSDJump", "Location", "CarrierJump"):
            system_name = raw_event.get("StarSystem") or system_name
            system_coords = raw_event.get("StarPos") or system_coords
            system_address = raw_event.get("SystemAddress") or system_address

        enriched = dict(raw_event)
        if system_name:
            enriched["_systemName"] = system_name
        if system_address is not None:
            enriched["_systemAddress"] = system_address
        if system_coords:
            enriched["_systemCoordinates"] = system_coords

        try:
            with self._db_lock:
                self._db_conn.execute(
                    "INSERT INTO edsm_queue (queued_ts, event_json) VALUES (?, ?)",
                    (time.time(), json.dumps(enriched)),
                )
                self._db_conn.commit()
        except Exception as e:
            logging.warning(f"EDSM: failed to queue event: {e}")
            return

        self._arm_flush()

    def flush_upload_queue(self):
        """Force an immediate flush — call this on system jumps."""
        self._arm_flush(immediate=True)

    def _arm_flush(self, immediate=False, delay=None, expected_generation=None):
        with self._queue_lock:
            if expected_generation is not None and expected_generation != self._profile_generation:
                return
            if self._flush_timer is not None:
                if not immediate and delay is None:
                    return  # existing timer is fine
                self._flush_timer.cancel()
                self._flush_timer = None
            if delay is None:
                delay = 0 if immediate else _FLUSH_INTERVAL_S
            t = threading.Timer(delay, self._do_flush)
            t.daemon = True
            self._flush_timer = t
        t.start()

    # ------------------------------------------------------------------
    # Historical backfill
    # ------------------------------------------------------------------

    def run_backfill(self, journal_path):
        """Queue all unprocessed historical journal events. Runs in background."""
        if not self._db_conn:
            return
        if not self.config.get("edsm_upload_enabled"):
            return
        if not self.config.get("edsm_cmdr_name", "").strip():
            return
        if not self.config.get("edsm_api_key", "").strip():
            return
        with self._queue_lock:
            generation = self._profile_generation
            db_conn = self._db_conn
            db_lock = self._db_lock
        threading.Thread(
            target=self._do_backfill,
            args=(journal_path, generation, db_conn, db_lock),
            daemon=True,
        ).start()

    def _do_backfill(self, journal_path, generation, db_conn, db_lock):
        try:
            if not journal_path or not os.path.exists(journal_path):
                return

            all_files = sorted(
                f for f in os.listdir(journal_path)
                if f.startswith("Journal.") and f.endswith(".log")
            )
            if not all_files:
                return

            # The most recently modified file is the active one — the live watcher handles it.
            current = max(all_files, key=lambda f: os.path.getmtime(os.path.join(journal_path, f)))

            if generation != self._profile_generation:
                return
            with db_lock:
                done = {r[0] for r in db_conn.execute("SELECT journal_file FROM edsm_backfill").fetchall()}

            to_process = [f for f in all_files if f != current and f not in done]
            if not to_process:
                return

            logging.info(f"EDSM backfill: {len(to_process)} journal file(s) to process")
            total = 0
            for filename in to_process:
                if generation != self._profile_generation:
                    return
                total += self._backfill_file(
                    os.path.join(journal_path, filename), filename,
                    generation, db_conn, db_lock,
                )

            if total > 0:
                if self._log_callback:
                    self._log_callback("EDSM", f"Backfilled {total} historical event(s) — uploading", "INFO")
                self._arm_flush(immediate=True, expected_generation=generation)
        except Exception as e:
            logging.warning(f"EDSM backfill error: {e}")

    def _backfill_file(self, filepath, filename, generation, db_conn, db_lock):
        """Read one journal file, insert relevant events into edsm_queue. Returns count queued."""
        count = 0
        system_name = None
        system_coords = None
        system_address = None
        batch = []

        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw = json.loads(line)
                    except Exception:
                        continue

                    ev = raw.get("event", "")
                    if not ev:
                        continue

                    # Mirror queue_journal_event: jump events carry their own system context.
                    if ev in ("FSDJump", "Location", "CarrierJump"):
                        system_name = raw.get("StarSystem") or system_name
                        system_coords = raw.get("StarPos") or system_coords
                        system_address = raw.get("SystemAddress") or system_address

                    if ev in _EDSM_DISCARD_EVENTS:
                        continue

                    enriched = dict(raw)
                    if system_name:
                        enriched["_systemName"] = system_name
                    if system_address is not None:
                        enriched["_systemAddress"] = system_address
                    if system_coords:
                        enriched["_systemCoordinates"] = system_coords

                    batch.append((time.time(), json.dumps(enriched)))
                    count += 1

                    if len(batch) >= 200:
                        if generation != self._profile_generation:
                            return count
                        with db_lock:
                            db_conn.executemany(
                                "INSERT INTO edsm_queue (queued_ts, event_json) VALUES (?, ?)", batch
                            )
                            db_conn.commit()
                        batch = []

            if batch:
                if generation != self._profile_generation:
                    return count
                with db_lock:
                    db_conn.executemany(
                        "INSERT INTO edsm_queue (queued_ts, event_json) VALUES (?, ?)", batch
                    )
                    db_conn.commit()

            if generation != self._profile_generation:
                return count
            with db_lock:
                db_conn.execute(
                    "INSERT OR REPLACE INTO edsm_backfill (journal_file, backfilled_ts) VALUES (?, ?)",
                    (filename, time.time()),
                )
                db_conn.commit()

        except Exception as e:
            logging.warning(f"EDSM: failed to backfill {filename}: {e}")
            count = 0

        return count

    # ------------------------------------------------------------------

    def _do_flush(self):
        with self._queue_lock:
            self._flush_timer = None
            generation = self._profile_generation
            db_conn = self._db_conn
            db_lock = self._db_lock

        if not db_conn:
            return

        try:
            with db_lock:
                rows = db_conn.execute(
                    "SELECT id, event_json FROM edsm_queue ORDER BY id ASC LIMIT ?",
                    (_BATCH_SIZE,),
                ).fetchall()
        except Exception as e:
            logging.warning(f"EDSM: DB read failed: {e}")
            return

        if not rows:
            return

        ids = [r[0] for r in rows]
        try:
            batch = [json.loads(r[1]) for r in rows]
        except Exception as e:
            logging.warning(f"EDSM: failed to parse queued events: {e}")
            return

        cmdr = self.config.get("edsm_cmdr_name", "").strip()
        key = self.config.get("edsm_api_key", "").strip()
        game_version = self._game_version
        game_build = self._game_build

        if not cmdr or not key or not game_version or not game_build:
            self._arm_flush()
            return

        def _send():
            try:
                payload = {
                    "commanderName": cmdr,
                    "apiKey": key,
                    "fromSoftware": "VoidCompass",
                    "fromSoftwareVersion": APP_VERSION,
                    "fromGameVersion": game_version,
                    "fromGameBuild": game_build,
                    "message": batch,
                }
                with self._http_limiter:
                    headers = {"User-Agent": f"VoidCompass/{APP_VERSION}"}
                    r = self._session.post(
                        "https://www.edsm.net/api-journal-v1",
                        json=payload,
                        headers=headers,
                        timeout=20,
                    )
                    r.raise_for_status()
                    try:
                        resp = r.json()
                    except Exception:
                        resp = {}
                    msgnum = resp.get("msgnum", 100)
                    msg = resp.get("msg", "OK")
                    if generation != self._profile_generation:
                        return
                    if msgnum >= 200:
                        # Credential/cmdr error — drop the batch, don't retry.
                        logging.warning(f"EDSM rejected batch [{msgnum}]: {msg}")
                        with db_lock:
                            db_conn.execute(
                                f"DELETE FROM edsm_queue WHERE id IN ({','.join('?'*len(ids))})", ids
                            )
                            db_conn.commit()
                        if self._log_callback:
                            self._log_callback("EDSM", f"Upload rejected [{msgnum}]: {msg}", "ERROR")
                    else:
                        self._retry_count = 0
                        with db_lock:
                            db_conn.execute(
                                f"DELETE FROM edsm_queue WHERE id IN ({','.join('?'*len(ids))})", ids
                            )
                            remaining = db_conn.execute("SELECT COUNT(*) FROM edsm_queue").fetchone()[0]
                            db_conn.commit()
                        logging.debug(f"EDSM upload OK: {len(batch)} events")
                        if self._log_callback:
                            self._log_callback("EDSM", f"Uploaded {len(batch)} event(s) to EDSM", "INFO")
                        if remaining > 0:
                            self._arm_flush(immediate=True, expected_generation=generation)
            except Exception as e:
                # Network/HTTP error — rows stay in DB, retry with backoff.
                if generation != self._profile_generation:
                    return
                logging.warning(f"EDSM batch upload failed ({len(batch)} events): {e}")
                retry_delay = _RETRY_DELAYS[min(self._retry_count, len(_RETRY_DELAYS) - 1)]
                self._retry_count += 1
                if self._log_callback:
                    self._log_callback("EDSM", f"Upload failed, retrying in {retry_delay}s", "WARN")
                self._arm_flush(delay=retry_delay, expected_generation=generation)

        threading.Thread(target=_send, daemon=True).start()

    # ------------------------------------------------------------------
    # Read-only EDSM / Spansh fetch helpers (unchanged)
    # ------------------------------------------------------------------

    def _limited_get(self, url, params=None, timeout=10, retries=2):
        last_exc = None
        for attempt in range(retries + 1):
            with self._http_limiter:
                try:
                    headers = {'User-Agent': f'VoidCompass/{APP_VERSION}'}
                    r = self._session.get(url, params=params, headers=headers, timeout=timeout)
                    r.raise_for_status()
                    return r
                except Exception as e:
                    last_exc = e
            if attempt < retries:
                time.sleep(0.25 * (attempt + 1))
        raise last_exc

    def fetch_traffic(self, system_name, callback):
        def _fetch():
            result = None
            try:
                params = {'systemName': system_name}
                url = "https://www.edsm.net/api-system-v1/traffic"
                r = self._limited_get(url, params=params, timeout=10, retries=1)
                data = r.json()
                if isinstance(data, dict):
                    traffic = data.get("traffic") or {}
                    result = {
                        "day": int(traffic.get("day") or 0),
                        "week": int(traffic.get("week") or 0),
                        "total": int(traffic.get("total") or 0),
                    }
            except Exception as e:
                logging.warning(f"Traffic fetch failed: {e}")
            callback(result)
        threading.Thread(target=_fetch, daemon=True).start()

    def fetch_system_coords(self, system_name, callback):
        def _fetch():
            try:
                params = {'systemName': system_name, 'showCoordinates': 1}
                url = "https://www.edsm.net/api-v1/system"
                r = self._limited_get(url, params=params, timeout=12, retries=2)
                data = r.json()
                if isinstance(data, dict) and "coords" in data:
                    callback(data.get("name", system_name), data["coords"])
                else:
                    callback(system_name, None)
            except Exception as e:
                logging.warning(f"Coords fetch failed: {e}")
                callback(system_name, None)
        threading.Thread(target=_fetch, daemon=True).start()

    def fetch_system_details(self, system_name, callback):
        def _fetch():
            try:
                params = {'systemName': system_name, 'showInformation': 1, 'showPrimaryStar': 1}
                url = "https://www.edsm.net/api-v1/system"
                r = self._limited_get(url, params=params, timeout=12, retries=2)
                data = r.json()
                if isinstance(data, dict) and "name" in data:
                    callback(data)
                else:
                    callback(None)
            except Exception as e:
                logging.warning(f"System details fetch failed: {e}")
                callback(None)
        threading.Thread(target=_fetch, daemon=True).start()

    def fetch_spansh_system(self, system_address, callback):
        def _fetch():
            try:
                url = f"https://spansh.co.uk/api/dump/{system_address}/"
                r = self._limited_get(url, timeout=15, retries=1)
                data = r.json()
                callback(data if isinstance(data, dict) else None)
            except Exception as e:
                logging.warning(f"Spansh system dump failed: {e}")
                callback(None)
        threading.Thread(target=_fetch, daemon=True).start()

    def fetch_system_blurb(self, system_name, callback):
        def _fetch():
            try:
                params = {"systemName": system_name}
                url = "https://www.edsm.net/en/system"
                r = self._limited_get(url, params=params, timeout=15, retries=2)
                text = r.text

                match = re.search(
                    r"Galactic Mapping Project entry.*?<div class=\"card-body\">(.*?)</div>",
                    text,
                    re.S | re.I
                )
                if not match:
                    callback(None)
                    return

                block = match.group(1)
                paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", block, re.S | re.I)
                cleaned = []
                for p in paragraphs:
                    p = re.sub(r"<[^>]+>", "", p)
                    p = html.unescape(p).strip()
                    if p:
                        cleaned.append(p)
                if not cleaned:
                    callback(None)
                    return

                blurb = " ".join(cleaned[:2]).strip()
                if len(blurb) > 420:
                    blurb = blurb[:417].rstrip() + "..."
                callback(blurb or None)
            except Exception as e:
                logging.warning(f"System blurb fetch failed: {e}")
                callback(None)

        threading.Thread(target=_fetch, daemon=True).start()
