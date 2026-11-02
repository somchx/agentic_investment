"""Intent Analyzer: a deterministic first step that classifies a chat
question before any LLM call, so the investigation plan (which tools are
*required* before an answer may be accepted) comes from the task, not from
the model's own choice -- the same "required claims come from the task"
principle as Agent Output Schema v0.1 section 4.1.

Rules-based on purpose: free, reproducible, testable, and recorded in the
trace. The model still decides *how* to investigate beyond the minimum.
"""

import re
from dataclasses import asdict, dataclass, field

COMPANY_ALIASES = {
    "AAPL": ["aapl", "apple", "แอปเปิล", "แอปเปิ้ล", "แอปเปิ้ล"],
    "MSFT": ["msft", "microsoft", "ไมโครซอฟท์", "ไมโครซอฟต์"],
    "AMZN": ["amzn", "amazon", "อเมซอน", "แอมะซอน"],
    "GOOGL": ["googl", "goog", "google", "alphabet", "กูเกิล", "กูเกิ้ล", "อัลฟาเบท"],
    "NVDA": ["nvda", "nvidia", "เอ็นวิเดีย", "เอ็นวีเดีย", "เอนวิเดีย"],
}

# Checked in order; first match wins. Each intent lists the tools whose
# evidence the answer cannot do without.
INTENT_RULES = [
    ("change_explanation", [r"ทำไม", r"เพราะอะไร", r"สาเหตุ", r"\bwhy\b", r"\bcause", r"\breason (?:for|behind)\b"]),
    ("change_since_purchase", [r"เปลี่ยน(?:ไป|แปลง)?.*(?:ตอน|ตั้งแต่)ซื้อ", r"ตั้งแต่(?:ฉัน)?ซื้อ", r"since (?:i )?(?:bought|purchase)", r"\bchanged?\b.*\bbought\b"]),
    ("risk_review", [r"ระวัง", r"ความเสี่ยง", r"น่า(?:เป็น)?ห่วง", r"กังวล", r"\brisk", r"\bworr", r"\bconcern", r"ใกล้จะไม่เป็นจริง"]),
    ("thesis_check", [r"เหตุผล.*(?:ยัง|จริง)", r"ยังจริง", r"ยังผ่าน", r"still (?:true|hold|valid)", r"\bthesis\b"]),
    ("portfolio_review", [r"พอร์ต", r"portfolio", r"ภาพรวม", r"overview", r"เป็น(?:ยัง|อย่าง)?ไง"]),
]

REQUIRED_TOOLS = {
    "portfolio_review": ["get_user_portfolio", "get_latest_thesis_evaluations", "compare_financial_periods", "check_new_sec_filings"],
    "thesis_check": ["get_original_thesis_snapshot", "get_latest_thesis_evaluations"],
    "risk_review": ["get_user_portfolio", "get_latest_thesis_evaluations", "check_new_sec_filings"],
    "change_since_purchase": ["get_original_thesis_snapshot", "compare_financial_periods", "check_new_sec_filings"],
    "change_explanation": ["get_verified_financial_metrics", "retrieve_filing_evidence"],
    "general": [],
}

# Agent Output Schema v0.1 section 4.1: a "why" question makes the
# explanatory claims required; every other question is a rule check.
TASK_SCOPE = {"change_explanation": "CHANGE_EXPLANATION"}


@dataclass
class Intent:
    intent: str
    tickers: list[str] = field(default_factory=list)
    task_scope: str = "RULE_CHECK"
    required_tools: list[str] = field(default_factory=list)
    matched: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def mentioned_tickers(question: str, universe: list[str] | None = None) -> list[str]:
    q = question.lower()
    found = []
    for ticker, aliases in COMPANY_ALIASES.items():
        if universe is not None and ticker not in universe:
            continue
        if any(re.search(rf"(?<![a-z]){re.escape(a)}(?![a-z])", q) for a in aliases):
            found.append(ticker)
    return found


def classify(question: str, held_tickers: list[str] | None = None) -> Intent:
    q = question.lower()
    tickers = mentioned_tickers(question)
    for name, patterns in INTENT_RULES:
        for p in patterns:
            if re.search(p, q):
                return _build(name, tickers, held_tickers, p)
    return _build("general", tickers, held_tickers, None)


def _build(name: str, tickers: list[str], held: list[str] | None, matched: str | None) -> Intent:
    required = list(REQUIRED_TOOLS[name])
    # A question about a holding the user doesn't own can't be answered from
    # purchase records; fall back to the company's current evidence.
    if tickers and held is not None and not set(tickers) & set(held):
        required = [t for t in required if t not in ("get_user_portfolio", "get_original_thesis_snapshot", "compare_financial_periods")]
        required = required or ["get_verified_financial_metrics"]
    if held is not None and not held:
        required = [t for t in required if t == "get_user_portfolio"]
    return Intent(name, tickers, TASK_SCOPE.get(name, "RULE_CHECK"), required, matched)
