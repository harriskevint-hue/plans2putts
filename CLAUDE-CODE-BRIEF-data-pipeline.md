# Claude Code Brief — ShadesCaddie Course-Data Pipeline

**For:** Claude Code (running on Kevin's machine / cloud, WITH internet access).
**From:** the ShadesCaddie project. Read the repo first:
`https://raw.githubusercontent.com/harriskevint-hue/plans2putts/main/docs/PROJECT-STATUS.md`
and `docs/COURSE-DATA-STRATEGY.md` — they define the data model and the rules below.

Kevin is a non-programmer. Explain what you're doing, work in small steps, show
results, and never silently fabricate data.

---

## THE GOAL

Build a pipeline that assembles a large directory of US golf courses (target
10,000+) as a launch "skeleton," ready for golfer refinement. Each course gets:
name, address, geocoded location, and scorecard data. This is a DIRECTORY-WITH-
SCORECARDS, not a working rangefinder dataset — see the hard constraint below.

## THE HARD CONSTRAINT — READ THIS FIRST (do not violate)

**None of the free/cheap sources in this pipeline provide per-hole GPS coordinates
(green/tee/hazard positions).** The Census geocoder returns ONE point per address
(the property). Scorecards provide par/yardage/handicap only. USGS provides imagery
(a picture), not coordinates.

Therefore:
- Every hole's coordinates (tee, green front/center/back, hazards) must be stored as
  NULL with `status: "unverified"`. DO NOT invent, estimate, or guess coordinates.
  DO NOT attempt automated green-detection from imagery — it is unreliable and a
  wrong coordinate produces a wrong yardage on a real golf shot.
- Coordinates get filled later by (a) golfer on-course capture, or (b) an iGolf
  license. That is out of scope for this pipeline.
- The app must label these courses honestly as "unverified — help map this course."

If you ever find yourself about to write a coordinate that didn't come from a real
GPS capture or a licensed provider, STOP. That is the one thing this project must
never do.

---

## WHAT TO BUILD (in order, test each step before moving on)

### Step 0 — Database schema (build this first, get it right)
Create the database (Kevin needs you to recommend and set up the DB — likely
start simple: SQLite locally or a managed Postgres/Airtable; advise him). Schema:

**courses**
- id, name, club_name, address, city, state, country
- property_lat, property_lng        (from geocoder; the single point)
- hole_count                          (9/18/27/etc.)
- source_list                         (where name/address came from)
- created_at, updated_at

**holes**  (one row per hole per course)
- course_id, hole_number, par, yardage_by_tee (json), handicap
- tee_lat, tee_lng                              (NULL until refined)
- green_front_lat/lng, green_center_lat/lng, green_back_lat/lng  (NULL until refined)
- hazards (json array)                          (empty until refined)
- status                                        ("unverified" | "refined" | "verified")
- refined_by                                    (subscriber id, NULL until refined)
- refined_at                                    (NULL until refined)
- source                                        ("scorecard" | "subscriber" | "igolf")

**contributors**  (for QA/attribution — build now, painful to retrofit)
- id, name/handle, joined_at, quality_weight (default 1.0), notes

This schema MUST support per-hole attribution and the ability to filter/roll back
all contributions from one contributor. This is the data-integrity backbone.

### Step 1 — Course list (name + address), state by state
Pull public-source course names + addresses. CRITICAL: use only sources whose terms
permit it. Check each source's terms of service BEFORE scraping; report to Kevin
what sources you're using and whether they're permitted. Prefer official/open
directories. Store into `courses`. Start with ONE state as a test (e.g. Illinois),
verify quality, then scale.

### Step 2 — Geocode addresses (Census service)
Use the US Census Geocoder batch endpoint (geocoding.geo.census.gov) — free, public,
handles bulk (up to ~10,000 per batch file). Feed it the addresses, store the
returned property_lat/property_lng. Handle failures gracefully (some addresses won't
match — log them, don't crash, don't fake a point).

### Step 3 — Scorecard enrichment
For each course, look up scorecard data (GolfCourseAPI: par/yardage/handicap/tees).
CHECK GolfCourseAPI's terms re: per-course on-demand lookups vs. bulk — do on-demand
per course, not a bulk scrape of their whole DB (that violates ToS and isn't needed).
Populate `holes` rows: par, yardage_by_tee, handicap. Coordinates stay NULL.
Cross-check: if a course's hole count or pars look inconsistent, flag don't guess.

### Step 4 — Mapping canvas (NOT bulk image download)
The mapper uses a LIVE satellite map view (Google/Apple/Leaflet+tiles) as the canvas
for subscribers placing pins — free, current, no storage burden. Do NOT bulk-download
10,000 USGS images up front. OPTIONAL later: cache a USGS/NAIP image for a single
course on-demand to support OFFLINE mapping on remote courses. Build the live-view
canvas first; treat offline image caching as a later enhancement.

---

## WHAT IS EXPLICITLY OUT OF SCOPE (do not attempt)
- Automated detection of greens/tees/hazards from imagery (the hard CV problem).
- Generating/estimating any coordinate by any automated means.
- Bulk-downloading the entire GolfCourseAPI database or any provider's full dataset.
- Building the subscriber-facing app backend (accounts, live API) — separate effort,
  though the schema here should be compatible with it.

## DELIVERABLES
1. The database, created and populated for ONE test state first (Illinois), reviewed
   with Kevin, then scaled to more states.
2. Re-runnable scripts for each step (list → geocode → scorecard), documented simply.
3. A short report: how many courses collected, how many geocoded successfully, how
   many scorecard-matched, and which sources were used (with ToS notes).
4. Everything committed to the repo under an `integrations/data-pipeline/` folder so
   it's preserved (per the project's repo-is-the-brain rule).

## SUCCESS CRITERIA
A reviewable database of courses (start: Illinois; goal: scale toward 10,000+ across
states) each with name, address, property location, and scorecard — every hole
honestly marked `unverified` with NULL coordinates, ready for golfer refinement.
No fabricated coordinates anywhere. Attribution schema in place from day one.

## NOTES FOR KEVIN (not instructions to Claude Code)
- This produces COVERAGE (a directory), not working distances. The rangefinder still
  needs golfer refinement or iGolf for coordinates. That's by design and by honesty.
- Sequencing reality: this data needs the Phase 4 backend to actually serve it to
  subscribers. Consider whether to run the full 10,000 now or prove the core app +
  backend first, then scale data to match real demand.
- Legal: the riskiest part is Step 1 sourcing. Make Claude Code report its sources.
