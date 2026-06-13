#!/usr/bin/env python3
"""
ShadesCaddie / Plans2Putts — Data Pipeline, Step 0
Creates the empty course-directory database (schema only, no data).

Plain-language summary (for KT, a non-programmer):
  Running this script makes a single file called `courses.db` next to this
  script. That file is the empty container the pipeline will later fill with
  course names, addresses, and scorecards (Step 1+). It holds NO course data
  yet and — by design — NO GPS coordinates ever come from this pipeline.
  Every hole starts life as "unverified" with all coordinate fields empty
  (NULL). Real coordinates only ever come from a golfer's on-course tap or an
  iGolf license, never from here. (See CLAUDE.md, "the one hard rule".)

How to run it:
    python3 setup_db.py            # creates ./courses.db if missing
    python3 setup_db.py --force    # deletes and recreates ./courses.db

The database file (courses.db) is intentionally NOT committed to git — it is a
regenerable artifact. This script + the schema are the source of truth.

Portability note (keep the Phase-4 migration path open — see MIGRATION-NOTES.md):
  We use only plain SQL types (INTEGER / REAL / TEXT) and standard constraints
  (PRIMARY KEY, FOREIGN KEY, CHECK, UNIQUE). JSON is stored as TEXT. Nothing
  here is SQLite-specific in a way that would block a later move to Postgres or
  DynamoDB. SQLite is the build-time tool; it is not the production backend.
"""

import argparse
import os
import sqlite3
import sys

DB_FILENAME = "courses.db"

# --- Allowed-value vocabularies (kept in one place so they can't drift) -------
# These mirror CLAUDE.md / COURSE-DATA-STRATEGY.md exactly.
HOLE_STATUS_VALUES = ("unverified", "refined", "verified")
HOLE_SOURCE_VALUES = ("scorecard", "subscriber", "igolf")

# --- The schema ---------------------------------------------------------------
# One statement per table. Written to read clearly for a non-programmer review.
SCHEMA = f"""
-- courses: one row per course = a LISTED directory entry.
-- LISTED (name/address/scorecard) is NOT the same as PLAYABLE. A course is only
-- PLAYABLE once its holes have real coordinates, which never come from here.
CREATE TABLE IF NOT EXISTS courses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    club_name     TEXT,
    address       TEXT,
    city          TEXT,
    state         TEXT,                       -- e.g. 'WA' (Washington = test state)
    country       TEXT    NOT NULL DEFAULT 'USA',
    property_lat  REAL,                        -- single property point; NULL until geocoded (Step 2)
    property_lng  REAL,                        -- NOTE: a property point is NOT a hole coordinate
    hole_count    INTEGER,                     -- 9 / 18 / 27 ...
    source_list   TEXT,                        -- where name/address came from (for the ToS report)
    website       TEXT,                        -- course website (optional; from source)
    notes         TEXT,                        -- free-text audit/cleaning note (optional)
    created_at    TEXT    NOT NULL,            -- ISO-8601 UTC timestamp
    updated_at    TEXT    NOT NULL
);

-- holes: one row per hole per course. The attribution backbone lives here.
-- Every coordinate field is NULL until a real refinement fills it. status
-- starts 'unverified'. A CHECK constraint makes illegal status/source values
-- impossible to store.
CREATE TABLE IF NOT EXISTS holes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id         INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    hole_number       INTEGER NOT NULL,
    par               INTEGER,
    yardage_by_tee    TEXT,                    -- JSON object, e.g. {{"blue":420,"white":390}}
    handicap          INTEGER,                 -- stroke index
    tee_lat           REAL,                    -- NULL until refined
    tee_lng           REAL,                    -- NULL until refined
    green_front_lat   REAL,                    -- NULL until refined
    green_front_lng   REAL,                    -- NULL until refined
    green_center_lat  REAL,                    -- NULL until refined
    green_center_lng  REAL,                    -- NULL until refined
    green_back_lat    REAL,                    -- NULL until refined
    green_back_lng    REAL,                    -- NULL until refined
    hazards           TEXT    NOT NULL DEFAULT '[]',   -- JSON array, empty until refined
    status            TEXT    NOT NULL DEFAULT 'unverified'
                      CHECK (status IN ('unverified', 'refined', 'verified')),
    refined_by        INTEGER REFERENCES contributors(id),  -- NULL until refined
    refined_at        TEXT,                    -- NULL until refined
    source            TEXT    CHECK (source IS NULL OR source IN ('scorecard', 'subscriber', 'igolf')),
    created_at        TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL,
    UNIQUE (course_id, hole_number)            -- a course can't have two of the same hole
);

-- contributors: one row per person who touches data. Built from day one so we
-- can attribute every refinement and, if needed, down-weight or roll back ALL
-- holes a bad contributor touched (quality control).
CREATE TABLE IF NOT EXISTS contributors (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT,                       -- name or handle
    joined_at      TEXT    NOT NULL,
    quality_weight REAL    NOT NULL DEFAULT 1.0,
    notes          TEXT
);

-- Indexes for the lookups the pipeline and a future backend will do most.
CREATE INDEX IF NOT EXISTS idx_courses_state    ON courses(state);
CREATE INDEX IF NOT EXISTS idx_holes_course     ON holes(course_id);
CREATE INDEX IF NOT EXISTS idx_holes_status     ON holes(status);
"""


def create_database(db_path: str, force: bool = False) -> None:
    if os.path.exists(db_path):
        if not force:
            print(f"Database already exists: {db_path}")
            print("Nothing changed. Use --force to delete and recreate it.")
            return
        print(f"--force given: removing existing {db_path}")
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    try:
        # Enforce foreign keys (SQLite leaves them off by default).
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

    print(f"Created empty database: {db_path}")
    print("Tables: courses, holes, contributors (0 rows each).")
    print("No course data and no coordinates were written — that is correct for Step 0.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create the empty ShadesCaddie course-directory database (Step 0).")
    parser.add_argument("--force", action="store_true", help="Delete and recreate the database if it already exists.")
    parser.add_argument("--db", default=None, help=f"Path to the database file (default: ./{DB_FILENAME} next to this script).")
    args = parser.parse_args(argv)

    db_path = args.db or os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_FILENAME)
    create_database(db_path, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
