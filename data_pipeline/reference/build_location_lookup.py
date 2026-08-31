"""
build_location_lookup.py

Builds ph_locations.json — a lookup table of every Philippine city and
municipality, derived from the official PSGC (Philippine Standard
Geographic Code), published by the PSA. This replaces the hand-typed
CITY_REGION_MAP that had to be extended one entry at a time.

Source data: jgngo/psgc-data on GitHub, a cleaned CSV mirror of the PSA's
official PSGC publication. region.csv / province.csv / muncity.csv are
already downloaded into this folder — re-run download_source_data() if
you want a fresher copy.

WHY THIS IS TRICKIER THAN IT LOOKS:
1. NCR cities (Makati, Taguig, Pasig, etc.) aren't in muncity.csv — the
   PSGC treats each NCR city as its own "province"-level entry, so they
   have to be pulled from province.csv separately.
2. 109 city/municipality names are NOT unique across the Philippines
   (e.g. "Santa Rosa" exists in Ilocos Region AND in Laguna; "San Mateo"
   exists in two different regions). A naive name->region dict silently
   picks the wrong one for these. This script keeps a "city + province"
   lookup for precise matches, and a separate "city alone" lookup that
   ONLY includes names that are unambiguous nationwide.

Run this once (or whenever you want to refresh from source):
    python data_pipeline/reference/build_location_lookup.py
"""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parent

# PSGC region descriptions -> the shorter names already used elsewhere
# in this project (matches what you've been using in CITY_REGION_MAP).
REGION_NAME_MAP = {
    "Region I (Ilocos Region)": "Ilocos Region",
    "Region II (Cagayan Valley)": "Cagayan Valley",
    "Region III (Central Luzon)": "Central Luzon",
    "Region IV-A (CALABARZON)": "CALABARZON",
    "Region V (Bicol Region)": "Bicol Region",
    "Region VI (Western Visayas)": "Western Visayas",
    "Region VII (Central Visayas)": "Central Visayas",
    "Region VIII (Eastern Visayas)": "Eastern Visayas",
    "Region IX (Zamboanga Peninsula)": "Zamboanga Peninsula",
    "Region X (Northern Mindanao)": "Northern Mindanao",
    "Region XI (Davao Region)": "Davao Region",
    "Region XII (SOCCSKSARGEN)": "SOCCSKSARGEN",
    "National Capital Region (NCR)": "NCR",
    "Cordillera Administrative Region (CAR)": "Cordillera Administrative Region",
    "Autonomous Region in Muslim Mindanao (ARMM)": "ARMM",
    "Region XIII (Caraga)": "Caraga",
    "MIMAROPA Region": "MIMAROPA",
}


def read_csv(path: Path) -> list[dict]:
    # cp1252, not utf-8 — the source data has characters (ñ, etc.) that
    # break under strict utf-8 decoding.
    with open(path, encoding="cp1252") as f:
        return list(csv.DictReader(f))


def normalize(text: str) -> str:
    text = text.lower().strip()
    replacements = {"ñ": "n", "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def strip_prefix(name: str) -> str:
    """'City of Makati' -> 'Makati'; leaves names without the prefix alone."""
    if name.lower().startswith("city of "):
        return name[len("city of "):].strip()
    return name.strip()


def strip_suffixes(name: str) -> str:
    """Remove '(Capital)' and similar annotations baked into PSGC names."""
    name = re.sub(r"\s*\(capital\)", "", name, flags=re.IGNORECASE)
    return name.strip()


def build():
    region_rows = read_csv(REFERENCE_DIR / "region.csv")
    province_rows = read_csv(REFERENCE_DIR / "province.csv")
    muncity_rows = read_csv(REFERENCE_DIR / "muncity.csv")

    # IMPORTANT: this source file's province_id / region_id foreign keys
    # are unreliable — several rows have IDs that coincidentally collide
    # with an unrelated province (e.g. "City Of Makati" links to Nueva
    # Ecija's province_id, "Cebu City" resolves to Cagayan Valley, etc.).
    # Instead of trusting those columns, we derive region/province purely
    # from the PSGC `code` field itself, which is the actual official
    # hierarchical identifier: the first 2 digits ALWAYS encode the region,
    # and the first 4 digits ALWAYS encode the province. This sidesteps
    # every bad foreign key in the file.

    # region code prefix (2 digits) -> region name
    region_by_code = {}
    for r in region_rows:
        prefix = r["code"][:2]
        region_by_code[prefix] = REGION_NAME_MAP.get(r["description"], r["description"])

    # province code prefix (4 digits) -> (province name, region name)
    province_by_code = {}
    for p in province_rows:
        prefix = p["code"][:4]
        region_name = region_by_code.get(p["code"][:2])
        province_by_code[prefix] = (p["description"].strip(), region_name)

    # entries: list of (canonical_city_name, province_name_or_None, region_name)
    entries = []

    # NCR cities: their PSGC codes start with "13" (NCR's region code).
    # Some are listed in province.csv (as pseudo-provinces), so pull them
    # from there using the code prefix — not the region_id column.
    ncr_city_names = set()
    for p in province_rows:
        if p["code"][:2] == "13":
            city_name = strip_suffixes(strip_prefix(p["description"]))
            entries.append((city_name, None, "NCR"))
            ncr_city_names.add(normalize(city_name))

    # Everyone else: muncity.csv, with province/region derived from the
    # row's own code prefix (not the province_id column).
    skipped_ncr_dupes = 0
    unresolved = 0
    for m in muncity_rows:
        code = m["code"]
        province_info = province_by_code.get(code[:4])
        if province_info is None:
            unresolved += 1
            continue

        province_name, region_name = province_info
        city_name = strip_suffixes(strip_prefix(m["description"]))

        if normalize(city_name) in ncr_city_names:
            skipped_ncr_dupes += 1
            continue

        entries.append((city_name, province_name, region_name))

    if skipped_ncr_dupes:
        print(f"Skipped {skipped_ncr_dupes} muncity.csv rows that duplicated an NCR city.")
    if unresolved:
        print(f"Warning: {unresolved} muncity.csv rows had a code prefix with no "
              f"matching province — check these manually if the count is large.")

    # --- Build the two lookup structures ---

    # 1. Precise: (city, province) -> (canonical city, region)
    by_city_province = {}
    for city, province, region in entries:
        if province is None:
            continue
        key = f"{normalize(city)}|{normalize(province)}"
        by_city_province[key] = [city, region]

    # 2. City-alone: only for names that are unambiguous nationwide.
    name_to_regions = defaultdict(set)
    name_to_canonical = {}
    for city, province, region in entries:
        key = normalize(city)
        name_to_regions[key].add(region)
        name_to_canonical[key] = city

    unambiguous_by_city = {}
    ambiguous_cities = []
    for key, region_set in name_to_regions.items():
        if len(region_set) == 1:
            unambiguous_by_city[key] = [name_to_canonical[key], next(iter(region_set))]
        else:
            ambiguous_cities.append(key)

    # 3. Province-only fallback: PhilJobNet sometimes lists just a province
    # name with no city (e.g. "Negros Occidental", "Pampanga" alone).
    # These never appear in muncity.csv (a province isn't a municipality),
    # so they need their own lookup, derived the same code-prefix way.
    provinces_by_name = {}
    for p in province_rows:
        region_name = region_by_code.get(p["code"][:2])
        province_name = strip_suffixes(strip_prefix(p["description"]))
        provinces_by_name[normalize(province_name)] = [province_name, region_name]

    output = {
        "by_city_province": by_city_province,
        "unambiguous_by_city": unambiguous_by_city,
        "ambiguous_cities": sorted(ambiguous_cities),
        "provinces_by_name": provinces_by_name,
    }

    out_path = REFERENCE_DIR / "ph_locations.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Built lookup with:")
    print(f"  {len(by_city_province):,} precise (city, province) entries")
    print(f"  {len(unambiguous_by_city):,} unambiguous city-only entries")
    print(f"  {len(ambiguous_cities):,} ambiguous city names (need province context to resolve)")
    print(f"  {len(provinces_by_name):,} province-only entries")
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    build()
