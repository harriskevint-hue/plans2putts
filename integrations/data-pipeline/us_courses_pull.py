#!/usr/bin/env python3
"""
ShadesCaddie / Plans2Putts — National golf-course directory RAW pull (OSM/Overpass).

Pulls golf-course records (leisure=golf_course) for all 50 US states + DC in one
pass and writes a single CSV. Standard-library only. The course directory changes
slowly, so this is an occasional refresh (once or twice a year), not a runtime app
feature — the app reads the pre-loaded database and never calls Overpass at runtime.

RAW pull ONLY. It does NOT clean, de-dupe, or apply the practice-facility filter —
all of that happens DOWNSTREAM at load time (clean the CSV, then import with the
loader; see REFRESH-COURSE-DIRECTORY.md). It FLAGS probable duplicates rather than
deleting them, because at national scale you can't hand-verify every collision the
way Washington was checked.

THE HARD RULE: `lat`/`lon` here are OSM PROPERTY points (course centroids), which map
to property_lat/lng — NOT per-hole coordinates. No per-hole geometry is read or written.

=============================================================================
WHERE THIS RUNS: LOCALLY (not in the Claude Code web environment).
=============================================================================
The cloud environment's network policy blocks overpass-api.de (HTTP 403). Run this on
a normal machine with internet, then clean the CSV and import it with the loader.

Output: writes to integrations/data-pipeline/data/us_courses.csv by default (the same
data/ directory the loader reads from), plus a printed summary. The raw output is a
regenerable artifact and is gitignored; the cleaned CSV is what gets committed.

Usage:
    python3 us_courses_pull.py                 # all 50 + DC -> data/us_courses.csv
    python3 us_courses_pull.py --states WA,OR  # specific states
    python3 us_courses_pull.py --out PATH --delay 5

This makes ~51 sequential Overpass requests with polite delays (~10-25 min). Transient
rate-limit/timeout responses are retried automatically.
"""

import argparse
import csv
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "ShadesCaddie-DataPipeline/0.1 (national course directory pull; contact harriskevint@gmail.com)"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "data", "us_courses.csv")
DELAY_BETWEEN_STATES = 5          # seconds, to be polite to the public endpoint
DUP_DISTANCE_KM = 1.0             # same-name records closer than this = probable duplicate
CSV_COLUMNS = ["state", "osm_type", "osm_id", "name", "lat", "lon",
               "address", "city", "website", "flag"]

STATES = {
    "US-AL": "Alabama", "US-AK": "Alaska", "US-AZ": "Arizona", "US-AR": "Arkansas",
    "US-CA": "California", "US-CO": "Colorado", "US-CT": "Connecticut", "US-DE": "Delaware",
    "US-FL": "Florida", "US-GA": "Georgia", "US-HI": "Hawaii", "US-ID": "Idaho",
    "US-IL": "Illinois", "US-IN": "Indiana", "US-IA": "Iowa", "US-KS": "Kansas",
    "US-KY": "Kentucky", "US-LA": "Louisiana", "US-ME": "Maine", "US-MD": "Maryland",
    "US-MA": "Massachusetts", "US-MI": "Michigan", "US-MN": "Minnesota", "US-MS": "Mississippi",
    "US-MO": "Missouri", "US-MT": "Montana", "US-NE": "Nebraska", "US-NV": "Nevada",
    "US-NH": "New Hampshire", "US-NJ": "New Jersey", "US-NM": "New Mexico", "US-NY": "New York",
    "US-NC": "North Carolina", "US-ND": "North Dakota", "US-OH": "Ohio", "US-OK": "Oklahoma",
    "US-OR": "Oregon", "US-PA": "Pennsylvania", "US-RI": "Rhode Island", "US-SC": "South Carolina",
    "US-SD": "South Dakota", "US-TN": "Tennessee", "US-TX": "Texas", "US-UT": "Utah",
    "US-VT": "Vermont", "US-VA": "Virginia", "US-WA": "Washington", "US-WV": "West Virginia",
    "US-WI": "Wisconsin", "US-WY": "Wyoming", "US-DC": "District of Columbia",
}

QUERY_TMPL = """
[out:json][timeout:120];
area["ISO3166-2"="{code}"]->.s;
(
  node["leisure"="golf_course"](area.s);
  way["leisure"="golf_course"](area.s);
  relation["leisure"="golf_course"](area.s);
);
out center tags;
"""


def fetch(query, retries=3):
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(OVERPASS_URL, data=data, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 504) and attempt < retries:
                wait = 15 * (attempt + 1)
                print(f"    Overpass {e.code}; waiting {wait}s and retrying...")
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            if attempt < retries:
                print(f"    Network error ({e.reason}); retrying in 10s...")
                time.sleep(10)
                continue
            raise
    raise RuntimeError("Overpass request failed after retries")


def coords_of(el):
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    c = el.get("center")
    if c:
        return c.get("lat"), c.get("lon")
    return None, None


def address_of(t):
    parts = [t.get("addr:housenumber"), t.get("addr:street"), t.get("addr:city"),
             t.get("addr:state"), t.get("addr:postcode")]
    return " ".join(p for p in parts if p).strip()


def dist_km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def flag_duplicates(all_rows):
    """Flag (not delete) probable duplicates: same name + same state, centroids
    within DUP_DISTANCE_KM. NOTE: name+proximity only — name-variation duplicates
    (e.g. Sky Ridge) are caught downstream at load-time review, not here."""
    by_key = {}
    for r in all_rows:
        if r["name"].strip() and r["lat"] != "" and r["lon"] != "":
            by_key.setdefault((r["state"], r["name"].strip().lower()), []).append(r)
    dup_clusters = 0
    for grp in by_key.values():
        if len(grp) < 2:
            continue
        close = any(
            dist_km((float(grp[a]["lat"]), float(grp[a]["lon"])),
                    (float(grp[b]["lat"]), float(grp[b]["lon"]))) < DUP_DISTANCE_KM
            for a in range(len(grp)) for b in range(a + 1, len(grp)))
        if close:
            dup_clusters += 1
            ids = ", ".join(f"{x['osm_type']}/{x['osm_id']}" for x in grp)
            for x in grp:
                x["flag"] = f"probable duplicate — review ({ids})"

    for r in all_rows:
        if not r["name"].strip():
            r["flag"] = (r["flag"] + "; " if r["flag"] else "") + "missing name"
        if r["lat"] == "" or r["lon"] == "":
            r["flag"] = (r["flag"] + "; " if r["flag"] else "") + "missing coords"
    return dup_clusters


def pull(codes, out_path, delay):
    all_rows, empty_states = [], []
    for i, code in enumerate(codes, 1):
        name = STATES[code]
        print(f"[{i:>2}/{len(codes)}] {name} ({code})...", end=" ", flush=True)
        try:
            result = fetch(QUERY_TMPL.format(code=code))
        except Exception as e:  # noqa: BLE001 - report and keep going
            print(f"FAILED: {e}")
            empty_states.append(name)
            continue
        els = result.get("elements", [])
        for el in els:
            tags = el.get("tags", {})
            lat, lon = coords_of(el)
            all_rows.append({
                "state": name,
                "osm_type": el.get("type", ""),
                "osm_id": el.get("id", ""),
                "name": tags.get("name", ""),
                "lat": lat if lat is not None else "",
                "lon": lon if lon is not None else "",
                "address": address_of(tags),
                "city": tags.get("addr:city", ""),
                "website": tags.get("website", "") or tags.get("contact:website", ""),
                "flag": "",
            })
        print(f"{len(els)} courses")
        if not els:
            empty_states.append(name)
        if i < len(codes):
            time.sleep(delay)

    dup_clusters = flag_duplicates(all_rows)
    all_rows.sort(key=lambda r: (r["state"], r["name"] == "", r["name"].lower()))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(all_rows)

    total = len(all_rows)
    missing_addr = sum(1 for r in all_rows if not r["address"])
    missing_coord = sum(1 for r in all_rows if r["lat"] == "" or r["lon"] == "")
    unnamed = sum(1 for r in all_rows if not r["name"].strip())

    print("\n" + "=" * 52)
    print("US COURSE DIRECTORY PULL  -  SUMMARY")
    print("=" * 52)
    print(f"Total course records:        {total}")
    print(f"States with 0 results:       {len(empty_states)}" +
          (f"  -> {', '.join(empty_states)}" if empty_states else ""))
    print(f"Rows missing an address:     {missing_addr}  ({100*missing_addr//total if total else 0}%)")
    print(f"Rows missing coordinates:    {missing_coord}")
    print(f"Rows with no name:           {unnamed}")
    print(f"Probable-duplicate clusters: {dup_clusters} (rows flagged, not deleted)")
    print(f"\nWrote {total} rows to {out_path}")
    print("Raw pull only. Next: clean/dedup the CSV, then import with the loader.")
    print("See REFRESH-COURSE-DIRECTORY.md.")


def main(argv=None):
    p = argparse.ArgumentParser(description="National RAW OSM course pull (all 50 states + DC).")
    p.add_argument("--states", help="Comma-separated state codes (e.g. WA,OR). Default: all 50 + DC.")
    p.add_argument("--out", default=DEFAULT_OUT, help=f"Output CSV path (default: {DEFAULT_OUT}).")
    p.add_argument("--delay", type=float, default=DELAY_BETWEEN_STATES,
                   help="Seconds between state queries (be polite).")
    args = p.parse_args(argv)

    if args.states:
        codes = []
        for raw in args.states.split(","):
            code = raw.strip().upper()
            code = code if code.startswith("US-") else f"US-{code}"
            if code not in STATES:
                print(f"Unknown state code: {raw}")
                return 1
            codes.append(code)
    else:
        codes = list(STATES)

    print(f"RAW pull for {len(codes)} jurisdiction(s) -> {args.out}")
    print("(Runs LOCALLY; overpass-api.de is blocked in the Claude Code web env.)\n")
    pull(codes, args.out, args.delay)
    return 0


if __name__ == "__main__":
    sys.exit(main())
