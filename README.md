# SAMANVAY: Integrated Institution Complaint Monitoring (SIH26264, AICTE)

**One institution. One view. No duplicate action.** SAMANVAY puts every complaint about a college in one place,
warns when two AICTE units are acting on the same college, and chases cases before they go late.

> Prototype. All data is synthetic (12 fictional institutions, 120 cases). Not connected to any AICTE system.

## Run it (macOS/Linux, Postgres running locally)
```bash
make setup        # venv, npm install, create DB role + databases, migrate, seed; copies .env.example -> .env
make api          # API on :8010   (terminal 1)
make web          # web on :5173   (terminal 2) -> http://localhost:5173
```
One-tap demo roles on the login page, or password `samanvay-demo-2026` (usernames: officer, officer-pgrc,
head, head-pgrc, coordinator, management, admin). Docker instead: `docker compose up --build` → http://localhost:8080.

| Command | What |
|---|---|
| `make seed` | reset to the demo data (do this before and after a demo) |
| `make fit` | check every page fits at 320–1440 px (no sideways scroll, nothing cut off) |
| `make test` / `make e2e` | backend + frontend tests / Playwright demo path (needs api + web; reseed after) |
| `make evaluate` | measure the matcher → docs/MATCHING_EVAL.md |
| `make facts` | recompute docs/SLIDE_FACTS.md |
| `make demo-check` (`SEND=1`) | green/red readiness list (and send a real test email) |
| `make test-email` (`API=https://…`) | send one real email to TEST_ALERT_EMAIL, fail loudly if not delivered |
| `make tamper` / `make untamper` | audit-log tamper demo |

## College users (complainants)
"Create an account" on the sign-in page: 2 steps (about you, your college), city or PIN resolved offline from the
India Post directory (old names like Poona work; ambiguous towns ask; nothing ever blocks sign-up), then a 6-digit
email code. Then: File a complaint (3 steps, autosaved, proof files checked) → reference number + QR → Track.
The system picks the unit and runs overlap detection; complainants never see officers, remarks or other complaints.
Demo college user: `student` (R. Verma, Narmada). In development the code is also printed in the API log.
Data source and licence: docs/DATA_SOURCES.md.

## Architecture
React + TypeScript + Vite → `/api` proxy → FastAPI → PostgreSQL (SQLAlchemy, Alembic). APScheduler runs the daily
SLA/escalation job, email retry and a heartbeat. Session = JWT in an httpOnly cookie + `X-Requested-With` CSRF header.

```
backend/app/services/matching.py   name normalisation, RapidFuzz, TF-IDF, pair score with reasons
                     overlap.py    alerts per institution, suggestions, conflict guard
                     workflow.py   create/assign/action/transfer/escalate/dispose/link/merge, next-step rules
                     sla.py        SLA stages, ageing buckets, escalation ladder (digest emails)
                     audit.py      hash-chained audit log (DB trigger refuses UPDATE/DELETE)
                     mail.py       SMTP or Brevo HTTPS, email log, one retry; sms.py = "not configured"
frontend/src/pages                 Today, Cases, Case, Institution 360, Overlaps (explainer), Dashboard, Reports, Admin…
```
Data model: institution (aliases), unit, case, case_event, case_link, overlap_alert, notification, email_log,
audit_log, setting (Admin-editable rules). How the matching works and fails: docs/MATCHING_METHOD.md.

## What is real and what is simulated
| Part | Status |
|---|---|
| Institutions, cases, officers | Simulated (fictional, river names) |
| AICTE integration | None. Integration points: REST API (`/docs`), CSV/PDF export |
| Overlap detection, name matching | Real, rule-based (not AI); accuracy measured on synthetic data only |
| Emails | Real sender + log, when configured (see Email status) |
| SMS | Not built ("SMS planned") |
| Demo clock | Simulated time (Admin only) |
| Audit log, roles, workflow, reports | Real |
| Hindi | Every UI string; server-written reasons stay English; under review |

## If a judge asks
See docs/JUDGE_QA.md. Short: overlap = ID/fuzzy name + category + text similarity + dates, scored with reasons;
not AI; never blocks officers; synthetic data; SLA alerts + email ladder; hash-chained audit with Verify.

## Email status
`.env.example` and `.env` use `bhooshakti.alearts@gmail.com` as sender and test inbox, as briefed. On 27 Oct the
real send **failed** at Gmail login. The Gmail app password in `.env` was issued for the BHOOSHAKTI sender
used in earlier projects, which is spelled differently ("alerts", not "alearts"). Either put that exact address in
`SMTP_USER`, `SMTP_FROM` and `TEST_ALERT_EMAIL`, or create an app password for `bhooshakti.alearts@gmail.com`.
Then run `make test-email`. In-app messages work regardless.

## Deploy (not done yet: needs your go-ahead)
Render: `render.yaml` (API + free Postgres; set `BREVO_API_KEY`, `SMTP_FROM`, `TEST_ALERT_EMAIL`, `PUBLIC_WEB_URL`,
`CORS_ORIGINS`, because Render's free tier blocks SMTP). Vercel: deploy `frontend/`; `vercel.json` proxies `/api` to
`https://samanvay-api.onrender.com`. Then `make test-email API=https://samanvay-api.onrender.com` and open the site once
before judging (free servers sleep).

## Limitations / next steps
1. Fix the email sender (above), then deploy.  2. Test the matcher on real, labelled AICTE files and retune.
3. CSV import of each unit's register.  4. Working-day SLA calendar.  5. Native Hindi review; Hindi reasons.
6. SMS via a DLT-registered gateway.  7. Access code on public status check (case numbers are guessable).
Docs: COMPETITOR_RESEARCH, FEATURE_GAP_ANALYSIS, INNOVATION_STRATEGY, DECISIONS, MATCHING_METHOD, MATCHING_EVAL,
TEST_RESULTS, DEMO_SCRIPT, JUDGE_QA, INNOVATION_SCORECARD, SLIDE_FACTS (all in docs/).
