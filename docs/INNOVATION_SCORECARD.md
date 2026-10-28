# Innovation scorecard (what was built, how it is proven)

| # | Feature | Status | Proof in the demo | Measured / tested |
|---|---|---|---|---|
| U1 | Overlap explainer (side by side, 3-part score, reasons + missing evidence) | Built | Narmada, Kaveri | Pair precision 0.99 / recall 0.98 (synthetic); `test_narmada_overlap_banner_and_reasons` |
| U2 | Institution 360 one-sentence summary, ageing heat strip, decisions, conflicts | Built | Narmada page | `test_institution_360_sentence` |
| U3 | Who is acting now (unit · officer · days) | Built | Every list | e2e demo path |
| U4 | Conflict guard (server-side, reason, notifies other unit) | Built | Show-cause on Narmada | `test_conflict_guard_warns_then_records_acknowledgement` |
| U5 | SLA chips + ageing strip | Built | Lists, Institution 360 | `test_sla_maths` |
| U6 | Demo clock + digest emails + ladder | Built | Admin +30 | `test_demo_clock_sends_digests_and_escalates` (≤20 emails) |
| U7 | What to do now, Hindi, A+, mobile | Built (Hindi labelled "under review") | Header switch | component tests |
| U8 | Public status check, masked | Built | /check/… | `test_public_check_is_masked_and_minimal` |
| U9 | Honest labels (Rule-based matching, Synthetic data ribbon, What is real page) | Built | Every page | `test_score_is_labelled_rule_based` |
| + | Name-learning aliases (confirmed spellings match exactly next time) | Built | Kaveri confirm | `test_create_typed_name_gets_suggestion_then_confirm_learns_alias` |
| + | Suggested next step with evidence; follow-rate recorded | Built | Case page | stored as `followed` on each action |
| + | Thresholds chosen by measurement, ablations published | Built | MATCHING_EVAL.md | `make evaluate` |
| – | SMS | Not built ("SMS planned", interface only) | Admin page | — |
| – | ML/embeddings | Deliberately not built | — | Rules already 0.99/0.98 on synthetic set |
