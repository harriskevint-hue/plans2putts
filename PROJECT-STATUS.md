# ShadesCaddie / Plans2Putts — PROJECT STATUS
**Last updated: June 11, 2026 (end of session 3 — strategy deep-dive)

> **IF YOU ARE A NEW CLAUDE SESSION:** Read this file first, then read every other
> .md file in this repo's `docs/` folder (or root). Fetch any app file you need from
> `https://raw.githubusercontent.com/harriskevint-hue/plans2putts/main/<filename>`.
> Kevin (KT) is a non-programmer on Windows; you write the code, he clicks. Never
> fabricate GPS coordinates. Never put API keys in client code. Do not break the
> working production app — build changes in separate files, test, then promote.

---

## 1. WHAT THIS IS

**ShadesCaddie** (project name Plans2Putts / P2P) is a GPS golf rangefinder web app
for Meta smart glasses. Live yardages to green front/center/back, hazards, voice
caddy via the glasses' speakers/screen reader, stroke counting, scorecard with PDF
download, focus mode (HUD auto-hide). Works on Meta Ray-Ban Display (visual HUD +
voice) and Oakley Meta HSTN (voice-only via Bluetooth audio with phone in pocket).

- **Business:** $4.99/mo or $39.99/yr subscription (Stripe pending). Sold outside
  Meta's platform (Bluetooth-audio path has no Meta restrictions).
- **Domains:** ShadesCaddie.com (primary, live), ShadeCaddie.com, ShadesCaddie.golf,
  ShadeCaddie.golf (301 redirects via Namecheap).
- **Infrastructure:** AWS Amplify auto-deploys from this GitHub repo (account
  "PERMITPREVIEW", us-east-2, resources prefixed `shadescaddie-`; dedicated AWS
  account planned post-revenue via AWS Organizations). Route 53 hosted zone for
  shadescaddie.com. MFA enabled on root.
- **Meta:** registered in Wearables Developer Center; app loads on glasses by URL
  (Developer Mode → Connect a Web App).

## 2. WHAT IS LIVE AND WORKING (do not break)

| File | Status |
|---|---|
| `index.html` | Landing page (light theme, AI golfer images, pricing, FAQ) — LIVE |
| `rangefinder.html` | Production app — **White Horse GC fully working on glasses** |
| `course-mapper.html` | Satellite pin-mapping tool (18-hole, White Horse centered) |
| `gps-spike.html` | GPS accuracy test (passed: 3.0 m outdoors) |

White Horse Golf Club (Kingston, WA) is fully mapped (embedded in rangefinder.html)
with 6 tee sets. Verified on-course on the Ray-Ban Display.

## 3. BUILT & TESTED — REPO UPLOAD STATUS (as of end of session 2)

**NOW LIVE IN REPO (uploaded & verified this session):**
- ROOT: `rangefinder-v4.html`, `course-mapper-armynavy.html`, updated `README.md`
- `docs/`: `PROJECT-STATUS.md`, `COURSE-DATA-STRATEGY.md`, `V4-UPLOAD-AND-MAPPING-GUIDE.md`
- `courses/`: `army-navy-blue.json`, `-red.json`, `-white.json` (all 3 verified byte-for-byte
  against masters: par 36 each; Blue/Red assembles to 18, par 72, blue tees 6644)

**STILL TO UPLOAD:**
- `integrations/` folder (iGolf + GolfCourseAPI code) — packaged as batch4-integrations.zip,
  NOT yet uploaded. Pure code-preservation; nothing live depends on it. (TO-DO)

**Details of what these files do:**

1. **`rangefinder-v4.html`** — nine-based architecture. Subscriber picks a starting
   nine → "Just these 9" or "Add a second nine" → picks finishing nine. True 9-hole
   rounds supported. White Horse unchanged inside it. Separate file so production is
   untouched until v4 is verified, then promote it to `rangefinder.html`.
   NOT YET TESTED on device — White Horse regression test is the next action.
2. **`courses/army-navy-*.json`** — nine-hole stubs. Pars + all tee yardages filled
   from physical scorecards; **all coordinates null — must be mapped** (see §5).
3. **`course-mapper-armynavy.html`** — 9-hole mapper, pre-centered on Fairfax VA.
4. **`docs/COURSE-DATA-STRATEGY.md`** — the permanent three-tier data strategy.
5. **`docs/V4-UPLOAD-AND-MAPPING-GUIDE.md`** — upload + mapping walkthrough.
6. **iGolf integration** (`igolf-transform.js`, `lambda-course-proxy.js`, tests —
   30/30 passing) — converts iGolf Connect polygons to P2P schema (derives green
   front/center/back from green polygon + tee line-of-play). Config-driven FIELD_MAP;
   waiting only on iGolf credentials/license. In batch4 zip; add under `integrations/igolf/`.
7. **GolfCourseAPI integration** (`gca-transform.js`, `live-test.js`, browser tester,
   16/16 tests) — scorecard-layer filler. In batch4 zip; add under `integrations/golfcourseapi/`.

## 4. THE COURSE-DATA STRATEGY (permanent — full doc: COURSE-DATA-STRATEGY.md)

Three-tier fallback so a subscriber is NEVER stuck:
- **Tier 1:** self-mapped library (White Horse now; Army Navy nines next).
- **Tier 2:** commercial API (iGolf is the chosen candidate — see §6).
- **Tier 3:** on-demand self-mapping via the mapper — the guarantee. On any data
  failure the app routes the subscriber to the mapper. **Never invent coordinates.**

Nine-hole clubs (like Army Navy): map each nine ONCE; app assembles 18s at runtime.

**P2P course JSON schema (the contract):**
`{course, holes:[{hole, par, handicap, tee:{lat,lng}, green:{front,center,back:{lat,lng}}, hazards:[{label,lat,lng}], dogleg, layups:[]}], tees:{key:{label,total,holes:[yards]}}}`

## 5. IMMEDIATE TO-DO (in order)

### SESSION 3 SUMMARY (June 11 — strategy, no new app code)
This was a strategy + planning session. Accomplished: (a) ran GolfCourseAPI live test
via browser tester — confirmed scorecard-only, no coordinates, both courses present;
(b) fully evaluated and rejected DIY workarounds for GPS coordinates (geocoding,
scraping, satellite auto-detection, training an AI agent) — all either illegal, don't
produce coordinates, or are a company-sized ML project; (c) developed the complete
crowdsourced data + growth model (see COURSE-DATA-STRATEGY.md, much expanded); (d)
wrote the Claude Code data-pipeline brief. NO changes to app code this session.
NOTE: docs updated this session are NOT yet uploaded to GitHub (Kevin will upload).

0. **Claude Code data pipeline** — brief written: `docs/CLAUDE-CODE-BRIEF-data-pipeline.md`.
   Builds a course directory (name/address/geocode/scorecard) for 10,000+ courses as a
   launch skeleton; coordinates stay NULL/unverified (NO fabrication). Run via cloud
   Claude Code (avoids installing Node on Kevin's non-owned laptop). First step is
   getting cloud Claude Code running, then Step 0/1 for one test state (Illinois).
   NOTE: this produces a directory, NOT working distances — does not replace iGolf/
   on-course capture for coordinates.
   FIRST ACTUAL STEP: get cloud Claude Code running (see support.claude.com — local
   install needs Node, which Kevin can't install on company laptop). Then point it at
   this repo + the brief.

1. **Test v4 on phone — White Horse regression check (NEXT ACTION).** Open
   shadescaddie.com/rangefinder-v4.html, select White Horse. It must go STRAIGHT to
   tee selection (NOT ask "how many holes" — that's only for nines), then play exactly
   like production rangefinder.html. Then optionally test a nine (Blue→9, Blue+Red→18).
2. **Add `integrations/` folder to repo** (batch4-integrations.zip) — code preservation.
   Two subfolders igolf/ and golfcourseapi/, each with its own README. Low urgency.
3. **Map Army Navy Blue + Red coordinates — BLOCKED.** No hole-routing reference
   available. Scorecards have data tables only, NOT overhead layout diagrams. Kevin
   played it once (scramble) so mapping from memory is hard. NEED a routing source
   first: Army Navy CC website course map, a yardage book, or a return visit. Until
   then, Army Navy Blue/Red show in v4 but distances won't calculate. Parked, not dropped.
4. **iGolf — RESPONDED, trial offered (ACTIVE THREAD).** Ryan Eibner replied June 11
   confirming Full Vector GPS data + $5k entry + trial access. Reply sent accepting
   trial & call. NEXT: schedule call, get trial credentials, test the pre-built iGolf
   integration against White Horse (ground truth), confirm the 4 open questions
   (Vector in entry tier? transaction counting? paid-subscription license? coverage?).
   Decide AFTER testing — don't commit on the call. This substantially de-risks the
   GPS-coordinate problem and may be a faster path to launch-with-distances than the
   DIY data pipeline.
5. **Rotate the GolfCourseAPI key** — NO self-service rotation exists (confirmed: their
   API has only register/activate endpoints, no key management). Must EMAIL support to
   reset. Low priority: key only reads public scorecard data, ~$10/mo capped exposure.
   Better fix going forward: never paste keys in chat; keep in Lambda env only.

DONE this session: GolfCourseAPI live test (see §6); all root/docs/courses files
uploaded & verified in repo; ramp-up + wrap-up doc system established.

## 6. DATA-PROVIDER VERDICTS (evidence-based, June 2026)

| Provider | Verdict |
|---|---|
| **iGolf** | **RESPONDED June 11 — Ryan Eibner, Global Account Manager (ryan.eibner@igolf.com).** Confirmed in writing: 40,000+ courses / 177 countries, REST API + JSON, and crucially "Full Vector GPS Data for rich 2D mapping" = the per-hole green/tee/hazard coordinates we need. Entry licensing transaction-based, $5,000/yr, stated as sufficient for "initial implementation and early-stage scaling." OFFERED TRIAL ACCESS to validate data. Reply sent (iGolf-Reply-to-Ryan.md) accepting trial + call, with 4 open questions: (1) is Full Vector GPS in the $5k entry tier or higher; (2) how are transactions counted / cost to scale; (3) does license permit paid-subscription resale; (4) trial validation against White Horse (our ground truth). NEXT: take call, get trial creds, test our built integration vs White Horse, THEN decide. Do not commit on the call. |
| **GolfCourseAPI** | **TESTED LIVE THIS SESSION — confirmed scorecard-only, no per-hole coordinates** (verified via live browser test AND official OpenAPI schema: every hole is just {par, yardage, handicap}; one property-level lat/lng only). Both courses present: White Horse (id 18462); Army Navy Fairfax Blue/Red (id 10779) & White/Blue (id 10742), plus Arlington combos. $9.99/mo. Best uses: (1) auto-fill scorecard data when adding courses, (2) cross-check hand-entered pars/yardages. NOT a coordinate source. Bonus data available: bogey rating, front/back nine ratings, total_meters. NO self-service key rotation (email support). |
| **Golfbert** | Right data shape (polygons + flag coords, SigV4 auth) but activity/pricing unverified; parked. |
| **TruGolf** | NO course API (confirmed by Ryan Jones email): player/round data only. Closed for course data; possible future round-data partner. |

## 7. HARD-WON LESSONS (do not relearn)

- `zip -j` when packaging files for GitHub upload (subfolder paths break Amplify).
- GitHub web upload must land files at repo ROOT (or intended folder) — a stray
  `home/claude/` folder once broke the deploy.
- GitHub makes a folder by committing a file into it — type `folder/file.ext` in
  "Create new file" (the slash makes the folder). No empty-folder creation exists.
- GitHub web upload sometimes lists each file TWICE if selected twice — delete the
  dupes (✗) before committing, or re-do the upload with a single clean selection.
- GitHub raw URL (raw.githubusercontent.com) CACHES ~1–2 min after commit — a fresh
  commit may read as empty/1-byte briefly. Not an error; re-fetch after a minute.
  Browser file view can also show a stale "1 Byte / 0 lines" render — refresh page.
- To verify a committed file's content, fetch the raw URL (after cache settles) or
  use the GitHub API; don't trust the first render.
- Glasses runtime: Web Speech API unsupported → voice via ARIA live regions and the
  glasses' screen reader. D-pad nav needs `.focusable` + keydown handling. Black
  background = transparent on the additive display.
- App open gesture on glasses: first tap announces, second tap opens.
- GPS permission on glasses: auto-retry every 8 s (button taps were unreliable).
- API keys: server-side only (Lambda env). Rotate any key pasted into chat. Note:
  not every provider offers self-service key rotation (GolfCourseAPI does not).
- Amplify auto-deploys ~2 min after any commit to `main`.
- Multi-nine course mapping needs an OVERHEAD ROUTING DIAGRAM, not just a scorecard.
  Scorecards are data tables (yardage/par/handicap), they do NOT show which green/tee
  belongs to which nine. Get a course-layout map before attempting to map a shared-
  property multi-nine club like Army Navy Fairfax.
- Army Navy flag colors (from card): Red flag = front, White = center, Gold = back.
- GolfCourseAPI / similar: bulk-scraping the whole database violates ToS AND wouldn't
  help (no coordinates). Use per-course on-demand lookups only. Coverage-with-coords
  comes from licensing iGolf, not scraping.

### Session 3 strategy lessons (data coverage)
- NO cheap/free workaround produces per-hole GPS coordinates. Confirmed dead ends:
  Census geocoder (gives ONE property point, not green/tee coords); scorecard photos
  (no coords); USGS imagery (a picture, not coords); AI auto-detection of greens from
  imagery (unreliable, a wrong coord = wrong yardage on a real shot); training a
  custom AI agent (a company-sized ML project, costs more than licensing iGolf).
- Coordinates come from exactly 3 places: license (iGolf), golfer on-course GPS
  capture, or careful human satellite pin-placement. There is no 4th shortcut.
- USGS imagery's real use = a CANVAS for humans/subscribers placing pins, not a
  coordinate source. And a live satellite map view (Google/Apple tiles) usually beats
  bulk-downloading USGS images (free, current, no storage). Cache USGS per-course only
  for offline mapping on remote courses.
- Two contribution types must NOT be conflated: scorecard upload (effortless, confirms
  scorecard, does NOT improve coordinates) vs. on-course GPS tap (the real refinement).
  Separate badges. Design for "one tap at the green while putting out" as the minimum-
  effort high-value contribution.
- Honest framing of the pipeline: it builds a DIRECTORY (name/address/geocode/
  scorecard), not a working rangefinder dataset. Good for coverage/credibility at
  launch IF every unverified hole is honestly labeled. Does not substitute for a GPS
  provider — those solve different problems.
- Sequencing caution: the pipeline produces data that needs the Phase 4 backend to
  serve, for an app not yet beta-validated. Consider proving the core app + a few
  well-mapped courses BEFORE scaling to 10,000. Market lead comes from the experience
  being real on N courses, not from a large directory that can't show distances.
- Kevin can't install Node on his company-owned laptop → use CLOUD Claude Code. The
  app lives in GitHub regardless of where Claude Code runs; nothing to "migrate."

## 8. PROJECT-STATUS / SESSION PROCEDURES (the ramp-up & wrap-up system)

The repo is the project's permanent brain — survives cleared sandboxes, new chats,
and the 100-image limit. Two matched prompts:

**RAMP UP a new chat** — paste:
> "Fetch and read
> https://raw.githubusercontent.com/harriskevint-hue/plans2putts/main/docs/PROJECT-STATUS.md
> then read the other docs it references and list the repo contents. Tell me where we
> left off and what's next."

**WRAP UP a session** — paste:
> "Wrap up the day: update PROJECT-STATUS.md with everything we accomplished this
> session, what changed in the app or strategy, any new lessons learned, and the
> current to-do list. Then package every new or changed file from today into a flat
> zip ready for GitHub upload, list exactly what goes where in the repo, and give me
> the step-by-step upload checklist."

(Short wrap-up for small sessions: "Update PROJECT-STATUS.md and give me just the
changed files.")

Requirements: repo stays public; chat has the code/analysis tool (claude.ai does).
Backup: Claude can search past chats by topic; memory carries a project summary.
After any wrap-up, upload the refreshed PROJECT-STATUS.md to docs/ so it stays current.

- **P1–P3 (done):** rangefinder, voice, stroke/score, scorecard+PDF, focus mode,
  localStorage persistence, glasses operation.
- **P3.5 (current):** nine-based v4, Army Navy, provider selection, ramp-up docs.
- **P4 (next):** AWS backend (Lambda proxy, Cognito accounts, DynamoDB/Airtable
  round history), Stripe, iGolf Tier 2, Google Play (TWA, $25), landing-page demo
  video, beta testers. Break-even ≈170 subs @$4.99 if iGolf at $5k/yr (≈84 without).
