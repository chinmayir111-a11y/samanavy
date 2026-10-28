# Feature Gap Analysis: SAMANVAY (27 Oct 2026)

**Key point:** explainable overlap, fuzzy matching, human confirm/dismiss, hash-chained audit, Hindi and public tracking each already exist in at least one public SIH26264 repo [verified]. SAMANVAY should not claim any of them as novel on its own.

The real gaps are listed below. They are based on 5 repos checked; "not seen" means not found by code reading or keyword grep.

1. Nobody gates the action itself:
   - chandan-bk warns, but only in the browser, and records no acknowledgement [verified].
   - Altamash346 detects conflicts after the fact [verified].
2. "Who is acting now and for how many days" is not seen as a first-class field [inferred].
3. Tiered SLA (75/90/100%) feeding a named escalation ladder is not seen [inferred].
4. Accuracy claims are either missing or measured only on each team's own seed data; one repo overstates its "AI" [verified].
5. CPGRAMS and e-Samadhan show no public cross-unit, entity-level overlap view [inferred from absence].

## Differentiation Matrix

| Capability | Existing solution or baseline | Verified gap | SAMANVAY's proposed improvement | Implementation status | How to demonstrate | Measurable success criterion |
|---|---|---|---|---|---|---|
| Overlap detection | Adit-K06 and narendra: TF-IDF plus fuzzy matching with reasons [verified] | Score is not broken down additively; thresholds are opaque [inferred] | Score 0-100 as a sum of named signals (ID, name, text, date window, different unit), shown as a waterfall like Fellegi-Sunter/Splink [proposed] | **built**: 3-part score (institution 40, issue 40, time 20) with reasons and missing evidence; topic-word points dropped after measurement | Overlap explainer page | On labelled synthetic pairs: precision ≥ 0.8 and recall ≥ 0.9, with 0 auto-merges. **Measured: 0.99 / 0.98 at 65; nothing merges without the Coordinator** |
| Institution matching | Abbreviations, Jaro-Winkler and city checks in narendra and Altamash [verified] | None major; this is table stakes [verified] | RapidFuzz plus abbreviation normalisation plus a review band [proposed] | **built**: hybrid whole-name/distinctive-word score, city check, ambiguity → human; confirmed names saved as aliases | Kaveri typed name → Confirm match | 0 wrong auto-links on the test set; ambiguous names go to review. **Measured: precision 1.00, recall 0.96 at 80; nothing links without a click** |
| Conflict guard | chandan-bk pre-action advisory (front end only); Altamash post-hoc rules [verified] | No server-side check at action time and no reason recorded [verified] | Before a regulatory action: warn, require an acknowledgement reason, never block, notify the other unit [proposed] | **built** (server-side, 409 until acknowledged; other unit notified) | Show-cause on Narmada RB case | 100% of guarded actions on overlapped institutions show a warning; every override has a stored reason |
| Who is acting now | Case lists with officer and status [verified] | No days-held view per unit [inferred] | Unit + officer + days held on the Institution 360 view [proposed] | **built** on every case row, case page and Institution 360 | Any list | Every open case has holder and days-held figures that match the audit log |
| SLA and escalation | SLA flags and escalation exist (Adit, ritheya) [verified] | 75/90/100% tiers with a ladder not seen [inferred] | Alerts at 75/90/100% and an email escalation ladder; demo clock [proposed] | **built**: digest emails, in-app inbox, ladder 3/10/25 days overdue | Admin +30 days → Email log | Alerts fire at the correct tier for every seeded case |
| Audit integrity | Hash chains in Altamash and chandan [verified] | Not a gap, only parity [verified] | Hash chain plus a Verify button that points to the tampered row [proposed] | **built** (+ DB trigger refuses UPDATE/DELETE) | `make tamper` → Verify → `make untamper` | Detects 100% of single-row edits |
| Public status check | CPGRAMS tracking by registration ID; Altamash `#/track` [verified] | Parity [verified] | Masked names and officer details; status only [proposed] | **built**: masked name, status, last-updated only; confidential cases hidden; rate-limited. No check field yet | /check/RB-2026-0001 | No personal data in the response (field audit) |
| Honest evaluation | Adit and Altamash give metrics; dhanya overstates its AI [verified] | Metrics are not shown next to their limits [inferred] | Evaluation page with the data label "synthetic", confusion counts and known failure cases [proposed] | **built** as docs/MATCHING_EVAL.md (`make evaluate`) + "What is real" page | `make evaluate` | Numbers reproduce from one command |

_Status column updated 27 Oct 2026 after the build. Measurements are on our own synthetic set (docs/MATCHING_EVAL.md)._
