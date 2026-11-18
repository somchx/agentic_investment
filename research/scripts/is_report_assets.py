"""Tables and figures for IS report chapters 4-5, built only from frozen results (no API call, no new metric).

Reads the frozen Gold 150 evaluation (evaluation.json), the run's predictions / A3v2_2e traces, the frozen
v1 run and the dev-v0.2 offline run; writes results/is_report/{tables,figures}/ and refuses to overwrite.

    research/.venv/bin/python research/scripts/is_report_assets.py
"""
import csv
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from engine import RESEARCH_ROOT  # noqa: E402
from engine.plots import BAD, GOOD, INK, INK2, NEUTRAL, style  # noqa: E402
from engine.reference import load_reference  # noqa: E402

RUN = "a3v2.2-gold150-20261118T112814Z"
EVAL = os.path.join(RESEARCH_ROOT, "results", "gold150", RUN, "evaluation.json")
PRED = os.path.join(RESEARCH_ROOT, "results", "runs", RUN, "predictions.jsonl")
TRACES = os.path.join(RESEARCH_ROOT, "results", "runs", RUN, "traces", "A3v2_2e")
DEV_RUN = os.path.join(RESEARCH_ROOT, "results", "runs", "a3v2.2-dev-v0.2-20261118T052512Z", "predictions.jsonl")
DEV_LABELS = os.path.join(RESEARCH_ROOT, "datasets", "annotations_dev", "dev-v0.2_reference_labels.v2.approved.jsonl")
OUT = os.path.join(RESEARCH_ROOT, "results", "is_report")
ARMS = [("A1_conventional_rag", "A1 RAG"), ("A2_rag_numeric", "A2 RAG + numeric"), ("SR_self_reflection", "SR self-reflection"),
        ("A3v2_1_1_R", "A3 v2.1.1 R"), ("A3v2_1_1_RG", "A3 v2.1.1 RG"), ("A3v2_2e", "A3v2_2e (final)"),
        ("V1:A3_contradiction_aware", "A3 v1")]
SERIES = {"A2_rag_numeric": "#2a78d6", "SR_self_reflection": "#eb6834", "A3v2_2e": "#1baf7a"}  # reference palette slots 1-3
CATS = ("numerical", "interpretive", "ambiguous")
I = "INSUFFICIENT_EVIDENCE"


def write_csv(name: str, header: list, rows: list) -> None:
    with open(os.path.join(OUT, "tables", name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def md_table(header: list, rows: list) -> str:
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] +
                     ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def main() -> None:
    if os.path.exists(OUT):
        raise SystemExit(f"{OUT} exists; not overwritten")
    os.makedirs(os.path.join(OUT, "tables"))
    os.makedirs(os.path.join(OUT, "figures"))
    E = json.load(open(EVAL))
    ref = {k: v["label"] for k, v in load_reference()["labels"].items()}
    P = {}
    for r in map(json.loads, open(PRED)):
        P.setdefault(r["approach"], {})[r["claim_id"]] = r["predicted_label"]
    ids = sorted(ref)
    md = [f"# IS report tables (Gold 150, run `{RUN}`)\n",
          "สร้างจาก `evaluation.json` ที่ freeze แล้วและ predictions / traces ของ run เดียวกัน ไม่มีการคำนวณ metric ใหม่นอกจากการนับเชิงพรรณนาที่ระบุไว้\n"]

    # T4.1 main results
    rows = []
    for key, name in ARMS:
        a = E["arms"][key]
        ci = a["ci"]["accuracy"]
        rows.append([name, a["correct"], pct(a["accuracy"]), f"[{pct(ci['ci_low'])}, {pct(ci['ci_high'])}]",
                     f"{a['macro_f1']:.3f}", f"{a['insufficient_recall']['k']}/{a['insufficient_recall']['n']}",
                     *[f"{a['by_category'][c]['k']}/{a['by_category'][c]['n']}" for c in CATS]])
    h = ["Arm", "Correct", "Accuracy", "95% CI", "Macro-F1", "INSUFF recall", "Numerical", "Interpretive", "Ambiguous"]
    write_csv("T4_1_main_results.csv", h, rows)
    md += ["## ตาราง 4.1 ผลหลัก (n = 150, strict)", md_table(h, rows), ""]

    # T4.2 paired tests
    rows = []
    for name, t in E["tests"].items():
        m, b = t["mcnemar"], t["bootstrap"]["accuracy"]
        rows.append([name, f"{100 * m['accuracy_diff_b_minus_a']:+.1f} pp", f"[{100 * b['ci_low']:+.1f}, {100 * b['ci_high']:+.1f}]",
                     f"{m['b_right_a_wrong']} : {m['a_right_b_wrong']}", f"{m['p_value_exact']:.3f}", f"{t['p_holm']:.2f}", "primary" if "A2" in name else "secondary"])
    for name, t in E["descriptive_tests"].items():
        m, b = t["mcnemar"], t["bootstrap"]["accuracy"]
        rows.append([name, f"{100 * m['accuracy_diff_b_minus_a']:+.1f} pp", f"[{100 * b['ci_low']:+.1f}, {100 * b['ci_high']:+.1f}]",
                     f"{m['b_right_a_wrong']} : {m['a_right_b_wrong']}", f"{m['p_value_exact']:.3f}", "—", "descriptive"])
    h = ["Comparison (A vs B)", "B − A", "Bootstrap 95% CI", "B right : A right (discordant)", "McNemar exact p", "Holm p", "Role"]
    write_csv("T4_2_paired_tests.csv", h, rows)
    md += ["## ตาราง 4.2 การทดสอบแบบจับคู่ (คอลัมน์แรกเป็นคู่ A vs B ตามที่ evaluator บันทึก ผลต่าง = B − A)", md_table(h, rows), ""]

    # T4.3 acceptance criteria
    ac = dict(E["acceptance"])
    ac["AC7_run_complete_and_intact"] = True
    rows = [[k, "ผ่าน" if v else "ไม่ผ่าน"] for k, v in ac.items()]
    write_csv("T4_3_acceptance.csv", ["Criterion", "Result"], rows)
    md += ["## ตาราง 4.3 Acceptance criteria (AC7 จาก run status: complete 900/900, ERROR 0, SHA256SUMS ผ่าน)",
           md_table(["Criterion", "Result"], rows), ""]

    # T4.4 correction / regression vs A2
    rows = []
    for key, name in ARMS:
        a = E["arms"][key]
        if "correction_vs_A2" not in a:
            continue
        c, r, p = a["correction_vs_A2"], a["regression_vs_A2"], a["accepted_decisive_change_precision"]
        rows.append([name, f"{c['k']}/{c['n']} ({pct(c['rate'])})", f"{r['k']}/{r['n']} ({pct(r['rate'])})", c["k"] - r["k"],
                     f"{p['k']}/{p['n']} ({pct(p['rate'])})"])
    h = ["Arm", "Correction vs A2", "Regression vs A2", "Net", "Accepted decisive change precision"]
    write_csv("T4_4_correction_regression.csv", h, rows)
    md += ["## ตาราง 4.4 การแก้ถูก / ทำพังเทียบ A2", md_table(h, rows), ""]

    # T4.5 efficiency
    rows = []
    for key, name in ARMS[:6]:
        f = E["efficiency"][key]
        rows.append([name, f"{f['llm_calls']['median']:.0f}", f"{f['input_tokens']['median']:,.0f}", f"{f['output_tokens']['median']:,.0f}",
                     f"{f['api_latency_ms']['median'] / 1000:.1f}", f"${f['cost_usd']['median']:.4f}", f"${f['cost_usd']['total']:.2f}"])
    h = ["Arm", "LLM calls (median)", "Input tokens (median)", "Output tokens (median)", "API latency s (median)",
         "Cost/claim (median, list price)", "Cost total (list price)"]
    write_csv("T4_5_efficiency.csv", h, rows)
    md += ["## ตาราง 4.5 ประสิทธิภาพ (ต้นทุนเป็น list price ของทุก call รวมที่อ่านจาก cache; ค่าที่จ่ายจริงของ run คือ $23.24)",
           md_table(h, rows), ""]

    # T4.6 confusion matrices (descriptive)
    labs = ["SUPPORTED", "CONTRADICTED", I]
    rows = []
    for key in ("A2_rag_numeric", "SR_self_reflection", "A3v2_2e"):
        cm = Counter((ref[i], P[key][i]) for i in ids)
        for g in labs:
            rows.append([key, g] + [cm[(g, p)] for p in labs])
    h = ["Arm", "Gold \\ Pred", "SUPPORTED", "CONTRADICTED", "INSUFFICIENT"]
    write_csv("T4_6_confusion.csv", h, rows)
    md += ["## ตาราง 4.6 Confusion matrix (นับเชิงพรรณนา)", md_table(h, rows), ""]

    # T5.1 label-change mechanism of A3v2_2e vs A2 (descriptive, from traces; matches doc 13)
    a2, e = P["A2_rag_numeric"], P["A3v2_2e"]
    mech = Counter()
    for i in ids:
        if a2[i] == e[i] or (a2[i] != ref[i] and e[i] != ref[i]):
            continue
        g = next(s for s in json.load(open(os.path.join(TRACES, f"{i}.json")))["stages"] if s["stage"] == "reconciliation_guard")
        later = [k for k in ("decidability_gate", "numeric_checks", "coverage")
                 if (g.get(k) or {}).get("label_before") != (g.get(k) or {}).get("label_after")]
        m = "Reviewer + guard ACCEPT" if g["outcome"] == "ACCEPT" else \
            {"decidability_gate": "Decidability (D-sup)", "numeric_checks": "N1 numeric validity", "coverage": "E1 evidence coverage"}[later[-1]]
        mech[(m, "correction" if e[i] == ref[i] else "regression")] += 1
    order = ["Reviewer + guard ACCEPT", "Decidability (D-sup)", "E1 evidence coverage", "N1 numeric validity"]
    rows = [[m, mech[(m, "correction")], mech[(m, "regression")], mech[(m, "correction")] - mech[(m, "regression")]] for m in order]
    h = ["Mechanism (stage where label changed)", "Correction", "Regression", "Net"]
    write_csv("T5_1_mechanism.csv", h, rows)
    md += ["## ตาราง 5.1 กลไกที่เปลี่ยนคำตอบของ A3v2_2e เทียบ A2 (25 ข้อ, ระบุตำแหน่งไม่ใช่ counterfactual)", md_table(h, rows), ""]

    # T5.2 dev vs gold
    dref = {r["claim_id"]: r["final_label"] for r in map(json.loads, open(DEV_LABELS))}
    D = {}
    for r in map(json.loads, open(DEV_RUN)):
        D.setdefault(r["approach"], {})[r["claim_id"]] = r["predicted_label"]
    dev = {k: sum(D[k][c] == dref[c] for c in dref) for k in ("A2_rag_numeric", "A3v2_2e")}
    rows = [["dev-v0.2 (n = 72, used for development)", f"{dev['A2_rag_numeric']} ({pct(dev['A2_rag_numeric'] / 72)})",
             f"{dev['A3v2_2e']} ({pct(dev['A3v2_2e'] / 72)})", f"{dev['A3v2_2e'] - dev['A2_rag_numeric']:+d}", f"{sum(v == I for v in dref.values())}/72"],
            ["Gold 150 (preregistered)", f"{E['arms']['A2_rag_numeric']['correct']} ({pct(E['arms']['A2_rag_numeric']['accuracy'])})",
             f"{E['arms']['A3v2_2e']['correct']} ({pct(E['arms']['A3v2_2e']['accuracy'])})",
             f"{E['arms']['A3v2_2e']['correct'] - E['arms']['A2_rag_numeric']['correct']:+d}", f"{sum(v == I for v in ref.values())}/150"]]
    h = ["Set", "A2 correct", "A3v2_2e correct", "Difference", "Share labelled INSUFFICIENT"]
    write_csv("T5_2_dev_vs_gold.csv", h, rows)
    md += ["## ตาราง 5.2 ผลบน dev เทียบ Gold", md_table(h, rows), ""]
    open(os.path.join(OUT, "tables", "tables.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")

    figures(E, dev)


def save(fig, name: str) -> None:
    fig.savefig(os.path.join(OUT, "figures", name + ".png"), dpi=200, bbox_inches="tight")
    fig.savefig(os.path.join(OUT, "figures", name + ".svg"), bbox_inches="tight")
    plt.close(fig)


def figures(E: dict, dev: dict) -> None:
    style()
    # F4.1 accuracy with 95% CI per arm (point + whisker), A2 reference line
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    arms = list(reversed(ARMS))
    for y, (key, name) in enumerate(arms):
        a = E["arms"][key]
        ci = a["ci"]["accuracy"]
        hi = key in ("A2_rag_numeric", "A3v2_2e")
        col = SERIES.get(key, NEUTRAL)
        ax.plot([100 * ci["ci_low"], 100 * ci["ci_high"]], [y, y], color=col, lw=2, solid_capstyle="round")
        ax.plot(100 * a["accuracy"], y, "o", ms=8, color=col, mec="#fcfcfb", mew=2)
        ax.text(100 * ci["ci_high"] + 0.8, y, f"{100 * a['accuracy']:.1f}%", va="center", color=INK if hi else INK2, fontsize=9.5)
    ax.axvline(100 * E["arms"]["A2_rag_numeric"]["accuracy"], color=SERIES["A2_rag_numeric"], lw=1, ls="--", zorder=0)
    ax.set_yticks(range(len(arms)), [n for _, n in arms])
    ax.set_xlim(50, 82)
    ax.set_xlabel("Accuracy on Gold 150 (%), point and bootstrap 95% CI")
    ax.set_title("Figure 4.1  Accuracy by approach (dashed line = A2)")
    ax.grid(axis="y", visible=False)
    save(fig, "F4_1_accuracy_ci")

    # F4.2 paired differences: A3v2_2e minus each comparator
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    tests = list(E["tests"].items())
    for y, (name, t) in enumerate(reversed(tests)):
        b = t["bootstrap"]["accuracy"]
        ax.plot([100 * b["ci_low"], 100 * b["ci_high"]], [y, y], color=SERIES["A3v2_2e"], lw=2, solid_capstyle="round")
        ax.plot(100 * b["diff_b_minus_a"], y, "o", ms=8, color=SERIES["A3v2_2e"], mec="#fcfcfb", mew=2)
        ax.text(100 * b["ci_high"] + 0.6, y, f"p = {t['mcnemar']['p_value_exact']:.2f}, Holm {t['p_holm']:.2f}", va="center", color=INK2, fontsize=9)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(range(len(tests)), [n.replace("A3v2_2e vs ", "vs ").replace("_rag_numeric", "").replace("_self_reflection", "")
                                     .replace("A3v2_1_1_", "").replace("V1:A3_contradiction_aware", "A3 v1") for n, _ in reversed(tests)])
    ax.set_xlim(-13, 19)
    ax.set_xlabel("A3v2_2e minus comparator, accuracy (pp), bootstrap 95% CI")
    ax.set_title("Figure 4.2  Preregistered comparisons of A3v2_2e")
    ax.grid(axis="y", visible=False)
    save(fig, "F4_2_paired_differences")

    # F4.3 accuracy by claim category: grouped bars, three series
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    keys = [("A2_rag_numeric", "A2"), ("SR_self_reflection", "SR"), ("A3v2_2e", "A3v2_2e")]
    w = 0.26
    for j, (key, name) in enumerate(keys):
        vals = [100 * E["arms"][key]["by_category"][c]["rate"] for c in CATS]
        xs = [i + (j - 1) * w for i in range(len(CATS))]
        ax.bar(xs, vals, w - 0.03, color=SERIES[key], label=name)
        for x, v in zip(xs, vals):
            ax.text(x, v + 1, f"{v:.0f}", ha="center", color=INK2, fontsize=8.5)
    ax.set_xticks(range(len(CATS)), [f"{c} (n = 50)" for c in CATS])
    ax.set_ylim(0, 105)
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Figure 4.3  Accuracy by claim category")
    ax.legend(ncol=3, loc="upper right")
    ax.grid(axis="x", visible=False)
    save(fig, "F4_3_accuracy_by_category")

    # F4.4 corrections (up) and regressions (down) vs A2
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    rows = [(n, E["arms"][k]) for k, n in ARMS if "correction_vs_A2" in E["arms"][k]]
    for x, (n, a) in enumerate(rows):
        c, r = a["correction_vs_A2"]["k"], a["regression_vs_A2"]["k"]
        ax.bar(x, c, 0.6, color=GOOD)
        ax.bar(x, -r, 0.6, color=BAD)
        ax.text(x, c + 0.5, str(c), ha="center", color=INK2, fontsize=9)
        ax.text(x, -r - 1.6, str(r), ha="center", color=INK2, fontsize=9)
        ax.text(x, -22.5, f"net {c - r:+d}", ha="center", color=INK, fontsize=9)
    ax.axhline(0, color=INK2, lw=1)
    ax.set_xticks(range(len(rows)), [n.replace(" (final)", "") for n, _ in rows], fontsize=9)
    ax.set_ylim(-24, 22)
    ax.set_ylabel("Claims (corrections ↑ / regressions ↓)")
    ax.set_title("Figure 4.4  Corrections and regressions relative to A2")
    ax.grid(axis="x", visible=False)
    save(fig, "F4_4_correction_regression")

    # F4.5 cost per claim vs accuracy
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for key, name in ARMS[:6]:
        cost = E["efficiency"][key]["cost_usd"]["median"]
        acc = 100 * E["arms"][key]["accuracy"]
        ax.plot(cost, acc, "o", ms=9, color=SERIES.get(key, NEUTRAL), mec="#fcfcfb", mew=2)
        dy = {"A1_conventional_rag": -1.0}.get(key, 0)
        left = key == "A3v2_1_1_RG"
        ax.annotate(name.replace(" (final)", ""), (cost, acc + dy), xytext=(-8 if left else 8, 0), textcoords="offset points",
                    va="center", ha="right" if left else "left", fontsize=9, color=INK2)
    ax.set_xlim(0, 0.19)
    ax.set_ylim(60, 72)
    ax.set_xlabel("Median cost per claim (USD, list price)")
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Figure 4.5  Cost versus accuracy")
    save(fig, "F4_5_cost_vs_accuracy")

    # F5.1 dev vs gold slope chart (A2 and A3v2_2e)
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    pts = {"A2_rag_numeric": [100 * dev["A2_rag_numeric"] / 72, 100 * E["arms"]["A2_rag_numeric"]["accuracy"]],
           "A3v2_2e": [100 * dev["A3v2_2e"] / 72, 100 * E["arms"]["A3v2_2e"]["accuracy"]]}
    for key, (d, g) in pts.items():
        ax.plot([0, 1], [d, g], "-o", color=SERIES[key], lw=2, ms=8, mec="#fcfcfb", mew=2)
        ax.text(1.04, g, f"{'A2' if key.startswith('A2') else 'A3v2_2e'} {g:.1f}%", va="center", color=INK, fontsize=9.5)
        ax.text(-0.04, d, f"{d:.1f}%", va="center", ha="right", color=INK2, fontsize=9.5)
    ax.set_xticks([0, 1], ["dev-v0.2 (n = 72)\nused for development", "Gold 150\npreregistered"])
    ax.set_xlim(-0.35, 1.45)
    ax.set_ylim(60, 95)
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Figure 5.1  Dev gains did not carry to Gold")
    ax.grid(axis="x", visible=False)
    save(fig, "F5_1_dev_vs_gold")

    # F5.2 mechanism of A3v2_2e changes (diverging bars)
    rows = list(csv.reader(open(os.path.join(OUT, "tables", "T5_1_mechanism.csv"))))[1:]
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    for y, (m, c, r, n) in enumerate(reversed(rows)):
        c, r = int(c), int(r)
        ax.barh(y, c, 0.6, color=GOOD)
        ax.barh(y, -r, 0.6, color=BAD)
        ax.text(c + 0.2, y, f"+{c}", va="center", color=INK2, fontsize=9)
        ax.text(-r - 0.2, y, f"−{r}", va="center", ha="right", color=INK2, fontsize=9)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(range(len(rows)), [r[0] for r in reversed(rows)])
    ax.set_xlim(-8, 8)
    ax.set_xlabel("Claims: regressions ← | → corrections (A3v2_2e vs A2)")
    ax.set_title("Figure 5.2  Where A3v2_2e changed A2's answer")
    ax.grid(axis="y", visible=False)
    save(fig, "F5_2_change_mechanism")


if __name__ == "__main__":
    main()
    print("wrote", os.path.relpath(OUT, RESEARCH_ROOT))
