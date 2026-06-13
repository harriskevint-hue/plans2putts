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

## What's here
| File | What it is |
|---|---|
| `setup_db.py` | **Step 0.** Creates the empty database `courses.db` with three tables. |
| `step1_washington.py` | **Step 1.** Pulls Washington golf-course names + addresses from OpenStreetMap into `courses` (coordinates stay NULL). **Not yet run against live Overpass** — see status below. Also home to the shared `practice_facility_reason` filter, and the single-state pull form. |
| `us_courses_pull.py` | **Canonical RAW national pull** for all 50 states + DC (OSM/Overpass → `us_courses.csv`). **Raw only** — cleaning, dedup review, and the practice-facility filter happen DOWNSTREAM at load time. Runs locally (Overpass blocked in the web env). See `REFRESH-COURSE-DIRECTORY.md`. |
| `load_washington_csv.py` | **Step 1 (CSV path).** Loads a cleaned Washington CSV (pulled locally, then cleaned) into `courses`. See "Loading the cleaned Washington CSV". |
| `data/washington_courses_clean.csv` | The cleaned Washington source data the loader reads (tracked, so the loaded rows are reproducible). |
| `SOURCES.md` | Data-source + terms-of-service report (OSM/ODbL findings, attribution, share-alike note). |
| `REFRESH-COURSE-DIRECTORY.md` | How to run the national raw pull and refresh the directory (procedure doc). |
| `MIGRATION-NOTES.md` | How this maps to a future Postgres/DynamoDB backend (plan only — not built). |
| `courses.db` | The database itself. **Not committed** (gitignored); regenerate it from the CSV. |

## National raw pull — `us_courses_pull.py` (all 50 states + DC)
`us_courses_pull.py` is the **canonical RAW pull** for the whole country: it queries
`leisure=golf_course` for every state + DC and writes one `us_courses.csv`. It is
**raw only** — it does NOT clean, the practice-facility filter does NOT run here, and
its duplicate detection is **name + proximity** (same name, same state, within ~1 km),
so it **flags** probable duplicates rather than deleting them. **Caveat:**
name-variation duplicates (e.g. the Sky Ridge case — "Sky Ridge Golf Course" vs
"Sky Ridge Golf Course & Driving Range") are **not** auto-flagged by the pull; they
are caught at **load-time review** (cleaning) instead. Cleaning, dedup review, and the
practice-facility filter all happen downstream at load time. Full procedure:
`REFRESH-COURSE-DIRECTORY.md`.

## Step 1 — Washington course list (names + addresses)
Source: **OpenStreetMap via the Overpass API** (ODbL — attribution required; see
`SOURCES.md`). Pulls `leisure=golf_course` in Washington, filters out driving ranges,
mini-golf, and unnamed entries, de-dupes the same course appearing more than once,
and loads names + addresses into `courses`. **No coordinates** are written
(`property_lat/lng` stay NULL — the hard rule) and **no OSM per-hole geometry** is
harvested.

> **⚠️ LIVE-RUN STATUS: NOT YET RUN AGAINST LIVE OVERPASS.** The cloud
> environment's network policy currently blocks `overpass-api.de` (HTTP 403). The
> parsing / junk-filter / de-dupe logic is proven in `--dry-run` mode against a
> small built-in **mock** sample (run `--self-test` to verify). The real pull is
> gated until `overpass-api.de` is allowed by the network policy.

```bash
python3 integrations/data-pipeline/step1_washington.py              # DRY RUN on the mock sample (default)
python3 integrations/data-pipeline/step1_washington.py --self-test  # assert the logic on the mock sample
python3 integrations/data-pipeline/step1_washington.py --live       # REAL pull (needs network access; gated)
```
A run writes a review CSV (`washington_courses_DRYRUN.csv` in dry-run, or
`washington_courses_review.csv` when live) for a human to eyeball before the data is
trusted. Re-running is idempotent (it clears and reloads the state's rows).

## Loading the cleaned Washington CSV (the actual current data)
Because Overpass is blocked in the cloud environment, the real Washington pull was
run **locally** with the same approach as `step1_washington.py`, then **cleaned and
de-duped by hand** (merging duplicate OSM records, flagging missing names). That
cleaned file lives at `data/washington_courses_clean.csv` (tracked) and is loaded by:

```bash
python3 integrations/data-pipeline/setup_db.py --force      # fresh empty DB (adds website/notes columns)
python3 integrations/data-pipeline/load_washington_csv.py   # loads data/washington_courses_clean.csv
```

What the loader does:
- Maps `name, lat, lon, address, city, website, review` → `courses`. **`lat`/`lon` are
  OSM PROPERTY points (course centroids) → stored in `property_lat`/`property_lng`.
  These are NOT per-hole coordinates;** the `holes` table is left empty, so the hard
  rule holds (no per-hole green/tee/hazard coordinates anywhere).
- Applies the shared `practice_facility_reason` filter to drop driving ranges,
  putting/practice greens, hitting zones, and mini-golf — but keeps a "… & Driving
  Range" entry when it also names a real course, and **keeps unnamed rows** with an
  honest placeholder (`(name unknown — needs manual identification)`), never invented.
- Merges a "<X> Golf Course & Driving Range" annex into its base "<X> Golf Course"
  row (copies the address); preserves `website` and `review`→`notes`.

Current load: **255 courses** (268 read − 12 practice facilities − 1 annex merge),
all with an OSM property point, most without a street address yet. `holes` table = 0.

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
