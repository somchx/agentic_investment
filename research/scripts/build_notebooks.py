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

NOTEBOOKS["01_dataset_exploration.ipynb"] = [
    md("# 01 · Dataset exploration\n\nClaims in `datasets/development_cases.jsonl` (development) and "
       "`datasets/gold_claims.jsonl` (held-out). Labels are **not** stored with claims; they come only from "
       "independent human annotations (notebook 02). This notebook reads files and never writes datasets."),
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
    md("## Label distribution (finalized gold only)"),
    code('''\
gold_labels = load_gold_labels()
if not gold_labels:
    banner("No finalized gold labels yet (needs two agreeing independent human reviewers or an adjudication). "
           "Label distribution is not shown rather than guessed.")
else:
    lab = pd.DataFrame([{"claim_id": k, "label": v["label"], "status": v["status"]} for k, v in gold_labels.items()])
    lab = lab.merge(df[["claim_id", "claim_category", "company"]], on="claim_id", how="left")
    display(pd.crosstab(lab.claim_category, lab.label, margins=True))'''),
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
]

NOTEBOOKS["02_gold_dataset_review.ipynb"] = [
    md("# 02 · Gold dataset review\n\nReviewer annotations (`datasets/annotations/<reviewer>.jsonl`), disagreements, "
       "missing evidence references, adjudication progress and finalized gold cases.\n\n**Read-only:** this notebook "
       "never writes labels. Adjudications are recorded with `engine.datasets.append_adjudication`, which refuses to "
       "overwrite an existing decision. The last cell proves no dataset file changed."),
    code(SETUP),
    code('''\
import glob
from engine.datasets import (DATASET_DIR, file_sha256, load_split, load_annotations, load_adjudications,
                             gold_status, finalized_gold, cohen_kappa, FINAL_STATUSES)
from engine.notebook import banner
from engine import synthetic
before = {p: file_sha256(p) for p in glob.glob(os.path.join(DATASET_DIR, "**", "*.jsonl"), recursive=True)}
claims = load_split("development") + load_split("gold")
annotations, adjudications = load_annotations(), load_adjudications()
USE_SYNTHETIC = not annotations
if USE_SYNTHETIC:
    banner("No real annotations exist yet. The tables below run on SYNTHETIC claims and reviewers (ids SYN-*) "
           "only to show the review workflow works. They are not gold labels.")
    claims = synthetic.synthetic_claims()
    annotations, adjudications = synthetic.synthetic_annotations(claims)
print(len(claims), "claims |", len(annotations), "annotations |", len(adjudications), "adjudications")'''),
    md("## Reviewer annotations"),
    code('''\
ann = pd.DataFrame([{**asdict(a), "n_supporting": len(a.supporting_evidence), "n_contradictory": len(a.contradictory_evidence)}
                    for a in annotations])
display(ann[["claim_id", "reviewer_id", "gold_label", "n_supporting", "n_contradictory", "review_notes"]].head(40))
pd.crosstab(ann.reviewer_id, ann.gold_label, margins=True)'''),
    md("## Adjudication progress"),
    code('''\
status = pd.DataFrame(gold_status(claims, annotations, adjudications))
progress = status.adjudication_status.value_counts().rename("claims").to_frame()
progress["share"] = (progress.claims / len(status)).round(2)
display(progress)
fig, ax = plt.subplots(figsize=(6, 2.6))
progress.claims.plot.barh(ax=ax, title="Review state per claim"); ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()'''),
    md("## Reviewer disagreements"),
    code('''\
dis = status[status.adjudication_status.isin(["DISAGREED"]) |
             ((status.adjudication_status == "ADJUDICATED") & status.reviewer_labels.apply(lambda d: len(set(d.values())) > 1))]
dis[["claim_id", "claim_category", "reviewer_labels", "adjudication_status", "final_label"]]'''),
    md("## Inter-annotator agreement (Cohen's κ per reviewer pair)"),
    code('''\
from itertools import combinations
by = {}
for a in annotations:
    by.setdefault(a.reviewer_id, {})[a.claim_id] = a.gold_label
rows = []
for r1, r2 in combinations(sorted(by), 2):
    shared = sorted(set(by[r1]) & set(by[r2]))
    pairs = [(by[r1][c], by[r2][c]) for c in shared]
    rows.append({"pair": f"{r1} vs {r2}", "shared_claims": len(shared), "raw_agreement": (sum(a == b for a, b in pairs) / len(pairs)) if pairs else None,
                 "cohen_kappa": cohen_kappa(pairs)})
pd.DataFrame(rows)'''),
    md("## Missing evidence references\n\nA SUPPORTED / CONTRADICTED annotation must point at the evidence "
       "(filing accession + verbatim quote, or XBRL concept + period)."),
    code('''\
miss = status[status.reviewers_missing_evidence.apply(len) > 0][["claim_id", "reviewer_labels", "reviewers_missing_evidence"]]
print(len(miss), "claim(s) with an annotation lacking evidence references")
miss'''),
    md("## Finalized gold cases"),
    code('''\
final = finalized_gold(claims, annotations, adjudications)
fin = pd.DataFrame([{"claim_id": k, "label": v["label"], "status": v["status"],
                     "supporting_refs": len(v["supporting_evidence"]), "contradictory_refs": len(v["contradictory_evidence"])}
                    for k, v in final.items()])
print(f"{len(fin)} finalized of {len(status)} claims ({', '.join(FINAL_STATUSES)})")
fin'''),
    code('''\
after = {p: file_sha256(p) for p in glob.glob(os.path.join(DATASET_DIR, "**", "*.jsonl"), recursive=True)}
assert after == before, "a dataset file changed while this notebook ran"
print("OK: no dataset file was modified by this notebook")'''),
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
       "evidence. Correctness of changes is shown only for claims with finalized gold labels."),
    code(SETUP),
    code('''\
RUN_ID = None
EXPERIMENT_ID = "claimverif-main-v1"''', tags=["parameters"]),
    code('''\
from engine.notebook import banner, pick_run, describe_run, load_gold_labels, trace_index, save_figure
run = pick_run(EXPERIMENT_ID, RUN_ID)
assert run is not None, "no run found -- execute notebook 03 first"
describe_run(run)
gold = load_gold_labels()
if not gold:
    banner("No finalized gold labels: the help / harm / false-contradiction columns cannot be computed yet and are left empty.")
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
    md("## Did changes help or harm? (finalized gold only)"),
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
       "(finalized gold labels only); evidence precision / recall against annotated evidence; unsupported-conclusion "
       "rate; latency, tokens and estimated cost — grouped by approach, company, claim category and difficulty. "
       "Missing measurements stay missing (`NaN` with the count measured), never filled in."),
    code(SETUP),
    code('''\
RUN_ID = None
EXPERIMENT_ID = "claimverif-main-v1"''', tags=["parameters"]),
    code('''\
from engine.metrics import evaluate, classification_metrics
from engine.notebook import banner, pick_run, describe_run, load_gold_labels, trace_index, save_table, save_figure
from engine.schema import LABELS
run = pick_run(EXPERIMENT_ID, RUN_ID)
assert run is not None, "no run found -- execute notebook 03 first"
describe_run(run)
preds, traces = run["predictions"], trace_index(run)
gold = load_gold_labels()
labelled = sum(1 for p in preds if p["claim_id"] in gold)
if not labelled:
    banner("None of this run's claims has a finalized gold label, so accuracy / precision / recall / macro-F1 / "
           "evidence metrics are not computed. Gold-free measures (unsupported conclusions, cost, latency) are shown.")'''),
    md("## By approach"),
    code('''\
COLS = ["n_predictions", "n_labelled", "accuracy", "macro_f1", "evidence_precision", "evidence_recall", "n_evidence_scored",
        "decisive", "unsupported_conclusion_rate", "invalid_citations", "avg_latency_ms", "avg_input_tokens",
        "avg_output_tokens", "avg_llm_calls", "avg_cost_usd", "total_cost_usd", "n_cost", "is_mock"]
by_approach = pd.DataFrame(evaluate(preds, gold, traces, ("approach",)))
print("saved", save_table(by_approach, "metrics_by_approach", run))
by_approach[["approach"] + COLS]'''),
    md("## By company, claim category and difficulty"),
    code('''\
for keys in (("approach", "company"), ("approach", "claim_category"), ("approach", "difficulty")):
    t = pd.DataFrame(evaluate(preds, gold, traces, keys))
    save_table(t, "metrics_by_" + "_".join(keys), run)
    display(t[list(keys) + ["n_predictions", "n_labelled", "accuracy", "macro_f1", "unsupported_conclusion_rate", "avg_cost_usd"]])'''),
    md("## Per-class precision / recall and confusion matrices"),
    code('''\
if labelled:
    approaches = sorted({p["approach"] for p in preds})
    fig, axes = plt.subplots(1, len(approaches), figsize=(3.6 * len(approaches), 3.2), squeeze=False)
    for ax, a in zip(axes[0], approaches):
        ps = [p for p in preds if p["approach"] == a and p["claim_id"] in gold]
        m = classification_metrics([gold[p["claim_id"]]["label"] for p in ps], [p["predicted_label"] for p in ps])
        cm = pd.DataFrame(m["confusion_matrix"]).T
        display(pd.DataFrame(m["per_class"]).T.assign(approach=a))
        ax.imshow(cm.values, cmap="Blues"); ax.set_title(a, fontsize=9)
        ax.set_xticks(range(cm.shape[1])); ax.set_xticklabels([c[:4] for c in cm.columns], fontsize=7)
        ax.set_yticks(range(cm.shape[0])); ax.set_yticklabels([c[:4] for c in cm.index], fontsize=7)
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, int(cm.values[i, j]), ha="center", va="center", fontsize=8)
    plt.tight_layout(); print("saved", save_figure(fig, f"05_confusion_{run['manifest']['run_id']}", run))
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

NOTEBOOKS["06_statistical_tests.ipynb"] = [
    md("# 06 · Statistical tests\n\nPaired comparisons on the same claim ids:\n\n- **main:** A2 (RAG + numeric "
       "verification) vs A3 (contradiction-aware)\n- **second-look control:** SR (self-reflection) vs A3\n\n"
       "McNemar's test on per-claim correctness and paired bootstrap confidence intervals for the accuracy and "
       "macro-F1 differences. Only claims with a finalized gold label and a prediction from both approaches count."),
    code(SETUP),
    code('''\
RUN_ID = None
EXPERIMENT_ID = "claimverif-main-v1"
N_BOOT = 5000
SEED = 20261102''', tags=["parameters"]),
    code('''\
from engine.stats import compare
from engine.notebook import banner, pick_run, describe_run, load_gold_labels, save_table
run = pick_run(EXPERIMENT_ID, RUN_ID)
assert run is not None, "no run found -- execute notebook 03 first"
describe_run(run)
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
    banner("No finalized gold labels for this run's claims, so no test is computed on it. "
           "A significance test on unlabelled or mock data would be meaningless.")
else:
    res = report(run["predictions"], gold, comparisons)
    print("saved", save_table(res, "statistical_tests", run))
    if res.n.max() < 30:
        banner(f"Only {res.n.max()} paired claims: confidence intervals will be wide and the test has little power.")
    display(res)'''),
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
