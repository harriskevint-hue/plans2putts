# iGolf Connect -> ShadesCaddie (P2P) Integration

Server-side course-data integration. Built and tested BEFORE credentials so it
drops in the moment iGolf's license is green-lit and a key arrives.

## Files
- `igolf-transform.js` — converts an iGolf Connect course response into P2P course
  JSON (same schema as White Horse). Field mapping is config-driven (FIELD_MAP).
  Derives green front/center/back from the green polygon + tee line-of-play.
- `lambda-course-proxy.js` — AWS Lambda handler. Hides credentials, calls iGolf,
  transforms, validates, caches. Always falls back to "self-map" (Tier 3) on any
  failure so the subscriber is never stuck.
- `test-transform.js` / `test-lambda.js` — 30 passing tests (geometry, hazard
  filtering, tee mapping, alternate field names, fallback paths).
- `NOTES.md` — what iGolf's docs confirm + the key uncertainties.

## When the iGolf key arrives — the ONLY things to change
1. **FIELD_MAP** in `igolf-transform.js` — set the real field names from iGolf's
   actual response (the candidate-key design means most may already match).
2. **CONFIG** in `lambda-course-proxy.js` — real base URL, endpoint paths, and auth
   style. If iGolf uses AWS SigV4 (like Golfbert), add signing in `callIgolf()` only.
3. Set env vars: `IGOLF_API_KEY`, `IGOLF_BASE_URL`, `IGOLF_AUTH_STYLE`.
4. Re-run tests, then test against White Horse (compare to hand-mapped data).

## How it fits the three-tier strategy
- Tier 1 (your mapped library) is checked first by the app.
- This Lambda IS Tier 2 — call it when a course isn't in the library.
- On no key / no match / error / invalid data, it returns `fallback: "self-map"`,
  which the app uses to open the mapper (Tier 3). Subscriber never blocked.

## Run tests
```
node test-transform.js   # 18 tests
node test-lambda.js      # 12 tests
```

## NEVER
- Put the API key in client code. It lives in Lambda env / Secrets Manager only.
- Ship a course that fails validation (missing green center) as if it works —
  validateCourse() flags it and the app self-maps instead.
- Fabricate coordinates. Missing data -> self-map, never invented lat/lng.
