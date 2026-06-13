# Data Sources & Terms-of-Service Report

Records WHERE each piece of directory data comes from and WHETHER the source's
terms permit our use. Per the data-pipeline brief: check ToS before pulling, and
report sources used. Update this file whenever a new source is added.

---

## Step 1 — Washington course list (names + addresses)

### Source: OpenStreetMap, via the Overpass API
- **What we take:** golf-course `name` and address tags (`addr:*`) for courses in
  Washington. Nothing else.
- **What we DO NOT take:** no per-hole geometry (`golf=green`/`golf=tee`) is ever
  harvested into coordinates. The Overpass `center` point is used only transiently
  in-memory for de-dupe and is **never written to the database**.

### License: Open Database License (ODbL) — PERMITTED for our use
Verified 2026-06-13 (the official pages 403'd the fetcher; confirmed via OSM
Foundation / OSM Wiki sources — see links below).

- **Attribution — ALWAYS required.** Credit string: **"© OpenStreetMap contributors"**.
  Stored in each row's `source_list` and shown wherever the data is surfaced.
- **Share-alike — CONDITIONAL.** ODbL share-alike applies only if we publish a
  **Derivative Database** (i.e. distribute our course dataset *as data*). If we only
  publish a **Produced Work** (the app showing course info to a subscriber, not
  handing out the database), we owe **attribution only**.
  - **Our position (KT-approved):** treat share-alike as a **pre-distribution
    checkpoint, NOT a Step-1 blocker.** Using OSM internally to build the directory
    is fine; we are **not** distributing the dataset as data. If that ever changes,
    decide deliberately first. Commercial use itself is allowed (ODbL is not
    non-commercial).

### Overpass API fair-use (verified 2026-06-13)
- One sequential query at a time (no parallel queries); be polite.
- Leaky-bucket rate limiting per IP; a single-state query run a few times in dev is
  well within limits. Heavy/repeated use should self-host or use a paid mirror.

### The exact query used (live mode)
```
[out:json][timeout:90];
area["ISO3166-2"="US-WA"][admin_level=4]->.wa;
(
  nwr["leisure"="golf_course"](area.wa);
);
out tags center;
```

### Retrieval status
**`step1_washington.py` (live mode) NOT YET RUN IN THIS ENVIRONMENT.** The cloud
environment's network policy blocks `overpass-api.de` (HTTP 403); its logic is proven
in `--dry-run` against a built-in mock sample.

### How the current Washington data was actually produced (the CSV load path)
Because Overpass is blocked here, the Washington pull was run **locally** (same
`leisure=golf_course` Overpass approach as `step1_washington.py`), then **cleaned and
de-duped by hand** (merged duplicate OSM records, flagged missing names). The result
is committed at `data/washington_courses_clean.csv` (tracked, so the load is
reproducible) and imported by `load_washington_csv.py` into `courses`.

Key honesty points about this load:
- **`lat`/`lon` in the CSV are OSM PROPERTY points (course centroids), stored in
  `property_lat`/`property_lng`. They are NOT per-hole coordinates.** The `holes`
  table is intentionally left **empty** — no per-hole green/tee/hazard coordinates
  exist anywhere, so the one hard rule holds. (This is the documented "OSM point
  first" intention for property location; it does not make any course PLAYABLE.)
- Practice facilities (driving/golf ranges, putting/practice greens, hitting zones,
  mini-golf) are filtered out via the shared `practice_facility_reason` rule; unnamed
  rows are kept with an honest placeholder (never invented).
- Current result: 255 LISTED courses (not playable — coordinates are property points
  only). ODbL attribution (`© OpenStreetMap contributors`) is recorded per row.

### Intention for Step 2 (property location) — don't lose this
When we do Step 2, **OSM's course `center` point becomes the FIRST source for
`property_lat/lng`**, with the **US Census geocoder as the fallback** for courses
where OSM has no usable point. This may make a separate Census pass largely
redundant for OSM-sourced courses. (A property point is NOT a hole coordinate —
the hard rule is unaffected.)

---

## Sources deliberately NOT used (and why)
- **GolfCourseAPI** — ToS prohibits bulk pulls; it's scorecard data, not a course
  listing. Reserved for Step 3 (per-course, on-demand scorecard lookups only).
- **Commercial course-finder/directory sites** (GolfLink, GolfNow, Golf Advisor,
  etc.) — their terms generally prohibit scraping. Not used.
- **Wikidata (CC0)** — available as an optional cross-check on coverage if OSM looks
  thin; not used as the primary load.

## Reference links (verified 2026-06-13)
- OSM Foundation — Licence and Legal FAQ: https://osmfoundation.org/wiki/Licence/Licence_and_Legal_FAQ
- OSM Foundation — Attribution Guidelines: https://osmfoundation.org/wiki/Licence/Attribution_Guidelines
- OSM Wiki — Open Database License: https://wiki.openstreetmap.org/wiki/Open_Database_License
- OSMF Operations — API Usage Policy: https://operations.osmfoundation.org/policies/api/
- Geofabrik — Overpass API (paid mirror / heavy use): https://www.geofabrik.de/data/overpass-api.html
