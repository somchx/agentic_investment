"""Every notebook executes top to bottom offline (no credentials, no paid
calls). Runs written by notebook 03's mock fallback go to a temp dir."""
import os

import pytest

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NB_DIR = os.path.join(ROOT, "notebooks")
NOTEBOOKS = sorted(n for n in os.listdir(NB_DIR) if n.endswith(".ipynb"))

NO_NETWORK = nbformat.v4.new_code_cell(
    "import requests\n"
    "def _refuse(*a, **k): raise RuntimeError('network access attempted in notebook test')\n"
    "requests.get = requests.post = requests.Session.request = _refuse")


def test_six_notebooks_exist():
    assert NOTEBOOKS == ["01_dataset_exploration.ipynb", "02_gold_dataset_review.ipynb", "03_baseline_comparison.ipynb",
                         "04_contradiction_analysis.ipynb", "05_evaluation_metrics.ipynb", "06_statistical_tests.ipynb"]


def test_notebooks_execute_offline(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setenv("RC_RESEARCH_RUNS_DIR", str(runs))  # inherited by the kernel
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    for name in NOTEBOOKS:
        nb = nbformat.read(os.path.join(NB_DIR, name), as_version=4)
        nb.cells.insert(0, NO_NETWORK)
        nbclient.NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": NB_DIR}}).execute()
        errors = [o for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", []) if o.get("output_type") == "error"]
        assert not errors, f"{name}: {errors}"
    made = os.listdir(runs)
    assert made and all(r.startswith("MOCK-") for r in made)
