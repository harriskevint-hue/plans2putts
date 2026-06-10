# ShadesCaddie — Course Data Strategy (Permanent Reference)

**Purpose:** Define how the app ALWAYS provides course GPS data to a subscriber,
so that a subscriber is NEVER blocked from playing — even when a course has no
data available anywhere. This is the canonical solution to the "no GPS data"
problem first encountered with Army Navy Country Club (Fairfax).

Hand this document to any future build session before touching course-data code.

---

## THE PROBLEM (stated permanently)

When a subscriber selects a course, the app needs GPS coordinates for each hole
(tee, green front/center/back, hazards, dogleg, layups) to calculate distances.
If no coordinates exist for that course, the rangefinder cannot function and the
subscriber is stranded. This MUST never be allowed to happen.

---

## THE SOLUTION: THREE-TIER FALLBACK CHAIN

On course selection, the app walks DOWN this chain until data is found:

### Tier 1 — Self-Mapped Library (first choice)
- Courses mapped by Kevin / the ShadesCaddie team (e.g. White Horse, Army Navy Blue, Army Navy Red).
- Stored as standard JSON in the app's course library.
- Highest accuracy, zero cost, instant load.
- ALWAYS checked first.

### Tier 2 — Commercial API (broad coverage)
- A paid GPS data provider (e.g. iGolf, Golfbert, GolfAPI.io, Golf Intelligence).
- Queried for any course NOT in the Tier 1 library.
- Provides "thousands of courses on day one."
- REQUIRES a backend proxy to hide the API key (never put the key in client code).
- Returned data is transformed into the standard JSON schema before use.

### Tier 3 — On-Demand Self-Mapping (the guarantee / escape hatch)
- Used when a course is in NEITHER Tier 1 NOR Tier 2.
- The subscriber is handed the in-app course mapper, pre-centered on the course.
- They click tees / greens / hazards using satellite imagery + their scorecard.
- Output saves to the SUBSCRIBER'S ACCOUNT (so they own it and reuse it).
- Optionally copied to a REVIEW QUEUE for promotion into the Tier 1 library.
- **This tier is what guarantees the app always works.** API coverage is never
  100%; self-mapping is the floor that catches everything else.

---

## WHY THIS IS FAST TO IMPLEMENT (every time)

The mapper and data schema are already built and proven (White Horse was mapped
this exact way). The "no data" solution is NOT new code each time — it is the
same pipeline reused:

1. Course not found in Tier 1 or Tier 2
2. App opens the course mapper, pre-centered on the course location
3. Subscriber clicks tees / greens / hazards (scorecard as guide)
4. Mapper exports the STANDARD JSON schema (below)
5. JSON saves to subscriber account (Tier 3) + optional review queue (-> Tier 1)
6. App loads it and plays — identical to how White Horse works today

The virtuous cycle: every course a subscriber maps can be reviewed and promoted
into Tier 1, so coverage improves the more the app is used.

---

## STANDARD COURSE JSON SCHEMA (the contract every tier must produce)

This is the format the rangefinder reads. API responses and mapper exports must
both be transformed into this shape.

```json
{
  "course": "Course Name",
  "holes": [
    {
      "hole": 1,
      "par": 4,
      "tee":   { "lat": 47.768034, "lng": -122.532291 },
      "green": {
        "front":  { "lat": 47.76899, "lng": -122.5379 },
        "center": { "lat": 47.76871, "lng": -122.5378 },
        "back":   { "lat": 47.76855, "lng": -122.5377 }
      },
      "hazards": [ { "label": "hazard 1", "lat": 47.7667, "lng": -122.5380 } ],
      "dogleg":  null,
      "layups":  []
    }
    // ... one object per hole (9 or 18)
  ]
}
```

Required per hole: hole number, par, tee lat/lng, green center lat/lng.
Recommended: green front + back, hazards. Optional: dogleg, layups.

---

## NINE-HOLE / COMBINATION COURSES (Army Navy model)

Some clubs are multiple 9-hole nines combined into 18-hole rounds
(Army Navy Fairfax = Blue 9, Red 9, White 9).

RULE: Map each nine ONCE as its own 9-hole file
(army-navy-blue.json, army-navy-red.json, army-navy-white.json).

At runtime the subscriber picks a STARTING nine and a FINISHING nine; the app
assembles the 18 by concatenating two nines. Any 9 can also be played alone
(start nine + "9 holes only"). Coordinates are never duplicated across combos.

White Horse and other true 18-hole courses are stored as a single 18 and play
normally without the start/finish picker.

---

## IMPLEMENTATION CHECKLIST (for any future session)

- [ ] On course select, try Tier 1 (library) -> Tier 2 (API) -> Tier 3 (mapper)
- [ ] Never put API keys in client code — always proxy through the backend
- [ ] All sources output the STANDARD JSON SCHEMA above
- [ ] Mapper saves Tier 3 output to subscriber account + review queue
- [ ] Promotion path: reviewed subscriber maps -> Tier 1 library
- [ ] Nine-hole clubs: map each nine once; assemble combos at runtime
- [ ] NEVER fabricate coordinates. Missing data -> route to mapper, never invent.
