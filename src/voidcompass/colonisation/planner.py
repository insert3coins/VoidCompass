"""The system planner (5.5.2.1): tier points, economies, links, effects, score
and unlocks for a system's sites, as Raven Colonial's website works them out.

A port of RavenColonialWeb's system-model2.ts and economy-model2.ts
(https://github.com/njthomson/RavenColonialWeb, GPL-3.0, like Void Compass),
kept close to the original so the numbers match the website's; its site
types come from data/colonisation/site_types.json (vendored from
site-data.ts by tools/vendor_colonisation_data.py).

``build_model(sys, use_incomplete, buff_nerf)`` takes the system as the
service returns it (``/api/v2/system/{name}``) and returns plain data;
``snapshot(sys)`` is what the website saves with a system's sites.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
import functools
import json
import math

from voidcompass.core.paths import resource_path

ECONOMIES = ("agriculture", "extraction", "hightech", "industrial", "military",
             "refinery", "terraforming", "tourism", "service")
LINK_ECONOMIES = ("agriculture", "extraction", "industrial", "hightech", "tourism",
                  "military", "service", "refinery", "terraforming")
EFFECTS = ("pop", "mpop", "sec", "tech", "wealth", "sol", "dev")
EFFECT_NAMES = {"pop": "Population", "mpop": "Max population", "sec": "Security", "tech": "Tech level",
                "wealth": "Wealth", "sol": "Standard of living", "dev": "Development level"}
ECONOMY_NAMES = {"agriculture": "Agriculture", "service": "Service", "extraction": "Extraction",
                 "hightech": "High Tech", "industrial": "Industrial", "military": "Military", "none": "None",
                 "tourism": "Tourism", "refinery": "Refinery", "terraforming": "Terraforming", "colony": "Colony"}
STATUSES = ("plan", "build", "complete", "demolish")
RESERVE_LEVELS = ("depleted", "low", "common", "major", "pristine")
BODY_FEATURES = ("bio", "geo", "rings", "volcanism", "terraformable", "tidal", "landable", "atmosphere")
BODY_TYPE_NAMES = {"bh": "Black hole", "ns": "Neutron star", "wd": "White dwarf", "st": "Star",
                   "aw": "Ammonia world", "elw": "Earth-like world", "gg": "Gas giant",
                   "hmc": "High metal content body", "ib": "Icy body", "mrb": "Metal-rich body",
                   "rb": "Rocky body", "ri": "Rocky ice body", "wg": "Water giant", "ww": "Water world",
                   "ac": "Asteroid cluster", "bc": "Barycentre", "un": "Unknown"}

STELLAR_REMNANTS = ("bh", "ns", "wd")
_STARS_AND_CLUSTERS = (*STELLAR_REMNANTS, "ac", "st")
_STARS = (*STELLAR_REMNANTS, "st")
# The most two stars can be apart for their barycentre to host stations.
_BARYCENTRE_MAX_LS = 20


@functools.lru_cache(maxsize=1)
def _data():
    path = resource_path("data", "colonisation", "site_types.json")
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def site_types():
    return _data()["site_types"]


def site_pads(build_type):
    return _data()["site_pads"].get(str(build_type or ""))


def system_unlocks():
    return _data()["system_unlocks"]


def site_type(build_type):
    """The site type for a layout (``dual_truss``), or the Unknown type."""
    build_type = str(build_type or "").replace(" (primary)", "")
    trimmed = build_type[:-1]
    for row in site_types():
        names = row["subTypes"] + row.get("altTypes", [])
        if build_type in names or trimmed in names:
            return row
    return site_types()[0]


def build_type_name(build_type):
    """The website's name for a layout: ``Coriolis Starport (dual_truss)``."""
    if not build_type:
        return "?"
    build_type = str(build_type).replace(" (primary)", "")
    row = site_type(build_type)
    text = row["displayName"] if row["buildClass"] == "starport" else f"{row['displayName']} {row['buildClass']}"
    if row["buildClass"] == "settlement":
        for size in ("Small ", "Medium ", "Large "):
            text = text.replace(size, "")
    return f"{text} ({build_type})"


def can_receive_links(row):
    return row["buildClass"] in ("starport", "outpost")


def apply_tax(tier, cost, tax_count):
    if tax_count > 0:
        if tier == 3:
            cost += cost * tax_count
        else:
            cost += math.trunc(cost * 0.75 * tax_count)
    return cost


def _locale_key(text):
    return (str(text or "").casefold(), str(text or ""))


def _js_round_2(value):
    """Math.round(value * 100) / 100."""
    return math.floor(value * 100 + 0.5) / 100


def _round_effect(value):
    """parseFloat((v * 1000).toFixed()) / 1000 (halves away from zero)."""
    scaled = Decimal(repr(value * 1000)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return float(scaled) / 1000


class _Site:
    __slots__ = ("raw", "id", "name", "body_num", "build_type", "status", "type", "body", "sys",
                 "links", "economies", "intrinsic", "audit", "primary_economy", "parent_link",
                 "body_buffed", "system_buffed", "calc_needs")

    def __init__(self, raw, sys, body):
        self.raw = raw
        self.id = str(raw.get("id") or "")
        self.name = str(raw.get("name") or "")
        self.body_num = raw.get("bodyNum") if raw.get("bodyNum") is not None else -1
        self.build_type = str(raw.get("buildType") or "")
        self.status = raw.get("status") or "plan"
        self.type = site_type(self.build_type)
        self.body = body
        self.sys = sys
        self.links = None
        self.economies = None
        self.intrinsic = None
        self.audit = None
        self.primary_economy = None
        self.parent_link = None
        self.body_buffed = set()
        self.system_buffed = set()
        self.calc_needs = None


class _Body:
    def __init__(self, raw):
        self.raw = raw
        self.name = raw.get("name") or "Unknown"
        self.num = raw.get("num")
        self.type = raw.get("type") or "un"
        self.parents = list(raw.get("parents") or ())
        self.features = list(raw.get("features") or ())
        self.dist_ls = raw.get("distLS")
        self.sites = []
        self.surface = []
        self.orbital = []
        self.surface_primary = None
        self.orbital_primary = None


class _Sys:
    def __init__(self, raw):
        self.raw = raw
        self.name = raw.get("name") or ""
        self.reserve_level = raw.get("reserveLevel") if raw.get("reserveLevel") is not None else "pristine"
        self.bodies = [dict(body, parents=list(body.get("parents") or ()), features=list(body.get("features") or ()))
                       for body in raw.get("bodies") or () if isinstance(body, dict)]
        self.body_by_num = {body.get("num"): body for body in self.bodies}

    def has_body_type(self, body_type):
        return any(body.get("type") == body_type for body in self.bodies)


_UNKNOWN_BODY = {"name": "Unknown", "num": -1, "distLS": -1, "features": ["landable"], "parents": [],
                 "subType": "Unknown", "type": "un", "radius": -1, "temp": -1, "gravity": -1}


class _Model:
    def __init__(self, raw_sys, use_incomplete, buff_nerf):
        self.sys = _Sys(raw_sys)
        sites = [site for site in raw_sys.get("sites") or () if isinstance(site, dict)]
        limit = raw_sys.get("idxCalcLimit")
        limit = len(sites) if limit is None else int(limit)
        if use_incomplete:
            self.calc_ids = {str(site.get("id")) for index, site in enumerate(sites)
                             if index < limit and site.get("status") != "demolish"}
        else:
            self.calc_ids = {str(site.get("id")) for site in sites if site.get("status") == "complete"}
        self.use_incomplete = use_incomplete
        self.buff_nerf = buff_nerf
        self._hosting_barycentres()
        self.body_map = {}
        self.sites = []
        self.score = 0
        for raw in sites:
            raw_body = self.sys.body_by_num.get(raw.get("bodyNum") if raw.get("bodyNum") is not None else -1) or _UNKNOWN_BODY
            body = self.body_map.get(raw_body["name"])
            if body is None:
                body = self.body_map[raw_body["name"]] = _Body(raw_body)
            site = _Site(raw, self.sys, body)
            self.sites.append(site)
            body.sites.append(site)
            if site.status != "demolish":
                (body.orbital if site.type["orbital"] else body.surface).append(site)
            if site.id in self.calc_ids:
                self.score += site.type.get("score", 0) or 0
        bodies = list(self.body_map.values())
        for body in bodies:
            body.surface_primary = self._primary_port(body.surface)
            body.orbital_primary = self._primary_port(self._siblings(body, bool(body.surface_primary)))
        for body in bodies:
            self._body_links(body)
        self.tier_points, self.tax_count = self._tier_points(not use_incomplete)
        self.system_economies, self.effects = self._effects()
        self.unlocks = {key: any(site.id in self.calc_ids and any(site.build_type.startswith(need) for need in row["need_types"])
                                 for site in self.sites)
                        for key, row in system_unlocks().items()}

    # -- structure -------------------------------------------------------
    def _hosting_barycentres(self):
        """A barycentre of two close stars can host stations (named for them)."""
        for body in self.sys.bodies:
            if body.get("type") != "bc":
                continue
            children = [child for child in self.sys.bodies
                        if (child.get("parents") or [None])[0] == body.get("num") and child.get("type") in _STARS]
            if len(children) == 2 and abs((children[0].get("distLS") or 0) - (children[1].get("distLS") or 0)) < _BARYCENTRE_MAX_LS:
                body["hostBC"] = True
                body["name"] = "x " + children[0]["name"].replace(self.sys.name, "").strip() + children[1]["name"].replace(self.sys.name, "").strip()
                body["subType"] = "Barycentre"
                if not body.get("parents"):
                    body["parents"] = list(children[0].get("parents") or ())[1:]

    def _siblings(self, body, only_orbitals):
        if body.type not in _STARS_AND_CLUSTERS:
            return list(body.orbital if only_orbitals else body.sites)
        parent = body.raw if body.type != "ac" else self.sys.body_by_num.get(body.parents[0] if body.parents else None)
        if parent is None:
            return []
        members = [parent] + [item for item in self.sys.bodies
                              if item.get("type") == "ac" and (item.get("parents") or [None])[0] == parent.get("num")]
        found = []
        for member in members:
            mapped = self.body_map.get(member.get("name"))
            if mapped is not None:
                found.extend(mapped.orbital if only_orbitals else mapped.sites)
        return found

    def _primary_port(self, sites):
        if not sites:
            return None
        if self.calc_ids:
            sites = [site for site in sites if site.id in self.calc_ids]
        for tier in (3, 2, 1):
            for site in sites:
                if site.type["tier"] == tier and can_receive_links(site.type):
                    return site
        return None

    def _body_links(self, body):
        if not body.surface_primary and not body.orbital_primary:
            return
        if body.surface_primary:
            self._site_links(body, body.surface_primary)
        if body.orbital_primary:
            self._site_links(body, body.orbital_primary)
        for site in body.sites:
            self._site_link_economies(site)

    def _site_links(self, body, primary):
        siblings = self._siblings(body, False)
        strong = []
        for site in siblings:
            if site.parent_link or site.type["inf"] == "none" or site is primary or site.id not in self.calc_ids:
                continue
            if not primary.type["orbital"] and site.type["orbital"] and site.type["buildClass"] in ("outpost", "starport"):
                continue
            if site.type["orbital"] and not primary.type["orbital"] and body.orbital_primary:
                continue
            site.parent_link = primary
            strong.append(site)
        strong.sort(key=lambda site: _locale_key(site.name))
        sibling_ids = {id(site) for site in siblings}
        weak = [site for other in self.body_map.values() if other is not body for site in other.sites
                if id(site) not in sibling_ids and site.type["inf"] != "none"
                and site is not site.body.orbital_primary and site is not site.body.surface_primary
                and site.id in self.calc_ids]
        if primary.links is None and (strong or weak):
            primary.links = {"economies": {}, "strong": strong, "weak": weak}

    def _site_link_economies(self, site):
        """What links feed a port, per economy (for display)."""
        if site.links is None:
            return
        counts = {economy: {"strong": 0, "weak": 0} for economy in LINK_ECONOMIES}
        for other in site.links["strong"]:
            inf = other.type["inf"]
            if inf == "none":
                continue
            current = set()
            if inf == "colony":
                self.colony_economies(other)
                current.update(item for item in other.intrinsic or () if item not in ("none", "colony"))
            else:
                current.add(inf)
            for sub in (other.links or {}).get("strong", ()):
                if sub.type["inf"] not in ("none", "colony"):
                    current.add(sub.type["inf"])
            for economy in current:
                counts.setdefault(economy, {"strong": 0, "weak": 0})["strong"] += 1
        for other in site.links["weak"]:
            inf = other.type["inf"]
            if inf == "none":
                continue
            if inf == "colony":
                self.colony_economies(other)
                for item in other.intrinsic or ():
                    if item not in ("none", "colony"):
                        counts[item]["weak"] += 1
            else:
                counts.setdefault(inf, {"strong": 0, "weak": 0})["weak"] += 1
        ordered = sorted(counts, key=functools.cmp_to_key(lambda a, b: (
            counts[b]["strong"] - counts[a]["strong"] or counts[b]["weak"] - counts[a]["weak"]
            or (-1 if b < a else 1 if b > a else 0))))
        for key in ordered:
            if counts[key]["strong"] or counts[key]["weak"]:
                site.links["economies"][key] = counts[key]

    # -- points, effects -------------------------------------------------
    def _tier_points(self, include_started):
        points = {"tier2": 0, "tier3": 0}
        primary_id = self.sites[0].id if self.sites else None
        tax_count = -2
        for site in self.sites:
            if site.status == "demolish":
                continue
            if include_started:
                if site.status == "plan":
                    continue
            elif site.id not in self.calc_ids:
                continue
            needs = site.type["needs"]
            if site.id != primary_id and needs["count"] > 0 and needs["tier"] > 1:
                count = needs["count"]
                if site.type["buildClass"] == "starport" and site.type["tier"] > 1:
                    tax_count += 1
                    count = apply_tax(site.type["tier"], count, tax_count)
                points["tier2" if needs["tier"] == 2 else "tier3"] -= count
                site.calc_needs = {"tier": needs["tier"], "count": count}
            if site.id not in self.calc_ids:
                continue
            gives = site.type["gives"]
            if gives["count"] > 0 and gives["tier"] > 1:
                points["tier2" if gives["tier"] == 2 else "tier3"] += gives["count"]
        return points, tax_count

    def _effects(self):
        economies, effects = {}, {}
        first = True
        for site in self.sites:
            if site.status == "demolish" or site.id not in self.calc_ids:
                continue
            if site.type["buildClass"] in ("settlement", "outpost", "starport"):
                self.colony_economies(site)
            inf = site.primary_economy or site.type["inf"]
            if inf != "none":
                economies[inf] = economies.get(inf, 0) + 1
            for key in EFFECTS:
                effect = (site.type.get("effects") or {}).get(key, 0) or 0
                if effect == 0:
                    continue
                if self.buff_nerf:
                    effect = _afflicted_effect(key, effect, first)
                effects[key] = effects.get(key, 0) + effect
            first = False
        ordered = sorted(economies, key=functools.cmp_to_key(lambda a, b: (
            economies[b] - economies[a] or (-1 if b < a else 1 if b > a else 0))))
        return {key: economies[key] for key in ordered}, {key: _round_effect(value) for key, value in effects.items()}

    # -- economies (economy-model2.ts) -----------------------------------
    def colony_economies(self, site):
        if site.economies is not None and site.primary_economy:
            return site.primary_economy
        site.audit = []
        values = {economy: 0 for economy in ECONOMIES}
        build_class = site.type["buildClass"]
        if build_class not in ("settlement", "outpost", "starport"):
            return "none"
        if build_class == "settlement":
            self._adjust(site.type["inf"], 1.0, "Odyssey settlement fixed economy", values, site)
            self._buffs(values, site, True)
            return self._finish(values, site)
        if site.type.get("fixed"):
            self._specialised(values, site)
        else:
            self._body_type(values, site)
            self._buffs(values, site, False)
        if site.links is not None:
            self._strong_links(values, site.links["strong"], site)
            self._weak_links(values, site)
        return self._finish(values, site)

    @staticmethod
    def _finish(values, site):
        primary = sorted(values, key=lambda key: -values[key])[0]
        site.economies = values
        site.primary_economy = primary
        site.audit.sort(key=lambda row: (-values.get(row["inf"], 0), row["inf"]))
        return primary

    @staticmethod
    def _adjust(inf, delta, reason, values, site, source=None):
        before = values.get(inf)
        value = (values.get(inf) if values.get(inf) is not None else math.nan) + delta
        if value <= 0:
            value = 0.1
        values[inf] = _js_round_2(value) if not math.isnan(value) else value
        if site.audit is not None:
            site.audit.append({"inf": inf, "delta": delta, "reason": reason, "before": before, "after": values[inf]})
        if source == "body":
            site.body_buffed.add(inf)
        elif source == "sys":
            site.system_buffed.add(inf)

    def _specialised(self, values, site):
        fixed = site.type.get("fixed")
        if not fixed or fixed in ("none", "colony"):
            return
        if site.type["orbital"]:
            self._adjust(fixed, 1.0, "Specialised orbital economy", values, site)
        else:
            self._adjust(fixed, 0.5, "Specialised surface economy", values, site)
        self._buffs(values, site, False)

    def _body_type(self, values, site):
        if site.type["inf"] != "colony":
            return
        intrinsic = []

        def add(economy, reason, source=None):
            self._adjust(economy, 1, reason, values, site, source)
            if economy not in intrinsic:
                intrinsic.append(economy)

        body_type = site.body.type if site.body else None
        if body_type == "un":
            pass
        elif body_type in ("bh", "ns", "wd"):
            add("hightech", "Body type: BH/NS/WD")
            add("tourism", "Body type: BH/NS/WD")
        elif body_type in ("st", "bc"):
            add("military", "Body type: STAR")
        elif body_type == "elw":
            for economy in ("agriculture", "hightech", "military", "tourism"):
                add(economy, "Body type: ELW")
        elif body_type == "ww":
            add("agriculture", "Body type: WW")
            add("tourism", "Body type: WW")
        elif body_type == "aw":
            add("hightech", "Body type: AMMONIA")
            add("tourism", "Body type: AMMONIA")
        elif body_type in ("gg", "wg"):
            add("hightech", "Body type: GG/WG")
            add("industrial", "Body type: GG/WG")
        elif body_type in ("hmc", "mrb"):
            add("extraction", "Body type: HMC")
        elif body_type == "ri":
            add("industrial", "Body type: ROCKY-ICE")
            add("refinery", "Body type: ROCKY-ICE")
        elif body_type == "rb":
            add("refinery", "Body type: ROCKY")
        elif body_type == "ib":
            add("industrial", "Body type: ICY")
        elif body_type == "ac":
            add("extraction", "Body type: ASTEROID")
        else:
            return
        body = site.body
        if body.name and body_type in ("st", *STELLAR_REMNANTS):
            if any(item.get("type") == "ac" and str(item.get("name") or "").startswith(body.name) for item in self.sys.bodies):
                add("extraction", "Star has: ASTEROIDs")
        if "rings" in body.features and body_type not in ("hmc", "mrb"):
            add("extraction", "Body has: RINGS", "body")
        if "bio" in body.features:
            if body_type not in ("elw", "ww"):
                add("agriculture", "Body has: BIO", "body")
            add("terraforming", "Body has: BIO", "body")
        if "geo" in body.features:
            if body_type not in ("hmc", "mrb"):
                add("extraction", "Body has: GEO", "body")
            if body_type not in ("gg", "wg", "ri", "ib"):
                add("industrial", "Body has: GEO", "body")
        site.intrinsic = intrinsic

    def _strong_links(self, values, strong_sites, site, sub_link=None):
        for other in strong_sites:
            inf = other.type["inf"]
            if inf == "none" or other.id not in self.calc_ids:
                continue
            size = 0.4 if other.type["tier"] == 1 else 0.8 if other.type["tier"] == 2 else 1.2
            prefix = "sub-strong link" if sub_link else "Strong link"
            if inf != "colony":
                if inf in values:
                    self._adjust(inf, size, f"Apply {prefix} from: {other.name} (T{other.type['tier']})", values, site)
                    self._strong_link_boost(inf, values, site, prefix)
                if other.links and not sub_link:
                    self._strong_links(values, other.links["strong"], site, inf)
                continue
            if not other.primary_economy:
                continue
            for economy in other.economies or {}:
                if economy in (other.intrinsic or ()):
                    self._adjust(economy, size, f"Apply colony {prefix} from: {other.name} (T{other.type['tier']})", values, site)
                    self._strong_link_boost(economy, values, site, f"{prefix}s")
            if other.links and not sub_link:
                self._strong_links(values, other.links["strong"], site, "*")

    def _strong_link_boost(self, inf, values, site, reason):
        reserve = self.sys.reserve_level
        body = site.body
        body_type = body.type if body else None
        features = body.features if body else ()
        if inf == "agriculture":
            if body_type in ("elw", "ww") or "bio" in features:
                self._adjust(inf, 0.4, f"+ {reason} boost: Body is ELW/WW or has BIO", values, site, "body")
            if body_type == "ib" or self._tidal_to_star(body.raw if body else None):
                self._adjust(inf, -0.4, f"- {reason} boost: Body is ICY or has TIDAL", values, site, "body")
        elif inf == "extraction":
            self._reserve_boost(inf, values, site, reason, reserve)
            if "volcanism" in features:
                self._adjust(inf, 0.4, f"+ {reason} boost: Body has VOLCANISM", values, site, "body")
        elif inf == "hightech":
            if body_type in ("aw", "elw", "ww"):
                self._adjust(inf, 0.4, f"+ {reason} boost: Body is AW/ELW/WW", values, site, "body")
            if "bio" in features:
                self._adjust(inf, 0.4, f"+ {reason} boost: Body has BIO", values, site, "body")
            if "geo" in features:
                self._adjust(inf, 0.4, f"+ {reason} boost: Body has GEO", values, site, "body")
        elif inf in ("industrial", "refinery"):
            self._reserve_boost(inf, values, site, reason, reserve)
        elif inf == "tourism":
            if body_type in ("aw", "elw", "ww"):
                self._adjust(inf, 0.4, f"+ {reason} boost: Body is AW/ELW/WW", values, site, "body")
            if "bio" in features:
                self._adjust(inf, 0.4, f"+ {reason} boost: Body has BIO", values, site, "body")
            if "geo" in features:
                self._adjust(inf, 0.4, f"+ {reason} boost: Body has GEO", values, site, "body")
            for star, label in (("ns", "Neutron Star"), ("bh", "Black Hole"), ("wd", "White Dwarf")):
                if self.sys.has_body_type(star):
                    self._adjust(inf, 0.4, f"+ {reason} boost: System has {label}", values, site, "sys")

    def _reserve_boost(self, inf, values, site, reason, reserve):
        if reserve in ("major", "pristine"):
            self._adjust(inf, 0.4, f"+ {reason} boost: System reserveLevel is MAJOR or PRISTINE", values, site, "sys")
        elif reserve in ("depleted", "low"):
            self._adjust(inf, -0.4, f"- {reason} boost: System reserveLevel is LOW or DEPLETED", values, site, "sys")

    def _buffs(self, values, site, settlement):
        reserve = self.sys.reserve_level
        body = site.body
        body_type = body.type if body else None
        features = body.features if body else ()
        for key in ("industrial", "extraction", "refinery"):
            if values[key] > 0:
                if reserve in ("major", "pristine"):
                    self._adjust(key, 0.4, "Buff: reserveLevel MAJOR or PRISTINE", values, site, "sys")
                elif reserve in ("low", "depleted") and not settlement:
                    self._adjust(key, -0.4, "Buff: reserveLevel LOW or DEPLETED", values, site, "sys")
        if values["agriculture"] > 0:
            buffed = False
            if "bio" in features or "terraformable" in features:
                self._adjust("agriculture", 0.4, "Buff: body has BIO or TERRAFORMABLE", values, site, "body")
                buffed = True
            elif body_type in ("elw", "ww"):
                self._adjust("agriculture", 0.4, "Buff: body is ELW or WW", values, site, "body")
            if (body_type == "ib" or self._tidal_to_star(body.raw if body else None)) and (not settlement or buffed):
                self._adjust("agriculture", -0.4, "Buff: body is ICY or has TIDAL", values, site, "body")
        if values["hightech"] > 0:
            if settlement:
                if "bio" in features:
                    self._adjust("hightech", 0.4, "Buff: body has BIO", values, site, "body")
                if "geo" in features:
                    self._adjust("hightech", 0.4, "Buff: body has GEO", values, site, "body")
                if body_type in ("elw", "aw"):
                    self._adjust("hightech", 0.4, "Buff: body is ELW or AW", values, site, "body")
            elif "bio" in features or "geo" in features:
                self._adjust("hightech", 0.4, "Buff: body has BIO or GEO", values, site, "body")
            elif body_type in ("elw", "aw"):
                self._adjust("hightech", 0.4, "Buff: body is ELW or AW", values, site, "body")
        if values["extraction"] > 0 and "volcanism" in features:
            self._adjust("extraction", 0.4, "Buff: body has VOLCANISM", values, site, "body")
        if values["tourism"] > 0:
            for star, label in (("bh", "a Black Hole"), ("ns", "a Neutron Star"), ("wd", "a White Dwarf")):
                if self.sys.has_body_type(star):
                    self._adjust("tourism", 0.4, f"Buff: system has {label}", values, site, "sys")
            if "tourism" not in site.body_buffed:
                if "bio" in features or "geo" in features:
                    self._adjust("tourism", 0.4, "Buff: body has BIO or GEO", values, site, "body")
                elif body_type in ("elw", "ww", "aw"):
                    self._adjust("tourism", 0.4, "Buff: body is ELW or WW or AW", values, site, "body")

    def _weak_links(self, values, site):
        for other in site.links.get("weak", ()):
            if other.id not in self.calc_ids:
                continue
            inf = other.type["inf"]
            if inf == "none":
                continue
            if inf == "colony":
                if other.primary_economy:
                    for item in other.intrinsic or ():
                        self._adjust(item, 0.05, f"Apply weak link from: {other.name} (intrinsic)", values, site)
                continue
            if inf in values:
                self._adjust(inf, 0.05, f"Apply weak link from: {other.name}", values, site)

    def _tidal_to_star(self, body, parents=None):
        if body is None:
            return False
        if parents is None:
            parents = list(body.get("parents") or ())
        if "tidal" not in (body.get("features") or ()) and body.get("type") != "bc":
            return False
        parent_num = parents.pop(0) if parents else None
        parent = self.sys.body_by_num.get(parent_num)
        if parent is None:
            return False
        if parent.get("type") in _STARS:
            return True
        if parent.get("type") == "bc":
            children = [item for item in self.sys.bodies if (item.get("parents") or [None])[0] == parent.get("num")]
            if len(children) > 1:
                index = next((i for i, item in enumerate(children) if item.get("name") == body.get("name")), -1)
                if index < 2:
                    other = children[1] if index == 0 else children[0]
                    if other.get("type") in _STARS:
                        return True
                    beyond = self.sys.body_by_num.get(parents[0] if parents else None)
                    if beyond is not None and beyond.get("type") == "st":
                        return True
                if index > 1 and children[0].get("type") in _STARS and children[1].get("type") in _STARS:
                    return True
                return False
        return self._tidal_to_star(parent, parents)


def _afflicted_effect(key, effect, initial):
    if key in ("pop", "mpop"):
        return effect
    up, down = {"dev": (0.4, 0.1), "sec": (0.4, 0.1), "sol": (0.4, 0.2), "tech": (0.2, 0.25), "wealth": (0.4, 0.25)}[key]
    return effect + effect * up if initial else effect - effect * down


def type_validity(model, row, prior_row=None):
    """Can this site type be built here (tier points, prerequisites)?"""
    if model is not None:
        tier2, tier3 = model["tier_points"]["tier2"], model["tier_points"]["tier3"]
        if prior_row is not None:
            if prior_row["needs"]["tier"] == 2:
                tier2 += prior_row["needs"]["count"]
            if prior_row["needs"]["tier"] == 3:
                tier3 += prior_row["needs"]["count"]
        if row["needs"]["tier"] == 2 and tier2 < row["needs"]["count"]:
            return {"valid": False, "message": "Not enough Tier 2 points", "unlocks": row.get("unlocks") or []}
        if row["needs"]["tier"] == 3 and tier3 < row["needs"]["count"]:
            return {"valid": False, "message": "Not enough Tier 3 points", "unlocks": row.get("unlocks") or []}
    if row.get("preReq"):
        needed = _data()["pre_reqs"].get(row["preReq"], [])
        valid = model is None or any(site["status"] != "demolish" and any(site["build_type"].startswith(item) for item in needed)
                                     for site in model["sites"])
        return {"valid": valid, "message": "" if valid else f"Requires {_PRE_REQ_NAMES.get(row['preReq'], row['preReq'])}",
                "unlocks": row.get("unlocks") or []}
    return {"valid": True, "message": "", "unlocks": row.get("unlocks") or []}


_PRE_REQ_NAMES = {"satellite": "a satellite installation", "comms": "a communications installation",
                  "settlementAgr": "an agricultural settlement", "installationAgr": "a space farm",
                  "installationMil": "a military installation", "outpostMining": "a mining outpost installation",
                  "relay": "a relay installation", "settlementBio": "a bio research settlement",
                  "settlementTourist": "a tourism settlement", "settlementMilitary": "a military settlement",
                  "settlementExtraction": "an extraction settlement"}


def build_model(raw_sys, use_incomplete=False, buff_nerf=True):
    """The planner's view of a system: per site its type, links, economies
    (with the reasons), taxed tier cost; for the system its tier points,
    score, effects, economies and unlocks."""
    model = _Model(raw_sys or {}, use_incomplete, buff_nerf)
    sites = []
    for site in model.sites:
        links = site.links or {}
        sites.append({
            "id": site.id, "name": site.name, "body_num": site.body_num, "body": site.body.name if site.body else "",
            "build_type": site.build_type, "status": site.status, "build_id": site.raw.get("buildId"),
            "market_id": site.raw.get("marketId"), "in_calc": site.id in model.calc_ids,
            "type": {"name": site.type["displayName2"], "class": site.type["buildClass"], "tier": site.type["tier"],
                     "orbital": site.type["orbital"], "pad": site.type["padSize"], "inf": site.type["inf"],
                     "fixed": site.type.get("fixed"), "score": site.type.get("score", 0) or 0,
                     "needs": site.type["needs"], "gives": site.type["gives"], "haul": site.type.get("haul", 0),
                     "effects": {key: value for key, value in (site.type.get("effects") or {}).items() if value}},
            "calc_needs": site.calc_needs,
            "primary_economy": site.primary_economy,
            "economies": {key: value for key, value in (site.economies or {}).items() if value > 0},
            "audit": site.audit or [],
            "links": {"economies": links.get("economies", {}),
                      "strong": [other.name for other in links.get("strong", ())],
                      "weak": [other.name for other in links.get("weak", ())]} if links else None,
            "parent_link": site.parent_link.name if site.parent_link else None,
            "body_primary": bool(site.body and (site is site.body.orbital_primary or site is site.body.surface_primary)),
        })
    return {
        "name": model.sys.name, "score": model.score, "tier_points": model.tier_points, "tax_count": model.tax_count,
        "effects": model.effects, "economies": model.system_economies, "unlocks": model.unlocks,
        "sites": sites, "calc_ids": sorted(model.calc_ids), "use_incomplete": use_incomplete, "buff_nerf": buff_nerf,
        "bodies": [{"num": body.get("num"), "name": body.get("name"), "type": body.get("type"),
                    "sub_type": body.get("subType") or "", "features": list(body.get("features") or ()),
                    "dist_ls": body.get("distLS"), "parents": list(body.get("parents") or ())}
                   for body in model.sys.bodies],
    }


def snapshot(raw_sys, favourite=None):
    """What the website saves with a system's sites: completed sites only,
    with the buff/nerf on."""
    full = _Model(raw_sys, False, True)
    return {
        "architect": raw_sys.get("architect"), "id64": raw_sys.get("id64"), "v": raw_sys.get("v"),
        "name": raw_sys.get("name"), "pos": raw_sys.get("pos"), "tierPoints": full.tier_points,
        "sumEffects": full.effects, "sites": list(raw_sys.get("sites") or ()), "pop": raw_sys.get("pop"),
        "stale": False, "score": full.score, "fav": favourite,
    }


def predict_surface_slots(body):
    """Likely ground slots on a body (the website's estimate); -1 unknown."""
    if (body.get("type") or "un") == "un":
        return -1
    features = set(body.get("features") or ())
    if (body.get("temp") or 0) > 700 or (body.get("gravity") or 0) > 2.7 or "landable" not in features:
        return 0
    radius = body.get("radius") or 0
    slots = 1 if radius < 1500 else 2 if radius < 3750 else 3 if radius < 6000 else 4
    if body.get("subType") == "High metal content world":
        slots += 1
    if "terraformable" in features:
        slots += 1
    if "volcanism" in features or "geo" in features:
        slots += 1
    if "atmosphere" in features:
        slots += 2
    return min(slots, 7)


def haul_estimate(build_types):
    """Approximate cargo to build these layouts (the website's figures)."""
    total = 0
    for build_type in build_types:
        total += site_type(build_type).get("haul", 0) or 0
    return total
