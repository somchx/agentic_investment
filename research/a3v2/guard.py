"""Reconciliation Guard: deterministic, evidence-grounded acceptance of a
verdict change, run after v1's reconciliation and v1's guards.

It does NOT count CHALLENGE_SUPPORTED. In v1, 2 of the 8 correct A3 changes
(KO-12, META-06) had none, while 4 of the 15 harmful ones were made the same
way. It asks instead whether the proposed verdict rests on cited evidence that
the reviewer found deciding and that passed every deterministic check.

    decisive proposal (to SUPPORTED / CONTRADICTED)
      ACCEPT  >= 1 valid finding of the matching relation (ENTAILS / CONTRADICTS)
              whose evidence is among the surviving citations or deterministic checks,
              and (for SUPPORTED) no valid CONTRADICTS finding
      REJECT  otherwise, with the most specific reason:
              INVALID_DECIDING_EVIDENCE (quote / period / intent downgrades),
              ARGUMENT_FROM_SILENCE, REFUTED_CHALLENGES_ONLY, CONTEXT_ONLY,
              CONFLICTING_DECIDING_EVIDENCE, DECIDING_EVIDENCE_NOT_CITED
    move to INSUFFICIENT_EVIDENCE from a decisive verdict
      ACCEPT  no valid evidence still decides the initial verdict, or a valid
              definition-mismatch finding exists
      REJECT  INITIAL_VERDICT_STILL_DECIDED
    any change away from A2's decisive numeric rule (NUMERIC_FALSE / NUMERIC_ALL_TRUE)
      REJECT  A2_NUMERIC_CONCLUSION_PRESERVED unless a counter numeric check reaches
              the opposite status or a definition mismatch is shown

Invalid citations are excluded first and the rules run on what remains. A
rejected change keeps A2's label and citations. The reviewer's labels are
inputs, not truths: the guard can only be as right as the findings it gets,
which is why every finding and decision is written to the trace."""

from . import GUARD_VERSION
from .checks import check_citations
from .schemas import GuardDecision

DECISIVE = ("SUPPORTED", "CONTRADICTED")
NUMERIC_DECISIVE = {"NUMERIC_FALSE": "CONTRADICTED", "NUMERIC_ALL_TRUE": "SUPPORTED"}
RELATION_FOR = {"SUPPORTED": "ENTAILS", "CONTRADICTED": "CONTRADICTS"}


def _valid(f: dict) -> bool:
    return f.get("validation_status") == "VALID"


def _numeric_basis(rule: str | None, checks: list[dict], label: str) -> list[str]:
    """Evidence ids of A2's deterministic checks that decide `label`."""
    if NUMERIC_DECISIVE.get(rule or "") != label:
        return []
    want = "FALSE" if label == "CONTRADICTED" else "TRUE"
    return [f"numeric:{c['evidence_ids'][0]}" if c.get("evidence_ids") else "numeric" for c in checks if c.get("status") == want] or ["numeric"]


def decide(*, initial_label: str, proposed_label: str, initial_rule: str | None, initial_checks: list[dict],
           supporting: list, contradicting: list, assessments: list[dict], counter_numeric: list[dict],
           findings: list[dict], ledger, claim, period) -> GuardDecision:
    trace: list[str] = []
    cited = list(supporting or []) + list(contradicting or [])
    kept, excluded = check_citations(ledger, claim, period, cited)
    kept_ids = {c["evidence_id"] for c in kept}
    if excluded:
        trace.append(f"excluded {len(excluded)} citation(s): " + ", ".join(f"{e['evidence_id']}({'/'.join(e['issues'])})" for e in excluded))

    def out(final, outcome, reason, deciding=(), basis=()):
        trace.append(f"{outcome}: {reason}")
        return {"version": GUARD_VERSION, "initial_label": initial_label, "proposed_label": proposed_label, "final_label": final,
                "outcome": outcome, "reason_code": reason, "excluded_citations": excluded, "deciding_findings": list(deciding),
                "initial_basis": list(basis), "rule_trace": trace}

    if proposed_label == initial_label:
        return out(initial_label, "NO_CHANGE", "NO_CHANGE")

    definition = [f["finding_id"] for f in findings if _valid(f) and f.get("definition_mismatch") and f["relation"] != "IRRELEVANT"]

    # A2's decisive numeric conclusion stands unless numbers or a definition overturn it
    if initial_rule in NUMERIC_DECISIVE:
        opposite = "TRUE" if initial_rule == "NUMERIC_FALSE" else "FALSE"
        if not definition and not any(n.get("status") == opposite for n in counter_numeric or []):
            return out(initial_label, "REJECT", "A2_NUMERIC_CONCLUSION_PRESERVED", basis=_numeric_basis(initial_rule, initial_checks, initial_label))
        trace.append("A2 numeric conclusion challenged by " + ("a definition mismatch" if definition else "a counter numeric check"))

    if proposed_label == "INSUFFICIENT_EVIDENCE":
        want = RELATION_FOR.get(initial_label)
        basis = [f["finding_id"] for f in findings if _valid(f) and f["relation"] == want]
        basis += _numeric_basis(initial_rule, initial_checks, initial_label) if initial_rule in NUMERIC_DECISIVE else []
        if basis and not definition:
            return out(initial_label, "REJECT", "INITIAL_VERDICT_STILL_DECIDED", basis=basis)
        return out(proposed_label, "ACCEPT", "DEFINITION_MISMATCH" if definition else "INITIAL_VERDICT_NOT_DECIDED_BY_VALID_EVIDENCE",
                   deciding=definition)

    want = RELATION_FOR[proposed_label]
    numeric_ids = {e for n in counter_numeric or [] if n.get("status") == ("TRUE" if want == "ENTAILS" else "FALSE")
                   for e in n.get("evidence_ids") or []}
    valid_deciding = [f for f in findings if _valid(f) and f["relation"] == want]
    cited_deciding = [f for f in valid_deciding if set(f["evidence_ids"]) & (kept_ids | numeric_ids)]
    if proposed_label == "SUPPORTED":
        conflicting = [f["finding_id"] for f in findings if _valid(f) and f["relation"] == "CONTRADICTS"]
        if conflicting:
            return out(initial_label, "REJECT", "CONFLICTING_DECIDING_EVIDENCE", basis=conflicting)
    if cited_deciding:
        return out(proposed_label, "ACCEPT", "DECIDING_EVIDENCE_CITED", deciding=[f["finding_id"] for f in cited_deciding])
    if valid_deciding:
        return out(initial_label, "REJECT", "DECIDING_EVIDENCE_NOT_CITED", deciding=[f["finding_id"] for f in valid_deciding])

    # no valid deciding evidence: name the most specific reason
    downgraded = [f for f in findings if f.get("declared_relation") == want and f.get("downgraded_reason")]
    if downgraded:
        reasons = sorted({f["downgraded_reason"].split(":")[0] for f in downgraded})
        trace.append("deciding findings downgraded: " + ", ".join(f"{f['finding_id']}={f['downgraded_reason']}" for f in downgraded))
        return out(initial_label, "REJECT", "INVALID_DECIDING_EVIDENCE:" + "+".join(reasons))
    statuses = [a.get("assessment") for a in assessments or []]
    if not statuses or all(s == "NO_RELEVANT_EVIDENCE" for s in statuses):
        return out(initial_label, "REJECT", "ARGUMENT_FROM_SILENCE")
    if "CHALLENGE_REFUTED" in statuses and "CHALLENGE_SUPPORTED" not in statuses:
        return out(initial_label, "REJECT", "REFUTED_CHALLENGES_ONLY")
    return out(initial_label, "REJECT", "CONTEXT_ONLY")
