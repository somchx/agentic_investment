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

    def _conflicts_with_primary(v: Fact) -> bool:
        if v.value == 0 and primary.value == 0:
            return False  # both zero -- not a conflict, and avoids 0/0
        if primary.value == 0:
            # Went from a nonzero earlier value to zero (or vice versa) --
            # a real, material discrepancy, but the usual relative-difference
            # formula divides by primary.value and would crash here
            # (reproduced: ZeroDivisionError, found via external code audit).
            return v.value != 0
        return abs(v.value - primary.value) / abs(primary.value) > RESTATEMENT_TOLERANCE

    conflicts = [v for v in versions[:-1] if _conflicts_with_primary(v)]
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
    if reason.rule_definition:
        return evaluate_structured(reason, all_facts, None, as_of_date)
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
    if reason.rule_definition:
        return evaluate_structured(reason, numerator_facts, denominator_facts, as_of_date)
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


def evaluate_structured(reason, all_facts, denominator_facts, as_of_date):
    """Evaluate confirmed v1 definitions; comparisons never divide by prior values."""
    import math
    rule = reason.rule_definition
    if rule.get('thesis_type') == 'NATURAL_LANGUAGE':
        return Evaluation(reason, as_of_date, 'Not enough data', None, explanation='Qualitative thesis: numeric rule NOT_EVALUATED. Investigate confirmed claims separately.')
    mode = rule['mode']
    annual = rule['evaluation_period'] == 'annual'
    def missing(message, future=False):
        ev = Evaluation(reason, as_of_date, 'Not enough data', None, explanation=message)
        ev.not_yet_observable = future
        return ev
    def period_valid(f):
        try:
            if f.form not in ('10-Q', '10-K') or not f.filed or not f.accession_number:
                return False
            if reason.instant:
                return not f.period_start or f.period_start == f.period_end
            days = (date.fromisoformat(f.period_end) - date.fromisoformat(f.period_start)).days
            return (350 <= days <= 380) if annual else (80 <= days <= 100)
        except (ValueError, TypeError):
            return False
    eligible = [f for f in all_facts if period_valid(f)]
    # Requested cadence may not silently use YTD or a different duration.
    available = facts_as_of(eligible, as_of_date)
    by = latest_version_per_quarter(available)
    current_q = _latest_quarter_on_or_before(by, as_of_date)
    if current_q is None:
        future = any(f.period_end <= as_of_date < f.filed for f in eligible)
        return missing('No eligible published facts for this evaluation period.', future)
    current, conflicts = _pick_primary_and_conflicts(by[current_q])
    selected = [current]
    prior = None
    if mode in ('value_comparison', 'margin_comparison', 'yoy_growth'):
        candidates = [q for q in by if abs((date.fromisoformat(current_q)-date.fromisoformat(q)).days-365) <= 8]
        prior_q = min(candidates, key=lambda q: abs((date.fromisoformat(current_q)-date.fromisoformat(q)).days-365)) if candidates else None
        if prior_q is None:
            return missing('Missing comparable same-period prior-year fact.')
        prior, extra = _pick_primary_and_conflicts(by[prior_q]); conflicts += extra
        if not reason.instant:
            days_current = (date.fromisoformat(current.period_end)-date.fromisoformat(current.period_start)).days
            days_prior = (date.fromisoformat(prior.period_end)-date.fromisoformat(prior.period_start)).days
            if abs(days_current-days_prior) > 8:
                return missing('Period duration mismatch between current and comparative.')
        selected.append(prior)
    if mode in ('margin_comparison', 'margin_level'):
        dens = latest_version_per_quarter(facts_as_of([f for f in (denominator_facts or []) if period_valid(f)], as_of_date))
        margins=[]
        for num in list(selected):
            candidates=[f for f in dens.get(num.period_end, []) if f.period_start == num.period_start]
            den, extra = _pick_primary_and_conflicts(candidates)
            if den is None:
                return missing('Missing same-start and same-end revenue denominator.')
            if den.unit != num.unit or den.value <= 0:
                return missing('Margin requires matching units and positive revenue.')
            selected.append(den); conflicts += extra
            margins.append(num.value / den.value)
        left=margins[0]; right=margins[1] if mode == 'margin_comparison' else reason.threshold
    elif mode == 'positive_level':
        left=current.value;right=0.0
    elif mode == 'value_comparison':
        left=current.value;right=prior.value
    else:
        if prior.value <= 0:
            return missing('YoY percent requires a positive prior value; use a directional comparison for zero/negative bases.')
        left=(current.value-prior.value)/prior.value;right=reason.threshold
    if any(f.unit != 'USD' or not math.isfinite(f.value) for f in selected):
        return missing('All operands must be finite consolidated USD facts; unit mismatch or unsupported currency.')
    if len({f.cik for f in selected}) != 1:
        return missing('Company scope mismatch.')
    if not math.isfinite(left) or right is None or not math.isfinite(right):
        return missing('Nonfinite or missing comparison operand.')
    holds={'>':left>right, '>=':left>=right, '<':left<right, '<=':left<=right}[reason.comparison]
    ev=Evaluation(reason,as_of_date,'Supported' if holds else 'Broken',left,
                  supporting_evidence=selected,conflicting_evidence=conflicts,
                  explanation=f"{rule['preview']}; {left:,.6g} {reason.comparison} {right:,.6g}; period {current.period_start or 'instant'} to {current.period_end}. "
                              'Mathematical result only; causal explanation requires separate evidence.')
    ev.comparison_value=right
    ev.value_unit=rule['unit']
    ev.calculation_trace={'mode':mode,'left':left,'operator':reason.comparison,'right':right,
                          'period':rule['evaluation_period'],
                          'operands':[{'value':f.value,'unit':f.unit,'start':f.period_start,'end':f.period_end,
                                       'filed':f.filed,'accession':f.accession_number,'source_url':f.source_url} for f in selected]}
    return ev
