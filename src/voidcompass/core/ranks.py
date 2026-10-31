"""Elite's rank names, by the journal's rank number (Rank and Promotion events)."""

RANKS = {
    "Combat": ("Harmless", "Mostly Harmless", "Novice", "Competent", "Expert", "Master", "Dangerous", "Deadly", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "Trade": ("Penniless", "Mostly Penniless", "Peddler", "Dealer", "Merchant", "Broker", "Entrepreneur", "Tycoon", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "Explore": ("Aimless", "Mostly Aimless", "Scout", "Surveyor", "Trailblazer", "Pathfinder", "Ranger", "Pioneer", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "CQC": ("Helpless", "Mostly Helpless", "Amateur", "Semi Professional", "Professional", "Champion", "Hero", "Legend", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "Soldier": ("Defenceless", "Mostly Defenceless", "Rookie", "Soldier", "Gunslinger", "Warrior", "Gladiator", "Deadeye", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "Exobiologist": ("Directionless", "Mostly Directionless", "Compiler", "Collector", "Cataloguer", "Taxonomist", "Ecologist", "Geneticist", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "Empire": ("None", "Outsider", "Serf", "Master", "Squire", "Knight", "Lord", "Baron", "Viscount", "Count", "Earl", "Marquis", "Duke", "Prince", "King"),
    "Federation": ("None", "Recruit", "Cadet", "Midshipman", "Petty Officer", "Chief Petty Officer", "Warrant Officer", "Ensign", "Lieutenant", "Lt Commander", "Post Commander", "Post Captain", "Rear Admiral", "Vice Admiral", "Admiral"),
}

# How a rank is said: "Elite, in exploration".
FIELDS = {
    "Combat": "in combat", "Trade": "in trade", "Explore": "in exploration", "CQC": "in CQC",
    "Soldier": "as a mercenary", "Exobiologist": "as an exobiologist",
    "Empire": "in the Imperial Navy", "Federation": "in the Federal Navy",
}


def name(kind, number):
    """The rank's name, or "" for a kind or number the journal doesn't use."""
    names = RANKS.get(str(kind))
    try:
        index = int(number)
    except (TypeError, ValueError):
        return ""
    return names[index] if names and 0 <= index < len(names) else ""


def said(kind, number):
    """"Elite, in exploration", for a promotion."""
    title = name(kind, number)
    return f"{title}, {FIELDS[kind]}" if title and kind in FIELDS else title
