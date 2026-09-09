"""SQLite persistence layer -- Phase D/E prep (production-hardening pass,
see README.md). Uses the stdlib `sqlite3` module, not an ORM, to keep the
same "no framework where plain code does the job" discipline this project
has followed elsewhere (e.g. agent.py calling the Anthropic API directly
instead of pulling in the SDK).

Deliberately additive, not a replacement of `tools.REASON_DEFS`:
`REASON_DEFS` is depended on directly by 11 already-tested scripts
(agent.py, baseline1/2.py, run_full_experiment.py, ...); rewriting all of
them to read reasons from the database in one pass would risk regressing
work that's already been validated against real SEC data and real money.
Instead:

- The 3 built-in reasons are seeded into the `reasons` table on first init
  (so everything is queryable from one place going forward), but existing
  code keeps reading `REASON_DEFS` unchanged.
- NEW custom reasons (user-entered thresholds, reasons for tickers beyond
  the built-in 3) go into the database -- this is what the Web UI (Phase D)
  actually needs: a place to persist what an investor typed in, not a
  replacement for the already-tested rule engine's defaults.
- Investor profiles move from the hardcoded `ALL_PROFILES` list in
  investor_profile.py into the database, so the Web UI can create/list/
  edit them instead of only ever using the 4 synthetic ones.
- Every `run_with_llm` / `investigate_and_personalize` result gets
  persisted to `investigation_runs` -- a permanent history instead of the
  scattered per-experiment JSON files under data/.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get("INVESMENT_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "invesment.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS reasons (
    reason_key         TEXT PRIMARY KEY,
    ticker              TEXT,           -- NULL = applies to any ticker (built-in reasons)
    metric              TEXT NOT NULL,
    comparison          TEXT NOT NULL,  -- '>' | '>=' | '<' | '<='
    threshold           REAL NOT NULL,
    kind                TEXT NOT NULL,  -- 'yoy_growth' | 'margin_level'
    denominator_metric  TEXT DEFAULT '',
    description         TEXT NOT NULL,
    is_builtin          INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS investor_profiles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL UNIQUE,
    risk_tolerance      TEXT NOT NULL,  -- 'low' | 'medium' | 'high'
    investment_horizon  TEXT NOT NULL,  -- '<1y' | '1-5y' | '>5y'
    position_size_pct   REAL NOT NULL,
    objective           TEXT NOT NULL,  -- 'growth' | 'income' | 'preservation'
    is_builtin          INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS investigation_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker              TEXT NOT NULL,
    reason_key          TEXT NOT NULL,
    status              TEXT,
    confidence          TEXT,
    human_review_recommended INTEGER,
    rationale           TEXT,
    escalated           INTEGER NOT NULL DEFAULT 0,
    escalation_reason   TEXT,
    profile_name        TEXT,           -- NULL if this run wasn't personalized
    rule_based_tier     TEXT,
    llm_tier            TEXT,
    integrity_ok        INTEGER,
    trace_json          TEXT,           -- json-encoded trace list
    input_tokens        INTEGER,
    output_tokens        INTEGER,
    created_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_ticker ON investigation_runs (ticker);
CREATE INDEX IF NOT EXISTS idx_runs_created ON investigation_runs (created_at);
"""


@contextmanager
def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if missing, and seed the 3 built-in reasons + 4 built-in
    investor profiles on first run (idempotent -- INSERT OR IGNORE).
    """
    with get_conn() as conn:
        conn.executescript(SCHEMA)

        from tools import REASON_DEFS
        now = datetime.now(timezone.utc).isoformat()
        for key, r in REASON_DEFS.items():
            conn.execute(
                "INSERT OR IGNORE INTO reasons "
                "(reason_key, ticker, metric, comparison, threshold, kind, denominator_metric, description, is_builtin, created_at) "
                "VALUES (?, NULL, ?, ?, ?, ?, ?, ?, 1, ?)",
                (key, r.metric, r.comparison, r.threshold, r.kind, r.denominator_metric, r.description, now),
            )

        from investor_profile import ALL_PROFILES
        for p in ALL_PROFILES:
            conn.execute(
                "INSERT OR IGNORE INTO investor_profiles "
                "(name, risk_tolerance, investment_horizon, position_size_pct, objective, is_builtin, created_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?)",
                (p.name, p.risk_tolerance, p.investment_horizon, p.position_size_pct, p.objective, now),
            )


# ---------------------------------------------------------------------------
# Reasons
# ---------------------------------------------------------------------------

def save_reason(reason_key: str, ticker: str | None, metric: str, comparison: str, threshold: float,
                kind: str, description: str, denominator_metric: str = "") -> None:
    """Persist a user-entered custom reason (Web UI, Phase D). Built-in
    reasons are seeded by init_db() and shouldn't be re-saved through here.
    """
    if comparison not in (">", ">=", "<", "<="):
        raise ValueError(f"comparison must be one of '>','>=','<','<=', got {comparison!r}")
    if kind not in ("yoy_growth", "margin_level"):
        raise ValueError(f"kind must be 'yoy_growth' or 'margin_level', got {kind!r}")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reasons (reason_key, ticker, metric, comparison, threshold, kind, "
            "denominator_metric, description, is_builtin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)"
            " ON CONFLICT(reason_key) DO UPDATE SET ticker=excluded.ticker, metric=excluded.metric, "
            "comparison=excluded.comparison, threshold=excluded.threshold, kind=excluded.kind, "
            "denominator_metric=excluded.denominator_metric, description=excluded.description",
            (reason_key, ticker, metric, comparison, threshold, kind, denominator_metric,
             description, datetime.now(timezone.utc).isoformat()),
        )


def list_reasons(ticker: str | None = None) -> list[dict]:
    """Built-in reasons (ticker IS NULL, apply to everything) plus any custom
    reasons scoped to `ticker` if given.
    """
    with get_conn() as conn:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM reasons WHERE ticker IS NULL OR ticker = ? ORDER BY is_builtin DESC, reason_key",
                (ticker,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM reasons ORDER BY is_builtin DESC, reason_key").fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Investor profiles
# ---------------------------------------------------------------------------

def save_profile(name: str, risk_tolerance: str, investment_horizon: str,
                  position_size_pct: float, objective: str) -> int:
    if risk_tolerance not in ("low", "medium", "high"):
        raise ValueError(f"risk_tolerance must be low/medium/high, got {risk_tolerance!r}")
    if investment_horizon not in ("<1y", "1-5y", ">5y"):
        raise ValueError(f"investment_horizon must be <1y/1-5y/>5y, got {investment_horizon!r}")
    if objective not in ("growth", "income", "preservation"):
        raise ValueError(f"objective must be growth/income/preservation, got {objective!r}")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO investor_profiles (name, risk_tolerance, investment_horizon, position_size_pct, "
            "objective, is_builtin, created_at) VALUES (?, ?, ?, ?, ?, 0, ?) "
            "ON CONFLICT(name) DO UPDATE SET risk_tolerance=excluded.risk_tolerance, "
            "investment_horizon=excluded.investment_horizon, position_size_pct=excluded.position_size_pct, "
            "objective=excluded.objective",
            (name, risk_tolerance, investment_horizon, position_size_pct, objective,
             datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def list_profiles() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM investor_profiles ORDER BY is_builtin DESC, name").fetchall()
        return [dict(r) for r in rows]


def get_profile_by_name(name: str):
    """Returns an investor_profile.InvestorProfile, or None if not found."""
    from investor_profile import InvestorProfile
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM investor_profiles WHERE name = ?", (name,)).fetchone()
    if not row:
        return None
    return InvestorProfile(
        name=row["name"], risk_tolerance=row["risk_tolerance"],
        investment_horizon=row["investment_horizon"],
        position_size_pct=row["position_size_pct"], objective=row["objective"],
    )


# ---------------------------------------------------------------------------
# Investigation runs
# ---------------------------------------------------------------------------

def save_run(ticker: str, reason: dict, trace: list[str], usage: dict,
             escalated: bool = False, escalation_reason: str | None = None,
             profile_name: str | None = None) -> int:
    """Persist one reason's result from a run_with_llm / investigate_and_personalize
    call. Call once per reason in the result (or once with an empty `reason`
    dict for an escalated run that produced none).
    """
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO investigation_runs (ticker, reason_key, status, confidence, "
            "human_review_recommended, rationale, escalated, escalation_reason, profile_name, "
            "rule_based_tier, llm_tier, integrity_ok, trace_json, input_tokens, output_tokens, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ticker, reason.get("reason_key", ""), reason.get("status"), reason.get("confidence"),
                int(bool(reason.get("human_review_recommended", False))), reason.get("rationale"),
                int(escalated), escalation_reason, profile_name,
                reason.get("rule_based_tier"), reason.get("llm_tier"),
                None if "integrity_ok" not in reason else int(bool(reason["integrity_ok"])),
                json.dumps(trace), usage.get("input_tokens"), usage.get("output_tokens"),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return cur.lastrowid


def save_investigation_result(result: dict, profile_name: str | None = None) -> list[int]:
    """Convenience wrapper: persist every reason in a run_with_llm (or
    investigate_and_personalize) result dict in one call. Handles the
    escalated-with-no-reasons case too.
    """
    ticker = result["ticker"]
    if result.get("escalated"):
        return [save_run(
            ticker, {}, result["trace"], result["usage"],
            escalated=True, escalation_reason=result.get("escalation_reason"),
            profile_name=profile_name,
        )]
    return [
        save_run(ticker, r, result["trace"], result["usage"], profile_name=profile_name)
        for r in result["reasons"]
    ]


def list_runs(ticker: str | None = None, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM investigation_runs WHERE ticker = ? ORDER BY created_at DESC LIMIT ?",
                (ticker, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM investigation_runs ORDER BY created_at DESC LIMIT ?", (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print(f"Initialized DB at {os.path.abspath(DB_PATH)}")
    print(f"  {len(list_reasons())} reason(s) seeded")
    print(f"  {len(list_profiles())} investor profile(s) seeded")
