"""Small helpers shared by the analysis notebooks (display, run lookup,
figure saving). Business logic lives in the other engine modules."""

import json
import os

from . import RESEARCH_ROOT
from .datasets import finalized_gold, load_adjudications, load_annotations, load_split
from .runner import RUNS_DIR, list_runs, load_run

FIGURES_DIR = os.path.join(RESEARCH_ROOT, "results", "figures")
METRICS_DIR = os.path.join(RESEARCH_ROOT, "results", "metrics")


def banner(text: str, kind: str = "warning") -> None:
    colors = {"warning": "#b45309", "info": "#1d4ed8", "danger": "#b91c1c"}
    try:
        from IPython.display import HTML, display
        display(HTML(f'<div style="border-left:6px solid {colors.get(kind, "#555")};padding:8px 12px;margin:6px 0;'
                     f'background:rgba(127,127,127,.08)"><b>{kind.upper()}</b>: {text}</div>'))
    except ImportError:
        print(f"[{kind.upper()}] {text}")


def pick_run(experiment_id: str | None = None, run_id: str | None = None, allow_mock: bool = True, runs_dir: str = RUNS_DIR) -> dict | None:
    """The requested run, else the newest complete real run, else (if
    allowed) the newest mock run. Returns None when there is nothing."""
    if run_id:
        return load_run(run_id, runs_dir)
    runs = [r for r in list_runs(runs_dir) if experiment_id is None or r["experiment_id"] == experiment_id]
    real = [r for r in runs if not r["is_mock"] and r["state"] == "complete"]
    mock = [r for r in runs if r["is_mock"]]
    pick = (real or (mock if allow_mock else []))
    return load_run(pick[-1]["run_id"], runs_dir) if pick else None


def describe_run(run: dict) -> None:
    m, s = run["manifest"], run["status"]
    if m.get("is_mock"):
        banner(f"Run {m['run_id']} used the MOCK LLM ({m['llm'].get('mock_version')}). Its labels come from keyword "
               "heuristics and are NOT experimental results.", "danger")
    if s.get("state") != "complete":
        banner(f"Run {m['run_id']} is {s.get('state')}: {s.get('completed')}/{s.get('expected_predictions')} predictions. "
               f"{s.get('note') or ''}")
    print(json.dumps({"run_id": m["run_id"], "experiment": m["experiment_id"], "split": m["dataset"]["split"],
                      "claims": len(m["dataset"]["claim_ids"]), "approaches": m["approaches"], "llm": m["llm"],
                      "prompt_version": m["versions"]["prompt_version"], "git_commit": m["code"]["git"]["commit"],
                      "git_dirty": m["code"]["git"]["dirty"], "state": s.get("state")}, indent=1))


def load_gold_labels() -> dict[str, dict]:
    claims = load_split("development") + load_split("gold")
    return finalized_gold(claims, load_annotations(), load_adjudications())


def trace_index(run: dict) -> dict:
    out = {}
    for p in run["predictions"]:
        path = os.path.join(run["run_dir"], p.get("trace_path", ""))
        if p.get("trace_path") and os.path.exists(path):
            with open(path) as f:
                out[(p["approach"], p["claim_id"])] = json.load(f)
    return out


def save_figure(fig, name: str, run: dict | None = None) -> str:
    os.makedirs(FIGURES_DIR, exist_ok=True)
    prefix = "MOCK-" if run and run["manifest"].get("is_mock") and not name.startswith("MOCK") else ""
    path = os.path.join(FIGURES_DIR, f"{prefix}{name}.png")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    return path


def save_table(df, name: str, run: dict | None = None) -> str:
    os.makedirs(METRICS_DIR, exist_ok=True)
    rid = run["manifest"]["run_id"] if run else "adhoc"
    path = os.path.join(METRICS_DIR, f"{rid}__{name}.csv")
    df.to_csv(path, index=False)
    return path
