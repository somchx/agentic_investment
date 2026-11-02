"""Local web frontend for the Phase 1 pipeline -- the "My reasons for
investing" dashboard from PROPOSAL.md section 7, browsable instead of only
readable as terminal output. Now multi-user: register/login gate the app,
and every reason/profile/purchase is private to the logged-in user.

Everything is free (SEC data only, no LLM calls) except two routes: "Ask AI
Agent" (calls agent.run_with_llm on demand) and "Personalize" (calls
investigate_and_personalize) -- both spend real API budget only when the
user explicitly clicks them, never automatically.

Usage:
    python3 webapp.py
    (then open http://127.0.0.1:5050)
"""

import functools
import os
import secrets

from flask import Flask, jsonify, render_template, request, session

import db
from agent import run_with_llm
from personalization import investigate_and_personalize
from portfolio_report import STATUS_ICON, build_company_reasons, evaluate
from sec_client import KNOWN_CIKS, get_company_facts
from tools import check_reason_status
from xbrl_extract import list_available_tags

app = Flask(__name__)
# A fresh random key each process start is fine for local single-instance
# dev (sessions just don't survive a restart) -- set INVESMENT_SECRET_KEY
# in the environment for a stable key across restarts.
app.secret_key = os.environ.get("INVESMENT_SECRET_KEY") or secrets.token_hex(32)
db.init_db()


def login_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "not logged in"}), 401
        return fn(*args, **kwargs)
    return wrapper


def current_user_id() -> int:
    return session["user_id"]


def get_company_report(ticker: str, user_id: int | None) -> dict:
    company_name, reasons = build_company_reasons(ticker, user_id=user_id)

    out_reasons = []
    for reason, facts, denom_facts in reasons:
        reason_dates = sorted({f.filed for f in facts})
        if len(reason_dates) < 2:
            out_reasons.append({
                "key": reason.reason_id,
                "description": reason.description,
                "status": "Not enough data",
                "icon": STATUS_ICON["Not enough data"],
                "computed_value": None,
                "as_of": None,
                "explanation": "Not enough filing history for this metric yet.",
                "evidence": [],
                "previous_status": None,
                "changed": False,
            })
            continue

        latest_as_of, previous_as_of = reason_dates[-1], reason_dates[-2]
        latest = evaluate(reason, facts, denom_facts, latest_as_of)
        previous = evaluate(reason, facts, denom_facts, previous_as_of)

        out_reasons.append({
            "key": reason.reason_id,
            "description": reason.description,
            "status": latest.status,
            "icon": STATUS_ICON[latest.status],
            "computed_value": latest.computed_value,
            "as_of": latest_as_of,
            "explanation": latest.explanation,
            "evidence": [f.label() for f in latest.supporting_evidence],
            "conflicting_evidence": [f.label() for f in latest.conflicting_evidence],
            "previous_status": previous.status,
            "previous_as_of": previous_as_of,
            "changed": previous.status != latest.status,
        })

    return {"ticker": ticker, "company": company_name, "reasons": out_reasons}


@app.route("/")
def index():
    return render_template("index.html", tickers=sorted(KNOWN_CIKS.keys()))


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route("/api/register", methods=["POST"])
def api_register():
    body = request.get_json(force=True) or {}
    email, password = body.get("email", ""), body.get("password", "")
    try:
        user_id = db.create_user(email, password)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:  # noqa: BLE001 -- sqlite3.IntegrityError on duplicate email
        return jsonify({"error": "that email is already registered"}), 409
    session["user_id"] = user_id
    session["email"] = email.lower().strip()
    return jsonify({"ok": True, "user": {"id": user_id, "email": session["email"]}})


@app.route("/api/login", methods=["POST"])
def api_login():
    body = request.get_json(force=True) or {}
    user = db.verify_user(body.get("email", ""), body.get("password", ""))
    if not user:
        return jsonify({"error": "incorrect email or password"}), 401
    session["user_id"] = user["id"]
    session["email"] = user["email"]
    return jsonify({"ok": True, "user": user})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me")
def api_me():
    if "user_id" not in session:
        return jsonify({"error": "not logged in"}), 401
    return jsonify({"id": session["user_id"], "email": session["email"]})


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@app.route("/api/report/<ticker>")
@login_required
def api_report(ticker):
    try:
        return jsonify(get_company_report(ticker.upper(), current_user_id()))
    except Exception as e:  # noqa: BLE001 -- surface the real error to the frontend
        return jsonify({"error": str(e)}), 500


@app.route("/api/ask-agent/<ticker>")
@login_required
def api_ask_agent(ticker):
    try:
        result = run_with_llm(ticker.upper())
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500
    return jsonify(result)


# ---------------------------------------------------------------------------
# Investor profiles
# ---------------------------------------------------------------------------

@app.route("/api/profiles", methods=["GET"])
@login_required
def api_list_profiles():
    return jsonify(db.list_profiles(current_user_id()))


@app.route("/api/profiles", methods=["POST"])
@login_required
def api_create_profile():
    body = request.get_json(force=True) or {}
    required = {"name", "risk_tolerance", "investment_horizon", "position_size_pct", "objective"}
    missing = required - body.keys()
    if missing:
        return jsonify({"error": f"missing field(s): {sorted(missing)}"}), 400
    try:
        db.save_profile(
            user_id=current_user_id(),
            name=body["name"],
            risk_tolerance=body["risk_tolerance"],
            investment_horizon=body["investment_horizon"],
            position_size_pct=float(body["position_size_pct"]),
            objective=body["objective"],
        )
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "profiles": db.list_profiles(current_user_id())})


@app.route("/api/runs")
@login_required
def api_list_runs():
    ticker = request.args.get("ticker") or None
    limit = min(int(request.args.get("limit", 30)), 200)
    return jsonify(db.list_runs(ticker=ticker, limit=limit))


@app.route("/api/personalize/<ticker>")
@login_required
def api_personalize(ticker):
    profile_name = request.args.get("profile")
    if not profile_name:
        return jsonify({"error": "missing ?profile=<name> query param"}), 400
    profile = db.get_profile_by_name(profile_name, current_user_id())
    if not profile:
        return jsonify({"error": f"no investor profile named {profile_name!r}"}), 404
    try:
        result = investigate_and_personalize(ticker.upper(), profile)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500
    return jsonify(result)


# ---------------------------------------------------------------------------
# Custom reasons
# ---------------------------------------------------------------------------

@app.route("/api/xbrl-tags/<ticker>")
@login_required
def api_xbrl_tags(ticker):
    """Every XBRL tag this specific company has actually reported -- the
    picker for defining a custom reason draws from this, never free text,
    so a custom reason can never reference a tag that doesn't exist for
    the company.
    """
    try:
        facts_json = get_company_facts(ticker.upper())
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500
    return jsonify(list_available_tags(facts_json))


@app.route("/api/reasons")
@login_required
def api_list_all_reasons():
    """Built-in reasons + every custom reason this user has defined, across
    any ticker -- for pickers that aren't scoped to one company (the
    Screener's condition dropdown, and Record Purchase's "because this
    reason was true" dropdown falls back to this if the ticker has none of
    its own).
    """
    return jsonify(db.list_reasons(user_id=current_user_id()))


@app.route("/api/reasons/<ticker>")
@login_required
def api_list_reasons(ticker):
    """This user's own custom (non-built-in) reasons for this ticker --
    for a management list in the UI. Built-in reasons are already implicit
    in every /api/report/<ticker> response and don't need their own
    listing.
    """
    rows = [r for r in db.list_reasons(ticker=ticker.upper(), user_id=current_user_id()) if not r["is_builtin"]]
    return jsonify(rows)


@app.route("/api/reasons", methods=["POST"])
@login_required
def api_create_reason():
    body = request.get_json(force=True) or {}
    required = {"reason_key", "ticker", "metric", "comparison", "threshold", "kind", "description", "instant"}
    missing = required - body.keys()
    if missing:
        return jsonify({"error": f"missing field(s): {sorted(missing)}"}), 400
    if body["reason_key"] in ("revenue_growth", "operating_margin", "debt_growth"):
        return jsonify({"error": "reason_key collides with a built-in reason"}), 400
    try:
        db.save_reason(
            reason_key=body["reason_key"],
            user_id=current_user_id(),
            ticker=body["ticker"].upper(),
            metric=body["metric"],
            comparison=body["comparison"],
            threshold=float(body["threshold"]),
            kind=body["kind"],
            description=body["description"],
            denominator_metric=body.get("denominator_metric", ""),
            instant=bool(body["instant"]),
        )
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400
    # Confirm it actually computes something before telling the caller it
    # succeeded -- a tag picked from list_available_tags should always work,
    # but a margin reason's denominator could still turn out empty for this
    # specific ticker even though the tag exists company-wide in general.
    check = check_reason_status(body["ticker"].upper(), body["reason_key"])
    return jsonify({"ok": True, "preview": check})


@app.route("/api/reasons/<reason_key>", methods=["DELETE"])
@login_required
def api_delete_reason(reason_key):
    db.delete_reason(reason_key, current_user_id())
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Screener -- run any reason (built-in or a user's own custom one) across
# every known company, mechanically. This is NOT an opinion about what to
# buy: it's the exact same deterministic check_reason_status the rest of
# the app uses for one company, just looped over all of them. No LLM.
# ---------------------------------------------------------------------------

@app.route("/api/screen")
@login_required
def api_screen():
    reason_key = request.args.get("reason_key")
    if not reason_key:
        return jsonify({"error": "missing ?reason_key=<key>"}), 400
    matches, errors = [], []
    for ticker in sorted(KNOWN_CIKS.keys()):
        result = check_reason_status(ticker, reason_key)
        if "error" in result:
            errors.append({"ticker": ticker, "error": result["error"]})
            continue
        matches.append({
            "ticker": ticker, "company": result["company"], "status": result["status"],
            "computed_value": result["computed_value"], "as_of": result["as_of"],
        })
    matches.sort(key=lambda m: {"Supported": 0, "Weakened": 1, "Not enough data": 2, "Broken": 3}.get(m["status"], 9))
    return jsonify({"reason_key": reason_key, "matches": matches, "skipped": errors})


# ---------------------------------------------------------------------------
# Purchases -- the real position record, with a frozen snapshot of the
# reason that justified the buy so later edits (or the reason's status
# simply changing over time) can never rewrite what was true at purchase.
# ---------------------------------------------------------------------------

@app.route("/api/purchases", methods=["GET"])
@login_required
def api_list_purchases():
    ticker = request.args.get("ticker")
    return jsonify(db.list_purchases(current_user_id(), ticker=ticker))


@app.route("/api/purchases", methods=["POST"])
@login_required
def api_record_purchase():
    body = request.get_json(force=True) or {}
    required = {"ticker", "quantity", "purchase_price", "purchase_date"}
    missing = required - body.keys()
    if missing:
        return jsonify({"error": f"missing field(s): {sorted(missing)}"}), 400
    ticker = body["ticker"].upper()
    reason_key = body.get("reason_key") or None

    snapshot = None
    if reason_key:
        check = check_reason_status(ticker, reason_key)
        if "error" in check:
            return jsonify({"error": f"could not evaluate reason_key for snapshot: {check['error']}"}), 400
        snapshot = {
            "description": check["reason"],
            "status_at_purchase": check["status"],
            "computed_value_at_purchase": check["computed_value"],
            "explanation_at_purchase": check["explanation"],
        }

    try:
        pid = db.record_purchase(
            user_id=current_user_id(), ticker=ticker,
            quantity=float(body["quantity"]), purchase_price=float(body["purchase_price"]),
            purchase_date=body["purchase_date"], reason_key=reason_key, reason_snapshot=snapshot,
        )
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "id": pid, "reason_snapshot": snapshot})


@app.route("/api/purchases/<int:purchase_id>", methods=["DELETE"])
@login_required
def api_delete_purchase(purchase_id):
    db.delete_purchase(purchase_id, current_user_id())
    return jsonify({"ok": True})


@app.route("/api/portfolio/summary")
@login_required
def api_portfolio_summary():
    """Aggregate the free, already-built per-company report across every
    ticker this user has a purchase record for. A ticker not in
    sec_client.KNOWN_CIKS (data not available) is reported with an error
    per-company rather than failing the whole summary. For each held
    ticker, also reports whether every purchase's reason is still holding
    (the point of the feature): compares each purchase's frozen
    status_at_purchase against the reason's CURRENT status.
    """
    user_id = current_user_id()
    held = db.list_held_tickers(user_id)
    companies = []
    totals = {"Supported": 0, "Weakened": 0, "Broken": 0, "Not enough data": 0}
    for ticker in held:
        try:
            report = get_company_report(ticker, user_id)
        except Exception as e:  # noqa: BLE001
            companies.append({"ticker": ticker, "error": str(e)})
            continue
        for r in report["reasons"]:
            if r["status"] in totals:
                totals[r["status"]] += 1
        worst = "Supported"
        rank = {"Supported": 0, "Not enough data": 1, "Weakened": 2, "Broken": 3}
        for r in report["reasons"]:
            if rank.get(r["status"], 0) > rank.get(worst, 0):
                worst = r["status"]

        purchases = db.list_purchases(user_id, ticker=ticker)
        for p in purchases:
            if not p["reason_key"] or not p["reason_snapshot"]:
                p["still_true"] = None
                continue
            current = check_reason_status(ticker, p["reason_key"])
            p["current_status"] = current.get("status")
            p["still_true"] = (
                current.get("status") == p["reason_snapshot"]["status_at_purchase"]
                if "error" not in current else None
            )

        companies.append({
            "ticker": ticker, "company": report["company"], "worst_status": worst,
            "reason_count": len(report["reasons"]), "purchases": purchases,
        })
    return jsonify({"held": held, "totals": totals, "companies": companies})


if __name__ == "__main__":
    # use_reloader=False: this environment's `watchdog` install is incompatible
    # with Werkzeug's reloader (ImportError on EVENT_TYPE_OPENED); debug mode's
    # in-browser error pages still work without it, just no autoreload on save.
    app.run(debug=True, port=5050, use_reloader=False)
