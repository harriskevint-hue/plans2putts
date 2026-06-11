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

---

## DATA-QUALITY TIERS: APPROXIMATE vs. GOLFER-VERIFIED (added session 2)

A course is never "empty." Every hole carries a STATUS so the golfer always knows
how trustworthy each yardage is. This lets the app launch with broad coverage
(approximate) that improves hole-by-hole as real golfers walk courses.

### Per-hole status values
- **approximate** — coordinates roughly placed from satellite imagery (quick human
  estimate) OR licensed from iGolf. Usable, labeled "unverified."
- **verified** — a golfer physically walked the hole and captured GPS on-course.
  Highest trust. Badge: "GPS verified on-course by a ShadesCaddie member."
  Stores who + when.

IMPORTANT HONESTY NOTE: free/cheap data (GolfCourseAPI scorecards, geocoding) does
NOT supply per-hole coordinates. It supplies pars/yardages/handicaps + one property
point. So the "approximate" coordinate baseline still must come from rough satellite
mapping or iGolf — the free data only *guides* placement and powers the distance
cross-check (measured tee->green vs. scorecard yardage). Do not promise "free
coordinates for every hole" — the baseline costs rough-mapping labor or an iGolf license.

### Schema addition (per hole)
Add to each hole object:
  "status": "approximate" | "verified",
  "verified_by": "<member id or null>",
  "verified_at": "<ISO date or null>"

### Incremental mapping flow (subscriber, over weeks)
- App knows the course's hole count (e.g. 27 holes = three nines) and shows progress:
  "27 holes — 6 verified, 21 approximate."
- Subscriber maps in small bites (3 / 7 / 9 holes at a time). Each hole uploads and
  graduates independently from approximate -> verified. No need to map a whole course
  at once (that's what makes it not a chore).
- Design the incentive as a small mission ("go map these 9 holes") rather than
  "map while you play" — stopping to walk to each green slows a real round and annoys
  playing partners.

### On-course capture (the verified-data workflow)
- Subscriber walks/rides the course, stands ON each point, taps once to capture GPS:
  tee, front/center/back of green, hazards. GPS works offline (talks to satellites),
  so spotty WiFi is fine — capture stores LOCALLY first, uploads later.
- One tap = capture. One tap = undo a bad entry. Re-tap = recapture. Simple big buttons.
- Audio fallback: subscriber narrates points while walking ("front of green 4, bunker
  right..."), uploads after the round, company reviews/transcribes. Good for local
  knowledge ("hidden creek short of the green").
- Phone/iPad tap is the PRIMARY, reliable input. Meta wristband one-click is
  EXPERIMENTAL (depends on what gestures Meta exposes to web apps) — build tap first.

---

## AUDIENCE & DEVICE TIERS (added session 2) — DESIGN PRINCIPLE

ShadesCaddie must NOT be a Meta-glasses-only app. Tying viability to a tiny new-device
base caps the market. Phone + ANY audio is a first-class experience; glasses are the
premium enhancement, never a requirement.

- **Tier A — Phone + any earbuds/bone speakers (Shokz, AirPods, etc.):** FULL core
  experience. Voice yardages through audio, phone in pocket. This is the LARGE market.
- **Tier B — Meta voice-only (Oakley Meta / Ray-Ban non-display):** same audio
  experience via the glasses' speakers.
- **Tier C — Meta Ray-Ban Display:** premium — adds the visual HUD on top of audio.

Every feature should degrade gracefully: if it works great for a golfer with a phone
and cheap earbuds, it works for everyone. Design audio-first; treat the visual HUD as
an enhancement layer for the device that has it.

### Launch-coverage principle
Launching with ~500 approximate courses (ready for subscriber enrichment) reads as a
real product; launching with 6 reads as a hobby. Coverage is a credibility
requirement, not just a feature. Budget for the approximate baseline (rough mapping
labor or iGolf license) as a launch cost.

---

## LAUNCH PHILOSOPHY: COVERAGE-FIRST WITH HONEST CONFIDENCE (added session 2)

Resolved strategic position (Kevin's call, endorsed):

**Launch broad, not perfect.** A large library of rough courses with honest labeling
beats a handful of perfect ones. 6 flawless courses fails market acceptance; thousands
of rough-but-honestly-labeled courses, refinable by local golfers, succeeds. Coverage
is the credibility and adoption driver.

**The safety constraint is honesty, not precision.** The one failure a rangefinder
cannot have is confidently showing a WRONG number as if it were trusted. The fix is
not higher accuracy everywhere — it is transparent per-hole confidence:

- Every hole shows its status to the golfer: **verified-by-golfer** vs.
  **not yet reviewed by a golfer**.
- Unverified holes are clearly labeled and paired with a call to action:
  "This hole hasn't been reviewed by a golfer yet — help us improve it."
- This protects trust (golfers calibrate; their own eyes give rough distance sense)
  AND recruits contributors (the visible gap is the invitation).

**Minimum quality floor for rough data:** approximate coordinates should be
"roughly right" (in the ballpark from satellite estimation or iGolf), not random.
Honest labeling covers imprecision; it cannot rescue data that is wildly wrong.

### The Wikipedia / recognition model (growth engine)
Golfers, like Wikipedia editors, are motivated by RECOGNITION as much as reward:
- Attribute every refinement: "Hole 5 refined by [member], [date]."
- Recognition features: contributor badges, "you've verified N holes," course-level
  and community leaderboards, "refined by [member]" shown on the hole.
- Material reward (incentives) PLUS status/recognition. Do not underestimate status —
  it may drive more contribution than money. Local pride in a home course is real.

### Per-hole status model (UI + data)
- `unverified` (rough: iGolf or satellite estimate) — labeled, shows "help improve."
- `refined` (a golfer recorded data on-course) — attributed to that member.
- Multiple subscribers can refine different holes on the same course; in busy markets
  a popular course fills in fast. Each hole graduates independently.
- Attribution enables QUALITY CONTROL: weight or revoke a contributor's data; if a
  member proves unreliable, filter/roll back all holes they touched. Build attribution
  in from day one — it is painful to retrofit.

---

## TWO CONTRIBUTION TYPES — DON'T CONFLATE THEM (added session 2)

A critical distinction for data integrity. There are two very different kinds of
subscriber contribution. Conflating them breaks the honest-labeling principle.

### Type A — Scorecard verification (effortless, LOW coordinate value)
- Subscriber uploads a photo of the scorecard (optionally with notes).
- Confirms/corrects the SCORECARD layer only: par, yardage, handicap.
- Does NOT add or improve any GPS coordinate. The app likely already had the
  scorecard from GolfCourseAPI. A scorecard photo contains NO coordinates and
  cannot be turned into them.
- Value: engagement, recruitment, confirming scorecard accuracy. Reward modestly.
- Badge: "Scorecard confirmed by [member]" — NOT "GPS verified."

### Type B — On-course GPS capture (some effort, HIGH value)
- Subscriber stands on the actual point and taps; phone GPS records the real coord.
- THIS is what refines coordinates and improves live distances for the next golfer.
- Value: the real refinement engine. Reward most heavily. Weight in QA.
- Badge: "GPS verified by [member]" — this is the one that changes the hole's
  position and flips status unverified -> refined.

### The trap to avoid
Do NOT show a hole as "refined by [member]" because someone uploaded a scorecard.
The coordinates never changed; the next golfer would trust an unimproved number.
Keep the badges separate. Only Type B changes coordinates and confidence status.

### Design goal: make Type B nearly as effortless as Type A
The win is not "upload a scorecard" (effortless but doesn't help coordinates) — it is
making ON-COURSE CAPTURE almost as effortless. Minimum-effort version: a single
"I'm at the green" CENTER-of-green tap while the golfer is already putting out — no
walking to front/back required. One tap, barely more than nothing, and it actually
refines the coordinate. Engineer for that one-tap-at-the-green capture. Front/back/
hazard taps are optional bonus contributions for the more engaged.

Reality: most golfers won't walk a course tapping pins. But many will tap once at
the green on holes they're already playing. That single tap is the contribution worth
designing around — effortless capture of the thing that's actually missing (a GPS
point), not effortless upload of the thing we already have (the scorecard).
