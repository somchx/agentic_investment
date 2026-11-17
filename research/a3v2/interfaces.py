"""Interfaces of the two components that come after the Reviewer and Guard
are tested: the Initial Verdict Analyzer and the Decidability Check.

Only the contracts and conservative defaults live here. The defaults add no
LLM call and decide nothing new: the analyzer returns the whole claim plus the
numeric assertions the initial model already extracted; the decidability
check returns NOT_ASSESSED, which the guard ignores. Replacing either default
is a separate, versioned change."""

from typing import Protocol, TypedDict

from .checks import claim_period
from .schemas import Assertion, ClaimPeriod, Computation


class AnalysisResult(TypedDict):
    assertions: list[Assertion]
    computations: list[Computation]  # deterministic figures to compute (a3v2.derived)
    claim_period: ClaimPeriod
    analyzer: str


class DecidabilityResult(TypedDict, total=False):
    assertion_id: str
    status: str            # "DECIDABLE" | "UNDECIDABLE" | "NOT_ASSESSED"
    predicate: str | None  # e.g. "resilient", "adequate returns"
    criterion: str | None  # the criterion applied
    criterion_source: str | None  # "claim_text" or an evidence_id whose quote states it
    reason: str


class InitialVerdictAnalyzer(Protocol):
    """Planned output per assertion: type (numeric / factual / causal /
    evaluative), period and comparison period, whether the assertion is a
    level or a change, and the deterministic computations it needs (Δ, share
    of change, FCF, two-date balances). It sees the claim and A2's evidence,
    never the reference label."""

    def analyze(self, claim, model_verdict: dict, filings: list[dict]) -> AnalysisResult: ...


class DecidabilityCheck(Protocol):
    """Planned: an evaluative or causal assertion without a criterion stated
    in the claim or quoted from a filing is UNDECIDABLE and may not be the
    basis of a decisive verdict. A factual sub-assertion contradicted by
    same-period evidence still decides (KO-12, NVDA-11)."""

    def assess(self, claim, assertions: list[Assertion], evidence: list[dict]) -> list[DecidabilityResult]: ...


class DefaultAnalyzer:
    """Placeholder until the real analyzer exists."""

    name = "default-whole-claim-0.1"

    def __init__(self, computations: list[Computation] | None = None):
        self.computations = list(computations or [])  # tests may request figures explicitly

    def analyze(self, claim, model_verdict: dict, filings: list[dict]) -> AnalysisResult:
        period = claim_period(claim, filings)
        assertions: list[Assertion] = [{"assertion_id": "A0", "text": claim.claim, "type": "claim",
                                        "period_end": period["period_end"], "comparison_end": period["comparison_end"]}]
        for i, a in enumerate(model_verdict.get("numeric_assertions") or [], start=1):
            if isinstance(a, dict):
                assertions.append({"assertion_id": f"N{i}", "type": "numeric", "numeric": a,
                                   "text": f"{a.get('metric')} {a.get('measure')} {a.get('comparison')} {a.get('threshold')}",
                                   "period_end": a.get("period_end") or period["period_end"], "comparison_end": period["comparison_end"]})
        return {"assertions": assertions, "computations": self.computations, "claim_period": period, "analyzer": self.name}


class NotAssessedDecidability:
    name = "not-assessed-0.1"

    def assess(self, claim, assertions, evidence):
        return [{"assertion_id": a["assertion_id"], "status": "NOT_ASSESSED", "reason": "decidability check not implemented yet"}
                for a in assertions]
