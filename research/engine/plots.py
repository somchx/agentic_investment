"""Report figures for notebooks 04-06 (matplotlib). Each function takes
already-computed numbers and returns a Figure; nothing here computes a
metric. Colours follow the entity (an approach keeps its colour in every
chart); text stays in ink colours; status colours mark helped / harmed."""

import matplotlib.pyplot as plt
import numpy as np

INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUES = ["#f3f7fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#104281"]
GOOD, BAD, NEUTRAL = "#0ca30c", "#d03b3b", "#a8a6a0"
KIND_COLOR = {"conventional_rag": "#2a78d6", "financial_verification": "#eb6834",
              "contradiction_aware": "#1baf7a", "self_reflection": "#52514e"}
KIND_LABEL = {"conventional_rag": "A1 Conventional RAG", "financial_verification": "A2 RAG + numeric verification",
              "contradiction_aware": "A3 Contradiction-aware", "self_reflection": "SR Self-reflection"}
CATEGORIES = ("numerical", "interpretive", "ambiguous")
SHORT = {"SUPPORTED": "SUPPORTED", "CONTRADICTED": "CONTRADICTED", "INSUFFICIENT_EVIDENCE": "INSUFFICIENT", "NO_PREDICTION": "NONE"}


def style() -> None:
    plt.rcParams.update({
        "font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"], "font.size": 10.5,
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlecolor": INK, "axes.titlelocation": "left",
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.8, "axes.axisbelow": True, "legend.frameon": False, "figure.dpi": 110})


def label(kind: str, name: str) -> str:
    return KIND_LABEL.get(kind, name)


def color(kind: str) -> str:
    return KIND_COLOR.get(kind, INK2)


def accuracy_summary(rows: list[dict], title: str):
    """rows: approach, kind, accuracy, acc_lo, acc_hi, macro_f1, f1_lo, f1_hi, n."""
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 0.75 * len(rows) + 1.6), sharey=True)
    y = np.arange(len(rows))[::-1]
    for ax, (m, lo, hi, name) in zip(axes, (("accuracy", "acc_lo", "acc_hi", "Accuracy"),
                                           ("macro_f1", "f1_lo", "f1_hi", "Macro-F1"))):
        for yi, r in zip(y, rows):
            c = color(r["kind"])
            ax.plot([r[lo], r[hi]], [yi, yi], color=c, linewidth=2.2, solid_capstyle="round")
            ax.scatter([r[m]], [yi], s=70, color=c, edgecolor=SURFACE, linewidth=1.5, zorder=3)
            ax.text(r[hi] + 0.015, yi, f"{r[m]:.1%}" if m == "accuracy" else f"{r[m]:.3f}", va="center", fontsize=10, color=INK)
        ax.set_xlim(0.3, 1.0)
        ax.set_title(f"{name} (95% bootstrap CI)")
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(y, [label(r["kind"], r["approach"]) for r in rows])
    axes[0].xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    fig.suptitle(title, x=0.01, ha="left", fontsize=12.5, fontweight="bold", color=INK)
    fig.tight_layout()
    return fig


def category_accuracy(rows: list[dict], title: str):
    """rows: approach, kind, claim_category, accuracy, n."""
    kinds = list(dict.fromkeys((r["approach"], r["kind"]) for r in rows))
    fig, ax = plt.subplots(figsize=(10, 4.2))
    x = np.arange(len(CATEGORIES))
    w = 0.8 / len(kinds)
    for i, (name, kind) in enumerate(kinds):
        vals = [next((r["accuracy"] for r in rows if r["approach"] == name and r["claim_category"] == c), np.nan) for c in CATEGORIES]
        xs = x - 0.4 + w * (i + 0.5)
        ax.bar(xs, vals, width=w - 0.02, color=color(kind), label=label(kind, name), edgecolor=SURFACE, linewidth=2)
        for xi, v in zip(xs, vals):
            if not np.isnan(v):
                ax.text(xi, v + 0.015, f"{v:.0%}", ha="center", va="bottom", fontsize=9, color=INK)
    n = {c: next((r["n"] for r in rows if r["claim_category"] == c), 0) for c in CATEGORIES}
    ax.set_xticks(x, [f"{c.capitalize()}\n(n={n[c]})" for c in CATEGORIES])
    ax.set_ylim(0, 1.08)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_ylabel("Accuracy vs reference")
    ax.grid(axis="x", visible=False)
    ax.set_title(title)
    ax.legend(ncol=len(kinds), loc="upper center", bbox_to_anchor=(0.5, -0.16))
    fig.tight_layout()
    return fig


def confusion_grid(cms: list[tuple[str, str, dict]], title: str):
    """cms: (approach, kind, confusion_matrix as {true: {pred: n}})."""
    fig, axes = plt.subplots(1, len(cms), figsize=(4.1 * len(cms), 3.9), squeeze=False)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue", BLUES)
    vmax = max(max(row.values()) for _, _, cm in cms for row in cm.values())
    for ax, (name, kind, cm) in zip(axes[0], cms):
        rows = list(cm)
        cols = [c for c in next(iter(cm.values())) if c != "NO_PREDICTION" or any(cm[r][c] for r in rows)]
        m = np.array([[cm[r][c] for c in cols] for r in rows])
        ax.imshow(m, cmap=cmap, vmin=0, vmax=vmax)
        for i in range(m.shape[0]):
            for j in range(m.shape[1]):
                ax.text(j, i, int(m[i, j]), ha="center", va="center", fontsize=11,
                        color="white" if m[i, j] > vmax * 0.55 else INK, fontweight="bold" if i == j else "normal")
        ax.set_xticks(range(len(cols)), [SHORT[c] for c in cols], fontsize=8, rotation=20)
        ax.set_yticks(range(len(rows)), [SHORT[r] for r in rows], fontsize=8)
        ax.set_xlabel("Predicted"); ax.grid(False); ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_title(label(kind, name), fontsize=10.5)
    axes[0][0].set_ylabel("Reference")
    fig.suptitle(title, x=0.01, ha="left", fontsize=12.5, fontweight="bold", color=INK)
    fig.tight_layout()
    return fig


def second_look_transitions(rows: list[dict], title: str):
    """rows: claim_category, incorrect_to_correct, correct_to_incorrect, changed_still_wrong, unchanged."""
    fig, ax = plt.subplots(figsize=(9.5, 3.4))
    cats = [r["claim_category"] for r in rows]
    y = np.arange(len(rows))[::-1]
    parts = (("incorrect_to_correct", "Changed: wrong → right", GOOD), ("correct_to_incorrect", "Changed: right → wrong", BAD),
             ("changed_still_wrong", "Changed: still wrong", NEUTRAL))
    left = np.zeros(len(rows))
    for key, name, c in parts:
        vals = np.array([r[key] for r in rows], dtype=float)
        ax.barh(y, vals, left=left, height=0.55, color=c, edgecolor=SURFACE, linewidth=2, label=name)
        for yi, l0, v in zip(y, left, vals):
            if v:
                ax.text(l0 + v / 2, yi, str(int(v)), ha="center", va="center", fontsize=10,
                        color="white" if c != NEUTRAL else INK, fontweight="bold")
        left += vals
    for yi, r, l0 in zip(y, rows, left):
        ax.text(l0 + 0.3, yi, f"of {r['n']} claims", va="center", fontsize=9, color=INK2)
    ax.set_yticks(y, [c.capitalize() for c in cats])
    ax.set_xlabel("Claims whose verdict the contradiction stage changed")
    ax.set_xlim(0, max(left) + 4)
    ax.grid(axis="y", visible=False)
    ax.set_title(title)
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.25))
    fig.tight_layout()
    return fig


def paired_differences(rows: list[dict], title: str):
    """rows: label, diff, lo, hi, p (paired accuracy differences, B − A)."""
    fig, ax = plt.subplots(figsize=(9.5, 0.62 * len(rows) + 1.5))
    y = np.arange(len(rows))[::-1]
    for yi, r in zip(y, rows):
        sig = r["lo"] > 0 or r["hi"] < 0
        c = (GOOD if r["diff"] > 0 else BAD) if sig else INK2
        ax.plot([r["lo"], r["hi"]], [yi, yi], color=c, linewidth=2.2, solid_capstyle="round")
        ax.scatter([r["diff"]], [yi], s=60, color=c, edgecolor=SURFACE, linewidth=1.5, zorder=3)
        ax.text(max(r["hi"], 0) + 0.012, yi, f"{r['diff']:+.1%}  [{r['lo']:+.1%}, {r['hi']:+.1%}]   p = {r['p']:.3f}",
                va="center", fontsize=9.5, color=INK)
    ax.axvline(0, color=INK2, linewidth=1, linestyle=(0, (4, 3)))
    ax.set_yticks(y, [r["label"] for r in rows])
    lo = min(r["lo"] for r in rows)
    ax.set_xlim(min(-0.05, lo - 0.03), max(r["hi"] for r in rows) + 0.3)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:+.0%}"))
    ax.set_xlabel("Accuracy difference (second − first), 95% paired bootstrap CI; McNemar exact p")
    ax.grid(axis="y", visible=False)
    ax.set_title(title)
    fig.tight_layout()
    return fig


def efficiency(rows: list[dict], title: str):
    """rows: approach, kind, avg_input_tokens, avg_output_tokens, avg_llm_calls, avg_cost_usd."""
    metrics = (("avg_llm_calls", "LLM calls / claim", "{:.0f}"), ("avg_input_tokens", "Input tokens / claim", "{:,.0f}"),
               ("avg_output_tokens", "Output tokens / claim", "{:,.0f}"), ("avg_cost_usd", "Est. cost / claim (USD)", "${:.3f}"))
    fig, axes = plt.subplots(1, len(metrics), figsize=(13, 0.62 * len(rows) + 1.6), sharey=True)
    y = np.arange(len(rows))[::-1]
    for ax, (key, name, fmt) in zip(axes, metrics):
        vals = [r[key] or 0 for r in rows]
        ax.barh(y, vals, height=0.55, color=[color(r["kind"]) for r in rows], edgecolor=SURFACE, linewidth=2)
        for yi, v in zip(y, vals):
            ax.text(v, yi, " " + fmt.format(v), va="center", fontsize=9.5, color=INK)
        ax.set_xlim(0, max(vals) * 1.35 if max(vals) else 1)
        ax.set_title(name, fontsize=10.5)
        ax.grid(axis="y", visible=False)
        ax.set_xticks([])
        ax.tick_params(axis="y", length=0)
    axes[0].set_yticks(y, [label(r["kind"], r["approach"]) for r in rows])
    fig.suptitle(title, x=0.01, ha="left", fontsize=12.5, fontweight="bold", color=INK)
    fig.tight_layout()
    return fig


# ------------------------------------------------------- error analysis (08)

# Okabe-Ito hues (colour-blind safe); "correct" recedes so the errors carry the chart
ERROR_COLOR = {"correct": "#e4e3df", "overconfident_supported": "#0072B2", "overconfident_contradicted": "#D55E00",
               "over_abstention": "#56B4E9", "polarity_error": "#CC79A7", "no_prediction": "#52514e"}
ERROR_LABEL = {"correct": "Correct", "overconfident_supported": "SUPPORTED on an INSUFFICIENT claim",
               "overconfident_contradicted": "CONTRADICTED on an INSUFFICIENT claim",
               "over_abstention": "INSUFFICIENT on a decisive claim", "polarity_error": "SUPPORTED ↔ CONTRADICTED",
               "no_prediction": "No prediction"}


def paired_quadrants(rows: list[dict], a: tuple[str, str], b: tuple[str, str], title: str):
    """rows: group, both_correct, only_a, only_b, both_wrong (counts).
    a / b: (approach, kind) -- each 'only' segment wears its approach's colour."""
    parts = (("both_correct", "Both correct", "#cde2fb"), ("only_a", f"Only {label(a[1], a[0]).split(' ')[0]} correct", color(a[1])),
             ("only_b", f"Only {label(b[1], b[0]).split(' ')[0]} correct", color(b[1])), ("both_wrong", "Both wrong", NEUTRAL))
    fig, ax = plt.subplots(figsize=(10, 0.6 * len(rows) + 1.7))
    y = np.arange(len(rows))[::-1]
    left = np.zeros(len(rows))
    for key, name, c in parts:
        vals = np.array([r[key] for r in rows], dtype=float)
        ax.barh(y, vals, left=left, height=0.58, color=c, edgecolor=SURFACE, linewidth=2, label=name)
        for yi, l0, v in zip(y, left, vals):
            if v:
                ax.text(l0 + v / 2, yi, str(int(v)), ha="center", va="center", fontsize=9.5,
                        color="white" if key in ("only_a", "only_b") else INK, fontweight="bold")
        left += vals
    ax.set_yticks(y, [f"{r['group']} (n={int(sum(r[k] for k, _, _ in parts))})" for r in rows])
    ax.set_xlabel("Claims")
    ax.grid(axis="y", visible=False)
    ax.set_title(title)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.2 - 0.02 * len(rows)))
    fig.tight_layout()
    return fig


def error_types(rows: list[dict], title: str):
    """rows: approach, kind, plus a count per engine.error_analysis.ERROR_TYPES key."""
    keys = [k for k in ERROR_COLOR if any(r.get(k) for r in rows)]
    fig, ax = plt.subplots(figsize=(10.5, 0.62 * len(rows) + 1.9))
    y = np.arange(len(rows))[::-1]
    left = np.zeros(len(rows))
    for k in keys:
        vals = np.array([r.get(k, 0) for r in rows], dtype=float)
        ax.barh(y, vals, left=left, height=0.58, color=ERROR_COLOR[k], edgecolor=SURFACE, linewidth=2, label=ERROR_LABEL[k])
        for yi, l0, v in zip(y, left, vals):
            if v:
                ax.text(l0 + v / 2, yi, str(int(v)), ha="center", va="center", fontsize=9.5,
                        color=INK if k in ("correct", "over_abstention") else "white", fontweight="bold")
        left += vals
    ax.set_yticks(y, [label(r["kind"], r["approach"]) for r in rows])
    ax.set_xlabel("Claims (reference: Final Gold v3)")
    ax.grid(axis="y", visible=False)
    ax.set_title(title)
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.3), fontsize=9)
    fig.tight_layout()
    return fig


def change_balance(rows: list[dict], title: str, xlabel: str):
    """rows: name, helped, harmed -- diverging bars (harmed left, helped right)."""
    fig, ax = plt.subplots(figsize=(9.5, 0.45 * len(rows) + 1.6))
    y = np.arange(len(rows))[::-1]
    h = np.array([r["harmed"] for r in rows], dtype=float)
    g = np.array([r["helped"] for r in rows], dtype=float)
    ax.barh(y, -h, height=0.6, color=BAD, edgecolor=SURFACE, linewidth=2, label="Right → wrong")
    ax.barh(y, g, height=0.6, color=GOOD, edgecolor=SURFACE, linewidth=2, label="Wrong → right")
    for yi, hv, gv in zip(y, h, g):
        if hv:
            ax.text(-hv - 0.15, yi, str(int(hv)), ha="right", va="center", fontsize=9.5, color=INK)
        if gv:
            ax.text(gv + 0.15, yi, str(int(gv)), ha="left", va="center", fontsize=9.5, color=INK)
    m = max(h.max(initial=0), g.max(initial=0)) + 1.5
    ax.set_xlim(-m, m)
    ax.axvline(0, color=INK2, linewidth=1)
    ax.set_yticks(y, [r["name"] for r in rows], fontsize=9)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{abs(v):.0f}"))
    ax.set_xlabel(xlabel)
    ax.grid(axis="y", visible=False)
    ax.set_title(title)
    ax.legend(ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.12 - 0.3 / max(len(rows), 1)))
    fig.tight_layout()
    return fig


def accuracy_vs_cost(rows: list[dict], title: str):
    """rows: approach, kind, accuracy, acc_lo, acc_hi, cost_per_claim, latency_s (two panels, one axis each)."""
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8), sharey=True)
    for ax, (key, name, fmt) in zip(axes, (("cost_per_claim", "Est. API cost per claim (USD)", "${:.3f}"),
                                           ("latency_s", "Mean latency per claim (s, live run)", "{:.1f} s"))):
        xs = [r[key] for r in rows]
        span = max(xs) or 1
        for r in rows:
            c = color(r["kind"])
            # approaches with the same cost / latency are dodged sideways so their intervals stay readable
            same = [q for q in rows if abs(q[key] - r[key]) < 0.02 * span]
            x = r[key] + (same.index(r) - (len(same) - 1) / 2) * 0.05 * span
            ax.plot([x, x], [r["acc_lo"], r["acc_hi"]], color=c, linewidth=2, solid_capstyle="round")
            ax.scatter([x], [r["accuracy"]], s=80, color=c, edgecolor=SURFACE, linewidth=1.5, zorder=3)
            ax.annotate(f"{label(r['kind'], r['approach']).split(' ')[0]}  {r['accuracy']:.1%} @ {fmt.format(r[key])}",
                        (x, r["accuracy"]), xytext=(8, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
        ax.set_xlim(0, max(xs) * 1.6)
        ax.set_xlabel(name)
    axes[0].set_ylabel("Accuracy (strict), 95% CI")
    axes[0].yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    fig.suptitle(title, x=0.01, ha="left", fontsize=12.5, fontweight="bold", color=INK)
    fig.tight_layout()
    return fig


# ------------------------------------------------------------ graph diagram

NODE_INFO = {
    "retrieve_evidence": ("tool", "BM25 search over 10-K/10-Q\nfiled on or before the cutoff"),
    "initial_verdict": ("llm", "Claude call: initial verdict\n+ numeric assertions"),
    "numeric_verification": ("tool", "Python: recompute figures\nfrom SEC XBRL, apply rule"),
    "generate_hypotheses": ("llm", "Claude call: what could make\nthe verdict wrong? (≤ 3)"),
    "counter_investigation": ("tool", "search NEW passages per\nhypothesis + compute figures"),
    "reconcile": ("llm", "Claude call: weigh evidence\nvs counter-evidence"),
    "self_critique": ("llm", "Claude call: critique own\nverdict (no new evidence)"),
    "revise": ("llm", "Claude call: revised verdict"),
    "apply_guards": ("guard", "deterministic guards: change only\nwith a valid citation; re-apply rule"),
    "finalize": ("guard", "prediction + trace, tokens,\ncost, latency"),
}
NODE_FILL = {"llm": "#d6e6fa", "tool": "#ecebe7", "guard": "#d9f2e6"}
NODE_EDGE = {"llm": "#2a78d6", "tool": "#8a8882", "guard": "#1baf7a"}


def _main_path(g) -> list[str]:
    succ = {}
    for e in g.edges:
        succ.setdefault(e.source, []).append(e.target)
    path, cur = [], "__start__"
    while cur != "__end__":
        nxt = [t for t in succ.get(cur, []) if t not in ("finalize", "__end__")]
        cur = nxt[0] if nxt else ("finalize" if "finalize" in succ.get(cur, []) else "__end__")
        if cur != "__end__":
            path.append(cur)
    return path


def graph_diagram(graphs: list[tuple[str, str, object]], title: str):
    """graphs: (kind, panel title, compiled LangGraph). Draws each graph's
    real node/edge structure: solid = fixed edge, dashed = conditional edge
    (a failed stage routes straight to `finalize`)."""
    from matplotlib.patches import FancyBboxPatch
    gs = [(k, t, c.get_graph()) for k, t, c in graphs]
    rows = max(len(_main_path(g)) for _, _, g in gs)
    fig, axes = plt.subplots(1, len(gs), figsize=(4.6 * len(gs), 1.25 * rows + 1.6))
    for ax, (kind, panel, g) in zip(np.atleast_1d(axes), gs):
        path = _main_path(g)
        pos = {n: (0.0, -i) for i, n in enumerate(path)}
        cond = {(e.source, e.target): e.conditional for e in g.edges}
        w, h = 1.5, 0.78
        for n, (x, y) in pos.items():
            cat, desc = NODE_INFO.get(n, ("tool", ""))
            ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                        facecolor=NODE_FILL[cat], edgecolor=NODE_EDGE[cat], linewidth=1.6))
            ax.text(x, y + 0.17, n, ha="center", va="center", fontsize=9.5, fontweight="bold", color=INK)
            ax.text(x, y - 0.13, desc, ha="center", va="center", fontsize=7.4, color=INK2, linespacing=1.15)
        for a, b in zip(path, path[1:]):
            dashed = cond.get((a, b), False)
            ax.annotate("", xy=(0, pos[b][1] + h / 2), xytext=(0, pos[a][1] - h / 2),
                        arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.3, linestyle=(0, (3, 2)) if dashed else "-"))
        # failure routes: conditional edges into finalize from nodes other than its predecessor
        fails = [e.source for e in g.edges if e.target == "finalize" and e.conditional and e.source != path[-2]]
        fails += [path[-2]] if cond.get((path[-2], "finalize")) and len(path) > 1 else []
        bus = w / 2 + 0.28
        for n in fails:
            y = pos[n][1]
            ax.plot([w / 2, bus], [y, y], color=BAD, lw=1, linestyle=(0, (3, 2)))
        if fails:
            top = max(pos[n][1] for n in fails)
            fy = pos["finalize"][1]
            ax.plot([bus, bus], [top, fy], color=BAD, lw=1, linestyle=(0, (3, 2)))
            ax.annotate("", xy=(w / 2, fy), xytext=(bus, fy), arrowprops=dict(arrowstyle="-|>", color=BAD, lw=1))
            ax.text(bus + 0.05, (top + fy) / 2, "on failure", rotation=90, va="center", ha="left", fontsize=7.5, color=BAD)
        ax.text(0, 0.75, "START", ha="center", fontsize=8, color=INK2)
        ax.annotate("", xy=(0, h / 2), xytext=(0, 0.68), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.3))
        ax.text(0, pos["finalize"][1] - h / 2 - 0.42, "END", ha="center", fontsize=8, color=INK2)
        ax.annotate("", xy=(0, pos["finalize"][1] - h / 2 - 0.3), xytext=(0, pos["finalize"][1] - h / 2),
                    arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.3))
        calls = sum(1 for n in path if NODE_INFO.get(n, ("",))[0] == "llm")
        ax.set_title(f"{panel}\n{calls} Claude call{'s' if calls > 1 else ''} per claim", fontsize=11, color=color(kind), loc="center")
        ax.set_xlim(-1.1, 1.3)
        ax.set_ylim(-rows + 0.05, 1.0)
        ax.axis("off")
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    handles = [Patch(facecolor=NODE_FILL[k], edgecolor=NODE_EDGE[k], label=l) for k, l in
               (("llm", "LLM node (Claude call)"), ("tool", "deterministic tool node (no LLM)"), ("guard", "guard / output node"))]
    handles += [Line2D([], [], color=INK2, lw=1.3, label="edge"),
                Line2D([], [], color=BAD, lw=1, linestyle=(0, (3, 2)), label="conditional edge to finalize on stage failure")]
    fig.legend(handles=handles, ncol=5, loc="lower center", fontsize=8.5, frameon=False)
    fig.suptitle(title, x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    return fig
