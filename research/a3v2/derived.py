"""Deterministic derived figures the v1 numeric verifier cannot compute.
Inputs come from SEC XBRL facts filed on or before the cutoff (the same
extraction as A2); the result is registered in the run's evidence ledger as a
`derived_metric` unit, so a reviewer or the guard can cite it like any fact.

Implemented: free cash flow = operating cash flow - purchases of property and
equipment (MSFT-12 in v1 was lost because nobody computed it)."""

from engine.numeric import _prior_value, _value_at

from evidence_ledger import EvidenceUnit  # noqa: E402

from .schemas import Computation

DERIVED_VERSION = "a3v2-derived-0.1"


def free_cash_flow(ticker: str, cutoff: str, basis: str, period_end: str | None) -> dict:
    """{'status', 'current', 'prior', 'change', 'inputs'} -- figures in USD.
    UNAVAILABLE when either input is missing for either period."""
    ocf, ocf_f, _, end = _value_at(ticker, "OperatingCashFlow", basis, cutoff, period_end)
    capex, capex_f, _, capex_end = _value_at(ticker, "CapitalExpenditure", basis, cutoff, period_end)
    if ocf is None or capex is None or end != capex_end:
        return {"status": "UNAVAILABLE", "current": None, "prior": None, "change": None, "period_end": end, "inputs": []}
    p_ocf, p_ocf_f = _prior_value(ticker, "OperatingCashFlow", basis, cutoff, end)
    p_capex, p_capex_f = _prior_value(ticker, "CapitalExpenditure", basis, cutoff, end)
    cur = ocf - capex
    prior = p_ocf - p_capex if p_ocf is not None and p_capex is not None else None
    inputs = [*ocf_f, *capex_f, *p_ocf_f, *p_capex_f]
    return {"status": "OK" if prior is not None else "NO_PRIOR", "current": cur, "prior": prior,
            "change": None if prior is None else cur - prior, "period_end": end,
            "prior_period_end": p_ocf_f[0]["period_end"] if p_ocf_f else None, "inputs": inputs}


def render(result: dict) -> str:
    m = lambda x: f"{x / 1e6:,.0f}"
    s = f"Free cash flow (operating cash flow minus purchases of property and equipment) for the period ended {result['period_end']}: ${m(result['current'])} million"
    if result.get("prior") is not None:
        s += f"; same period a year earlier ({result['prior_period_end']}): ${m(result['prior'])} million; change ${m(result['change'])} million"
    return s + "."


def run_computation(ledger, claim, comp: Computation) -> dict:
    """Execute one requested computation and register it as evidence."""
    if comp.get("metric") != "FreeCashFlow":
        return {"computation_id": comp.get("computation_id"), "status": "UNSUPPORTED_METRIC", "evidence_id": None}
    r = free_cash_flow(claim.company, claim.as_of_date, comp.get("basis") or "quarter", comp.get("period_end"))
    if r["status"] == "UNAVAILABLE":
        return {"computation_id": comp.get("computation_id"), "status": "UNAVAILABLE", "evidence_id": None}
    first = r["inputs"][0]
    eid = ledger.add(EvidenceUnit(
        kind="derived_metric", ticker=claim.company, accession_number=first["accession_number"], form=first["form"],
        filed=max(f["filed"] for f in r["inputs"]), period_start=first.get("period_start"), period_end=r["period_end"],
        source_url=first.get("source_url"), locator=f"FreeCashFlow {comp.get('basis')} {r['period_end']} ({DERIVED_VERSION})",
        excerpt=render(r), values=[v for v in (r["current"], r["prior"], r["change"]) if v is not None], unit="USD"))
    return {"computation_id": comp.get("computation_id"), "status": r["status"], "evidence_id": eid,
            "current": r["current"], "prior": r["prior"], "change": r["change"],
            "inputs": [{k: f[k] for k in ("metric", "period_end", "value", "accession_number")} for f in r["inputs"]]}
