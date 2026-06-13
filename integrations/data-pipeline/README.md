# ShadesCaddie Data Pipeline

Builds a **directory** of golf courses (name → address → geocode → scorecard) as a
launch skeleton. This is **Step 0** of the pipeline described in
`/CLAUDE-CODE-BRIEF-data-pipeline.md`.

> **Read first:** `/CLAUDE.md`, `/COURSE-DATA-STRATEGY.md`,
> `/CLAUDE-CODE-BRIEF-data-pipeline.md` at the repo root. They define the data
> model and the rules this code follows.

## The one hard rule (built into the schema)
This pipeline **never produces GPS coordinates.** No free/cheap source provides
per-hole green/tee/hazard positions. So every hole is created with all coordinate
fields **NULL** and `status = "unverified"`. Real coordinates only ever come from a
golfer's on-course capture or an iGolf license — never from here. A LISTED course
(name/address/scorecard) is **not** a PLAYABLE course (one with real coordinates).

## What's here so far (Step 0 — schema only)
| File | What it is |
|---|---|
| `setup_db.py` | Creates the empty database `courses.db` with three tables. |
| `MIGRATION-NOTES.md` | How this maps to a future Postgres/DynamoDB backend (plan only — not built). |
| `courses.db` | The database itself. **Not committed** (see below); regenerate it. |

## How to build / rebuild the database
You need Python 3 (3.11 used here). `sqlite3` is built in — nothing to install.

```bash
# from the repo root
python3 integrations/data-pipeline/setup_db.py          # create courses.db if missing
python3 integrations/data-pipeline/setup_db.py --force  # delete & recreate it
```

Running it prints what it did and creates `integrations/data-pipeline/courses.db`
with `courses`, `holes`, and `contributors` tables — **0 rows each**. No course
data is pulled in Step 0; that's Step 1 (Washington first).

## Why the `.db` file is NOT in git
The database is a **regenerable artifact** — `setup_db.py` is the source of truth
for the schema. We version the script, not the binary file. `courses.db` is listed
in the repo's `.gitignore`. (Once Step 1 populates real directory data, we'll decide
separately how/where to store that data — likely an export, not the SQLite binary.)

## Why SQLite (and why that doesn't lock us in)
SQLite is a single file, no server, no account, no cost, and built into Python — the
simplest tool that fully meets a build-time need. It is **not** the production
backend. The schema deliberately uses only portable SQL (plain `INTEGER`/`REAL`/
`TEXT` types, `PRIMARY KEY` / `FOREIGN KEY` / `CHECK` / `UNIQUE`, JSON-as-TEXT) so it
moves cleanly to Postgres or DynamoDB later. See `MIGRATION-NOTES.md`.

## The schema in brief
- **courses** — one row per course (the directory entry). Holds the single property
  point (`property_lat/lng`, NULL until geocoded) — which is *not* a hole coordinate.
- **holes** — one row per hole. All coordinate fields NULL until refined; `status`
  starts `unverified` (allowed: `unverified` | `refined` | `verified`); `source`
  allowed: `scorecard` | `subscriber` | `igolf`. Carries `refined_by` / `refined_at`
  for attribution. A hole can't be duplicated within a course.
- **contributors** — one row per person who touches data, with a `quality_weight` so
  a bad contributor's holes can be down-weighted or rolled back. Built from day one.

The database enforces these rules itself: illegal `status` values and duplicate holes
are rejected at insert time, and a brand-new hole defaults to NULL coordinates +
`unverified`. (Verified during the Step 0 build.)
