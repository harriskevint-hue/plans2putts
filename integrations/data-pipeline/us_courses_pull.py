#!/usr/bin/env python3
"""
ShadesCaddie / Plans2Putts — Canonical RAW course pull (all 50 states + DC).

Pulls golf-course entries (leisure=golf_course) from OpenStreetMap via the Overpass
API for every US state and the District of Columbia, and writes ONE RAW CSV per
state. This is the canonical first step of refreshing the course directory.

RAW means: minimal transformation. Names + addresses + the OSM property point
(centroid) + website, as OSM has them. NO cleaning, NO de-dupe, NO practice-facility
filtering here — all of that happens DOWNSTREAM at load time (see
REFRESH-COURSE-DIRECTORY.md and load_washington_csv.py). Keeping the pull raw makes
it re-runnable and keeps the cleaning auditable/separate.

THE HARD RULE: the `lat`/`lon` written here are OSM PROPERTY points (course
centroids) -> they map to property_lat/lng, which are NOT per-hole coordinates. This
script does NOT read or emit any per-hole geometry (golf=green/tee/hazard).

=============================================================================
WHERE THIS RUNS: LOCALLY (not in the Claude Code web environment).
=============================================================================
The cloud environment's network policy blocks overpass-api.de (HTTP 403), so run
this on a machine with internet access, commit the resulting cleaned CSV(s) as the
seed, and load them with the loader. Use --print-query to inspect a query with no
network, and --list-states to see coverage.

Usage:
  python3 us_courses_pull.py --list-states
  python3 us_courses_pull.py --print-query WA
  python3 us_courses_pull.py --states WA,OR        # pull specific states
  python3 us_courses_pull.py                        # pull ALL 50 + DC (be patient/polite)
  python3 us_courses_pull.py --out-dir data/raw --delay 3
"""

import argparse
import csv
import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
USER_AGENT = "ShadesCaddie-DataPipeline/0.1 (golf course directory build; contact harriskevint@gmail.com)"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "data", "raw")
RAW_COLUMNS = ["osm_type", "osm_id", "name", "lat", "lon", "address", "city", "website", "state"]

# 50 states + DC, with ISO 3166-2 codes used by OSM boundaries.
STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


def build_query(state_code):
    return (f'[out:json][timeout:180];\n'
            f'area["ISO3166-2"="US-{state_code}"][admin_level=4]->.st;\n'
            f'(\n  nwr["leisure"="golf_course"](area.st);\n);\n'
            f'out tags center;')


def fetch_overpass(query):
    """LIVE network call (gated by network policy; run locally)."""
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(OVERPASS_ENDPOINT, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.load(resp).get("elements", [])


def _assemble_address(tags):
    street = " ".join(p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p)
    parts = [street, tags.get("addr:city"), tags.get("addr:state"), tags.get("addr:postcode")]
    line = " ".join(p for p in parts if p).strip()
    return line or ""


def element_to_row(el, state_code):
    tags = el.get("tags", {})
    center = el.get("center") or {}
    return {
        "osm_type": el.get("type"),
        "osm_id": el.get("id"),
        "name": (tags.get("name") or "").strip(),
        "lat": center.get("lat", el.get("lat")),
        "lon": center.get("lon", el.get("lon")),
        "address": _assemble_address(tags),
        "city": tags.get("addr:city") or "",
        "website": tags.get("website") or tags.get("contact:website") or "",
        "state": state_code,
    }


def pull_state(state_code, out_dir):
    elements = fetch_overpass(build_query(state_code))
    rows = [element_to_row(e, state_code) for e in elements if e.get("tags")]
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{state_code}_courses_raw.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=RAW_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return out_path, len(rows)


def main(argv=None):
    p = argparse.ArgumentParser(description="Canonical RAW OSM course pull for all 50 states + DC.")
    p.add_argument("--states", help="Comma-separated state codes (default: all 50 + DC).")
    p.add_argument("--out-dir", default=DEFAULT_OUT, help=f"Output dir (default: {DEFAULT_OUT}).")
    p.add_argument("--delay", type=float, default=3.0, help="Seconds between state queries (be polite).")
    p.add_argument("--list-states", action="store_true", help="List covered states and exit.")
    p.add_argument("--print-query", metavar="STATE", help="Print the Overpass query for STATE and exit (no network).")
    args = p.parse_args(argv)

    if args.list_states:
        print(f"{len(STATES)} jurisdictions (50 states + DC):")
        for code, name in STATES.items():
            print(f"  US-{code}  {name}")
        return 0

    if args.print_query:
        code = args.print_query.upper()
        if code not in STATES:
            print(f"Unknown state code: {code}")
            return 1
        print(build_query(code))
        return 0

    codes = [c.strip().upper() for c in args.states.split(",")] if args.states else list(STATES)
    unknown = [c for c in codes if c not in STATES]
    if unknown:
        print(f"Unknown state code(s): {', '.join(unknown)}")
        return 1

    print(f"RAW pull starting for {len(codes)} jurisdiction(s). Output -> {args.out_dir}")
    print("(Runs LOCALLY; overpass-api.de is blocked in the Claude Code web env.)\n")
    total = 0
    for i, code in enumerate(codes):
        try:
            path, n = pull_state(code, args.out_dir)
            total += n
            print(f"  US-{code} {STATES[code]:22} -> {n:5d} raw rows  ({os.path.basename(path)})")
        except Exception as e:  # noqa: BLE001 - report cleanly, keep going
            print(f"  US-{code} {STATES[code]:22} -> ERROR: {type(e).__name__}: {e}")
        if i < len(codes) - 1:
            time.sleep(args.delay)  # Overpass fair-use: one query at a time, spaced out
    print(f"\nDone. {total} raw rows across {len(codes)} jurisdiction(s).")
    print("Next: clean/dedup the raw CSV(s), then load with the loader. See REFRESH-COURSE-DIRECTORY.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
