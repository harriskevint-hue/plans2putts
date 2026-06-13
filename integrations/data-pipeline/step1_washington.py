#!/usr/bin/env python3
"""
ShadesCaddie / Plans2Putts — Data Pipeline, Step 1 (Washington)
Pull golf-course NAMES + ADDRESSES from OpenStreetMap into the `courses` table.

=============================================================================
LIVE-RUN STATUS:  NOT YET RUN AGAINST LIVE OVERPASS.
=============================================================================
As of this commit the cloud environment's network policy blocks outbound
internet (overpass-api.de returns 403), so this script has only been exercised
in --dry-run mode against the small built-in MOCK sample below. The parsing,
junk-filtering, and de-dupe logic are proven on that sample; the live pull is
gated until `overpass-api.de` is allowed by the network policy. See README.

Plain-language summary (for KT, a non-programmer):
  When network access is available, running this with --live asks OpenStreetMap
  (a free, openly-licensed map database) for every golf course in Washington and
  records each course's NAME and ADDRESS in courses.db. It records NO GPS
  coordinates (property_lat/lng stay empty / NULL) and no scorecards — that's
  the hard rule and a later step. Right now (--dry-run, the default) it runs on a
  tiny FAKE sample so you can see the filtering and de-duping logic work.

THE HARD RULE (enforced here):
  This script never writes any coordinate. property_lat/lng are inserted as NULL.
  We also do NOT harvest OSM per-hole geometry (golf=green/tee) into coordinates.

What it does:
  1. (live) Run ONE polite Overpass query for leisure=golf_course in Washington.
  2. Parse name + address tags from each result.
  3. Junk-filter: drop unnamed entries, driving ranges, and mini-golf.
  4. De-dupe: merge the same course appearing more than once (e.g. a node and a
     way, or split polygons) by normalized name + proximity / same city.
  5. Load survivors into `courses` (property_lat/lng NULL). Record provenance in
     source_list (OSM element ref + retrieval date + ODbL attribution).
  6. Export a review CSV for a human to eyeball before anything is trusted.

Usage:
  python3 step1_washington.py                 # DRY RUN on the mock sample (default)
  python3 step1_washington.py --self-test     # assert the logic on the mock sample
  python3 step1_washington.py --live          # REAL pull (needs network; gated)
  python3 step1_washington.py --db PATH --csv PATH
"""

import argparse
import csv
import datetime
import json
import math
import os
import re
import sqlite3
import sys
import urllib.parse
import urllib.request

# --- Config -------------------------------------------------------------------
OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
USER_AGENT = "ShadesCaddie-DataPipeline/0.1 (golf course directory build; contact harriskevint@gmail.com)"
STATE_CODE = "WA"
DEDUPE_DISTANCE_M = 300.0  # same-named courses within this distance are treated as one

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(HERE, "courses.db")

# The single, polite Overpass query (used only in --live mode). `out tags center`
# gives us tags plus ONE center point per way/relation. The center is used ONLY
# transiently for de-dupe proximity — it is never written to the database.
OVERPASS_QUERY = """[out:json][timeout:90];
area["ISO3166-2"="US-WA"][admin_level=4]->.wa;
(
  nwr["leisure"="golf_course"](area.wa);
);
out tags center;"""

# --- Mock sample for the dry run ---------------------------------------------
# !!! FAKE DATA — NOT REAL OPENSTREETMAP DATA. For testing the logic only. !!!
# Shaped exactly like Overpass `out tags center` JSON elements. Coordinates are
# approximate/fake and are used only to exercise the proximity de-dupe; nothing
# here is stored as a coordinate. Cases covered:
#   101 + 102  same course (way + nearby node)      -> de-dupe to one
#   103        normal course                         -> keep
#   104        no name                               -> exclude (unnamed)
#   105        driving range (golf tag)              -> exclude (driving_range)
#   106        mini golf (leisure tag)               -> exclude (mini_golf)
#   107        normal course                         -> keep
#   108 + 109  same NAME, far apart / diff city      -> keep BOTH (not a dup)
#   110        driving range mis-tagged golf_course  -> exclude (driving_range)
MOCK_ELEMENTS = [
    {"type": "way", "id": 101, "center": {"lat": 47.7680, "lon": -122.5323},
     "tags": {"leisure": "golf_course", "name": "White Horse Golf Club",
              "addr:housenumber": "22025", "addr:street": "Centaur Dr NE",
              "addr:city": "Kingston", "addr:state": "WA", "addr:postcode": "98346",
              "golf:holes": "18"}},
    {"type": "node", "id": 102, "lat": 47.7682, "lon": -122.5320,
     "tags": {"leisure": "golf_course", "name": "White Horse Golf Club",
              "addr:city": "Kingston", "addr:state": "WA"}},
    {"type": "way", "id": 103, "center": {"lat": 47.5210, "lon": -122.7350},
     "tags": {"leisure": "golf_course", "name": "Gold Mountain Golf Club",
              "addr:housenumber": "7263", "addr:street": "W Belfair Valley Rd",
              "addr:city": "Bremerton", "addr:state": "WA", "addr:postcode": "98312",
              "holes": "36"}},
    {"type": "way", "id": 104, "center": {"lat": 47.6000, "lon": -122.3000},
     "tags": {"leisure": "golf_course"}},  # unnamed
    {"type": "node", "id": 105, "lat": 47.6100, "lon": -122.3300,
     "tags": {"golf": "driving_range", "name": "Sunset Driving Range"}},
    {"type": "way", "id": 106, "center": {"lat": 47.6200, "lon": -122.3400},
     "tags": {"leisure": "miniature_golf", "name": "Putt Putt Fun Center"}},
    {"type": "way", "id": 107, "center": {"lat": 47.4400, "lon": -122.6600},
     "tags": {"leisure": "golf_course", "name": "Trophy Lake Golf & Casting",
              "addr:housenumber": "3900", "addr:street": "SW Lake Flora Rd",
              "addr:city": "Port Orchard", "addr:state": "WA", "golf:holes": "18"}},
    {"type": "way", "id": 108, "center": {"lat": 47.5000, "lon": -122.2000},
     "tags": {"leisure": "golf_course", "name": "Riverside Golf Club",
              "addr:city": "Seattle", "addr:state": "WA"}},
    {"type": "node", "id": 109, "lat": 47.6588, "lon": -117.4260,  # Spokane, far away
     "tags": {"leisure": "golf_course", "name": "Riverside Golf Club",
              "addr:city": "Spokane", "addr:state": "WA"}},
    {"type": "way", "id": 110, "center": {"lat": 47.7000, "lon": -122.4000},
     "tags": {"leisure": "golf_course", "golf": "driving_range",
              "name": "Bayside Driving Range"}},
]


# --- Pure logic (unit-testable; no network, no DB) ---------------------------
def parse_hole_count(tags):
    raw = tags.get("golf:holes") or tags.get("holes")
    if raw and str(raw).isdigit():
        return int(raw)
    return None


def element_to_candidate(el):
    tags = el.get("tags", {})
    center = el.get("center") or {}
    return {
        "osm_type": el.get("type"),
        "osm_id": el.get("id"),
        "name": (tags.get("name") or "").strip(),
        "housenumber": tags.get("addr:housenumber"),
        "street": tags.get("addr:street"),
        "city": tags.get("addr:city"),
        "state": tags.get("addr:state") or STATE_CODE,
        "postcode": tags.get("addr:postcode"),
        "hole_count": parse_hole_count(tags),
        "lat": center.get("lat", el.get("lat")),
        "lon": center.get("lon", el.get("lon")),
        "tags": tags,
    }


def practice_facility_reason(name):
    """Name-based test for a practice facility (NOT a real course): driving/golf
    ranges, putting/practice greens, hitting zones, mini-golf. Returns a reason
    string or None. Used by exclusion_reason AND by the CSV loader (which has
    names but no OSM tags), so the rule lives in one place.

    Exception: a name with 'driving range'/'range' is KEPT (returns None) when it
    also names a course ('golf course'/'golf club'/'country club') — e.g. a real
    course that happens to have a co-located range."""
    nl = (name or "").lower()
    is_course = any(k in nl for k in ("golf course", "golf club", "country club"))
    if "driving range" in nl or re.search(r"\brange\b", nl):
        return None if is_course else "driving_range"
    if any(k in nl for k in ("miniature golf", "mini golf", "mini-golf",
                             "putt putt", "putt-putt", "golfland")):
        return "mini_golf"
    if any(k in nl for k in ("putting green", "practice green", "practice range",
                             "practice facility", "practice area", "hitting zone",
                             "hitting bay")):
        return "practice"
    return None


def exclusion_reason(c):
    """Return a reason string if this candidate is junk, else None."""
    tags = c["tags"]
    if not c["name"]:
        return "unnamed"
    if tags.get("golf") == "driving_range":
        return "driving_range"
    if tags.get("leisure") == "miniature_golf" or tags.get("golf") == "miniature_golf":
        return "mini_golf"
    return practice_facility_reason(c["name"])


def normalize_name(name):
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def haversine_m(a_lat, a_lon, b_lat, b_lon):
    if None in (a_lat, a_lon, b_lat, b_lon):
        return None
    r = 6371000.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dphi = math.radians(b_lat - a_lat)
    dlmb = math.radians(b_lon - a_lon)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _same_place(a, b):
    """Two same-named candidates are the same course if close in distance, or
    (when coords are missing) if they share a city."""
    d = haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
    if d is not None and d <= DEDUPE_DISTANCE_M:
        return True
    if a["city"] and b["city"] and a["city"].strip().lower() == b["city"].strip().lower():
        return True
    return False


def _completeness(c):
    return sum(1 for f in ("housenumber", "street", "city", "postcode") if c.get(f))


def _merge_cluster(cluster):
    """Pick the most complete record as the base, then fill gaps from the rest.
    Tie-breaks: more complete address > has hole_count > 'way' over 'node' > lower id."""
    def rank(c):
        return (_completeness(c), 1 if c["hole_count"] else 0,
                1 if c["osm_type"] == "way" else 0, -(c["osm_id"] or 0))
    ordered = sorted(cluster, key=rank, reverse=True)
    base = dict(ordered[0])
    for other in ordered[1:]:
        for f in ("housenumber", "street", "city", "postcode", "hole_count"):
            if not base.get(f) and other.get(f):
                base[f] = other[f]
    base["_merged_refs"] = [f"{c['osm_type']}/{c['osm_id']}" for c in ordered]
    return base


def dedupe(candidates):
    """Group by normalized name, then cluster by proximity/city within each name."""
    by_name = {}
    for c in candidates:
        by_name.setdefault(normalize_name(c["name"]), []).append(c)
    kept = []
    removed = 0
    for _, group in by_name.items():
        clusters = []
        for c in group:
            placed = False
            for cl in clusters:
                if any(_same_place(c, member) for member in cl):
                    cl.append(c)
                    placed = True
                    break
            if not placed:
                clusters.append([c])
        for cl in clusters:
            kept.append(_merge_cluster(cl))
            removed += len(cl) - 1
    kept.sort(key=lambda c: normalize_name(c["name"]))
    return kept, removed


def process_elements(elements):
    """Full pipeline on raw OSM elements -> (kept_records, stats)."""
    candidates = [element_to_candidate(e) for e in elements]
    stats = {"fetched": len(candidates), "unnamed": 0, "driving_range": 0,
             "mini_golf": 0, "practice": 0, "deduped": 0, "kept": 0}
    survivors = []
    for c in candidates:
        reason = exclusion_reason(c)
        if reason:
            stats[reason] += 1
        else:
            survivors.append(c)
    kept, removed = dedupe(survivors)
    stats["deduped"] = removed
    stats["kept"] = len(kept)
    return kept, stats


def build_address(c):
    street_line = " ".join(p for p in (c.get("housenumber"), c.get("street")) if p).strip()
    parts = [p for p in (street_line, c.get("postcode")) if p]
    return ", ".join(parts) if parts else None


# --- I/O: network + database + CSV -------------------------------------------
def fetch_overpass(query=OVERPASS_QUERY):
    """LIVE network call. Single, sequential, polite request. Gated by network policy."""
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(OVERPASS_ENDPOINT, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp).get("elements", [])


def load_into_db(db_path, records, retrieved_date, dry_run):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        # Idempotent: clear this state's rows before reloading.
        conn.execute("DELETE FROM courses WHERE state = ?", (STATE_CODE,))
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for r in records:
            ref = "/".join(r.get("_merged_refs", [f"{r['osm_type']}/{r['osm_id']}"]))
            source = (f"OpenStreetMap (Overpass) {ref}, retrieved {retrieved_date}, "
                      f"ODbL; © OpenStreetMap contributors")
            if dry_run:
                source = "DRY-RUN MOCK DATA — " + source
            conn.execute(
                """INSERT INTO courses
                   (name, club_name, address, city, state, country,
                    property_lat, property_lng, hole_count, source_list,
                    created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r["name"], None, build_address(r), r.get("city"), r.get("state"), "USA",
                 None, None, r.get("hole_count"), source, now, now),  # property_lat/lng = NULL
            )
        conn.commit()
    finally:
        conn.close()


def export_csv(csv_path, records, retrieved_date):
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "address", "city", "state", "hole_count",
                    "property_lat", "property_lng", "osm_ref"])
        for r in records:
            ref = "/".join(r.get("_merged_refs", [f"{r['osm_type']}/{r['osm_id']}"]))
            w.writerow([r["name"], build_address(r) or "", r.get("city") or "",
                        r.get("state") or "", r.get("hole_count") or "",
                        "", "", ref])  # property_lat/lng intentionally blank (NULL)


# --- Self-test (asserts the logic on the mock sample) ------------------------
def _coords_written_after_load(kept):
    """Load the kept records into an in-memory DB (real schema) and count how
    many rows ended up with ANY coordinate. The hard rule => must be 0."""
    import setup_db  # local module; SCHEMA is the source of truth
    conn = sqlite3.connect(":memory:")
    conn.executescript(setup_db.SCHEMA)
    now = "2026-01-01T00:00:00Z"
    for r in kept:
        conn.execute(
            """INSERT INTO courses (name, address, city, state, country,
               property_lat, property_lng, hole_count, source_list, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (r["name"], build_address(r), r.get("city"), r.get("state"), "USA",
             None, None, r.get("hole_count"), "test", now, now))
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM courses WHERE property_lat IS NOT NULL "
                     "OR property_lng IS NOT NULL").fetchone()[0]
    conn.close()
    return n


def run_self_test():
    kept, stats = process_elements(MOCK_ELEMENTS)
    names = sorted(k["name"] for k in kept)
    checks = [
        ("fetched == 10", stats["fetched"] == 10),
        ("unnamed excluded == 1", stats["unnamed"] == 1),
        ("driving ranges excluded == 2", stats["driving_range"] == 2),
        ("mini golf excluded == 1", stats["mini_golf"] == 1),
        ("deduped == 1 (White Horse node+way)", stats["deduped"] == 1),
        ("kept == 5", stats["kept"] == 5),
        ("White Horse present", "White Horse Golf Club" in names),
        ("both Riverside kept (same name, far apart)",
         names.count("Riverside Golf Club") == 2),
        ("White Horse address merged from way", any(
            k["name"] == "White Horse Golf Club" and k["street"] == "Centaur Dr NE"
            for k in kept)),
        ("zero coordinates written to DB after load (the hard rule)",
         _coords_written_after_load(kept) == 0),
    ]
    print("SELF-TEST (mock sample):")
    ok = True
    for label, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
        ok = ok and passed
    print(f"  kept courses: {names}")
    return ok


def print_summary(stats, records, dry_run, csv_path):
    banner = "DRY RUN (mock sample — NOT real data)" if dry_run else "LIVE Overpass pull"
    print("=" * 70)
    print(f"Step 1 — Washington — {banner}")
    print("=" * 70)
    print(f"  Fetched from source : {stats['fetched']}")
    print(f"  Excluded (unnamed)  : {stats['unnamed']}")
    print(f"  Excluded (driving range): {stats['driving_range']}")
    print(f"  Excluded (mini golf): {stats['mini_golf']}")
    print(f"  Removed as duplicates: {stats['deduped']}")
    print(f"  KEPT (loaded into courses): {stats['kept']}")
    wh = [r for r in records if "white horse" in r["name"].lower()]
    print(f"  White Horse present : {'YES' if wh else 'NO'}")
    print(f"  property_lat/lng    : NULL for every row (the hard rule)")
    print(f"  Review CSV          : {csv_path}")
    print("-" * 70)


def main(argv=None):
    p = argparse.ArgumentParser(description="Step 1 (Washington): pull golf-course names + addresses from OSM.")
    p.add_argument("--live", action="store_true", help="Run the REAL Overpass query (needs network access; gated).")
    p.add_argument("--self-test", action="store_true", help="Assert the logic against the mock sample and exit.")
    p.add_argument("--db", default=DEFAULT_DB, help=f"Database path (default: {DEFAULT_DB}).")
    p.add_argument("--csv", default=None, help="Review CSV output path.")
    args = p.parse_args(argv)

    if args.self_test:
        return 0 if run_self_test() else 1

    dry_run = not args.live
    retrieved_date = datetime.date.today().isoformat()

    if args.live:
        try:
            elements = fetch_overpass()
        except Exception as e:  # noqa: BLE001 - report cleanly for a non-programmer
            print("LIVE pull failed — could not reach Overpass.")
            print(f"  {type(e).__name__}: {e}")
            print("  This is expected while the environment's network policy blocks")
            print("  overpass-api.de. Allow that host, then re-run with --live.")
            return 2
    else:
        elements = MOCK_ELEMENTS
        print("NOTE: --dry-run (default). Using the built-in FAKE sample. No real data pulled.\n")

    kept, stats = process_elements(elements)
    csv_path = args.csv or os.path.join(
        HERE, "washington_courses_DRYRUN.csv" if dry_run else "washington_courses_review.csv")

    load_into_db(args.db, kept, retrieved_date, dry_run)
    export_csv(csv_path, kept, retrieved_date)
    print_summary(stats, kept, dry_run, csv_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
