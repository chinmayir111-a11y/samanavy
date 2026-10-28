# Innovation Strategy: SAMANVAY (27 Oct 2026)

**Scoring:** each criterion is 1-5, where higher is better. For **Effort**, 5 means the least effort. **Novelty** is judged against the 5 verified SIH26264 repos and CPGRAMS; it is not an absolute measure. Only public repos were seen.

| Rank | Idea | Novelty | Relevance | Feasibility | Impact | Demo | Explainability | Effort (5 = low) | Total | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | D Conflict prevention: server-side guard plus acknowledgement reason plus notify the other unit | 4 | 5 | 4 | 5 | 5 | 5 | 4 | 32 | Build. Our clearest differentiator. |
| 2 | A Cross-unit "who is acting now / days held" | 3 | 5 | 5 | 4 | 5 | 5 | 5 | 32 | Build. Cheap and directly answers the problem statement. |
| 3 | C Institution 360 one-sentence summary (template-generated, not an LLM) | 3 | 5 | 5 | 3 | 5 | 5 | 5 | 31 | Build. Template text only. |
| 4 | B Explainable overlap with additive score breakdown (waterfall) | 2 | 5 | 5 | 4 | 5 | 5 | 4 | 30 | Build. Table stakes; the waterfall view is the difference. |
| 5 | E SLA 75/90/100% plus escalation ladder plus demo clock | 3 | 4 | 5 | 4 | 5 | 5 | 4 | 30 | Build. Use a mock email outbox and do not wire real SMTP. |
| 6 | H1 Honest evaluation page (synthetic labelled pairs, confusion counts, failure cases) | 3 | 4 | 5 | 3 | 4 | 5 | 4 | 28 | Build. Guards against the overclaiming judges punish. |
| 7 | H2 Shared "documents already requested" registry (ask the college once) | 3 | 4 | 4 | 4 | 4 | 5 | 3 | 27 | Optional. chandan-bk already has a front-end version. |
| 8 | H3 Overlap reopens automatically when a new case joins a dismissed group | 2 | 4 | 4 | 3 | 3 | 5 | 4 | 25 | Cheap add-on if time allows. |
| 9 | Hash-chained audit with Verify | 1 | 3 | 5 | 2 | 4 | 5 | 4 | 24 | Build, but small. It is parity, so do not pitch it as innovation. |
| 10 | F Next-action recommendation with override (rules) | 2 | 4 | 3 | 3 | 3 | 4 | 3 | 22 | Skip, or offer one rule ("lead unit suggestion"). Risk of looking like fake AI. |
| 11 | H5 Hindi/English UI | 1 | 3 | 4 | 2 | 4 | 4 | 3 | 21 | Labels only, for the key screens. |
| 12 | G Masked public status check | 1 | 2 | 4 | 2 | 3 | 4 | 4 | 20 | Minimal version only. Peripheral to SIH26264 (an internal tool). |
| 13 | H6 Fellegi-Sunter weights learned with Splink | 3 | 3 | 2 | 3 | 2 | 4 | 1 | 18 | Skip for the build; mention as roadmap. |
| 14 | H4 Optional embedding similarity as an extra signal | 2 | 3 | 3 | 2 | 2 | 2 | 2 | 16 | Skip. Research shows simple methods are competitive (arXiv 2212.00548); it costs explainability. |

**Recommended 1-2 day combination:** D + A + B + E + C + H1, with a small hash-chain audit.
- **Pitch:** "We do not just detect overlap. We stop the second unit from acting blind, and we show exactly why, with honest numbers."

**What to skip and why:**
- **F:** rules dressed up as recommendations invite scrutiny.
- **H4 and H6:** time cost and less explainability.
- **Full G and full Hindi:** low relevance to an internal coordination tool.

**Risks:**
1. The crowded field means judges may have seen B, C, the audit and G several times. Lead with D and A.
2. Our name clashes with chandan-bk's "AICTE Samanvay".
