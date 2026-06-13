# Refreshing / Expanding the Course Directory (all 50 states + DC)

The standard, repeatable method for building the LISTED course directory from
OpenStreetMap. Washington was the pilot; this is how every other state is done.

> **LISTED ≠ PLAYABLE.** This pipeline produces a directory (name / address /
> property point). A course becomes PLAYABLE only when it has per-hole coordinates,
> which come later from a golfer's on-course capture or an iGolf license — never from
> here. See `/CLAUDE.md` and `SOURCES.md`.

## The three stages

### 1. RAW pull — `us_courses_pull.py`  (run LOCALLY)
Canonical raw pull of `leisure=golf_course` for all 50 states + DC from OSM Overpass.
Writes one raw CSV per state (`data/raw/<STATE>_courses_raw.csv`) with:
`osm_type, osm_id, name, lat, lon, address, city, website, state`.

**Runs locally**, because the Claude Code web environment's network policy blocks
`overpass-api.de` (HTTP 403). (If `overpass-api.de` is later allowlisted in the
environment, it can run in-cloud too.)

```bash
python3 us_courses_pull.py --list-states          # show coverage (51 jurisdictions)
python3 us_courses_pull.py --print-query WA        # inspect a query, no network
python3 us_courses_pull.py --states WA,OR          # pull specific states
python3 us_courses_pull.py                          # pull ALL 50 + DC (polite, spaced)
```
RAW means no cleaning: no de-dupe, no practice-facility filtering. That is deliberate
— the pull stays auditable and re-runnable; judgment happens downstream.

### 2. Clean + de-dupe review  (human-in-the-loop)
Turn a raw per-state CSV into a cleaned `*_courses_clean.csv` (the committed seed):
- Merge duplicate OSM records for the same course (e.g. a node + a way, split
  polygons, or a "… & Driving Range" annex that carries the address).
- Flag missing names (leave them — don't invent; the loader keeps them with a
  placeholder).
- Add a `review` column with audit notes for any non-obvious decision.

The cleaned CSV is what gets committed (the DB is gitignored and regenerable from it).
Washington's seed: `data/washington_courses_clean.csv`.

### 3. Load — `load_washington_csv.py`
Loads a cleaned CSV into `courses` in `courses.db`:
- `lat`/`lon` → `property_lat`/`property_lng` (**OSM property points / centroids — NOT
  per-hole coordinates**). The `holes` table is left empty → the hard rule holds.
- Applies the shared **practice-facility filter** (`practice_facility_reason` in
  `step1_washington.py`): drops driving/golf ranges, putting/practice greens, hitting
  zones, mini-golf — but keeps a "… & Driving Range" entry that also names a real
  course, and keeps unnamed rows with an honest placeholder.
- Preserves `website` and `review`→`notes`; records ODbL attribution per row.

```bash
python3 setup_db.py --force                 # fresh empty DB (courses/holes/contributors)
python3 load_washington_csv.py              # loads data/washington_courses_clean.csv
```

> **Note:** `load_washington_csv.py` is currently Washington-specific (state hardcoded
> to `WA`, default CSV path). Generalizing it to take a `--state`/`--csv` for any
> cleaned file is a small future step when we expand beyond WA.

## Status
- **Washington: DONE** — 255 LISTED courses loaded and merged to `main` (PR #2).
- Other states: raw pull method ready (`us_courses_pull.py`); run + clean + load
  per state as we expand.

## Licensing
OpenStreetMap data is ODbL: attribution always (`© OpenStreetMap contributors`);
share-alike only if we ever distribute the dataset AS DATA (a pre-distribution
checkpoint, not our plan). Full details in `SOURCES.md`.
