"""
BioRewardCatalog — loads reward values from SrvSurvey's codexRef.json.

Provides species-level exact reward lookup and genus-level range fallback
for cases where only the genus name is known before sampling completes.
"""

import json
import os
import re


def _norm(text):
    if text is None:
        return ""
    text = str(text).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


class BioRewardCatalog:
    def __init__(self):
        self.source_path = ""
        self.species_reward = {}   # normalised english name → exact reward
        self.genus_ranges = {}     # normalised genus name → (min, max)
        self.genus_token_map = {}  # "$Codex_Ent_STEM_…" stem → genus name
        self.global_min = 1_000_000
        self.global_max = 19_000_000

    def species_range(self, species_name, genus_name=None):
        """Return (min, max) reward for a species.  Both values equal when exact match found."""
        s_key = _norm(species_name)
        if s_key and s_key in self.species_reward:
            val = int(self.species_reward[s_key])
            return val, val
        g_key = _norm(genus_name)
        if g_key and g_key in self.genus_ranges:
            return self.genus_ranges[g_key]
        return 0, 0

    def genus_range(self, genus_name):
        """Return (min, max) reward range for a genus token or localised name."""
        g_key = _norm(genus_name)
        # Map "$Codex_Ent_STEM_…" tokens to normalised genus names.
        if g_key.startswith("$codex_ent_"):
            m = re.match(r"^\$codex_ent_([^_]+)", g_key)
            if m:
                stem = m.group(1)
                mapped = self.genus_token_map.get(stem)
                if mapped:
                    g_key = mapped
        if g_key in self.genus_token_map:
            g_key = self.genus_token_map[g_key]
        if g_key and g_key in self.genus_ranges:
            return self.genus_ranges[g_key]
        return 0, 0

    def lookup(self, species_name, genus_name=None):
        """Return best single reward estimate (exact if known, genus-high if not)."""
        exact, _ = self.species_range(species_name, genus_name)
        if exact:
            return exact
        _, hi = self.genus_range(genus_name or species_name)
        return hi or 0


_CACHE = None


def _candidate_paths():
    cwd = os.getcwd()
    here = os.path.dirname(os.path.abspath(__file__))
    return [
        os.path.join(cwd, "codexRef.json"),
        os.path.join(here, "codexRef.json"),
    ]


def _build_catalog(codex):
    cat = BioRewardCatalog()
    rewards = []
    species_map = {}
    genus_values = {}
    genus_token_map = {}

    for entry in codex.values():
        if entry.get("hud_category") != "Biology":
            continue
        reward = entry.get("reward")
        if not isinstance(reward, (int, float)):
            continue
        reward = int(reward)
        if reward <= 0:
            continue

        english_name = entry.get("english_name", "")
        raw_name = entry.get("name", "")

        # "Stratum Tectonicas - Emerald" → base = "Stratum Tectonicas"
        base_name = english_name.split(" - ", 1)[0].strip()
        words = base_name.split()
        if not words:
            continue

        # Exact species lookup on full base name and first-two-word form.
        species_candidates = {_norm(base_name)}
        if len(words) >= 2:
            species_candidates.add(_norm(f"{words[0]} {words[1]}"))

        # Genus lookup on first word and other prefix combos.
        genus_candidates = {_norm(words[0])}
        if len(words) >= 2:
            genus_candidates.add(_norm(f"{words[0]} {words[1]}"))
            genus_candidates.add(_norm(" ".join(words[-2:])))
        if len(words) >= 3:
            genus_candidates.add(_norm(" ".join(words[-3:])))

        for s_key in species_candidates:
            if not s_key:
                continue
            existing = species_map.get(s_key)
            species_map[s_key] = reward if existing is None else max(existing, reward)

        for g_key in genus_candidates:
            if not g_key:
                continue
            genus_values.setdefault(g_key, []).append(reward)

        # Build "$Codex_Ent_STEM" → genus name mapping.
        if raw_name.startswith("$Codex_Ent_"):
            m = re.match(r"^\$Codex_Ent_([^_]+)", raw_name)
            if m:
                stem = _norm(m.group(1))
                genus_token_map[stem] = _norm(words[0])

        rewards.append(reward)

    if rewards:
        cat.global_min = max(1_000_000, min(rewards))
        cat.global_max = max(rewards)

    cat.species_reward = species_map
    cat.genus_ranges = {
        key: (min(vals), max(vals))
        for key, vals in genus_values.items()
        if vals
    }
    cat.genus_token_map = genus_token_map
    return cat


def load_bio_reward_catalog(force_reload=False):
    global _CACHE
    if _CACHE is not None and not force_reload:
        return _CACHE

    codex = None
    source = None
    for path in _candidate_paths():
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                codex = json.load(f)
            if isinstance(codex, dict):
                source = path
                break
        except Exception:
            continue

    cat = _build_catalog(codex if isinstance(codex, dict) else {})
    cat.source_path = source or "(codexRef.json not found)"
    _CACHE = cat
    return cat
