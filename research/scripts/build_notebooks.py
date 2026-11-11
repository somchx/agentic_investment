"""Generate research/notebooks/*.ipynb from the cell sources below.

The notebooks are committed without outputs; edit them here (or in
Jupyter, then keep this file in sync) and re-run:

    research/.venv/bin/python research/scripts/build_notebooks.py
"""
import os

import nbformat as nbf

NB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "notebooks"))

SETUP = '''\
import os, sys, json
from dataclasses import asdict
ROOT = os.path.abspath("..") if os.path.basename(os.getcwd()) == "notebooks" else os.getcwd()
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
import pandas as pd
import matplotlib.pyplot as plt
%matplotlib inline
pd.set_option("display.max_colwidth", 120); pd.set_option("display.width", 200)
print("research root:", ROOT)'''


def md(s):
    return nbf.v4.new_markdown_cell(s)


def code(s, tags=None):
    c = nbf.v4.new_code_cell(s)
    if tags:
        c.metadata["tags"] = tags
    return c


NOTEBOOKS = {}

NOTEBOOKS["01_gold_dataset_validation.ipynb"] = [
    md("# 01 · Gold dataset validation\n\nClaims in `datasets/development_cases.jsonl` (development) and "
       "`datasets/gold_claims.jsonl` (held-out, claims only), and the evaluation reference labels in "
       "`datasets/workbooks/Final_Gold_v3_approved.xlsx` (read through `engine/reference.py`, evaluation code only).\n\n"
       "Checks: claim ids, labels, cutoffs, SEC filing dates against each cutoff, future-period claims, evidence QA status, "
       "and that the claims file approaches read carries no label. Read-only: the last cell proves no file changed."),
    code(SETUP),
    code('''\
from engine.datasets import load_split, check_split_separation
from engine.notebook import banner, load_gold_labels, save_figure
dev, gold = load_split("development"), load_split("gold")
df = pd.DataFrame([asdict(c) for c in dev + gold])
print("development claims:", len(dev), "| gold (held-out) claims:", len(gold))
df[["claim_id", "split", "company", "claim_category", "difficulty", "reporting_period", "as_of_date", "claim"]]'''),
    md("## Distribution by company, category and difficulty"),
    code('''\
display(pd.crosstab([df.split, df.company], df.claim_category, margins=True))
display(pd.crosstab(df.split, df.difficulty.fillna("unset")))
TARGET_PER_CATEGORY = 50
progress = (df[df.split == "gold"].claim_category.value_counts()
            .reindex(["numerical", "interpretive", "ambiguous"], fill_value=0).rename("gold_claims").to_frame())
progress["target"] = TARGET_PER_CATEGORY
progress["remaining"] = (progress.target - progress.gold_claims).clip(lower=0)
progress'''),
    md("## Reference labels: provenance and distribution"),
    code('''\
import glob
from engine.datasets import DATASET_DIR, file_sha256, load_annotations
from engine.reference import REFERENCE_PATH, load_reference, validate_reference
from engine.schema import ClaimInput
watched = [REFERENCE_PATH, *glob.glob(os.path.join(DATASET_DIR, "*.jsonl"))]
before = {p: file_sha256(p) for p in watched}
ref = load_reference()
prov = ref["provenance"]
display(pd.Series({k: v for k, v in prov.items() if k != "label_normalisations"}, name="provenance").to_frame())
print("label normalisations:", prov["label_normalisations"] or "none (all labels already canonical)")
lab = pd.DataFrame([{"claim_id": k, **{f: v[f] for f in ("label", "qa_status", "vote_pattern")}} for k, v in ref["labels"].items()])
lab = lab.merge(df[["claim_id", "claim_category", "company"]], on="claim_id", how="left")
display(pd.crosstab(lab.claim_category, lab.label, margins=True))
display(pd.crosstab(lab.company, lab.label, margins=True))'''),
    md("## Validation against the claims file and the SEC corpus\n\n**Errors** block evaluation; **warnings** are "
       "limitations to report. `PERIOD_ENDS_AFTER_CUTOFF` / `NO_ELIGIBLE_FILING_COVERS_PERIOD` mark the claims built to "
       "test future-data leakage: their reference label must be INSUFFICIENT_EVIDENCE."),
    code('''\
v = validate_reference(gold, ref)
print(f"errors: {len(v['errors'])}")
for e in v["errors"]:
    print("  ERROR", e)
for w in v["warnings"]:
    print("  warning:", w)
display(pd.Series(v["qa_status_counts"], name="evidence QA status").to_frame())
vc = pd.DataFrame(v["claims"])
display(vc[vc.issues.apply(len) > 0][["claim_id", "as_of_date", "stated_period_end", "label", "qa_status", "issues"]])
assert not v["errors"], "reference validation failed"'''),
    md("## Claims-only input\n\nEvery gold record must convert to the model input (`ClaimInput`), which refuses any "
       "record carrying a label or annotation field. Human annotations (`datasets/annotations/`) are counted for "
       "completeness; the reference above is what evaluation uses."),
    code('''\
inputs = [c.to_input() for c in gold]
print(len(inputs), "gold claims convert to ClaimInput; fields:", list(inputs[0].to_dict()))
print("human annotations on file:", len(load_annotations()))'''),
    md("## Missing fields"),
    code('''\
missing = pd.DataFrame({
    "reporting_period": df.reporting_period.isna(),
    "difficulty": df.difficulty.isna(),
    "relevant_filings (empty)": df.relevant_filings.apply(lambda x: not x),
    "notes": df.notes.isna(),
}).sum().rename("claims_missing").to_frame()
missing["share"] = (missing.claims_missing / max(len(df), 1)).round(2)
missing'''),
    md("## Evidence availability at each claim's cutoff\n\nEligible = SEC filings in the claim's allowed sources filed on or "
       "before `as_of_date` (the same rule the retriever applies). A missing document can be fetched with "
       "`scripts/build_corpus.py --download` (SEC EDGAR is free)."),
    code('''\
from engine.corpus import eligible_filings, document_path, facts_path, RetrievalConfig
cfg_r = RetrievalConfig()
rows = []
for c in dev + gold:
    ci = c.to_input()
    fl = eligible_filings(ci.company, ci.as_of_date, ci.allowed_forms(), cfg_r.max_filings_per_form)
    cached = [os.path.exists(document_path(f["accession_number"], f["primary_document"])) for f in fl]
    rows.append({"claim_id": c.claim_id, "company": c.company, "as_of_date": c.as_of_date,
                 "eligible_filings": len(fl), "cached": sum(cached),
                 "latest_eligible": max((f["filed"] for f in fl), default=None),
                 "forms": ",".join(sorted({f["form"] for f in fl})),
                 "xbrl_facts": os.path.exists(facts_path(c.company))})
avail = pd.DataFrame(rows)
avail'''),
    md("## Dataset quality warnings"),
    code('''\
import re
warnings = list(check_split_separation(dev, gold))
if not gold:
    warnings.append("gold_claims.jsonl is empty: held-out evaluation cannot run yet")
for cat, n in df[df.split == "gold"].claim_category.value_counts().items():
    if n < TARGET_PER_CATEGORY:
        warnings.append(f"gold category {cat}: {n}/{TARGET_PER_CATEGORY} claims")
for _, r in avail.iterrows():
    if r.eligible_filings == 0:
        warnings.append(f"{r.claim_id}: no eligible filing at cutoff {r.as_of_date}")
    elif r.cached < r.eligible_filings:
        warnings.append(f"{r.claim_id}: {r.eligible_filings - r.cached} eligible document(s) not cached")
    if not r.xbrl_facts:
        warnings.append(f"{r.claim_id}: no XBRL facts file for {r.company}")
months = "January|February|March|April|May|June|July|August|September|October|November|December"
for c in dev + gold:  # a period that ends after the cutoff cannot be verified without future data
    for m in re.finditer(rf"({months}) (\\d{{1,2}}), (\\d{{4}})", c.claim):
        end = pd.Timestamp(f"{m.group(1)} {m.group(2)} {m.group(3)}").date().isoformat()
        if end > c.as_of_date:
            warnings.append(f"{c.claim_id}: refers to a period ending {end}, after its cutoff {c.as_of_date}")
dupes = df[df.duplicated(["company", "claim"], keep=False)]
if len(dupes):
    warnings.append(f"duplicate claim texts: {sorted(dupes.claim_id)}")
counts = df.groupby("split").company.value_counts(normalize=True)
for (split, co), share in counts.items():
    if share > 0.6:
        warnings.append(f"{split}: {co} is {share:.0%} of claims")
print(f"{len(warnings)} warning(s)")
for w in warnings:
    print(" -", w)'''),
    code('''\
fig, ax = plt.subplots(1, 2, figsize=(10, 3.2))
pd.crosstab(df.company, df.split).plot.bar(ax=ax[0], rot=0, title="Claims by company")
pd.crosstab(df.claim_category, df.split).plot.bar(ax=ax[1], rot=0, title="Claims by category")
for a in ax:
    a.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
print("saved", save_figure(fig, "01_dataset_distribution"))'''),
    code('''\
after = {p: file_sha256(p) for p in watched}
assert after == before, "a dataset file changed while this notebook ran"
print("OK: reference workbook and dataset files unchanged")'''),
]

NOTEBOOKS["02_langgraph_pilot.ipynb"] = [
    md("# 02 · LangGraph pilot\n\nA few **development** claims through all four approaches, showing each graph's "
       "shape, the node-by-node execution trace, the evidence retrieved, the deterministic numeric checks and the initial "
       "vs final verdict.\n\n**`MODE` defaults to `mock`** (keyword stand-in, no credentials, not results). `offline_cache` "
       "uses stored model responses only. `live` makes paid Claude calls and needs `APPROVAL_PHRASE` set to the exact "
       "phrase the cost plan prints. Gold claims are never used here."),
    code(SETUP),
    code('''\
CONFIG = "configs/main_comparison.json"
PILOT_CLAIMS = ["DEV-AMZN-06", "DEV-AAPL-04", "DEV-MSFT-02"]
MODE = "mock"                  # mock | offline_cache | live
APPROVAL_PHRASE = ""           # live only''', tags=["parameters"]),
    md("## Graph shapes"),
    code('''\
from graphs import build_graph, mermaid, GRAPH_VERSION
from engine.config import load_config
cfg = load_config(CONFIG)
print("graph version:", GRAPH_VERSION)
for name, a in cfg["approaches"].items():
    g = build_graph(a["kind"], bool(a["contradiction"]["enabled"]) if a["kind"] == "contradiction_aware" else True).get_graph()
    edges = [f"{e.source}->{e.target}" + (" (conditional)" if e.conditional else "") for e in g.edges]
    print(f"{name} [{a['kind']}]\\n   " + "\\n   ".join(edges))
print("\\nMermaid source for A3 (paste into any Mermaid viewer):\\n")
print(mermaid("contradiction_aware"))'''),
    code('''\
from engine import plots
from engine.notebook import save_figure
plots.style()
specs = [("conventional_rag", "A1 Conventional RAG"), ("financial_verification", "A2 RAG + numeric verification"),
         ("contradiction_aware", "A3 Contradiction-aware (proposed)"), ("self_reflection", "SR Self-reflection (control)")]
fig = plots.graph_diagram([(k, t, build_graph(k)) for k, t in specs],
                          "LangGraph StateGraphs of the four claim-verification approaches")
print("saved", save_figure(fig, "langgraph_architecture")); plt.show()'''),
    md("## Run the pilot"),
    code('''\
from engine.runner import select_claims, plan_run, run_experiment, load_run
from engine.llm import approve_paid_run
from engine.notebook import banner, describe_run, trace_index
claims, info = select_claims(cfg, split="development", claim_ids=PILOT_CLAIMS)
plan = plan_run(cfg, claims)
print(f"upper bound: {plan['max_llm_calls']} calls, ${plan['max_cost_usd']:.2f}")
if MODE == "live":
    run = load_run(run_experiment(cfg, claims, info, llm_mode="live", approval=approve_paid_run(plan, APPROVAL_PHRASE)))
elif MODE == "offline_cache":
    run = load_run(run_experiment(cfg, claims, info, llm_mode="offline"))
else:
    run = load_run(run_experiment(cfg, claims, info, llm_mode="mock", progress=lambda s: None))
describe_run(run)
traces = trace_index(run)'''),
    md("## Execution trace (node by node)"),
    code('''\
rows = []
for (approach, cid), t in sorted(traces.items()):
    for i, s in enumerate((t.get("graph") or {}).get("execution_trace", [])):
        rows.append({"approach": approach, "claim_id": cid, "step": i + 1, "node": s["node"], "status": s["status"],
                     "ms": s["duration_ms"], "llm_calls": s["llm_calls_so_far"], "queries": s["retrieval_queries_so_far"],
                     "detail": {k: v for k, v in s.items() if k not in ("node", "status", "duration_ms", "llm_calls_so_far",
                                                                         "retrieval_queries_so_far")}})
steps = pd.DataFrame(rows)
steps[steps.claim_id == PILOT_CLAIMS[0]]'''),
    md("## Retrieved evidence and numeric checks (A3, first pilot claim)"),
    code('''\
t = traces[("A3_contradiction_aware", PILOT_CLAIMS[0])]
print("claim:", t["claim"]["claim"], "| cutoff:", t["claim"]["as_of_date"])
display(pd.DataFrame(t["corpus"]["filings"])[["form", "accession_number", "filed", "report_date"]])
ev = pd.DataFrame(t["evidence"])
display(ev[["evidence_id", "kind", "form", "filed", "period_end", "locator"]].head(15))
checks = [c for s in t["tool_calls"] if s["tool"] == "verify_numbers" for c in s["checks"]]
display(pd.DataFrame([{"metric": c["assertion"].get("metric"), "measure": c["assertion"].get("measure"),
                       "basis": c["assertion"].get("period_basis"), "status": c["status"], "issues": c["issues"],
                       "period": (c["computed"] or {}).get("period_end"), "value": (c["computed"] or {}).get("level"),
                       "yoy": (c["computed"] or {}).get("yoy_change")} for c in checks]))'''),
    md("## Initial vs final verdicts"),
    code('''\
preds = pd.DataFrame(run["predictions"])
cols = ["approach", "claim_id", "initial_label", "predicted_label", "verdict_changed", "stop_reason", "llm_calls",
        "retrieval_queries", "numeric_checks"]
display(preds[cols])
recs = [{"approach": p["approach"], "claim_id": p["claim_id"], **p["second_look_record"]}
        for p in run["predictions"] if p.get("second_look_record")]
pd.DataFrame(recs)'''),
    md("## Data isolation checks"),
    code('''\
from engine.metrics import integrity_metrics
integ = pd.DataFrame(integrity_metrics(run["predictions"], traces))
display(integ)
assert (integ.future_data_leakage_rate == 0).all(), "a run used data filed after its cutoff"
assert set(run["manifest"]["dataset"]["claim_ids"]) <= set(PILOT_CLAIMS) and run["manifest"]["dataset"]["split"] == "development"
print("OK: development claims only; nothing filed after any cutoff was used")'''),
]

NOTEBOOKS["03_baseline_comparison.ipynb"] = [
    md("# 03 · Baseline comparison\n\nRuns or loads the four approaches on the same claims:\n\n"
       "| name | pipeline |\n|---|---|\n| A1 conventional RAG | claim → SEC retrieval → LLM → verdict |\n"
       "| A2 RAG + numeric verification | A1 → deterministic XBRL check → verdict |\n"
       "| A3 contradiction-aware | A2 → challenge questions → counter-evidence retrieval → reconciliation |\n"
       "| SR self-reflection | A2 → self-critique → revision (no new retrieval) |\n\n"
       "**`RUN_MODE` (default `load`) never calls a paid API.**\n\n"
       "- `load`: analyse the newest complete real run (or, if none exists, run a MOCK demo)\n"
       "- `mock`: run the whole pipeline with the keyword mock LLM (no credentials; not results)\n"
       "- `offline_cache`: run using cached model responses only\n"
       "- `live`: paid Claude API calls; set `APPROVAL_PHRASE` to the exact phrase the cost plan prints\n\n"
       "Every run is written to `results/runs/<run_id>/` and locked (read-only + SHA256SUMS) once complete."),
    code(SETUP),
    code('''\
CONFIG = "configs/main_comparison.json"
SPLIT = "development"          # "gold" only for the final held-out evaluation
CLAIM_IDS = None               # e.g. ["DEV-AAPL-01", "DEV-MSFT-04"]
APPROACHES = None              # None = all approaches in the config
RUN_MODE = "load"              # load | mock | offline_cache | live
RUN_ID = None                  # load a specific run
RESUME_RUN_ID = None           # continue an interrupted run (offline_cache / live)
APPROVAL_PHRASE = ""           # live only: paste the confirmation phrase printed below''', tags=["parameters"]),
    code('''\
from engine.config import load_config, config_hash, thaw
from engine.runner import select_claims, plan_run, run_experiment, load_run, verify_run_integrity
from engine.llm import approve_paid_run
from engine.notebook import banner, pick_run, describe_run
cfg = load_config(CONFIG)
print(cfg["description"])
pd.DataFrame([{"approach": n, "kind": a["kind"], "config_hash": config_hash(a), "numeric": a["numeric"]["enabled"],
               "contradiction": a["contradiction"]["enabled"], "reflection": a["reflection"]["enabled"],
               "model": a["llm"]["model"], "temperature": a["llm"]["temperature"], "max_output_tokens": a["llm"]["max_output_tokens"],
               "top_k": a["retrieval"]["top_k"]} for n, a in cfg["approaches"].items()])'''),
    code('''\
print("fairness problems:", cfg["fairness_problems"] or "none")
claims, info = select_claims(cfg, split=SPLIT, claim_ids=CLAIM_IDS, allow_gold=(SPLIT == "gold"))
plan = plan_run(cfg, claims, APPROACHES)
display(pd.DataFrame(plan["approaches"]))
print(f"upper bound: {plan['max_llm_calls']} calls, ${plan['max_cost_usd']:.2f}  (typical ≈ ${plan['typical_cost_usd']:.2f})")
print("To approve a live run, set APPROVAL_PHRASE to exactly:\\n  ", plan["confirmation_phrase"])'''),
    code('''\
if RUN_MODE == "live":
    approval = approve_paid_run(plan, APPROVAL_PHRASE)   # raises unless the phrase matches exactly
    run = load_run(run_experiment(cfg, claims, info, llm_mode="live", approval=approval, approaches=APPROACHES,
                                  resume_run_id=RESUME_RUN_ID))
elif RUN_MODE == "offline_cache":
    run = load_run(run_experiment(cfg, claims, info, llm_mode="offline", approaches=APPROACHES, resume_run_id=RESUME_RUN_ID))
elif RUN_MODE == "mock":
    run = load_run(run_experiment(cfg, claims, info, llm_mode="mock", approaches=APPROACHES, progress=lambda s: None))
else:
    run = pick_run(cfg["experiment_id"], RUN_ID)
    if run is None:
        banner("No stored run for this experiment yet; running the MOCK pipeline so the analysis below has data. "
               "Mock labels are keyword heuristics, not results.", "info")
        run = load_run(run_experiment(cfg, claims, info, llm_mode="mock", approaches=APPROACHES, progress=lambda s: None))
describe_run(run)'''),
    md("## Predictions side by side"),
    code('''\
preds = pd.DataFrame(run["predictions"])
side = preds.pivot_table(index=["claim_id", "claim_category"], columns="approach", values="predicted_label", aggfunc="first")
side'''),
    md("## Initial → final verdicts for the second-look approaches"),
    code('''\
two = preds[preds.approach_kind.isin(["contradiction_aware", "self_reflection"])]
two[["approach", "claim_id", "claim_category", "initial_label", "predicted_label", "verdict_changed", "stop_reason"]]'''),
    md("## How often approaches agree"),
    code('''\
names = list(side.columns)
agree = pd.DataFrame(index=names, columns=names, dtype=float)
for a in names:
    for b in names:
        agree.loc[a, b] = (side[a] == side[b]).mean()
agree.round(2)'''),
    md("## Run health: stop reasons, errors, citations"),
    code('''\
health = preds.groupby("approach").agg(n=("claim_id", "count"), errors=("error", lambda s: s.notna().sum()),
                                       unsupported=("unsupported_conclusion", "sum"),
                                       invalid_citations=("invalid_citations", lambda s: sum(len(x or []) for x in s)),
                                       avg_llm_calls=("llm_calls", "mean"), avg_retrieval_queries=("retrieval_queries", "mean"))
display(health)
display(preds.groupby(["approach", "stop_reason"]).size().unstack(fill_value=0))'''),
    md("## Stored artifacts"),
    code('''\
print(run["run_dir"])
for root, _, files in os.walk(run["run_dir"]):
    depth = root[len(run["run_dir"]):].count(os.sep)
    if depth <= 1:
        print(" ", os.path.relpath(root, run["run_dir"]), f"({len(files)} files)")
print("integrity:", verify_run_integrity(run["run_dir"]) or "all files match SHA256SUMS")'''),
]

NOTEBOOKS["04_contradiction_analysis.ipynb"] = [
    md("# 04 · Contradiction analysis\n\nWhat the contradiction stage (A3) did on each claim: its initial verdict "
       "(= A2), the challenges it raised, the counter-evidence retrieved, and whether the final verdict changed — "
       "compared with the self-reflection control (SR), which gets the same number of extra model calls but no new "
       "evidence. Correctness of changes is judged against the reference labels (Final Gold v3, gold split only)."),
    code(SETUP),
    code('''\
RUN_ID = None
EXPERIMENT_ID = "claimverif-main-v1"''', tags=["parameters"]),
    code('''\
from engine.notebook import banner, pick_run, describe_run, load_gold_labels, reference_banner, trace_index, save_figure
from engine.metrics import second_look_metrics
run = pick_run(EXPERIMENT_ID, RUN_ID)
assert run is not None, "no run found -- execute notebook 03 first"
describe_run(run)
reference_banner()
gold = load_gold_labels()
if not {p["claim_id"] for p in run["predictions"]} & set(gold):
    banner("This run's claims have no reference label (the reference covers the gold split only): the help / harm / "
           "false-contradiction columns are left empty.")
preds = pd.DataFrame(run["predictions"])
traces = trace_index(run)'''),
    md("## A3: initial vs final verdict, and what the investigation found"),
    code('''\
def second_look_rows(kind, key):
    rows = []
    for p in run["predictions"]:
        if p.get("approach_kind") != kind:
            continue
        info = p.get(key) or {}
        g = gold.get(p["claim_id"], {}).get("label")
        rows.append({"approach": p["approach"], "claim_id": p["claim_id"], "category": p["claim_category"],
                     "initial": p.get("initial_label"), "final": p.get("predicted_label"), "changed": p.get("verdict_changed"),
                     "items": len(info.get("hypotheses") or info.get("weaknesses") or []),
                     "counter_passages": len(info.get("counter_evidence_ids") or []),
                     "counter_numeric": len(info.get("counter_numeric") or []),
                     "challenges_supported": info.get("challenges_supported"), "invalid_challenges": info.get("invalid_challenges"),
                     "guard_reverted": info.get("guard_reverted"), "numeric_rule": info.get("final_numeric_rule"),
                     "gold": g, "initial_correct": (p.get("initial_label") == g) if g else None,
                     "final_correct": (p.get("predicted_label") == g) if g else None})
    return pd.DataFrame(rows)
a3 = second_look_rows("contradiction_aware", "contradiction")
sr = second_look_rows("self_reflection", "reflection")
a3'''),
    md("## Verdict transitions"),
    code('''\
for name, d in (("A3 contradiction-aware", a3), ("SR self-reflection", sr)):
    if d.empty:
        print(name, ": not in this run"); continue
    print(f"{name}: changed {int(d.changed.sum())}/{len(d)} verdicts; guard reverted {d.guard_reverted.notna().sum()}; "
          f"challenges asserted without valid evidence: {int(d.invalid_challenges.fillna(0).sum())}")
    display(pd.crosstab(d.initial, d.final, margins=True))'''),
    md("## Second-look metrics\n\nInitial vs final accuracy, verdict-change rate and the four transitions "
       "(incorrect→correct, correct→incorrect, correct→correct, incorrect→incorrect) against the reference; "
       "counter-evidence retrieval success for A3 (share of claims where the investigation found any new passage or "
       "figure)."),
    code('''\
slm = pd.DataFrame(second_look_metrics(run["predictions"], gold))
slm'''),
    md("## Did changes help or harm? (reference-labelled claims only)"),
    code('''\
def outcome(r):
    if r.gold is None or pd.isna(r.gold):
        return None
    if not r.changed:
        return "unchanged"
    return {(False, True): "helped", (True, False): "harmed", (False, False): "changed, still wrong"}.get((r.initial_correct, r.final_correct), "changed")
for name, d in (("A3", a3), ("SR", sr)):
    if d.empty:
        continue
    d["outcome"] = d.apply(outcome, axis=1)
    labelled = d[d.gold.notna()]
    if labelled.empty:
        print(name, ": no labelled claims"); continue
    false_contra = labelled[(labelled.final == "CONTRADICTED") & (labelled.gold != "CONTRADICTED")]
    print(f"{name}: {labelled.outcome.value_counts().to_dict()} | false contradictions: {len(false_contra)}")
    display(pd.crosstab(labelled.category, labelled.outcome))'''),
    md("### Figure: what the contradiction stage changed, by category"),
    code('''\
from engine import plots
plots.style()
if not a3.empty and a3.gold.notna().any():
    lab = a3[a3.gold.notna()]
    rows = []
    for c in plots.CATEGORIES:
        d = lab[lab.category == c]
        ch = d[d.changed == True]  # noqa: E712
        rows.append({"claim_category": c, "n": len(d),
                     "incorrect_to_correct": int(((ch.initial_correct == False) & (ch.final_correct == True)).sum()),  # noqa: E712
                     "correct_to_incorrect": int(((ch.initial_correct == True) & (ch.final_correct == False)).sum()),  # noqa: E712
                     "changed_still_wrong": int(((ch.initial_correct == False) & (ch.final_correct == False)).sum())})  # noqa: E712
    display(pd.DataFrame(rows))
    fig = plots.second_look_transitions(rows, "A3: verdicts changed by the contradiction stage (vs reference)")
    print("saved", save_figure(fig, f"04_transitions_{run['manifest']['run_id']}", run)); plt.show()
else:
    print("skipped: no reference-labelled A3 claims in this run")'''),
    md("## By claim category"),
    code('''\
cat = pd.concat([d.assign(method=n) for n, d in (("A3", a3), ("SR", sr)) if not d.empty])
if not cat.empty:
    summary = cat.groupby(["method", "category"]).agg(claims=("claim_id", "count"), change_rate=("changed", "mean"),
                                                      avg_counter_passages=("counter_passages", "mean"))
    display(summary.round(2))
    fig, ax = plt.subplots(figsize=(6, 2.8))
    summary.change_rate.unstack(0).plot.bar(ax=ax, rot=0, title="Share of verdicts changed by the second look")
    ax.spines[["top", "right"]].set_visible(False); plt.tight_layout()
    print("saved", save_figure(fig, f"04_change_rate_{run['manifest']['run_id']}", run))'''),
    md("## Investigation examples\n\nChallenges, queries and the counter-evidence actually retrieved (changed verdicts first)."),
    code('''\
ex = a3.sort_values("changed", ascending=False).head(3)
for _, r in ex.iterrows():
    t = traces.get((r.approach, r.claim_id)) or {}
    print("=" * 100, f"\\n{r.claim_id}  {r.initial} -> {r.final}   claim: {t.get('claim', {}).get('claim')}")
    inv = next((s for s in t.get("stages", []) if s["stage"] == "contradiction_investigation"), {})
    ev = {e["evidence_id"]: e for e in t.get("evidence", [])}
    for h in inv.get("hypotheses", []):
        print(f"  [{h['hypothesis_id']}] {h['challenge']}\\n      query: {h.get('search_query')}")
    for q in inv.get("queries", []):
        for eid in q["results"][:1]:
            e = ev.get(eid, {})
            print(f"      {q['hypothesis_id']} -> {eid} {e.get('form')} filed {e.get('filed')}: {(e.get('excerpt') or '')[:240]}…")
    rec = next((s for s in t.get("stages", []) if s["stage"] == "reconciliation"), {})
    for a in rec.get("assessments", []):
        print(f"  assessment {a['item_id']}: {a['assessment']}" + (f" (declared {a['declared']}, {a['flag']})" if a.get("flag") else ""))'''),
]

NOTEBOOKS["05_evaluation_metrics.ipynb"] = [
    md("# 05 · Evaluation metrics\n\nAccuracy, per-class precision / recall, macro-F1 and confusion matrices "
       "(against the Final Gold v3 reference labels); evidence integrity (citation validity, future-data leakage, "
       "fiscal-period mismatches, reference-filing overlap); unsupported-conclusion "
       "rate; latency, tokens and estimated cost — grouped by approach, company, claim category and difficulty. "
       "Missing measurements stay missing (`NaN` with the count measured), never filled in."),
    code(SETUP),
    code('''\
RUN_ID = None
EXPERIMENT_ID = "claimverif-main-v1"''', tags=["parameters"]),
    code('''\
from engine.metrics import evaluate, classification_metrics
from engine.metrics import integrity_metrics, second_look_metrics
from engine.notebook import banner, pick_run, describe_run, load_gold_labels, reference_banner, trace_index, save_table, save_figure
from engine.schema import LABELS
run = pick_run(EXPERIMENT_ID, RUN_ID)
assert run is not None, "no run found -- execute notebook 03 first"
describe_run(run)
reference_banner()
preds, traces = run["predictions"], trace_index(run)
gold = load_gold_labels()
labelled = sum(1 for p in preds if p["claim_id"] in gold)
if not labelled:
    banner("None of this run's claims has a reference label (the reference covers the gold split only), so accuracy / "
           "precision / recall / macro-F1 are not computed. Gold-free measures (integrity, cost, latency) are shown.")
banner("Evidence precision / recall are not computed: the reference evidence quotes are not verbatim-verified "
       "(v3: 71/150 are corroborated table values, not quotes). Filing-level overlap with the reference is reported instead.", "info")'''),
    md("## By approach"),
    code('''\
COLS = ["n_predictions", "n_labelled", "accuracy", "macro_f1", "evidence_precision", "evidence_recall", "n_evidence_scored",
        "decisive", "unsupported_conclusion_rate", "invalid_citations", "avg_latency_ms", "avg_input_tokens",
        "avg_output_tokens", "avg_llm_calls", "avg_cost_usd", "total_cost_usd", "n_cost", "is_mock"]
by_approach = pd.DataFrame(evaluate(preds, gold, traces, ("approach",)))
print("saved", save_table(by_approach, "metrics_by_approach", run))
by_approach[["approach"] + COLS]'''),
    md("### Figure: accuracy and macro-F1 per approach\n\nDots are point estimates; lines are 95% percentile bootstrap "
       "intervals over claims (5,000 resamples, fixed seed). Overlapping intervals do not by themselves mean no "
       "difference -- the paired tests in notebook 06 are the comparison."),
    code('''\
from engine import plots
from engine.stats import bootstrap_ci
plots.style()
RID = run["manifest"]["run_id"]
kind_of = {p["approach"]: p["approach_kind"] for p in preds}
summary = []
for a in sorted(kind_of):
    ps = [p for p in preds if p["approach"] == a and p["claim_id"] in gold]
    if not ps:
        continue
    ci = bootstrap_ci([gold[p["claim_id"]]["label"] for p in ps], [p["predicted_label"] for p in ps])
    summary.append({"approach": a, "kind": kind_of[a], "n": ci["n"],
                    "accuracy": ci["accuracy"]["point"], "acc_lo": ci["accuracy"]["ci_low"], "acc_hi": ci["accuracy"]["ci_high"],
                    "macro_f1": ci["macro_f1"]["point"], "f1_lo": ci["macro_f1"]["ci_low"], "f1_hi": ci["macro_f1"]["ci_high"]})
if summary:
    fig = plots.accuracy_summary(summary, f"Claim verification vs reference labels (n = {summary[0]['n']} claims)")
    print("saved", save_figure(fig, f"05_accuracy_{RID}", run)); plt.show()
    display(pd.DataFrame(summary).round(3))
    save_table(pd.DataFrame(summary), "accuracy_with_ci", run)
else:
    print("skipped: no labelled claims")'''),
    md("## Evidence integrity\n\n- **citation_validity**: cited ids issued in the run, same company, filed by the cutoff, "
       "verbatim quote\n- **future_data_leakage_rate**: runs that used any filing, passage or XBRL fact filed after the "
       "cutoff (must be 0)\n- **incorrect_fiscal_period_rate**: runs with a numeric check whose model-extracted period or "
       "basis does not exist at the cutoff (a proxy; the reference has no period annotation)\n- "
       "**reference_filing_hit_rate**: labelled runs citing at least one SEC filing the reference names (filing level)"),
    code('''\
integ = pd.DataFrame(integrity_metrics(preds, traces, gold))
save_table(integ, "evidence_integrity", run)
integ'''),
    md("## Sensitivity: scoring decisive answers on INSUFFICIENT_EVIDENCE claims\n\n"
       "| scoring | a decisive answer on an INSUFFICIENT_EVIDENCE claim counts as correct when |\n|---|---|\n"
       "| **strict** (primary) | never -- only an exact match with the reference |\n"
       "| **adjudicated** | a person, blind to the approach, judged it ACCEPTABLE case by case |\n"
       "| **lenient** | always (every decisive answer accepted) -- an upper bound |\n\n"
       "Decisions come from `datasets/adjudication/` (`scripts/insufficient_adjudication.py`). Only claims whose "
       "reference is INSUFFICIENT_EVIDENCE can change; all other claims are scored strictly in every variant."),
    code('''\
from engine.reference import alternative_variants, load_alternatives, correct
from engine.stats import compare_correctness
from engine import plots
plots.style()
RID = run["manifest"]["run_id"]
variants = alternative_variants(RID)
if not variants:
    print("no adjudication recorded for this run -- see scripts/insufficient_adjudication.py")
else:
    ids = sorted({p["claim_id"] for p in preds} & set(gold))
    byc = {a: {p["claim_id"]: p for p in preds if p["approach"] == a} for a in sorted({p["approach"] for p in preds})}
    kind_of = {p["approach"]: p["approach_kind"] for p in preds}
    scorings = {"strict": None, **{v: load_alternatives(RID, v) for v in variants}}
    table, forest = [], []
    for name, alts in scorings.items():
        row = {"scoring": name}
        for a, m in byc.items():
            row[a] = sum(correct(m[i], gold, alts) for i in ids) / len(ids)
            if alts:
                row[f"{a} accepted"] = sum(1 for i in ids if alts.get((i, a)) == "ACCEPTABLE")
        table.append(row)
        for c in run["manifest"].get("comparisons") or []:
            if c["a"] in byc and c["b"] in byc:
                r = compare_correctness([correct(byc[c["a"]][i], gold, alts) for i in ids],
                                        [correct(byc[c["b"]][i], gold, alts) for i in ids])
                short = {"conventional_rag": "A1", "financial_verification": "A2", "contradiction_aware": "A3", "self_reflection": "SR"}
                forest.append({"label": f"{short[kind_of[c['a']]]} → {short[kind_of[c['b']]]}  ({name})",
                               "diff": r["accuracy_diff"]["diff_b_minus_a"], "lo": r["accuracy_diff"]["ci_low"],
                               "hi": r["accuracy_diff"]["ci_high"], "p": r["mcnemar"]["p_value_exact"], "_c": c["name"]})
    sens = pd.DataFrame(table)
    save_table(sens, "accuracy_by_scoring", run)
    display(sens.round(3))
    order = [c["name"] for c in run["manifest"].get("comparisons") or []]
    forest.sort(key=lambda r: (order.index(r["_c"]), list(scorings).index(r["label"].rsplit("(", 1)[1][:-1])))
    pd.DataFrame(forest).drop(columns="_c").pipe(lambda d: save_table(d, "paired_differences_by_scoring", run))
    fig = plots.paired_differences(forest, "Paired accuracy differences under three scorings of INSUFFICIENT_EVIDENCE claims")
    print("saved", save_figure(fig, f"05_scoring_sensitivity_{RID}", run)); plt.show()
    for v in variants:
        path = os.path.join("datasets", "adjudication", f"insufficient_alternatives__{RID}__{v}.jsonl")
        rows = [json.loads(line) for line in open(path)]
        print(f"{v}: {sum(r['decision'] == 'ACCEPTABLE' for r in rows)}/{len(rows)} answers accepted; "
              f"source {rows[0].get('source_workbook')}; adjudicator {rows[0].get('adjudicator')}")'''),
    md("## Agentic metrics (second look)"),
    code('''\
slm = pd.DataFrame(second_look_metrics(preds, gold))
save_table(slm, "second_look_metrics", run)
slm'''),
    md("## By company, claim category and difficulty"),
    code('''\
for keys in (("approach", "company"), ("approach", "claim_category"), ("approach", "difficulty")):
    t = pd.DataFrame(evaluate(preds, gold, traces, keys))
    save_table(t, "metrics_by_" + "_".join(keys), run)
    display(t[list(keys) + ["n_predictions", "n_labelled", "accuracy", "macro_f1", "unsupported_conclusion_rate", "avg_cost_usd"]])'''),
    code('''\
cat_rows = [{"approach": r["approach"], "kind": kind_of[r["approach"]], "claim_category": r["claim_category"],
             "accuracy": r["accuracy"], "n": r["n_labelled"]}
            for r in evaluate(preds, gold, traces, ("approach", "claim_category")) if r["n_labelled"]]
if cat_rows:
    fig = plots.category_accuracy(cat_rows, "Accuracy by claim category")
    print("saved", save_figure(fig, f"05_accuracy_by_category_{RID}", run)); plt.show()
else:
    print("skipped: no labelled claims")'''),
    md("## Per-class precision / recall and confusion matrices"),
    code('''\
if labelled:
    cms = []
    for a in sorted(kind_of):
        ps = [p for p in preds if p["approach"] == a and p["claim_id"] in gold]
        m = classification_metrics([gold[p["claim_id"]]["label"] for p in ps], [p["predicted_label"] for p in ps])
        display(pd.DataFrame(m["per_class"]).T.assign(approach=a).round(3))
        cms.append((a, kind_of[a], m["confusion_matrix"]))
    fig = plots.confusion_grid(cms, "Confusion matrices (rows: reference label, columns: prediction)")
    print("saved", save_figure(fig, f"05_confusion_{RID}", run)); plt.show()
else:
    print("skipped: no labelled claims in this run")'''),
    md("## Self-check of the metric code (SYNTHETIC data, not research results)\n\nRecomputes accuracy and macro-F1 by "
       "hand on synthetic labels and asserts the library agrees, so a reader can trust the tables above."),
    code('''\
from engine import synthetic
from engine.datasets import finalized_gold
sc = synthetic.synthetic_claims()
sa, sj = synthetic.synthetic_annotations(sc)
sgold = finalized_gold(sc, sa, sj)
spreds = synthetic.synthetic_predictions(sgold, {"A": 0.6, "B": 0.75})
res = {r["approach"]: r for r in evaluate(spreds, sgold, None, ("approach",))}
for a in ("A", "B"):
    ps = [p for p in spreds if p["approach"] == a]
    hand_acc = sum(p["predicted_label"] == sgold[p["claim_id"]]["label"] for p in ps) / len(ps)
    f1s = []
    for lab in LABELS:
        tp = sum(p["predicted_label"] == lab and sgold[p["claim_id"]]["label"] == lab for p in ps)
        fp = sum(p["predicted_label"] == lab and sgold[p["claim_id"]]["label"] != lab for p in ps)
        fn = sum(p["predicted_label"] != lab and sgold[p["claim_id"]]["label"] == lab for p in ps)
        if tp + fn:
            pr, rc = (tp / (tp + fp) if tp + fp else 0), tp / (tp + fn)
            f1s.append(2 * pr * rc / (pr + rc) if pr + rc else 0)
    assert abs(res[a]["accuracy"] - hand_acc) < 1e-12 and abs(res[a]["macro_f1"] - sum(f1s) / len(f1s)) < 1e-12
    print(f"synthetic {a}: accuracy {hand_acc:.3f}, macro-F1 {sum(f1s)/len(f1s):.3f} -- library matches hand computation")'''),
]

NOTEBOOKS["06_statistical_analysis.ipynb"] = [
    md("# 06 · Statistical analysis\n\nPaired comparisons on the same claim ids:\n\n- **main:** A2 (RAG + numeric "
       "verification) vs A3 (contradiction-aware)\n- **second-look control:** SR (self-reflection) vs A3\n\n"
       "McNemar's test on per-claim correctness and paired bootstrap confidence intervals for the accuracy and "
       "macro-F1 differences, overall and per claim category, then token / latency / cost / tool-call comparisons. "
       "Only claims with a reference label and a prediction from both approaches count."),
    code(SETUP),
    code('''\
RUN_ID = None
EXPERIMENT_ID = "claimverif-main-v1"
N_BOOT = 5000
SEED = 20261102''', tags=["parameters"]),
    code('''\
from engine.stats import compare
from engine.notebook import banner, pick_run, describe_run, load_gold_labels, reference_banner, save_table, save_figure
run = pick_run(EXPERIMENT_ID, RUN_ID)
assert run is not None, "no run found -- execute notebook 03 first"
describe_run(run)
reference_banner()
gold = load_gold_labels()
comparisons = run["manifest"].get("comparisons") or [{"name": "main", "a": "A2_rag_numeric", "b": "A3_contradiction_aware"}]

def report(preds, gold, comparisons, n_boot=N_BOOT, seed=SEED):
    rows = []
    for c in comparisons:
        pa = [p for p in preds if p["approach"] == c["a"]]
        pb = [p for p in preds if p["approach"] == c["b"]]
        r = compare(pa, pb, gold, n_boot=n_boot, seed=seed)
        if not r["n"]:
            rows.append({"comparison": c["name"], "a": c["a"], "b": c["b"], "n": 0}); continue
        m, bs = r["mcnemar"], r["bootstrap"]
        rows.append({"comparison": c["name"], "a": c["a"], "b": c["b"], "n": r["n"],
                     "acc_a": m["accuracy_a"], "acc_b": m["accuracy_b"],
                     "acc_diff_b_minus_a": bs["accuracy"]["diff_b_minus_a"],
                     "acc_ci95": (round(bs["accuracy"]["ci_low"], 3), round(bs["accuracy"]["ci_high"], 3)),
                     "macro_f1_diff": bs["macro_f1"]["diff_b_minus_a"],
                     "macro_f1_ci95": (round(bs["macro_f1"]["ci_low"], 3), round(bs["macro_f1"]["ci_high"], 3)),
                     "b_right_a_wrong": m["b_right_a_wrong"], "a_right_b_wrong": m["a_right_b_wrong"],
                     "mcnemar_p_exact": m["p_value_exact"], "odds_ratio": m["odds_ratio_b_over_a"],
                     "dropped_unpaired": r["pairing"]["dropped_unpaired"], "note": m["note"]})
    return pd.DataFrame(rows)'''),
    md("## Results on this run"),
    code('''\
labelled = {p["claim_id"] for p in run["predictions"]} & set(gold)
if not labelled:
    banner("No reference labels for this run's claims, so no test is computed on it. "
           "A significance test on unlabelled or mock data would be meaningless.")
else:
    res = report(run["predictions"], gold, comparisons)
    print("saved", save_table(res, "statistical_tests", run))
    if res.n.max() < 30:
        banner(f"Only {res.n.max()} paired claims: confidence intervals will be wide and the test has little power.")
    display(res)'''),
    md("## Per claim category\n\nThe same paired comparisons within each category (n ≈ 50 each on the full gold set; "
       "exploratory -- not corrected for multiple comparisons)."),
    code('''\
cats = sorted({p.get("claim_category") for p in run["predictions"] if p.get("claim_category")})
if labelled:
    per_cat = pd.concat([report([p for p in run["predictions"] if p.get("claim_category") == c], gold, comparisons).assign(category=c)
                         for c in cats], ignore_index=True)
    save_table(per_cat, "statistical_tests_by_category", run)
    display(per_cat[["category", "comparison", "n", "acc_a", "acc_b", "acc_diff_b_minus_a", "acc_ci95", "mcnemar_p_exact"]])
else:
    print("skipped: no labelled claims")'''),
    md("### Figure: paired accuracy differences\n\nEach row is one planned comparison (second approach minus first) on "
       "the same claims, overall and -- exploratory -- within each category. Coloured rows are those whose 95% interval "
       "excludes zero."),
    code('''\
from engine import plots
plots.style()
if labelled:
    short = {"conventional_rag": "A1", "financial_verification": "A2", "contradiction_aware": "A3", "self_reflection": "SR"}
    kind_of = {p["approach"]: p["approach_kind"] for p in run["predictions"]}
    forest = []
    order = {"all claims": 0, "numerical": 1, "interpretive": 2, "ambiguous": 3}
    both = pd.concat([res.assign(category="all claims"), per_cat])
    both = both.assign(_c=both.comparison.map({c["name"]: i for i, c in enumerate(comparisons)}), _k=both.category.map(order))
    for _, r in both.sort_values(["_c", "_k"]).iterrows():
        if not r.n:
            continue
        forest.append({"label": f"{short[kind_of[r.a]]} → {short[kind_of[r.b]]}  ({r.category}, n={r.n})",
                       "diff": r.acc_diff_b_minus_a, "lo": r.acc_ci95[0], "hi": r.acc_ci95[1], "p": r.mcnemar_p_exact})
    fig = plots.paired_differences(forest, "Paired accuracy differences")
    print("saved", save_figure(fig, f"06_paired_differences_{run['manifest']['run_id']}", run)); plt.show()
else:
    print("skipped: no labelled claims")'''),
    md("## Efficiency and reasoning budget\n\nA3 and SR make three model calls per claim, A1 / A2 one; A3 also issues up to "
       "three counter-evidence queries. An accuracy gain must be read against this extra budget (SR is the equal-call "
       "control)."),
    code('''\
from engine.metrics import efficiency
from engine import plots
plots.style()
eff = []
for a in sorted({p["approach"] for p in run["predictions"]}):
    ps = [p for p in run["predictions"] if p["approach"] == a]
    e = efficiency(ps)
    eff.append({"approach": a, "claims": len(ps), "avg_llm_calls": e["avg_llm_calls"],
                "avg_retrieval_queries": sum(p.get("retrieval_queries") or 0 for p in ps) / len(ps),
                "avg_numeric_checks": sum(p.get("numeric_checks") or 0 for p in ps) / len(ps),
                "avg_input_tokens": e["avg_input_tokens"], "avg_output_tokens": e["avg_output_tokens"],
                "avg_latency_ms": e["avg_latency_ms"], "total_cost_usd": e["total_cost_usd"]})
eff = pd.DataFrame(eff)
save_table(eff, "efficiency", run)
display(eff)
kind_of = {p["approach"]: p["approach_kind"] for p in run["predictions"]}
fig = plots.efficiency([{**r, "kind": kind_of[r["approach"]], "avg_cost_usd": r["total_cost_usd"] / r["claims"]}
                        for r in eff.to_dict("records")], "Reasoning budget and cost per claim")
print("saved", save_figure(fig, f"06_efficiency_{run['manifest']['run_id']}", run)); plt.show()
if run["manifest"].get("is_mock"):
    banner("Mock run: token counts and costs are the stand-in's fixed values, not measurements.")'''),
    md("## Demonstration on SYNTHETIC data (not research results)\n\nShows the full report on made-up labels "
       "(A3 drawn with 70% accuracy, A2 60%, SR 62%) so the output format and the code path are visible before "
       "real gold labels exist."),
    code('''\
from engine import synthetic
from engine.datasets import finalized_gold
banner("SYNTHETIC demonstration -- these numbers say nothing about any approach.", "info")
sc = synthetic.synthetic_claims(120)
sa, sj = synthetic.synthetic_annotations(sc)
sgold = finalized_gold(sc, sa, sj)
spreds = synthetic.synthetic_predictions(sgold, {"A2_rag_numeric": 0.60, "A3_contradiction_aware": 0.70, "SR_self_reflection": 0.62})
report(spreds, sgold, [{"name": "main", "a": "A2_rag_numeric", "b": "A3_contradiction_aware"},
                       {"name": "second_look_control", "a": "SR_self_reflection", "b": "A3_contradiction_aware"}], n_boot=2000)'''),
    md("## Assumptions and limitations\n\n"
       "- **Pairing.** Both approaches are scored on the same claim ids; McNemar uses only discordant pairs "
       "(claims one approach got right and the other wrong). With fewer than ~25 discordant pairs the exact "
       "binomial p-value is the one to read.\n"
       "- **Independence.** Claims are treated as independent draws. Several claims about the same company and "
       "period share filings, so the effective sample size is smaller than the claim count; report per-company "
       "results (notebook 05) alongside.\n"
       "- **Bootstrap.** Percentile intervals from resampling claims with replacement (fixed seed); they describe "
       "uncertainty over this claim population, not over other companies, periods or models.\n"
       "- **Multiple comparisons.** Two planned comparisons (main, second-look control) are pre-registered in the "
       "config; any further comparison should be reported as exploratory or corrected (e.g. Holm).\n"
       "- **Effect size.** Report the accuracy / macro-F1 difference with its interval and the discordant-pair "
       "odds ratio, not only the p-value.\n"
       "- **Scope.** A significant difference means the contradiction-aware pipeline did better on this claim set, "
       "with this model snapshot, corpus and prompt version. It is not evidence that the method is better in general.\n"
       "- **Model determinism.** Temperature 0 reduces but does not remove run-to-run variation; cached responses make "
       "a run reproducible, and repeated live runs are needed to estimate that variation."),
]


NOTEBOOKS["08_error_analysis.ipynb"] = [
    md("# 08 · Post-experiment error analysis\n\n"
       "Why the contradiction-aware pipeline (A3) did not outperform A2. Read-only over the frozen run: no prompt is "
       "changed, no model is called, nothing in the run directory or the reference is modified. Every number below is "
       "recomputed from the run's predictions and traces.\n\n"
       "**Observed vs interpreted.** Tables and counts are observations. The *mechanism* column of the discordant-case "
       "review (section 6) is an analyst judgement made from the traces by an AI assistant and is **not researcher-"
       "verified**; the research findings report (`docs/error_analysis_report.md`) separates the two explicitly."),
    code(SETUP),
    code('''\
RUN_ID = None
EXPERIMENT_ID = "claimverif-main-v1"
A, B = "A2_rag_numeric", "A3_contradiction_aware"   # main comparison (B = second look on top of A)''', tags=["parameters"]),
    code('''\
import os
from engine import error_analysis as ea, plots
from engine.freeze import build_freeze, diff_freeze, freeze_path
from engine.metrics import classification_metrics
from engine.notebook import banner, pick_run, describe_run, load_gold_labels, reference_banner, trace_index, save_table, save_figure
from engine.reference import alternative_variants, load_alternatives
from engine.runner import RUNS_DIR
run = pick_run(EXPERIMENT_ID, RUN_ID)
assert run is not None, "no run found -- execute notebook 03 first"
describe_run(run)
reference_banner()
RID = run["manifest"]["run_id"]
preds, traces, gold = run["predictions"], trace_index(run), load_gold_labels()
kind_of = {p["approach"]: p["approach_kind"] for p in preds}
LABELLED = bool({p["claim_id"] for p in preds} & set(gold)) and {A, B} <= set(kind_of)
if not LABELLED:
    banner("This run has no reference-labelled claims for both compared approaches (the reference covers the gold "
           "split only); the label-based sections are skipped.")
plots.style()'''),
    md("## 1. Freeze check: the original results are unchanged\n\n"
       "`scripts/freeze_experiment.py` stored checksums of the run directories, configuration, prompts, model "
       "settings, datasets, reference, adjudication files, cached model responses and result files, plus the scores "
       "recomputed from the frozen predictions. Here everything is recomputed and compared."),
    code('''\
FREEZE = freeze_path(RID)
frozen = json.load(open(FREEZE)) if os.path.exists(FREEZE) else None
SOURCE_RUNS = list(frozen["runs"])[1:] if frozen else []
if frozen is None:
    banner(f"No freeze record for {RID}: run scripts/freeze_experiment.py --run {RID} before reporting.", "danger")
else:
    now = build_freeze(RID, SOURCE_RUNS)
    d = diff_freeze(frozen, now)
    print("frozen at", frozen["frozen_at"], "| git", frozen["git"]["commit"][:10], "dirty" if frozen["git"]["dirty"] else "clean")
    print("changed:", d["changed"] or "none", "| removed:", d["removed"] or "none", "| added since freeze:", len(d["added"]))
    assert not d["changed"] and not d["removed"], "frozen inputs or results changed -- stop and investigate"
    print("model:", frozen["model"]["model"], "temperature", frozen["model"]["temperature"],
          "| prompts", frozen["versions"]["prompt_version"], "| prompt drift:", frozen["prompts"]["drift"] or "none",
          "| cached responses:", frozen["llm_cache"]["entries"], "missing", len(frozen["llm_cache"]["missing"]))
    display(pd.DataFrame(frozen["scores"]["accuracy"]).round(4))'''),
    md("## 2. Sensitivity scorings: right adjudication file, right provenance\n\n"
       "Each recorded variant must name its source workbook, and re-reading that workbook must give the same "
       "decisions. Strict scoring uses no adjudication file."),
    code('''\
adj_dir = os.path.join("datasets", "adjudication")
prov = []
for v in alternative_variants(RID):
    path = os.path.join(adj_dir, f"insufficient_alternatives__{RID}__{v}.jsonl")
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    for book in sorted({r.get("source_workbook") for r in rows}):
        chk = ea.adjudication_matches_workbook(path, os.path.join(adj_dir, book))
        prov.append({"variant": v, "source_workbook": book, "adjudicator": ",".join(sorted({r.get("adjudicator") for r in rows})),
                     **{k: chk[k] for k in ("cases_recorded", "acceptable_recorded", "acceptable_in_workbook", "consistent")}})
prov = pd.DataFrame(prov)
display(prov if not prov.empty else "no adjudication variants recorded for this run")
if not prov.empty:
    assert prov.consistent.all(), "a recorded variant disagrees with its source workbook"
DEPRECATED = os.path.join("results", "DEPRECATED.json")
dep = [d for d in (json.load(open(DEPRECATED))["artifacts"] if os.path.exists(DEPRECATED) else []) if d["run_id"] == RID]
for d in dep:
    banner(f"{d['path']} is {d['status']}: {d['problem']} Use {', '.join(os.path.basename(x) for x in d['superseded_by'])}. "
           f"{d['action']}", "danger")
if dep:
    display(pd.DataFrame(dep)[["path", "status", "superseded_by"]])
current = os.path.join("results", "metrics", f"{RID}__accuracy_by_scoring.csv")
if os.path.exists(current) and frozen:
    t = pd.read_csv(current).set_index("scoring")
    s = t[[c for c in t.columns if not c.endswith("accepted")]].round(6).T.to_dict()
    assert s == frozen["scores"]["accuracy"], "accuracy_by_scoring.csv disagrees with the scores recomputed at freeze time"
    print("accuracy_by_scoring.csv matches the frozen strict / adjudicated / lenient scores")'''),
    md("## 3. A2 vs A3, claim by claim (strict scoring)\n\n"
       "A3 starts from A2's final verdict (same initial request, same numeric verification), so every A2/A3 "
       "disagreement is a verdict the A3 second look changed."),
    code('''\
if LABELLED:
    pair = pd.DataFrame(ea.paired_outcomes(preds, gold, A, B))
    same_start = sum(1 for p in preds if p["approach"] == B and p.get("initial_label") ==
                     next((q["predicted_label"] for q in preds if q["approach"] == A and q["claim_id"] == p["claim_id"]), None))
    print(f"A3 initial verdict == A2 final verdict on {same_start}/{len(pair)} claims")
    q = pair.quadrant.value_counts().reindex(ea.QUADRANTS, fill_value=0)
    display(pd.crosstab(pair.correct_a.map({True: f"{A[:2]} correct", False: f"{A[:2]} wrong"}),
                        pair.correct_b.map({True: f"{B[:2]} correct", False: f"{B[:2]} wrong"}), margins=True))
    by_cat = pair.pivot_table(index="category", columns="quadrant", values="claim_id", aggfunc="count", fill_value=0) \\
        .reindex(columns=list(ea.QUADRANTS), fill_value=0).reindex(list(plots.CATEGORIES))
    display(by_cat)
    save_table(pair, "ea_a2_a3_paired_claims", run)
    rows = [{"group": "All claims", **q.to_dict()}] + [{"group": c.capitalize(), **by_cat.loc[c].to_dict()} for c in by_cat.index]
    fig = plots.paired_quadrants(rows, (A, kind_of[A]), (B, kind_of[B]), "A2 vs A3 on the same claims (strict scoring)")
    print("saved", save_figure(fig, f"08_paired_quadrants_{RID}", run)); plt.show()'''),
    md("## 4. A3 initial vs final verdict\n\nTransitions against the reference, and which way the label moved."),
    code('''\
if LABELLED:
    sl = pd.DataFrame(ea.second_look_rows(preds, gold, kind_of[B]))
    display(sl.transition.value_counts().rename("claims").to_frame())
    changed = sl[sl["shift"] != "unchanged"]
    print(f"changed {len(changed)}/{len(sl)}; reconciliation did not complete (NO_FINAL_VERDICT) on "
          f"{int((~sl.completed).sum())}; guard reverted {int(sl.guard_reverted.notna().sum())}")
    display(pd.crosstab(changed.path, changed.transition, margins=True))
    display(pd.crosstab([changed["shift"], changed.gold], changed.final))
    display(pd.crosstab(sl.category, sl.transition, margins=True))
    save_table(sl, "ea_a3_second_look", run)
    paths = []
    for path, d in changed.groupby("path"):
        paths.append({"name": f"{path}  (n={len(d)})", "helped": int((d.transition == "incorrect_to_correct").sum()),
                      "harmed": int((d.transition == "correct_to_incorrect").sum())})
    paths.sort(key=lambda r: r["helped"] - r["harmed"])
    fig = plots.change_balance(paths, "A3 verdict changes by direction (I = INSUFFICIENT, S = SUPPORTED, C = CONTRADICTED)",
                               "Claims (changes that stayed wrong are not shown)")
    print("saved", save_figure(fig, f"08_change_direction_{RID}", run)); plt.show()'''),
    md("## 5. Errors by type, approach and category\n\n"
       "*Overconfident*: a decisive label where the reference is INSUFFICIENT_EVIDENCE. *Over-abstention*: "
       "INSUFFICIENT_EVIDENCE where the reference is decisive. *Polarity*: SUPPORTED ↔ CONTRADICTED."),
    code('''\
if LABELLED:
    er = pd.DataFrame(ea.error_rows(preds, gold))
    et = pd.crosstab(er.approach, er.error_type).reindex(columns=list(ea.ERROR_TYPES), fill_value=0)
    display(et)
    display(pd.crosstab([er.category, er.approach], er.error_type).reindex(columns=list(ea.ERROR_TYPES), fill_value=0))
    save_table(et.reset_index(), "ea_error_types", run)
    acc_cat = er.assign(ok=er.error_type == "correct").pivot_table(index="category", columns="approach", values="ok", aggfunc="mean")
    display(acc_cat.reindex(list(plots.CATEGORIES)).round(3))
    fig = plots.error_types([{"approach": a, "kind": kind_of[a], **et.loc[a].to_dict()} for a in et.index],
                            "Final labels against the reference, by error type")
    print("saved", save_figure(fig, f"08_error_types_{RID}", run)); plt.show()
    cms = []
    for a in sorted(kind_of):
        ps = [p for p in preds if p["approach"] == a and p["claim_id"] in gold]
        cms.append((a, kind_of[a], classification_metrics([gold[p["claim_id"]]["label"] for p in ps],
                                                          [p["predicted_label"] for p in ps])["confusion_matrix"]))
    fig = plots.confusion_grid(cms, "Confusion matrices (rows: reference, columns: prediction)")
    print("saved", save_figure(fig, f"08_confusion_{RID}", run)); plt.show()'''),
    md("## 6. Contradiction investigation: was genuine counter-evidence retrieved and read correctly?\n\n"
       "Automatic part (every A3 claim): what the investigation retrieved, how many challenges it judged supported "
       "with a valid citation, and whether changed verdicts rest on the counter-evidence. Manual part (the 23 A2/A3 "
       "discordant claims): `datasets/error_analysis/discordant_case_review__<run>.csv`, an AI-analyst reading of each "
       "trace (genuine counter-evidence? correctly interpreted? do the final citations entail the verdict?) awaiting "
       "researcher confirmation."),
    code('''\
aud = pd.DataFrame([ea.counter_evidence_audit(p, traces.get((p["approach"], p["claim_id"])))
                    for p in preds if p["approach"] == B])
if not aud.empty:
    assess = pd.Series([x.get("assessment") for p in preds if p["approach"] == B
                        for x in ((p.get("contradiction") or {}).get("assessments") or []) if isinstance(x, dict)]).value_counts()
    display(assess.rename("hypotheses").to_frame())
    s = {"claims": len(aud), "completed": int(aud.completed.sum()), "mean_counter_passages": aud.counter_passages.mean(),
         "claims_with_new_filings": int((aud.new_filings > 0).sum()),
         "claims_with_supported_challenge": int((aud.challenges_supported > 0).sum()),
         "supported_challenges_with_valid_citation": f"{int(aud.supported_with_valid_citation.sum())}/{int(aud.challenges_supported.sum())}",
         "changed": int(aud.changed.sum()), "changed_citing_counter_evidence": int((aud.changed & aud.final_cites_counter_evidence).sum()),
         "changed_without_supported_challenge": int(aud.changed_without_supported_challenge.sum()),
         "guard_reverted": int(aud.guard_reverted.notna().sum())}
    display(pd.Series(s, name="A3").to_frame())
    save_table(aud, "ea_counter_evidence_audit", run)
REVIEW = os.path.join("datasets", "error_analysis", f"discordant_case_review__{RID}.csv")
review = pd.read_csv(REVIEW) if os.path.exists(REVIEW) and LABELLED else None
if review is None:
    print("no discordant-case review for this run")
else:
    banner(f"Mechanisms below are an AI-analyst reading of the traces ({review.reviewer.iloc[0]}); "
           f"researcher-confirmed: {int(review.researcher_confirmed.notna().sum())}/{len(review)}.", "info")
    rv = review.merge(pair[["claim_id", "category", "gold", "label_a", "label_b", "quadrant"]], on="claim_id", how="left")
    rv["outcome"] = rv.quadrant.map({"only_a": "harmed", "only_b": "helped"})
    display(pd.crosstab(rv.mechanism, rv.outcome, margins=True))
    display(pd.crosstab(rv.outcome, [rv.counterevidence_genuine]).rename_axis(columns="genuine counter-evidence?"))
    display(pd.crosstab(rv.outcome, [rv.interpretation_correct]).rename_axis(columns="interpreted correctly?"))
    display(pd.crosstab(rv.outcome, [rv.final_citations_entail_verdict]).rename_axis(columns="final citations entail verdict?"))
    mech = [{"name": m.replace("_", " ").lower(), "helped": int((d.outcome == "helped").sum()), "harmed": int((d.outcome == "harmed").sum())}
            for m, d in rv.groupby("mechanism")]
    mech.sort(key=lambda r: (r["helped"] - r["harmed"], r["helped"]))
    fig = plots.change_balance(mech, "Why A3 changed A2's verdict: 23 discordant claims (AI-analyst coding)",
                               "Claims where A2 and A3 disagree")
    print("saved", save_figure(fig, f"08_discordant_mechanisms_{RID}", run)); plt.show()
    save_table(rv, "ea_discordant_review", run)'''),
    md("## 7. Citations: provenance, cutoff, period, and what a valid citation does not show\n\n"
       "Re-checked from the trace's evidence ledger, independently of the pipeline's `valid` flag. The pipeline "
       "checks passage quotes verbatim but **not** the quotes attached to XBRL facts or derived metrics, so those are "
       "checked here by matching the cited figure against the quoted numbers. Period alignment is measured on claims "
       "that state a period end. None of these checks shows that the evidence *entails* the verdict; entailment of "
       "the discordant cases is in section 6 (manual)."),
    code('''\
cit = pd.DataFrame([r for p in preds for r in ea.citation_audit(p, traces.get((p["approach"], p["claim_id"])))])
if not cit.empty:
    cs = pd.DataFrame(ea.citation_summary(cit.to_dict("records")))
    display(cs.round(3))
    save_table(cs, "ea_citation_audit_summary", run)
    save_table(cit, "ea_citation_audit", run)
    print("future-data leakage (cited filing after the claim cutoff):", int(cit.after_cutoff.sum()))
    mism = cit[cit.xbrl_value_in_quote == False]  # noqa: E712
    print("XBRL / derived-metric citations whose quote does not contain the cited figure:")
    display(mism[["approach", "claim_id", "evidence_id", "kind", "period_end"]])
    print("citations whose period differs from the claim's stated period end:")
    display(cit[cit.period_matches_claim == False].groupby(["approach", "claim_id"]).size().rename("citations").to_frame())  # noqa: E712
    decisive_no_valid = [p for p in preds if p["predicted_label"] in ea.DECISIVE and not any(c.get("valid") for c in p.get("citations") or [])]
    print("decisive answers with no valid citation:", pd.Series([p["approach"] for p in decisive_no_valid]).value_counts().to_dict())'''),
    md("## 8. Tool calls, tokens, cost and latency\n\n"
       "Calls, tokens and cost come from the frozen run (identical to the live run's, which it replays). Latency "
       "comes from the live run: an offline replay records 0 ms. A request shared by approaches (A1, A2 and A3 send a "
       "byte-identical initial request) is charged to each, as if run alone."),
    code('''\
live = ea.live_latency_index([run["run_dir"]] + [os.path.join(RUNS_DIR, r) for r in SOURCE_RUNS])
eff = pd.DataFrame(ea.efficiency_rows(preds, traces, live))
lab = {a: [p for p in preds if p["approach"] == a and p["claim_id"] in gold] for a in kind_of}
summ = eff.groupby("approach").agg(claims=("claim_id", "count"), llm_calls=("llm_calls", "mean"), tool_calls=("tool_calls", "mean"),
                                   retrieval_queries=("retrieval_queries", "mean"), numeric_checks=("numeric_checks", "mean"),
                                   input_tokens=("input_tokens", "mean"), output_tokens=("output_tokens", "mean"),
                                   cost_per_claim=("cost_usd", "mean"), total_cost=("cost_usd", "sum"))
lat = eff[eff.latency_complete].groupby("approach").latency_s
summ["latency_mean_s"], summ["latency_median_s"], summ["latency_n"] = lat.mean(), lat.median(), lat.count()
if LABELLED:
    summ["correct"] = [sum(p["predicted_label"] == gold[p["claim_id"]]["label"] for p in lab[a]) for a in summ.index]
    summ["cost_per_correct"] = summ.total_cost / summ.correct
display(summ.round(3).T)
save_table(summ.reset_index(), "ea_efficiency", run)
display(eff.groupby(["approach", "category"])[["llm_calls", "tool_calls", "input_tokens", "cost_usd", "latency_s"]].mean().round(3))
if LABELLED and summ.latency_n.notna().all():
    from engine.stats import bootstrap_ci
    rows = []
    for a in summ.index:
        ci = bootstrap_ci([gold[p["claim_id"]]["label"] for p in lab[a]], [p["predicted_label"] for p in lab[a]])["accuracy"]
        rows.append({"approach": a, "kind": kind_of[a], "accuracy": ci["point"], "acc_lo": ci["ci_low"], "acc_hi": ci["ci_high"],
                     "cost_per_claim": summ.loc[a, "cost_per_claim"], "latency_s": summ.loc[a, "latency_mean_s"]})
    fig = plots.accuracy_vs_cost(rows, "Accuracy against cost and latency per claim")
    print("saved", save_figure(fig, f"08_accuracy_vs_cost_{RID}", run)); plt.show()'''),
    md("## 9. Failure case studies\n\n"
       "Discordant claims from the review, with the reference rationale and the change A3 made. Full traces: "
       "`results/runs/<run>/traces/A3_contradiction_aware/<claim>.json`."),
    code('''\
if review is not None:
    idx = {(p["approach"], p["claim_id"]): p for p in preds}
    cases = []
    for _, r in rv.sort_values(["outcome", "mechanism"]).iterrows():
        p = idx[(B, r.claim_id)]
        cases.append({"claim_id": r.claim_id, "category": r.category, "outcome": r.outcome, "mechanism": r.mechanism,
                      "claim": gold[r.claim_id]["claim"], "reference": gold[r.claim_id]["label"],
                      "a2_final": r.label_a, "a3_final": r.label_b,
                      "reference_rationale": gold[r.claim_id].get("rationale"),
                      "a3_change_reason": (p.get("contradiction") or {}).get("change_reason"), "analyst_note": r.note})
    cases = pd.DataFrame(cases)
    save_table(cases, "ea_case_studies", run)
    for _, c in cases[cases.claim_id.isin(["GOLD-NFLX-09", "GOLD-NVDA-07", "GOLD-TSLA-13", "GOLD-NFLX-11", "GOLD-KO-09", "GOLD-GOOGL-04"])].iterrows():
        print("=" * 100)
        print(f"{c.claim_id} [{c.category}] {c.outcome.upper()} -- {c.mechanism}\\nclaim: {c.claim}\\n"
              f"reference {c.reference} | A2 {c.a2_final} -> A3 {c.a3_final}\\nA3 change reason: {(c.a3_change_reason or '')[:500]}\\n"
              f"analyst: {c.analyst_note}")'''),
]


def main():
    os.makedirs(NB_DIR, exist_ok=True)
    for name, cells in NOTEBOOKS.items():
        nb = nbf.v4.new_notebook()
        nb.cells = cells
        nb.metadata["kernelspec"] = {"display_name": "Python 3 (research)", "language": "python", "name": "python3"}
        nb.metadata["language_info"] = {"name": "python"}
        nbf.write(nb, os.path.join(NB_DIR, name))
        print("wrote", name)


if __name__ == "__main__":
    main()
