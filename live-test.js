# GolfCourseAPI -> ShadesCaddie (scorecard layer)

GolfCourseAPI provides scorecard data (par, yardage, handicap, rating, slope) and a
single property-level lat/lng — but NO per-hole green/tee/hazard coordinates. So this
integration fills the SCORECARD layer of a P2P course and leaves coordinates for the
mapper (Tier 3). It roughly halves manual data entry.

## Files
- `gca-transform.js` — transforms a GolfCourseAPI course into a partial P2P course
  (pars, tee yardages, handicaps, rating/slope filled; coordinates null).
- `test-gca.js` — 16 passing tests against the documented OpenAPI schema.
- `live-test.js` — run on YOUR machine to see real data:
    `GCA_KEY=yourkey node live-test.js "white horse"`
  It searches, fetches, prints the scorecard, runs the transform, and confirms
  whether coordinates are present (they won't be).

## Security
- Rotate the key you pasted in chat — treat it as public.
- The key goes in your Lambda environment, NEVER in client code.

## Role in the three-tier strategy
- This is a Tier-2 PARTIAL: scorecard auto-fill, not a coordinate source.
- Coordinates still come from Tier 3 (the mapper) or, if licensed later, iGolf.
