# ShadesCaddie v4 — Upload & Army Navy Mapping Guide

## What changed in this build

- **Nine-based course model.** Army Navy is now three 9-hole nines (Blue, Red, White),
  each mapped ONCE. The app assembles 18-hole rounds at runtime.
- **Start-nine / finish-nine picker.** Subscriber picks a starting nine, then chooses
  "Just these 9" or "Add a second nine," then picks the finishing nine. Any combination
  works (Blue/Red, Red/Blue, White-only, etc.) from just three small files.
- **True 9-hole play** is now a first-class option.
- **White Horse is untouched** — same 18-hole experience, same data, same behavior.
- **Safety:** this is a SEPARATE file (`rangefinder-v4.html`). Your live app at
  `rangefinder.html` keeps working. Nothing you have now is at risk.

## Files in this package

| File | Where it goes in the repo | Purpose |
|------|---------------------------|---------|
| `rangefinder-v4.html` | repo root | The new app (test before promoting) |
| `course-mapper-armynavy.html` | repo root | 9-hole mapper, pre-centered on Fairfax VA |
| `courses/army-navy-blue.json` | `courses/` folder | Blue nine — pars + tee yardages filled, coords empty |
| `courses/army-navy-red.json` | `courses/` folder | Red nine — same |
| `courses/army-navy-white.json` | `courses/` folder | White nine — same |
| `COURSE-DATA-STRATEGY.md` | repo root (reference) | Permanent 3-tier data strategy |

## Upload steps (GitHub)

1. Go to `github.com/harriskevint-hue/plans2putts`
2. **Create the courses folder + files:** Add file → Create new file →
   type `courses/army-navy-blue.json` (typing the slash creates the folder).
   Paste the contents of the blue stub, commit. Repeat for red and white.
   (Or Add file → Upload files and drag all three after creating the folder once.)
3. **Upload the app + mapper:** Add file → Upload files → drag
   `rangefinder-v4.html` and `course-mapper-armynavy.html` → commit.
4. Amplify auto-deploys in ~2 minutes.

## Test order (do this before relying on it)

1. Open `ShadesCaddie.com/rangefinder-v4.html` on your phone.
2. **Confirm White Horse still works** — select it, play, verify yardages. This proves
   no regression.
3. Select **Army Navy — Blue** → "Add a second nine" → **Red**. You'll get an 18-hole
   round, par 72, Blue tees 6644. (Distances won't calculate yet — coords aren't mapped.)
4. Select **Army Navy — White** → "Just these 9." Confirms 9-hole play.

## Mapping the nines (this is what makes distances work)

Open `ShadesCaddie.com/course-mapper-armynavy.html` on a computer (big screen, satellite view).

For EACH nine (do Blue and Red first — that's your played round):
1. Type the course name (e.g. "Army Navy — Blue").
2. For each of the 9 holes: select Tee, click the tee box on the satellite image;
   select Green Front/Center/Back, click each; add Hazards as needed.
3. Use the Blue/Red scorecards as your guide for what's on each hole.
4. Click **Export JSON** (or Copy) when the nine is done.

Then drop each nine's mapped coordinates into the matching file in `courses/`.
The pars and tee yardages are already correct in those files — you're only adding
the lat/lng coordinates. Once a nine's coords are in, it plays exactly like White Horse.

## Important

- **Coordinates are intentionally empty** in the stub files. They MUST come from the
  mapper. We never fabricate coordinates — a wrong lat/lng = a wrong yardage on a real shot.
- The Army Navy mapper builds **9 holes** (not 18) to match the nine-hole files.
- When v4 is confirmed working, promote it by renaming/replacing `rangefinder.html`
  with the v4 contents — and keep a copy of the old one just in case.
