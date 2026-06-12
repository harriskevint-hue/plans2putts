# iGolf Connect data model — what their marketing/docs state (from uploaded page)

Confirmed available (Golf GPS Maps):
- "perimeter GeoData for fairways, greens, tee boxes, hazards, water"
- "advanced GeoData for trees and other obstacles (including size)"
- "cart paths, center line path to hole and clubhouse structures"
- JSON format
- ~40,000 courses

Confirmed available (Golf Course Information):
- tee box: name, color, yardages
- scorecard: yardage, par, handicap rating
- slope and rating

KEY UNCERTAINTY:
- Exact JSON field names are NOT public (behind partner login).
- Greens/hazards are described as POLYGONS (perimeter GeoData), i.e. arrays of
  lat/lng points outlining each feature — NOT pre-computed front/center/back points.
- So our transform must: (a) accept polygons, (b) derive front/center/back of green
  from the green polygon + the hole's line of play (tee->green direction).

DESIGN DECISION:
- Make field mapping CONFIG-DRIVEN (a FIELD_MAP object). When the real API key
  arrives and we see actual field names, we edit FIELD_MAP only — not the logic.
- Output must match P2P's proven schema exactly (same as White Horse / Army Navy).
