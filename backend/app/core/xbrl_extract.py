"""Turn raw SEC company-facts JSON into a clean list of quarterly Facts.

XBRL company-facts mixes quarterly and year-to-date/full-year durations for
the same tag, and the same fiscal quarter is often reported multiple times
across successive filings (originally, then again as a prior-year comparative,
sometimes restated). This module filters down to single-quarter periods and
keeps every reported version so restatements are visible as evidence rather
than silently overwritten.
"""

from datetime import date

from models import Fact

# Preference order: try each tag until one has data. XBRL tag usage varies
# by company and by year (Apple switched from SalesRevenueNet to
# RevenueFromContractWithCustomerExcludingAssessedTax around 2018).
METRIC_TAGS = {
    "Revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "OperatingIncome": [
        "OperatingIncomeLoss",
    ],
}

# Balance-sheet metrics are reported as an "instant" snapshot (only an `end`
# date, no `start`/duration) rather than over a period, so they need their
# own extraction path -- see extract_instant_facts().
INSTANT_METRIC_TAGS = {
    "LongTermDebt": [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
    ],
}


def _is_single_quarter(period_start: str, period_end: str) -> bool:
    start = date.fromisoformat(period_start)
    end = date.fromisoformat(period_end)
    days = (end - start).days
    return 80 <= days <= 100


def list_available_tags(facts_json: dict) -> list[dict]:
    """Every us-gaap tag this specific company has actually reported, for
    the custom-reason picker (webapp.py's /api/xbrl-tags/<ticker>) -- the
    dropdown is built from this, not free text, so a custom reason can
    never reference a tag that doesn't exist for the company (the "no facts
    found" failure mode this whole feature exists to avoid).

    `quarterly` / `instant` say which extraction path (extract_quarterly_
    facts_for_tag / extract_instant_facts_for_tag) will actually find data
    for this tag -- a tag can support both if it's ever been reported both
    ways.
    """
    us_gaap = facts_json.get("facts", {}).get("us-gaap", {})
    out = []
    for tag, tag_data in us_gaap.items():
        has_quarterly = False
        has_instant = False
        for entries in tag_data.get("units", {}).values():
            for e in entries:
                start, end = e.get("start"), e.get("end")
                if start and end and _is_single_quarter(start, end):
                    has_quarterly = True
                elif end and not start and e.get("form") in ("10-Q", "10-K"):
                    has_instant = True
            if has_quarterly and has_instant:
                break
        if has_quarterly or has_instant:
            out.append({
                "tag": tag,
                "label": tag_data.get("label") or tag,
                "quarterly": has_quarterly,
                "instant": has_instant,
            })
    out.sort(key=lambda t: t["tag"])
    return out


def extract_quarterly_facts(facts_json: dict, cik: str, metric: str) -> list[Fact]:
    """Return every quarterly Fact reported for `metric`, across all filings.

    `metric` must be a key in METRIC_TAGS. Multiple Facts can share the same
    period_end if a later filing restated the number — callers that need a
    single value per quarter should pick the latest by `filed` date, but
    should also check for large discrepancies as conflicting evidence.
    """
    return _extract_quarterly_from_tags(facts_json, cik, metric, METRIC_TAGS[metric])


def extract_quarterly_facts_for_tag(facts_json: dict, cik: str, tag: str) -> list[Fact]:
    """Same as extract_quarterly_facts, but for a single raw XBRL tag rather
    than a curated METRIC_TAGS entry -- the custom-reason path (a user picks
    one exact tag from list_available_tags(), so there's no tag-migration-
    over-time list to merge; the tag itself is a single string).
    """
    return _extract_quarterly_from_tags(facts_json, cik, tag, [tag])


def _extract_quarterly_from_tags(facts_json: dict, cik: str, metric_label: str, tags: list[str]) -> list[Fact]:
    us_gaap = facts_json.get("facts", {}).get("us-gaap", {})

    # Companies switch which XBRL tag they report a metric under over time
    # (e.g. Apple: SalesRevenueNet until ~2018, then
    # RevenueFromContractWithCustomerExcludingAssessedTax after). No single
    # tag covers the whole history, and "whichever tag has the most data
    # points" is also wrong -- a tag used briefly for a one-off footnote
    # disclosure, or retired years ago, can outscore the tag currently in
    # use. So tags are tried in priority order and merged. The one case that
    # must NOT be merged: two tags both reporting the same period *within
    # the same filing* (accession number) -- that means the company tagged
    # two different concepts that happen to share a period, not two
    # versions of the same number (see extract_instant_facts' docstring for
    # the debt example this was found on). Two tags reporting the same
    # period from *different* filings, on the other hand, is exactly what a
    # genuine restatement across a tag migration looks like (confirmed with
    # Microsoft's ASC 606 SalesRevenueNet -> RevenueFromContractWithCustomer
    # switch) and must be kept as conflicting evidence, not deduped away.
    covered_accn_periods: set[tuple[str, str]] = set()
    facts: list[Fact] = []
    for tag in tags:
        tag_data = us_gaap.get(tag)
        if not tag_data:
            continue
        tag_facts: list[Fact] = []
        for unit, entries in tag_data.get("units", {}).items():
            for e in entries:
                start = e.get("start")
                end = e.get("end")
                if not start or not end or not _is_single_quarter(start, end):
                    continue
                accn = e.get("accn", "")
                if (accn, end) in covered_accn_periods:
                    continue
                tag_facts.append(
                    Fact(
                        metric=metric_label,
                        period_start=start,
                        period_end=end,
                        value=float(e["val"]),
                        unit=unit,
                        fiscal_year=e.get("fy"),
                        fiscal_period=e.get("fp", ""),
                        form=e.get("form", ""),
                        accession_number=accn,
                        filed=e.get("filed", ""),
                        cik=cik,
                    )
                )
        facts.extend(tag_facts)
        covered_accn_periods.update((f.accession_number, f.period_end) for f in tag_facts)

    facts.sort(key=lambda f: (f.period_end, f.filed))
    return facts


def extract_instant_facts(facts_json: dict, cik: str, metric: str) -> list[Fact]:
    """Return every quarter-end snapshot reported for an instant (balance-sheet)
    metric, across all filings. See extract_quarterly_facts() for why every
    reported version is kept rather than just the latest.

    `metric` must be a key in INSTANT_METRIC_TAGS. period_start is set equal
    to period_end (there's no duration for an instant fact) -- callers only
    use period_end and filed.

    Tags are merged in priority order, and -- same reasoning as
    extract_quarterly_facts -- a lower-priority tag's entry is only dropped
    when it duplicates a period already reported *within the same filing* by
    a higher-priority tag; the same period reported by a different tag in a
    different filing is kept as a potential restatement. This was found to
    matter in practice: Microsoft's 10-K reports both `LongTermDebtNoncurrent`
    ($31.1B, excludes the portion of debt due within a year) and
    `LongTermDebt` ($40.3B, includes it) for the same quarter-end, in the
    same filing. Naively merging both as if they were two versions of the
    same number produced a spurious ~30% "restatement conflict" that was
    actually just two different, both-correct accounting concepts reported
    side by side.
    """
    return _extract_instant_from_tags(facts_json, cik, metric, INSTANT_METRIC_TAGS[metric])


def extract_instant_facts_for_tag(facts_json: dict, cik: str, tag: str) -> list[Fact]:
    """Same as extract_instant_facts, but for a single raw XBRL tag -- the
    custom-reason path. See extract_quarterly_facts_for_tag()."""
    return _extract_instant_from_tags(facts_json, cik, tag, [tag])


def _extract_instant_from_tags(facts_json: dict, cik: str, metric_label: str, tags: list[str]) -> list[Fact]:
    us_gaap = facts_json.get("facts", {}).get("us-gaap", {})

    covered_accn_periods: set[tuple[str, str]] = set()
    facts: list[Fact] = []
    for tag in tags:
        tag_data = us_gaap.get(tag)
        if not tag_data:
            continue
        tag_facts: list[Fact] = []
        for unit, entries in tag_data.get("units", {}).items():
            for e in entries:
                end = e.get("end")
                if not end or e.get("start"):  # instant facts have no `start`
                    continue
                if e.get("form") not in ("10-Q", "10-K"):
                    continue
                accn = e.get("accn", "")
                if (accn, end) in covered_accn_periods:
                    continue
                tag_facts.append(
                    Fact(
                        metric=metric_label,
                        period_start=end,
                        period_end=end,
                        value=float(e["val"]),
                        unit=unit,
                        fiscal_year=e.get("fy"),
                        fiscal_period=e.get("fp", ""),
                        form=e.get("form", ""),
                        accession_number=e.get("accn", ""),
                        filed=e.get("filed", ""),
                        cik=cik,
                    )
                )
        facts.extend(tag_facts)
        covered_accn_periods.update((f.accession_number, f.period_end) for f in tag_facts)

    facts.sort(key=lambda f: (f.period_end, f.filed))
    return facts


def facts_as_of(facts: list[Fact], as_of_date: str) -> list[Fact]:
    """Point-in-time filter: only Facts from filings published on/before as_of_date.

    This is the mechanism that prevents lookahead bias — a Fact filed after
    the simulated "today" simply does not exist yet as far as the Agent is
    concerned.
    """
    return [f for f in facts if f.filed <= as_of_date]


def latest_version_per_quarter(facts: list[Fact]) -> dict[str, list[Fact]]:
    """Group Facts by period_end, preserving every reported version in filed order.

    facts must already be point-in-time filtered via facts_as_of() first.
    """
    by_quarter: dict[str, list[Fact]] = {}
    for f in facts:
        by_quarter.setdefault(f.period_end, []).append(f)
    for versions in by_quarter.values():
        versions.sort(key=lambda f: f.filed)
    return by_quarter
