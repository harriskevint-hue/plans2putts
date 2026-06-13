# CLAUDE.md — ShadesCaddie / Plans2Putts (P2P)

Auto-loaded every Claude Code session. Read this first, then read the three
reference docs below before doing substantial work. Keep this file under ~200 lines.

## What this project is
ShadesCaddie (project name Plans2Putts / P2P) is a GPS golf rangefinder web app.
A subscriber picks a course; the app shows live yardages to the green
(front/center/back), hazards, and a voice caddy, plus stroke counting and a
scorecard. Audio-first: it must be a FULL experience on a phone + any earbuds or
bone speakers. Meta smart glasses (voice, or Ray-Ban Display HUD) are a PREMIUM
ENHANCEMENT, never a requirement. Business model: ~$4.99/mo or ~$39.99/yr.

Owner: KT (Kevin Harris). KT is a non-programmer — explain what you're doing in
plain language, work in small steps, show results, and never silently fabricate
data.

## Read these before substantial work (repo ROOT)
- `PROJECT-STATUS.md` — current state, decisions, lessons, to-do list. START HERE.
- `COURSE-DATA-STRATEGY.md` — the full course-data + growth strategy (the canonical
  rules for how course data is sourced, labeled, and refined).
- `CLAUDE-CODE-BRIEF-data-pipeline.md` — the spec for the data-pipeline task.
- `CLAUDE-CODE-NOTES.md` — how we work effectively with Claude Code (reference).
Also: `V4-UPLOAD-AND-MAPPING-GUIDE.md` lives in `docs/`.

## The one hard rule: never fabricate coordinates
The rangefinder needs per-hole GPS coordinates (tee, green front/center/back,
hazards). NO free/cheap source produces these:
- Census geocoder → ONE property point per course, not hole coordinates.
- Scorecards (GolfCourseAPI) → par/yardage/handicap only, no coordinates.
- USGS/satellite imagery → a picture, not coordinates (a canvas for humans, not a
  coordinate source).
Real coordinates come from only three places: an iGolf license, a golfer's
on-course GPS capture, or careful human satellite pin-placement.
**Therefore: never invent, estimate, or auto-detect coordinates. Unknown
coordinates stay NULL with status "unverified." A wrong coordinate = a wrong
yardage on a real shot, which is the one failure this product cannot have.**

## Data model essentials (per hole)
Every hole carries a status and attribution:
- `status`: "unverified" (rough: iGolf or human estimate) | "refined" (a golfer
  walked it) | "verified".
- `refined_by`, `refined_at`, `source` ("scorecard" | "subscriber" | "igolf").
Per-hole attribution is the quality-control backbone — build it in from day one;
it lets us weight or roll back a bad contributor's data. No course is ever empty;
unverified holes are honestly labeled "not yet reviewed by a golfer — help improve."

## Two contribution types — do NOT conflate
- Scorecard upload: effortless, confirms par/yardage, does NOT add coordinates.
  Badge "Scorecard confirmed." Modest reward.
- On-course GPS tap (one tap at the green): the REAL coordinate refinement.
  Badge "GPS verified." Weight most. Never badge a hole "GPS verified" from a
  scorecard upload.

## Current focus / data pipeline
The pipeline builds a course DIRECTORY (name → address → geocode → scorecard),
NOT working distances. It produces coverage for launch; coordinates come later from
golfer refinement or iGolf. See CLAUDE-CODE-BRIEF-data-pipeline.md. Start small:
Step 0 (database with the status/attribution schema) + Step 1 (ONE test state,
Illinois) before scaling. Use only data sources whose terms permit it; report
sources used.

## iGolf (active thread)
iGolf (Ryan Eibner) confirmed they have Full Vector GPS data and offered trial
access; KT's reply is sent. Plan: take the call, get trial creds, test the
pre-built `integrations/igolf/` code against White Horse (KT's ground-truth
self-mapped course), confirm the four open questions, then decide. Do not commit
on the call.

## How to work here
- Orient before building; confirm understanding before writing code.
- One contained task at a time; show your plan before big executions.
- The repo is the project's memory (survives new sessions). Commit work here.
- Ask before modifying files KT hasn't pointed you to.
- When unsure about strategy, flag it — KT relays strategic questions to a
  separate navigator chat that holds the project history.

## Commands & conventions
- This is currently a static web app (HTML/JS, localStorage). Production file:
  `rangefinder.html` (White Horse working). `rangefinder-v4.html` is nine-based,
  untested on device. Course JSON lives in `courses/`.
- No build system yet. If you add tooling (e.g. for the data pipeline), document
  the commands here so future sessions know them.
- White Horse Golf Club (Kingston, WA) is the ground-truth test course.
