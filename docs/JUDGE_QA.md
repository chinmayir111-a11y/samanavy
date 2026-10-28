# Likely judge questions

| Question | Honest answer |
|---|---|
| How do you detect overlap when descriptions differ? | AICTE ID or fuzzy name match, plus category and TF-IDF text similarity and the date gap, scored 0-100 with reasons. People confirm. |
| Is it AI? | No. Rule-based matching and text similarity. An ML model could plug in later if labelled AICTE data shows it helps; on our set, rules already reach 0.99/0.98. |
| How accurate is it? | On our synthetic labelled set: names precision 1.00 / recall 0.96; pairs 0.99 / 0.98. We wrote that set, so real accuracy is unknown until tested on real files. |
| What about false alarms? | Threshold 65 was chosen by measurement. Every alert shows its evidence *and* what is missing; dismissed pairs never come back. |
| Does it stop an officer from acting? | No. It warns, asks for a reason, logs it and tells the other unit. Humans decide. |
| Real AICTE data? Integration? | No, synthetic. Integration points: REST API (`/docs`) and CSV/PDF exports; a CSV import would map onto the same case model. |
| What if a unit is late? | SLA alerts at 75/90/100%, then an escalation ladder by email (Unit Head, Coordinator, Management), all logged. |
| Can records be altered silently? | Audit entries are hash-chained and the DB refuses UPDATE/DELETE. Verify turns red at a changed entry (we demo it). |
| Is the public page a privacy risk? | It shows masked name, status, last update only. No complainant, remarks or officer names; confidential cases are hidden; rate-limited. |
| Do emails really go out? | Yes when SMTP/Brevo is configured; every attempt is in the Email log with delivered/failed, one retry and Admin resend. SMS is not built ("SMS planned"). |
| Easy for a small cell? | One "What to do now" box, suggested next step, Hindi, larger text, mobile layout. |
| How is this different from other SIH26264 teams? | Several public repos already have fuzzy matching and audit logs. Ours adds a server-side conflict guard with a recorded reason, "who is acting now / days held", a tiered SLA ladder and thresholds chosen from measured results. |
