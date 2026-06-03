# Step 0 — Go / No-Go Validation (Cloud build)

**Purpose:** Before building the golf HUD app, prove the one thing the project truly
depends on — usable GPS on the glasses — and stand up the cloud setup. Everything
lives in the cloud; nothing on your laptop.

This file is written for a non-programmer. You can also hand it to Claude Code on the
web and say "help me work through STEP-0-CHECKLIST.md."

**Target course:** White Horse Golf Club, 22795 Three Lions Pl NE, Kingston, WA 98346
(18 holes; approx 47.7696, -122.5293)

---

## Your cloud stack (using accounts you already have)

| Layer | Tool | Why |
|---|---|---|
| Code home | **GitHub** repo | Code lives in the cloud, not your laptop |
| Building | **Claude Code on the web** (claude.ai/code) | Builds in the cloud against your repo; needs Max ✓ |
| Hosting (the URL the glasses load) | **GitHub Pages** | Free, automatic HTTPS (required for GPS), publishes from the repo |
| Course data | A small **JSON file** in the repo | Loads instantly, works even with no signal mid-round |
| (Optional) friendly data editing | **Airtable** or **Google Sheets** | Edit hole coordinates in a grid; Claude Code syncs it to the app |
| (Reserved for later) | **AWS** | Only if you later want cross-device saved rounds / a real backend |

You do NOT need a paid course-data API. Because it's one course you know, we map
White Horse ourselves, once (see Gate 2).

---

## The one gate that can kill the project: GPS

Uses **`gps-spike.html`**.

**Desktop check (today, no glasses):**
1. Ask Claude Code: "serve gps-spike.html over localhost." Open it in Chrome.
2. Click START, allow location, watch the Verdict line.
3. Click "Copy log" and paste it into the planning chat.

**On-glasses check (needs hardware, done outdoors):**
1. Deploy the app to its GitHub Pages URL and open it on the glasses.
2. Stand outside with clear sky, click START, walk a little.
3. Read the verdict; copy the log.

**Pass criteria:**
- PASS — updates keep coming AND accuracy stays at/under ~5 m (≈5.5 yd)
- MARGINAL — updates come but accuracy is 5–15 m (works; expect rough yardages)
- FAIL — no geolocation, no updates, or accuracy over 15 m

**Deliverable:** `gps-results.md` — desktop log + on-glasses log, verdict on top.

---

## Gate 2 (now just a build task): map White Horse

No availability risk anymore — we own the data. Uses **`course-mapper.html`**.

1. Open `course-mapper.html` in your browser (desktop, big screen).
2. It shows a satellite view of White Horse. For each of the 18 holes, click to drop
   pins for: the tee, the green front / center / back, and any hazards.
   Tracing from satellite imagery is more precise than walking with phone GPS.
3. Drag any pin to fine-tune it.
4. Click "Export JSON" — that file (`white-horse-course.json`) is your course data.
   Hand it to Claude Code to drop into the app.

**Deliverable:** `white-horse-course.json` — all 18 holes mapped.

> Tip: Export early and often. The tool keeps data only while the page is open, so
> export to save your progress; re-import to resume.

---

## Supporting checks (after the GPS gate passes)

- **Display constraints fact sheet** — pull from Meta's Web Apps docs: resolution,
  font minimums, refresh, overlay persistence, location permissions model.
  Deliverable: `display-constraints.md`.
- **Input model** — how the web app receives input on the glasses; whether Neural
  Band gestures are exposed to web apps. Note it in the same file.

---

## Who does what

| Task | Claude Code (web) | Hardware (you, wearing glasses) | You (by hand) |
|---|---|---|---|
| Create the GitHub repo + Pages hosting | helps set up | | ✅ click-through |
| Build/serve the GPS spike | ✅ | | |
| Desktop GPS test | | | ✅ |
| On-glasses GPS test | | ✅ | ✅ |
| Map the course (course-mapper) | provides the tool | | ✅ click pins |
| Read Meta docs, write fact sheet | ✅ | | |
| Accept Meta developer terms | | | ✅ |
| Go/no-go decision | | | ✅ (with planning chat) |

---

## Deliverables checklist

- [ ] GitHub repo created, GitHub Pages turned on (HTTPS URL live)
- [ ] `gps-spike.html` deployed to the Pages URL
- [ ] `gps-results.md` — desktop + on-glasses verdicts
- [ ] `white-horse-course.json` — all 18 holes mapped
- [ ] `display-constraints.md` — limits + input/permissions
- [ ] `go-no-go.md` — proceed / redesign / wait, with reasons

---

## First things to say to Claude Code on the web

1. "Create a new GitHub repo for a Meta Ray-Ban Display web app, add the
   gps-spike.html and course-mapper.html files I have, and turn on GitHub Pages so I
   get an HTTPS URL."
2. "Give me the GitHub Pages URL for gps-spike.html so I can open it on the glasses."
3. (After mapping) "Add white-horse-course.json to the repo — this is the course data
   the app will read."

Paste any errors or anything confusing into the planning chat and we'll work through it.
