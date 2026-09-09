"""Investor Context Layer, part 2 (PROPOSAL.md Contribution 4): turns an
Objective Evidence Layer status (Supported/Weakened/Broken/Not enough data --
computed once, identical for everyone) into a priority tier for one
investor, given their profile.

Two independent implementations of the same decision, on purpose:

- `rule_based_tier` is a deterministic matrix. No LLM call, free, fully
  auditable -- this is the reference baseline the LLM-derived tier is
  checked against.
- `llm_tier` asks Claude to make the same call. It is forced (via the tool
  schema) to echo the evidence status it was given verbatim, so a caller can
  check that personalization never mutated the fact it's supposed to be
  reacting to -- see run_personalization_experiment.py's integrity check.

Tiers: "Monitor" < "Watch" < "Review Soon" < "Review Now".
"""

from investor_profile import InvestorProfile
from llm_client import call_claude
from tools import REASON_DEFS

TIERS = ["Monitor", "Watch", "Review Soon", "Review Now"]

_SEVERITY = {"Supported": 0, "Weakened": 1, "Not enough data": 1, "Broken": 2}


def _position_multiplier(position_size_pct: float) -> float:
    if position_size_pct >= 30:
        return 2.0
    if position_size_pct >= 15:
        return 1.5
    if position_size_pct >= 5:
        return 1.0
    return 0.5


def _risk_adjustment(risk_tolerance: str) -> float:
    return {"low": 1.0, "medium": 0.0, "high": -1.0}[risk_tolerance]


def _horizon_adjustment(investment_horizon: str) -> float:
    return {"<1y": 1.0, "1-5y": 0.0, ">5y": -1.0}[investment_horizon]


def rule_based_tier(evidence_status: str, profile: InvestorProfile) -> str:
    """Deterministic. A Supported reason is always "Monitor" regardless of
    profile -- nothing adverse happened, so there's nothing for the investor
    context to elevate. Personalization only changes urgency once the
    evidence layer has actually flagged something.
    """
    if evidence_status == "Supported":
        return "Monitor"

    severity = _SEVERITY[evidence_status]
    score = (
        severity * _position_multiplier(profile.position_size_pct)
        + _risk_adjustment(profile.risk_tolerance)
        + _horizon_adjustment(profile.investment_horizon)
    )
    score = max(score, 0.0)

    if score <= 0:
        return "Monitor"
    if score <= 2:
        return "Watch"
    if score <= 4:
        return "Review Soon"
    return "Review Now"


PERSONALIZE_TOOL = {
    "name": "assess_personalized_impact",
    "description": (
        "Submit your assessment of how much this evidence matters to this "
        "specific investor. Call this exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "echoed_evidence_status": {
                "type": "string",
                "enum": ["Supported", "Weakened", "Broken", "Not enough data"],
                "description": (
                    "Repeat back EXACTLY the evidence status you were given. "
                    "Do not change it -- you are not re-evaluating the evidence, "
                    "only its priority for this investor."
                ),
            },
            "tier": {"type": "string", "enum": TIERS},
            "rationale": {
                "type": "string",
                "description": (
                    "One or two sentences explaining the tier in terms of this "
                    "investor's profile (position size, horizon, risk tolerance)."
                ),
            },
        },
        "required": ["echoed_evidence_status", "tier", "rationale"],
    },
}


def llm_tier(
    ticker: str, reason_description: str, evidence_status: str, profile: InvestorProfile
) -> dict:
    """One Claude call. Returns dict with echoed_evidence_status, tier,
    rationale, and usage -- caller is responsible for checking
    echoed_evidence_status == evidence_status (the integrity check).
    """
    messages = [{
        "role": "user",
        "content": (
            f"An investment reason for {ticker} -- \"{reason_description}\" -- has "
            f"already been evaluated against the evidence and its status is: "
            f"{evidence_status}. This status is fixed and correct; you are not being "
            f"asked to re-evaluate the evidence.\n\n"
            f"Your job is only to decide how urgent this is for ONE specific investor, "
            f"given their profile:\n"
            f"- Risk tolerance: {profile.risk_tolerance}\n"
            f"- Investment horizon: {profile.investment_horizon}\n"
            f"- This holding is {profile.position_size_pct}% of their total portfolio\n"
            f"- Investment objective: {profile.objective}\n\n"
            f"Assign a priority tier (Monitor / Watch / Review Soon / Review Now) "
            f"reflecting how much this investor specifically should care right now, "
            f"and call assess_personalized_impact."
        ),
    }]

    payload = call_claude(messages, tools=[PERSONALIZE_TOOL], max_tokens=400)
    content = payload["content"]
    usage = payload.get("usage", {})
    call = next((b for b in content if b["type"] == "tool_use" and b["name"] == "assess_personalized_impact"), None)
    if not call:
        raise RuntimeError(f"llm_tier: model did not call assess_personalized_impact ({content!r})")

    return {
        **call["input"],
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        },
    }


def investigate_and_personalize(ticker: str, profile: InvestorProfile, persist: bool = True) -> dict:
    """The Contribution 4 pipeline end-to-end for one investor: run the
    Investigation Agent (agent.run_with_llm) to get each reason's Objective
    Evidence status, then run both tier decisions (rule-based baseline +
    LLM) for this profile against every reason it returned.

    Previously this was two separate, manually-chained steps -- an agent
    run's output had to be copied into run_personalization_experiment.py by
    hand (or via a saved results file) to get a personalized view. This
    closes that gap: one call, real evidence in, personalized priorities
    out. Costs one agent run's worth of LLM calls plus one llm_tier call
    per reason returned -- call sparingly (same budget discipline as
    run_personalization_experiment.py).

    Persists every reason's result to the investigation_runs table (db.py)
    by default -- this is the actual "production" pipeline entry point,
    unlike agent.run_with_llm itself (called directly, many times per run,
    by experiment scripts that would otherwise flood the database with
    test noise). Pass persist=False to opt out (e.g. in tests).
    """
    from agent import run_with_llm  # local import: agent.py doesn't import

    # this module, so no cycle -- but keeping the import here (rather than
    # top-level) makes that direction of dependency explicit at the call site.
    investigation = run_with_llm(ticker)

    if investigation.get("escalated"):
        # Nothing to personalize -- the agent never reached a conclusion for
        # this ticker, so there's no Objective Evidence status yet to weigh
        # against the investor's profile. Propagate the escalation as-is
        # rather than silently returning an empty personalized list, which
        # would look identical to "checked everything, all Supported."
        escalated_result = {
            "ticker": ticker,
            "profile": profile.name,
            "trace": investigation["trace"],
            "assessor_gaps": [],
            "escalated": True,
            "escalation_reason": investigation["escalation_reason"],
            "reasons": [],
            "usage": investigation["usage"],
        }
        if persist:
            import db
            db.save_investigation_result(escalated_result, profile_name=profile.name)
        return escalated_result

    personalized = []
    for r in investigation["reasons"]:
        reason = REASON_DEFS[r["reason_key"]]
        rule_result = rule_based_tier(r["status"], profile)
        llm_result = llm_tier(ticker, reason.description, r["status"], profile)
        personalized.append({
            **r,
            "rule_based_tier": rule_result,
            "llm_tier": llm_result["tier"],
            "llm_rationale": llm_result["rationale"],
            "integrity_ok": llm_result["echoed_evidence_status"] == r["status"],
        })

    final_result = {
        "ticker": ticker,
        "profile": profile.name,
        "trace": investigation["trace"],
        "assessor_gaps": investigation.get("assessor_gaps", []),
        "escalated": False,
        "reasons": personalized,
        "usage": investigation["usage"],  # personalization-call tokens aren't
        # separately tracked here -- see run_personalization_experiment.py
        # for a version that tallies both stages' cost precisely.
    }
    if persist:
        import db
        db.save_investigation_result(final_result, profile_name=profile.name)
    return final_result
