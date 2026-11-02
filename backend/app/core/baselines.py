"""B0-B3 experiment baselines on the shared investigation architecture
(protocol b0b3-2.0; Gold Design v0.1 section 6, Agent Output Schema v0.1).

All four start from the same initial packet (thesis rule, evaluation date,
authoritative rule-engine result, initial evidence) built by the same
deterministic tools the chat assistant uses:

- B0 deterministic only: the packet itself, no LLM.
- B1 fixed-evidence LLM: sees the packet, no retrieval tools.
- B2 agentic retrieval: B1 + EXPERIMENT_TOOLS (same engine as chat).
- B3 agentic + verification: B2 + forced evidence assessment + the
  verification gate (citation verification, section 4.1 recomputation).

B1-B3 share model, temperature, finalize schema, output cap and prompt; B2
and B3 share tools and budget. Every output is measured the same way after
the fact (claim verification, status consistency, tokens, cost, latency),
whether or not verification was part of the treatment.
"""

from agent_config import EXPERIMENT_BUDGET, EXPERIMENT_PROTOCOL_VERSION, config_manifest
from evidence_ledger import verify_claims
from investigation_engine import EngineConfig, InvestigationEngine
from investigation_prompts import EXPERIMENT_SYSTEM_PROMPT
from investigation_tools import EXPERIMENT_TOOLS, ToolContext, _evaluate, _rule_summary

BASELINES = ("B0", "B1", "B2", "B3")

FINALIZE_REASON_TOOL = {
    "name": "finalize_reason_assessment",
    "description": "Submit the structured assessment for this one reason (Agent Output Schema v0.1).",
    "input_schema": {"type": "object", "properties": {
        "reason_key": {"type": "string"},
        "rule_status": {"type": "string", "enum": ["SATISFIED", "BREACHED", "NOT_EVALUATED"]},
        "rule_reason_code": {"type": "string"},
        "evidence_status": {"type": "string", "enum": ["SUFFICIENT", "CONFLICTING", "INSUFFICIENT", "NOT_YET_OBSERVABLE"]},
        "task_scope": {"type": "string", "enum": ["RULE_CHECK", "CHANGE_EXPLANATION"]},
        "evidence_reason_codes": {"type": "array", "items": {"type": "string"}},
        "claims": {"type": "array", "items": {"type": "object", "properties": {
            "claim_id": {"type": "string"}, "proposition": {"type": "string"},
            "claim_type": {"type": "string", "enum": ["numeric", "management_attribution", "causal_interpretation", "uncertainty"]},
            "required": {"type": "boolean"},
            "status": {"type": "string", "enum": ["SUPPORTED", "CONTRADICTED", "NOT_ESTABLISHED"]},
            "evidence_ids": {"type": "array", "items": {"type": "string"}}, "quoted_span": {"type": "string"}},
            "required": ["claim_id", "proposition", "claim_type", "required", "status", "evidence_ids"]}},
        "review_required": {"type": "boolean"},
        "review_reasons": {"type": "array", "items": {"type": "string"}},
        "affected_claim_ids": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    }, "required": ["reason_key", "rule_status", "evidence_status", "task_scope", "claims", "review_required", "rationale"]},
}


def build_packet(ctx: ToolContext, case: dict) -> dict:
    """The shared starting point: authoritative numeric result + its evidence."""
    rule = case.get("frozen_rule")
    if rule:
        ctx.reason_defs[case["reason_key"]] = rule
    ev = _evaluate(ctx, case["ticker"], case["reason_key"], rule, ctx.analysis_date)
    return {
        "case_id": case["case_id"], "ticker": case["ticker"], "reason_key": case["reason_key"],
        "evaluation_date": ctx.analysis_date, "task_scope": case.get("task_scope", "RULE_CHECK"),
        "question": case.get("question"),
        "rule_result": _rule_summary(ctx, case["ticker"], ev, case["reason_key"], rule),
        "initial_evidence": ctx.ledger.public(),
    }


def evidence_status_from_claims(claims: list[dict], affected: list[str] | None = None) -> str:
    """Agent Output Schema v0.1 section 4.1 over required claims (the
    NOT_YET_OBSERVABLE branch needs filing-history evidence and is not
    recomputed here)."""
    required = [c for c in claims if c.get("required")]
    if affected:
        return "CONFLICTING"
    if not required or any(c.get("status") == "NOT_ESTABLISHED" for c in required):
        return "INSUFFICIENT"
    if all(c.get("status") in ("SUPPORTED", "CONTRADICTED") and c.get("evidence_ids") for c in required):
        return "SUFFICIENT"
    return "INSUFFICIENT"


def structural_problems(final: dict, packet: dict) -> list[str]:
    problems = []
    if final.get("rule_status") != packet["rule_result"].get("rule_status"):
        problems.append(f"rule_status must equal the rule engine result {packet['rule_result'].get('rule_status')}")
    claims = final.get("claims") or []
    required = [c for c in claims if c.get("required")]
    if not any(c.get("claim_type") == "numeric" for c in required):
        problems.append("a required numeric claim (what the rule result relies on) is missing")
    if packet["task_scope"] == "CHANGE_EXPLANATION" and not any(
            c.get("claim_type") in ("management_attribution", "causal_interpretation") for c in required):
        problems.append("task scope CHANGE_EXPLANATION requires a required explanatory claim (may be NOT_ESTABLISHED)")
    if final.get("evidence_status") == "CONFLICTING" and not final.get("affected_claim_ids"):
        problems.append("CONFLICTING evidence_status requires affected_claim_ids")
    if final.get("evidence_status") != "NOT_YET_OBSERVABLE":
        expected = evidence_status_from_claims(claims, final.get("affected_claim_ids"))
        if final.get("evidence_status") != expected:
            problems.append(f"evidence_status {final.get('evidence_status')} does not follow from the claims (section 4.1 gives {expected})")
    return problems


def _opening(packet: dict) -> str:
    import json
    return ("Initial evidence packet (authoritative; evidence ids are citable):\n"
            + json.dumps({k: packet[k] for k in ("case_id", "ticker", "reason_key", "evaluation_date", "task_scope", "question",
                                                  "rule_result", "initial_evidence")}, ensure_ascii=False, default=str))


def engine_config(baseline: str, packet: dict) -> EngineConfig:
    tools = [] if baseline == "B1" else EXPERIMENT_TOOLS
    return EngineConfig(
        mode=baseline, system_prompt=EXPERIMENT_SYSTEM_PROMPT, tool_names=tools, finalize_tool=FINALIZE_REASON_TOOL,
        budget=EXPERIMENT_BUDGET, require_assessment=baseline == "B3", verify=baseline == "B3",
        reason_keys=[packet["reason_key"]], gate=(lambda final, run: structural_problems(final, packet)) if baseline == "B3" else None,
    )


def run_case(baseline: str, case: dict, llm=None) -> dict:
    if baseline not in BASELINES:
        raise ValueError(f"unknown baseline {baseline}")
    ctx = ToolContext(analysis_date=case["evaluation_date"], allowed_tickers=[case["ticker"]], live_override=False)
    packet = build_packet(ctx, case)
    if baseline == "B0":
        r = packet["rule_result"]
        return {"case_id": case["case_id"], "baseline": "B0", "protocol": EXPERIMENT_PROTOCOL_VERSION,
                "config": config_manifest("B0", {}), "output": {
                    "reason_key": case["reason_key"], "rule_status": r.get("rule_status"), "task_scope": packet["task_scope"],
                    "computed_value": r.get("computed_value"), "threshold": r.get("threshold"), "evaluated_period": r.get("evaluated_period"),
                    "evidence": packet["initial_evidence"], "generated_explanation": None},
                "measures": {"llm_calls": 0, "tool_calls": 0, "cost_usd": 0.0}}

    engine = InvestigationEngine(engine_config(baseline, packet), ctx, llm=llm)
    result = engine.run([{"role": "user", "content": _opening(packet)}])
    final = result["final"] or {}
    declared_rule_status = final.get("rule_status")
    if final:
        final["rule_status"] = packet["rule_result"].get("rule_status")  # authoritative; the model cannot change it
    verification, citation_problems = verify_claims(final.get("claims") or [], ctx.ledger, ctx.analysis_date)
    trace = result["trace"]
    return {
        "case_id": case["case_id"], "baseline": baseline, "protocol": EXPERIMENT_PROTOCOL_VERSION, "config": trace["config"],
        "output": final, "stop_reason": result["stop_reason"],
        "measures": {
            "declared_rule_status_matched": declared_rule_status == packet["rule_result"].get("rule_status"),
            "claims": len(final.get("claims") or []),
            "claims_verified": sum(1 for v in verification if v["verified"]),
            "citation_problems": citation_problems,
            "structural_problems": structural_problems(final, packet) if final else ["no final output"],
            "budget_exhausted": result["stop_reason"] == "BUDGET_EXHAUSTED",
            "tool_calls": len(trace["tool_calls"]), "invalid_tool_calls": sum(1 for c in trace["tool_calls"] if c.get("error")),
            "retrieval_iterations": trace["retrieval_iterations"], "documents_opened": len({e["accession_number"] for e in trace["evidence"] if e.get("accession_number")}),
            "input_tokens": trace["usage"]["input_tokens"], "output_tokens": trace["usage"]["output_tokens"],
            "cost_usd": trace["cost_usd"], "latency_ms": trace["latency_ms"], "gate_rejections": len(trace["gate_rejections"]),
        },
        "trace": trace,
    }
