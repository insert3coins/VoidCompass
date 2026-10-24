Game card pictures for the Games page.

Each card is a screenshot of the game itself, mid-run, taken by:

    python tools/game_cards.py              every game
    python tools/game_cards.py rock-rats    just one

Each game stages its own scene for it (the card hook in its game.js), and
the picture lands here named after the game's folder in web/games, for
example thargoid-swarm.png.

Size: 1200 x 1350 (8:9, an arcade screen's shape). Retake a game's picture
whenever its look changes. A game without a picture gets a drawn placeholder.
