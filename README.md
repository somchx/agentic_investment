# Phase 1 Thin Vertical Slice

Proof-of-concept for the numeric-only Phase 1 scope described in
[PROPOSAL.md](PROPOSAL.md) — one company, one investment reason, walked
forward quarter by quarter using only point-in-time SEC data (no lookahead).

## Run it

```
pip install -r requirements.txt
cd src
python3 main.py AAPL
```

First run fetches and caches `data/cache/CIK0000320193.json` from the SEC
XBRL company-facts API (~3.7MB, public, no API key needed — just a
descriptive User-Agent, see `SEC_USER_AGENT` env var in `src/sec_client.py`).
Subsequent runs use the cache.

## What it does

For the reason "Revenue growth must exceed 10% YoY", the script:

1. Pulls every quarterly Revenue figure Apple has ever reported to the SEC
   (`src/xbrl_extract.py`), keeping every reported version of each quarter
   (so a later restatement doesn't silently overwrite the original number).
2. Walks forward through each historical filing date as a simulated "today".
   At each step, only filings published on/before that date are visible
   (`facts_as_of`) — this is the Point-in-Time mechanism from the proposal,
   implemented as a plain filter rather than an API feature.
3. Computes YoY growth from the most-recently-filed ("authoritative")
   version of the current and prior-year quarter, flags any earlier-filed
   version that disagrees by >0.5% as conflicting evidence
   (`_pick_primary_and_conflicts` in `src/reason_engine.py`).
4. Classifies the reason's status as Supported / Weakened / Broken / Not
   enough data, with the exact evidence (value, filing form, accession
   number, filed date) attached to every verdict.

## What's proven

- SEC XBRL is a usable structured data source for Phase 1 — no PDF parsing
  needed for revenue.
- Point-in-time retrieval works as a simple filed-date filter over a locally
  cached fact table.
- The reason-evaluation domain logic (Contribution 1) runs end-to-end and
  produces a status timeline that matches Apple's known revenue history
  (COVID surge in 2020-2021, the 2022-2023 slowdown, recovery in 2025-2026).

## Status: validated on 3 companies x 2 reasons

`main.py` now runs both reasons ("Revenue growth > 10% YoY" and "Operating
margin >= 20%") and has been checked against AAPL, MSFT, and NVDA:

- AAPL: growth/margin timeline matches known history (COVID surge,
  2022-2023 slowdown, 2025-2026 recovery).
- MSFT: margins consistently 45-49%, growth mostly Supported — matches
  reality.
- NVDA: growth/margin correctly reflect the 2023-2026 AI-driven boom
  (e.g. +262% YoY revenue growth, ~50-65% operating margin).

**Bug found and fixed during multi-company testing:** the original tag
picker took the first candidate XBRL tag that had *any* data, which broke
on NVDA — `RevenueFromContractWithCustomerExcludingAssessedTax` was only
used for a one-off ASC 606 transition footnote (28 raw points, mostly not
single-quarter), while the real quarterly series lived under `Revenues`
(276 points). Fixed in `extract_quarterly_facts` (`xbrl_extract.py`) to pick
whichever candidate tag yields the most single-quarter facts, not just the
first one with any data. This is exactly the kind of silent-failure risk
Contribution 1's pipeline needs to be robust against before scaling to more
companies.

## Contribution 2 evidence source: Earnings Release vs 10-Q (`earnings_release.py`)

Built and tested end to end: `python3 earnings_release_check.py [TICKER]`.

1. `list_earnings_release_filings` finds every 8-K tagged Item 2.02
   ("Results of Operations") via the SEC submissions API — these are the
   preliminary press releases, filed days to weeks before the 10-Q.
2. `_find_ex99_filename` locates the EX-99.1 press-release exhibit inside
   each filing (the SEC-assigned document type in the filing index, not a
   filename guess — exhibit naming conventions vary too much between
   companies to regex the filename itself).
3. The exhibit's income-statement table is text-parsed for the headline
   Revenue figure and the quarter-end date it belongs to, then compared
   against the authoritative 10-Q/10-K Fact for the same period.

**Real, non-trivial parsing problems found and fixed along the way** (both
are exactly the kind of silent-failure risk this project is meant to guard
against, so they're recorded here rather than smoothed over):
- The first value-extraction regex captured footnote markers like the "(1)"
  in "Total net sales (1)" as if it were the dollar figure — fixed by
  requiring a comma-grouped number (`\d{1,3}(?:,\d{3})+`), which a footnote
  digit never has.
- The first period-date extraction anchored on the *first* "Three Months
  Ended" heading in the document. For Apple that's the real income
  statement; for Microsoft it's an unrelated "Constant Currency
  Reconciliation" table earlier in the release, giving the wrong or
  unparseable date. Fixed by anchoring the date search on the heading
  nearest *before the specific value match* rather than the first one in
  the whole document — ties the date to the same table the number came
  from.

**Results (`python3 earnings_release_check.py AAPL` / `MSFT`):**
- AAPL: 40 match, 0 conflict, 1 unparsed, 5 quarters with no standalone
  10-Q fact to compare against (fiscal Q4 is derived as FY minus Q1-Q3, not
  separately filed).
- MSFT: 19 match, 0 conflict, 0 unparsed, 6 quarters with the same Q4 gap
  (MSFT's fiscal year also ends in Q4, June 30).
- **Zero conflicts found for either company's headline revenue** — expected
  for large, well-audited filers; the preliminary press-release number and
  the final 10-Q number are the same number filed twice. This is itself a
  meaningful (if unglamorous) result: the mechanism works and correctly
  reports "no discrepancy" rather than manufacturing one.

**A real conflict *was* found via the other path** (`_pick_primary_and_conflicts`
in `reason_engine.py`, comparing a quarter's value as first filed vs. as
referenced in later filings): Microsoft's revenue for the quarter ending
2016-09-30 was originally reported as **$20,453M**, then restated to
**$21,928M** (+7.2%) in filings from mid-2017 onward — Microsoft's early
adoption of the ASC 606 revenue recognition standard. `main.py MSFT` surfaces
this as conflicting evidence automatically. Concretely: computing that
quarter's YoY comparison with the original figure instead of the restated
one changes the growth rate by about 8 percentage points — a materially
different answer depending on which version of the number the Agent trusts.
This is real evidence that Contribution 2 (knowing *which* source to trust,
not just averaging them) matters.

## Scaled up: 5 companies x 3 reasons (`portfolio_report.py`)

```
python3 portfolio_report.py                      # AAPL, MSFT, NVDA, GOOGL, AMZN
python3 portfolio_report.py AAPL MSFT ...         # any ticker set
```

Third reason added: "Long-term debt must not grow more than 15% YoY"
(`LongTermDebt`, comparison `<`). Debt is a balance-sheet *instant* fact
(only an `end` date, no duration), unlike Revenue/OperatingIncome, so it
needed its own extraction path — `extract_instant_facts` in
`xbrl_extract.py` — rather than reusing `extract_quarterly_facts`, which
filters for single-quarter *durations* and would silently drop every
balance-sheet number.

The dashboard prints each company's latest snapshot (as of its most recent
filing) in the "My reasons for investing" format from the proposal's
illustrative UI, plus a diff against the previous quarter's snapshot.

**Real finding, not a bug:** both GOOGL and AMZN currently show the debt
reason as 🔴 Broken — Alphabet's long-term debt went from ~$10.9B (Q1 2025)
to ~$98B (Q2 2026); Amazon's from ~$58.8B to ~$133.0B over the same window.
Verified these aren't an extraction artifact by reading the raw `by_quarter`
values directly. This lines up with the real large-scale AI-datacenter bond
issuances both companies did in 2025-2026 — exactly the kind of signal this
reason is supposed to catch. AMZN's operating margin reason also correctly
shows 🟡 Weakened (~13.7%, below the 20% threshold but still positive).

## Scaled up further: 10-15 companies (`portfolio_report.py`)

```
python3 portfolio_report.py                                          # AAPL MSFT NVDA GOOGL AMZN
python3 portfolio_report.py AAPL MSFT NVDA GOOGL AMZN META TSLA PEP JNJ PG KO WMT NFLX ORCL COST
```

Expanded `KNOWN_CIKS` to 15 companies across a mix of sectors (mega-cap
tech, consumer staples, retail, streaming, enterprise software), pulled
from SEC's own `company_tickers.json` ticker->CIK mapping rather than
hand-typed, so no risk of pointing at a stale or wrong entity. All 15 run
cleanly end to end.

**Original pilot list included JPM (JPMorgan); dropped it and swapped in
PEP.** A bank's income statement doesn't have a conventional "Operating
Income" line or "Revenue" in the same XBRL sense as a product/services
company (interest income, net interest margin, etc. instead) — JPM came
back with Revenue and Debt facts that stopped in 2014 (the tags this project
uses were only ever incidentally populated for JPM around then) and zero
Operating Income facts at all. This is a real scope boundary, not a bug:
Phase 1's numeric reasons assume a standard non-financial income statement,
so financial-sector companies are out of scope for now rather than
special-cased.

**Fixed a related bug this surfaced:** the "what's changed since last
review" comparison originally picked one global "previous filing date"
shared across all three reasons for a company. If one reason's data source
has a coverage gap (stale or missing recent tagging), that would silently
drag every *other* reason's comparison back to whatever old date that one
source last has — exactly what happened with JPM (the diff line showed
"2014-08-04 -> 2014-11-03" while other reasons were current in 2026). Fixed
in `portfolio_report.py` to compute each reason's own previous-vs-latest
comparison from its own facts' filed dates, independent of the other
reasons for that company.

**Two more genuine "Not enough data" cases surfaced honestly, not
papered over** — this is the Insufficient Evidence / Abstention mechanism
from the proposal working as intended:
- JNJ's Operating Margin reason flips from Supported to Not enough data
  after 2015-05-01 — J&J stopped reporting a standalone `OperatingIncomeLoss`
  figure under this tag around then.
- ORCL's Debt reason shows Not enough data — neither
  `LongTermDebtNoncurrent` nor `LongTermDebt` is populated for Oracle in a
  way this pipeline currently picks up (likely a different debt tag/line
  item). Not investigated further yet; noted as a real per-company tag-
  coverage gap rather than assumed to be universal.

## Fixed: a spurious "conflict" from merging two different accounting concepts

Building the agent's tool layer (below) surfaced a real correctness bug in
the tag-merging logic added earlier: MSFT's debt reason reported a
"conflicting evidence" note that turned out to be fake. Both
`LongTermDebtNoncurrent` ($31.1B) and `LongTermDebt` ($40.3B) are reported
in *the same 10-K filing* for the same quarter-end — but they're not two
versions of the same number, they're two different concepts (the second
includes the portion of debt due within a year, the first excludes it).
Merging them as if one restated the other produced a bogus ~30%
discrepancy that would have been reported to an Agent as evidence of data
untrustworthiness when nothing was actually wrong.

Fixed in `xbrl_extract.py` (`extract_quarterly_facts` and
`extract_instant_facts`): a lower-priority tag's entry for a period is now
only dropped when a higher-priority tag reported that *same period within
the same filing* (same accession number) — that's the "two concepts, one
filing" collision. A tag reporting the same period from a *different*
filing is kept, because that's what a genuine restatement across a tag
migration looks like. Verified this distinction against both real cases
found this session: MSFT's debt collision (same accession number for both
tags -> correctly suppressed) and MSFT's ASC 606 revenue restatement
(`SalesRevenueNet` filed 2016/2017 vs `RevenueFromContractWithCustomer...`
filed 2018, different accession numbers -> correctly kept as conflicting
evidence). Re-ran the full 15-company x 3-reason suite and both
earnings-release checks after the fix — no regressions, same match/conflict
counts as before except the one bogus MSFT debt conflict, which is now
gone.

## Agent layer (`tools.py` + `agent.py`)

```
python3 agent.py AAPL     # clean case: all Supported, no follow-up tool call
python3 agent.py GOOGL    # debt reason Broken -> pulls a second source -> Human review: RECOMMENDED
python3 agent.py AMZN     # two uncertain reasons -> both cross-checked
python3 agent.py JNJ      # Not enough data -> still triggers a follow-up check, not a silent skip
```

`tools.py` wraps the domain logic built so far as discrete, independently
callable tools with explicit name/description/input-schema, matching
PROPOSAL.md section 5's tool table:
- `check_reason_status(ticker, reason_key, as_of=None)` -- the
  Calculator/Rule-Engine step; wraps `reason_engine.evaluate_yoy_growth` /
  `evaluate_margin_level`.
- `check_earnings_release_conflict(ticker)` -- pulls a second,
  independently-sourced number for the latest quarter via
  `earnings_release.py`.

`agent.py` implements the "Reason -> pick tool -> observe -> pick next tool
-> decide if evidence is sufficient" loop from PROPOSAL.md section 4, in two
forms:

- **`run_rule_based(ticker)` -- built and verified this session.** A
  deterministic planner: check a reason's status first; if it's Weakened,
  Broken, Not-enough-data, or already carries conflicting evidence from
  `reason_engine`, call the earnings-release tool for a second source, then
  decide whether to flag the reason for human review and say why. Every
  branch has been run against live SEC data (see the transcript above --
  GOOGL and AMZN's Broken debt reasons, JNJ's Not-enough-data margin, TSLA's
  Weakened margin, all correctly triggered the follow-up tool call and a
  "Human review: RECOMMENDED" verdict with reasons attached; AAPL and MSFT's
  clean Supported-everywhere case correctly triggered *no* follow-up call).
- **`run_with_llm(ticker)` -- now built AND run for real.** Claude picks
  which tool to call via the Anthropic Messages API's tool-use feature
  (same `TOOL_SPECS`/tool functions as the rule-based path), in a loop,
  until it produces a final answer. `python3 agent.py TICKER --llm`
  (requires `ANTHROPIC_API_KEY` in a `.env` file). Per the proposal's
  explicit guidance this is a thin loop over an existing tool-use API, not
  a custom agent framework -- and it does NOT use the `anthropic` SDK: the
  SDK's bundled HTTP client hit a response-decompression bug in this
  environment (`Decompressor.decompress() got an unexpected keyword
  argument 'output_buffer_limit'`, from a mismatched httpx2/h11 install
  pulled in alongside it) that a raw `requests.post` to the same endpoint
  with the same payload didn't have. `agent.py` calls the API directly.

**Real run, AAPL** (`python3 agent.py AAPL --llm`): checked all three
reasons, then proactively also called `check_earnings_release_conflict` --
more thorough than the rule-based planner, which only pulls a second source
when a reason already looks uncertain. Concluded all three Supported, no
human review needed, with correct numbers cited from the tool results.

**Real run, GOOGL** (`python3 agent.py GOOGL --llm`): correctly flagged the
debt reason as **Broken, human review URGENT**, reasoned about plausible
causes (acquisition, refinancing, "potential data classification changes"),
noted it tried the earnings-release tool to cross-check but that tool only
verifies Revenue (not Debt) so it couldn't actually confirm the number that
way -- an accurate read of the tool's real limitation, not a hallucinated
capability. Same bottom-line verdict as the rule-based planner, with richer,
correctly-grounded reasoning about *why*.

**Real bug found and fixed while building this layer:** exercising the
tools surfaced the spurious MSFT debt "conflict" documented above -- the
kind of thing that would have been silently reported to an LLM agent as
evidence the data source disagreed with itself, when actually two different
accounting line items were being compared. Caught before it could reach the
agent layer, not after.

## Experiment: rule-based vs LLM-driven planner across all 15 companies (`compare_planners.py`)

```
python3 compare_planners.py            # all 15 tickers, both planners, per-reason comparison
```

This is the comparison PROPOSAL.md section 9 calls for: not "does the LLM
sound smart" but does its tool-selection and verdict match, differ from, or
improve on the deterministic planner's, reason by reason.

**First attempt was broken, caught before trusting the result.** The
comparison originally had the LLM write a free-text summary and used
keyword regex (`"recommended" in text`) to decide if it had flagged a
reason for human review. Spot-checking one disagreement (PG) against the
raw LLM output found a report that literally said *"Human Review Needed:
**YES**"* get scored as "no review needed" -- the regex just didn't match
that phrasing. Fixed by adding `FINALIZE_REPORT_TOOL` to `tools.py`: the
LLM must call `finalize_report` with a structured
`{reason_key, status, human_review_recommended, rationale}` per reason as
its actual final answer, instead of prose this script had to reverse-guess.

**Real result after the fix, 15 companies x 3 reasons = 45 comparisons:**
- **Status agreement: 100%** (45/45) -- both planners compute the same
  Supported/Weakened/Broken/Not-enough-data verdict every time, expected
  since both call the exact same deterministic `check_reason_status` tool.
- **Human-review-recommended agreement: 87%** (39/45).
- **All 6 disagreements follow one clean pattern:** every one is a
  `Weakened` reason (PEP, JNJ, PG, WMT's revenue-growth and/or
  operating-margin) where the rule-based planner flags it for human review
  (its rule is blunt: any non-Supported status = review) but the LLM
  judged that particular borderline case as not concerning enough to
  escalate. **Zero disagreements on Broken or Not-enough-data reasons** --
  both planners agree 100% on the cases that are actually severe (GOOGL/
  AMZN/META/TSLA's Broken debt reasons, AMZN/TSLA/COST's Weakened margins
  that *did* get flagged, JNJ/ORCL's Not-enough-data cases).
- Total cost for this 15-company run: **$0.397** (77,109 input + 11,042
  output tokens at $3/$15 per MTok) -- cheap enough to re-run freely.

**Caveat found while fixing the parsing bug, worth stating plainly:** on
one single reason (PG's Weakened revenue growth), an earlier free-text run
said review was needed, and the later structured run on the same reason
said it wasn't. That's the LLM planner giving a different judgment call on
the *same input* across two separate runs -- exactly the "reasoning
consistency" risk PROPOSAL.md's evaluation dimensions call out. The 45-case
comparison above used one run per reason, so it captures a snapshot of
agreement, not a measurement of the LLM planner's own run-to-run
consistency; that would need repeated runs per reason, not done here.

## Web frontend (`webapp.py`)

```
python3 webapp.py
# open http://127.0.0.1:5050
```

A small local Flask app for browsing the dashboard instead of reading
terminal output -- the "My reasons for investing" mockup from
PROPOSAL.md section 7, made clickable:

- Sidebar lists all 15 pilot companies. Selecting one calls
  `/api/report/<ticker>`, which reuses `portfolio_report.py`'s per-reason
  latest-vs-previous evaluation -- **free, SEC data only, no LLM call.**
- Each reason renders as a card: status badge (color-coded Supported/
  Weakened/Broken/Not-enough-data), computed value, plain-language
  explanation, a "changed since last review" note when the status flipped,
  and a collapsible evidence list (including conflicting evidence, when
  present, in red).
- An **"Ask AI Agent to review" button** is the only thing that spends API
  budget -- it calls `/api/ask-agent/<ticker>`, which runs
  `agent.run_with_llm` for real and renders its tool-call trace, per-reason
  structured verdict, and rationale. Never fires automatically, only on
  click, so browsing the dashboard itself never costs anything.

Verified end to end: fetched `/api/report/AAPL` and `/api/report/GOOGL`
over real HTTP (not just calling the Python functions directly), confirmed
all 15 tickers render in the sidebar, and ran a real `/api/ask-agent/AAPL`
request through the web layer (not just agent.py's CLI) to confirm the
whole path -- browser-facing route to live LLM call to rendered result --
actually works, not just the pieces in isolation.

**Known rough edges:** `python3 webapp.py` needed `use_reloader=False` --
this environment's installed `watchdog` package is incompatible with
Werkzeug's file-watching reloader (`ImportError: cannot import name
'EVENT_TYPE_OPENED'`); debug mode's in-browser error pages still work,
there's just no autoreload on file save. This is a plain Flask dev server
(`app.run(debug=True)`) -- fine for local/single-user use, explicitly not
meant to be exposed beyond localhost as-is.

## Generalized the secondary-evidence tool (`get_secondary_evidence`)

`check_earnings_release_conflict` only ever checked Revenue -- exactly the
gap the LLM agent flagged on its own when it couldn't cross-check GOOGL's
Broken debt reason. Renamed to `get_secondary_evidence(ticker, reason_key)`
and generalized `earnings_release.py` to parse OperatingIncome and
LongTermDebt from the press release too, not just Revenue:

- OperatingIncome reuses the existing income-statement parsing path
  unchanged (it was already in the same table as Revenue).
- LongTermDebt needed real new logic: it's a *balance-sheet* line, not an
  income-statement one, so it needs a different date anchor ("...BALANCE
  SHEETS... <date1> <date2>" instead of "Three Months Ended <date>"), and
  the line item appears twice (current portion under current liabilities,
  non-current portion under non-current liabilities) -- confirmed against
  Apple's own release that the XBRL `LongTermDebt` fact matches the
  *second* occurrence, not the first.

Tested for free (no LLM calls, just re-running the earnings-release check
against already-cached documents): **AAPL 45/46 debt-quarters matched, 0
conflicts; MSFT 25/25 matched, 0 conflicts.** Re-ran `agent.py GOOGL`
(rule-based, free) afterward and it now genuinely cross-checks the Broken
debt reason instead of silently checking Revenue instead -- confirms
$46,547M debt figure independently against the earnings release.

## Gold set: an independent check on extraction and classification accuracy

Direct response to the most important critique of this session: every
"correct" status up to this point was "this system's own SEC extraction,
run through this system's own rule" -- circular, and doesn't prove
anything. Built `build_gold_set.py` and `score_against_gold.py`, both free
(SEC data only, no LLM calls).

**Honest scope of what "gold" means here** (stated plainly, not oversold):
for each (ticker, reason_key, quarter), the XBRL 10-Q/10-K value is
cross-checked against the same company's own 8-K earnings-release
figure -- a genuinely separate filing, prepared and usually submitted
*before* the 10-Q, not a second read of the same document. This is real
independent verification, but it is not the same as a human analyst
re-deriving the number from first principles; both documents ultimately
come from the company's own books. A stronger gold set would add a small
number of hand-verified entries read directly from primary filing text.

**Two real bugs in earnings_release.py found via this cross-check, both
fixed:**
- **Unit mismatch (NFLX, TSLA):** the code assumed every press release
  reports dollar figures in millions. Netflix's income statement is
  explicitly "(in thousands...)" -- every NFLX dollar value parsed here
  was silently 1000x too large, though it matched the XBRL value
  digit-for-digit (only the decimal scale was wrong, so no earlier check
  caught it). Fixed by detecting the "(in thousands/millions)" annotation
  nearest the matched value instead of assuming; TSLA turned out to have
  the same issue in its 2018-2019 releases.
- **False positive on the unit-detection fix's first attempt:** a naive
  substring search for "in thousands" also matched inside Apple's header
  "...except number of shares which are reflected **in thousands** and per
  share amounts", which describes the share count, not the dollar unit --
  this silently broke every AAPL entry (0/119 agreement) before being
  caught by an immediate regression re-run. Fixed by anchoring the regex to
  the parenthetical right after "(", the standard SEC table-header
  convention, not a bare keyword search.

**One real bug in the underlying SEC XBRL data itself, found (not fixed --
noted as a real data-quality risk):** Oracle's own FY2020 10-K tags one
revenue datapoint with quarter-length start/end dates (`2018-03-01` to
`2018-05-31`, 91 days -- passes this project's single-quarter filter) but a
value of $39.4B -- Oracle's actual *full-year* FY2018 revenue, not a
quarter's. The filer's own tagging is internally inconsistent (a "Selected
Financial Data" comparative table mistagged), not a bug in this project's
extraction code, but the `_is_single_quarter` date-length filter alone
can't catch a scope mismatch like this. Left as a known gap -- see below.

**Final numbers, after fixing both earnings_release.py bugs and two
methodology bugs in the scorer itself** (documented in `build_gold_set.py`
and `score_against_gold.py` -- the first scoring attempt used the 8-K's
filed date as the point-in-time cutoff, which is sometimes *before* the
quarter's own 10-Q was filed, so the live pipeline correctly returned the
*previous* quarter and the script mis-scored that as a classification bug;
fixing that to use the 10-Q's own filed date, and then further fixing which
*version* of a restated number to date-anchor against, is what got the
score from an initial ~86% down to a false ~81% and finally up to the real
number):
- **Extraction accuracy: 371/390 (95.1%)** dual-sourced values agree
  between the XBRL 10-Q and the 8-K earnings release.
- **Classification accuracy: 310/312 (99.4%)** -- an independently
  reimplemented Supported/Weakened/Broken classifier (not calling
  `reason_engine.py`'s own function) agrees with the live pipeline's status
  on confirmed-correct values. The 2 remaining mismatches (both KO) trace
  to a genuine prior-year-comparator restatement between when it was first
  filed and when the following year's comparison used it -- a real
  evidence-conflict case, not a classification bug.

`data/gold_set.json` (390 entries) is now a reusable artifact -- e.g. as
the reference set for the LLM-vs-baseline experiment PROPOSAL.md section 9
asks for, instead of scoring against this pipeline's own output.

## Baseline 1 & 2 scaffolding (`baseline1.py`, `baseline2.py`)

**Status as of the full experiment further down: both have since been run
for real, repeatedly** (a 5-company subset, then the full 45-case
experiment, then reused again in the consistency experiment) -- the
"written but not run yet" framing below is kept as-written for the
still-accurate account of *why* they were built and how they were verified
before any money was spent on them; it described the true state at the
time.

The rule-based-vs-LLM comparison already done (`compare_planners.py`) isn't
the baseline ladder PROPOSAL.md section 9 actually asks for -- both those
planners call the same tools for the underlying number, so of course the
number matches (see the "system works, research design doesn't yet"
critique below). Wrote the two weaker baselines that comparison is missing,
so the real ladder (parametric-only -> single-shot RAG -> this system's
tool-using agent) can be scored against `data/gold_set.json` once budget is
available -- but did **not** spend any API budget running them yet, per
"finish what's free first."

- **`baseline1.py`** -- parametric-only: Claude gets the reason description
  and nothing else (no tools, no retrieved data), asked to classify from
  training knowledge alone or honestly say "Not enough data." This is
  expected to be stale or wrong for recent quarters -- that's the point;
  it's what should make Contribution 1's point-in-time retrieval look
  necessary once scored.
- **`baseline2.py`** -- single-shot RAG: this script (not the model) calls
  `check_reason_status` exactly once, embeds the JSON result as prompt
  text, and asks for a classification -- no tool-calling loop, no ability
  to go get a second source if the evidence looks uncertain. That
  limitation is exactly what `agent.py`'s `get_secondary_evidence` follow-up
  step is meant to improve on.
- Both funnel through a new shared `llm_client.py` (factored out rather
  than copy-pasting `agent.py`'s HTTP-calling code into two more files;
  `agent.py` itself was left untouched since it's already tested and
  working) and a new `FINALIZE_SINGLE_REASON_TOOL` in `tools.py` (the
  single-reason counterpart to `FINALIZE_REPORT_TOOL`, same reasoning:
  structured output, not free text to parse).

**Verified for free, without spending any API budget:** monkeypatched
`llm_client.call_claude` with a canned response and ran both scripts
end-to-end -- confirms the tool-call parsing, the loop-termination logic,
and (for baseline2) that the real retrieval call to `check_reason_status`
actually runs and returns real data (`AAPL revenue_growth` -> `Supported`,
fetched live from the cached SEC data) before the fake LLM response gets
spliced in. Also verified the "model didn't call the tool, get nudged,
retry" path works and token usage accumulates correctly across turns. (At
the time this was written, how the real model actually answers baseline1/
baseline2 was still unverified and intentionally deferred -- see the
5-company subset immediately below, and the full 45-case experiment
further down, for the real runs that followed.)

## Real budgeted run: baseline1 vs baseline2 vs agent, 5-company subset (`run_baseline_subset.py`)

First real spend of the session on the baseline ladder, deliberately scoped
to a subset (AAPL, MSFT, NVDA, GOOGL, AMZN x 3 reasons = 15 cases) before
committing to the full 15-company run. Cost: **$0.356** (52,864 input +
13,192 output tokens).

**Clean, exactly the pattern the ladder is supposed to show:**
- **Baseline 1 (parametric only, zero data): 2/15 (13%) agreement** with
  the retrieved ground truth. Correctly answered "Not enough data" 13/15
  times instead of guessing -- the right behavior for a model with no data
  access, not a failure. Of the 2 times it did commit to an answer: one
  happened to match, one was a real wrong guess (AMZN operating margin:
  guessed Broken, actually Weakened).
- **Baseline 2 (single retrieval, no follow-up): 14/15 (93%)**. Real
  retrieved data gets you most of the way there. The one miss is the exact
  same AMZN operating-margin case -- baseline2 had the real number but
  classified a borderline-Weakened margin as Broken.
- **Agent (this project, follow-up tool calls): 15/15 (100%)**. The one
  case baseline2 got wrong is precisely where a second source
  (`get_secondary_evidence`) helps the agent land on the correct
  classification instead of over-reading a borderline number -- the exact
  mechanism Contribution 2 is supposed to add value through, now shown
  against an external reference rather than the pipeline scoring itself.

This is the first result in the whole session that compares the agent
against something *other than its own tools* -- see "Not yet done" below
for what's left before this generalizes past a 15-case spot check.

## Fixed: indefensible Weakened/Broken boundary for growth and margin reasons

Direct response to a sharp question: "why is AMZN's 13.7% margin (vs a 20%
threshold) 'Weakened' and not 'Broken'? Who decided that?" Read the actual
rule (`reason_engine.py`'s `_classify`) to answer it precisely, and found a
real inconsistency: for `>`/`>=` reasons (revenue growth, margin), Weakened
only meant "still positive" (`computed >= 0`) -- a 0.5% margin against a 20%
threshold classified identically to a 19.9% margin, both merely "still
positive." Meanwhile the `<` reason (debt) already used a *proportional*
buffer (`computed <= threshold * 1.5`). No defensible answer existed for
where the >/>= boundary came from.

Fixed to use the same proportional-buffer logic on both sides: Weakened
means "still cleared at least half of what was required" (>/>=) or "missed
by no more than half again" (< /<=) -- one 50%-of-threshold rule in both
directions, applied consistently. Updated in two places that must stay in
sync by spec (not by import, deliberately -- see `score_against_gold.py`):
`reason_engine.py`'s `_classify` and `score_against_gold.py`'s independent
`classify_independent`.

**Real, defensible changes in the live dashboard after the fix** (all free
to verify, `portfolio_report.py` and the web app, no LLM calls): TSLA's
1.4% operating margin, WMT's 4.3%, and COST's 4.0% all flip from 🟡
Weakened to 🔴 Broken -- correctly, since none of them cleared even half of
the 20% target. AMZN's 13.7% margin (closer to the 10% half-threshold
boundary) correctly stays 🟡 Weakened. Re-ran `score_against_gold.py` after
the fix: still 310/312 (99.4%) classification accuracy, same two KO
mismatches as before (the known restatement-timing edge case) -- confirms
the fix didn't regress anything it was already getting right.

## Investigation capability: reading the actual filing narrative (`filing_context.py` + `investigate.py`)

Direct response to the sharpest question raised this session: "where's the
Agentic value if it's really just `154 > 15`?" The answer proposed was a
second capability layer -- when a deterministic reason comes back Broken,
an agent that can read the company's own explanation for it (the MD&A
narrative in the primary 10-Q/10-K, not just XBRL numbers) is doing
something a threshold rule fundamentally cannot.

**`filing_context.py` (free, no LLM calls) locates and extracts the
relevant narrative section.** Fetches the primary 10-Q/10-K document (not
an exhibit -- the actual filing text), finds the section discussing the
reason's metric (e.g. "Long-Term Debt", "Financing", "Results of
Operations"), and returns the surrounding text. Verified against 3 real
companies' actual Broken-debt-reason filings:
- **GOOGL:** found "Long-Term Debt ... During 2026, we issued $20.0
  billion of US dollar-denominated ... and $31.8 billion of foreign
  currency-denominated fixed-rate senior unsecured notes for general
  corporate purposes" on the first try.
- **META:** found "$24.91 billion net proceeds from the issuance of the
  Notes in May 2026" under a "Financing Activities" section.
- **AMZN:** first attempt returned an irrelevant lease-commitments table --
  caught and fixed a real bug: the keyword search was case-sensitive, and
  Amazon writes "Long-term debt" (lowercase "t") where the keyword list had
  "Long-Term Debt". Fixed to case-insensitive matching; re-verified it then
  finds the actual debt cash-flow figures ($66,998M / $81,925M proceeds).

**`investigate.py` reads that narrative and synthesizes findings -- real,
budgeted run, GOOGL's Broken debt reason** (cost: **$0.017**, 1516 input +
843 output tokens):
- Correctly identified the cause: $51.8B in senior unsecured notes issued
  in 2026 ($20B USD + $31.8B foreign currency), grounded in the actual
  filing text, not speculation.
- Correctly concluded `is_data_artifact: False` -- a real financing event,
  not a restatement or tag mismatch.
- Unprompted, flagged something worth checking in this project's own
  pipeline: it noticed the prior-period comparative figure in the filing
  text didn't obviously match what our growth calculation used, and listed
  that as a specific follow-up -- the model auditing this project's own
  arithmetic, not just the company's numbers.
- `what_to_check_next` gave concrete, specific follow-ups (how the $51.8B
  was deployed, any related preferred-stock changes) rather than generic
  "investigate further" boilerplate.

This is the answer to "why Agentic AI and not just a threshold rule":
`154% > 15%` only detects the anomaly; explaining *why* -- financing event
vs. restatement vs. tag mismatch vs. acquisition -- needs reading unstructured
filing text and synthesizing it, which no deterministic rule in this
project could do.

## Wired into the agent's own tool loop: the LLM decides when to investigate

`investigate.py` above was a standalone script -- a human decided when to
run it. Generalized `filing_context.get_filing_narrative` into a proper
`get_filing_context(ticker, reason_key)` tool in `tools.py` (reusing the
same retrieval logic, no LLM involved in the tool itself) and added it to
`agent.py`'s `run_with_llm` tool set, with one line of prompt guidance:
investigate a reason's filing context when it's Broken or otherwise severe,
before writing the rationale.

**Real run, GOOGL, $0.035** (7,495 input + 851 output tokens): the agent
called `check_reason_status` for all three reasons, found debt Broken,
and *on its own initiative* -- nothing forced it -- called both
`get_secondary_evidence` (numeric cross-check) and the new
`get_filing_context` (narrative cross-check) before finalizing. The
resulting rationale changed from "154% > 15%, Broken" to:

> "Long-term debt grew 315.8% YoY, far exceeding the 15% limit. This
> reflects real debt issuances of approximately $51.8 billion in Q1-Q2
> 2026 (US dollar, Sterling, and Swiss Franc notes) for general corporate
> purposes, representing a significant change in capital structure."

The rule-based planner (`run_rule_based`, free) was re-checked afterward
too -- unaffected, still correctly triggers `get_secondary_evidence` on
Broken/Weakened/Not-enough-data reasons; it doesn't call
`get_filing_context` (that's a deliberate scope decision for right now, not
an oversight -- see below).

## AI-assisted primary-source verification set: a third source, primary filing text (`build_primary_source_verification_set.py`)

Direct response to: "`data/gold_set.json`'s two sources are both the
company's own books -- add a stratified verified subset read from primary
filing text." Built `build_primary_source_verification_set.py` -- free (SEC
document fetches only, no LLM calls) -- which for every (ticker,
reason_key) takes the exact number `check_reason_status`'s XBRL evidence
relied on and confirms it's genuinely printed in the primary 10-Q/10-K's
own text (not the 8-K, not XBRL) with a direct quote, across all 15 pilot
companies x 3 reasons.

**Named precisely, deliberately not "human-verified":** this is Claude
reading primary-source text and recording a judgment with a citation, not
a professional human analyst -- the module was originally named
`build_primary_source_verification_set.py` and renamed specifically because that implied
more than it delivers. It's a genuinely independent third source -- distinct
from both
the XBRL pipeline and the 8-K cross-check -- but should be described as
"AI-assisted verification against primary filing text," not "human-labeled
ground truth."

**Three real bugs found and fixed while building this, in order:**
1. **Blind column-order extraction breaks across companies.** A first
   attempt tried to independently re-derive the value (find the keyword,
   take the first number after it) the same way `earnings_release.py`
   does for 8-K exhibits. Broke immediately: Amazon's 10-Q lists the
   *prior-year* quarter's column before the current one (Apple's 8-K does
   the opposite), so "first number after the keyword" silently grabbed the
   wrong figure for several companies -- not a small rounding difference,
   a completely different number. Fixed by switching from blind extraction
   to citation search: take the number the live pipeline already trusts,
   and confirm it's printed nearby, which is robust to column order.
2. **Wrong filing entirely for companies whose latest filing is a 10-K.**
   A second attempt always fetched "whichever 10-Q/10-K is most recent."
   Broke on MSFT: its latest filing is an annual 10-K printing only
   full-year figures ($331,839M FY2026) -- the $82,886M quarterly figure
   the live pipeline's growth calculation actually used was filed months
   earlier in a 10-Q, and isn't re-printed anywhere in the 10-K at all.
   Fixed by parsing the accession number directly out of the XBRL
   evidence citation (`Fact.label()`'s "(filed ..., form, accn ...)"
   suffix) and fetching *that* specific filing, not just the newest one.
3. **Keyword search anchored on the wrong metric's section.** A third bug:
   the keyword-anchor search used one combined list of Revenue +
   OperatingIncome + LongTermDebt keywords regardless of which metric was
   being checked, so operating_margin/debt_growth checks kept anchoring on
   a "Revenue" mention (found earlier in every document) and never reached
   the real Operating Income or Debt section within the search window.
   Fixed by using `earnings_release.py`'s existing per-metric keyword map
   instead of a flattened list.

**First result, 49 entries** (latest quarter only per ticker x reason):
38/43 (88%) confirmed, 2 correctly found no evidence (JNJ operating margin,
ORCL debt -- independently confirms "Not enough data" is real, not a
pipeline bug), 5 misses individually diagnosed (see below), 4 structural
cases.

**Expanded to 352 entries by walking historical quarters, not just the
latest.** `historical_as_of_dates()` samples up to 8 distinct filed-dates
per (ticker, reason_key) from the same underlying facts `main.py`/
`portfolio_report.py` already walk, and `verify_one()` now takes an
`as_of` parameter so each historical quarter gets its own citation-search
pass -- still free, just more SEC document fetches (cached after first
fetch). Deduped by accession number so a quarter's filing that resolves
identically from two nearby simulated "todays" isn't counted twice, and
the "latest" (as_of=None) call is always kept even when historical
sampling would otherwise land on older dates -- without that, a company
whose metric later stopped being reported (JNJ) would only ever hit the
old dates where it still existed, silently losing the current "Missing"
case.

**Final result, 352 entries in `data/primary_source_verification_set.json`**
(346 per-quarter scans across 15 companies x 3 reasons x up to 8 historical
quarters, plus 4 structural cases):
- **308/346 (89%)** of the scannable cases had their XBRL-derived value
  directly confirmed printed in the primary filing text, quoted.
- **Status distribution across the historical sample: 216 Supported, 80
  Broken, 50 Weakened** -- real variation across time, not just the
  15-company snapshot's current-quarter mix (e.g. WMT alone shows Broken
  in some quarters and Weakened/Supported in others across the 8 sampled).
- **2** correctly found no evidence at all (JNJ operating margin, ORCL
  debt) -- independently confirms those "Not enough data" statuses are
  real, not a pipeline bug hiding real data.
- **38 misses on the expanded pass**, 5 of which (the original latest-quarter
  ones) are individually diagnosed rather than left as a bare failure (see
  `diagnosis` field): a "Financial Highlights" summary table matched before
  the real income statement (COST), inline-XBRL tag metadata leaking
  through the HTML-stripping regex (JNJ, PEP), a debt commitments/
  payment-schedule table matched before the real balance sheet line (MSFT),
  and an accounting-policy footnote sentence matched before the real
  balance sheet line (PG). The remaining historical-quarter misses weren't
  individually diagnosed (would mean hand-checking dozens more documents)
  -- each is a distinct, real limitation of full-text search on large SEC
  documents, not evidence the underlying XBRL values are wrong (all
  previously cross-confirmed in `data/gold_set.json`'s 8-K comparison).
- **4 structural cases** (Restatement, Tag/definition conflict, Real
  anomaly, Data artifact) using the concrete real cases already found
  earlier this session -- MSFT's ASC 606 revenue restatement, MSFT's
  LongTermDebt/LongTermDebtNoncurrent tag conflict, GOOGL's debt issuance
  (directly quoted from primary filing text, independently re-confirmed by
  `investigate.py`'s real LLM run), and Oracle's FY-tagged-as-quarter data
  artifact -- each with its evidence citation and provenance recorded.

`352` clears the ~100-200 case target originally proposed. The 4 structural
categories are still 1 example each -- they're rare, cross-period phenomena
by nature, not something a per-quarter scan can multiply the way Supported/
Weakened/Broken sampling could.

## Stratified review packet for a real human reviewer (`build_review_sample.py`, `render_review_packet.py`)

The 352-entry set above is too large to hand someone as "please review
this" -- built `build_review_sample.py` to select a stratified, diverse
61-case sample from it (15 Supported, 15 Weakened, 15 Broken -- capped at 2
per ticker so no single company's history dominates a bucket -- 2 Missing,
10 "needs human eyes" cases the citation search itself couldn't confirm,
and the 4 structural cases), and `render_review_packet.py` to turn that
into a browsable page: every case links to the real SEC filing index page
(spot-checked one link with a live HTTP request -- 200 OK), shows the
quoted primary-filing text and the pipeline's value/status side by side,
and has a per-case "Reviewed" checkbox + notes field that persists in the
*viewer's own browser* (localStorage) -- explicitly labeled as a personal
convenience, not a shared record, since nothing here should be presented
as more authoritative than what a human reviewer actually confirms.
Published as an Artifact rather than a flat file specifically so a
non-technical reviewer can just open a link and start working through it.

## Full baseline experiment: 4 approaches x 45 cases, scored against a reference set (`run_full_experiment.py`)

The real experiment this session's other comparisons were building toward:
not scoring against `check_reason_status`'s own output (which every earlier
run in this session did to some degree), but against an independently
derived reference status -- `run_full_experiment.build_reference()` reuses
`score_against_gold.py`'s `classify_independent` (a second, separate
implementation of the classification rule) applied to
`data/primary_source_verification_set.json`'s primary-filing-confirmed
values, picking each (ticker, reason_key)'s most recent confirmed quarter.
Found a real coverage problem first: an initial version sourced the
reference from `data/gold_set.json` and only got a usable reference for
20/45 pairs, several badly stale (TSLA's most recent gold-confirmed quarter
was 2019 -- nowhere near what the live pipeline actually evaluates as
"latest"). Switching to `primary_source_verification_set.json` (denser,
more recent, built for the review packet) raised that to **39/45 (87%)**,
all in 2024-2026.

**Real, budgeted run, all 4 approaches x 45 cases** (cost: **$1.365**,
105 LLM calls -- Baseline 1 $0.404, Baseline 2 $0.396, Rule-based $0.000,
Agent $0.565):

| | Accuracy | Severe-case (Broken) escalation recall | False-positive rate (escalates on Supported) |
|---|---|---|---|
| Baseline 1 (parametric only) | 5/39 (12.8%) | 5/5 (100%) | **29/29 (100%)** |
| Baseline 2 (single-shot RAG) | 34/39 (87.2%) | 2/5 (40%) | 0/29 (0%) |
| Rule-based (this project, free) | 39/39 (100%) | 5/5 (100%) | 0/29 (0%) |
| Agent (this project, tool-using) | 39/39 (100%) | 5/5 (100%) | 0/29 (0%) |

**Baseline 1's "100% severe-case escalation" is not real judgment --
checked before reporting it at face value.** Its human-review flag is
`True` on literally every single case, severe or not (100% false-positive
rate on the 29 reference=Supported cases too) -- a model with no data
always says "needs review" because it's always uncertain, which trivially
maximizes recall at the cost of being useless as a filter. Recorded
precisely rather than citing the misleading 100% recall figure alone.

**Baseline 2's real weakness: it misses 3 of 5 genuinely severe cases**
(40% recall) despite 0% false positives -- it has the right data but
under-escalates on borderline-severe readings, the same failure mode the
AMZN margin case demonstrated earlier in this session, now shown at
5x the sample size.

**Rule-based and Agent tie at 100% accuracy and identical escalation
behavior** -- expected, since both ultimately rely on the same
`check_reason_status` tool already validated at 99.4% classification
accuracy (see the gold-set section above), so neither can score higher
than that tool's own ceiling on this metric. This is exactly why "the
agent is more accurate" was never the right claim for this project (see
the "system works, research design doesn't" critique earlier) -- accuracy
was never where the agent's advantage would show up. The agent's actual
differentiator, demonstrated earlier in this session and not re-measured
by this accuracy table, is investigation depth: `get_filing_context`
turning "Debt Broken, 315.8% > 15%" into a grounded explanation of *why*
(a real $51.8B note issuance, confirmed not a data artifact) -- something
this accuracy score can't capture because Rule-based and Agent's raw
status/review outputs are identical by construction.

**Latency, for completeness:** Rule-based ~0.1s/call (deterministic,
no network round-trip beyond cached SEC data), Baseline 2 ~6.5s/call,
Baseline 1 ~9.9s/call (small prompt, no tools -- surprisingly not the
fastest, likely dominated by network/queueing rather than prompt size),
Agent ~19.9s/call (multi-turn tool-use loop, slowest but does the most
work per call).

Full row-by-row results in `data/full_experiment_results.json`.

## Run-to-run consistency experiment (`run_consistency_experiment.py`)

The other open question this session's PG case (same input, different
human-review verdict across two runs) raised but never systematically
measured. Repeated `agent.run_with_llm` 7x each on the 9 tickers with a
non-Supported reference status (GOOGL, AMZN, META, TSLA, PEP, JNJ, PG, WMT,
COST -- the ones where a judgment call is actually being exercised, not
just re-confirming "Supported" every time) and measured, per reason, how
often the final status, the human-review verdict, and the tool-selection
pattern actually varied on identical input.

**One near-miss caught before it became real spend:** the first attempt at
a free dry-run monkeypatched `agent.call_claude`, but `agent.py` makes its
own direct `requests.post` call (a deliberate earlier decision, documented
above, to leave it untouched rather than risk the already-tested code) --
so that patch silently did nothing and the "free" test was actually about
to make real paid calls. Caught within seconds (no output had even been
written to the log yet) and killed before it ran meaningfully far; verified
the one piece of genuinely new logic (`tool_signature()`, the tool-call
parser) against a hand-written trace string instead, then proceeded
straight to the real run rather than trying to mock around a script that
doesn't support mocking.

**Real, budgeted run: 63 calls, $2.836** (603,248 input + 68,441 output
tokens -- higher than the ~$2.20 estimate, because `get_filing_context`'s
quoted filing text accumulates in the conversation across multi-turn
tool-use loops, so prompts on investigation-heavy tickers run larger than
the earlier per-call estimate assumed):

| | Agreement |
|---|---|
| **Final status** (Supported/Weakened/Broken/Not-enough-data) | **100%** across all 27 reason-checks |
| **Human-review verdict** | **97.9%** (2 disagreements, both traced to specific tickers below) |
| **Tool-selection pattern** (which tools got called, how many times) | **71.4%** mean across 9 tickers, ranging 57%-86% |

**Three distinct findings, not one pass/fail number:**
- **The status itself never varies.** It's derived from `check_reason_status`'s
  deterministic tool output, which the LLM reports rather than invents --
  100% agreement here isn't surprising, but it's the right thing to confirm
  rather than assume.
- **The human-review judgment call is *nearly* but not perfectly stable.**
  PEP flipped on 1/7 runs each for revenue_growth and operating_margin (86%
  agreement); JNJ flipped on 2/7 runs for revenue_growth (71% agreement).
  Every other ticker/reason was perfectly consistent (100%). This is the
  PG-style inconsistency found earlier, now reproduced systematically and
  quantified rather than found by accident -- real, but rare (2 of 27
  reason-checks, both on Weakened-not-Broken cases, consistent with the
  earlier finding that judgment calls near a status boundary are exactly
  where this shows up).
- **The investigation *process* is markedly less stable than its
  *outcome*.** Tool-selection agreement (57-86%) is much lower than status
  or review agreement (97-100%) -- the agent sometimes calls
  `get_secondary_evidence` once, sometimes twice, sometimes skips
  `get_filing_context` on a run where it called it on others, even while
  landing on the identical final status and review verdict almost every
  time. The *path* to a conclusion varies more than the conclusion itself.
  Worth stating plainly as its own finding: this project's earlier
  "Agentic value" claims were about the investigation capability existing
  and being reachable, not about it running identically every time --
  this experiment is the first evidence characterizing that variability
  rather than just noting it might exist.

Full per-run data in `data/consistency_experiment_results.json`.

## Personalization layer: Investor Context on top of Objective Evidence (`investor_profile.py`, `personalization.py`, `run_personalization_experiment.py`)

Contribution 4 (PROPOSAL.md) -- the part of the original vision (Contribution
3) that got deferred out of scope early on, brought back in lightweight form
after a reviewer push-back that the same evidence can legitimately mean
different things to different investors, and that dropping it entirely left
a real research-question gap unaddressed (InvestLogicBench, arXiv:2608.06108,
makes exactly this point with 201k real investor decisions -- see
`LITERATURE_REVIEW.md` section 7).

Implemented as two layers, kept strictly separate on purpose:

- **Objective Evidence Layer** (unchanged): the existing
  Supported/Weakened/Broken/Not-enough-data status from `reason_engine.py` /
  `agent.py`. Identical for every investor -- this layer is never
  personalized.
- **Investor Context Layer** (new): takes that status plus a synthetic
  `InvestorProfile` (risk tolerance, investment horizon, position size %,
  objective) and produces a priority tier -- Monitor / Watch / Review Soon /
  Review Now. Two independent implementations of this decision: a free
  deterministic `rule_based_tier()` matrix (severity x position-size
  multiplier + risk/horizon adjustments, with Supported hard-coded to always
  return Monitor regardless of profile), and `llm_tier()`, which asks Claude
  to make the same call and is forced (via the tool schema) to echo back the
  evidence status it was given verbatim -- the mechanism the integrity check
  below relies on.

**Real, budgeted run: 68 calls, $0.341** (58,622 input + 11,026 output
tokens -- under the $1 cap set for this experiment), 17 cases (15
non-Supported cases from the full-experiment set, plus 2 Supported controls)
x 4 synthetic profiles spanning the interaction the experiment is meant to
surface (aggressive/small-position/long-horizon vs.
conservative/large-position/short-horizon, plus two mixed profiles):

| | Result |
|---|---|
| **Evidence integrity** (echoed status == input status) | **68/68, 100%** |
| **Cases where profile changed the tier** | **15/17** |
| **Agreement with the rule-based baseline** | **28/68, 41.2%** |

**Three findings:**
- **The safeguard held: 0 integrity failures.** Across every profile x case
  combination, the LLM never once returned a different evidence status than
  it was given -- personalization stayed confined to the tier decision and
  never leaked into re-judging the underlying fact. This was the one
  outcome this architecture was not allowed to produce, and it's the
  concrete answer to "how do you know the AI isn't bending evidence to fit
  the user."
- **The 2 non-divergent cases are exactly the 2 Supported controls.** Both
  Apple cases (revenue_growth, operating_margin) returned Monitor for all 4
  profiles, by design (`rule_based_tier` short-circuits Supported to Monitor
  before considering profile at all). All 15 non-Supported cases produced at
  least 2 distinct tiers across the 4 profiles -- concretely reproducing the
  worked example from the design discussion (same Broken debt-growth
  finding, different priority for a 3%-position/high-risk-tolerance investor
  vs. a 25%-position/low-risk-tolerance one with a 1-year horizon).
- **Low rule/LLM agreement (41.2%) has a direction, not just noise: the LLM
  is never less urgent than the rule baseline, often more.** Most visibly on
  the aggressive/small-position profile -- the rule matrix lets a small
  enough position size fully offset a Broken/Weakened severity back down to
  Monitor, but the LLM almost always floors it at Watch regardless of how
  small the position is. Read as the rule matrix treating severity and
  position size as freely offsetting, while the LLM treats severity as a
  base level that profile factors can adjust but not fully cancel out. Not
  a bug in either -- a genuine difference in decision philosophy between a
  hand-written matrix and an LLM asked to weigh the same factors, worth
  treating as a discussion point rather than picking one as "correct."

Full per-case data in `data/personalization_experiment_results.json`.

## Investigation State + deterministic Evidence Assessor (`investigation_state.py`), and wiring evidence into personalization (`personalization.investigate_and_personalize`)

A design review of the architecture (Investigation Agent broken into its 5
sub-parts: Context/State, LLM Decision, Tool Executor, Evidence Assessor,
Stop/Escalation Rules) found two real gaps against `agent.py` as it stood:

1. **No explicit state.** The only record of what the agent had investigated
   was the raw `messages` conversation history -- nothing tracked, as
   structured data, which reason had which tool called against it.
2. **No Evidence Assessor separate from the LLM.** "Is the evidence
   sufficient to finalize" was entirely the LLM's own judgment, prompted in
   natural language ("for anything uncertain, gather a second source") but
   never checked in code. The LLM could finalize a Broken/Weakened reason
   without ever having actually gathered the corroborating evidence the
   prompt asked for, and nothing would catch it.

**`InvestigationState`** (new module, `investigation_state.py`) records every
tool call (name, input, result) as the agent makes it, queryable via
`calls_for(tool_name, reason_key)` -- kept alongside the message history, not
instead of it.

**`assess_sufficiency(state, proposed_reasons)`** is a deterministic
checkpoint `agent.run_with_llm` now runs on every `finalize_report` call
before accepting it. It doesn't re-judge the LLM's classification of a
reason's status (that stays the LLM's call) -- it only catches a narrow,
checkable failure: an uncertain status finalized without `get_secondary_evidence`
having been called for it, or conflicting evidence found without
`get_filing_context` having been called. On a problem, the loop **rejects the
finalize call and pushes the agent to actually investigate further** (an
injected user message listing what's missing), capped at 2 rejections so a
reason the agent genuinely can't satisfy (e.g. filing context comes back
empty) can't spin forever -- the existing `range(10)` overall loop cap is the
backstop either way. A run's `assessor_gaps` field records what was still
unresolved when it gave up, if anything.

**Verified free before spending anything real**: 5 synthetic
`InvestigationState` fixtures covering each rule (missing secondary evidence,
missing filing context, already-sufficient, never-checked) all passed before
touching the API.

**Real, cheap run: GOOGL, $0.036.** `assessor_gaps: []` -- the agent already
called `get_secondary_evidence` + `get_filing_context` for the Broken
debt_growth reason on its own (matching what the system prompt asks), so the
assessor passed clean rather than needing to reject anything. That's the
expected common case -- the assessor is a safety net proven to work by the
synthetic tests, not something meant to fire on every run.

**`investigate_and_personalize(ticker, profile)`** (added to
`personalization.py`) closes the third gap: Contribution 1/2 (evidence
status, via the agent) and Contribution 4 (personalization) used to be two
separately-run scripts whose output had to be manually chained (run the
agent, save the result, feed it into the personalization experiment). One
call now runs `agent.run_with_llm(ticker)` and, for every reason it returns,
both `rule_based_tier()` and `llm_tier()` for the given profile -- returning
status, both tiers, and the integrity check in one result.

**Real test**: GOOGL + a conservative/short-horizon/large-position profile --
all 3 reasons came back with status, `rule_based_tier`, `llm_tier`, and
`integrity_ok: True` in a single call.

## Confidence field + real Human Escalation on loop exhaustion

Two more gaps found comparing this project against a full production-grade
"Agentic System Architecture" reference diagram (Context / Application /
Component levels + a 3-tool Investigation Agent) -- the two cheapest,
highest-value ones to close first:

- **Confidence.** `FINALIZE_REPORT_TOOL`'s schema (`tools.py`) previously had
  no way to say "I found this, but I'm not fully sure" separately from the
  status itself. Added a required `confidence: high|medium|low` field,
  explicitly documented as independent of `human_review_recommended` (a
  low-confidence Supported doesn't need escalating; a high-confidence Broken
  still might, for severity reasons). **Real test, MSFT, $0.023**: all 3
  reasons came back `confidence: high` -- the expected result on a clean
  case with no conflicting evidence.
- **Human Escalation on loop exhaustion.** `run_with_llm` previously
  `raise`d a bare `RuntimeError` if the agent never reached
  `finalize_report` within its 10-iteration cap -- every caller had to
  handle a crash. "The agent couldn't reach a conclusion in a bounded
  number of steps" is exactly the case a Human Escalation path exists for,
  not an error state, so it's now a normal return: `escalated: True`,
  `escalation_reason` (naming which reasons were checked before giving up,
  read back from `InvestigationState`), `reasons: []`. Every successful
  path also now carries `escalated: False` so callers can check one field
  instead of a try/except. `personalization.investigate_and_personalize`
  propagates escalation instead of silently returning an empty
  personalized list (which would otherwise look identical to "checked
  everything, all Supported").
  **Verified free**: mocked `requests.post` so the model only ever calls
  `check_reason_status` and never `finalize_report`, forcing the real loop
  to exhaust its cap -- confirmed no crash, `escalated: True`,
  `escalation_reason` correctly named the one reason it had checked
  (`revenue_growth`) before giving up. No real run has actually hit this
  path in any experiment so far (all agent runs to date reach
  `finalize_report` well within 10 iterations) -- expected, since this is a
  safety net for a case that hasn't occurred yet, not a common path.

## Production-grade push: database, a Metric Calculator tool, web search, and a real Web UI (`db.py`, `tools.calculate_metric`, `tools.WEB_SEARCH_TOOL`, `webapp.py`)

Requested explicitly, against the architecture reference diagram's full
production vision -- four pieces, each additive to the already-tested
pipeline rather than replacing it (see each section for why).

**SQLite persistence (`db.py`).** Stdlib `sqlite3`, no ORM -- same "no
framework where plain code does the job" discipline as agent.py calling the
Anthropic API directly. Deliberately additive rather than a replacement for
`tools.REASON_DEFS`: 11 already-tested scripts import `REASON_DEFS`
directly, so rewriting them all to read from a database in one pass would
risk regressing work already validated against real SEC data and real
money. Instead: the 3 built-in reasons + 4 built-in investor profiles are
seeded into `reasons` / `investor_profiles` tables on init (idempotent),
existing code keeps reading `REASON_DEFS`/`ALL_PROFILES` unchanged, and new
custom profiles + a full run history (`investigation_runs`) are the
database's actual job. **Verified free**: full CRUD round-trip (save/list a
custom reason, save/list/get-by-name a custom profile, save + list a fake
investigation result) -- all passed before anything touched a real API.
**Wired into the real pipeline**: `personalization.investigate_and_personalize`
now persists every reason's result automatically (`persist=True` by
default; experiment scripts that call `agent.run_with_llm` directly are
untouched, so they don't flood the table with test noise). **Real test**:
MSFT + a profile -- 3 rows appeared in `investigation_runs` with the
correct ticker/status/tiers, confirmed by reading them back.

**Metric Calculator as its own tool (`tools.calculate_metric`).** Refactored
the fetch-facts-and-evaluate step out of `check_reason_status` into a shared
`_evaluate_reason()` helper so the Rule Engine (status + threshold) and the
new Metric Calculator (the arithmetic alone, no threshold judgment) can't
drift apart on the actual number -- both call the same `reason_engine`
functions. **Regression-tested free** against cached SEC data: confirmed
`check_reason_status`'s output is byte-identical to before the refactor, and
`calculate_metric` returns the exact same `computed_value` with no `status`
field. **Real test**: NVDA end-to-end through `agent.run_with_llm` with the
new tool available -- ran clean, no errors ($0.041; the agent didn't happen
to reach for it this time, which is fine -- it's optional, not mandatory).

**Web search (`tools.WEB_SEARCH_TOOL`).** Anthropic's native server-side
`web_search_20250305` tool -- no new API key, since this project already
calls the Messages API directly. **A real methodological risk, not just
another tool**: live search returns *today's* information, not what was
knowable as of the analysis date, so using it to help decide a reason's
status would reintroduce exactly the look-ahead bias the whole point-in-time
XBRL pipeline exists to prevent. Scoped narrowly in the system prompt:
available only to enrich the rationale text with qualitative context, never
as evidence for the Supported/Weakened/Broken classification, which must
stay derived from `check_reason_status`/`calculate_metric`'s point-in-time
data. Every search call is logged to `trace` for auditability (a reviewer
seeing a rationale that mentions something outside the filed numbers should
be able to see that a search happened and what query ran). **Verified real**:
confirmed the tool type is accepted by this project's exact model
(`claude-sonnet-4-5-20250929`) with a live probe call that returned a real
Apple newsroom search result; ran GOOGL end-to-end through the full agent
loop with the tool available -- no errors, agent chose not to search this
time; a second targeted probe forced a real search to confirm the trace-logging
code matches the actual `server_tool_use` block shape Anthropic returns.

**Web UI: investor profile self-service (`webapp.py` + `templates/index.html`).**
New routes `GET/POST /api/profiles` and `GET /api/personalize/<ticker>` wire
`db.py` and `personalization.investigate_and_personalize` into the existing
Flask dashboard. A new "Personalize for an Investor" panel lets a user pick
an existing profile or create one inline (name, risk tolerance, horizon,
position size, objective) and get real personalized priority tiers rendered
per reason. **Not done**: a UI for entering *custom reasons/thresholds* --
deliberately skipped, because a reason's `metric` field has to match a real
SEC XBRL concept name (`Revenue`, `OperatingIncome`, `LongTermDebt`) for the
extraction code to find anything; letting a user type an arbitrary metric
name via a text box would silently produce "no facts found" for anything
that isn't already a known tag, which is a worse experience than not
offering it, and doing it properly means XBRL-taxonomy validation that's its
own scope. **Verified**: all new routes tested via Flask's test client free
(list, create, and both validation-error paths for profiles; missing-profile
and unknown-profile-name error paths for personalize), then the actual page
was rendered by a live server process and a real personalize call was made
through it end-to-end (MSFT, real tiers came back) before shutting the test
server down.

## The two "not built yet" items, actually built: custom reasons and a portfolio view

Both of these turned out to not need the risky part of what "not built yet"
had implied.

**Custom reasons (`xbrl_extract.list_available_tags`, `tools.get_reason_def`,
`db.save_reason`/`delete_reason`).** The original concern was free-text metric
names silently producing "no facts found." Solved by never taking free text:
`get_company_facts(ticker)` already returns every XBRL tag the company has
actually reported, so `list_available_tags()` turns that into a picker-ready
list (tag name, human label, and whether it's a quarterly-flow or
balance-sheet-instant concept) -- a custom reason can only ever reference a
tag proven to exist for that company. `xbrl_extract.py`'s extraction
functions were refactored (not rewritten) into shared `_extract_quarterly_
from_tags` / `_extract_instant_from_tags` helpers, so the existing curated
multi-tag lookup (`extract_quarterly_facts`, handles tag migration like
Apple's Revenue rename) and the new single-raw-tag lookup (`extract_
quarterly_facts_for_tag`, for a user's exact pick) share one computation
path -- confirmed byte-for-byte identical output on the old path before
building the new one. `tools._evaluate_reason` now resolves a reason from
`REASON_DEFS` first, then a per-ticker `db.list_reasons()` lookup
(`get_reason_def`), so `check_reason_status` and `calculate_metric` handle
custom reasons with zero special-casing beyond that lookup.

**Real, free tests** (all SEC data, no LLM calls): built-in reasons verified
byte-identical to pre-refactor output; a custom yoy_growth reason (AAPL cash
growth via `CashAndCashEquivalentsAtCarryingValue`) and a custom margin_level
reason (AAPL R&D intensity, two quarterly tags) both evaluated correctly
against real filings; a full round-trip through the actual `/api/reasons`
POST/DELETE routes and the web form (pick a tag, save, see it appear in the
main reasons list with real computed status, delete it, list updates) --
caught one real bug this way: `saveCustomReason()`'s confirmation message was
being wiped immediately by a full `selectTicker()` re-entry it triggered
right after showing it; fixed by extracting a lighter `refreshReasonsList()`
that updates just the reasons list without resetting open forms or messages.

**Portfolio view (`db.add_holding`/`remove_holding`/`list_holdings`,
`GET /api/portfolio/summary`, the "My Portfolio" sidebar view).** Reuses
`get_company_report()` (already free, already tested) per held ticker and
rolls up counts -- no new evidence logic, just a `holdings` table and a loop.
**Real test**: added AAPL/MSFT/GOOGL as holdings through the actual UI
(dropdown + button), got back correct per-company worst-status badges and
portfolio-wide totals (11 reasons across 3 companies, matching 5+3+3), and
clicking a row correctly navigates to that company's full detail view.

Both features are fully bilingual (EN/TH) through the same i18n system as
the rest of the app, and neither touches the LLM at all -- defining a
reason, evaluating it, and building the portfolio summary are all free,
same as the rest of the Objective Evidence Layer.

## Multi-user accounts, a mechanical screener, and purchase-time reason snapshots (`db.py`, `webapp.py`)

The simple holdings-based portfolio view above (add/remove a ticker) is
superseded by a purchase-record model built around the project's actual
research question: not "what do I hold" but "is the reason I bought still
true." Requested flow: register, log in, define a personal condition,
screen every company against it, record what was actually bought (with the
reason that justified it), then track whether that reason still holds.

**Accounts.** `users` table + `werkzeug.security` password hashing (ships
with Flask, no new dependency) + Flask signed-cookie sessions
(`app.secret_key`, a `login_required` decorator). `reasons` and
`investor_profiles` gained a nullable `user_id` column (`NULL` = the
existing built-in/shared rows everyone already had; a real id = private to
that user), with a `UNIQUE(user_id, name)` constraint on profiles so two
users can each have their own "Conservative" profile. Every route that
lists, saves, or deletes a reason/profile now scopes its query by
`current_user_id()` -- verified with two real accounts (Alice/Bob): neither
can see or delete the other's custom reasons or profiles.

**Screening, not recommending (`GET /api/screen`).** The user explicitly
wants the system to say which stocks qualify, which sounds like it
conflicts with this project's own claim that it does not recommend what to
buy. Resolved by keeping it mechanical: `/api/screen?reason_key=...` loops
every company in `KNOWN_CIKS` and calls the exact same
`check_reason_status()` used everywhere else in the app -- same free XBRL
lookup, same Supported/Weakened/Broken rule, zero LLM involvement. The
"recommendation" is a transparent filter on the user's own stated
criteria, not an opinion.

**Purchases with a frozen reason snapshot (`purchases` table,
`POST /api/purchases`).** Recording a purchase (ticker, quantity, price,
date, optional `reason_key`) calls `check_reason_status()` once at that
moment and stores the full result as `reason_snapshot_json` -- what the
reason's status *was*, frozen, independent of what it drifts to later or
whether the reason itself gets edited afterward. This is the same
point-in-time principle the rest of the project applies to SEC filings,
now applied to the user's own investment record.

**Tracking (`GET /api/portfolio/summary`).** For each purchase, a fresh
`check_reason_status()` call is compared against the frozen snapshot's
status to produce `still_true` (True/False/None) -- the actual answer to
"does the reason I bought this for still hold." No new evidence logic,
just comparing two calls to a function that already existed.

**A display-ID bug caught before it shipped.** Built-in reasons expose a
cosmetic `R1`/`R2`/`R3` `key` in report responses (from how
`portfolio_report.py` originally built `Reason` objects for display), which
is *not* the real `reason_key` string (`revenue_growth`, etc.) the
screener/purchase APIs require. Recording a purchase against "R2" would
have silently failed to link to the actual reason. Fixed with a
`BUILTIN_KEY_MAP` in the frontend so the purchase-reason and
screener-reason dropdowns always submit the real key.

**Real, free tests.** Backend verified directly via `db.py` calls and
Flask's `test_client()` (registration, duplicate-email rejection,
cross-user isolation, purchase snapshot + both a matching and a
deliberately-mismatched `still_true` case) before touching the browser.
Then a full Playwright run against the real running app: auth gate blocks
access until login/register, a fresh account sees an empty portfolio,
selecting a company shows a purchase form whose reason dropdown carries
correct real keys (not `R1`/`R2`/`R3` -- confirms the bug above is fixed),
recording a purchase against "operating margin >= 20%" produces the
expected confirmation and shows up in My Portfolio with a "Still true"
badge, the screener returns real Supported/Weakened/Broken results with
real percentages across all 15 companies (e.g. NVDA 65.6%, TSLA 1.4%),
logout returns to the auth gate and re-login restores the session, and
switching EN/TH on the new Screener and Portfolio views re-labels
correctly while triggering zero calls to any paid endpoint.

Zero LLM API cost for any part of this feature set -- flagged to the user
up front per their standing rule, and confirmed free before building.

## Fixed: every LLM call was running at the API default temperature (1.0), never actually set (`llm_client.py`, `agent.py`)

Audited every `POST /v1/messages` call site in the codebase (`llm_client.call_claude`, and
`agent.py`'s two inline `requests.post` calls in `run_with_llm`/`_chat_loop`) and found none of
them ever set `temperature` -- every call ran at Anthropic's API default (1.0, full sampling
randomness), silently, since the very first version. This matters because every call this
project makes is a **fact-grounded classification or extraction task** (evidence status,
priority tier, an answer that must be traceable to a specific tool result) -- never creative
generation. The applicable guidance (Deterministic vs. Stochastic Generation: tasks needing
"ข้อมูลข้อเท็จจริง... ควรลด Randomness") is unambiguous for this task shape. Set
`temperature=0` as the default in `call_claude` and explicitly in both of `agent.py`'s inline
calls.

**Known consequence, recorded rather than hidden**: every prior experiment in this README
(`baseline1.py`/`baseline2.py`, the full 45-case experiment, the run-to-run consistency
experiment, the sensitivity analysis) ran at the old default (temperature=1.0, unset). Those
results and any future re-run at temperature=0 are **not directly comparable** -- a drop in
observed variability after this change reflects the temperature change itself, not a change in
the underlying Rule Engine or Evidence Assessor logic (neither was touched). If reproducing the
consistency experiment specifically to measure run-to-run stability going forward, note which
temperature the run used.

## Not yet done

Cleaned up 2026-08-26: several items below were previously listed as open
gaps and are now done (`get_secondary_evidence` generalized past Revenue,
`data/gold_set.json` built) -- removed rather than left contradicting the
sections above. What's left, current as of the investigation-capability work:

- ~~Baseline 2 isn't a fair single-shot-RAG comparison~~ **Fixed and
  re-verified.** `baseline2.py` called `check_reason_status`, which returns
  an *already-classified* status, and handed that straight to the model --
  testing "does it defer to a label it was given," not "can it reason from
  raw evidence." Fixed to strip the `status` field from the retrieved
  payload before it reaches the prompt (dry-tested for free with an
  assertion that no `"status"` key appears in what the model sees, then
  re-ran the AMZN operating-margin case for real, $0.008): the model
  *still* classified it as Broken, independently computing "13.69% is
  6.31 points below the 20% threshold" -- the same disagreement with this
  project's own Weakened/Broken rule as before, but now demonstrably not
  label-parroting. A genuine, if minor, bonus finding: this run's
  `human_review_recommended` came back `False` despite the model calling
  the reason "Broken" -- an internal inconsistency baseline2 has that the
  agent's structured output doesn't. (At the time this was written the
  5-company subset hadn't been re-run with the fixed baseline2 yet --
  since superseded by the full 45-case experiment further down, which
  used the corrected version throughout.)
- ~~Add a stratified human-verified subset~~ **Done and scaled past the
  target, `build_primary_source_verification_set.py` -> 352 entries, free.**
  Started at 49 (latest quarter only), then extended to walk up to 8
  historical quarters per (ticker, reason_key) -- clears the ~100-200 case
  target. A curated 61-case diverse subset of it is published as a
  browsable Artifact (`build_review_sample.py` +
  `render_review_packet.py`) for an actual human reviewer to work through.
  See the dedicated sections below for the full results and the bugs
  found along the way. Scaling further from here means more companies
  (past the 15-ticker pilot set), which the same scripts already support.
- **`data/gold_set.json` is a cross-checked reference set, not ground
  truth, and should be called that precisely.** Both sides (XBRL 10-Q,
  8-K earnings release) come from the same company's own books -- real
  independent verification of *extraction*, but not of what a status
  *should* be. `data/primary_source_verification_set.json` (see below) adds a genuinely
  third source (the primary 10-Q/10-K filing text itself) on top of this.
- **The 50%-of-threshold Weakened/Broken boundary is an operational
  definition, not a finance principle** -- true, and should be written
  that way in any report ("the researcher set a 50% tolerance to grade
  severity for this prototype"), not implied to be derived from anywhere.
  Ran the sensitivity check this suggested (`sensitivity_analysis.py`,
  free, reuses the gold set): reclassifying all 312 scorable gold-set
  cases at 25%/50%/75% buffers instead of just the live 50% only flips
  **27/312 (8.7%)** at 25% and **23/312 (7.4%)** at 75% -- and every single
  flip is between Weakened and Broken, never touching Supported (193/312,
  unchanged at every buffer, since the buffer only reshapes the boundary
  *within* the not-Supported region). Real evidence the rule is reasonably
  robust to the exact buffer chosen, not just an assumption -- worth citing
  this number rather than the sensitivity check being purely hypothetical.
- The rule-based planner doesn't call `get_filing_context` -- only the LLM
  planner does, deliberately (keeps `run_rule_based` a simple/blunt
  baseline to compare the LLM against). Worth stating explicitly if asked
  why the comparison isn't symmetric.
- ~~Full baseline experiment, scored against a reference set instead of the
  pipeline's own output~~ **Done -- see the dedicated section above.**
  39/45 scorable cases, all 4 approaches, $1.365.
- ~~Run-to-run consistency not measured~~ **Done -- see the dedicated
  section above.** 63 calls, $2.836. Status 100% stable, human-review
  verdict 97.9% stable (2 real disagreements on PEP/JNJ), tool-selection
  process only 71.4% stable -- the investigation path varies more than
  its outcome.
- Oracle's debt tag gap, NVIDIA's fiscal-calendar-labeled earnings
  releases (0/25 parsed -- "Q1 FY27" instead of "Three Months Ended
  <date>"), the Oracle FY-tagged-as-quarter data-quality issue (a
  plausibility check like ">2x the median of adjacent quarters" could
  catch it), and uneven gold-set coverage (COST/JNJ/PEP produced zero
  dual-sourced entries; GOOGL's debt and PG's margin have unresolved
  disagreement) are all still open, lower-priority per-company/per-filer
  edge cases -- see the sections above where each was found for detail.
