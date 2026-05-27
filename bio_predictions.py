"""
Bio species prediction engine for Elite Dangerous exobiology.

Loads SrvSurvey bio-criteria JSON files and evaluates body scan conditions
to predict which genera / species can spawn on a given planet.

Usage:
    from bio_predictions import predict_for_body, load_criteria

    predictions = predict_for_body(
        body_type   = "Rocky",          # journal PlanetClass normalised
        gravity     = 0.18,             # SurfaceGravity (already in g)
        temp        = 178.0,            # SurfaceTemperature K
        pressure    = 0.022,            # SurfacePressure atm
        atmos_type  = "CarbonDioxide",  # AtmosphereType
        atmos_comp  = {"CarbonDioxide": 100.0},
        volcanism   = "None",           # normalised volcanism string
        materials   = {"Iron": 18.5},   # {Name: Percent}
        star_types  = ["G"],            # parent star type(s)
    )
    # → [{"genus": "Aleoida", "species": "Arcus", "variant": "Teal", "reward": ...}, ...]
"""

import json
import os
import re


# ── Volcanism normalisation ───────────────────────────────────────────────────

def _norm_volcanism(raw: str) -> str:
    """'Minor Water Magma Volcanism' → 'Minor Water Magma'; 'No volcanism' → 'None'."""
    v = (raw or "").strip()
    if not v or v.lower() in ("no volcanism", "none"):
        return "None"
    v = re.sub(r"\s*volcanism\s*$", "", v, flags=re.IGNORECASE).strip()
    return v or "None"


# ── Planet class normalisation ────────────────────────────────────────────────

_PC_MAP = {
    "rocky body":               "Rocky",
    "high metal content body":  "HMC",
    "icy body":                 "Icy",
    "rocky ice body":           "RockyIce",
    "metal rich body":          "MRB",
    "earthlike body":           "Earthlike",
    "water world":              "WaterWorld",
    "ammonia world":            "AmmoniaWorld",
}

def _norm_planet_class(raw: str) -> str:
    return _PC_MAP.get((raw or "").strip().lower(), raw or "")


# ── Clause parsing ────────────────────────────────────────────────────────────

_CLAUSE_RE = re.compile(r'^(\w+)\s+([&!]?)\[(.+)\]$')

def _parse_clause(s: str) -> dict | None:
    s = s.strip()
    if not s or s.startswith('#'):
        return None
    m = _CLAUSE_RE.match(s)
    if not m:
        return None
    prop  = m.group(1).lower()
    mod   = m.group(2)          # "&" | "!" | ""
    inner = m.group(3).strip()

    # Skip unsupported / unneeded clauses
    if prop in ('guardian', 'nebulae'):
        return None

    # Range: "175.0 ~ 180.0" / " ~ 0.276" / "0.0161 ~ "
    if '~' in inner and '>=' not in inner:
        parts = inner.split('~', 1)
        lo_s  = parts[0].strip()
        hi_s  = parts[1].strip()
        return {
            'prop': prop,
            'op':   'range',
            'lo':   float(lo_s) if lo_s else None,
            'hi':   float(hi_s) if hi_s else None,
        }

    # Atmosphere composition: "CarbonDioxide >= 100 | SulphurDioxide >= 0.99"
    if '>=' in inner:
        comps = []
        for part in inner.split('|'):
            m2 = re.match(r'(\w+)\s*>=\s*([0-9.]+)', part.strip())
            if m2:
                comps.append((m2.group(1), float(m2.group(2))))
        return {'prop': prop, 'op': 'comp', 'comps': comps}

    # List of values
    values = [v.strip() for v in inner.split(',') if v.strip()]
    op = 'all' if mod == '&' else ('not' if mod == '!' else 'is')
    return {'prop': prop, 'op': op, 'values': values}


# ── Clause evaluation ─────────────────────────────────────────────────────────

def _eval_clause(clause: dict, body: dict, star_types: list[str]) -> bool:
    prop = clause['prop']
    op   = clause['op']

    if prop == 'body':
        bt = body.get('body_type', '')
        return bt in clause['values']

    if prop in ('gravity', 'temp', 'pressure'):
        key_map = {'gravity': 'gravity', 'temp': 'temp', 'pressure': 'pressure'}
        val = float(body.get(key_map[prop]) or 0)
        lo, hi = clause.get('lo'), clause.get('hi')
        return (lo is None or val >= lo) and (hi is None or val <= hi)

    if prop == 'atmostype':
        at = body.get('atmos_type', '')
        if op == 'is':
            return any(v.lower() == at.lower() for v in clause['values'])

    if prop == 'atmoscomp':
        comp = body.get('atmos_comp') or {}
        if op == 'comp':
            # OR logic: any component meeting the threshold
            for name, min_pct in clause['comps']:
                if float(comp.get(name) or comp.get(name.lower()) or 0) >= min_pct:
                    return True
            return False

    if prop == 'volcanism':
        vol = body.get('volcanism', 'None')
        vals_lower = [v.lower() for v in clause['values']]
        vol_lower  = vol.lower()
        if op == 'is':
            return vol_lower in vals_lower or any(v in vol_lower for v in vals_lower)

    if prop == 'mats':
        mats = {k.lower() for k in (body.get('materials') or {})}
        vals = [v.lower() for v in clause['values']]
        if op == 'is':  return any(v in mats for v in vals)
        if op == 'all': return all(v in mats for v in vals)
        if op == 'not': return not any(v in mats for v in vals)

    if prop == 'star':
        st_lower = [s.upper() for s in star_types]
        if op == 'is':
            return any(v.upper() in st_lower for v in clause['values'])

    if prop == 'regions':
        # Optimistic: unknown region passes all region checks so players near the
        # galactic edge still get predictions (at worst a few extras are shown).
        region = body.get('region')
        if region is None:
            return True
        r = str(region)
        if op == 'is':  return r in clause['values']
        if op == 'not': return r not in clause['values']

    return True   # unknown / unimplemented property — assume passes


def _queries_pass(queries: list[str], body: dict, star_types: list[str]) -> bool:
    for q in queries:
        c = _parse_clause(q)
        if c and not _eval_clause(c, body, star_types):
            return False
    return True


# ── Tree flattening ───────────────────────────────────────────────────────────

def _flatten(node: dict,
             genus: str = '',
             species: str = '',
             acc_query: list | None = None,
             common_children: list | None = None):
    """Yield (genus, species, variant, full_query_list) for every leaf in the tree."""
    acc_query = list(acc_query or [])
    my_query  = [q for q in (node.get('query') or [])
                 if not q.strip().startswith('#')]
    full_q    = acc_query + my_query

    genus   = node.get('genus')   or genus
    species = node.get('species') or species
    variant = node.get('variant', '')

    if node.get('commonChildren'):
        common_children = node['commonChildren']

    # Leaf: this node has a variant
    if variant:
        yield (genus, species, variant, full_q)
        return

    for child in (node.get('children') or []):
        c_genus   = child.get('genus')   or genus
        c_species = child.get('species') or species

        if child.get('useCommonChildren'):
            child_q = [q for q in (child.get('query') or [])
                       if not q.strip().startswith('#')]
            for cc in (common_children or []):
                cc_q = [q for q in (cc.get('query') or [])
                        if not q.strip().startswith('#')]
                cc_variant = cc.get('variant', '')
                yield (c_genus, c_species, cc_variant, full_q + child_q + cc_q)
        else:
            yield from _flatten(child,
                                genus=c_genus,
                                species=c_species,
                                acc_query=full_q,
                                common_children=common_children)


# ── Loading ───────────────────────────────────────────────────────────────────

_CRITERIA: list[dict] | None = None


def _criteria_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    cwd  = os.getcwd()
    for d in (cwd, here):
        p = os.path.join(d, 'bio-criteria')
        if os.path.isdir(p):
            return p
    return os.path.join(cwd, 'bio-criteria')


def load_criteria(force: bool = False) -> list[dict]:
    global _CRITERIA
    if _CRITERIA is not None and not force:
        return _CRITERIA
    cdir = _criteria_dir()
    result = []
    if os.path.isdir(cdir):
        for fname in sorted(os.listdir(cdir)):
            if fname.endswith('.json'):
                try:
                    with open(os.path.join(cdir, fname), encoding='utf-8') as f:
                        result.append(json.load(f))
                except Exception:
                    pass
    _CRITERIA = result
    return result


# ── Public API ────────────────────────────────────────────────────────────────

def predict_for_body(body_type: str,
                     gravity: float,
                     temp: float,
                     pressure: float,
                     atmos_type: str,
                     atmos_comp: dict,
                     volcanism: str,
                     materials: dict,
                     star_types: list[str]) -> list[dict]:
    """Return a list of predicted species dicts for a planet body.

    Each dict has keys: genus, species, variant.
    Normalise inputs before calling (see _norm_planet_class / _norm_volcanism).
    """
    body = {
        'body_type':  _norm_planet_class(body_type),
        'gravity':    float(gravity or 0),
        'temp':       float(temp or 0),
        'pressure':   float(pressure or 0),
        'atmos_type': atmos_type or '',
        'atmos_comp': {k: float(v) for k, v in (atmos_comp or {}).items()},
        'volcanism':  _norm_volcanism(volcanism),
        'materials':  {k: float(v) for k, v in (materials or {}).items()},
    }
    stars = [s.upper() for s in (star_types or [])]

    seen    = set()
    results = []

    for root in load_criteria():
        for genus, species, variant, full_q in _flatten(root):
            if not _queries_pass(full_q, body, stars):
                continue
            key = (genus.lower(), species.lower())
            if key not in seen:
                seen.add(key)
                results.append({
                    'genus':   genus,
                    'species': species,
                    'variant': variant,
                })

    return results
