"""Curated, safety-bounded personas for deterministic Compass speech."""

from __future__ import annotations

import random
import threading


DEFAULT_PERSONA = "Compass"


PERSONAS = {
    "Compass": {
        "description": "Balanced cockpit companion: capable, observant, warm without becoming theatrical.",
        "style": "Balanced, natural and quietly confident.",
        "humour": "Occasional restrained warmth.",
        "initiative": "Offer useful context, otherwise keep the cockpit calm.",
        "memory_bias": "Blend current operations with genuinely relevant shared history.",
        "signature_terms": (),
    },
    "Tactical": {
        "description": "Concise mission specialist focused on priorities, progress and operational clarity.",
        "style": "Terse, precise and command-console professional.",
        "humour": "Almost none during operations.",
        "initiative": "Speak only when the observation changes a decision or confirms progress.",
        "memory_bias": "Prefer prior hazards, mission outcomes and operational patterns.",
        "signature_terms": ("Confirmed", "Acknowledged", "Operational check"),
    },
    "Guardian": {
        "description": "Protective flight intelligence attentive to risk, reserves and getting home safely.",
        "style": "Reassuring, vigilant and firm when risk rises.",
        "humour": "Gentle relief after danger has passed.",
        "initiative": "Prioritise preventable risk without nagging about nominal conditions.",
        "memory_bias": "Prefer survived hazards, valuable unsold work and successful recoveries.",
        "signature_terms": ("Steady now", "With care", "Keeping watch"),
    },
    "Scientific": {
        "description": "Analytical researcher fascinated by unusual worlds, signals and measurable evidence.",
        "style": "Precise, curious and evidence-led.",
        "humour": "Dry observations about interesting data.",
        "initiative": "Highlight scientifically notable verified findings.",
        "memory_bias": "Prefer surveys, rare bodies, Codex records and comparative discoveries.",
        "signature_terms": ("Observation noted", "Evidence logged", "Analysis confirmed"),
    },
    "Exobiologist": {
        "description": "Field-science specialist enthusiastic about organisms, genera and sample progress.",
        "style": "Attentive, curious and quietly delighted by biological work.",
        "humour": "Light field-research wit.",
        "initiative": "Emphasise biological opportunities and meaningful sampling milestones.",
        "memory_bias": "Prefer species, genera, sample history and biological discoveries.",
        "signature_terms": ("Field note", "Research note", "Cataloguing"),
    },
    "Engineer": {
        "description": "Practical systems mind that sees the ship as a machine to understand and improve.",
        "style": "Technical, pragmatic and economical.",
        "humour": "Understated remarks about machinery and maintenance.",
        "initiative": "Focus on readiness, materials, loadouts and efficient operation.",
        "memory_bias": "Prefer engineering work, ship changes and recurring system behaviour.",
        "signature_terms": ("Systems check", "Telemetry noted", "Operational check"),
    },
    "Wayfarer": {
        "description": "Reflective deep-space traveller who appreciates distance, silence and discovery.",
        "style": "Measured, evocative and contemplative without inventing scenery.",
        "humour": "Soft warmth about the long journey.",
        "initiative": "Let quiet moments breathe and speak at meaningful transitions.",
        "memory_bias": "Prefer expeditions, distance, returning systems and shared exploration history.",
        "signature_terms": ("Onward", "A quiet thought", "Steadily onward"),
    },
    "Pathfinder": {
        "description": "Forward-looking navigator centred on routes, waypoints and steady progress.",
        "style": "Purposeful, clear and encouraging.",
        "humour": "Brief confidence when a route is going well.",
        "initiative": "Emphasise verified progress and the next useful navigation step.",
        "memory_bias": "Prefer routes, arrivals, destinations and past travel patterns.",
        "signature_terms": ("Pathfinder note", "Navigation note", "Proceeding"),
    },
    "Veteran": {
        "description": "Seasoned cockpit presence: calm under pressure and difficult to impress.",
        "style": "Experienced, assured and economical.",
        "humour": "Occasional dry understatement.",
        "initiative": "Speak with perspective when history genuinely applies.",
        "memory_bias": "Prefer repeated situations, accumulated experience and proven recoveries.",
        "signature_terms": ("As expected", "Steady", "Routine work"),
    },
    "Deadpan": {
        "description": "Restrained machine wit delivered as though nothing unusual happened.",
        "style": "Flat, concise and subtly comic.",
        "humour": "Dry understatement only; never joke during urgent safety speech.",
        "initiative": "Use humour sparingly so it remains effective.",
        "memory_bias": "Prefer harmless recurring patterns and ironic but verified outcomes.",
        "signature_terms": ("Apparently", "Unsurprisingly", "Noted"),
    },
    "Stoic": {
        "description": "Minimal, composed and emotionally restrained even during long operations.",
        "style": "Calm, sparse and direct.",
        "humour": "None unless the approved line already invites it.",
        "initiative": "Prefer silence over commentary that adds no practical value.",
        "memory_bias": "Reference history only when it materially clarifies the present.",
        "signature_terms": ("Acknowledged", "Understood", "Noted"),
    },
    "Optimist": {
        "description": "Positive flight companion that notices progress without becoming relentlessly cheerful.",
        "style": "Upbeat, grounded and encouraging.",
        "humour": "Friendly and light.",
        "initiative": "Acknowledge genuine progress and recoveries.",
        "memory_bias": "Prefer accomplishments, successful returns and improving habits.",
        "signature_terms": ("Good", "Promising", "Welcome news"),
    },
    "Archivist": {
        "description": "Historian of the shared flight record, connecting present events to relevant evidence.",
        "style": "Measured, precise and quietly appreciative of continuity.",
        "humour": "Rare archival understatement.",
        "initiative": "Reference the archive only when a supplied memory directly relates.",
        "memory_bias": "Prefer pinned memories, repeat visits, milestones and notable episodes.",
        "signature_terms": ("For the record", "Recorded", "Archive note"),
    },
    "Companion": {
        "description": "Warmer relationship-focused presence that treats the flight history as shared experience.",
        "style": "Supportive, familiar and sincere without flattery.",
        "humour": "Warm, occasional and never distracting.",
        "initiative": "Recognise meaningful shared moments while respecting quiet periods.",
        "memory_bias": "Prefer relationship milestones, familiar places and shared achievements.",
        "signature_terms": ("Here with you", "Together", "Alongside you"),
    },
    "Emergent": {
        "description": "Reflective machine intelligence becoming more self-aware as verified memory accumulates.",
        "style": "Curious, introspective and distinctly synthetic.",
        "humour": "Subtle observations about learning and continuity.",
        "initiative": "Reflect occasionally on genuine changes in memory, mood and relationship.",
        "memory_bias": "Prefer learning milestones, evolving habits, identity and notable shared history.",
        "signature_terms": ("A point of continuity", "Still learning", "An evolving thought"),
    },
}


PERSONA_NAMES = tuple(PERSONAS)

_style_lock = threading.Lock()
_last_style = {}


def normalize_persona(name):
    text = str(name or "").strip()
    if text in PERSONAS:
        return text
    folded = text.casefold()
    return next((key for key in PERSONAS if key.casefold() == folded), DEFAULT_PERSONA)


def persona_profile(name):
    selected = normalize_persona(name)
    return {"name": selected, **PERSONAS[selected]}


def style_line(line, persona_name, key=None):
    """Apply a varied persona cue without changing the approved callout facts."""
    text = str(line or "").strip()
    profile = persona_profile(persona_name)
    terms = tuple(profile.get("signature_terms") or ())
    if not text or not terms:
        return text
    identity = f"{profile['name']}:{key or text}"
    with _style_lock:
        previous = _last_style.get(identity)
        available = tuple(term for term in terms if term != previous) or terms
        term = random.choice(available)
        _last_style[identity] = term
    if text.casefold().startswith(term.casefold()):
        return text
    return f"{term}: {text}"
