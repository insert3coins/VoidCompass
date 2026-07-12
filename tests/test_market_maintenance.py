import pathlib
import sys
import tempfile
import time


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trade import marketdb, seed  # noqa: E402


def _insert_market(conn, system_id, system_name, market_id, station_name, updated, price):
    conn.execute(
        "INSERT OR REPLACE INTO systems(id64, name, x, y, z) VALUES(?, ?, 0, 0, 0)",
        (system_id, system_name),
    )
    conn.execute(
        "INSERT OR REPLACE INTO stations"
        "(market_id, system_id64, name, type, dist_ls, large_pad, updated_at)"
        " VALUES(?, ?, ?, 'Coriolis Starport', 10, 1, ?)",
        (market_id, system_id, station_name, updated),
    )
    conn.execute(
        "INSERT OR REPLACE INTO commodities"
        "(market_id, symbol, buy_price, sell_price, supply, demand)"
        " VALUES(?, 'gold', ?, ?, 100, 100)",
        (market_id, price, price + 10),
    )
    conn.execute(
        "INSERT OR REPLACE INTO commodity_names(symbol, name, category)"
        " VALUES('gold', 'Gold', 'Metals')"
    )
    conn.commit()


def test_full_rebuild_preserves_newer_live_markets():
    original_db_path = marketdb.DB_PATH
    original_build_path = seed.BUILD_DB_PATH
    original_status_cache = marketdb._status_cache
    try:
        with tempfile.TemporaryDirectory() as folder:
            folder = pathlib.Path(folder)
            live_path = folder / "market.db"
            build_path = folder / "market_build.db"
            live = marketdb.connect(live_path)
            build = marketdb.connect(build_path)
            try:
                _insert_market(build, 1, "Sol", 100, "Galileo", 100, 1000)
                _insert_market(live, 1, "Sol", 100, "Galileo", 200, 2000)
                _insert_market(live, 2, "New System", 200, "New Port", 300, 3000)
                live.execute(
                    "INSERT INTO watches(created, payload) VALUES('now', '{}')"
                )
                marketdb.set_meta(live, "journal_market_updated_at", "2026-07-13T12:00:00Z")
                live.commit()
            finally:
                live.close()
                build.close()

            marketdb.DB_PATH = live_path
            seed.BUILD_DB_PATH = build_path
            seed.Seeder()._preserve_user_tables()

            merged = marketdb.connect(build_path)
            try:
                station = merged.execute(
                    "SELECT updated_at FROM stations WHERE market_id=100"
                ).fetchone()
                price = merged.execute(
                    "SELECT buy_price FROM commodities WHERE market_id=100 AND symbol='gold'"
                ).fetchone()
                new_system = merged.execute(
                    "SELECT name FROM systems WHERE id64=2"
                ).fetchone()
                new_station = merged.execute(
                    "SELECT name FROM stations WHERE market_id=200"
                ).fetchone()
                assert station == (200,)
                assert price == (2000,)
                assert new_system == ("New System",)
                assert new_station == ("New Port",)
                assert merged.execute("SELECT COUNT(*) FROM watches").fetchone() == (1,)
                assert marketdb.get_meta(merged, "journal_market_updated_at") == "2026-07-13T12:00:00Z"
                assert marketdb.get_meta(merged, "live_markets_preserved") == "2"

                now = int(time.time())
                merged.execute("UPDATE stations SET updated_at=? WHERE market_id=100", (now,))
                merged.commit()
                marketdb._status_cache = None
                status = marketdb.status(merged, force=True)
                assert status["latest_market_updated_at"]
                assert status["fresh_markets_1d"] == 1
                assert status["stale_markets_30d"] == 1
                assert status["live_markets_preserved"] == 2
            finally:
                merged.close()
    finally:
        marketdb.DB_PATH = original_db_path
        seed.BUILD_DB_PATH = original_build_path
        marketdb._status_cache = original_status_cache


if __name__ == "__main__":
    test_full_rebuild_preserves_newer_live_markets()
    print("ALL MARKET MAINTENANCE TESTS PASSED")
