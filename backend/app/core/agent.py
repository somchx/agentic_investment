"""Agent orchestration layer: the "Reason -> pick tool -> observe -> pick
next tool -> decide if evidence is sufficient" loop from PROPOSAL.md
section 4, built on top of the tools.py tool layer.

Two execution paths:

- `run_rule_based(ticker)` -- a deterministic stand-in planner. No LLM
  involved: it always checks a reason's status first, and only calls the
  earnings-release conflict tool when the status looks uncertain (Weakened,
  Broken, or Not enough data, or when the reason evaluation itself already
  flagged conflicting evidence). This is fully testable without any
  external API, and every branch below has actually been exercised against
  live SEC data in this session (see README.md).

- `run_with_llm(ticker)` -- the real target architecture: Claude decides
  which tool to call and when, via the Anthropic Messages API's tool-use
  feature, using the same TOOL_SPECS/tool functions as the rule-based path.
  Calls the API directly with `requests` rather than the `anthropic` SDK --
  the SDK's bundled HTTP client hit a response-decompression bug in this
  environment (`Decompressor.decompress() got an unexpected keyword
  argument 'output_buffer_limit'`, from a mismatched httpx2/h11 install);
  a raw POST to /v1/messages with the same payload worked fine, so that's
  what this uses. Requires ANTHROPIC_API_KEY (loaded from .env if present).

Per PROPOSAL.md's explicit guidance, this project does not build its own
agent runtime/planner framework -- run_with_llm is a thin loop over the
Anthropic Messages API's tool-use feature, not a custom framework.
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone

import requests
from dotenv import load_dotenv

from investigation_state import (
    InvestigationState,
    assess_debate_case_sufficiency,
    assess_sufficiency,
    assess_thesis_sufficiency,
)
from sec_client import KNOWN_CIKS, SecDataUnavailableError, UnsupportedTickerError, is_supported_ticker
from tools import (
    FINALIZE_DEBATE_CASE_TOOL,
    FINALIZE_REPORT_TOOL,
    FINALIZE_THESIS_REVIEW_TOOL,
    REASON_DEFS,
    THESIS_ATTACK_TOOL_SPECS,
    TOOL_SPECS,
    WEB_SEARCH_TOOL,
    calculate_metric,
    check_reason_status,
    evaluate_frozen_reason,
    get_filing_context,
    get_secondary_evidence,
)

load_dotenv()

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"

UNCERTAIN_STATUSES = {"Weakened", "Broken", "Not enough data"}


def run_rule_based(ticker: str) -> dict:
    """Deterministic planner: check every Phase 1 reason for `ticker`, and
    for any reason whose status is uncertain (or whose own evaluation
    already surfaced conflicting evidence), pull a second, independently-
    sourced number (the earnings-release check) before concluding.

    Returns a structured report mirroring the "My reasons for investing"
    style output from the proposal, including which reasons need human
    review and why.
    """
    trace = []
    reason_reports = []

    for reason_key in REASON_DEFS:
        trace.append(f"check_reason_status(ticker={ticker!r}, reason_key={reason_key!r})")
        result = check_reason_status(ticker, reason_key)
        if "error" in result:
            reason_reports.append({"reason_key": reason_key, "error": result["error"]})
            continue

        needs_more_evidence = (
            result["status"] in UNCERTAIN_STATUSES or bool(result["conflicting_evidence"])
        )
        release_check = None
        human_review = False
        review_reasons = []

        if needs_more_evidence:
            trace.append(
                f"  -> status={result['status']!r} looks uncertain, "
                f"calling get_secondary_evidence(ticker={ticker!r}, reason_key={reason_key!r})"
            )
            release_check = get_secondary_evidence(ticker, reason_key)

            if result["conflicting_evidence"]:
                review_reasons.append(
                    f"{len(result['conflicting_evidence'])} earlier-filed version(s) of the "
                    "underlying figure disagreed with the value used -- a data source conflict, "
                    "not just a borderline number."
                )
            if result["status"] == "Not enough data":
                review_reasons.append("insufficient filed data to evaluate this reason at all.")
            elif result["status"] in ("Weakened", "Broken"):
                review_reasons.append(
                    f"reason status is {result['status']}, below the required threshold."
                )
            if release_check and release_check.get("checked") and release_check.get("conflict"):
                review_reasons.append(
                    "the latest earnings-release figure disagrees with the filed 10-Q/10-K value."
                )

            human_review = bool(review_reasons)

        reason_reports.append({
            "reason_key": reason_key,
            "reason": result["reason"],
            "status": result["status"],
            "computed_value": result["computed_value"],
            "as_of": result["as_of"],
            "explanation": result["explanation"],
            "conflicting_evidence": result["conflicting_evidence"],
            "earnings_release_check": release_check,
            "human_review_recommended": human_review,
            "human_review_reasons": review_reasons,
        })

    return {"ticker": ticker, "trace": trace, "reasons": reason_reports}


def print_report(report: dict) -> None:
    print(f"\n{report['ticker']}")
    print("Agent trace:")
    for line in report["trace"]:
        print(f"  {line}")
    print()
    for r in report["reasons"]:
        if "error" in r:
            print(f"  [{r['reason_key']}] ERROR: {r['error']}")
            continue
        value_str = f"({r['computed_value']:+.1%})" if r["computed_value"] is not None else ""
        print(f"  [{r['reason_key']}] {r['status']:<16} {r['reason']} {value_str}")
        if r["human_review_recommended"]:
            print("      Human review: RECOMMENDED")
            for why in r["human_review_reasons"]:
                print(f"        - {why}")
            if r["earnings_release_check"] and r["earnings_release_check"].get("checked"):
                erc = r["earnings_release_check"]
                print(
                    f"      Earnings-release cross-check: release=${erc['earnings_release_value']:,.0f} "
                    f"vs filed=${erc['filed_value']:,.0f} (diff={erc['diff_pct']:.2%})"
                )
    print()


class Planner:
    """Investigation Agent component: analyzes the current goal & context
    (the running `messages` transcript) and asks Claude to determine the
    next action -- either a tool call or a `finalize_report` call. Owns
    nothing but the HTTP call itself; it never decides whether a proposed
    finalize is *accepted* (that's the Evidence Assessor's job) or whether
    to keep looping (the Loop Controller's job).
    """

    def __init__(self, api_key: str, model: str, tools: list[dict]):
        self.headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        self.model = model
        self.tools = tools

    def decide(self, messages: list[dict]) -> dict:
        """Sends the transcript to Claude and returns the raw API payload
        (content blocks + usage) -- the "prompt + context -> tool result /
        LLM response" step in the component diagram."""
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers=self.headers,
            json={
                "model": self.model,
                "max_tokens": 2048,
                "temperature": 0,  # fact-grounded classification, not creative generation
                "tools": self.tools,
                "messages": messages,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()


class ToolExecutor:
    """Investigation Agent component: executes whichever tool call(s) the
    Planner proposed, against the plain-Python functions in tools.py, and
    records each call into the Working State (InvestigationState). Schema
    validation and parsing are already handled by tools.py's own functions
    (each returns a plain dict or an {"error": ...} dict) -- this class's
    job is dispatch + state-recording, not re-validating their output.

    Also owns enforcing the single `analysis_date` for the whole
    investigation (Code Audit Session 4 follow-up, item 2): every
    point-in-time tool call gets `as_of` overwritten to this one fixed
    value before dispatch, regardless of what the LLM did or didn't pass --
    the model is never allowed to pick or drift the analysis date mid
    investigation.
    """

    # Every one of these tools accepts an `as_of` kwarg (point-in-time
    # evaluation) -- see tools.py. Tools not in this set (none currently)
    # would be dispatched without the override.
    POINT_IN_TIME_TOOLS = {
        "check_reason_status", "calculate_metric", "get_secondary_evidence", "get_filing_context",
    }

    DISPATCH = {
        "check_reason_status": lambda **kw: check_reason_status(**kw),
        "calculate_metric": lambda **kw: calculate_metric(**kw),
        "get_secondary_evidence": lambda **kw: get_secondary_evidence(**kw),
        "get_filing_context": lambda **kw: get_filing_context(**kw),
    }

    def __init__(self, analysis_date: str):
        self.analysis_date = analysis_date

    def execute(
        self, tool_uses: list[dict], state: InvestigationState, trace: list[str], verbose: bool = False
    ) -> list[dict]:
        tool_results = []
        for call in tool_uses:
            call_input = dict(call["input"])
            if call["name"] in self.POINT_IN_TIME_TOOLS:
                call_input["as_of"] = self.analysis_date
            trace.append(f"LLM called {call['name']}({call_input})")
            if verbose:
                print(trace[-1])
            # tools.py's own functions return a plain {"error": ...} dict for
            # anticipated failures (unknown reason_key, no data for a
            # metric) -- assess_sufficiency already knows how to reject a
            # finalize off of those. Genuinely unexpected failures raise
            # instead, and are classified here (Code Audit Session 4
            # follow-up, item 3) rather than stringified wholesale into the
            # agent's context:
            #  - SecDataUnavailableError (SEC itself unreachable, nothing
            #    cached) is NOT a fact about the company -- it must not be
            #    interpreted as "no evidence" or folded into a completed
            #    report, so it re-raises and aborts the whole investigation;
            #    the API layer turns this into an explicit 503.
            #  - UnsupportedTickerError is defense-in-depth (the ticker
            #    should already have been rejected before an LLM call was
            #    ever made -- see api_investigate) but is still classified
            #    distinctly rather than read as missing evidence.
            #  - Anything else unexpected is logged with full detail
            #    server-side (never sent to the LLM/agent) and surfaced to
            #    the gate as a generic TOOL_UNAVAILABLE, so a real bug still
            #    can't be finalized over silently.
            try:
                result = self.DISPATCH[call["name"]](**call_input)
            except SecDataUnavailableError:
                raise
            except UnsupportedTickerError as e:
                logger.warning("Unsupported ticker mid-investigation in %s(%s): %s", call["name"], call_input, e)
                result = {"error_code": "INVALID_TICKER", "error": "This ticker is not supported by this system."}
            except Exception as e:  # noqa: BLE001 -- any other tool failure must reach the gate, not crash past it
                logger.error("Unexpected tool failure in %s(%s): %s", call["name"], call_input, e, exc_info=True)
                result = {
                    "error_code": "TOOL_UNAVAILABLE",
                    "error": "An unexpected error occurred while gathering evidence for this tool call.",
                }
            state.record(call["name"], call_input, result)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": call["id"],
                "content": json.dumps(result),
            })
        return tool_results


class LoopController:
    """Investigation Agent component: owns the stop conditions -- the max
    iteration cap, and the separate cap on how many times the Evidence
    Assessor may reject a finalize_report call before the loop gives up on
    the assessor specifically and accepts the agent's answer anyway. Pure
    bookkeeping; it doesn't call the LLM or execute tools itself.
    """

    def __init__(self, max_iterations: int = 10, max_rejections: int = 2):
        self.max_iterations = max_iterations
        self.max_rejections = max_rejections
        self.rejection_count = 0

    def register_rejection(self) -> bool:
        """Records one assessor rejection. Returns True if the caller should
        push the agent to investigate further, False if the rejection cap is
        used up and the answer should be accepted as-is."""
        if self.rejection_count < self.max_rejections:
            self.rejection_count += 1
            return True
        return False


class Finalizer:
    """Investigation Agent component: turns an accepted finalize_report call
    (or a loop-cap exhaustion) into the structured report this module
    returns to its callers -- never decides sufficiency itself, that's
    already been settled by the Evidence Assessor / Loop Controller before
    either of these methods is called."""

    @staticmethod
    def build_report(ticker: str, trace: list[str], reasons: list[dict], gaps: list[str], usage: dict) -> dict:
        return {
            "ticker": ticker,
            "trace": trace,
            "reasons": reasons,
            "assessor_gaps": gaps,
            "escalated": False,
            "usage": usage,
        }

    @staticmethod
    def build_gap_escalation(
        ticker: str, trace: list[str], proposed_reasons: list[dict], gaps: list[str], usage: dict,
    ) -> dict:
        """Session 3 audit item 1: the Evidence Assessor rejected
        finalize_report up to the rejection cap and gaps are STILL
        unresolved -- this must not come back as a clean, successful
        report (that was the bug: it previously did, with escalated=False
        and the unresolved gaps only visible if a caller happened to check
        assessor_gaps). `reasons` is empty like build_escalation's -- what
        Claude proposed is kept under `unresolved_proposal` for a human
        reviewer to look at, but never returned as an authoritative result.
        """
        return {
            "ticker": ticker,
            "trace": trace,
            "reasons": [],
            "assessor_gaps": gaps,
            "escalated": True,
            "escalation_reason": (
                "Evidence Assessor rejected finalize_report the maximum number of times "
                f"and evidence gaps remained unresolved: {gaps}"
            ),
            "unresolved_proposal": proposed_reasons,
            "usage": usage,
        }

    @staticmethod
    def build_escalation(ticker: str, trace: list[str], state: InvestigationState, max_iterations: int, usage: dict) -> dict:
        checked_reason_keys = sorted({
            c["input"].get("reason_key") for c in state.tool_calls
            if c["name"] == "check_reason_status" and c["input"].get("reason_key")
        })
        return {
            "ticker": ticker,
            "trace": trace,
            "reasons": [],
            "assessor_gaps": [],
            "escalated": True,
            "escalation_reason": (
                f"Exceeded the tool-call loop cap ({max_iterations} iterations) without reaching "
                f"finalize_report. Reasons checked before giving up: {checked_reason_keys or 'none'}."
            ),
            "usage": usage,
        }


def language_instruction(language: str | None) -> str:
    """Appended to a run's opening prompt so the investor reads the free text
    in their UI language. Enum fields stay in English: the code (status
    badges, the Evidence Gate, stored history) matches on those exact values.
    None/"en" adds nothing, so CLI and experiment runs are unchanged."""
    if language != "th":
        return ""
    return (
        "\n\nWrite every free-text field you produce (rationale, counter_evidence, "
        "key_points, strongest_evidence, rebuttals, escalation reasons) in Thai. Keep enum "
        "values such as status, thesis_status and confidence exactly as the tool schema "
        "specifies, in English, and keep tickers, XBRL tag names, numbers and dates as-is."
    )

def run_with_llm(
    ticker: str, analysis_date: str | None = None, verbose: bool = False, language: str | None = None,
) -> dict:
    """The real target: Claude chooses which tool to call, in a loop, using
    TOOL_SPECS, via a direct call to the Messages API (see module docstring
    for why this bypasses the `anthropic` SDK).

    Orchestrates the 5 Investigation Agent components from the design
    diagram: Planner (decide next action) -> Evidence Assessor
    (assess_sufficiency, in investigation_state.py) -> Tool Executor
    (execute) -> Loop Controller (register_rejection / iteration cap) ->
    Finalizer (build_report / build_escalation). Working State is
    `InvestigationState`, also in investigation_state.py.

    `analysis_date` is the ONE point-in-time date for this entire
    investigation (Code Audit Session 4 follow-up, item 2) -- it defaults
    to today (a live investigation) but, once fixed here, is force-injected
    into every point-in-time tool call by ToolExecutor regardless of
    whatever `as_of` (if anything) the LLM itself tries to pass. The model
    never gets to pick or drift the analysis date mid-investigation.
    """
    # Cheapest possible rejection: an unsupported ticker never needs to
    # reach the LLM at all, let alone cost an API call (Code Audit Session 4
    # follow-up, item 1) -- distinct from "valid company, no evidence found"
    # (which legitimately does need investigation, see EVIDENCE_NOT_FOUND)
    # and from "SEC is down" (SecDataUnavailableError, mid-investigation).
    if not is_supported_ticker(ticker):
        raise UnsupportedTickerError(
            f"'{ticker}' is not one of this system's supported tickers: {sorted(KNOWN_CIKS)}"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "run_with_llm requires ANTHROPIC_API_KEY to be set (e.g. in a .env file). "
            "Use run_rule_based() instead if no key is available."
        )

    today = datetime.now(timezone.utc).date().isoformat()
    is_historical = analysis_date is not None and analysis_date < today
    if analysis_date is None:
        analysis_date = today

    historical_notice = ""
    if is_historical:
        # web_search returns today's information and has no way to verify a
        # result's publish date, so it's excluded from `all_tools` entirely
        # for a historical investigation -- offering it and merely warning
        # against its use (the live-investigation approach) isn't good
        # enough once look-ahead bias is the whole point being guarded
        # against. Even so, this can only filter the TOOLS' evidence by
        # date; it cannot strip whatever the model already knows from
        # training about this company's events after `analysis_date` --
        # that residual risk is a known, documented limitation, not
        # something code can close, so the model is told about it plainly.
        historical_notice = (
            f"\n\nThis is a POINT-IN-TIME investigation as of {analysis_date} -- not today. "
            "All tool results are already restricted to filings at or before this date, and "
            "web_search has been disabled for this investigation because it cannot verify a "
            "source's publish date and could leak information not knowable as of that date. "
            "Be aware, however, that this cannot fully rule out look-ahead bias: your own "
            "training may include general knowledge of this company's events after "
            f"{analysis_date}. Do not let anything you know about events after {analysis_date} "
            "influence your conclusions -- rely only on the evidence the tools return."
        )

    messages = [{
        "role": "user",
        "content": (
            f"Check every investment reason for {ticker} using the available tools. "
            "For any reason that looks uncertain, gather a second source of evidence "
            "before concluding. For any reason that comes back Broken (or otherwise "
            "looks severe), also call get_filing_context to read the company's own "
            "explanation before concluding -- a threshold breach alone doesn't tell "
            "you whether it's a real event, a restatement, or a data/tag mismatch, "
            "and the rationale you write should reflect what you actually found, not "
            "just the number."
            + ("" if is_historical else (
                " A web_search tool is also available, but it is STRICTLY for "
                "qualitative context to enrich the rationale text (e.g. is there a "
                "known reason a metric moved) -- it returns today's information, not "
                "what was knowable as of the analysis date, so it must NEVER be used "
                "to decide a reason's Supported/Weakened/Broken status. That status "
                "must come only from check_reason_status / calculate_metric's "
                "point-in-time SEC data."
            ))
            + " Once you're done, call finalize_report exactly once with a "
            "structured entry for every reason you checked -- that call is your final "
            "answer, not a free-text summary."
            + historical_notice
        ),
    }]
    messages[0]["content"] += language_instruction(language)
    trace: list[str] = []
    total_input_tokens = 0
    total_output_tokens = 0
    all_tools = list(TOOL_SPECS)
    if not is_historical:
        all_tools.append(WEB_SEARCH_TOOL)
    all_tools.append(FINALIZE_REPORT_TOOL)

    state = InvestigationState(ticker=ticker)
    planner = Planner(api_key, ANTHROPIC_MODEL, all_tools)
    tool_executor = ToolExecutor(analysis_date)
    loop_controller = LoopController(max_iterations=10, max_rejections=2)

    for _ in range(loop_controller.max_iterations):
        payload = planner.decide(messages)
        content = payload["content"]
        usage = payload.get("usage", {})
        total_input_tokens += usage.get("input_tokens", 0)
        total_output_tokens += usage.get("output_tokens", 0)
        messages.append({"role": "assistant", "content": content})

        # web_search is server-executed by Anthropic (never dispatched by
        # our code, see tools.WEB_SEARCH_TOOL), but its use is logged here
        # for auditability -- a reviewer checking why a rationale mentions
        # something outside the filed numbers should be able to see that a
        # search happened and what query was run.
        for block in content:
            if block.get("type") == "server_tool_use" and block.get("name") == "web_search":
                trace.append(f"LLM called web_search({block['input']})")
                if verbose:
                    print(trace[-1])

        tool_uses = [b for b in content if b["type"] == "tool_use"]
        finalize_call = next((c for c in tool_uses if c["name"] == "finalize_report"), None)
        usage_totals = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens}

        if finalize_call:
            # Evidence Assessor: is what's been gathered sufficient to finalize?
            problems = assess_sufficiency(state, finalize_call["input"]["reasons"])
            if problems and loop_controller.register_rejection():
                trace.append(f"finalize_report rejected by assess_sufficiency: {problems}")
                # Every tool_use in the assistant turn we just appended --
                # finalize_report included -- needs a matching tool_result in
                # the next message, or the next Messages API call is a flat
                # 400 ("tool_use ids were found without tool_result blocks"),
                # which crashes the loop entirely before the model ever gets
                # a chance to fix its answer. A plain-text nudge alone (the
                # original approach) omits finalize_report's own tool_result
                # and always hit this once a real rejection actually
                # happened against the live API -- previously only exercised
                # via mocks, which don't enforce this. Any other tool calls
                # made in the same turn as finalize_report are executed
                # normally so their ids get a real result too.
                other_calls = [c for c in tool_uses if c is not finalize_call]
                rejection_results = tool_executor.execute(other_calls, state, trace, verbose=verbose)
                rejection_results.append({
                    "type": "tool_result",
                    "tool_use_id": finalize_call["id"],
                    "content": (
                        "This finalize_report call was rejected -- the evidence gathered "
                        "so far doesn't support finalizing these reasons yet:\n"
                        + "\n".join(f"- {p}" for p in problems)
                        + "\nInvestigate further (call the relevant tool(s)) and then call "
                        "finalize_report again."
                    ),
                    "is_error": True,
                })
                messages.append({"role": "user", "content": rejection_results})
                continue
            if problems:
                # Rejection budget exhausted and gaps are still unresolved --
                # this must escalate, not come back as a clean report (Code
                # Audit Session 3, item 1: this previously fell through to
                # build_report with escalated=False).
                trace.append(
                    f"finalize_report rejected {loop_controller.max_rejections} time(s) and "
                    f"gaps remained unresolved -- escalating instead of accepting: {problems}"
                )
                return _with_tool_calls(Finalizer.build_gap_escalation(
                    ticker, trace, finalize_call["input"]["reasons"], problems, usage_totals
                ), state)
            return _with_tool_calls(Finalizer.build_report(
                ticker, trace, finalize_call["input"]["reasons"], [], usage_totals
            ), state)

        if not tool_uses:
            # Model produced text instead of calling finalize_report -- nudge it
            # rather than accepting an unstructured answer.
            messages.append({
                "role": "user",
                "content": "Please call finalize_report with your structured conclusion now.",
            })
            continue

        tool_results = tool_executor.execute(tool_uses, state, trace, verbose=verbose)
        messages.append({"role": "user", "content": tool_results})

    # Loop cap reached without ever calling finalize_report. "The agent
    # couldn't reach a conclusion in a bounded number of steps" is exactly
    # the case the Human Escalation path exists for, not an error state.
    return _with_tool_calls(Finalizer.build_escalation(
        ticker, trace, state, loop_controller.max_iterations,
        {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
    ), state)


def _with_tool_calls(result: dict, state: InvestigationState) -> dict:
    """Attach the structured record of every tool call the run made ({name,
    input, result}) so the UI can show the Evidence Trail. Read-only: the
    record already exists in InvestigationState for the Evidence Assessor;
    this changes nothing about what the agent does or concludes."""
    result["tool_calls"] = list(state.tool_calls)
    return result


def run_thesis_attack(
    ticker: str, reason_key: str, frozen_def: dict, purchase_date: str, thesis: str, verbose: bool = False,
    language: str | None = None,
) -> dict:
    """Decision Journal / "Attack the Thesis" -- extends Contribution 2
    (Evidence Conflict-Aware Reasoning) from "does this number conflict
    with that number" to "does any evidence conflict with the investor's
    own stated reason for buying." Purchase Snapshot already freezes WHAT
    rule justified the buy (Code Audit Session 3, item 2); this is the
    missing WHY -- a free-text thesis, frozen alongside it -- and a
    dedicated adversarial pass that actively tries to find evidence AGAINST
    that thesis, instead of only re-confirming the frozen rule's number.

    Every tool here is a zero-argument closure over this one ticker,
    reason, and (purchase_date-pinned) point in time -- the model cannot
    target a different position or drift the analysis date, the same
    orchestrator-enforced discipline as run_with_llm's `analysis_date`
    (Code Audit Session 5 follow-up, item 2).
    """
    if not is_supported_ticker(ticker):
        raise UnsupportedTickerError(
            f"'{ticker}' is not one of this system's supported tickers: {sorted(KNOWN_CIKS)}"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "run_thesis_attack requires ANTHROPIC_API_KEY to be set (e.g. in a .env file)."
        )

    def _dispatch_frozen_status(**_kw) -> dict:
        return evaluate_frozen_reason(ticker, frozen_def, as_of=purchase_date)

    def _dispatch_secondary_evidence(**_kw) -> dict:
        return get_secondary_evidence(ticker, reason_key, as_of=purchase_date)

    def _dispatch_filing_context(**_kw) -> dict:
        return get_filing_context(ticker, reason_key, as_of=purchase_date)

    dispatch = {
        "get_frozen_reason_status": _dispatch_frozen_status,
        "get_secondary_evidence": _dispatch_secondary_evidence,
        "get_filing_context": _dispatch_filing_context,
    }

    def _execute(call: dict) -> dict:
        try:
            return dispatch[call["name"]]()
        except SecDataUnavailableError:
            raise
        except UnsupportedTickerError as e:
            logger.warning("Unsupported ticker mid-thesis-attack in %s: %s", call["name"], e)
            return {"error_code": "INVALID_TICKER", "error": "This ticker is not supported by this system."}
        except Exception as e:  # noqa: BLE001 -- any tool failure must reach the gate, not crash past it
            logger.error("Unexpected tool failure in %s for thesis attack: %s", call["name"], e, exc_info=True)
            return {
                "error_code": "TOOL_UNAVAILABLE",
                "error": "An unexpected error occurred while gathering evidence for this tool call.",
            }

    all_tools = THESIS_ATTACK_TOOL_SPECS + [FINALIZE_THESIS_REVIEW_TOOL]
    messages = [{
        "role": "user",
        "content": (
            f"An investor bought {ticker} on {purchase_date} because: \"{thesis}\"\n\n"
            "Your job is NOT to confirm this thesis. Actively try to find the strongest "
            f"evidence AGAINST it still holding. Every tool here is locked to {purchase_date}, "
            "the point in time the thesis was formed -- you cannot accidentally use "
            "information from after the purchase.\n\n"
            "Call get_frozen_reason_status first to see the exact baseline the thesis was "
            "based on, then use get_secondary_evidence and get_filing_context to dig for "
            "anything that contradicts or weakens it: a data conflict between sources, a "
            "worrying trend in the company's own narrative, anything the frozen number "
            "alone would not show. Report honestly if a genuine search turns up nothing -- "
            "do not manufacture doubt that isn't there; `counter_evidence` must reflect "
            "what you actually found, not what would sound appropriately cautious. Call "
            "finalize_thesis_review exactly once with your conclusion."
        ),
    }]
    messages[0]["content"] += language_instruction(language)
    trace: list[str] = []
    total_input_tokens = 0
    total_output_tokens = 0
    state = InvestigationState(ticker=ticker)
    planner = Planner(api_key, ANTHROPIC_MODEL, all_tools)
    loop_controller = LoopController(max_iterations=8, max_rejections=2)

    for _ in range(loop_controller.max_iterations):
        payload = planner.decide(messages)
        content = payload["content"]
        usage = payload.get("usage", {})
        total_input_tokens += usage.get("input_tokens", 0)
        total_output_tokens += usage.get("output_tokens", 0)
        messages.append({"role": "assistant", "content": content})

        tool_uses = [b for b in content if b["type"] == "tool_use"]
        finalize_call = next((c for c in tool_uses if c["name"] == "finalize_thesis_review"), None)
        usage_totals = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens}

        if finalize_call:
            problems = assess_thesis_sufficiency(state, reason_key, finalize_call["input"])
            if problems and loop_controller.register_rejection():
                trace.append(f"finalize_thesis_review rejected by assess_thesis_sufficiency: {problems}")
                # Same schema discipline as run_with_llm's rejection path (Code
                # Audit Session 4): every tool_use in this turn, including
                # finalize_thesis_review itself, needs a matching tool_result.
                other_calls = [c for c in tool_uses if c is not finalize_call]
                rejection_results = []
                for call in other_calls:
                    call_input = {**call["input"], "reason_key": reason_key}
                    trace.append(f"LLM called {call['name']}({call_input})")
                    if verbose:
                        print(trace[-1])
                    result = _execute(call)
                    state.record(call["name"], call_input, result)
                    rejection_results.append({
                        "type": "tool_result", "tool_use_id": call["id"], "content": json.dumps(result),
                    })
                rejection_results.append({
                    "type": "tool_result",
                    "tool_use_id": finalize_call["id"],
                    "content": (
                        "This finalize_thesis_review call was rejected -- the search so far "
                        "doesn't support this verdict yet:\n"
                        + "\n".join(f"- {p}" for p in problems)
                        + "\nInvestigate further and call finalize_thesis_review again."
                    ),
                    "is_error": True,
                })
                messages.append({"role": "user", "content": rejection_results})
                continue
            if problems:
                trace.append(
                    f"finalize_thesis_review rejected {loop_controller.max_rejections} time(s) and gaps "
                    f"remained unresolved -- escalating instead of accepting: {problems}"
                )
                return {
                    "ticker": ticker, "reason_key": reason_key, "thesis": thesis, "purchase_date": purchase_date,
                    "trace": trace, "escalated": True,
                    "escalation_reason": (
                        "Evidence Assessor rejected finalize_thesis_review the maximum number of "
                        f"times and gaps remained unresolved: {problems}"
                    ),
                    "unresolved_verdict": finalize_call["input"], "usage": usage_totals,
                }
            return {
                "ticker": ticker, "reason_key": reason_key, "thesis": thesis, "purchase_date": purchase_date,
                "trace": trace, "escalated": False, **finalize_call["input"], "usage": usage_totals,
            }

        if not tool_uses:
            messages.append({
                "role": "user",
                "content": "Please call finalize_thesis_review with your structured conclusion now.",
            })
            continue

        tool_results = []
        for call in tool_uses:
            call_input = {**call["input"], "reason_key": reason_key}
            trace.append(f"LLM called {call['name']}({call_input})")
            if verbose:
                print(trace[-1])
            result = _execute(call)
            state.record(call["name"], call_input, result)
            tool_results.append({"type": "tool_result", "tool_use_id": call["id"], "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})

    return {
        "ticker": ticker, "reason_key": reason_key, "thesis": thesis, "purchase_date": purchase_date,
        "trace": trace, "escalated": True,
        "escalation_reason": (
            f"Exceeded the tool-call loop cap ({loop_controller.max_iterations} iterations) "
            "without reaching finalize_thesis_review."
        ),
        "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
    }


def run_bull_bear_debate(
    ticker: str, reason_key: str, frozen_def: dict, purchase_date: str, thesis: str, verbose: bool = False,
    language: str | None = None,
) -> dict:
    """Mr. Bull / Mr. Bear Cross-Debate -- a more structured sibling of
    run_thesis_attack. Instead of one agent asked to be adversarial toward
    its own conclusion, two separate roles each build an evidence-grounded
    case (Bull: strongest case the thesis holds; Bear: strongest case it
    doesn't), then each writes one rebuttal of the other's case using only
    evidence already on the table (no new tool calls in the rebuttal step
    -- it's reasoning over the gathered evidence, not another search).

    Deliberately returns both sides' full cases and rebuttals rather than
    collapsing them into a single verdict: per this project's own
    "AI should not decide buy/sell" stance (PROPOSAL.md, Risk Assessment),
    the investor reading both cases is the one who weighs them, not the
    agent. run_thesis_attack's single verdict (Still Holds/Weakened/
    Broken) remains the quicker, cheaper option when a verdict is wanted;
    this is the more expensive, deliberately inconclusive-by-design option
    for a harder look.

    Tools are the same zero-argument, purchase-date-locked set as
    run_thesis_attack (get_frozen_reason_status, get_secondary_evidence,
    get_filing_context) -- neither side can target a different position or
    drift the analysis date.
    """
    if not is_supported_ticker(ticker):
        raise UnsupportedTickerError(
            f"'{ticker}' is not one of this system's supported tickers: {sorted(KNOWN_CIKS)}"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "run_bull_bear_debate requires ANTHROPIC_API_KEY to be set (e.g. in a .env file)."
        )

    def _dispatch_frozen_status(**_kw) -> dict:
        return evaluate_frozen_reason(ticker, frozen_def, as_of=purchase_date)

    def _dispatch_secondary_evidence(**_kw) -> dict:
        return get_secondary_evidence(ticker, reason_key, as_of=purchase_date)

    def _dispatch_filing_context(**_kw) -> dict:
        return get_filing_context(ticker, reason_key, as_of=purchase_date)

    dispatch = {
        "get_frozen_reason_status": _dispatch_frozen_status,
        "get_secondary_evidence": _dispatch_secondary_evidence,
        "get_filing_context": _dispatch_filing_context,
    }

    def _execute(call: dict) -> dict:
        try:
            return dispatch[call["name"]]()
        except SecDataUnavailableError:
            raise
        except UnsupportedTickerError as e:
            logger.warning("Unsupported ticker mid-debate in %s: %s", call["name"], e)
            return {"error_code": "INVALID_TICKER", "error": "This ticker is not supported by this system."}
        except Exception as e:  # noqa: BLE001 -- any tool failure must reach the gate, not crash past it
            logger.error("Unexpected tool failure in %s during bull/bear debate: %s", call["name"], e, exc_info=True)
            return {
                "error_code": "TOOL_UNAVAILABLE",
                "error": "An unexpected error occurred while gathering evidence for this tool call.",
            }

    trace: list[str] = []
    total_input_tokens = 0
    total_output_tokens = 0
    case_planner = Planner(api_key, ANTHROPIC_MODEL, THESIS_ATTACK_TOOL_SPECS + [FINALIZE_DEBATE_CASE_TOOL])
    # Separate, tool-less Planner for the rebuttal step -- it must reason
    # over evidence already gathered, never call a tool to go dig for more
    # (that would turn "one rebuttal sentence" into another full search).
    rebuttal_planner = Planner(api_key, ANTHROPIC_MODEL, [])

    side_instructions = {
        "bull": (
            "Your role is Mr. Bull: build the strongest POSITIVE case for why this thesis "
            "still holds. Actively dig for confirming evidence and real reasons for "
            "conviction -- do not just restate the thesis back."
        ),
        "bear": (
            "Your role is Mr. Bear: build the strongest NEGATIVE case for why this thesis "
            "might be wrong. Actively dig for disconfirming evidence and real risks -- do "
            "not just list generic risk factors that would apply to any company."
        ),
    }

    def _build_case(side: str) -> dict:
        # Each side gets its own InvestigationState and local trace/usage
        # accumulators (instead of mutating the shared ones via `nonlocal`)
        # so the two sides -- run concurrently below via ThreadPoolExecutor,
        # since they're fully independent -- can't interleave their tool
        # calls into one shared history (that would let assess_debate_
        # case_sufficiency see the OTHER side's digging and wrongly think
        # this side did enough) or race on the same counters.
        state = InvestigationState(ticker=ticker)
        local_trace: list[str] = []
        local_input_tokens = 0
        local_output_tokens = 0
        messages = [{
            "role": "user",
            "content": (
                f"An investor bought {ticker} on {purchase_date} because: \"{thesis}\"\n\n"
                f"{side_instructions[side]}\n\n"
                f"Every tool here is locked to {purchase_date}, the point in time the thesis "
                "was formed -- you cannot accidentally use information from after the "
                "purchase. Call get_frozen_reason_status first for the baseline, then use "
                "get_secondary_evidence and get_filing_context to dig for real evidence "
                "supporting your assigned side. Call finalize_case exactly once with your "
                "structured case."
            ),
        }]
        messages[0]["content"] += language_instruction(language)
        def _done(case: dict) -> dict:
            return {
                "case": case, "trace": local_trace,
                "input_tokens": local_input_tokens, "output_tokens": local_output_tokens,
            }

        local_loop = LoopController(max_iterations=6, max_rejections=1)
        for _ in range(local_loop.max_iterations):
            payload = case_planner.decide(messages)
            content = payload["content"]
            usage = payload.get("usage", {})
            local_input_tokens += usage.get("input_tokens", 0)
            local_output_tokens += usage.get("output_tokens", 0)
            messages.append({"role": "assistant", "content": content})

            tool_uses = [b for b in content if b["type"] == "tool_use"]
            finalize_call = next((c for c in tool_uses if c["name"] == "finalize_case"), None)

            if finalize_call:
                problems = assess_debate_case_sufficiency(state, reason_key, side)
                if problems and local_loop.register_rejection():
                    local_trace.append(f"[{side}] finalize_case rejected by assess_debate_case_sufficiency: {problems}")
                    other_calls = [c for c in tool_uses if c is not finalize_call]
                    rejection_results = []
                    for call in other_calls:
                        call_input = {**call["input"], "reason_key": reason_key}
                        local_trace.append(f"[{side}] LLM called {call['name']}({call_input})")
                        if verbose:
                            print(local_trace[-1])
                        result = _execute(call)
                        state.record(call["name"], call_input, result)
                        rejection_results.append({
                            "type": "tool_result", "tool_use_id": call["id"], "content": json.dumps(result),
                        })
                    rejection_results.append({
                        "type": "tool_result",
                        "tool_use_id": finalize_call["id"],
                        "content": (
                            "This finalize_case call was rejected -- the digging so far doesn't "
                            "support a grounded case yet:\n" + "\n".join(f"- {p}" for p in problems)
                            + "\nInvestigate further and call finalize_case again."
                        ),
                        "is_error": True,
                    })
                    messages.append({"role": "user", "content": rejection_results})
                    continue
                if problems:
                    local_trace.append(
                        f"[{side}] finalize_case rejected {local_loop.max_rejections} time(s) and gaps "
                        f"remained unresolved -- escalating this side instead of accepting: {problems}"
                    )
                    return _done({
                        "side": side, "escalated": True,
                        "escalation_reason": f"Could not build a sufficiently evidence-grounded case: {problems}",
                    })
                return _done({"side": side, "escalated": False, **finalize_call["input"]})

            if not tool_uses:
                messages.append({
                    "role": "user",
                    "content": "Please call finalize_case with your structured conclusion now.",
                })
                continue

            tool_results = []
            for call in tool_uses:
                call_input = {**call["input"], "reason_key": reason_key}
                local_trace.append(f"[{side}] LLM called {call['name']}({call_input})")
                if verbose:
                    print(local_trace[-1])
                result = _execute(call)
                state.record(call["name"], call_input, result)
                tool_results.append({"type": "tool_result", "tool_use_id": call["id"], "content": json.dumps(result)})
            messages.append({"role": "user", "content": tool_results})

        local_trace.append(f"[{side}] exceeded the tool-call loop cap without reaching finalize_case")
        return _done({
            "side": side, "escalated": True,
            "escalation_reason": f"Exceeded the tool-call loop cap ({local_loop.max_iterations}) without reaching finalize_case.",
        })

    # Bull and bear build their cases completely independently (own
    # InvestigationState, own trace/usage accumulators -- see _build_case's
    # docstring comment) so they can run concurrently instead of one
    # waiting on the other; this is an I/O-bound wait on the Anthropic API,
    # not CPU work, so a thread per side is enough to roughly halve the
    # wall-clock time for no extra token cost.
    with ThreadPoolExecutor(max_workers=2) as pool:
        bear_future = pool.submit(_build_case, "bear")
        bull_future = pool.submit(_build_case, "bull")
        bear_result = bear_future.result()
        bull_result = bull_future.result()

    trace.extend(bear_result["trace"])
    trace.extend(bull_result["trace"])
    total_input_tokens += bear_result["input_tokens"] + bull_result["input_tokens"]
    total_output_tokens += bear_result["output_tokens"] + bull_result["output_tokens"]
    bear_case = bear_result["case"]
    bull_case = bull_result["case"]

    def _rebut(side: str, own_case: dict, opposing_case: dict) -> str:
        nonlocal total_input_tokens, total_output_tokens
        if own_case.get("escalated") or opposing_case.get("escalated"):
            return "(skipped -- one side could not build a sufficiently evidence-grounded case)"
        own_label, opponent_label = ("Bull", "Bear") if side == "bull" else ("Bear", "Bull")
        prompt = (
            f"You are Mr. {own_label}. Here is your own case on this thesis:\n"
            f"{json.dumps(own_case, indent=2)}\n\n"
            f"Here is Mr. {opponent_label}'s case on the same thesis:\n"
            f"{json.dumps(opposing_case, indent=2)}\n\n"
            f"In 2-4 sentences, rebut Mr. {opponent_label}'s strongest point using ONLY the "
            "evidence already presented above (yours or theirs) -- you have no tools here, "
            "do not invent new evidence. If their point genuinely has merit, concede it "
            "honestly rather than deflecting."
        )
        prompt += language_instruction(language)
        payload = rebuttal_planner.decide([{"role": "user", "content": prompt}])
        usage = payload.get("usage", {})
        total_input_tokens += usage.get("input_tokens", 0)
        total_output_tokens += usage.get("output_tokens", 0)
        text_blocks = [b.get("text", "") for b in payload["content"] if b.get("type") == "text"]
        return "\n".join(text_blocks).strip() or "(no rebuttal text returned)"

    bull_rebuttal = _rebut("bull", bull_case, bear_case)
    bear_rebuttal = _rebut("bear", bear_case, bull_case)

    return {
        "ticker": ticker, "reason_key": reason_key, "thesis": thesis, "purchase_date": purchase_date,
        "trace": trace,
        "bull_case": bull_case, "bear_case": bear_case,
        "bull_rebuttal": bull_rebuttal, "bear_rebuttal": bear_rebuttal,
        "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
    }


WEB_SEARCH_CAVEAT = (
    "A web_search tool is also available, but it is STRICTLY for qualitative context (e.g. is "
    "there a known reason a metric moved) -- it returns today's information, not what was "
    "knowable historically, so it must NEVER be used to state a Supported/Weakened/Broken "
    "status; that must come only from check_reason_status/calculate_metric."
)


def _chat_loop(
    system_prompt: str, question: str, history: list[dict] | None = None, language: str | None = None,
) -> dict:
    """Shared free-form Q&A tool-use loop behind answer_question (scoped to
    one company) and answer_portfolio_question (scoped to everything the
    user holds) -- distinct from run_with_llm's structured, forced-
    finalize_report loop (used for the deterministic-comparison research
    runs, not for answering an arbitrary user question). Stops as soon as
    Claude replies with plain text and no further tool calls -- there is no
    schema to satisfy, just an answer grounded in whatever tools it chose
    to use (each tool call still takes whichever `ticker` Claude passes it,
    so a portfolio-wide question can still drill into any one holding).

    `history` (optional) is this chat session's prior turns, each
    {"role": "user"|"assistant", "content": str} -- included so a
    follow-up question ("what about last quarter?") has context, without
    any server-side conversation storage: the frontend keeps the
    transcript and resends it each turn.
    """
    if language == "th":
        system_prompt += "\n\nReply to the user in Thai. Keep tickers, XBRL tag names, numbers and dates as-is."
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "answer_question requires ANTHROPIC_API_KEY to be set (e.g. in a .env file)."
        )

    dispatch = {
        "check_reason_status": lambda **kw: check_reason_status(**kw),
        "calculate_metric": lambda **kw: calculate_metric(**kw),
        "get_secondary_evidence": lambda **kw: get_secondary_evidence(**kw),
        "get_filing_context": lambda **kw: get_filing_context(**kw),
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    messages = [*(history or []), {"role": "user", "content": question}]
    trace = []
    tool_call_log: list[dict] = []
    total_input_tokens = 0
    total_output_tokens = 0
    all_tools = TOOL_SPECS + [WEB_SEARCH_TOOL]

    for _ in range(8):  # hard cap so a runaway loop can't spin forever
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers=headers,
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 1024,
                "temperature": 0,  # fact-grounded Q&A, not creative generation
                "system": system_prompt,
                "tools": all_tools,
                "messages": messages,
            },
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json()
        content = payload["content"]
        usage = payload.get("usage", {})
        total_input_tokens += usage.get("input_tokens", 0)
        total_output_tokens += usage.get("output_tokens", 0)
        messages.append({"role": "assistant", "content": content})

        for block in content:
            if block.get("type") == "server_tool_use" and block.get("name") == "web_search":
                trace.append(f"LLM called web_search({block['input']})")

        tool_uses = [b for b in content if b["type"] == "tool_use"]
        if not tool_uses:
            answer = "".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
            return {
                "answer": answer or "The agent did not return a text answer.",
                "tool_calls": tool_call_log,
                "cost_usd": total_input_tokens / 1e6 * 3.0 + total_output_tokens / 1e6 * 15.0,
            }

        tool_results = []
        for call in tool_uses:
            trace.append(f"LLM called {call['name']}({call['input']})")
            result = dispatch[call["name"]](**call["input"])
            tool_call_log.append({"name": call["name"], "arguments": call["input"], "result": result})
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": call["id"],
                "content": json.dumps(result),
            })
        messages.append({"role": "user", "content": tool_results})

    return {
        "answer": (
            "The agent used up its tool-call budget for this question without reaching a "
            "final answer -- try a more specific question, or ask again."
        ),
        "tool_calls": tool_call_log,
        "cost_usd": total_input_tokens / 1e6 * 3.0 + total_output_tokens / 1e6 * 15.0,
    }


def answer_question(
    ticker: str, question: str, history: list[dict] | None = None, language: str | None = None,
) -> dict:
    """Free-form Q&A about one company, for the web UI's chat-style "Ask the
    agent" feature, scoped to whichever ticker the user picked."""
    system_prompt = (
        f"You are answering a user's question about {ticker}, for an evidence-grounded "
        "investment reason tracker. Use the available tools to ground your answer in the "
        "company's actual filed SEC data -- check_reason_status and calculate_metric give "
        "point-in-time numbers, get_secondary_evidence and get_filing_context give "
        f"corroborating evidence and narrative context. {WEB_SEARCH_CAVEAT} Answer directly "
        "and concisely once you have what you need -- do not call a tool you don't need, and "
        "do not pad the answer with a structured report format unless the user actually asked "
        "for one."
    )
    return _chat_loop(system_prompt, question, history, language=language)


def answer_portfolio_question(
    portfolio_context: str,
    question: str,
    history: list[dict] | None = None,
    investor_profile_context: str | None = None,
    language: str | None = None,
) -> dict:
    """Free-form Q&A across everything the user holds -- "how's my portfolio
    doing, anything I should be worried about" style questions that aren't
    scoped to one company. `portfolio_context` is a plain-text summary of
    the user's current positions (ticker, quantity, the reason that
    justified each purchase, and whether it still holds) built by the API
    layer from db.list_purchases + tools.check_reason_status -- the same
    data GET /api/portfolio/summary already computes, just formatted as
    prose instead of JSON. Claude can still call check_reason_status /
    calculate_metric / etc. for any specific ticker mentioned in that
    context (or in the question) to dig deeper before answering.

    By default this is NOT a stock-picking tool -- it only describes what
    the evidence shows about positions the user already holds. If the user
    has filled in their own investor profile (`investor_profile_context`
    non-empty -- budget, target growth, horizon, risk tolerance, goals),
    that default is explicitly lifted: the user opted into suggestions, so
    Claude may name candidate tickers from the tracked universe (including
    ones not currently held) when asked what might suit them, as long as
    the suggestion is grounded in a real tool call (check_reason_status /
    calculate_metric), not speculation, and is framed as an evidence-based
    observation -- not formal financial advice.
    """
    if investor_profile_context:
        tracked = ", ".join(sorted(KNOWN_CIKS.keys()))
        system_prompt = (
            "You are answering a user's question about their investment portfolio, for an "
            "evidence-grounded investment reason tracker. Here is their current portfolio, "
            "including the reason that justified each purchase and whether that reason still "
            f"holds today:\n\n{portfolio_context}\n\n"
            "The user has also filled in their own investor profile:\n\n"
            f"{investor_profile_context}\n\n"
            "Because they've shared this profile, you may go beyond describing their current "
            "holdings: if asked for investments that suit them, you may suggest candidate "
            f"tickers from this tracked universe ({tracked}) -- including ones they don't "
            "currently hold -- weighing their budget, target growth, horizon, risk tolerance "
            "and goals. Every suggestion must be grounded in an actual tool call for that "
            "ticker (check_reason_status with revenue_growth/operating_margin/debt_growth, or "
            "calculate_metric) showing real supporting evidence -- never suggest a ticker you "
            "haven't checked, and never fabricate a number. State plainly that this is an "
            "evidence-based observation from the tracked data, not formal financial advice, "
            f"and that the user should still use their own judgment. {WEB_SEARCH_CAVEAT} Answer "
            "directly and concisely."
        )
    else:
        system_prompt = (
            "You are answering a user's question about their investment portfolio, for an "
            "evidence-grounded investment reason tracker. This is NOT a stock-picking or "
            "recommendation tool -- never suggest what to buy or sell; only describe what the "
            "evidence currently shows about what the user already holds. Here is their current "
            "portfolio, including the reason that justified each purchase and whether that reason "
            f"still holds today:\n\n{portfolio_context}\n\n"
            "Use the available tools (passing whichever ticker is relevant to the question) to "
            "check current reason status, computed metrics, secondary evidence, or filing context "
            f"for any holding the user asks about. {WEB_SEARCH_CAVEAT} Answer directly and "
            "concisely -- if asked which holdings look risky or concerning, base that only on "
            "reasons that are Weakened or Broken or no longer true, not on speculation."
        )
    return _chat_loop(system_prompt, question, history, language=language)


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    use_llm = "--llm" in args
    args = [a for a in args if a != "--llm"]
    ticker = args[0] if args else "AAPL"

    if use_llm:
        result = run_with_llm(ticker, verbose=True)
        print(f"\n{ticker} -- LLM agent trace:")
        for line in result["trace"]:
            print(f"  {line}")
        print()
        for r in result["reasons"]:
            print(f"  [{r['reason_key']}] {r['status']:<16} human_review={r['human_review_recommended']}")
            print(f"      {r['rationale']}")
        u = result["usage"]
        print(f"\n[usage] input_tokens={u['input_tokens']} output_tokens={u['output_tokens']}")
    else:
        print_report(run_rule_based(ticker))
