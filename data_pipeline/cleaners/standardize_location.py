"""
standardize_location.py

Standardizes messy job-location strings into:

    {
        "location": canonical city/location,
        "region": canonical Philippine region or None
    }

REBUILT to use ph_locations.json — a lookup derived from the official PSA
PSGC (Philippine Standard Geographic Code), covering all ~1,600+ PH
cities/municipalities, instead of a hand-typed dict of ~30 entries.

Run data_pipeline/reference/build_location_lookup.py first (or after
pulling fresher PSGC source data) to generate ph_locations.json.

Handles PhilJobNet formats such as:

    "City Of Makati, Ncr, Fourth District"
    "City Of Santa Rosa, Laguna"
    "Mandaue City, Cebu"
    "Cebu City (Capital), Cebu"
    "San Pedro, Laguna"
"""

import json
import re
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parent.parent / "reference"
LOOKUP_PATH = REFERENCE_DIR / "ph_locations.json"


def _load_lookup() -> dict:
    if not LOOKUP_PATH.exists():
        raise FileNotFoundError(
            f"{LOOKUP_PATH} not found. Run "
            f"data_pipeline/reference/build_location_lookup.py first."
        )
    return json.loads(LOOKUP_PATH.read_text(encoding="utf-8"))


_LOOKUP = _load_lookup()
BY_CITY_PROVINCE = _LOOKUP["by_city_province"]
UNAMBIGUOUS_BY_CITY = _LOOKUP["unambiguous_by_city"]
AMBIGUOUS_CITIES = set(_LOOKUP["ambiguous_cities"])
PROVINCES_BY_NAME = _LOOKUP.get("provinces_by_name", {})


# ---------------------------------------------------------------------------
# OVERSEAS (OFW postings) — checked before any PH-specific normalization
# ---------------------------------------------------------------------------

OVERSEAS_LOCATIONS = {
    "new zealand", "australia", "canada", "united states", "usa",
    "united states of america", "uk", "united kingdom", "great britain",
    "japan", "singapore", "hong kong", "hongkong", "taiwan",
    "taiwan, r.o.c.", "taiwan roc", "south korea", "korea", "germany",
    "saudi arabia", "united arab emirates", "uae", "qatar", "kuwait",
    "bahrain", "oman", "dubai", "abu dhabi", "riyadh", "jeddah",
    "malaysia", "brunei", "italy", "spain", "ireland", "netherlands",
    "poland", "israel", "cyprus", "greece", "china", "vietnam",
    "thailand", "indonesia", "papua new guinea", "papaua new guinea",
    "micronesia", "micronesia(federated states of)",
    "micronesia (federated states of)", "mongolia", "slovakia",
    "hungary", "finland", "lithuania", "morocco", "guyana", "cambodia",
    "myanmar", "fiji", "france", "switzerland", "norway", "sweden",
    "denmark", "austria", "portugal", "russia", "turkey", "egypt",
    "libya", "nigeria", "south africa", "india", "pakistan",
    "bangladesh", "sri lanka", "mexico", "brazil", "chile", "argentina",
    "papua new guinea (independent state of)",
}

# Whole continents/regions used loosely on PhilJobNet postings instead of
# a specific country. Not a "location" in the PSGC sense, so we can't
# assign a province/region, but they are unambiguously overseas.
OVERSEAS_CONTINENTS = {
    "europe", "middle east", "asia", "africa", "oceania",
    "north america", "south america",
}

REMOTE_PATTERNS = re.compile(
    r"\b(remote|work from home|wfh|home[- ]based)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------------------------

def clean_location_string(raw: str) -> str:
    """Clean common PhilJobNet location formatting without guessing the city."""
    if not raw:
        return ""

    text = str(raw).strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r",?\s*philippines\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r",?\s*metro manila\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r",?\s*ncr\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*city\s+of\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r",?\s*(first|second|third|fourth|fifth|sixth|seventh)\s+district\s*$",
        "", text, flags=re.IGNORECASE,
    )
    text = re.sub(r"\s*\(capital\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"[,\s]+$", "", text)
    return text.strip()


def normalize_key(text: str) -> str:
    text = text.lower().strip()
    replacements = {"ñ": "n", "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def _strip_city_suffix(key: str) -> str:
    return re.sub(r"\s+city$", "", key).strip()


def _city_variants(key: str) -> list[str]:
    """
    Try a name as-is, with 'city' stripped, and with 'city' appended —
    the source data isn't consistent about which form it stores
    ("Taguig City" vs "Cebu City" vs just "Baguio" for some entries),
    so we check all three rather than guessing which one applies.
    """
    variants = [key]
    stripped = _strip_city_suffix(key)
    if stripped != key:
        variants.append(stripped)
    if not key.endswith(" city"):
        variants.append(f"{key} city")
    return variants


def _lookup_city_province(city_key: str, province_key: str):
    """Try the precise (city, province) lookup across name variants."""
    for c in _city_variants(city_key):
        combo = f"{c}|{province_key}"
        if combo in BY_CITY_PROVINCE:
            city, region = BY_CITY_PROVINCE[combo]
            return {"location": city, "region": region}
    return None


def _lookup_city_only(city_key: str):
    """
    Try the unambiguous city-only lookup. If the name is known but
    ambiguous nationwide (e.g. 'Santa Rosa'), we deliberately do NOT
    guess — return a flag instead of a silently wrong region.
    """
    for c in _city_variants(city_key):
        if c in UNAMBIGUOUS_BY_CITY:
            city, region = UNAMBIGUOUS_BY_CITY[c]
            return {"location": city, "region": region}
        if c in AMBIGUOUS_CITIES:
            return {"location": c.title(), "region": "Ambiguous"}
    return None


def _lookup_province_only(key: str):
    """Fallback for postings that give just a province, no city (e.g. 'Pampanga')."""
    if key in PROVINCES_BY_NAME:
        province, region = PROVINCES_BY_NAME[key]
        return {"location": province, "region": region}
    return None


# ---------------------------------------------------------------------------
# LEGACY REGION NAME FIXUP
# ---------------------------------------------------------------------------
#
# ph_locations.json is a static snapshot of PSGC data and may lag behind
# renamed regions. ARMM was replaced by BARMM (Bangsamoro Autonomous
# Region in Muslim Mindanao) in 2019 — remap here so a stale snapshot
# doesn't silently report an abolished region name in current-day output.

_REGION_NAME_FIXES = {
    "armm": "BARMM",
}


def _fix_region_name(region):
    if region is None:
        return None
    fixed = _REGION_NAME_FIXES.get(region.strip().lower())
    return fixed if fixed else region


def _apply_region_fixup(match):
    if match and match.get("region"):
        match["region"] = _fix_region_name(match["region"])
    return match


# ---------------------------------------------------------------------------
# MAIN FUNCTION
# ---------------------------------------------------------------------------

def standardize_location(raw: str) -> dict:
    if raw is None:
        return {"location": "Unknown", "region": None}

    raw = str(raw).strip()
    if not raw:
        return {"location": "Unknown", "region": None}

    if REMOTE_PATTERNS.search(raw):
        return {"location": "Remote", "region": None}

    normalized_raw = normalize_key(raw)
    if normalized_raw in OVERSEAS_LOCATIONS:
        return {"location": raw.strip().title(), "region": "Overseas"}
    if normalized_raw in OVERSEAS_CONTINENTS:
        # A continent-level posting ("Europe", "Middle East") — genuinely
        # overseas but with no single country to name as the location.
        return {"location": "Overseas (Unspecified)", "region": "Overseas"}

    cleaned = clean_location_string(raw)
    if not cleaned:
        return {"location": "Unknown", "region": None}

    key = normalize_key(cleaned)
    parts = [p.strip() for p in key.split(",") if p.strip()]

    # Case 1: "City, Province" — use the precise lookup first.
    if len(parts) >= 2:
        city_key, province_key = parts[0], parts[1]
        match = _lookup_city_province(city_key, province_key)
        if match:
            return match

    # Case 2: city name alone (or precise lookup missed) — try city-only.
    city_key = parts[0] if parts else key
    match = _lookup_city_only(city_key)
    if match:
        return match

    # Also try scanning the full string for any known city name, in case
    # of formats like "Some Barangay, Mandaue City, Cebu" where the city
    # isn't the first comma-segment.
    for part in parts:
        match = _lookup_city_only(part)
        if match:
            return match

    # Case 3: maybe it's a province name with no city at all
    # (e.g. "Pampanga", "Negros Occidental").
    match = _lookup_province_only(city_key)
    if match:
        return match
    for part in parts:
        match = _lookup_province_only(part)
        if match:
            return match

    # Unmapped — flag rather than guess. Check for this in your quality
    # report (unmapped_locations) and inspect data/processed/ periodically.
    return {"location": cleaned.title(), "region": None}