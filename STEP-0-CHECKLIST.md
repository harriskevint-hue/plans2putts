# Step 0 — Go / No-Go Validation

**Project:** Plans2Putts — golf rangefinder HUD for Meta Ray-Ban Display
**Last updated:** June 3, 2026

---

## Completed

- [x] **Meta Wearables Developer Center** — registered, org "Kevin T Harris Team,"
  project "Plans2Putts" created
- [x] **GitHub repo** — github.com/harriskevint-hue/plans2putts (public)
- [x] **GitHub Pages** — live at harriskevint-hue.github.io/plans2putts/ (HTTPS)
- [x] **GPS spike — desktop test** — geolocation API present, continuous updates,
  coordinates correct area. 84m accuracy (expected indoors on WiFi)
- [x] **GPS spike — outdoor phone test** — **PASSED at 3.0 m (≈ 3.3 yd)**.
  Continuous updates, strong accuracy. Gate 1 cleared.
- [x] **Course mapper deployed** — multi-course support, dogleg/layup point types,
  custom course names
- [x] **Friend mapping guide** — ready to send with the mapper link
- [x] **Data strategy** — three-layer approach finalized (tee sheets + satellite
  imagery + local player knowledge)
- [x] **Shot tracking** — scoped for Phase 3 (Airtable for POC, AWS for scale)

## Gate 1 result: PASS

Outdoor phone GPS accuracy: **3.0 m**. This is well within the ≤5 m threshold
needed for a usable golf rangefinder. Continuous updates confirmed.
The project's critical technical risk is cleared.

---

## Cloud stack

| Layer | Tool | Status |
|---|---|---|
| Code home | GitHub repo | ✅ Live |
| Building | Claude Code on the web (Max plan) | Ready to connect |
| Hosting | GitHub Pages (HTTPS) | ✅ Live |
| Course data | JSON files per course (self-mapped) | Tool ready |
| Shot data (POC) | Airtable | Phase 3 |
| Shot data (scale) | AWS (DynamoDB / S3) | Phase 3 |

## Data strategy

Three free layers:
1. **Published course materials** — scorecards and hole maps from course websites
2. **Satellite imagery** — GPS coordinates captured via the mapper tool
3. **Local player knowledge** — ground truth from players who know the course

Friends map their home courses using the mapper + friend guide. Each course = one
JSON file. No API costs.

---

## Remaining before build

- [ ] **Map White Horse Golf Club** — open course-mapper.html, use scorecard as
  reference, place pins for all 18 holes, export JSON
  → Deliverable: `white-horse-golf-club-course.json`

- [ ] **Display constraints fact sheet** — pull from Meta Web Apps docs: resolution,
  font minimums, refresh, overlay persistence, permissions, gesture input
  → Deliverable: `display-constraints.md`

---

## Build plan (once course data is ready)

**Phase 1 — Core rangefinder (the POC)**
- Load course JSON + live GPS
- Calculate distances (Haversine) to green front/center/back, hazards, doglegs, layups
- Display as HUD: one large yardage number, secondary callouts
- Auto-detect current hole from GPS proximity to tee boxes
- Auto-advance when player moves past the green
- Test on phone walking the course → test on glasses

**Phase 2 — Polish and partner readiness**
- Refine HUD design for Meta display constraints (600x600, sunlight, font sizes)
- Add course selection screen (for multi-course support)
- Neural Band gesture integration (manual hole advance, shot mark)
- Field test at White Horse: full 18 holes on the glasses
- Share via password-protected URL with testers

**Phase 3 — Shot tracking and scaling**
- Tap-to-mark ball position after each shot
- Calculate carry distance from previous position
- Store shot data in Airtable (POC) / AWS (at scale)
- Club tagging (optional per-shot club selection)
- Club distance analytics (average carry per club over time)
- Model: similar to Arccos — builds personal club profile from real data
- Multi-user backend when scaling beyond personal use

---

## Scaling plan

- Friends map courses → JSON files → bundled into app
- App gets a course-selection screen
- Each new course = one JSON file, zero cost
- Meta partner publishing opens later in 2026
- Monetization model TBD by Meta
- AWS backend only when adding user accounts + shot history sync

---

## Key URLs

| Resource | URL |
|---|---|
| GPS spike (live) | harriskevint-hue.github.io/plans2putts/gps-spike.html |
| Course mapper (live) | harriskevint-hue.github.io/plans2putts/course-mapper.html |
| GitHub repo | github.com/harriskevint-hue/plans2putts |
| Meta Developer Center | wearables.developer.meta.com |
| Meta Web Apps docs | wearables.developer.meta.com/docs/develop/webapps |
| Starter kit | github.com/facebookincubator/meta-wearables-webapp |
