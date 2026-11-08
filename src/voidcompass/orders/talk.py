"""Crew Orders in TALK (5.7.7): "any orders?", "what are my orders",
"accept the order", "decline it", "later", "cancel the order", "who gave me
this order", "how far is the target", "how's the campaign going".

Every phrase names an order (or errand, or campaign), so a plain "yes" stays
the Watcher's answer to its own questions.
"""

from __future__ import annotations

import re

_THING = r"(?:orders?|errands?|campaign|target|objective)"
INTENTS = (
    ("who", re.compile(rf"\bwho (?:gave|set|issued|sent)(?: me| us)? (?:this|that|the|my|our) {_THING}\b", re.I)),
    ("far", re.compile(rf"\bhow far(?: away)?(?: is| to)?(?: it to)? (?:the|my|our|this) {_THING}\b", re.I)),
    ("progress", re.compile(rf"\bhow(?:'s| is| are) (?:the|my|our|this) {_THING}(?: going| doing| coming along)?\b", re.I)),
    ("accept", re.compile(rf"\b(?:accept|take|i'?ll take|we'?ll take|yes to)(?: the| that| this| your)? {_THING}\b", re.I)),
    ("decline", re.compile(rf"\b(?:decline|refuse|turn down|reject|no to)(?: the| that| this| your)? {_THING}\b", re.I)),
    ("later", re.compile(rf"\b(?:{_THING} (?:for )?later|(?:hold|park|keep|save)(?: the| that| this)? {_THING}(?: for later)?)\b", re.I)),
    ("cancel", re.compile(rf"\b(?:cancel|abandon|drop|scrap|forget)(?: the| that| this| my| our)? {_THING}\b", re.I)),
    ("plot", re.compile(rf"\b(?:plot|copy)(?: the| that| this| my| our)? {_THING}\b", re.I)),
    ("ask", re.compile(r"\b(?:(?:any|got any|have you got any|do you have any|anything for me|new|give me (?:an? )?)\s*(?:orders?|errands?)|"
                       r"anything for me|what should (?:i|we) do (?:next|now))\b", re.I)),
    ("list", re.compile(r"\b(?:what are|what're|list|read(?: me)?|show me)(?: my| our| the)? (?:orders|standing orders)\b|"
                        r"\b(?:my|our) (?:standing )?orders\b", re.I)),
)


def intent(text):
    """The Crew Orders question asked, or None."""
    words = " ".join(str(text or "").split())
    if not words:
        return None
    for name, pattern in INTENTS:
        if pattern.search(words):
            return name
    return None
