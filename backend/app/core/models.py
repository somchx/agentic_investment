"""Core data structures for the Phase 1 thin vertical slice.

A `Fact` is a single point-in-time number pulled from an SEC filing.
A `Reason` is a numeric investment assumption to be revalidated.
An `Evaluation` is the outcome of checking a Reason as-of a given date,
grounded in the specific Facts used to reach that conclusion.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Fact:
    """One reported value for a financial metric, as filed with the SEC."""

    metric: str  # e.g. "Revenue"
    period_start: str  # ISO date, start of the reporting period
    period_end: str  # ISO date, end of the reporting period (fiscal quarter end)
    value: float
    unit: str
    fiscal_year: int
    fiscal_period: str  # "Q1", "Q2", "Q3", "Q4", "FY"
    form: str  # "10-Q" or "10-K"
    accession_number: str
    filed: str  # ISO date the filing was published — the point-in-time cutoff
    cik: str = ""

    @property
    def source_url(self) -> str:
        """Link to the EDGAR filing index page this fact was reported in."""
        if not self.cik:
            return ""
        accn_nodash = self.accession_number.replace("-", "")
        cik_nozero = str(int(self.cik))
        return (
            f"https://www.sec.gov/Archives/edgar/data/{cik_nozero}/"
            f"{accn_nodash}/{self.accession_number}-index.htm"
        )

    def label(self) -> str:
        return (
            f"{self.metric} {self.period_end} = {self.value:,.0f} {self.unit} "
            f"(filed {self.filed}, {self.form}, accn {self.accession_number})"
        )


@dataclass(frozen=True)
class Reason:
    """A numeric investment assumption, e.g. 'Revenue growth > 10% YoY'.

    kind="yoy_growth"   -> growth of `metric` vs the same quarter last year
    kind="margin_level" -> ratio of `metric` (numerator) to `denominator_metric`
                            for the current quarter, compared to `threshold`
    """

    reason_id: str
    company: str
    metric: str
    comparison: str  # ">", ">=", "<", "<="
    threshold: float  # as a ratio, e.g. 0.10 for 10%
    kind: str = "yoy_growth"
    denominator_metric: str = ""
    description: str = ""
    # True for a balance-sheet/instant concept (e.g. LongTermDebt -- a
    # snapshot with no duration), False for a duration/quarterly-flow
    # concept (e.g. Revenue). Built-in reasons set this explicitly in
    # tools.REASON_DEFS; custom reasons derive it from which shape the
    # picked XBRL tag actually reports (xbrl_extract.list_available_tags).
    instant: bool = False
    # Raw XBRL tag name, set only for custom (DB-backed) reasons -- built-in
    # reasons instead go through the curated METRIC_TAGS/INSTANT_METRIC_TAGS
    # multi-tag lookup in xbrl_extract.py, keyed by `metric`.
    is_custom: bool = False


@dataclass
class Evaluation:
    """Result of checking one Reason as-of one simulated date."""

    reason: Reason
    as_of_date: str
    status: str  # "Supported" | "Weakened" | "Broken" | "Not enough data" | "Conflicting"
    computed_value: float | None
    supporting_evidence: list[Fact] = field(default_factory=list)
    conflicting_evidence: list[Fact] = field(default_factory=list)
    explanation: str = ""
