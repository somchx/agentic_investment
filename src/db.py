"""SQLite persistence layer, now multi-user. Uses the stdlib `sqlite3`
module, not an ORM, to keep the same "no framework where plain code does
the job" discipline this project has followed elsewhere (e.g. agent.py
calling the Anthropic API directly instead of pulling in the SDK).

Deliberately additive, not a replacement of `tools.REASON_DEFS`:
`REASON_DEFS` is depended on directly by 11 already-tested scripts
(agent.py, baseline1/2.py, run_full_experiment.py, ...); rewriting all of
them to read reasons from the database in one pass would risk regressing
work that's already been validated against real SEC data and real money.
Instead:

- The 3 built-in reasons are seeded into the `reasons` table on first init
  (user_id NULL -- shared by everyone), but existing code keeps reading
  REASON_DEFS unchanged.
- Every other table (custom reasons, investor profiles, purchases) carries
  a `user_id` -- each user's data is private to them. Auth is basic
  email+password (werkzeug's hasher, ships with Flask -- no new
  dependency), sessions via Flask's signed cookie, appropriate for a
  single local instance rather than a public multi-tenant deployment.
- `purchases` (not just a watchlist "holdings" table) is the real record
  of what the user says they bought: ticker, quantity, price, date, and a
  snapshot of which reason justified the buy *and what its status was at
  that moment* -- so "is the reason I bought this for still true" can be
  answered by comparing the snapshot to the reason's current status,
  point-in-time, the same discipline the rest of this project applies to
  SEC filings.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

DB_PATH = os.environ.get("INVESMENT_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "invesment.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    email               TEXT NOT NULL UNIQUE,
    password_hash       TEXT NOT NULL,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reasons (
    reason_key         TEXT PRIMARY KEY,
    user_id             INTEGER,        -- NULL = built-in, shared by everyone
    ticker              TEXT,           -- NULL = applies to any ticker (built-in reasons, or a custom reason marked "global")
    metric              TEXT NOT NULL,  -- raw XBRL tag for custom reasons; curated METRIC_TAGS key for built-in
    comparison          TEXT NOT NULL,  -- '>' | '>=' | '<' | '<='
    threshold           REAL NOT NULL,
    kind                TEXT NOT NULL,  -- 'yoy_growth' | 'margin_level'
    denominator_metric  TEXT DEFAULT '',
    description         TEXT NOT NULL,
    instant             INTEGER NOT NULL DEFAULT 0,  -- 1 = balance-sheet snapshot tag, 0 = duration/quarterly-flow tag
    is_builtin          INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS investor_profiles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER,        -- NULL = built-in, shared by everyone
    name                TEXT NOT NULL,
    risk_tolerance      TEXT NOT NULL,  -- 'low' | 'medium' | 'high'
    investment_horizon  TEXT NOT NULL,  -- '<1y' | '1-5y' | '>5y'
    position_size_pct   REAL NOT NULL,
    objective           TEXT NOT NULL,  -- 'growth' | 'income' | 'preservation'
    is_builtin          INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL,
    UNIQUE(user_id, name)
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

-- The real position record (replaces the old ticker-only "holdings" list):
-- what was bought, how much, when, and -- the point of the whole feature --
-- a frozen snapshot of the reason that justified the buy and what its
-- status was AT THAT MOMENT, so it can never be silently rewritten by a
-- later edit to the reason itself.
CREATE TABLE IF NOT EXISTS purchases (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    ticker              TEXT NOT NULL,
    quantity            REAL NOT NULL,
    purchase_price      REAL NOT NULL,
    purchase_date       TEXT NOT NULL,  -- ISO date the user says they bought
    reason_key          TEXT,           -- which reason justified the buy (nullable -- "just buying it" is allowed)
    reason_snapshot_json TEXT,          -- {description, metric, comparison, threshold, kind, status_at_purchase, computed_value_at_purchase}
    created_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_purchases_user ON purchases (user_id);
CREATE INDEX IF NOT EXISTS idx_purchases_ticker ON purchases (user_id, ticker);
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
    investor profiles (user_id NULL -- shared) on first run (idempotent).
    """
    with get_conn() as conn:
        conn.executescript(SCHEMA)

        from tools import REASON_DEFS
        now = datetime.now(timezone.utc).isoformat()
        for key, r in REASON_DEFS.items():
            conn.execute(
                "INSERT OR IGNORE INTO reasons "
                "(reason_key, user_id, ticker, metric, comparison, threshold, kind, denominator_metric, description, instant, is_builtin, created_at) "
                "VALUES (?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (key, r.metric, r.comparison, r.threshold, r.kind, r.denominator_metric, r.description, int(r.instant), now),
            )

        from investor_profile import ALL_PROFILES
        for p in ALL_PROFILES:
            conn.execute(
                "INSERT OR IGNORE INTO investor_profiles "
                "(user_id, name, risk_tolerance, investment_horizon, position_size_pct, objective, is_builtin, created_at) "
                "VALUES (NULL, ?, ?, ?, ?, ?, 1, ?)",
                (p.name, p.risk_tolerance, p.investment_horizon, p.position_size_pct, p.objective, now),
            )


# ---------------------------------------------------------------------------
# Users / auth
# ---------------------------------------------------------------------------

def create_user(email: str, password: str) -> int:
    """Raises sqlite3.IntegrityError if the email is already registered --
    callers should catch that and return a friendly "already registered"
    rather than a 500.
    """
    if not email or "@" not in email:
        raise ValueError("a valid email is required")
    if not password or len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email.lower().strip(), generate_password_hash(password), datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def verify_user(email: str, password: str) -> dict | None:
    """Returns {id, email} on success, None on bad email/password. Doesn't
    distinguish "no such user" from "wrong password" in what it returns --
    that distinction belongs in a timing-safe login endpoint, not here."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return None
    return {"id": row["id"], "email": row["email"]}


def get_user_by_id(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Reasons
# ---------------------------------------------------------------------------

def save_reason(reason_key: str, user_id: int, ticker: str | None, metric: str, comparison: str,
                threshold: float, kind: str, description: str, denominator_metric: str = "",
                instant: bool = False) -> None:
    """Persist a user-entered custom reason. Built-in reasons (user_id NULL)
    are seeded by init_db() and shouldn't be re-saved through here.

    `ticker=None` means "apply this condition to any company" (for
    screening across all companies) -- the caller is responsible for only
    allowing that when the picked tag is a standard, widely-reported
    concept; a company-specific custom tag should stay scoped to that one
    ticker. `metric` (and `denominator_metric`) must be a raw XBRL tag name
    a company has actually reported -- sourced from
    xbrl_extract.list_available_tags(), never free text.
    """
    if comparison not in (">", ">=", "<", "<="):
        raise ValueError(f"comparison must be one of '>','>=','<','<=', got {comparison!r}")
    if kind not in ("yoy_growth", "margin_level"):
        raise ValueError(f"kind must be 'yoy_growth' or 'margin_level', got {kind!r}")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reasons (reason_key, user_id, ticker, metric, comparison, threshold, kind, "
            "denominator_metric, description, instant, is_builtin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)"
            " ON CONFLICT(reason_key) DO UPDATE SET ticker=excluded.ticker, metric=excluded.metric, "
            "comparison=excluded.comparison, threshold=excluded.threshold, kind=excluded.kind, "
            "denominator_metric=excluded.denominator_metric, description=excluded.description, "
            "instant=excluded.instant",
            (reason_key, user_id, ticker, metric, comparison, threshold, kind, denominator_metric,
             description, int(instant), datetime.now(timezone.utc).isoformat()),
        )


def delete_reason(reason_key: str, user_id: int) -> None:
    """Remove a custom reason -- scoped to user_id so one user can't delete
    another's (or a built-in, which has user_id NULL and never matches)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM reasons WHERE reason_key = ? AND user_id = ?", (reason_key, user_id))


def list_reasons(ticker: str | None = None, user_id: int | None = None) -> list[dict]:
    """Built-in reasons (user_id IS NULL, apply to everything) plus this
    user's own custom reasons -- global ones (ticker IS NULL) and any
    scoped to `ticker` if given. Pass user_id=None to see only built-ins
    (e.g. for an unauthenticated context).
    """
    with get_conn() as conn:
        clauses = ["is_builtin = 1"]
        params: list = []
        if user_id is not None:
            if ticker:
                clauses.append("(user_id = ? AND (ticker IS NULL OR ticker = ?))")
                params.extend([user_id, ticker])
            else:
                clauses.append("user_id = ?")
                params.append(user_id)
        query = f"SELECT * FROM reasons WHERE {' OR '.join(clauses)} ORDER BY is_builtin DESC, reason_key"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_reason_by_key(reason_key: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM reasons WHERE reason_key = ?", (reason_key,)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Investor profiles
# ---------------------------------------------------------------------------

def save_profile(user_id: int, name: str, risk_tolerance: str, investment_horizon: str,
                  position_size_pct: float, objective: str) -> int:
    if risk_tolerance not in ("low", "medium", "high"):
        raise ValueError(f"risk_tolerance must be low/medium/high, got {risk_tolerance!r}")
    if investment_horizon not in ("<1y", "1-5y", ">5y"):
        raise ValueError(f"investment_horizon must be <1y/1-5y/>5y, got {investment_horizon!r}")
    if objective not in ("growth", "income", "preservation"):
        raise ValueError(f"objective must be growth/income/preservation, got {objective!r}")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO investor_profiles (user_id, name, risk_tolerance, investment_horizon, position_size_pct, "
            "objective, is_builtin, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?) "
            "ON CONFLICT(user_id, name) DO UPDATE SET risk_tolerance=excluded.risk_tolerance, "
            "investment_horizon=excluded.investment_horizon, position_size_pct=excluded.position_size_pct, "
            "objective=excluded.objective",
            (user_id, name, risk_tolerance, investment_horizon, position_size_pct, objective,
             datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def list_profiles(user_id: int | None = None) -> list[dict]:
    """Built-in profiles (shared) plus this user's own."""
    with get_conn() as conn:
        if user_id is not None:
            rows = conn.execute(
                "SELECT * FROM investor_profiles WHERE is_builtin = 1 OR user_id = ? ORDER BY is_builtin DESC, name",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM investor_profiles WHERE is_builtin = 1 ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def get_profile_by_name(name: str, user_id: int | None = None):
    """Returns an investor_profile.InvestorProfile, or None if not found.
    Checks built-ins first, then this user's own profiles of that name.
    """
    from investor_profile import InvestorProfile
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM investor_profiles WHERE name = ? AND (is_builtin = 1 OR user_id = ?)",
            (name, user_id),
        ).fetchone()
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


# ---------------------------------------------------------------------------
# Purchases (real position records, per user)
# ---------------------------------------------------------------------------

def record_purchase(user_id: int, ticker: str, quantity: float, purchase_price: float,
                     purchase_date: str, reason_key: str | None = None,
                     reason_snapshot: dict | None = None) -> int:
    """The point of the whole feature: `reason_snapshot` freezes what the
    reason said *at the moment of purchase* (its description, threshold,
    and computed status) so that later edits to the reason -- or its
    current live status simply changing over time -- can never rewrite
    history. `list_purchases`/`get_purchase_tracking` compares this frozen
    snapshot against the reason's CURRENT status to answer "is the reason I
    bought this for still true."
    """
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO purchases (user_id, ticker, quantity, purchase_price, purchase_date, "
            "reason_key, reason_snapshot_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, ticker.upper(), quantity, purchase_price, purchase_date, reason_key,
             json.dumps(reason_snapshot) if reason_snapshot else None,
             datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def delete_purchase(purchase_id: int, user_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM purchases WHERE id = ? AND user_id = ?", (purchase_id, user_id))


def list_purchases(user_id: int, ticker: str | None = None) -> list[dict]:
    with get_conn() as conn:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM purchases WHERE user_id = ? AND ticker = ? ORDER BY purchase_date DESC",
                (user_id, ticker.upper()),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM purchases WHERE user_id = ? ORDER BY purchase_date DESC", (user_id,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["reason_snapshot"] = json.loads(d["reason_snapshot_json"]) if d["reason_snapshot_json"] else None
            del d["reason_snapshot_json"]
            out.append(d)
        return out


def list_held_tickers(user_id: int) -> list[str]:
    """Distinct tickers this user has any purchase record for -- what the
    Portfolio view rolls up, replacing the old ticker-only holdings list.
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT ticker FROM purchases WHERE user_id = ? ORDER BY ticker", (user_id,),
        ).fetchall()
        return [r["ticker"] for r in rows]


if __name__ == "__main__":
    init_db()
    print(f"Initialized DB at {os.path.abspath(DB_PATH)}")
    print(f"  {len(list_reasons())} built-in reason(s) seeded")
    print(f"  {len(list_profiles())} built-in investor profile(s) seeded")
