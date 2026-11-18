"""Deterministic contribution checks for "primarily driven by X" and "X was the
largest factor" claims (A3 v2.2 preparation, item 3). Pure functions: the
figures come from elsewhere (an extraction step that is not built yet, or a
filing passage parsed by `parse_bp_bridge`), so nothing here is wired into the
graph and no v2.0-v2.1.1 behaviour changes.

    primarily_driven(component_change, total_change)
        TRUE      component explains > PRIMARY_SHARE of a same-sign total change
        FALSE     it explains <= PRIMARY_SHARE, or moves against the total
        UNVERIFIABLE  missing figures or a zero total change
    largest_factor(bridge, factor, side)
        TRUE / FALSE / TIE / NOT_LISTED for one factor in a basis-point bridge
        ("The decrease in gross margin was due to: 120 basis points of ...")
"""
import re

CONTRIBUTION_VERSION = "a3v2-contribution-0.1-draft"
PRIMARY_SHARE = 0.5
_BP = re.compile(r"(\d+(?:\.\d+)?)\s*basis[- ]points?\s+(?:of\s+)?(?:(?:decline|increase|decrease)\s+(?:from|due to)\s+)?([^,;•.]+)", re.I)
_START = re.compile(r"(?:was|were) (?:due to|driven by)\s*:?", re.I)
_OFFSET = re.compile(r"partially offset by|offset by|these (?:decreases|increases) were", re.I)


def share_of_change(component_change: float | None, total_change: float | None) -> float | None:
    if component_change is None or not total_change:
        return None
    return component_change / total_change


def primarily_driven(component_change: float | None, total_change: float | None, threshold: float = PRIMARY_SHARE) -> dict:
    s = share_of_change(component_change, total_change)
    status = "UNVERIFIABLE" if s is None else ("TRUE" if s > threshold else "FALSE")
    return {"status": status, "share": s, "threshold": threshold, "version": CONTRIBUTION_VERSION}


def parse_bp_bridge(passage: str) -> list[dict]:
    """Basis-point items of a margin bridge, each marked as a driver ("main") or an offset."""
    text = " ".join((passage or "").split())
    start = _START.search(text)  # the headline ("decreased 100 basis points to 50.2%") is not a bridge item
    text = text[start.end():] if start else text
    cut = _OFFSET.search(text)
    items = []
    for m in _BP.finditer(text):
        items.append({"bps": float(m.group(1)), "factor": m.group(2).strip().lower(),
                      "side": "offset" if cut and m.start() > cut.start() else "main"})
    return items


def largest_factor(bridge: list[dict], factor_terms: list[str], side: str = "main") -> dict:
    """Is the item whose text contains every term in `factor_terms` the single largest on `side`?"""
    terms = [t.lower() for t in factor_terms]
    items = [b for b in bridge if b["side"] == side]
    hit = [b for b in items if all(t in b["factor"] for t in terms)]
    if not hit:
        return {"status": "NOT_LISTED", "version": CONTRIBUTION_VERSION}
    top = max(b["bps"] for b in items)
    mine = max(b["bps"] for b in hit)
    status = "FALSE" if mine < top else ("TIE" if sum(b["bps"] == top for b in items) > 1 else "TRUE")
    return {"status": status, "bps": mine, "largest_bps": top, "version": CONTRIBUTION_VERSION}


# ---------------------------------------------------------------- extraction call (prompt 0.1) + deterministic decision
# Only for claims the decidability record marks PRIMARY_DRIVER / LARGEST_FACTOR. The model sees the claim and the
# evidence passages the reviewer saw (same ids, same 1,200-character excerpts) and reports figures with the quote
# and evidence id they come from. Nothing it says is trusted: every figure must appear in its quote and every quote
# in its passage, and the verdict is computed here, not by the model. Rules fixed before the dev run:
#   PRIMARY_DRIVER  share = Δtarget / Δtotal > 0.5 -> TRUE; opposite sign, or another reported item with a larger
#                   same-direction change -> FALSE; otherwise UNDECIDED
#   LARGEST_FACTOR  target strictly largest |Δ| among same-side items -> TRUE; a larger item -> FALSE; tie -> UNDECIDED
#   target not reported as a figure, or any figure unverified -> NOT_REPORTED / UNVERIFIED (no effect on the label)
EXTRACTION_PROMPT_VERSION = "a3v2-contribution-prompt-0.1"
EXTRACTION_MAX_TOKENS = 1200
PASSAGE_CHARS = 1200
EXTRACTION_SYSTEM = """You extract figures from SEC filing passages so a program can test a claim of the form "X was the main driver of Y" or "X was the largest factor behind Y". You do NOT judge the claim.

Report, using ONLY figures printed in the passages:
- target: the item the claim credits (X), as the filing names it, with its value for the claim's period (current) and for the comparison period (prior). For a basis-point bridge item ("120 basis points of ..."), give the basis points as current and leave prior null.
- total: the overall quantity whose change the claim explains (Y), current and prior (PRIMARY_DRIVER only).
- other_items: the other components or bridge items the filing lists for the same change, each with current/prior as above.
Every item needs the evidence_id of the passage and a short verbatim quote from it that contains the figures.
If the filing does not report X itself as a figure (e.g. "demand from data centers", "efficiency"), set reported=false and leave target null. Use the units printed (e.g. millions); do not convert or compute."""
_ITEM = {"type": "object", "properties": {"name": {"type": "string"}, "current": {"type": ["number", "null"]}, "prior": {"type": ["number", "null"]},
                                          "evidence_id": {"type": "string"}, "quote": {"type": "string"}},
         "required": ["name", "current", "evidence_id", "quote"]}
EXTRACTION_TOOL = {
    "name": "report_contribution_figures",
    "description": "Figures for testing a main-driver / largest-factor claim. Does not judge the claim.",
    "input_schema": {"type": "object", "properties": {
        "test": {"type": "string", "enum": ["PRIMARY_DRIVER", "LARGEST_FACTOR"]},
        "reported": {"type": "boolean"}, "target": {"anyOf": [_ITEM, {"type": "null"}]}, "total": {"anyOf": [_ITEM, {"type": "null"}]},
        "other_items": {"type": "array", "items": _ITEM}, "note": {"type": "string"}},
        "required": ["test", "reported", "target", "other_items"]},
}


def extraction_request(claim: dict, contribution: dict, passages: list[dict]) -> tuple[str, list, list, int, dict]:
    import json as _json
    packet = {"claim": claim["claim"], "company": claim["company"], "reporting_period": claim.get("reporting_period"),
              "test": contribution.get("type"), "credited_item": contribution.get("component"), "explained_quantity": contribution.get("total"),
              "passages": [{"evidence_id": p["evidence_id"], "form": p.get("form"), "period_end": p.get("period_end"),
                            "text": (p.get("excerpt") or "")[:PASSAGE_CHARS]} for p in passages if p.get("excerpt")]}
    user = {"role": "user", "content": _json.dumps(packet, ensure_ascii=False)}
    return EXTRACTION_SYSTEM, [user], [EXTRACTION_TOOL], EXTRACTION_MAX_TOKENS, {"type": "tool", "name": EXTRACTION_TOOL["name"]}


def _num_in(value, quote: str) -> bool:
    from .checks import _figures
    if value is None:
        return True
    if float(value) == 0:  # filings print a zero as "—", "-" or "0"
        return bool(re.search(r"(^|[\s$(])(—|–|-|0)(?=[\s)%]|$)", quote or ""))
    figs = []
    for f in _figures(quote or "") + [x.replace(",", "") for x in re.findall(r"\b\d{4}\b", quote or "")]:
        try:
            figs.append(float(f))
        except ValueError:
            pass
    return any(abs(abs(float(value)) - x) <= max(0.5, 0.0005 * x) for x in figs)


def _verified(item: dict | None, excerpt_of) -> bool:
    from .checks import tolerant_quote_status
    if not item or item.get("current") is None:
        return False
    passage = excerpt_of(item.get("evidence_id")) or ""
    return tolerant_quote_status(item.get("quote") or "", passage) in ("VERIFIED", "VERIFIED_FRAGMENTS", "VERIFIED_NUMBERS") \
        and _num_in(item.get("current"), item.get("quote")) and _num_in(item.get("prior"), item.get("quote"))


def _delta(item: dict) -> float:
    return float(item["current"]) - float(item["prior"]) if item.get("prior") is not None else float(item["current"])


def decide_contribution(out: dict | None, test: str, excerpt_of) -> dict:
    """{'status': TRUE | FALSE | UNDECIDED | NOT_REPORTED | UNVERIFIED, ...} from the extraction output."""
    out = out if isinstance(out, dict) else {}
    if not out.get("reported") or not out.get("target"):
        return {"status": "NOT_REPORTED", "version": CONTRIBUTION_VERSION}
    target, others = out["target"], [o for o in out.get("other_items") or [] if isinstance(o, dict)]
    if not _verified(target, excerpt_of):
        return {"status": "UNVERIFIED", "why": "target", "version": CONTRIBUTION_VERSION}
    others = [o for o in others if _verified(o, excerpt_of)]
    dt = _delta(target)
    if test == "LARGEST_FACTOR":
        if not others:
            return {"status": "UNDECIDED", "why": "no verified other items", "version": CONTRIBUTION_VERSION}
        top = max(abs(_delta(o)) for o in others)
        status = "TRUE" if abs(dt) > top else ("UNDECIDED" if abs(dt) == top else "FALSE")
        return {"status": status, "target_delta": dt, "largest_other": top, "version": CONTRIBUTION_VERSION}
    total = out.get("total")
    if not _verified(total, excerpt_of):
        return {"status": "UNVERIFIED", "why": "total", "version": CONTRIBUTION_VERSION}
    r = primarily_driven(dt, _delta(total))
    if r["status"] == "TRUE":
        return {**r, "target_delta": dt, "total_delta": _delta(total)}
    if r["share"] is not None and (r["share"] <= 0 or any(abs(_delta(o)) > abs(dt) and _delta(o) * _delta(total) > 0 for o in others)):
        return {**r, "status": "FALSE", "target_delta": dt, "total_delta": _delta(total)}
    return {**r, "status": "UNDECIDED"}


def apply_contribution(final: str, verdict: dict | None) -> tuple[str, str | None]:
    status = (verdict or {}).get("status")
    new = {"TRUE": "SUPPORTED", "FALSE": "CONTRADICTED"}.get(status)
    if new and new != final:
        return new, f"C_{status}"
    return final, None


# ---- 0.1b (post hoc, after the dev run of the 0.1 rules: net -1 on dev-v0.2)
#  * LARGEST_FACTOR now compares same-side items as the 0.1 rule text said: the side comes from the bridge
#    passage itself (parse_bp_bridge on the target's passage), because the extraction does not report sides
#    (0.1 compared against all items, including offsets -- an implementation error, PG-06).
#  * TRUE only fills INSUFFICIENT_EVIDENCE -> SUPPORTED; it never overrides CONTRADICTED. The share test confirms the
#    attribution only, not the rest of the claim (same principle as N2; INTC-04: "recovery" false although the
#    credited segment explains most of the change). FALSE still makes the claim CONTRADICTED.
CONTRIBUTION_RULES_V01B = "a3v2-contribution-rules-0.1b"


def decide_contribution_b(out: dict | None, test: str, excerpt_of) -> dict:
    if test != "LARGEST_FACTOR":
        return decide_contribution(out, test, excerpt_of)
    out = out if isinstance(out, dict) else {}
    target = out.get("target")
    if not out.get("reported") or not target:
        return {"status": "NOT_REPORTED", "version": CONTRIBUTION_RULES_V01B}
    if not _verified(target, excerpt_of):
        return {"status": "UNVERIFIED", "why": "target", "version": CONTRIBUTION_RULES_V01B}
    bridge = parse_bp_bridge(excerpt_of(target.get("evidence_id")) or "")
    words = [w for w in re.findall(r"[a-z]{4,}", (target.get("name") or "").lower())]
    hit = [b for b in bridge if words and all(w in b["factor"] for w in words)]
    if not hit:
        return {"status": "UNDECIDED", "why": "target not found in a basis-point bridge", "version": CONTRIBUTION_RULES_V01B}
    r = largest_factor(bridge, words, side=hit[0]["side"])
    status = {"TRUE": "TRUE", "FALSE": "FALSE"}.get(r["status"], "UNDECIDED")
    return {**r, "status": status, "version": CONTRIBUTION_RULES_V01B}


def apply_contribution_b(final: str, verdict: dict | None) -> tuple[str, str | None]:
    status = (verdict or {}).get("status")
    if status == "TRUE" and final == "INSUFFICIENT_EVIDENCE":
        return "SUPPORTED", "C_TRUE"
    if status == "FALSE" and final != "CONTRADICTED":
        return "CONTRADICTED", "C_FALSE"
    return final, None


def assess_contribution(run, record: dict, reviewed_ids: list[str]) -> dict:
    """The extraction call inside a claim run (same budget, cache, ledger and trace as the other isolated calls),
    then the 0.1b decision. Claims without a contribution test make no call."""
    import time
    from experiments.pipeline import NoStructuredOutput, StageBudgetExhausted
    contrib = (record or {}).get("contribution") or {}
    if contrib.get("type") not in ("PRIMARY_DRIVER", "LARGEST_FACTOR"):
        return {"status": "NOT_APPLICABLE"}
    units = [(i, run.ledger.get(i)) for i in reviewed_ids]
    passages = [{"evidence_id": i, "form": u.form, "period_end": u.period_end, "excerpt": u.excerpt} for i, u in units if u is not None]
    c = run.claim
    try:
        run._check_budget()
        t0 = time.monotonic()
        payload = run.llm.create(*extraction_request({"claim": c.claim, "company": c.company, "reporting_period": c.reporting_period},
                                                     contrib, passages))
    except (NoStructuredOutput, StageBudgetExhausted) as e:
        return {"status": "NOT_RUN", "why": str(e)}
    usage = payload.get("usage") or {}
    run.input_tokens += usage.get("input_tokens", 0)
    run.output_tokens += usage.get("output_tokens", 0)
    use = next((b for b in payload.get("content") or [] if b.get("type") == "tool_use" and b.get("name") == EXTRACTION_TOOL["name"]), None)
    run.llm_calls.append({"stage": "contribution", "tool": EXTRACTION_TOOL["name"], "request_key": payload.get("_request_key"),
                          "source": payload.get("_source"), "input_tokens": usage.get("input_tokens", 0),
                          "output_tokens": usage.get("output_tokens", 0), "stop_reason": payload.get("stop_reason"),
                          "latency_ms": payload.get("_latency_ms", round((time.monotonic() - t0) * 1000)),
                          "output": use["input"] if use else None, "isolated_conversation": True, "prompt_version": EXTRACTION_PROMPT_VERSION})
    if use is None or payload.get("stop_reason") == "max_tokens":
        return {"status": "NOT_RUN", "why": "no complete tool output"}
    excerpt = {i: (u.excerpt if u is not None else "") for i, u in units}
    return {**decide_contribution_b(use["input"], contrib["type"], excerpt.get), "extraction": use["input"]}
