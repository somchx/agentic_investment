"""Point-in-time SEC corpus and passage retrieval shared by every approach.

Documents come from the application's SEC cache (backend/app/data/cache,
filled by sec_client), read directly from disk so an experiment never
triggers the app's 24-hour cache refresh. Network access to SEC EDGAR (free,
no API key) happens only in `build_corpus`, run explicitly beforehand; at
experiment time a missing document is reported as unavailable, never
fetched silently.

Point-in-time rule: a filing is eligible for a claim only if its form is in
the claim's allowed sources and it was filed on or before the claim's
as_of_date. That filter is applied before any text is read, so a later
filing cannot reach a prompt.

Retrieval is BM25 over fixed-size passages of the cleaned main document;
every returned passage is registered in the run's EvidenceLedger (the same
ledger + citation verifier the app's agent uses), so the model can only
cite ids the retriever actually issued.
"""

import hashlib
import html as html_lib
import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache

from . import BACKEND_CORE  # noqa: F401 -- puts backend/app/core on sys.path

from evidence_ledger import EvidenceLedger, EvidenceUnit  # noqa: E402
from sec_client import ALL_KNOWN_CIKS, CACHE_DIR  # noqa: E402

CLEANING_VERSION = "clean-1.0"
RETRIEVAL_VERSION = "bm25-1.0"

STOPWORDS = set("""a an and are as at be because been but by for from had has have its it in into is of on or our that the
their this to was were which while with company companys we us during than more less over also not""".split())


class CorpusUnavailable(RuntimeError):
    pass


# ------------------------------------------------------------- filings

def _cik(ticker: str) -> str:
    if ticker not in ALL_KNOWN_CIKS:
        raise CorpusUnavailable(f"ticker {ticker} has no known CIK")
    return ALL_KNOWN_CIKS[ticker].zfill(10)


def submissions_path(ticker: str) -> str:
    return os.path.join(CACHE_DIR, f"submissions_CIK{_cik(ticker)}.json")


def facts_path(ticker: str) -> str:
    return os.path.join(CACHE_DIR, f"CIK{_cik(ticker)}.json")


def document_path(accession_number: str, filename: str) -> str:
    return os.path.join(CACHE_DIR, f"doc_{accession_number}_{filename}")


@lru_cache(maxsize=32)
def _submissions(ticker: str) -> dict:
    path = submissions_path(ticker)
    if not os.path.exists(path):
        raise CorpusUnavailable(f"no cached SEC submissions index for {ticker}; run scripts/build_corpus.py")
    with open(path) as f:
        return json.load(f)


def list_filings(ticker: str) -> list[dict]:
    recent = _submissions(ticker)["filings"]["recent"]
    return [{"ticker": ticker, "form": recent["form"][i], "accession_number": recent["accessionNumber"][i],
             "filed": recent["filingDate"][i], "report_date": recent["reportDate"][i] or None,
             "primary_document": recent["primaryDocument"][i]} for i in range(len(recent["form"]))]


def eligible_filings(ticker: str, as_of_date: str, forms: set[str], max_per_form: dict[str, int] | None = None) -> list[dict]:
    """Most recent filings per form filed on or before the cutoff."""
    max_per_form = max_per_form or {}
    picked, counts = [], Counter()
    for f in sorted(list_filings(ticker), key=lambda r: r["filed"], reverse=True):
        if f["form"] not in forms or f["filed"] > as_of_date:
            continue
        family = f["form"].split("/")[0]
        if counts[family] >= max_per_form.get(family, 1):
            continue
        counts[family] += 1
        picked.append(f)
    return picked


def doc_url(f: dict) -> str:
    return (f"https://www.sec.gov/Archives/edgar/data/{int(_cik(f['ticker']))}/"
            f"{f['accession_number'].replace('-', '')}/{f['primary_document']}")


# ------------------------------------------------------------ cleaning

_HIDDEN = re.compile(r"<ix:header>.*?</ix:header>|<(script|style)\b.*?</\1>", re.S | re.I)
_BLOCK = re.compile(r"</?(p|div|tr|br|li|h[1-6]|table)\b[^>]*>", re.I)


def clean_filing_html(raw: str) -> str:
    text = _HIDDEN.sub(" ", raw)
    text = _BLOCK.sub(" \n ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return re.sub(r"\n{2,}", "\n", text).replace("\n", " ").strip()


@lru_cache(maxsize=16)
def document_text(accession_number: str, filename: str) -> str | None:
    path = document_path(accession_number, filename)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        return clean_filing_html(f.read())


def document_sha256(accession_number: str, filename: str) -> str | None:
    path = document_path(accession_number, filename)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------ passages

def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z][a-z0-9\-]+|\d+(?:\.\d+)?%?", text.lower()) if t not in STOPWORDS]


@dataclass
class Passage:
    chunk_id: str  # stable across runs: accession:start-end of the cleaned text
    filing: dict
    start: int
    end: int
    text: str


@lru_cache(maxsize=16)
def _chunks(accession_number: str, filename: str, size: int, overlap: int) -> tuple:
    text = document_text(accession_number, filename)
    if text is None:
        return ()
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):  # end on a sentence boundary when one is close
            dot = text.rfind(". ", start + size // 2, end)
            end = dot + 1 if dot != -1 else end
        out.append((start, end))
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return tuple(out)


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.avg = sum(len(d) for d in docs) / max(1, len(docs))
        self.tf = [Counter(d) for d in docs]
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def score(self, query: list[str], i: int) -> float:
        tf, dl = self.tf[i], len(self.docs[i])
        s = 0.0
        for t in set(query):
            if t in tf:
                f = tf[t]
                s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / max(self.avg, 1)))
        return s


@dataclass
class RetrievalConfig:
    top_k: int = 6
    chunk_chars: int = 1200
    chunk_overlap: int = 200
    max_filings_per_form: dict = field(default_factory=lambda: {"10-K": 1, "10-Q": 2, "8-K": 2})
    passage_chars_in_prompt: int = 1200

    def to_dict(self) -> dict:
        return {"method": RETRIEVAL_VERSION, "cleaning": CLEANING_VERSION, "top_k": self.top_k, "chunk_chars": self.chunk_chars,
                "chunk_overlap": self.chunk_overlap, "max_filings_per_form": dict(self.max_filings_per_form),
                "passage_chars_in_prompt": self.passage_chars_in_prompt}


class Retriever:
    """One instance per (approach, claim): holds that run's ledger and the
    passages already shown, so a contradiction query can ask for NEW text."""

    def __init__(self, claim, config: RetrievalConfig, ledger: EvidenceLedger):
        self.claim, self.config, self.ledger = claim, config, ledger
        self.filings = eligible_filings(claim.company, claim.as_of_date, claim.allowed_forms(), config.max_filings_per_form)
        self.unavailable = [f for f in self.filings if document_text(f["accession_number"], f["primary_document"]) is None]
        self.passages: list[Passage] = []
        for f in self.filings:
            text = document_text(f["accession_number"], f["primary_document"])
            if text is None:
                continue
            for s, e in _chunks(f["accession_number"], f["primary_document"], config.chunk_chars, config.chunk_overlap):
                self.passages.append(Passage(f"{f['accession_number']}:{s}-{e}", f, s, e, text[s:e].strip()))
        self.index = BM25([tokenize(p.text) for p in self.passages]) if self.passages else None
        self.shown: set[str] = set()
        self.queries: list[dict] = []

    def search(self, query: str, top_k: int | None = None, exclude_shown: bool = False, purpose: str = "initial") -> list[dict]:
        top_k = top_k or self.config.top_k
        q = tokenize(query)
        hits = []
        if self.index and q:
            scored = sorted(((self.index.score(q, i), i) for i in range(len(self.passages))), key=lambda x: (-x[0], x[1]))
            for score, i in scored:
                if score <= 0 or len(hits) >= top_k:
                    break
                p = self.passages[i]
                if exclude_shown and p.chunk_id in self.shown:
                    continue
                hits.append(self._register(p, score))
        self.queries.append({"purpose": purpose, "query": query, "top_k": top_k, "exclude_shown": exclude_shown,
                             "results": [h["evidence_id"] for h in hits]})
        return hits

    def _register(self, p: Passage, score: float) -> dict:
        f = p.filing
        eid = self.ledger.add(EvidenceUnit(
            kind="filing_passage", ticker=f["ticker"], accession_number=f["accession_number"], form=f["form"], filed=f["filed"],
            period_end=f.get("report_date"), source_url=doc_url(f), locator=f"{f['form']} {p.chunk_id}", excerpt=p.text))
        self.shown.add(p.chunk_id)
        return {"evidence_id": eid, "chunk_id": p.chunk_id, "form": f["form"], "filed": f["filed"],
                "accession_number": f["accession_number"], "period_end": f.get("report_date"), "score": round(score, 4),
                "text": p.text[:self.config.passage_chars_in_prompt]}

    def manifest(self) -> dict:
        return {"filings": [{**{k: f[k] for k in ("form", "accession_number", "filed", "report_date", "primary_document")},
                             "sha256": document_sha256(f["accession_number"], f["primary_document"])} for f in self.filings],
                "unavailable": [f["accession_number"] for f in self.unavailable], "passages_indexed": len(self.passages)}


# -------------------------------------------------------- corpus build

def build_corpus(claims, config: RetrievalConfig | None = None, allow_network: bool = False) -> list[dict]:
    """Report (and, with allow_network=True, download from SEC EDGAR) every
    document the claims' cutoffs make eligible. SEC access is free; it is
    still off by default so experiments stay offline and reproducible."""
    config = config or RetrievalConfig()
    rows, seen = [], set()
    for c in claims:
        if allow_network and not os.path.exists(submissions_path(c.company)):
            from sec_client import get_submissions
            get_submissions(c.company)
            _submissions.cache_clear()
        for f in eligible_filings(c.company, c.as_of_date, c.allowed_forms(), config.max_filings_per_form):
            key = (f["accession_number"], f["primary_document"])
            if key in seen:
                continue
            seen.add(key)
            path = document_path(*key)
            if not os.path.exists(path) and allow_network:
                from sec_client import get_document_text
                get_document_text(_cik(c.company), *key)
            rows.append({"company": c.company, "form": f["form"], "filed": f["filed"], "report_date": f["report_date"],
                         "accession_number": f["accession_number"], "primary_document": f["primary_document"],
                         "cached": os.path.exists(path), "sha256": document_sha256(*key)})
    document_text.cache_clear()
    _chunks.cache_clear()
    return rows
