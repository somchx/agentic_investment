# A3 v2: current development set and expansion plan

- **Status:** recommendation, not yet carried out.
- **Constraint:** no claim is added and no label is created until the researcher approves.
- **Status of the current set:** `datasets/development_cases.jsonl`, 24 claims, unlabelled, `relevant_filings` empty.

## 1. The current 24 claims

| | Numerical | Interpretive | Ambiguous | Total |
|---|---|---|---|---|
| AAPL | 4 | 3 | 1 | 8 |
| MSFT | 4 | 2 | 2 | 8 |
| AMZN | 4 | 2 | 2 | 8 |
| **Total** | **12** | **7** | **5** | **24** |

| | Count |
|---|---|
| Difficulty: easy / medium / hard | 11 / 8 / 5 |
| Cutoffs | 2026-05-15 (3 claims), 2026-08-15 (21 claims) |

**Coverage against the v1 error patterns** (counts are by claim text, before labelling):

| v1 pattern | Claims in the current dev set | Coverage |
|---|---|---|
| Evaluative predicate without a criterion | AAPL-07, MSFT-06, MSFT-07, AMZN-06 (4) | thin |
| Absence claim ("not affected by…") | AAPL-07 (1) | thin |
| Cause / driver ("primarily driven by", "because of") | AAPL-04, AAPL-05, MSFT-04, MSFT-05, AMZN-04, AMZN-05 (6) | fair |
| Computation needed (FCF, cash vs net income) | AAPL-06, AMZN-07 (2) | thin |
| Period traps (partial period, H1, comparison) | AMZN-07 (H1) (1) | thin |
| Definition / segment change | none | none |
| Pure numeric checks (protecting A2's numeric conclusions) | 12 | sufficient |
| Cases where A2 would likely answer INSUFF but the evidence exists, testing A3's ability to fix A2 | not known until labelled | — |

**Implications.**
- Ambiguous and interpretive claims make up 12/24. In v1, A3 caused harm only in these two categories, and
  15/15 of its harmful changes fell there.
- There are only 3 companies, all of which are also among the gold companies, with overlapping periods.
- The current set is too small and too narrow to choose an architecture.

## 2. Recommended additions

**Target: about 60–80 development claims.**

| Type | Target (approx.) | Reason (v1 evidence) | Example form (written fresh; not a paraphrase of a gold claim) |
|---|---|---|---|
| Ambiguous with an evaluative predicate | +15 | 10/15 harmful changes moved from INSUFF to a decisive label on claims like these | "X's results show disciplined cost management" |
| Absence / materiality claims | +5 | TSLA-13-type argument from silence | "X's margins were not affected by currency movements" |
| Cause or driver stated by the filing (SUPPORTED / CONTRADICTED) | +10 | The guard must not block correct answers (KO-09-type) | "X's growth was primarily driven by segment Y" |
| Computation required (FCF, share of change, level vs change) | +8 | MSFT-12, NVDA-07, NFLX-09 | "X's free cash flow rose despite higher capex" |
| Period traps (another period's disclosure sounds like the answer) | +6 | NFLX-11, AMZN-11, MSFT-11 | Quarterly claims where the 10-K states something similar for the prior year |
| Definition / segment changes | +4 | MSFT-08 (a fix A3 made), WMT-08 | Claims that use a segment's old name |
| A2 likely INSUFF but a same-period filing decides it | +6 | KO-12, NVDA-11, GOOGL-04 (fixes A3 made) | A claim that needs the MD&A or a note rather than the headline numbers |
| Numeric checks | keep 12, add a few with an edge threshold | Protects A2's NUMERIC_FALSE / ALL_TRUE conclusions | — |

**Composition.**
- **Reference labels:** aim for about one third INSUFFICIENT_EVIDENCE, so that abstention calibration can be
  measured.
- **Companies:** add companies beyond AAPL, MSFT and AMZN (5–6 companies).
  - Their filings must be downloaded from SEC (free; `scripts/build_corpus.py --download`).
  - Keep the companies and periods of the dev set separate from the planned holdout. Otherwise dev and holdout
    would share disclosures.

## 2b. Concrete expansion target (update after the first labelling round)

**Starting point: the first labels (`rev_som`, provisional, before second review and adjudication).**
- SUPPORTED 14, CONTRADICTED 8, INSUFFICIENT_EVIDENCE **2** (8%).
- The set measures A3 v1's main failure poorly: decisive answers on claims whose reference label is INSUFFICIENT.

**Target: 72 claims (24 current + 48 new).**

| Category | Now | Add | Target |
|---|---|---|---|
| Ambiguous | 5 | +25 | 30 |
| Interpretive | 7 | +15 | 22 |
| Numerical | 12 | +8 | 20 |
| **Total** | 24 | +48 | **72** |

**INSUFFICIENT_EVIDENCE.**
- Target: at least 24 of 72 (one third). About 22 of the 48 new claims therefore need to *turn out* INSUFFICIENT.
- Labels are known only after annotation. Authors should record a non-binding `design_intent` per claim (the
  outcome the author expects) and keep it out of the annotators' workbook.
- After labelling, compare the realised mix with the target and top up if needed.

**Avoid a shortcut.** Each "likely INSUFFICIENT" type needs decisive counterparts. Otherwise "evaluative wording →
INSUFFICIENT" would become a rule the system could learn from the wording alone.

| Pair | Likely INSUFFICIENT | Decisive counterpart |
|---|---|---|
| Evaluative predicate | No criterion in the claim or the filing (+12) | A factual part is false → CONTRADICTED (+6) |
| Cause / driver | Filing reports the change, not the cause (+6) | Filing states the cause (+5 SUPPORTED, +3 CONTRADICTED) |
| Absence claim | Filing states neither the absence nor that the effect is immaterial (+4) | Filing discloses the effect → CONTRADICTED (+2) |
| Period | Claimed period not covered or only partly covered (+2) | Another period's disclosure is a trap; the claim's own period decides (+4) |
| Computation / definition | — | FCF, share of change, level vs change, renamed segment (+4) |

**Companies.** Add 3–4 companies that are not among the 10 gold companies and not reserved for the holdout. Use a mix
of industries (for example, a consumer staples, an industrial, a software and a semiconductor company). Their filings
must be downloaded from SEC (free) before the claims are written.

**Labelling.**
- Two independent human reviewers for every new ambiguous and interpretive claim.
- One reviewer, with a second-review sample, for numerical claims.
- Report κ before adjudication.

## 3. Rules for writing new claims

1. **Do not use gold claims.** Do not copy or paraphrase the 150 gold claims, and do not write a claim by looking
   at v1 / v2 output. The patterns above come from the error analysis, so use them only to choose claim *types*.
2. **Fix the metadata first.** Set `claim_category`, `difficulty`, `reporting_period` and `as_of_date` from the claim
   text before anyone labels it.
3. **Author vs annotator.** The person who writes a claim should not be its only annotator.
4. **Bump the dataset version** (for example `dev-v0.2`) and record the sha256 before labelling.
5. **Plan the holdout separately:**
   - claims and labels are fixed before A3 v2 is frozen;
   - about 200 claims (an estimate, to be recomputed from the dev results);
   - companies or periods that do not overlap with the dev set.
