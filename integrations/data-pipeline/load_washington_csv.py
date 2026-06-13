#!/usr/bin/env python3
"""
ShadesCaddie / Plans2Putts — Load a cleaned Washington CSV into courses.db.

Imports a human-cleaned course CSV (osm_type, osm_id, name, lat, lon, address,
city, website, review) into the Step 0 `courses` table.

Column mapping (CSV -> courses):
  name            -> name           (NOT NULL; empty -> honest placeholder, never invented)
  lat             -> property_lat   (OSM property point / centroid — NOT a hole coordinate)
  lon             -> property_lng   (same; the holes table is left untouched -> hard rule holds)
  address         -> address        (full single-line address as cleaned)
  city            -> city
  website         -> website        (preserved)
  review          -> notes          (preserved; audit/cleaning note)
  osm_type/osm_id -> source_list    (provenance + ODbL attribution)
  (fixed)         -> state = 'WA', country = 'USA'
  (none)          -> hole_count = NULL  (no scorecard data in this CSV)

Filtering: applies the SHARED practice-facility filter from step1_washington.py
(practice_facility_reason) — driving/golf ranges, putting/practice greens, hitting
zones, mini-golf. A 'driving range' name that ALSO names a course is kept (real
course w/ a range). It does NOT apply step1's "unnamed" rule, so unnamed rows are
KEPT (with an honest placeholder name). Removed rows are reported in full.

Annex merge: a kept "<X> Golf Course & Driving Range" row is treated as a duplicate
of the base "<X> Golf Course" — its address/city/website are merged onto the base
and it is not inserted separately (one course row results).

Verify flags: a few known names are kept but tagged in `notes` for human review.

Idempotent for Washington: clears existing WA rows, then loads.
"""

import argparse
import csv
import datetime
import os
import re
import sqlite3
import sys

import setup_db                       # local module; SCHEMA is the source of truth
from step1_washington import practice_facility_reason  # the one shared filter

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(HERE, "courses.db")
STATE_CODE = "WA"
RETRIEVED = "2026-06-13"
NAME_PLACEHOLDER = "(name unknown — needs manual identification)"

COURSE_INDICATORS = ("golf course", "golf club", "country club")
FLAG_VERIFY_NOTE = "verify: possible practice facility — not confirmed as a playable course"
FLAGGED_NAMES = {"redwood golf center", "tom's golf center", "tin cup golf"}


def _clean(v):
    return v.strip() if v and v.strip() else None


def _to_float(v):
    v = _clean(v)
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _is_course_name(name):
    nl = (name or "").lower()
    return any(k in nl for k in COURSE_INDICATORS)


def _base_course_name(name):
    """Strip a trailing '& Driving Range' so an annex maps to its base course."""
    base = re.sub(r"\s*&\s*driving range\s*$", "", name, flags=re.I)
    base = re.sub(r"\s+and\s+driving range\s*$", "", base, flags=re.I)
    base = re.sub(r"\s*driving range\s*$", "", base, flags=re.I)
    return base.strip()


def load(csv_path, db_path):
    setup_db.create_database(db_path, force=False)  # ensure schema exists
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cleared = conn.execute("DELETE FROM courses WHERE state = ?", (STATE_CODE,)).rowcount
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Read + clean -----------------------------------------------------------
    records = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not any((row.get(c) or "").strip() for c in row):
                continue
            records.append({
                "osm_ref": f"{_clean(row.get('osm_type')) or '?'}/{_clean(row.get('osm_id')) or '?'}",
                "name": _clean(row.get("name")),
                "lat": row.get("lat"), "lon": row.get("lon"),
                "address": _clean(row.get("address")), "city": _clean(row.get("city")),
                "website": _clean(row.get("website")), "review": _clean(row.get("review")),
                "_merge_note": None,
            })
    rows_read = len(records)

    # 2. Practice-facility filter ----------------------------------------------
    removed, survivors = [], []
    for r in records:
        reason = practice_facility_reason(r["name"])
        (removed.append((r["name"], r["osm_ref"], reason)) if reason
         else survivors.append(r))

    # 3. Annex merge ('<X> Golf Course & Driving Range' -> '<X> Golf Course') ---
    by_name = {}
    for r in survivors:
        if r["name"]:
            by_name.setdefault(r["name"].lower(), []).append(r)
    merged, annex_refs = [], set()
    for r in survivors:
        nm = r["name"] or ""
        if "driving range" in nm.lower() and _is_course_name(nm):
            base = next((b for b in by_name.get(_base_course_name(nm).lower(), [])
                         if b is not r), None)
            if base is not None:
                for f in ("address", "city", "website"):
                    if not base.get(f) and r.get(f):
                        base[f] = r[f]
                base["_merge_note"] = f"address merged from {r['osm_ref']} (driving-range duplicate)"
                merged.append((nm, r["osm_ref"], base["osm_ref"]))
                annex_refs.add(r["osm_ref"])

    # 4. Insert -----------------------------------------------------------------
    stats = {"inserted": 0, "websites": 0, "review_notes": 0,
             "verify_flags": 0, "merge_notes": 0, "placeholders": 0}
    placeholders, flagged = [], []
    for r in survivors:
        if r["osm_ref"] in annex_refs:
            continue
        raw_name = r["name"]
        name = raw_name or NAME_PLACEHOLDER
        if raw_name is None:
            stats["placeholders"] += 1
            placeholders.append((r["osm_ref"], r["review"]))

        note_parts = []
        if r["review"]:
            note_parts.append(r["review"]); stats["review_notes"] += 1
        if (raw_name or "").lower() in FLAGGED_NAMES:
            note_parts.append(FLAG_VERIFY_NOTE); stats["verify_flags"] += 1
            flagged.append((raw_name, r["osm_ref"]))
        if r["_merge_note"]:
            note_parts.append(r["_merge_note"]); stats["merge_notes"] += 1
        notes = " | ".join(note_parts) if note_parts else None

        if r["website"]:
            stats["websites"] += 1
        source_list = (f"OpenStreetMap (Overpass) {r['osm_ref']}, retrieved {RETRIEVED}, "
                       f"ODbL; © OpenStreetMap contributors")
        conn.execute(
            """INSERT INTO courses
               (name, club_name, address, city, state, country,
                property_lat, property_lng, hole_count, source_list,
                website, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (name, None, r["address"], r["city"], STATE_CODE, "USA",
             _to_float(r["lat"]), _to_float(r["lon"]), None, source_list,
             r["website"], notes, now, now),
        )
        stats["inserted"] += 1
    conn.commit()

    # 5. Report -----------------------------------------------------------------
    wh = conn.execute("SELECT COUNT(*) FROM courses WHERE name LIKE 'White Horse Golf Club%' AND state=?",
                      (STATE_CODE,)).fetchone()[0]
    sky = conn.execute("SELECT name, address, city FROM courses WHERE name LIKE 'Sky Ridge Golf Course%' AND state=?",
                       (STATE_CODE,)).fetchall()
    empty_address = conn.execute(
        "SELECT COUNT(*) FROM courses WHERE state=? AND (address IS NULL OR address='')",
        (STATE_CODE,)).fetchone()[0]
    empty_coords = conn.execute(
        "SELECT COUNT(*) FROM courses WHERE state=? AND (property_lat IS NULL OR property_lng IS NULL)",
        (STATE_CODE,)).fetchone()[0]
    holes = conn.execute("SELECT COUNT(*) FROM holes").fetchone()[0]
    conn.close()

    print("=" * 72)
    print("Washington CSV reload (final) — SUMMARY")
    print("=" * 72)
    print(f"  Data rows read         : {rows_read}   (prior WA rows cleared: {cleared})")
    print(f"  Rows REMOVED by filter : {len(removed)}")
    print(f"  Rows MERGED (annex)    : {len(merged)}")
    print(f"  Rows INSERTED          : {stats['inserted']}")
    print(f"  White Horse Golf Club  : {'PRESENT' if wh else 'MISSING'} ({wh})")
    print(f"  Rows with EMPTY address    : {empty_address}")
    print(f"  Rows with EMPTY coordinates: {empty_coords}")
    print(f"  holes table rows (must stay 0): {holes}")
    print("-" * 72)
    print("  Sky Ridge Golf Course row(s):")
    for r in sky:
        print(f"      • {r[0]}  | address: {r[1]}  | city: {r[2]}")
    for nm, aref, bref in merged:
        print(f"      (merged {aref} '{nm}' -> {bref})")
    print("-" * 72)
    print(f"  Websites preserved : {stats['websites']}")
    print(f"  Notes populated    : {stats['review_notes'] + stats['verify_flags'] + stats['merge_notes']}"
          f"  ({stats['review_notes']} cleaning, {stats['verify_flags']} verify-flag, {stats['merge_notes']} merge)")
    print(f"  Verify-flagged rows (kept, tagged for review):")
    for nm, ref in flagged:
        print(f"      • {nm}  ({ref})")
    print(f"  Unnamed rows kept (placeholder, no invented names): {stats['placeholders']}")
    for ref, note in placeholders:
        print(f"      • {ref}  (note: {note})")
    print("-" * 72)
    print(f"  REMOVED practice facilities ({len(removed)}):")
    for name, ref, reason in sorted(removed, key=lambda x: (x[2], (x[0] or ''))):
        print(f"      • [{reason:13}] {name}  ({ref})")
    print("=" * 72)


def main(argv=None):
    p = argparse.ArgumentParser(description="Load a cleaned Washington course CSV into courses.db.")
    p.add_argument("csv_path", nargs="?",
                   default=os.path.join(HERE, "data", "washington_courses_clean.csv"),
                   help="Path to the cleaned Washington CSV (default: data/washington_courses_clean.csv).")
    p.add_argument("--db", default=DEFAULT_DB, help=f"Database path (default: {DEFAULT_DB}).")
    args = p.parse_args(argv)
    if not os.path.exists(args.csv_path):
        print(f"CSV not found: {args.csv_path}")
        return 1
    load(args.csv_path, args.db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
