# Migration Notes — from this build-time pipeline to the Phase-4 backend

**Status: PLAN ONLY. We are NOT building the backend now.** This document captures
the intended path so the build-time schema (SQLite) doesn't paint us into a corner.

## Two different things — keep them separate

| | This pipeline (now) | Phase-4 backend (later) |
|---|---|---|
| Role | **Build-time tool.** Assembles a course directory. | **Runtime service.** Serves data + entitlements to the app. |
| Store | SQLite file (`courses.db`), regenerable. | Managed DB (Postgres or DynamoDB). |
| Who runs it | Cloud Claude Code, on demand. | AWS (Amplify/Lambda), always on. |
| Trust | Internal, no users. | Server-authoritative; never trusts the client. |
| Owns | course / holes / contributors *directory data*. | accounts, entitlements, payments, credit ledger. |

The golden rule: **directory data** (what courses exist, their scorecards, and which
holes have been refined) is what this pipeline builds and what migrates. **Runtime
concerns** (who is logged in, what they paid for, how much mapping credit they've
earned) are NOT built here and are NOT in this schema — they belong to the backend,
must be server-authoritative, and (for the credit ledger) fraud-resistant. See
`/CLAUDE.md` → "Security & architecture" and "Launch model & paywall".

## How the tables map to a future backend

The schema uses only portable SQL (plain `INTEGER`/`REAL`/`TEXT`, `PRIMARY KEY`,
`FOREIGN KEY`, `CHECK`, `UNIQUE`; JSON stored as TEXT). Nothing is SQLite-specific.

### → If we go Postgres (relational, closest to today)
Nearly 1:1. The same three tables carry over.
- `INTEGER PRIMARY KEY AUTOINCREMENT` → `BIGINT GENERATED ALWAYS AS IDENTITY` (or `SERIAL`).
- `REAL` lat/lng → `DOUBLE PRECISION` (or PostGIS `geography(Point)` if we want real
  geo queries later).
- `yardage_by_tee` / `hazards` stored as TEXT JSON → `JSONB` (cast on migrate).
- `TEXT` ISO timestamps → `TIMESTAMPTZ`.
- `CHECK (status IN ...)` constraints carry over unchanged (or become enum types).
- Foreign keys + `UNIQUE(course_id, hole_number)` carry over unchanged.

### → If we go DynamoDB (NoSQL, fits Amplify defaults)
Denormalize into items keyed for the app's access patterns.
- `courses` → a `Course` item. PK `COURSE#<id>`.
- `holes` → either a `Hole` item per hole (PK `COURSE#<id>`, SK `HOLE#<n>`) or an
  embedded list on the course item if always read together. JSON fields become native
  maps/lists.
- `contributors` → a `Contributor` item (PK `CONTRIB#<id>`).
- `status` / `source` enums: validate in app code or a Lambda (DynamoDB has no CHECK).
- `UNIQUE(course_id, hole_number)` is enforced by the composite key, not a constraint.
- A GSI on `state` and on `status` covers the index lookups we added in SQLite.

### Field-level mapping (stable across either target)
| Pipeline field | Backend meaning | Notes |
|---|---|---|
| `courses.property_lat/lng` | course's single map point | NOT a hole coordinate; for centering the mapper. |
| `courses.hole_count`, `source_list` | directory metadata | `source_list` supports the ToS/source report. |
| `holes.tee_* / green_*_* ` | per-hole coordinates | **NULL until refined.** Filled at runtime by golfer capture or an iGolf import — never by this pipeline. |
| `holes.status` | confidence level | `unverified` → `refined`/`verified` happens in the backend when a golfer captures GPS. |
| `holes.refined_by` → `contributors.id` | attribution | becomes the backend's account/contributor id. |
| `holes.source` | provenance | `scorecard` (this pipeline) vs `subscriber`/`igolf` (runtime). |
| `contributors.quality_weight` | QA control | lets the backend down-weight or roll back a bad contributor's holes. |

## What is deliberately NOT in this schema (built later, in the backend)
- **Accounts / auth** — managed provider (Cognito/Auth0/Clerk); created at purchase.
- **Entitlements** — which courses a user unlocked. Server-authoritative; the app
  must not trust its local copy.
- **Payments** — Stripe only; no card data stored anywhere.
- **Mapping-credit ledger** and **course-referral revenue-share** — money-adjacent,
  deferred to a later version, must be server-authoritative and fraud-resistant.

If/when we build the backend, none of the above should be retrofitted onto the SQLite
file — it stays a build-time directory tool and the backend owns runtime state.
