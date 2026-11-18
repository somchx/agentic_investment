"""A3 v2.2 (Approach A) decidability schema and gate. Schema and pure functions
only: no prompt, no LLM call and no graph wiring yet, so nothing here changes
v2.0 / v2.1 / v2.1.1 behaviour or hashes. A future analyze_claim step fills one
record per assertion; anything missing or malformed becomes UNKNOWN, and an
UNKNOWN record never gates (the guard then behaves as guard 0.2).

Per assertion:
    predicate_type     MEASURABLE | EVALUATIVE | CAUSAL | NEGATIVE | UNKNOWN
    criterion_source   CLAIM_STATES | FILING_STATES | NONE | UNKNOWN
                       (where the yardstick of an evaluative predicate comes from)
    required_evidence  [{kind, scope}] -- what a deciding finding must show
        kind   NUMERIC_FACT | CRITERION_DEFINITION | EXPLICIT_CAUSAL_STATEMENT |
               EXPLICIT_ABSENCE_STATEMENT | SCOPE_MATCHED_FACT
        scope  {entity, segment, region, metric} (strings or null)
    status             DECIDABLE | NEEDS_CRITERION | UNKNOWN (derived, not asked)

Gate (G1 / G2 / G4 / G5 of the error analysis), applied to a change to a
decisive label:
    G1 EVALUATIVE with criterion_source NONE   -> block (NO_CRITERION)
    G2 CAUSAL                                  -> a deciding finding must have
       support_mode EXPLICIT                      (CAUSE_NOT_EXPLICIT)
    G4 any required scope term                 -> it must appear in a deciding
       key quote                                  (SCOPE_NOT_COVERED)
    G5 NEGATIVE, change to CONTRADICTED        -> a deciding finding must have
       polarity_match true                        (POLARITY_MISMATCH)
`support_mode` and `polarity_match` are future reviewer fields; a finding
without them counts as not satisfying G2 / G5 only when the gate is enabled.
"""

PREDICATE_TYPES = ("MEASURABLE", "EVALUATIVE", "CAUSAL", "NEGATIVE", "UNKNOWN")
CRITERION_SOURCES = ("CLAIM_STATES", "FILING_STATES", "NONE", "UNKNOWN")
EVIDENCE_KINDS = ("NUMERIC_FACT", "CRITERION_DEFINITION", "EXPLICIT_CAUSAL_STATEMENT", "EXPLICIT_ABSENCE_STATEMENT",
                  "SCOPE_MATCHED_FACT")
SCOPE_KEYS = ("entity", "segment", "region", "metric")
DECIDABILITY_VERSION = "a3v2-decidability-0.1-draft"
DECISIVE = ("SUPPORTED", "CONTRADICTED")


def normalize(raw: dict | None, assertion_id: str = "A0") -> dict:
    """One assertion's record with every field present; bad values become UNKNOWN and are listed in `issues`."""
    raw = raw if isinstance(raw, dict) else {}
    issues = []
    ptype = raw.get("predicate_type")
    if ptype not in PREDICATE_TYPES:
        issues.append(f"predicate_type {ptype!r}") if ptype is not None else None
        ptype = "UNKNOWN"
    crit = raw.get("criterion_source")
    if crit not in CRITERION_SOURCES:
        issues.append(f"criterion_source {crit!r}") if crit is not None else None
        crit = "UNKNOWN"
    req = []
    for i, r in enumerate(raw.get("required_evidence") or []):
        if not isinstance(r, dict) or r.get("kind") not in EVIDENCE_KINDS:
            issues.append(f"required_evidence[{i}] kind {r.get('kind') if isinstance(r, dict) else r!r}")
            continue
        scope = r.get("scope") if isinstance(r.get("scope"), dict) else {}
        req.append({"kind": r["kind"], "scope": {k: (str(scope[k]).strip() or None) if scope.get(k) else None for k in SCOPE_KEYS}})
    status = ("UNKNOWN" if ptype == "UNKNOWN" else
              "NEEDS_CRITERION" if ptype == "EVALUATIVE" and crit in ("NONE", "UNKNOWN") else "DECIDABLE")
    return {"assertion_id": raw.get("assertion_id") or assertion_id, "predicate_type": ptype, "criterion_source": crit,
            "required_evidence": req, "status": status, "issues": issues, "version": DECIDABILITY_VERSION}


def scope_terms(record: dict) -> list[str]:
    """Segment / region / metric terms a deciding quote must contain (entity names are left to the company check)."""
    return sorted({r["scope"][k] for r in record["required_evidence"] for k in ("segment", "region", "metric") if r["scope"].get(k)})


def scope_covered(terms: list[str], quote: str) -> bool:
    q = " ".join((quote or "").lower().split())
    return all(" ".join(t.lower().split()) in q for t in terms)


def gate(record: dict, proposed_label: str, deciding_findings: list[dict]) -> tuple[bool, str | None]:
    """(allowed, reason). UNKNOWN records and non-decisive proposals are never gated."""
    if proposed_label not in DECISIVE or record["predicate_type"] == "UNKNOWN":
        return True, None
    if record["predicate_type"] == "EVALUATIVE" and record["criterion_source"] == "NONE":
        return False, "NO_CRITERION"
    if record["predicate_type"] == "CAUSAL" and not any(f.get("support_mode") == "EXPLICIT" for f in deciding_findings):
        return False, "CAUSE_NOT_EXPLICIT"
    if record["predicate_type"] == "NEGATIVE" and proposed_label == "CONTRADICTED" and \
            not any(f.get("polarity_match") is True for f in deciding_findings):
        return False, "POLARITY_MISMATCH"
    terms = scope_terms(record)
    if terms and not any(scope_covered(terms, f.get("key_quote") or "") for f in deciding_findings):
        return False, "SCOPE_NOT_COVERED"
    return True, None


# ---------------------------------------------------------------- classifier call (prompt 0.1)
# One isolated call per claim. The model sees the claim text, company and
# reporting period only: no filing, no label, no system output. Its record
# feeds the guard only (never the reviewer), so the reviewer's cached requests
# are unchanged and the call can be added to an existing run's traces.
DECIDABILITY_PROMPT_VERSION = "a3v2-decidability-prompt-0.1"
DECIDABILITY_MAX_TOKENS = 600
DECIDABILITY_SYSTEM = """You classify financial claims before they are checked against SEC filings. You do NOT decide whether a claim is true and you see no filing.

For the claim, report:
- predicate_type: the kind of statement the claim's main predicate makes
    MEASURABLE  a fact a filing figure or explicit statement can settle (levels, changes, comparisons, thresholds, rankings, shares of a change)
    EVALUATIVE  a judgement word with no stated yardstick ("well", "strong", "solid", "exceptional", "healthy", "well positioned", "pricing power", "fully offsetting")
    CAUSAL      says what caused / drove / explains an outcome ("because of", "driven by", "the main reason", "came mainly from")
    NEGATIVE    says something did NOT happen or had NO effect ("not affected", "did not lose", "did not contribute")
  If several apply, choose the one that decides what evidence is needed, in this order: NEGATIVE, EVALUATIVE, CAUSAL, MEASURABLE.
  A claim that names a cause AND gives a measurable test of it ("primarily driven by X", "X was the largest factor") is CAUSAL with a contribution test.
- evaluative_terms: the exact judgement words from the claim (empty if none).
- criterion_source: CLAIM_STATES if the claim itself gives the yardstick (a number, a threshold, an explicit comparison); otherwise NONE.
- scope: the segment, region and metric the claim is restricted to, as written in the claim (null when the claim is company-wide or does not name one).
- contribution: for "primarily / mainly / largest / main driver" claims, type PRIMARY_DRIVER or LARGEST_FACTOR, the component named and the total it is part of; otherwise type NONE.
- required_evidence: what a filing must show to decide the claim, as a list of kinds:
    NUMERIC_FACT, CRITERION_DEFINITION, EXPLICIT_CAUSAL_STATEMENT, EXPLICIT_ABSENCE_STATEMENT, SCOPE_MATCHED_FACT

Answer only with the classify_claim tool."""
DECIDABILITY_TOOL = {
    "name": "classify_claim",
    "description": "Classify what a financial claim asserts and what evidence could decide it. Does not judge truth.",
    "input_schema": {
        "type": "object",
        "properties": {
            "predicate_type": {"type": "string", "enum": list(PREDICATE_TYPES[:-1])},
            "evaluative_terms": {"type": "array", "items": {"type": "string"}},
            "criterion_source": {"type": "string", "enum": ["CLAIM_STATES", "NONE"]},
            "scope": {"type": "object", "properties": {k: {"type": ["string", "null"]} for k in ("segment", "region", "metric")}},
            "contribution": {"type": "object", "properties": {
                "type": {"type": "string", "enum": ["PRIMARY_DRIVER", "LARGEST_FACTOR", "NONE"]},
                "component": {"type": ["string", "null"]}, "total": {"type": ["string", "null"]}}, "required": ["type"]},
            "required_evidence": {"type": "array", "items": {"type": "string", "enum": list(EVIDENCE_KINDS)}},
            "note": {"type": "string", "description": "one sentence, why"},
        },
        "required": ["predicate_type", "evaluative_terms", "criterion_source", "contribution", "required_evidence"],
    },
}


def decidability_request(claim: dict) -> tuple[str, list, list, int, dict]:
    """(system, messages, tools, max_tokens, tool_choice) for one claim; only the claim text, company and period are sent."""
    import json as _json
    user = {"role": "user", "content": _json.dumps({"claim": claim["claim"], "company": claim["company"],
                                                     "reporting_period": claim.get("reporting_period")}, ensure_ascii=False)}
    return DECIDABILITY_SYSTEM, [user], [DECIDABILITY_TOOL], DECIDABILITY_MAX_TOKENS, {"type": "tool", "name": DECIDABILITY_TOOL["name"]}


def record_from_output(out: dict | None) -> dict:
    """Classifier output -> the normalized record the gate reads (adds evaluative_terms, scope, contribution)."""
    out = out if isinstance(out, dict) else {}
    scope = out.get("scope") if isinstance(out.get("scope"), dict) else {}
    req = [{"kind": k, "scope": {"entity": None, **{s: scope.get(s) for s in ("segment", "region", "metric")}}}
           for k in out.get("required_evidence") or [] if k in EVIDENCE_KINDS]
    rec = normalize({"predicate_type": out.get("predicate_type"), "criterion_source": out.get("criterion_source"),
                     "required_evidence": req})
    contrib = out.get("contribution") if isinstance(out.get("contribution"), dict) else {}
    rec.update({"evaluative_terms": [str(t).strip() for t in out.get("evaluative_terms") or [] if str(t).strip()],
                "scope": {s: (scope.get(s) or None) for s in ("segment", "region", "metric")},
                "contribution": {"type": contrib.get("type") if contrib.get("type") in ("PRIMARY_DRIVER", "LARGEST_FACTOR") else "NONE",
                                 "component": contrib.get("component"), "total": contrib.get("total")},
                "note": out.get("note"), "prompt_version": DECIDABILITY_PROMPT_VERSION})
    return rec


def criterion_in_evidence(record: dict, quotes: list[str]) -> bool:
    """G1 escape: the filing itself uses the claim's judgement word in a deciding quote (e.g. "record quarter")."""
    terms = [" ".join(t.lower().split()) for t in record.get("evaluative_terms") or []]
    return any(t and t in " ".join((q or "").lower().split()) for t in terms for q in quotes)


def gate_phase1(record: dict, proposed_label: str, deciding_quotes: list[str], use_scope: bool = False) -> tuple[bool, str | None]:
    """Phase-1 gate (no reviewer changes): G1 always, G4 when `use_scope`. G2 / G5 need reviewer fields and are off."""
    if proposed_label not in DECISIVE or record.get("predicate_type") in (None, "UNKNOWN"):
        return True, None
    if record["predicate_type"] == "EVALUATIVE" and record["criterion_source"] != "CLAIM_STATES" \
            and not criterion_in_evidence(record, deciding_quotes):
        return False, "NO_CRITERION"
    if use_scope:
        terms = [t for t in ((record.get("scope") or {}).get(k) for k in ("segment", "region")) if t]
        if terms and not any(scope_covered(terms, q) for q in deciding_quotes):
            return False, "SCOPE_NOT_COVERED"
    return True, None


def assess_with_llm(run) -> dict:
    """The classifier call inside a claim run: same budget, cache, ledger and trace as the reviewer's isolated
    call. Only the claim text, company and reporting period are sent. Failure -> an UNKNOWN record (never gates)."""
    import time
    from experiments.pipeline import NoStructuredOutput, StageBudgetExhausted
    c = run.claim
    try:
        run._check_budget()
        t0 = time.monotonic()
        payload = run.llm.create(*decidability_request({"claim": c.claim, "company": c.company, "reporting_period": c.reporting_period}))
    except (NoStructuredOutput, StageBudgetExhausted) as e:
        rec = record_from_output(None)
        rec["issues"].append(f"classifier not run: {e}")
        return rec
    usage = payload.get("usage") or {}
    run.input_tokens += usage.get("input_tokens", 0)
    run.output_tokens += usage.get("output_tokens", 0)
    use = next((b for b in payload.get("content") or [] if b.get("type") == "tool_use" and b.get("name") == DECIDABILITY_TOOL["name"]), None)
    run.llm_calls.append({"stage": "decidability", "tool": DECIDABILITY_TOOL["name"], "request_key": payload.get("_request_key"),
                          "source": payload.get("_source"), "input_tokens": usage.get("input_tokens", 0),
                          "output_tokens": usage.get("output_tokens", 0), "stop_reason": payload.get("stop_reason"),
                          "latency_ms": payload.get("_latency_ms", round((time.monotonic() - t0) * 1000)),
                          "output": use["input"] if use else None, "isolated_conversation": True,
                          "prompt_version": DECIDABILITY_PROMPT_VERSION})
    rec = record_from_output(use["input"] if use and payload.get("stop_reason") != "max_tokens" else None)
    if use is None or payload.get("stop_reason") == "max_tokens":
        rec["issues"].append("classifier gave no complete tool output")
    return rec


def deciding_quotes(findings: list[dict], label: str) -> list[str]:
    rel = {"SUPPORTED": "ENTAILS", "CONTRADICTED": "CONTRADICTS"}.get(label)
    return [f.get("key_quote") or "" for f in findings if f.get("validation_status") == "VALID" and f.get("relation") == rel]


def apply_phase1(a2_label: str, final: str, record: dict | None, findings: list[dict], scope: bool, downgrade) -> tuple[str, str | None]:
    """Phase-1 decidability on top of a guard result.
    G1 (+G4 when `scope`): a change away from A2 to a decisive label is reverted when the gate fails.
    downgrade True: any decisive final label on an EVALUATIVE claim without a stated criterion becomes
      INSUFFICIENT_EVIDENCE unless a deciding quote uses the claim's own judgement word;
    downgrade "supported" (D-sup): the same for SUPPORTED only -- a claim whose factual part is refuted stays
      CONTRADICTED (annotation guideline); chosen after the dev-v0.2 debug replay (post hoc)."""
    if not record:
        return final, None
    quotes, reason = deciding_quotes(findings, final), None
    if final != a2_label and final in DECISIVE:
        ok, why = gate_phase1(record, final, quotes, use_scope=scope)
        if not ok:
            final, reason = a2_label, why
            quotes = deciding_quotes(findings, final)
    if downgrade and final in (DECISIVE if downgrade is True else ("SUPPORTED",)) and record.get("predicate_type") == "EVALUATIVE" \
            and record.get("criterion_source") != "CLAIM_STATES" and not criterion_in_evidence(record, quotes):
        return "INSUFFICIENT_EVIDENCE", (reason + "+" if reason else "") + "DOWNGRADE_NO_CRITERION"
    return final, reason
