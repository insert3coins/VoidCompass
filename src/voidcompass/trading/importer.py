"""Read the commander's whole journal history into the trading record.

Journals already read (same size and time) are skipped, so later starts only
read what is new. Only this commander's play counts (by Frontier ID first).
"""

from __future__ import annotations

import json
import logging
import os

from voidcompass.core.journal_files import list_journals
from voidcompass.exploration.travel_history import commander_matches
from voidcompass.trading.journal import TradeJournal

WANTED = ('"MarketBuy"', '"MarketSell"', '"Docked"', '"Undocked"', '"Location"', '"Market"',
          '"LoadGame"', '"Shutdown"', '"Commander"')


def import_journals(store, journal_path, commander=None, fid=None, should_stop=None):
    """Returns how many journals were read."""
    if not journal_path or not os.path.isdir(journal_path):
        return 0
    reader = TradeJournal()
    read = 0
    files = list_journals(journal_path)
    for index, path in enumerate(files):
        if should_stop and should_stop():
            break
        name = os.path.basename(path)
        try:
            stat = os.stat(path)
        except OSError:
            continue
        signature = (stat.st_size, stat.st_mtime)
        last = index == len(files) - 1
        if not last and store.file_signature(name) == signature:
            continue
        active = not (commander or fid)
        records = []
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if not any(marker in line for marker in WANTED):
                        continue
                    try:
                        raw = json.loads(line)
                    except ValueError:
                        continue
                    if raw.get("event") in ("Commander", "LoadGame"):
                        active = commander_matches(raw, commander, fid)
                    if active:
                        records.extend(reader.observe(raw))
        except OSError as exc:
            logging.info("Trading history: %s skipped (%s)", name, exc)
            continue
        store.apply(records, commit=False)
        store.file_done(name, *signature)
        store.commit()
        read += 1
    return read
