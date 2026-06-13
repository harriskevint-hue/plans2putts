# Refreshing the course directory (OpenStreetMap pull)

The course **directory** — where each golf course is and what it's called — comes
from OpenStreetMap via the Overpass API. It changes slowly, so this is an
occasional refresh (once or twice a year), not a runtime app feature. The app
reads the pre-loaded database; it never calls Overpass during a round.

This pull is run **outside** Claude Code, on a normal machine with open internet,
because the Claude Code web environment blocks `overpass-api.de`. Running it
locally sidesteps that entirely.

## What this gives you (and what it does not)
- **Gives you:** a national directory — course name, location (lat/lon), and
  whatever address/website OSM has. Good for coverage and discovery.
- **Does NOT give you:** hole-by-hole geometry (tee boxes, greens, pin positions).
  That is the data a yardage HUD actually reads, and it is a separate, harder
  data problem handled by the Tier 2 (commercial API) and Tier 3 (subscriber
  self-mapping) layers.

## How to run it
1. On your laptop (internet on), run:
   ```
   python us_courses_pull.py        # use python3 on macOS
   ```
   It queries all 50 states + DC sequentially with polite delays. Expect roughly
   10-25 minutes. Transient rate-limit/timeout responses retry automatically.
2. Output: `us_courses.csv`, one row per OSM golf-course record, plus a printed
   summary (totals, missing-data counts, probable-duplicate clusters).

## CSV columns
`state, osm_type, osm_id, name, lat, lon, address, city, website, flag`
- `flag` is empty for clean rows, or notes: `probable duplicate — review (...)`,
  `missing name`, `missing coords`.

## Handling duplicates
At national scale you can't hand-verify every collision the way Washington was
checked. The script **flags** probable duplicates (same name, same state,
records within ~1 km) rather than deleting them. The Washington pattern was a
point and a boundary mapped for the same course — usually one real course. Review
the flagged rows, collapse the genuine duplicates, and keep any that are actually
distinct nearby courses (Washington had one such case: Crescent Bar).

NOTE — duplicate detection is name + proximity only. Duplicates that differ in
NAME (e.g. the Sky Ridge case: "Sky Ridge Golf Course" vs "Sky Ridge Golf Course
& Driving Range") are NOT auto-flagged by this pull — they are caught at
load-time review/cleaning instead.

## Single-state refresh
To refresh just one state, the companion `step1_washington.py` shows the
single-state form. Change the `ISO3166-2` code in its query (e.g. `US-OR`) and
run it the same way.

## Importing into the database
Do the import inside Claude Code (it needs no internet — it's just loading a
local CSV into the Step 0 schema). Hand the cleaned CSV to Claude Code and have
it map the rows into `courses.db` using the existing Step 1 load path, then
report row counts and a data-quality check before committing.

## Cadence
Quarterly or semi-annually is plenty. New courses open and old ones close rarely,
so the directory does not drift fast.
