# 3-minute judge demo

Before: `make seed`, `make demo-check` (all green), open the hosted link once (free servers sleep). Demo password: `samanvay-demo-2026`.

| Time | Do | Say |
|---|---|---|
| 0:00 | Login → **Desk Officer · RB** | "Complaints about one college reach RB, PGRC and others separately. SAMANVAY puts them in one place." |
| 0:15 | Today's register: *What to do now* box, overdue chips, "Who is acting now" column | "Every case shows which unit and officer hold it and for how many days." |
| 0:30 | Institutions → **Narmada** | "One sentence answers what AICTE is doing about this college." Point at the banner **Potential Overlapping Cases - Coordination Required**. |
| 0:45 | Explain and decide → side-by-side | "Same AICTE ID, related categories (faculty complaint vs inspection), 8 days apart. Score 69 out of 100 from rules. We call it rule-based, not AI." |
| 1:00 | Sign out → **Coordinator** → Assign RB as lead unit, reason | "A person decides. Both units are told; it's in the audit log." |
| 1:20 | **Desk Officer · PGRC** → Cases, search "Kaveri Inst." → Confirm match | "Typed as 'Kaveri Inst. of Engg & Tech', no ID. The matcher found the right college, not the Kaveri pharmacy college. Confirming saves the spelling." |
| 1:40 | **Desk Officer · RB** → Narmada RB case → Record action → *Show-cause notice issued* | Warning lists PGRC's open case. "It never blocks. It asks why, records it, and tells PGRC." |
| 2:05 | **Admin** → +30 days | "Time jumps a month: SLA alerts at 75/90/100%, then the ladder Unit Head → Coordinator → Management." Open Email log; show the real inbox. |
| 2:25 | **Management** → Dashboard | Overdue, ageing buckets, unit workload, disposal rate; refreshes every 30 s. |
| 2:40 | Audit log → Verify (green). Optional: `make tamper`, Verify (red at the row), `make untamper` | "Nobody can quietly change a decision." |
| 2:50 | `/check/RB-2026-0001` | "The public sees status only, institution masked." |
| 2:55 | Close | "One institution. One view. No duplicate action. Synthetic data, measured matcher: 0.99 precision on our test set." |

After: Admin → Back to today, then `make seed`.
