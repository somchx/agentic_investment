"""Deterministic checks on the human-readable answer text, run by the Evidence
Gate before an answer is accepted:

- unsupported reassurance / trade recommendations ("no risk", "safe",
  "should hold", "ควรซื้อเพิ่ม", ...) presented as conclusions, and
- raw machine codes (SATISFIED, INSUFFICIENT, claim / evidence ids) leaking
  into prose a beginner investor reads.

A phrase preceded by a negating qualifier ("does not mean there is no
risk", "ไม่ได้หมายความว่าไม่มีความเสี่ยง") is the opposite of reassurance and
is allowed.
"""

import re

REASSURANCE_PATTERNS = [
    # Thai
    r"ไม่มีความเสี่ยง", r"ไม่ต้อง(?:กังวล|ห่วง)", r"(?:หุ้น|พอร์ต|การลงทุน)\S{0,20}ปลอดภัย",r"ควรถือ(?:ต่อ|ไว้)",
    r"ควรซื้อ(?:เพิ่ม)?", r"ควรขาย", r"(?:เติบโต|โต|ขึ้น)(?:ต่อ)?แน่นอน", r"การันตี", r"ไม่มีอะไรต้องห่วง",
    r"พอร์ต(?:ของคุณ)?ดี(?:มาก)?แล้ว",
    # English
    r"\bno risks?\b", r"\bnothing to worry\b", r"\bno need to worry\b", r"\b(?:is|are|looks?) safe\b",
    r"\bsafe (?:stock|investment|bet)\b", r"\bshould (?:hold|buy|sell|add)\b", r"\bguarantee[sd]?\b",
    r"\bwill (?:definitely|certainly) (?:grow|rise|increase)\b", r"\bportfolio looks good\b",
]
_NEGATIONS = (
    "ไม่ได้หมายความว่า", "ไม่ได้แปลว่า", "ไม่ใช่", "ไม่สามารถสรุปว่า", "ยังสรุปไม่ได้ว่า", "ไม่ควรสรุปว่า", "ไม่ได้บอกว่า",
    "does not mean", "doesn't mean", "not mean", "cannot conclude", "can't conclude", "not that", "not a signal",
    "do not imply", "does not imply", "doesn't imply", "not imply", "never",
)
RAW_CODE_PATTERNS = [
    r"\b(?:SATISFIED|BREACHED|NOT_EVALUATED|SUFFICIENT|INSUFFICIENT|CONFLICTING|NOT_YET_OBSERVABLE|NOT_ESTABLISHED|CONTRADICTED)\b",
    r"\b[CE]\d{1,3}\b",
]


def find_reassurance(text: str) -> list[str]:
    found = []
    for pattern in REASSURANCE_PATTERNS:
        for m in re.finditer(pattern, text, re.I):
            before = text[max(0, m.start() - 40):m.start()].lower()
            if any(n in before for n in _NEGATIONS):
                continue
            found.append(m.group(0))
    return found


def find_raw_codes(text: str) -> list[str]:
    return sorted({m.group(0) for p in RAW_CODE_PATTERNS for m in re.finditer(p, text)})


def check_answer_text(texts: list[str]) -> list[str]:
    problems = []
    for text in texts:
        for phrase in find_reassurance(text):
            problems.append(f"UNSUPPORTED_REASSURANCE: '{phrase}' -- replace with an evidence-bounded statement")
        for code in find_raw_codes(text):
            problems.append(f"RAW_CODE_IN_PROSE: '{code}' -- explain in plain language; link claims via claim_ids instead")
    return problems
