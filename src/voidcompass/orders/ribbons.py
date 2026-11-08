"""Commendations for Crew Orders (5.7.7): what each ribbon is for, and
which ones the ledger's record has earned."""

from voidcompass.orders.ledger import SPEAKERS

# Each ribbon: its name, and what it's for.
RIBBONS = {
    "first_order": ("First Orders", "Finished your first order"),
    "whole_crew": ("Whole Crew", "Finished an order for each of the five"),
    "ten_orders": ("Ten Orders", "Finished ten orders"),
    "fifty_orders": ("Fifty Orders", "Finished fifty orders"),
    "errand_runner": ("Errand Runner", "Did five errands for the Watcher"),
    "every_colour": ("Every Colour", "Finished the Every Colour campaign"),
    "long_haul": ("The Long Haul", "Finished the Long Haul"),
    "clean_sheet": ("A Clean Sheet", "Surveyed a region properly"),
    "the_ledger": ("The Ledger", "Balanced the books"),
    "first_light": ("First Light", "A whole system of firsts"),
    "home": ("Home", "Took the Watcher home"),
    "the_fork": ("The Fork", "Settled an argument on the bridge"),
    "right_hand_watcher": ("The Watcher's Right Hand", "Right hand standing with the Watcher"),
    "right_hand_aster": ("Aster's Right Hand", "Right hand standing with Aster"),
    "right_hand_axiom": ("Axiom's Right Hand", "Right hand standing with Axiom"),
    "right_hand_meridian": ("Meridian's Right Hand", "Right hand standing with Meridian"),
    "right_hand_lyra": ("Lyra's Right Hand", "Right hand standing with Lyra"),
}


def earned(data):
    """Every ribbon the record has earned so far."""
    history = [row for row in data.get("history") or () if row.get("status") == "done"]
    record = data.get("record") or {}
    ids = set()
    if history:
        ids.add("first_order")
    if all(int((record.get(name) or {}).get("done") or 0) > 0 for name in SPEAKERS):
        ids.add("whole_crew")
    if len(history) >= 10:
        ids.add("ten_orders")
    if len(history) >= 50:
        ids.add("fifty_orders")
    if sum(1 for row in history if row.get("kind") == "errand") >= 5:
        ids.add("errand_runner")
    for row in history:
        if row.get("size") == "campaign" and row.get("campaign") in RIBBONS:
            ids.add(row["campaign"])
    for name in SPEAKERS:
        if int((record.get(name) or {}).get("done") or 0) >= 15:
            ids.add(f"right_hand_{name}")
    return ids


# Postcard themes that commendations unlock (5.7.7): name, then the theme's
# parameters (postcard_themes.normalize). They join your own themes when the
# ribbon is earned, and are yours to change or delete like any other.
POSTCARD_THEMES = {
    "every_colour": ("Every Colour", {"base": "holo", "paper": "#10162a", "ink": "#e9f2ff", "greet": "#9df2c4",
                                      "font": "serif", "filter": "vivid"}),
    "long_haul": ("The Long Haul", {"base": "vintage", "paper": "#f1e3c4", "ink": "#3a2a14", "greet": "#8a5a1c",
                                    "font": "serif", "filter": "sepia", "angle": -3}),
    "clean_sheet": ("A Clean Sheet", {"base": "airmail", "paper": "#f6f8fb", "ink": "#1b2a3a", "greet": "#2c6fb3",
                                      "font": "hud", "filter": "cool"}),
    "the_ledger": ("The Ledger", {"base": "vintage", "paper": "#efe6d2", "ink": "#2b2b2b", "greet": "#7a5c12",
                                  "font": "hand"}),
    "first_light": ("First Light", {"base": "holo", "paper": "#0b0f14", "ink": "#ffffff", "greet": "#ffd166",
                                    "font": "hud", "filter": "vivid", "background": "colour", "bg_colour": "#05070a"}),
    "home": ("Home", {"base": "polaroid", "paper": "#fbf8f0", "ink": "#2a2a2a", "greet": "#b04a3a", "font": "hand",
                      "angle": 2}),
    "the_fork": ("The Fork", {"base": "airmail", "paper": "#fff7ea", "ink": "#23324a", "greet": "#3fbf8f", "font": "serif"}),
    "whole_crew": ("Whole Crew", {"base": "polaroid", "paper": "#121a22", "ink": "#dce8ef", "greet": "#00d1ff",
                                  "font": "hud", "filter": "cool"}),
    "right_hand_watcher": ("The Watcher's Hand", {"base": "holo", "paper": "#120a0b", "ink": "#f2dcdc", "greet": "#e0574f",
                                                  "font": "serif", "filter": "mono"}),
    "right_hand_aster": ("Aster's Hand", {"base": "vintage", "paper": "#f3ead6", "ink": "#2a2418", "greet": "#b8862b",
                                          "font": "serif"}),
    "right_hand_axiom": ("Axiom's Hand", {"base": "airmail", "paper": "#f4f5ff", "ink": "#1f2346", "greet": "#5f6cff",
                                          "font": "hud", "filter": "cool"}),
    "right_hand_meridian": ("Meridian's Hand", {"base": "vintage", "paper": "#ece2c8", "ink": "#22301f", "greet": "#2f8f68",
                                                "font": "serif", "filter": "sepia"}),
    "right_hand_lyra": ("Lyra's Hand", {"base": "holo", "paper": "#0d1420", "ink": "#eef8ff", "greet": "#74ddff",
                                        "font": "hud", "filter": "vivid"}),
}
