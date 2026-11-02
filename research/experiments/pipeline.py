"""Stages shared by every approach: the initial verdict, deterministic
numeric verification, citation validation, the verdict-change guard and
prediction / trace assembly.

One `ClaimRun` holds everything for one (approach, claim): its own
EvidenceLedger, its own Retriever over the claim's point-in-time corpus,
the conversation with the model, usage counters and the trace. Nothing is
shared between runs, so approaches cannot influence each other.
"""

import time
import uuid

from engine import ENGINE_VERSION
from engine.config import config_hash, thaw
from engine.corpus import RetrievalConfig, Retriever
from engine.numeric import NUMERIC_VERSION, RECONCILE_VERSION, reconcile_label, verify_assertions
from engine.prompts import INITIAL_INSTRUCTION, PROMPT_VERSION, SYSTEM_PROMPT, VERDICT_TOOL, packet_text
from engine.schema import LABELS, empty_prediction

from evidence_ledger import EvidenceLedger, _norm  # noqa: E402  (backend core, on sys.path via engine)

DECISIVE = ("SUPPORTED", "CONTRADICTED")


class StageBudgetExhausted(RuntimeError):
    """This claim's LLM / retrieval budget is used up (the run continues)."""


class NoStructuredOutput(RuntimeError):
    pass


class ClaimRun:
    def __init__(self, claim, cfg, llm, run_id: str | None = None):
        self.claim, self.cfg, self.llm = claim, cfg, llm
        self.ledger = EvidenceLedger()
        self.retriever = Retriever(claim, RetrievalConfig(**thaw(cfg["retrieval"])), self.ledger)
        self.messages: list[dict] = []
        self._pending: list[dict] = []
        self.llm_calls: list[dict] = []
        self.numeric_calls: list[dict] = []
        self.input_tokens = self.output_tokens = 0
        self.started = time.monotonic()
        self.trace_id = f"{run_id or 'adhoc'}:{cfg['name']}:{claim.claim_id}:{uuid.uuid4().hex[:8]}"
        self.stages: list[dict] = []

    # ------------------------------------------------------------ budget

    def _check_budget(self) -> None:
        b = self.cfg["budget"]
        if len(self.llm_calls) >= b["max_llm_calls_per_claim"]:
            raise StageBudgetExhausted(f"max_llm_calls_per_claim={b['max_llm_calls_per_claim']} reached")
        if self.input_tokens >= b["max_input_tokens_per_claim"]:
            raise StageBudgetExhausted(f"max_input_tokens_per_claim={b['max_input_tokens_per_claim']} reached")

    def search(self, query: str, top_k: int | None = None, exclude_shown: bool = False, purpose: str = "initial") -> list[dict]:
        if len(self.retriever.queries) >= self.cfg["budget"]["max_retrieval_queries_per_claim"]:
            raise StageBudgetExhausted("max_retrieval_queries_per_claim reached")
        return self.retriever.search(query, top_k=top_k, exclude_shown=exclude_shown, purpose=purpose)

    # --------------------------------------------------------------- llm

    def ask(self, stage: str, instruction: str, packet: dict, tool: dict) -> dict:
        self._check_budget()
        self.messages.append({"role": "user", "content": [*self._pending, {"type": "text", "text": packet_text(instruction, packet)}]})
        t0 = time.monotonic()
        payload = self.llm.create(SYSTEM_PROMPT, self.messages, [tool], self.cfg["llm"]["max_output_tokens"],
                                  {"type": "tool", "name": tool["name"]})
        usage = payload.get("usage") or {}
        self.input_tokens += usage.get("input_tokens", 0)
        self.output_tokens += usage.get("output_tokens", 0)
        content = [b for b in payload.get("content") or [] if b.get("type") in ("text", "tool_use")]
        self.messages.append({"role": "assistant", "content": content})
        use = next((b for b in content if b.get("type") == "tool_use" and b.get("name") == tool["name"]), None)
        self.llm_calls.append({"stage": stage, "tool": tool["name"], "request_key": payload.get("_request_key"),
                               "source": payload.get("_source"), "input_tokens": usage.get("input_tokens", 0),
                               "output_tokens": usage.get("output_tokens", 0), "stop_reason": payload.get("stop_reason"),
                               "latency_ms": payload.get("_latency_ms", round((time.monotonic() - t0) * 1000)),
                               "output": use["input"] if use else None})
        if use is None:
            raise NoStructuredOutput(f"{stage}: model did not call {tool['name']}")
        if payload.get("stop_reason") == "max_tokens":
            raise NoStructuredOutput(f"{stage}: structured output cut off at max_output_tokens")
        self._pending = [{"type": "tool_result", "tool_use_id": use["id"], "content": "recorded"}]
        return use["input"]

    # ----------------------------------------------------------- numeric

    def verify_numbers(self, assertions: list[dict], purpose: str) -> list[dict]:
        checks = verify_assertions(self.claim.company, self.claim.as_of_date, assertions, self.ledger,
                                   self.cfg["numeric"]["max_assertions"])
        self.numeric_calls.append({"purpose": purpose, "checks": checks})
        return checks

    # --------------------------------------------------------- citations

    def validate(self, items: list[dict], scope: set[str] | None = None) -> list[dict]:
        """Every cited (evidence_id, quote) checked without any LLM: the id
        was issued in this run, the source is the claim's company, it was
        filed on or before the cutoff, and a passage quote is verbatim."""
        out = []
        for it in items or []:
            eid, quote = str(it.get("evidence_id") or ""), it.get("quote") or ""
            unit = self.ledger.get(eid)
            issues = []
            if unit is None:
                issues.append("UNKNOWN_EVIDENCE_ID")
            else:
                if scope is not None and eid not in scope:
                    issues.append("NOT_IN_SCOPE")
                if unit.filed and unit.filed > self.claim.as_of_date:
                    issues.append("FUTURE_EVIDENCE")
                if unit.ticker and unit.ticker != self.claim.company:
                    issues.append("TICKER_MISMATCH")
                if unit.kind == "filing_passage":
                    if len(_norm(quote)) < 12:
                        issues.append("QUOTE_TOO_SHORT")
                    elif _norm(quote) not in _norm(unit.excerpt):
                        issues.append("QUOTE_NOT_IN_PASSAGE")
            out.append({"evidence_id": eid, "quote": quote, "valid": not issues, "issues": issues,
                        **({k: getattr(unit, k) for k in ("kind", "accession_number", "form", "filed", "period_end", "source_url", "locator")}
                           if unit else {})})
        return out

    # ------------------------------------------------------------- trace

    def usage(self) -> dict:
        return {"input": self.input_tokens, "output": self.output_tokens}

    def cost(self) -> float:
        return round(self.llm.pricing.cost(self.input_tokens, self.output_tokens), 6)


# ------------------------------------------------------------------ stages

def initial_stage(run: ClaimRun) -> dict:
    query = run.claim.claim + (f" {run.claim.reporting_period}" if run.claim.reporting_period else "")
    passages = run.search(query, purpose="initial")
    packet = {"claim": run.claim.to_dict(), "evidence_cutoff": run.claim.as_of_date, "evidence": passages,
              "unavailable_filings": [f["accession_number"] for f in run.retriever.unavailable]}
    out = run.ask("initial", INITIAL_INSTRUCTION, packet, VERDICT_TOOL)
    if out.get("label") not in LABELS:
        raise NoStructuredOutput(f"initial: invalid label {out.get('label')!r}")
    run.stages.append({"stage": "initial", "retrieved": [p["evidence_id"] for p in passages], "verdict": out})
    return out


def numeric_stage(run: ClaimRun, verdict: dict) -> tuple[str, str, list[dict]]:
    """A2's deterministic stage. Returns (label, rule, checks)."""
    assertions = verdict.get("numeric_assertions") or []
    checks = run.verify_numbers(assertions, "claim_assertions") if assertions else []
    label, rule = reconcile_label(verdict["label"], verdict.get("claim_type"), checks)
    run.stages.append({"stage": "numeric_verification", "rule_version": RECONCILE_VERSION, "llm_label": verdict["label"],
                       "label": label, "rule": rule, "checks": checks})
    return label, rule, checks


def numeric_evidence(checks: list[dict], status: str) -> list[dict]:
    return [{"evidence_id": c["evidence_ids"][0], "quote": ""} for c in checks if c["status"] == status and c["evidence_ids"]]


def apply_numeric_override(run: ClaimRun, label: str, claim_type: str | None, checks: list[dict], sup: list, con: list) -> tuple[str, str, list, list]:
    """The same deterministic rule A2 applies, re-applied to a revised verdict
    (A3 / SR) when numeric.override_final_label is on."""
    if not (run.cfg["numeric"]["enabled"] and run.cfg["numeric"]["override_final_label"]):
        return label, "NOT_APPLIED", sup, con
    new, rule = reconcile_label(label, claim_type, checks)
    if rule == "NUMERIC_FALSE":
        con = [*con, *numeric_evidence(checks, "FALSE")]
    elif rule == "NUMERIC_ALL_TRUE":
        sup = [*sup, *numeric_evidence(checks, "TRUE")]
    return new, rule, sup, con


def guard_change(run: ClaimRun, initial_label: str, final: dict, scope: set[str] | None) -> dict:
    """Shared by A3 and SR. A challenge counts only with valid evidence; a
    verdict may move to SUPPORTED / CONTRADICTED only with a valid citation
    for it (moving to INSUFFICIENT_EVIDENCE -- the cautious direction -- is
    allowed without one). Otherwise the initial verdict is kept and the
    attempted change is recorded."""
    assessments = []
    for a in final.get("assessments") or []:
        ev = run.validate(a.get("evidence") or [], scope)
        status = a.get("assessment")
        flag = None
        if status == "CHALLENGE_SUPPORTED" and not any(e["valid"] for e in ev):
            status, flag = "NO_RELEVANT_EVIDENCE", "CHALLENGE_WITHOUT_VALID_EVIDENCE"
        assessments.append({"item_id": a.get("item_id"), "declared": a.get("assessment"), "assessment": status,
                            "evidence": ev, "flag": flag})
    label = final.get("label")
    sup, con = run.validate(final.get("supporting_evidence")), run.validate(final.get("contradicting_evidence"))
    reverted = None
    if label not in LABELS:
        label, reverted = initial_label, "INVALID_LABEL"
    elif label != initial_label and label in DECISIVE:
        backing = sup if label == "SUPPORTED" else con
        if not any(e["valid"] for e in backing):
            reverted = f"CHANGE_TO_{label}_WITHOUT_VALID_EVIDENCE"
            label = initial_label
    return {"assessments": assessments, "label": label, "reverted": reverted, "supporting": sup, "contradicting": con}


def finish_revision(run: ClaimRun, s: dict, final: dict) -> tuple[dict, str, str, list, list]:
    """Second-look outcome for A3 and SR alike: guard the change, then
    re-apply the numeric rule. `s` is financial_verification.verified_initial
    output. Returns (guard record, label, rule, supporting, contradicting)."""
    g = guard_change(run, s["label"], final, scope=None)
    if g["reverted"]:
        return g, s["label"], "KEPT_INITIAL", s["supporting"], s["contradicting"]
    label, rule, sup, con = apply_numeric_override(
        run, g["label"], s["verdict"].get("claim_type"), s["checks"],
        list(final.get("supporting_evidence") or []), list(final.get("contradicting_evidence") or []))
    return g, label, rule, sup, con


def build_prediction(run: ClaimRun, *, initial_label: str | None, label: str, reasoning: str,
                     supporting: list[dict], contradicting: list[dict], stop_reason: str, error: str | None = None,
                     extra: dict | None = None) -> tuple[dict, dict]:
    """(prediction row, full trace). `supporting` / `contradicting` are the
    raw cited items; they are validated here."""
    sup, con = run.validate(supporting), run.validate(contradicting)
    citations, seen = [], set()
    for c in sup + con:
        if c["evidence_id"] not in seen:
            seen.add(c["evidence_id"])
            citations.append(c)
    decisive_backing = sup if label == "SUPPORTED" else con if label == "CONTRADICTED" else []
    pred = empty_prediction(run.claim, run.cfg["name"])
    pred.update({
        "approach_kind": run.cfg["kind"], "config_hash": config_hash(run.cfg),
        "predicted_label": label, "initial_label": initial_label,
        "verdict_changed": initial_label is not None and label != initial_label,
        "supporting_evidence": [c for c in sup if c["valid"]], "contradicting_evidence": [c for c in con if c["valid"]],
        "invalid_citations": [c for c in sup + con if not c["valid"]],
        "citations": citations, "reasoning_summary": reasoning,
        "unsupported_conclusion": label in DECISIVE and not any(c["valid"] for c in decisive_backing),
        "investigation_trace_id": run.trace_id, "token_usage": run.usage(),
        "latency_ms": round((time.monotonic() - run.started) * 1000), "estimated_cost_usd": run.cost(),
        "llm_calls": len(run.llm_calls), "retrieval_queries": len(run.retriever.queries),
        "numeric_checks": sum(len(n["checks"]) for n in run.numeric_calls),
        "llm_sources": sorted({c["source"] for c in run.llm_calls if c.get("source")}),
        "stop_reason": stop_reason, "error": error, **(extra or {}),
    })
    trace = {
        "trace_id": run.trace_id, "engine_version": ENGINE_VERSION, "prompt_version": PROMPT_VERSION,
        "numeric_version": NUMERIC_VERSION, "reconcile_version": RECONCILE_VERSION,
        "approach": run.cfg["name"], "approach_kind": run.cfg["kind"], "config": thaw(run.cfg), "config_hash": pred["config_hash"],
        "claim": run.claim.to_dict(), "initial_label": initial_label, "final_label": label,
        "stages": run.stages, "llm_calls": run.llm_calls,
        "tool_calls": [{"tool": "retrieve_passages", **q} for q in run.retriever.queries]
                      + [{"tool": "verify_numbers", **n} for n in run.numeric_calls],
        "corpus": run.retriever.manifest(), "evidence": run.ledger.public(),
        "citations": citations, "stop_reason": stop_reason, "error": error,
        "token_usage": pred["token_usage"], "latency_ms": pred["latency_ms"], "estimated_cost_usd": pred["estimated_cost_usd"],
    }
    return pred, trace
