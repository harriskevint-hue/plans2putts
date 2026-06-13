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
**Washington** — chosen so coverage matches the launch wave; White Horse members
play other WA courses) before scaling. Use only data sources whose terms permit it;
report sources used.

LISTED vs PLAYABLE — do not conflate (matters for KT's course-manager outreach):
a pipeline directory entry means a course is LISTED (name/address/scorecard,
coordinates NULL). A course is only PLAYABLE once it has per-hole coordinates
(from iGolf, satellite pin-placement, or a golfer mapping it). Never describe a
listed-only course as playable/working.

## iGolf (active thread)
iGolf (Ryan Eibner) confirmed they have Full Vector GPS data and offered trial
access; KT's reply is sent. Plan: take the call, get trial creds, test the
pre-built `integrations/igolf/` code against White Horse (KT's ground-truth
self-mapped course), confirm the four open questions, then decide. Do not commit
on the call.

## Launch model & paywall (decided)
First launch = simplest honest slice, then iterate (ship-then-improve):
- FREE tier: full rangefinder on ONE course (White Horse, verified/playable). No
  account required for free use — keep friction and stored data near zero.
- PAID: unlock additional courses. Two mechanisms built from the start —
  per-course/pack unlock (leads early, small catalog) AND annual all-access (lightly
  promoted until the catalog grows). Accounts are created at PURCHASE, not for free use.
- DEFERRED to a later version (do NOT build in v1; both are money-adjacent and must be
  built carefully + server-authoritative + fraud-resistant): (1) mapping-credit ledger
  (earn credit against fees by mapping), (2) course-referral revenue-share (pay a course
  when its members subscribe). Fine to discuss with course managers now / handle manually.

## Security & architecture (build securely by default)
- SECRETS NEVER COMMITTED. Repo is PUBLIC. API keys (GolfCourseAPI, iGolf, Stripe, AWS)
  live in environment variables / a gitignored `.env`, never hardcoded. Rotate anything
  already exposed. Never print a secret into a committed file.
- AUTH: use a managed provider (Cognito / Auth0 / Clerk). Never store passwords, never
  build custom login. Account data appears only at purchase.
- PAYMENTS: Stripe only (KT has an account). Never store or handle card data.
- ENTITLEMENTS ARE SERVER-AUTHORITATIVE. The server decides which courses a user can
  access; the app must NOT trust its own local copy. Same rule for any future credit/
  referral balances — calculated and stored server-side, never trusted from the client.
- Validate and sanitize all user/subscriber input. HTTPS only.
- Collect minimal personal data; only what a purchase actually requires.

## How to work here
- Orient before building; confirm understanding before writing code.
- One contained task at a time; show your plan before big executions.
- The repo is the project's memory (survives new sessions). Commit work here.
- Ask before modifying files KT hasn't pointed you to.
- When unsure about strategy, flag it — KT relays strategic questions to a
  separate navigator chat that holds the project history.

## Safety & review (KT is a non-programmer)
- Review changes before committing; explain in plain language what changed and why.
- Work in small, reversible steps. Before a large or risky change, note that KT can
  use `/rewind` to undo, and commit a known-good state to Git first.
- Never run destructive shell commands (rm, mv over existing files, force-push)
  without explicitly flagging it and getting KT's OK first. Note: `/rewind` does NOT
  undo files changed by bash commands — only direct edits.
- Advanced features (hooks, worktrees, subagents, agent teams) are used ONLY with a
  clear, stated reason and KT's sign-off — never by default. The project builds with
  ordinary file editing + git.

## Reference bundle + navigator protocol
- `claude-code-docs/` holds distilled current Claude Code references (e.g.
  CHECKPOINTING-AND-HOOKS.md) plus the Claude-Code-Reference PDF at the repo root.
- The navigator chat cannot fetch live docs. Protocol: before the navigator writes
  instructions that touch an advanced Claude Code feature, it NAMES the reference doc
  it needs and KT pastes that doc into the navigator chat. KT does not need to detect
  when an advanced topic applies — the navigator flags it and requests the doc.
- Claude Code itself is the authority on its own current mechanics; when in doubt about
  how a Claude Code feature works, Claude Code should rely on its own current knowledge
  or check code.claude.com/docs rather than guessing.

## Commands & conventions
- This is currently a static web app (HTML/JS, localStorage). Production file:
  `rangefinder.html` (White Horse working). `rangefinder-v4.html` is nine-based,
  untested on device. Course JSON lives in `courses/`.
- No build system yet. If you add tooling (e.g. for the data pipeline), document
  the commands here so future sessions know them.
- White Horse Golf Club (Kingston, WA) is the ground-truth test course.
