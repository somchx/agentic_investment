"""Evidence ledger + citation verification for the shared investigation engine.

Every tool result that carries a checkable source (an XBRL fact, a derived
metric, a filing passage, a filing record, a price quote, a stored portfolio
record) is registered here as an EvidenceUnit with a run-local id ("E1",
"E2", ...). The model never writes a citation itself -- it can only point a
claim at ids the ledger issued, and `verify_claims` then checks, without any
LLM, that each cited unit:

- exists (no invented references),
- was knowable at the analysis date (no future-data leakage),
- belongs to the company the claim is about,
- actually contains the numbers the claim states (numeric claims), and
- contains the quoted passage verbatim (causal / management claims).

Having a citation is therefore not treated as proof of support: the number
or the quote has to be found in the cited source. What this cannot check is
paraphrase-level meaning -- a quote that is present but used out of context
still passes. That residual gap is reported as a known limitation, not
hidden.
"""

import re
from dataclasses import asdict, dataclass, field

CLAIM_TYPES = ("numeric", "management_attribution", "causal_interpretation", "uncertainty")
CLAIM_STATUSES = ("SUPPORTED", "CONTRADICTED", "NOT_ESTABLISHED")
NARRATIVE_CLAIM_TYPES = ("management_attribution", "causal_interpretation")


@dataclass
class EvidenceUnit:
    kind: str  # xbrl_fact | derived_metric | filing_passage | filing_record | price_quote | portfolio_record | thesis_snapshot | stored_assessment
    ticker: str | None = None
    source: str = "SEC EDGAR"
    accession_number: str | None = None
    form: str | None = None
    filed: str | None = None  # publication date; the point-in-time cutoff
    period_start: str | None = None
    period_end: str | None = None
    source_url: str | None = None
    locator: str | None = None  # XBRL tag + period, or a passage anchor
    excerpt: str | None = None
    values: list[float] = field(default_factory=list)
    unit: str | None = None
    evidence_id: str = ""

    def key(self) -> tuple:
        return (self.kind, self.ticker, self.accession_number, self.locator, self.excerpt[:80] if self.excerpt else None,
                tuple(self.values))

    def public(self) -> dict:
        d = asdict(self)
        if d["excerpt"] and len(d["excerpt"]) > 1200:
            d["excerpt"] = d["excerpt"][:1200] + "…"
        return d


class EvidenceLedger:
    def __init__(self):
        self.units: dict[str, EvidenceUnit] = {}
        self._by_key: dict[tuple, str] = {}

    def add(self, unit: EvidenceUnit) -> str:
        k = unit.key()
        if k in self._by_key:
            return self._by_key[k]
        unit.evidence_id = f"E{len(self.units) + 1}"
        self.units[unit.evidence_id] = unit
        self._by_key[k] = unit.evidence_id
        return unit.evidence_id

    def get(self, evidence_id: str) -> EvidenceUnit | None:
        return self.units.get(evidence_id)

    def public(self) -> list[dict]:
        return [u.public() for u in self.units.values()]


# ---------------------------------------------------------------- numbers

_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")
# ASCII-only letter guards: "424B5" / "10-K" are form names, not figures, but
# Thai text often has no space around numbers ("โต16.4%"), so a Thai letter
# next to a number must not hide it from the check.
_NUMBER = re.compile(r"(?<![A-Za-z\d.,])([-+−]?\d[\d,]*(?:\.\d+)?)(?![A-Za-z\d])\s*(%|percent|เปอร์เซ็นต์)?")
_FISCAL = re.compile(r"\b(?:Q[1-4]|FY|fiscal)\s*\d{2,4}\b|\b\d{4}\s*(?:Q[1-4])\b", re.I)


def stated_numbers(text: str) -> list[tuple[float, bool]]:
    """Material numbers in a claim: (value, is_percent). Dates, fiscal labels,
    bare years and small counts ("3 holdings", "2 of 3 rules") are skipped --
    they are not financial figures the source has to contain."""
    cleaned = _FISCAL.sub(" ", _DATE.sub(" ", text))
    out = []
    for m in _NUMBER.finditer(cleaned):
        raw, pct = m.group(1), bool(m.group(2))
        try:
            v = float(raw.replace(",", "").replace("−", "-"))
        except ValueError:
            continue
        has_fraction = "." in raw
        if not pct and not has_fraction and "," not in raw:
            if abs(v) < 100 or (1900 <= v <= 2100):
                continue
        out.append((v, pct))
    return out


def _decimals(value: float) -> int:
    s = repr(abs(value))
    return len(s.split(".")[1]) if "." in s and not s.endswith(".0") else 0


def _matches(stated: float, is_percent: bool, source_values: list[float]) -> bool:
    """A stated figure matches a source value if it is that value, rounded the
    way people write it: as a percent (ratios), or in thousands / millions /
    billions (USD amounts). Tolerance is half a unit of the stated precision."""
    tol = 0.5 * 10 ** -_decimals(stated) + 1e-9
    for v in source_values:
        candidates = [v * 100] if is_percent else [v, v / 1e3, v / 1e6, v / 1e9, v * 100]
        for c in candidates:
            if abs(abs(c) - abs(stated)) <= max(tol, abs(c) * 0.0005):
                return True
    return False


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


# ---------------------------------------------------------------- verify

def verify_claims(claims: list[dict], ledger: EvidenceLedger, analysis_date: str) -> tuple[list[dict], list[str]]:
    """Returns (per-claim verification records, problems). An empty problem
    list means every SUPPORTED / CONTRADICTED claim is backed by eligible
    evidence that actually contains what the claim says."""
    records, problems = [], []
    seen = set()
    for claim in claims:
        cid = str(claim.get("claim_id") or "")
        status = claim.get("status")
        ctype = claim.get("claim_type")
        ids = [str(i) for i in claim.get("evidence_ids") or []]
        issues = []
        if not cid or cid in seen:
            issues.append("DUPLICATE_OR_MISSING_CLAIM_ID")
        seen.add(cid)
        if ctype not in CLAIM_TYPES:
            issues.append("UNKNOWN_CLAIM_TYPE")
        if status not in CLAIM_STATUSES:
            issues.append("UNKNOWN_CLAIM_STATUS")

        units = []
        for eid in ids:
            unit = ledger.get(eid)
            if unit is None:
                issues.append(f"UNKNOWN_EVIDENCE_ID:{eid}")
                continue
            units.append(unit)
            if unit.filed and unit.filed > analysis_date:
                issues.append(f"FUTURE_EVIDENCE:{eid}")
            if claim.get("ticker") and unit.ticker and unit.ticker != str(claim["ticker"]).upper():
                issues.append(f"TICKER_MISMATCH:{eid}")

        if status in ("SUPPORTED", "CONTRADICTED"):
            if not ids:
                issues.append("NO_EVIDENCE")
            if ctype == "numeric" and units:
                values = [v for u in units for v in u.values]
                for stated, pct in stated_numbers(claim.get("proposition", "")):
                    if not _matches(stated, pct, values):
                        issues.append(f"NUMBER_NOT_IN_EVIDENCE:{stated:g}{'%' if pct else ''}")
            if ctype in NARRATIVE_CLAIM_TYPES and status == "SUPPORTED":
                passages = [u for u in units if u.kind == "filing_passage"]
                quote = _norm(claim.get("quoted_span", ""))
                if not passages:
                    issues.append("NARRATIVE_CLAIM_WITHOUT_FILING_PASSAGE")
                elif len(quote) < 12:
                    issues.append("QUOTED_SPAN_REQUIRED")
                elif not any(quote in _norm(p.excerpt) for p in passages):
                    issues.append("QUOTED_SPAN_NOT_IN_CITED_PASSAGE")

        records.append({"claim_id": cid, "verified": not issues, "issues": issues})
        problems += [f"{cid or '?'}: {i}" for i in issues]
    return records, problems
