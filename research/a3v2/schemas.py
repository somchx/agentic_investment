"""Typed records of A3 v2. Every record is a JSON-serialisable TypedDict so it
can sit in the LangGraph state and in the trace unchanged."""

from typing import Literal, TypedDict

Label = Literal["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]
Relation = Literal["ENTAILS", "CONTRADICTS", "RELATED_NOT_DECIDING", "IRRELEVANT"]
EvidenceType = Literal["OBSERVED_RESULT", "DISCLOSED_FACT", "DEFINITION", "MANAGEMENT_INTENT", "FORWARD_LOOKING_OR_RISK",
                       "OTHER_CONTEXT"]
Addresses = Literal["LEVEL", "CHANGE", "CAUSE", "DEFINITION", "OTHER"]
PeriodStatus = Literal["MATCH", "COMPARISON", "PARTIAL_PERIOD", "OTHER_PERIOD", "UNKNOWN"]
GuardOutcome = Literal["NO_CHANGE", "ACCEPT", "REJECT"]

RELATIONS = ("ENTAILS", "CONTRADICTS", "RELATED_NOT_DECIDING", "IRRELEVANT")
DECIDING = ("ENTAILS", "CONTRADICTS")
EVIDENCE_TYPES = ("OBSERVED_RESULT", "DISCLOSED_FACT", "DEFINITION", "MANAGEMENT_INTENT", "FORWARD_LOOKING_OR_RISK", "OTHER_CONTEXT")
NON_RESULT_TYPES = ("MANAGEMENT_INTENT", "FORWARD_LOOKING_OR_RISK")  # may inform, never decide
ADDRESSES = ("LEVEL", "CHANGE", "CAUSE", "DEFINITION", "OTHER")


class ClaimPeriod(TypedDict):
    period_end: str | None      # ISO date the claim is about
    basis: str | None           # "quarter" | "annual" | None
    comparison_end: str | None  # same period one year earlier (legitimate comparison column)
    source: str                 # "stated_date" | "fiscal_year_10k" | "unknown"


class Assertion(TypedDict, total=False):
    assertion_id: str           # "A0" = the whole claim; "N1".. = numeric assertions
    text: str
    type: str                   # "claim" | "numeric" | later: "factual" | "causal" | "evaluative"
    period_end: str | None
    comparison_end: str | None
    numeric: dict | None        # engine.numeric ASSERTION_SCHEMA object, numeric assertions only


class Computation(TypedDict, total=False):
    """A deterministic figure requested by the Initial Verdict Analyzer."""
    computation_id: str
    metric: str                 # implemented: "FreeCashFlow"
    basis: str                  # "quarter" | "annual"
    period_end: str


class EvidenceCheck(TypedDict):
    """Deterministic checks of one evidence unit (and optionally one quote)."""
    evidence_id: str
    exists: bool
    kind: str | None
    company_ok: bool | None
    filed_by_cutoff: bool | None
    period_status: str          # PeriodStatus
    quote_status: str           # "VERIFIED" | "NOT_IN_PASSAGE" | "TOO_SHORT" | "XBRL_VALUE_NOT_IN_QUOTE" | "NOT_CHECKED"
    issues: list[str]


class ReviewFinding(TypedDict, total=False):
    finding_id: str
    assertion_id: str
    evidence_ids: list[str]     # usually one; several when a figure must be combined (price +14% vs impressions +10%)
    declared_relation: str      # what the reviewer said
    relation: str               # after deterministic validation (may be downgraded to RELATED_NOT_DECIDING)
    evidence_type: str
    addresses: str
    definition_mismatch: bool   # the evidence shows the claim's measure / segment is defined differently
    key_quote: str
    justification: str
    validation_status: str      # "VALID" or the first failing check
    downgraded_reason: str | None
    checks: list[EvidenceCheck]


class ReviewRecord(TypedDict):
    version: str
    claim_period: ClaimPeriod
    assertions: list[Assertion]
    reviewed_evidence_ids: list[str]
    findings: list[ReviewFinding]
    dropped_findings: list[dict]  # reviewer output that could not be parsed or referenced unknown ids
    llm_called: bool


class GuardDecision(TypedDict):
    version: str
    initial_label: str
    proposed_label: str
    final_label: str
    outcome: str                # GuardOutcome
    reason_code: str
    excluded_citations: list[dict]
    deciding_findings: list[str]
    initial_basis: list[str]
    rule_trace: list[str]
