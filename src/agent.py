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
import os

import requests
from dotenv import load_dotenv

from investigation_state import InvestigationState, assess_sufficiency
from tools import (
    FINALIZE_REPORT_TOOL,
    REASON_DEFS,
    TOOL_SPECS,
    WEB_SEARCH_TOOL,
    calculate_metric,
    check_reason_status,
    get_filing_context,
    get_secondary_evidence,
)

load_dotenv()

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


def run_with_llm(ticker: str, verbose: bool = False) -> dict:
    """The real target: Claude chooses which tool to call, in a loop, using
    TOOL_SPECS, via a direct call to the Messages API (see module docstring
    for why this bypasses the `anthropic` SDK).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "run_with_llm requires ANTHROPIC_API_KEY to be set (e.g. in a .env file). "
            "Use run_rule_based() instead if no key is available."
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
            "just the number. A web_search tool is also available, but it is "
            "STRICTLY for qualitative context to enrich the rationale text (e.g. is "
            "there a known reason a metric moved) -- it returns today's information, "
            "not what was knowable as of the analysis date, so it must NEVER be used "
            "to decide a reason's Supported/Weakened/Broken status. That status must "
            "come only from check_reason_status / calculate_metric's point-in-time SEC "
            "data. Once you're done, call finalize_report exactly once with a "
            "structured entry for every reason you checked -- that call is your final "
            "answer, not a free-text summary."
        ),
    }]
    trace = []
    total_input_tokens = 0
    total_output_tokens = 0
    all_tools = TOOL_SPECS + [WEB_SEARCH_TOOL, FINALIZE_REPORT_TOOL]
    state = InvestigationState(ticker=ticker)
    # How many times assess_sufficiency has rejected a finalize_report call.
    # Capped rather than unbounded so a reason the agent genuinely can't
    # satisfy (e.g. get_filing_context comes back empty) can't turn into an
    # infinite reject/retry cycle -- the overall range(10) loop cap is the
    # backstop, but this gives up on the *assessor* specifically after 2
    # rounds and accepts the agent's answer, flagged in the trace.
    rejection_count = 0
    MAX_REJECTIONS = 2

    for _ in range(10):  # hard cap so a runaway loop can't spin forever
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers=headers,
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 2048,
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
        if finalize_call:
            problems = assess_sufficiency(state, finalize_call["input"]["reasons"])
            if problems and rejection_count < MAX_REJECTIONS:
                rejection_count += 1
                trace.append(f"finalize_report rejected by assess_sufficiency: {problems}")
                messages.append({
                    "role": "user",
                    "content": (
                        "Your finalize_report call was rejected -- the evidence gathered "
                        "so far doesn't support finalizing these reasons yet:\n"
                        + "\n".join(f"- {p}" for p in problems)
                        + "\nInvestigate further (call the relevant tool(s)) and then call "
                        "finalize_report again."
                    ),
                })
                continue
            if problems:
                trace.append(
                    f"finalize_report accepted despite unresolved gaps (assessor gave up "
                    f"after {MAX_REJECTIONS} rejections): {problems}"
                )
            return {
                "ticker": ticker,
                "trace": trace,
                "reasons": finalize_call["input"]["reasons"],
                "assessor_gaps": problems,
                "escalated": False,
                "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
            }

        if not tool_uses:
            # Model produced text instead of calling finalize_report -- nudge it
            # rather than accepting an unstructured answer.
            messages.append({
                "role": "user",
                "content": "Please call finalize_report with your structured conclusion now.",
            })
            continue

        tool_results = []
        for call in tool_uses:
            trace.append(f"LLM called {call['name']}({call['input']})")
            if verbose:
                print(trace[-1])
            result = dispatch[call["name"]](**call["input"])
            state.record(call["name"], call["input"], result)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": call["id"],
                "content": json.dumps(result),
            })
        messages.append({"role": "user", "content": tool_results})

    # Loop cap reached without ever calling finalize_report. Previously this
    # raised and the caller had to handle a crash -- but "the agent couldn't
    # reach a conclusion in a bounded number of steps" is exactly the case
    # the Human Escalation path exists for, not an error state. Report what
    # was actually investigated (per state.tool_calls) so a reviewer sees
    # what the agent tried, not just "it gave up."
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
            f"Exceeded the tool-call loop cap ({10} iterations) without reaching "
            f"finalize_report. Reasons checked before giving up: {checked_reason_keys or 'none'}."
        ),
        "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
    }


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
