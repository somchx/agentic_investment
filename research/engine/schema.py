"""Claim input / prediction output schema and dataset record validation.

The model-facing input (`ClaimInput`) is built from a dataset record by
WHITELIST: only the fields below ever reach an approach, so a gold label,
reviewer note or gold evidence location stored next to a claim cannot leak
into a prompt even by accident. Constructing a ClaimInput from a record
that carries annotation fields is refused outright rather than silently
stripped, so a mixed-up file is noticed.
"""

import re
from dataclasses import asdict, dataclass, field
from datetime import date

LABELS = ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")
CATEGORIES = ("numerical", "interpretive", "ambiguous")
DIFFICULTIES = ("easy", "medium", "hard")
SPLITS = ("development", "gold")
# Source families a claim may restrict evidence to. Each maps to SEC forms.
SOURCE_FORMS = {
    "SEC_10K": ("10-K", "10-K/A"),
    "SEC_10Q": ("10-Q", "10-Q/A"),
    "SEC_8K": ("8-K",),
}
DEFAULT_SOURCES = ("SEC_10K", "SEC_10Q")

# Fields that belong to annotation / gold standard, never to the model input.
ANNOTATION_FIELDS = {
    "gold_label", "label", "dev_label", "reference_label", "supporting_evidence", "contradictory_evidence",
    "contradicting_evidence", "evidence_locations", "reviewer_id", "review_notes", "adjudication_status",
    "final_label", "annotations", "expected_verdict",
}
CLAIM_INPUT_FIELDS = ("claim_id", "company", "claim", "as_of_date", "allowed_sources", "reporting_period")

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$")
_TICKER = re.compile(r"^[A-Z][A-Z.]{0,9}$")


class SchemaError(ValueError):
    pass


def _iso(value, name: str) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as e:
        raise SchemaError(f"{name} must be YYYY-MM-DD, got {value!r}") from e


@dataclass(frozen=True)
class ClaimInput:
    """What an approach is allowed to see about a claim."""

    claim_id: str
    company: str
    claim: str
    as_of_date: str  # evidence cutoff: nothing filed after this date may be used
    allowed_sources: tuple[str, ...] = DEFAULT_SOURCES
    reporting_period: str | None = None  # e.g. "FY2026 Q3" -- part of the claim's wording, not a label

    def __post_init__(self):
        if not _ID.match(self.claim_id or ""):
            raise SchemaError(f"invalid claim_id {self.claim_id!r}")
        if not _TICKER.match(self.company or ""):
            raise SchemaError(f"company must be an upper-case ticker, got {self.company!r}")
        if not (self.claim or "").strip() or len(self.claim) > 2000:
            raise SchemaError("claim text must be 1..2000 characters")
        object.__setattr__(self, "as_of_date", _iso(self.as_of_date, "as_of_date"))
        sources = tuple(self.allowed_sources or ())
        if not sources or any(s not in SOURCE_FORMS for s in sources):
            raise SchemaError(f"allowed_sources must be a non-empty subset of {sorted(SOURCE_FORMS)}")
        object.__setattr__(self, "allowed_sources", sources)

    @classmethod
    def from_record(cls, record: dict) -> "ClaimInput":
        leaked = sorted(ANNOTATION_FIELDS & set(record))
        if leaked:
            raise SchemaError(f"claim record {record.get('claim_id')} carries annotation fields {leaked}; "
                              "claims and annotations must live in separate files")
        return cls(**{k: record[k] for k in CLAIM_INPUT_FIELDS if k in record and record[k] is not None})

    def allowed_forms(self) -> set[str]:
        return {f for s in self.allowed_sources for f in SOURCE_FORMS[s]}

    def to_dict(self) -> dict:
        d = asdict(self)
        d["allowed_sources"] = list(self.allowed_sources)
        return d


@dataclass
class DatasetClaim:
    """One row of development_cases.jsonl / gold_claims.jsonl (no labels)."""

    claim_id: str
    company: str
    claim: str
    as_of_date: str
    claim_category: str
    split: str
    allowed_sources: list[str] = field(default_factory=lambda: list(DEFAULT_SOURCES))
    reporting_period: str | None = None
    difficulty: str | None = None
    relevant_filings: list[str] = field(default_factory=list)  # accession numbers an annotator expects to need
    notes: str | None = None
    dataset_version: str | None = None

    def __post_init__(self):
        ClaimInput.from_record(asdict(self))  # same validation as the model input
        if self.claim_category not in CATEGORIES:
            raise SchemaError(f"{self.claim_id}: claim_category must be one of {CATEGORIES}")
        if self.split not in SPLITS:
            raise SchemaError(f"{self.claim_id}: split must be one of {SPLITS}")
        if self.difficulty is not None and self.difficulty not in DIFFICULTIES:
            raise SchemaError(f"{self.claim_id}: difficulty must be one of {DIFFICULTIES}")

    def to_input(self) -> ClaimInput:
        return ClaimInput.from_record(asdict(self))


@dataclass
class EvidenceRef:
    """Where an annotator found evidence. `quote` is copied verbatim from the
    filing so citations can be matched without trusting run-local ids."""

    accession_number: str
    form: str | None = None
    locator: str | None = None  # section heading, table name, or XBRL concept + period
    quote: str | None = None
    kind: str = "filing_passage"  # filing_passage | xbrl_fact
    xbrl_concept: str | None = None
    period_end: str | None = None


@dataclass
class Annotation:
    """One independent reviewer's judgement of one claim."""

    claim_id: str
    reviewer_id: str
    gold_label: str
    reviewer_type: str = "human"
    supporting_evidence: list[dict] = field(default_factory=list)
    contradictory_evidence: list[dict] = field(default_factory=list)
    review_notes: str | None = None
    annotated_at: str | None = None
    guideline_version: str | None = None
    time_spent_minutes: float | None = None

    def __post_init__(self):
        if self.gold_label not in LABELS:
            raise SchemaError(f"{self.claim_id}/{self.reviewer_id}: gold_label must be one of {LABELS}")
        if self.reviewer_type != "human":
            raise SchemaError(f"{self.claim_id}: only human reviewers may create gold annotations "
                              f"(reviewer_type={self.reviewer_type!r})")
        if re.match(r"(?i)^(claude|gpt|llm|model|ai)[-_:]", self.reviewer_id or ""):
            raise SchemaError(f"{self.claim_id}: reviewer_id {self.reviewer_id!r} looks like a model; "
                              "the model under evaluation must not label its own ground truth")
        for ev in self.supporting_evidence + self.contradictory_evidence:
            EvidenceRef(**ev)


@dataclass
class Adjudication:
    claim_id: str
    adjudicator_id: str
    final_label: str
    decision_notes: str
    adjudicated_at: str | None = None
    considered_reviewers: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.final_label not in LABELS:
            raise SchemaError(f"{self.claim_id}: final_label must be one of {LABELS}")
        if not (self.decision_notes or "").strip():
            raise SchemaError(f"{self.claim_id}: an adjudication must record why")


def empty_prediction(claim: ClaimInput, approach: str) -> dict:
    """The structured output every approach returns (task section 3)."""
    return {
        "claim_id": claim.claim_id,
        "approach": approach,
        "predicted_label": None,
        "initial_label": None,
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "reasoning_summary": "",
        "citations": [],
        "investigation_trace_id": None,
        "token_usage": {"input": 0, "output": 0},
        "latency_ms": 0,
        "estimated_cost_usd": 0.0,
        "llm_calls": 0,
        "stop_reason": None,
        "error": None,
    }
