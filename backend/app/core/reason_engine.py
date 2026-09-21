"""Contribution 1 + 2 domain logic: evaluate one numeric Reason as-of one date.

This is deliberately NOT an agent framework. It is the piece of logic that
IS the research contribution for Phase 1: given a Reason and a simulated
"today", find the relevant point-in-time evidence, check whether more than
one version of a number was ever reported for the same period (a numeric
stand-in for "evidence conflict"), and derive a Supported / Weakened /
Broken / Not enough data verdict with citations attached.
"""

from datetime import date, timedelta

from models import Evaluation, Fact, Reason
from xbrl_extract import facts_as_of, latest_version_per_quarter

RESTATEMENT_TOLERANCE = 0.005  # 0.5% — differences smaller than this are rounding noise


def _pick_primary_and_conflicts(versions: list[Fact]) -> tuple[Fact | None, list[Fact]]:
    """Given every reported version of one quarter's number (oldest filed first),
    return the most authoritative one plus any earlier versions that materially
    disagree with it — this is the numeric "conflicting evidence" signal.
    """
    if not versions:
        return None, []
    primary = versions[-1]  # most recently filed = most authoritative
    conflicts = [
        v
        for v in versions[:-1]
        if v.value != 0
        and abs(v.value - primary.value) / abs(primary.value) > RESTATEMENT_TOLERANCE
    ]
    return primary, conflicts


def _latest_quarter_on_or_before(by_quarter: dict[str, list[Fact]], as_of_date: str) -> str | None:
    eligible = [q for q in by_quarter if q <= as_of_date]
    return max(eligible) if eligible else None


def _find_prior_year_quarter(by_quarter: dict[str, list[Fact]], current_q: str) -> str | None:
    """Find the quarter-end ~1 year before current_q.

    Fiscal quarter-end dates drift year to year (e.g. Apple's Q1 ends the
    Saturday nearest a fixed date), so this matches by nearest date within a
    tolerance window instead of exact month/day subtraction.
    """
    current = date.fromisoformat(current_q)
    target = current - timedelta(days=365)
    window = timedelta(days=35)

    candidates = [
        q for q in by_quarter
        if q != current_q and abs(date.fromisoformat(q) - target) <= window
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda q: abs(date.fromisoformat(q) - target))


def _classify(comparison: str, computed: float, threshold: float) -> str:
    holds = {
        ">": computed > threshold,
        ">=": computed >= threshold,
        "<": computed < threshold,
        "<=": computed <= threshold,
    }[comparison]

    if holds:
        return "Supported"

    # "Weakened" = wrong side of the threshold but within a defensible
    # buffer of it; "Broken" = a severe miss. The buffer is proportional to
    # the threshold itself (50% either direction) rather than an absolute
    # zero cutoff, so the boundary means the same thing for every reason.
    #
    # An earlier version used "still positive" (computed >= 0) as the cutoff
    # for >/>= reasons, which meant a 0.5% margin against a 20% threshold
    # was classified identically to a 19.9% margin -- both merely "still
    # positive" -- with no way to justify the boundary if asked. Proportional
    # buffers answer that: Weakened means "still cleared at least half of
    # what was required" (>=) or "missed by no more than half again" (<),
    # the same 50% rule in both directions.
    if comparison in (">", ">="):
        return "Weakened" if computed >= threshold * 0.5 else "Broken"
    return "Weakened" if computed <= threshold * 1.5 else "Broken"


def evaluate_yoy_growth(reason: Reason, all_facts: list[Fact], as_of_date: str) -> Evaluation:
    pit_facts = facts_as_of(all_facts, as_of_date)
    by_quarter = latest_version_per_quarter(pit_facts)

    current_q = _latest_quarter_on_or_before(by_quarter, as_of_date)
    if current_q is None:
        return Evaluation(reason, as_of_date, "Not enough data", None,
                           explanation="No filings available yet as of this date.")

    prior_q = _find_prior_year_quarter(by_quarter, current_q)
    if prior_q is None:
        return Evaluation(reason, as_of_date, "Not enough data", None,
                           explanation=f"Missing prior-year comparative for quarter ending {current_q}.")

    current_primary, current_conflicts = _pick_primary_and_conflicts(by_quarter[current_q])
    prior_primary, prior_conflicts = _pick_primary_and_conflicts(by_quarter[prior_q])
    conflicts = current_conflicts + prior_conflicts

    if prior_primary.value == 0:
        return Evaluation(reason, as_of_date, "Not enough data", None,
                           explanation="Prior-year value is zero; growth rate undefined.")

    growth = (current_primary.value - prior_primary.value) / abs(prior_primary.value)
    status = _classify(reason.comparison, growth, reason.threshold)

    explanation = (
        f"{reason.metric} {current_q} = {current_primary.value:,.0f} vs "
        f"{prior_q} = {prior_primary.value:,.0f} -> YoY growth = {growth:+.1%} "
        f"(reason requires {reason.comparison} {reason.threshold:.0%})."
    )
    if conflicts:
        explanation += (
            f" Note: {len(conflicts)} earlier-filed version(s) of this period's number "
            f"disagreed with the figure used here by more than {RESTATEMENT_TOLERANCE:.1%}; "
            f"the most recently filed value was treated as authoritative."
        )

    return Evaluation(
        reason=reason,
        as_of_date=as_of_date,
        status=status,
        computed_value=growth,
        supporting_evidence=[current_primary, prior_primary],
        conflicting_evidence=conflicts,
        explanation=explanation,
    )


def evaluate_margin_level(
    reason: Reason,
    numerator_facts: list[Fact],
    denominator_facts: list[Fact],
    as_of_date: str,
) -> Evaluation:
    num_pit = facts_as_of(numerator_facts, as_of_date)
    den_pit = facts_as_of(denominator_facts, as_of_date)
    num_by_q = latest_version_per_quarter(num_pit)
    den_by_q = latest_version_per_quarter(den_pit)

    current_q = _latest_quarter_on_or_before(num_by_q, as_of_date)
    if current_q is None or current_q not in den_by_q:
        return Evaluation(reason, as_of_date, "Not enough data", None,
                           explanation="Missing numerator or denominator data for the latest quarter.")

    num_primary, num_conflicts = _pick_primary_and_conflicts(num_by_q[current_q])
    den_primary, den_conflicts = _pick_primary_and_conflicts(den_by_q[current_q])
    conflicts = num_conflicts + den_conflicts

    if den_primary.value == 0:
        return Evaluation(reason, as_of_date, "Not enough data", None,
                           explanation="Denominator is zero; margin undefined.")

    margin = num_primary.value / den_primary.value
    status = _classify(reason.comparison, margin, reason.threshold)

    explanation = (
        f"{reason.metric}/{reason.denominator_metric} for {current_q}: "
        f"{num_primary.value:,.0f} / {den_primary.value:,.0f} = {margin:.1%} "
        f"(reason requires {reason.comparison} {reason.threshold:.0%})."
    )
    if conflicts:
        explanation += f" Note: {len(conflicts)} conflicting earlier-filed value(s) found."

    return Evaluation(
        reason=reason,
        as_of_date=as_of_date,
        status=status,
        computed_value=margin,
        supporting_evidence=[num_primary, den_primary],
        conflicting_evidence=conflicts,
        explanation=explanation,
    )
