"""Take each game's card picture for the Games page: a screenshot of the
game itself, mid-run, at the card size (1200 x 1350).

    python tools/game_cards.py                 every game
    python tools/game_cards.py rock-rats ...   just these

Each game sets up its own scene for the picture (its cabinet's card hook).
Needs Playwright with Chromium, as the tests do.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAMES = ROOT / "web" / "games"
CARDS = ROOT / "assets" / "gamecards"
# Half the card size, drawn at twice the pixels.
VIEW = {"width": 600, "height": 675}


def game_ids(wanted):
    found = sorted(folder.name for folder in GAMES.iterdir() if (folder / "game.json").is_file())
    return [name for name in found if not wanted or name in wanted]


def main(argv):
    from playwright.sync_api import sync_playwright

    ids = game_ids(set(argv))
    if not ids:
        print("No games found.")
        return 1
    failed = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for game_id in ids:
            manifest = json.loads((GAMES / game_id / "game.json").read_text(encoding="utf-8"))
            entry = GAMES / game_id / (manifest.get("entry") or "index.html")
            context = browser.new_context(viewport=VIEW, device_scale_factor=2)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(entry.as_uri())
            page.wait_for_function("window.cabinet !== undefined", timeout=10000)
            page.evaluate("window.cabinet.card()")
            page.wait_for_timeout(int(manifest.get("card_wait_ms") or 120))
            target = CARDS / f"{game_id}.png"
            page.screenshot(path=str(target))
            context.close()
            if errors:
                failed.append(game_id)
                print(f"{game_id}: {errors[0]}")
            else:
                print(f"{game_id}: {target.relative_to(ROOT)}")
        browser.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
