"""LLM access for experiments: response cache, paid-call approval, budget
guard, and offline stand-ins.

Every model call goes through `CachedLLM`, keyed by a hash of the complete
request (model, temperature, system prompt, messages, tools, tool_choice,
max_tokens). Consequences:

- `offline` mode (the default) answers only from the cache and raises
  CacheMiss otherwise -- it can never reach the paid API.
- `live` mode calls the API only for cache misses, only with a
  PaidRunApproval whose cost cap the BudgetGuard enforces, and stores each
  response before returning it, so an interrupted run resumes without
  repeating a paid call.
- `mock` mode uses a deterministic stand-in (HeuristicMockLLM or a scripted
  one in tests). Mock outputs are marked as such in every artifact and are
  never research results.

The live client is the application's own AnthropicClient
(investigation_engine.py), so the research runs use the same request path
and model snapshot as the app's agent.
"""

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field

from . import BACKEND_CORE, RESEARCH_ROOT  # noqa: F401

import agent_config  # noqa: E402

DEFAULT_CACHE_DIR = os.path.join(RESEARCH_ROOT, "results", "llm_cache")
LLM_MODES = ("offline", "live", "mock")
MOCK_VERSION = "mock-heuristic-1.0"


class CacheMiss(RuntimeError):
    """Offline mode needed a response that is not cached."""


class PaidCallNotApproved(PermissionError):
    pass


class BudgetExceeded(RuntimeError):
    pass


def request_key(model: str, temperature: float, system: str, messages: list, tools: list, max_tokens: int, tool_choice) -> str:
    body = {"model": model, "temperature": temperature, "system": system, "messages": messages, "tools": tools,
            "max_tokens": max_tokens, "tool_choice": tool_choice}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


@dataclass
class Pricing:
    input_per_m: float = agent_config.PRICE_PER_M_INPUT
    output_per_m: float = agent_config.PRICE_PER_M_OUTPUT
    version: str = agent_config.PRICING_VERSION

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return input_tokens / 1e6 * self.input_per_m + output_tokens / 1e6 * self.output_per_m


@dataclass
class PaidRunApproval:
    """Created only by `approve_paid_run` with the exact confirmation phrase."""

    max_cost_usd: float
    max_calls: int
    phrase: str
    approved_at: float = field(default_factory=time.time)


def confirmation_phrase(max_cost_usd: float, max_calls: int) -> str:
    return f"I approve up to {max_calls} paid Claude API calls costing at most ${max_cost_usd:.2f}"


def approve_paid_run(plan: dict, typed_phrase: str) -> PaidRunApproval:
    """`plan` comes from runner.plan_run; the user must type the phrase it
    prints. Anything else -- including an empty string -- refuses."""
    expected = confirmation_phrase(plan["max_cost_usd"], plan["max_llm_calls"])
    if (typed_phrase or "").strip() != expected:
        raise PaidCallNotApproved(f"paid run not approved; to approve, type exactly: {expected!r}")
    return PaidRunApproval(max_cost_usd=plan["max_cost_usd"], max_calls=plan["max_llm_calls"], phrase=expected)


class BudgetGuard:
    def __init__(self, approval: PaidRunApproval | None, pricing: Pricing):
        self.approval, self.pricing = approval, pricing
        self.paid_calls = 0
        self.spent_usd = 0.0

    def before_call(self, max_tokens: int, est_input_tokens: int) -> None:
        if self.approval is None:
            raise PaidCallNotApproved("live mode requires a PaidRunApproval (see runner.plan_run / approve_paid_run)")
        if self.paid_calls >= self.approval.max_calls:
            raise BudgetExceeded(f"approved call budget of {self.approval.max_calls} paid calls is used up")
        worst = self.spent_usd + self.pricing.cost(est_input_tokens, max_tokens)
        if worst > self.approval.max_cost_usd:
            raise BudgetExceeded(f"next call could exceed the approved ${self.approval.max_cost_usd:.2f} "
                                 f"(spent ${self.spent_usd:.4f})")

    def after_call(self, usage: dict) -> None:
        self.paid_calls += 1
        self.spent_usd += self.pricing.cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0))


class CachedLLM:
    def __init__(self, mode: str = "offline", model: str = agent_config.MODEL, temperature: float = agent_config.TEMPERATURE,
                 cache_dir: str = DEFAULT_CACHE_DIR, inner=None, approval: PaidRunApproval | None = None,
                 pricing: Pricing | None = None):
        if mode not in LLM_MODES:
            raise ValueError(f"mode must be one of {LLM_MODES}")
        self.mode, self.model, self.temperature, self.cache_dir = mode, model, temperature, cache_dir
        self.pricing = pricing or Pricing()
        self.guard = BudgetGuard(approval, self.pricing)
        if mode == "live" and approval is None:
            raise PaidCallNotApproved("live mode requires a PaidRunApproval")
        if mode == "mock" and inner is None:
            inner = HeuristicMockLLM()
        self.inner = inner
        self.stats = {"cache_hits": 0, "live_calls": 0, "mock_calls": 0}

    def _path(self, key: str) -> str:
        return os.path.join(self.cache_dir, key[:2], f"{key}.json")

    def create(self, system: str, messages: list, tools: list, max_tokens: int, tool_choice: dict | None = None) -> dict:
        key = request_key(self.model, self.temperature, system, messages, tools, max_tokens, tool_choice)
        if self.mode == "mock":
            self.stats["mock_calls"] += 1
            payload = self.inner.create(system, messages, tools, max_tokens, tool_choice)
            return {**payload, "_request_key": key, "_source": "mock"}
        path = self._path(key)
        if os.path.exists(path):
            with open(path) as f:
                cached = json.load(f)
            self.stats["cache_hits"] += 1
            return {**cached["response"], "_request_key": key, "_source": "cache"}
        if self.mode == "offline":
            raise CacheMiss(f"no cached response for request {key[:12]} (offline mode never calls the paid API)")
        est_in = len(json.dumps([system, messages, tools], default=str)) // 3
        self.guard.before_call(max_tokens, est_in)
        if self.inner is None:
            from investigation_engine import AnthropicClient
            self.inner = AnthropicClient(model=self.model)
        t0 = time.monotonic()
        response = self.inner.create(system, messages, tools, max_tokens, tool_choice)
        latency = round((time.monotonic() - t0) * 1000)
        self.guard.after_call(response.get("usage") or {})
        self.stats["live_calls"] += 1
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"request_key": key, "model": self.model, "temperature": self.temperature, "latency_ms": latency,
                       "stored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "response": response}, f)
        os.replace(tmp, path)
        return {**response, "_request_key": key, "_source": "live", "_latency_ms": latency}

    def describe(self) -> dict:
        return {"mode": self.mode, "model": self.model, "temperature": self.temperature,
                "pricing": {"input_per_m": self.pricing.input_per_m, "output_per_m": self.pricing.output_per_m,
                            "version": self.pricing.version},
                "mock_version": getattr(self.inner, "version", None) if self.mode == "mock" else None}


# ------------------------------------------------------------- stand-ins

def _packet(messages: list) -> dict:
    """The approaches put a JSON packet after a 'PACKET:' line in each user turn."""
    for m in reversed(messages):
        content = m["content"] if isinstance(m["content"], str) else " ".join(
            b.get("text", "") for b in m["content"] if isinstance(b, dict))
        if "PACKET:" in content:
            return json.loads(content.split("PACKET:", 1)[1])
    return {}


def _tool_use(name: str, args: dict, usage=(1500, 300)) -> dict:
    return {"content": [{"type": "tool_use", "id": f"mock_{name}", "name": name, "input": args}],
            "usage": {"input_tokens": usage[0], "output_tokens": usage[1]}, "stop_reason": "tool_use"}


_PCT = r"(\d+(?:\.\d+)?)\s*%"
_METRIC_WORDS = [("operating margin", "OperatingMargin"), ("gross margin", "GrossMargin"), ("net margin", "NetMargin"),
                 ("long-term debt", "LongTermDebt"), ("operating cash flow", "OperatingCashFlow"),
                 ("cash from operations", "OperatingCashFlow"), ("net income", "NetIncome"),
                 ("operating income", "OperatingIncome"), ("revenue", "Revenue"), ("net sales", "Revenue")]
_CAUSAL = re.compile(r"\b(because|due to|driven|primarily|efficien|caused|reflect|thanks to|as a result)", re.I)
_CHALLENGE_WORDS = re.compile(r"\b(decrease[sd]?|declin\w+|impairment|one-time|charges?|unfavorabl\w+|headwind|lower)\b", re.I)


def _mock_assertions(claim: str, period: str | None) -> list[dict]:
    text = claim.lower()
    metric = next((m for w, m in _METRIC_WORDS if w in text), None)
    if metric is None:
        return []
    basis = "instant" if metric == "LongTermDebt" else ("annual" if re.search(r"\b(fiscal year|annual|full[- ]year)\b", text) else "quarter")
    pct = re.search(_PCT, text)
    th = float(pct.group(1)) / 100 if pct else None
    if re.search(r"\b(decreas|declin|fell|lower|reduc)", text):
        comp = "decrease"
    elif th is not None and re.search(r"\b(exceed|above|more than|over|at least)", text):
        comp = ">"
    elif th is not None and re.search(r"\b(below|less than|under)", text):
        comp = "<"
    else:
        comp = "increase"
    measure = "level" if metric.endswith("Margin") and comp in (">", "<") else ("level" if comp in ("increase", "decrease") else "yoy_growth")
    return [{"metric": metric, "measure": measure, "period_basis": basis, "period_end": None, "comparison": comp,
             "threshold": th if comp in (">", "<") else None, "stated_value": None}]


def _quote(text: str) -> str:
    s = (text or "").strip()
    return s[:80] if len(s) >= 12 else s


class HeuristicMockLLM:
    """Deterministic, credential-free stand-in so the whole pipeline can run
    offline. Its 'judgements' are keyword heuristics -- useful only to
    exercise plumbing, never as a result."""

    version = MOCK_VERSION

    def create(self, system, messages, tools, max_tokens, tool_choice=None):
        name = (tool_choice or {}).get("name") or tools[-1]["name"]
        p = _packet(messages)
        claim = (p.get("claim") or {}).get("claim", "")
        passages = p.get("evidence") or []
        if name == "submit_verdict":
            assertions = _mock_assertions(claim, (p.get("claim") or {}).get("reporting_period"))
            causal = bool(_CAUSAL.search(claim))
            ctype = "mixed" if assertions and causal else ("numeric" if assertions else "interpretive")
            label = "INSUFFICIENT_EVIDENCE" if causal or not passages else "SUPPORTED"
            sup = [{"evidence_id": passages[0]["evidence_id"], "quote": _quote(passages[0]["text"])}] if passages and label == "SUPPORTED" else []
            return _tool_use(name, {"label": label, "claim_type": ctype, "numeric_assertions": assertions,
                                    "supporting_evidence": sup, "contradicting_evidence": [],
                                    "reasoning_summary": "[MOCK] keyword heuristic, not a model judgement.", "confidence": "low"})
        if name == "submit_contradiction_plan":
            n = p.get("max_hypotheses", 3)
            hyps = [{"hypothesis_id": "H1", "challenge": "Did the reported figures move in the direction the claim states?",
                     "search_query": "decrease decline compared prior year", "numeric_check": None},
                    {"hypothesis_id": "H2", "challenge": "Were results affected by one-time charges or accounting effects?",
                     "search_query": "one-time charge impairment restructuring accounting change", "numeric_check": None},
                    {"hypothesis_id": "H3", "challenge": "Was the change driven by mix, pricing or currency rather than the stated cause?",
                     "search_query": "foreign currency mix pricing unfavorable", "numeric_check": None}][:n]
            return _tool_use(name, {"hypotheses": hyps})
        if name == "submit_self_critique":
            n = p.get("max_hypotheses", 3)
            crit = [{"weakness_id": f"W{i + 1}", "critique": c} for i, c in enumerate(
                ["The cited passage may not address the claimed period.", "The causal explanation may not be stated by management.",
                 "Offsetting factors may not have been considered."][:n])]
            return _tool_use(name, {"weaknesses": crit})
        if name in ("submit_reconciliation", "submit_revision"):
            initial = p.get("initial_verdict") or {}
            items = p.get("hypotheses") or p.get("weaknesses") or []
            counter = p.get("counter_evidence") or []
            assessments, challenged = [], []
            for h in items:
                hid = h.get("hypothesis_id") or h.get("weakness_id")
                hit = next((c for c in counter if c.get("hypothesis_id") == hid and _CHALLENGE_WORDS.search(c.get("text", ""))), None)
                if hit:
                    m = _CHALLENGE_WORDS.search(hit["text"])
                    q = hit["text"][max(0, m.start() - 30): m.end() + 40].strip()
                    assessments.append({"item_id": hid, "assessment": "CHALLENGE_SUPPORTED",
                                        "evidence": [{"evidence_id": hit["evidence_id"], "quote": q}]})
                    challenged.append(assessments[-1]["evidence"][0])
                else:
                    assessments.append({"item_id": hid, "assessment": "NO_RELEVANT_EVIDENCE", "evidence": []})
            label = initial.get("label", "INSUFFICIENT_EVIDENCE")
            if challenged and label == "SUPPORTED" and initial.get("claim_type") != "numeric":
                label = "INSUFFICIENT_EVIDENCE"
            return _tool_use(name, {"assessments": assessments, "label": label,
                                    "verdict_changed": label != initial.get("label"),
                                    "change_reason": "[MOCK] challenge keyword found" if label != initial.get("label") else "",
                                    "supporting_evidence": initial.get("supporting_evidence") or [],
                                    "contradicting_evidence": challenged if label != initial.get("label") else [],
                                    "reasoning_summary": "[MOCK] keyword heuristic, not a model judgement."})
        raise ValueError(f"mock has no behaviour for tool {name}")


class ScriptedLLM:
    """Test double: responses[tool_name] is a dict (fixed tool input) or a
    callable(packet) -> dict. Records every request."""

    version = "scripted-test"

    def __init__(self, responses: dict, usage=(1000, 200)):
        self.responses, self.usage, self.requests = responses, usage, []

    def create(self, system, messages, tools, max_tokens, tool_choice=None):
        self.requests.append({"system": system, "messages": json.loads(json.dumps(messages, default=str)),
                              "tools": [t["name"] for t in tools], "tool_choice": tool_choice, "max_tokens": max_tokens})
        name = (tool_choice or {}).get("name") or tools[-1]["name"]
        r = self.responses[name]
        return _tool_use(name, r(_packet(messages)) if callable(r) else r, self.usage)
