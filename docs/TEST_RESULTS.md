# Test results (run 28 Oct 2026, macOS, Postgres 18, Python 3.12, real Chrome)

Every line below was run on this date; nothing is claimed that was not run.

| Suite | Command | Result |
|---|---|---|
| Backend (pytest) | `make test-backend` | **78 passed** |
| · sign-up | validation (name, email, password, user type, mobile), duplicate email (409), unverified sign-in refused, wrong code, verify signs in, resend wait 60 s and 5/hour, lockout message, demo login only with DEMO_MODE | in the 78 |
| · location | PIN wins over city text, misspellings (Puen, Jabalpr), old names (Poona, Bombay, Bangalore, Madras, Calcutta, Gurgaon), ambiguous Aurangabad returns choices, unknown city → manual, Admin region change takes effect, bad region refused | in the 78 |
| · institutions | existing AICTE ID → pending + Admin approves; picked college → attached; not listed → new unverified record with location; state/city drill-down | in the 78 |
| · complaints | category/description/date validation, system picks unit (Approval → AB), overlap detection runs, file type/size/content checks, QR SVG, tracking hides remarks/officer/overlap words, public check masked, own complaints only, college role blocked from officer routes | in the 78 |
| · earlier suites | matcher, workflow, conflict guard, roles, SLA, audit chain | in the 78 |
| Frontend (vitest) | `make test-web` | **12 passed**: login card order + demo dropdown + "You will see", show/hide password, sign-up steps and plain errors, location confirm/change and ambiguous choices, wizard validation, no SIH logo/badge/name in src, public, index.html or the built `dist/` (checked to fail on a planted badge) |
| End to end (Playwright) | `make e2e` | **2 passed**: (1) Create an account → college not listed → "Poona" resolves to "Pune, Pune district, Maharashtra, Western region" → code from the dev API log → verify → file → reference + QR → track → demo Desk Officer PGRC sees it in Today's register; (2) judge demo path |
| Layout | `make fit` | **23 pages fit at 320, 360, 390, 768, 1024, 1280, 1440 px**: no sideways scroll, nothing past the screen edge or cut off inside a card |
| Screenshots | `make shots` | 42 files in `screenshots/` (1440 and 390): login, create account steps, location confirm and choices, welcome, complaint steps, result, tracking, officer screens |
| **Real email** | `make test-email` | **FAILED**: Gmail closes the connection at login for `bhooshakti.alearts@gmail.com` (`SMTPServerDisconnected`). The app password on file belongs to a differently spelled sender. No verification or receipt email has been delivered; in-app messages and the dev log work. |

Not tested: screen readers, Safari/Firefox, real SMS (not built), deployed backend (not deployed).
