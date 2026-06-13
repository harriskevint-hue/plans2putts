#!/usr/bin/env python3
"""
National golf-course directory pull from OpenStreetMap (Overpass API).

Runs every US state + DC in one pass and writes a single CSV. Standalone,
standard-library only, intended to run on a normal laptop with internet access.
The course directory changes slowly, so this is an occasional refresh task
(once or twice a year), not something the app does at runtime.

What it produces:
  - us_courses.csv : one row per OSM golf-course record, with a `state` column
    and a `flag` column noting probable duplicates / missing data.
  - a printed summary (totals, missing-data counts, probable duplicates).

It FLAGS probable duplicates rather than deleting them, because at national
scale you can't hand-verify every collision the way we did for Washington.
Review the flagged rows, then decide what to collapse.

Usage:
    python us_courses_pull.py

This takes a while: it makes ~51 sequential Overpass requests with polite
delays, so expect roughly 10-25 minutes depending on Overpass load. Transient
rate-limit/timeout responses are retried automatically.

Requirements: Python 3.8+. No pip installs.
"""

import csv
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUTPUT_CSV = "us_courses.csv"
DELAY_BETWEEN_STATES = 5          # seconds, to be polite to the public endpoint
DUP_DISTANCE_KM = 1.0             # same-name records closer than this = probable duplicate

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
    req = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": "plans2putts-directory-pull/1.0 (periodic US course directory refresh)"},
    )
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


def main():
    all_rows = []
    empty_states = []
    for i, (code, name) in enumerate(STATES.items(), 1):
        print(f"[{i:>2}/{len(STATES)}] {name} ({code})...", end=" ", flush=True)
        try:
            result = fetch(QUERY_TMPL.format(code=code))
        except Exception as e:
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
        if i < len(STATES):
            time.sleep(DELAY_BETWEEN_STATES)

    # ---- flag probable duplicates (same name + same state, centroids < 1km) ----
    by_key = {}
    for r in all_rows:
        if r["name"].strip() and r["lat"] != "" and r["lon"] != "":
            by_key.setdefault((r["state"], r["name"].strip().lower()), []).append(r)
    dup_clusters = 0
    for grp in by_key.values():
        if len(grp) < 2:
            continue
        close = False
        for a in range(len(grp)):
            for b in range(a + 1, len(grp)):
                if dist_km((float(grp[a]["lat"]), float(grp[a]["lon"])),
                           (float(grp[b]["lat"]), float(grp[b]["lon"]))) < DUP_DISTANCE_KM:
                    close = True
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

    all_rows.sort(key=lambda r: (r["state"], r["name"] == "", r["name"].lower()))

    cols = ["state", "osm_type", "osm_id", "name", "lat", "lon", "address", "city", "website", "flag"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(all_rows)

    total = len(all_rows)
    missing_addr = sum(1 for r in all_rows if not r["address"])
    missing_coord = sum(1 for r in all_rows if r["lat"] == "" or r["lon"] == "")
    unnamed = sum(1 for r in all_rows if not r["name"].strip())

    print("\n" + "=" * 52)
    print("US COURSE DIRECTORY PULL  -  SUMMARY")
    print("=" * 52)
    print(f"Total course records:       {total}")
    print(f"States with 0 results:      {len(empty_states)}" +
          (f"  -> {', '.join(empty_states)}" if empty_states else ""))
    print(f"Rows missing an address:    {missing_addr}  ({100*missing_addr//total if total else 0}%)")
    print(f"Rows missing coordinates:   {missing_coord}")
    print(f"Rows with no name:          {unnamed}")
    print(f"Probable-duplicate clusters: {dup_clusters} (rows flagged, not deleted)")
    print(f"\nWrote {total} rows to {OUTPUT_CSV}")
    print("Review the flagged rows, then send the CSV back for cleanup/import.")


if __name__ == "__main__":
    main()
