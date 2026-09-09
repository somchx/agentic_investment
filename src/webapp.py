"""Local web frontend for the Phase 1 pipeline -- the "My reasons for
investing" dashboard from PROPOSAL.md section 7, browsable instead of only
readable as terminal output.

Everything on page load is free (SEC data only, no LLM calls): it reuses
portfolio_report.py's per-reason latest/previous evaluation. The "Ask AI
Agent" button per company is the only thing that spends API budget -- it
calls agent.run_with_llm on demand, never automatically, so browsing the
dashboard never costs anything by itself.

Usage:
    python3 webapp.py
    (then open http://127.0.0.1:5050)
"""

from flask import Flask, jsonify, render_template, request

import db
from agent import run_with_llm
from personalization import investigate_and_personalize
from portfolio_report import STATUS_ICON, build_company_reasons, evaluate
from sec_client import KNOWN_CIKS

app = Flask(__name__)
db.init_db()


def get_company_report(ticker: str) -> dict:
    company_name, reasons = build_company_reasons(ticker)

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


@app.route("/api/report/<ticker>")
def api_report(ticker):
    try:
        return jsonify(get_company_report(ticker.upper()))
    except Exception as e:  # noqa: BLE001 -- surface the real error to the frontend
        return jsonify({"error": str(e)}), 500


@app.route("/api/ask-agent/<ticker>")
def api_ask_agent(ticker):
    try:
        result = run_with_llm(ticker.upper())
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500
    return jsonify(result)


@app.route("/api/profiles", methods=["GET"])
def api_list_profiles():
    return jsonify(db.list_profiles())


@app.route("/api/profiles", methods=["POST"])
def api_create_profile():
    body = request.get_json(force=True) or {}
    required = {"name", "risk_tolerance", "investment_horizon", "position_size_pct", "objective"}
    missing = required - body.keys()
    if missing:
        return jsonify({"error": f"missing field(s): {sorted(missing)}"}), 400
    try:
        db.save_profile(
            name=body["name"],
            risk_tolerance=body["risk_tolerance"],
            investment_horizon=body["investment_horizon"],
            position_size_pct=float(body["position_size_pct"]),
            objective=body["objective"],
        )
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "profiles": db.list_profiles()})


@app.route("/api/runs")
def api_list_runs():
    ticker = request.args.get("ticker") or None
    limit = min(int(request.args.get("limit", 30)), 200)
    return jsonify(db.list_runs(ticker=ticker, limit=limit))


@app.route("/api/personalize/<ticker>")
def api_personalize(ticker):
    profile_name = request.args.get("profile")
    if not profile_name:
        return jsonify({"error": "missing ?profile=<name> query param"}), 400
    profile = db.get_profile_by_name(profile_name)
    if not profile:
        return jsonify({"error": f"no investor profile named {profile_name!r}"}), 404
    try:
        result = investigate_and_personalize(ticker.upper(), profile)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500
    return jsonify(result)


if __name__ == "__main__":
    # use_reloader=False: this environment's `watchdog` install is incompatible
    # with Werkzeug's reloader (ImportError on EVENT_TYPE_OPENED); debug mode's
    # in-browser error pages still work without it, just no autoreload on save.
    app.run(debug=True, port=5050, use_reloader=False)
