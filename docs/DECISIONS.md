# Decisions (made without asking, per the brief)

| # | Decision | Why |
|---|---|---|
| 1 | Built in `~/samanvay`, reusing JAMANAT's audit chain, mail (SMTP + Brevo), SMS stub, demo clock, cookie session + CSRF header, and CSS structure (restyled 27 Oct to Deep Forest with Clay Red: forest for structure and actions, clay #B5472F only for needs-action stamps, overdue counts, overlap alerts and one chart bar; the old JAMANAT vermilion look is not used). | The spec says reuse; these parts were already tested. |
| 2 | API on port **8010** (not 8000) locally. | JAMANAT's API was already running on 8000. |
| 3 | Overlap score = institution (0-40) + issue (0-40) + time (0-20); alert at **65**; pairs outside the 180-day window are capped at 50. | Chosen from `make evaluate`: 65 gives precision 0.99 / recall 0.98 on the synthetic set; 60 adds false alerts, 70 loses recall. |
| 4 | Name-match threshold **80** (spec suggested Admin-editable; we started at 88). | Measured: 80 keeps precision 1.00 and lifts recall from 0.87 to 0.96. |
| 5 | Topic-word points are switched off (the code stays, `use_topics=True` to compare). | Measured: they double-count with the category and cut precision from 0.99 to 0.94. |
| 6 | No embeddings, no ML, no LLM. | TF-IDF text similarity already lifts pair recall from 0.81 to 0.98; nothing left to justify a model. No complaint text leaves the server. |
| 7 | One overlap alert per institution (all cross-unit pairs inside it); resolved or dismissed pairs are never raised again. | Coordinators decide per institution; avoids repeat alerts. |
| 8 | Officers can *read* every case (needed to see the other unit's work) but change only their own unit's. | The problem is invisibility across units. |
| 9 | Case numbers keep their original unit prefix after a transfer (`RB-2026-0019` now held by PGRC). | A number never changes; the holder is shown separately. |
| 10 | Transfer = request (status Transferred) → receiving Unit Head accepts or returns with a reason. | Matches "Unit Head of receiving unit accepts". |
| 11 | SLA and escalation emails are **one digest per person per run**; in-app messages stay one per case. | +30 days on the demo clock would otherwise send ~100 emails to one inbox. |
| 12 | Escalation ladder: 3 / 10 / 25 days overdue → Unit Head / Coordinator / Management. | So the seeded Sahyadri case (20 days overdue) sits at Coordinator and +7 days moves it to Management. |
| 13 | Alert rules live in the Admin-editable settings (thresholds, SLA points, ladder), not a separate `alert_rule` table. | Same behaviour, less code; every change is audited. |
| 14 | Suggested next step ("evidence-based recommendation") = 9 ordered rules (R1-R9) with evidence; whether the officer followed it is stored on the action. | Explainable; officers can always choose differently. |
| 15 | Public status check shows masked name, status and last-updated date only; confidential cases return "no public record"; 30 checks per 5 min per IP. | Privacy. Case numbers are guessable, so the response carries nothing personal. |
| 16 | Email sender and test inbox: exactly the address in the brief, `bhooshakti.alearts@gmail.com`, in `.env.example` and `.env`. | Brief says no other address. See README "Email status". |
| 17 | Hindi: every UI string has a Hindi entry; server-written sentences (reasons, summaries) stay English. Labelled "Hindi translation under review". | Time; reasons are generated text. |
| 18 | The project name clashes with public repo chandan-bk/aicte-oneview ("AICTE Samanvay"). Kept the name as briefed. | Flagged for the team to decide. |
