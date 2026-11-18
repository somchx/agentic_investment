"""Evidence Reviewer (Review and Critique pattern), between contradiction
investigation and reconciliation.

1. Deterministic checks of every evidence unit (a3v2.checks).
2. One LLM call in a FRESH conversation with its own system prompt. The packet
   holds the claim, its period, the assertions and the evidence -- not A2's
   label, reasoning, citations or the contradiction hypotheses (they are
   phrased against A2's verdict and would prime the reviewer).
3. Deterministic validation of every finding. The reviewer is not trusted:
   a deciding relation (ENTAILS / CONTRADICTS) is downgraded to
   RELATED_NOT_DECIDING when its key quote is not in the evidence, the
   evidence is from another period, or the reviewer itself typed the evidence
   as a management intention / forward-looking statement. Declared and
   effective relations are both kept in the trace."""

import time

from engine.prompts import packet_text

from . import REVIEW_PROMPT_VERSION, REVIEW_PROMPT_VERSION_V21, REVIEW_PROMPT_VERSION_V211
from .checks import check_evidence
from .prompts import REVIEW_INSTRUCTION, REVIEW_SYSTEM_PROMPT, REVIEW_SYSTEM_PROMPT_V21, REVIEW_SYSTEM_PROMPT_V211, REVIEW_TOOL
from .schemas import ADDRESSES, DECIDING, EVIDENCE_TYPES, NON_RESULT_TYPES, RELATIONS, ReviewFinding, ReviewRecord

FATAL_ISSUES = ("UNKNOWN_EVIDENCE_ID", "TICKER_MISMATCH", "FUTURE_EVIDENCE", "NO_FILING_IDENTITY")


def evidence_view(ledger, claim, period, evidence_id: str, max_chars: int) -> dict:
    u = ledger.get(evidence_id)
    c = check_evidence(ledger, claim, period, evidence_id)
    view = {"evidence_id": evidence_id, "kind": u.kind, "form": u.form, "filed": u.filed, "period_end": u.period_end,
            "period_status": c["period_status"]}
    if u.kind == "filing_passage":
        view["text"] = (u.excerpt or "")[:max_chars]
    else:
        view.update({"metric": u.locator, "values": list(u.values or []), "unit": u.unit, "text": u.excerpt})
    if c.get("period_compatibility"):  # v2.1
        ev = c["period_compatibility"]["evidence_period"]
        view.update({"period_start": ev.get("start") or u.period_start, "period_months": ev.get("months"),
                     "period_kind": ev.get("kind"), "period_reason": c["period_compatibility"]["reason"]})
    return view


def review_packet(claim, period, assertions: list[dict], views: list[dict]) -> dict:
    return {"claim": {"text": claim.claim, "company": claim.company, "reporting_period": claim.reporting_period,
                      "evidence_cutoff": claim.as_of_date},
            "claim_period": period, "assertions": [{k: a.get(k) for k in ("assertion_id", "text", "type", "period_end", "comparison_end")}
                                                    for a in assertions],
            "evidence": views}


def ask_isolated(run, stage: str, packet: dict, max_output_tokens: int, system: str = REVIEW_SYSTEM_PROMPT,
                 prompt_version: str = REVIEW_PROMPT_VERSION) -> dict:
    """One structured call outside the verification conversation. Same budget,
    cache, accounting and trace as ClaimRun.ask; the conversation itself is
    not read or extended."""
    from experiments.pipeline import NoStructuredOutput, coerce_tool_input

    run._check_budget()
    user = {"role": "user", "content": [{"type": "text", "text": packet_text(REVIEW_INSTRUCTION, packet)}]}
    t0 = time.monotonic()
    payload = run.llm.create(system, [user], [REVIEW_TOOL], max_output_tokens, {"type": "tool", "name": REVIEW_TOOL["name"]})
    usage = payload.get("usage") or {}
    run.input_tokens += usage.get("input_tokens", 0)
    run.output_tokens += usage.get("output_tokens", 0)
    use = next((b for b in payload.get("content") or [] if b.get("type") == "tool_use" and b.get("name") == REVIEW_TOOL["name"]), None)
    run.llm_calls.append({"stage": stage, "tool": REVIEW_TOOL["name"], "request_key": payload.get("_request_key"),
                          "source": payload.get("_source"), "input_tokens": usage.get("input_tokens", 0),
                          "output_tokens": usage.get("output_tokens", 0), "stop_reason": payload.get("stop_reason"),
                          "latency_ms": payload.get("_latency_ms", round((time.monotonic() - t0) * 1000)),
                          "output": use["input"] if use else None, "isolated_conversation": True,
                          "prompt_version": prompt_version})
    if use is None:
        raise NoStructuredOutput(f"{stage}: model did not call {REVIEW_TOOL['name']}")
    if payload.get("stop_reason") == "max_tokens":
        raise NoStructuredOutput(f"{stage}: structured output cut off at max_output_tokens")
    return coerce_tool_input(use["input"], REVIEW_TOOL["input_schema"])[0]


def validate_findings(raw: list, ledger, claim, period, assertion_ids: set[str], allow_partial_period: bool) -> tuple[list[ReviewFinding], list[dict]]:
    findings, dropped = [], []
    for i, f in enumerate(raw if isinstance(raw, list) else []):
        if not isinstance(f, dict) or f.get("relation") not in RELATIONS:
            dropped.append({"index": i, "reason": "MALFORMED_FINDING", "raw": str(f)[:300]})
            continue
        ids = [str(e) for e in (f.get("evidence_ids") or []) if e]
        if f.get("assertion_id") not in assertion_ids or not ids:
            dropped.append({"index": i, "reason": "UNKNOWN_ASSERTION_OR_NO_EVIDENCE", "raw": {k: f.get(k) for k in ("assertion_id", "evidence_ids")}})
            continue
        quote = f.get("key_quote") or ""
        checks = [check_evidence(ledger, claim, period, e) for e in ids]
        # the key quote must come from one of the listed units (a passage verbatim, a figure by value)
        quoted = [check_evidence(ledger, claim, period, e, quote) for e in ids]
        quote_ok = any(q["quote_status"] == "VERIFIED" for q in quoted)
        status, downgrade = "VALID", None
        fatal = next((iss for c in checks for iss in c["issues"] if iss in FATAL_ISSUES), None)
        relation = f["relation"]
        etype = f.get("evidence_type") if f.get("evidence_type") in EVIDENCE_TYPES else "OTHER_CONTEXT"
        v21 = bool(period.get("version"))
        if fatal:
            status = fatal
        elif not quote_ok:
            status = "KEY_QUOTE_NOT_IN_EVIDENCE"
        elif v21 and any(q["period_status"] == "MISMATCH" for q in quoted):
            status = "PERIOD_MISMATCH"
        elif v21 and any(q["period_status"] == "UNKNOWN" for q in quoted):
            status = "PERIOD_UNKNOWN"  # never treated as a match
        elif v21 and (period.get("orientation") == "historical") and relation in DECIDING and \
                any((q.get("period_compatibility") or {}).get("temporal") == "FORWARD_LOOKING" for q in quoted):
            status = "FORWARD_LOOKING_FOR_HISTORICAL_CLAIM"
        elif v21 and (period.get("orientation") == "historical") and relation in DECIDING and \
                any((q.get("period_compatibility") or {}).get("temporal") == "MIXED_OR_UNCLEAR" for q in quoted):
            status = "TEMPORAL_MIXED_OR_UNCLEAR"
        elif v21:
            pass
        elif any(c["period_status"] == "OTHER_PERIOD" for c in checks):
            status = "PERIOD_MISMATCH"
        elif not allow_partial_period and any(c["period_status"] == "PARTIAL_PERIOD" for c in checks):
            status = "PARTIAL_PERIOD"
        if relation in DECIDING:
            if status != "VALID":
                relation, downgrade = "RELATED_NOT_DECIDING", status
            elif etype in NON_RESULT_TYPES:
                relation, downgrade = "RELATED_NOT_DECIDING", f"NON_RESULT_EVIDENCE:{etype}"
        findings.append({"finding_id": f"R{len(findings) + 1}", "assertion_id": f["assertion_id"], "evidence_ids": ids,
                         "declared_relation": f["relation"], "relation": relation, "evidence_type": etype,
                         "addresses": f.get("addresses") if f.get("addresses") in ADDRESSES else "OTHER",
                         "definition_mismatch": bool(f.get("definition_mismatch")) and status == "VALID",
                         "key_quote": quote, "justification": f.get("justification") or "",
                         "validation_status": status, "downgraded_reason": downgrade, "checks": quoted,
                         **({"period_compatibility": [q["period_status"] for q in quoted]} if period.get("version") else {}),
                         **({"statement_time": [(q.get("period_compatibility") or {}).get("temporal") for q in quoted]}
                            if period.get("orientation") else {})})
    return findings, dropped


def review(run, analysis: dict, evidence_ids: list[str], cfg: dict) -> ReviewRecord:
    claim, period, ledger = run.claim, analysis["claim_period"], run.ledger
    ids = [e for e in dict.fromkeys(evidence_ids) if ledger.get(e) is not None]
    record: ReviewRecord = {"version": REVIEW_PROMPT_VERSION, "claim_period": period, "assertions": analysis["assertions"],
                            "reviewed_evidence_ids": ids, "findings": [], "dropped_findings": [], "llm_called": False}
    v21 = bool(period.get("version"))
    if v21:  # deterministic derivations for the claim's exact window, registered as evidence
        record["period_derivations"] = derive_missing_periods(run, analysis, ids)
        ids += [d["evidence_id"] for d in record["period_derivations"] if d["evidence_id"] not in ids]
    if not ids:
        return record
    views = [evidence_view(ledger, claim, period, e, cfg["passage_chars"]) for e in ids]
    prompt = ((REVIEW_SYSTEM_PROMPT_V211, REVIEW_PROMPT_VERSION_V211) if period.get("orientation") else
              (REVIEW_SYSTEM_PROMPT_V21, REVIEW_PROMPT_VERSION_V21) if v21 else ())
    out = ask_isolated(run, "evidence_review", review_packet(claim, period, analysis["assertions"], views), cfg["max_output_tokens"], *prompt)
    record["llm_called"] = True
    record["findings"], record["dropped_findings"] = validate_findings(
        out.get("findings"), ledger, claim, period, {a["assertion_id"] for a in analysis["assertions"]}, cfg["allow_partial_period"])
    return record


def derive_missing_periods(run, analysis: dict, evidence_ids: list[str]) -> list[dict]:
    """A3 v2.1. For each flow metric that the numeric assertions or the XBRL
    evidence concern, when no unit states the claim's exact window, a filed
    fact with that window or a sum of filed single quarters is computed
    (a3v2.periods.derive_for_claim). No LLM call."""
    from engine.numeric import FLOW_TAGS
    from .periods import derive_for_claim, is_decisive
    claim, period, ledger = run.claim, analysis["claim_period"], run.ledger
    if period.get("kind") != "duration":
        return []
    metrics, covered = [], set()
    for a in analysis["assertions"]:
        m = (a.get("numeric") or {}).get("metric")
        if m in FLOW_TAGS and m not in metrics:
            metrics.append(m)
    for e in evidence_ids:
        u = ledger.get(e)
        if u is None or u.kind not in ("xbrl_fact", "derived_metric"):
            continue
        m = (u.locator or "").split(" ")[0]
        c = check_evidence(ledger, claim, period, e)
        if is_decisive(c["period_status"]):
            covered.add((m, c["period_compatibility"]["role"]))
        elif m in FLOW_TAGS and m not in metrics:
            metrics.append(m)
    out = []
    for m in metrics:
        if (m, "current") in covered and (m, "comparison") in covered:
            continue
        out += [d for d in derive_for_claim(ledger, claim, period, m) if (m, d["role"]) not in covered]
    return out
