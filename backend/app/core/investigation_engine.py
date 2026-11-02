"""InvestigationEngine: the one agent loop behind both the chat assistant and
the B1-B3 experiment baselines (workflow 2.0).

    Planner (LLM picks tools) -> Tool Executor (investigation_tools, evidence
    ledger) -> [B3/chat: forced evidence assessment] -> finalize ->
    Evidence Gate (citation verification, answer guard, required tools) ->
    accept | reject with reasons (bounded) -> Finalizer + stored trace

What differs between configurations is only what is passed in (tools,
whether the assessment step and the verification gate are on, the finalize
schema, the budget), so B2 and B3 differ exactly by the verification
procedure, and chat runs the B3 configuration with portfolio tools added.

The LLM is behind a small client interface so automated tests can script
model turns (MockLLM) without any paid call; production always uses
AnthropicClient against the real API.
"""

import json
import os
import time
from dataclasses import dataclass, field

import requests

from agent_config import MODEL, TEMPERATURE, config_manifest, estimate_cost
from evidence_ledger import verify_claims
from investigation_tools import RETRIEVAL_TOOLS, TOOL_REGISTRY, ToolContext, ToolInputError, run_tool, tool_specs

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MAX_TOOL_RESULT_CHARS = 9000


class AnthropicClient:
    """Raw Messages API call via `requests` (same reason as agent.py: the SDK's
    HTTP stack had a decompression bug in this environment)."""

    def __init__(self, api_key: str | None = None, model: str = MODEL):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set; the investigation agent cannot run without it.")
        self.model = model

    def create(self, system: str, messages: list[dict], tools: list[dict], max_tokens: int, tool_choice: dict | None = None) -> dict:
        body = {"model": self.model, "max_tokens": max_tokens, "temperature": TEMPERATURE, "system": system,
                "messages": messages, "tools": tools}
        if tool_choice:
            body["tool_choice"] = tool_choice
        resp = requests.post(ANTHROPIC_API_URL, timeout=120, json=body, headers={
            "x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        resp.raise_for_status()
        return resp.json()


ASSESSMENT_TOOL = {
    "name": "record_evidence_assessment",
    "description": (
        "Required before finalizing. For each reason or topic you investigated, record which evidence ids "
        "support the investment reason, which contradict it, whether evidence is sufficient, any conflicts "
        "between sources, and what remains open. Use only evidence ids returned by tools."),
    "input_schema": {"type": "object", "properties": {"assessments": {"type": "array", "items": {"type": "object", "properties": {
        "topic": {"type": "string"}, "ticker": {"type": "string"}, "reason_key": {"type": "string"},
        "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
        "contradicting_evidence_ids": {"type": "array", "items": {"type": "string"}},
        "sufficiency": {"type": "string", "enum": ["SUFFICIENT", "INSUFFICIENT", "CONFLICTING", "NOT_YET_OBSERVABLE"]},
        "conflicts": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
    }, "required": ["topic", "supporting_evidence_ids", "contradicting_evidence_ids", "sufficiency"]}}},
        "required": ["assessments"]},
}


@dataclass
class EngineConfig:
    mode: str  # chat | B1 | B2 | B3
    system_prompt: str
    tool_names: list[str]
    finalize_tool: dict
    budget: dict
    require_assessment: bool
    verify: bool  # run the verification gate as part of the loop (B3, chat)
    reason_keys: list[str] | None = None
    # extra gate: (finalize_input, run) -> problems
    gate: object = None


@dataclass
class Run:
    ctx: ToolContext
    tool_calls: list[dict] = field(default_factory=list)
    llm_calls: list[dict] = field(default_factory=list)
    assessments: list[dict] = field(default_factory=list)
    rejections: list[dict] = field(default_factory=list)
    retrieval_iterations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def called(self, name: str, ticker: str | None = None) -> bool:
        return any(c["name"] == name and not c.get("error") and (ticker is None or (c["input"].get("ticker") or "").upper() == ticker)
                   for c in self.tool_calls)


def _truncate(result: dict) -> str:
    text = json.dumps(result, ensure_ascii=False, default=str)
    if len(text) <= MAX_TOOL_RESULT_CHARS:
        return text
    return text[:MAX_TOOL_RESULT_CHARS] + '..."[truncated: ask a narrower question or a specific ticker/metric]"'


def _preview(result: dict, limit: int = 2500):
    text = json.dumps(result, ensure_ascii=False, default=str)
    return json.loads(text) if len(text) <= limit else {"preview": text[:limit] + "…", "truncated": True}


def _compact(result: dict):
    text = json.dumps(result, ensure_ascii=False, default=str)
    return json.loads(text) if len(text) <= MAX_TOOL_RESULT_CHARS else {"truncated": True, "preview": text[:MAX_TOOL_RESULT_CHARS]}


class InvestigationEngine:
    def __init__(self, config: EngineConfig, ctx: ToolContext, llm=None, on_event=None):
        self.config = config
        # Optional progress callback (live UI): receives plain dicts; never
        # changes what the agent does, and a failing listener is ignored.
        self.on_event = on_event
        self._run: Run | None = None
        self._started = 0.0
        self.ctx = ctx
        self.llm = llm or AnthropicClient()
        self.tools = tool_specs(config.tool_names, config.reason_keys)
        if config.require_assessment:
            self.tools.append(ASSESSMENT_TOOL)
        self.tools.append(config.finalize_tool)
        self.finalize_name = config.finalize_tool["name"]

    # -------------------------------------------------------------- loop

    def run(self, messages: list[dict]) -> dict:
        cfg, budget = self.config, self.config.budget
        run = Run(ctx=self.ctx)
        started = time.monotonic()
        self._run, self._started = run, started
        messages = list(messages)
        final, stop_reason, problems = None, None, []

        for _ in range(budget["max_iterations"]):
            exhausted = (len(run.tool_calls) >= budget["max_tool_calls"]
                         or run.retrieval_iterations >= budget["max_retrieval_iterations"]
                         or time.monotonic() - started > budget["max_seconds"])
            if exhausted:
                self._emit("budget_exhausted")
                stop_reason = "BUDGET_EXHAUSTED"
                final, problems = self._forced_finalize(run, messages)
                break
            payload = self._call(run, messages)
            content = payload.get("content") or []
            messages.append({"role": "assistant", "content": content})
            uses = [b for b in content if b.get("type") == "tool_use"]
            fin = next((u for u in uses if u["name"] == self.finalize_name), None)
            if fin is not None:
                results = self._execute(run, [u for u in uses if u is not fin])
                problems = self._gate(run, fin["input"])
                if payload.get("stop_reason") == "max_tokens":
                    problems = ["your answer was cut off at the output limit; write it again much shorter (fewer paragraphs and claims)"]
                if problems and len(run.rejections) < budget["max_gate_rejections"]:
                    run.rejections.append({"problems": problems, "proposal": fin["input"]})
                    self._emit("gate_rejected", problems=problems, attempt=len(run.rejections))
                    results.append({"type": "tool_result", "tool_use_id": fin["id"], "is_error": True, "content":
                                    "Rejected by the Evidence Gate. Fix these and call " + self.finalize_name + " again:\n"
                                    + "\n".join(f"- {p}" for p in problems)})
                    messages.append({"role": "user", "content": results})
                    continue
                final = fin["input"]
                stop_reason = "GATE_REJECTIONS_EXHAUSTED" if problems else "FINALIZED"
                self._emit("gate_accepted" if not problems else "gate_gave_up", problems=problems)
                break
            if not uses:
                messages.append({"role": "user", "content": f"Call {self.finalize_name} with your structured answer now."})
                continue
            messages.append({"role": "user", "content": self._execute(run, uses)})
        else:
            stop_reason = "BUDGET_EXHAUSTED"
            final, problems = self._forced_finalize(run, messages)

        verification, claim_problems = verify_claims((final or {}).get("claims") or [], self.ctx.ledger, self.ctx.analysis_date)
        return {
            "final": final,
            "stop_reason": stop_reason,
            "unresolved_problems": problems if stop_reason != "FINALIZED" else [],
            "verification": {"claims": verification, "problems": claim_problems},
            "trace": self._trace(run, started, stop_reason),
        }

    def _forced_finalize(self, run: Run, messages: list[dict]) -> tuple[dict | None, list[str]]:
        """Budget is used up: one last call that may only finalize, stating
        that the investigation stopped on budget, not on evidence."""
        note = {"type": "text", "text": (
            "The investigation budget is exhausted. Finalize now with only the evidence already gathered. Mark "
            "anything you could not check as NOT_ESTABLISHED and say the check was cut short by the budget, "
            "not that evidence is missing.")}
        last = messages[-1]
        if last["role"] == "assistant":
            pending = [{"type": "tool_result", "tool_use_id": b["id"], "is_error": True, "content": "Not executed: budget exhausted."}
                       for b in last["content"] if b.get("type") == "tool_use"]
            messages.append({"role": "user", "content": pending + [note]})
        elif isinstance(last["content"], list):
            last["content"] = [*last["content"], note]
        else:
            last["content"] = [{"type": "text", "text": last["content"]}, note]
        for attempt in range(2):
            payload = self._call(run, messages, tools=[self.config.finalize_tool], tool_choice={"type": "tool", "name": self.finalize_name})
            fin = next((b for b in payload.get("content") or [] if b.get("type") == "tool_use" and b["name"] == self.finalize_name), None)
            if fin is None:
                return None, ["model did not finalize after budget exhaustion"]
            if payload.get("stop_reason") != "max_tokens" or attempt == 1:
                break
            # Cut off mid-answer: one retry asking for a much shorter answer.
            messages += [{"role": "assistant", "content": payload["content"]},
                         {"role": "user", "content": [{"type": "tool_result", "tool_use_id": fin["id"], "is_error": True,
                                                       "content": "Cut off at the output limit. Write the answer again much shorter."}]}]
        return fin["input"], self._gate(run, fin["input"])

    def _call(self, run: Run, messages: list[dict], tools: list[dict] | None = None, tool_choice: dict | None = None) -> dict:
        t0 = time.monotonic()
        forced = tool_choice is not None
        self._emit("llm_start", call=len(run.llm_calls) + 1, purpose="finalize" if forced else "plan")
        payload = self.llm.create(self.config.system_prompt, messages, tools or self.tools,
                                  self.config.budget["max_output_tokens"], tool_choice)
        usage = payload.get("usage") or {}
        run.input_tokens += usage.get("input_tokens", 0)
        run.output_tokens += usage.get("output_tokens", 0)
        run.llm_calls.append({"latency_ms": round((time.monotonic() - t0) * 1000), "input_tokens": usage.get("input_tokens", 0),
                              "output_tokens": usage.get("output_tokens", 0), "stop_reason": payload.get("stop_reason")})
        blocks = payload.get("content") or []
        self._emit("llm_end", call=len(run.llm_calls), latency_ms=run.llm_calls[-1]["latency_ms"],
                   stop_reason=payload.get("stop_reason"),
                   text=" ".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()[:600] or None,
                   next_tools=[b["name"] for b in blocks if b.get("type") == "tool_use"])
        return payload

    # ---------------------------------------------------------- tools

    def _execute(self, run: Run, uses: list[dict]) -> list[dict]:
        results = []
        if any(u["name"] in RETRIEVAL_TOOLS for u in uses):
            run.retrieval_iterations += 1
        for u in uses:
            name, args = u["name"], dict(u.get("input") or {})
            t0 = time.monotonic()
            before = set(self.ctx.ledger.units)
            entry = {"name": name, "input": args}
            self._emit("tool_start", id=u["id"], name=name, input=args)
            if name == ASSESSMENT_TOOL["name"] and self.config.require_assessment:
                result = self._record_assessment(run, args)
            elif name not in self.config.tool_names:
                result = {"error": f"tool {name} is not available in this investigation"}
                entry["error"] = "UNAVAILABLE_TOOL"
            elif len([c for c in run.tool_calls if c["name"] in TOOL_REGISTRY]) >= self.config.budget["max_tool_calls"]:
                result = {"error": "investigation tool budget exhausted; finalize with the evidence gathered"}
                entry["error"] = "BUDGET_EXHAUSTED"
            else:
                try:
                    result = run_tool(self.ctx, name, args)
                except ToolInputError as e:
                    result, entry["error"] = {"error": str(e)}, "INVALID_INPUT"
                except TypeError as e:
                    result, entry["error"] = {"error": f"invalid arguments: {e}"}, "INVALID_INPUT"
                except Exception as e:  # noqa: BLE001 -- surfaced to the model and the trace, never silently dropped
                    from sec_client import SecDataUnavailableError
                    if isinstance(e, SecDataUnavailableError):
                        result, entry["error"] = {"error": "SEC data is temporarily unavailable; this is not evidence about the company."}, "SOURCE_UNAVAILABLE"
                    else:
                        result, entry["error"] = {"error": "tool failed unexpectedly"}, "TOOL_FAILURE"
                        entry["exception"] = f"{type(e).__name__}: {e}"[:300]
            entry["latency_ms"] = round((time.monotonic() - t0) * 1000)
            entry["evidence_ids"] = sorted(set(self.ctx.ledger.units) - before, key=lambda x: int(x[1:]))
            entry["output"] = result
            run.tool_calls.append(entry)
            self._emit("tool_end", id=u["id"], name=name, latency_ms=entry["latency_ms"], evidence_ids=entry["evidence_ids"],
                       error=entry.get("error"), output=_preview(result))
            results.append({"type": "tool_result", "tool_use_id": u["id"], "content": _truncate(result),
                            **({"is_error": True} if entry.get("error") else {})})
        return results

    def _record_assessment(self, run: Run, args: dict) -> dict:
        bad = sorted({i for a in args.get("assessments") or [] for i in (a.get("supporting_evidence_ids") or []) + (a.get("contradicting_evidence_ids") or [])
                      if self.ctx.ledger.get(i) is None})
        if bad:
            return {"error": f"unknown evidence ids {bad}; cite only ids returned by tools"}
        run.assessments = list(args.get("assessments") or [])
        return {"recorded": len(run.assessments)}

    def _emit(self, kind: str, **data) -> None:
        if not self.on_event or self._run is None:
            return
        run = self._run
        try:
            self.on_event({"type": kind, **data, "counters": {
                "tool_calls": len(run.tool_calls), "max_tool_calls": self.config.budget["max_tool_calls"],
                "input_tokens": run.input_tokens, "output_tokens": run.output_tokens,
                "elapsed_ms": round((time.monotonic() - self._started) * 1000)}})
        except Exception:  # noqa: BLE001 -- progress display must never break an investigation
            pass

    # ----------------------------------------------------------- gate

    def _gate(self, run: Run, final: dict) -> list[str]:
        problems = []
        if self.config.require_assessment and not run.assessments:
            problems.append("record_evidence_assessment must be called (supporting vs contradicting evidence, sufficiency, open questions) before finalizing")
        if self.config.verify:
            problems += verify_claims(final.get("claims") or [], self.ctx.ledger, self.ctx.analysis_date)[1]
        if self.config.gate:
            problems += self.config.gate(final, run)
        return problems

    # ---------------------------------------------------------- trace

    def _trace(self, run: Run, started: float, stop_reason: str | None) -> dict:
        return {
            "config": config_manifest(self.config.mode, self.config.budget, self.config.system_prompt, self.tools),
            "analysis_date": self.ctx.analysis_date,
            "tool_calls": [{**c, "output": _compact(c["output"])} for c in run.tool_calls],
            "evidence": self.ctx.ledger.public(),
            "assessments": run.assessments,
            "gate_rejections": run.rejections,
            "llm_calls": run.llm_calls,
            "stop_reason": stop_reason,
            "usage": {"input_tokens": run.input_tokens, "output_tokens": run.output_tokens},
            "cost_usd": round(estimate_cost(run.input_tokens, run.output_tokens), 6),
            "latency_ms": round((time.monotonic() - started) * 1000),
            "retrieval_iterations": run.retrieval_iterations,
        }
