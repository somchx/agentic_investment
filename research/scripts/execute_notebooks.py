"""Execute every notebook in research/notebooks in order (offline; the
default RUN_MODE never calls a paid API). Writes executed copies to
results/executed_notebooks/ and leaves the committed notebooks clean.

    research/.venv/bin/python research/scripts/execute_notebooks.py
"""
import os
import sys

import nbformat
from nbclient import NotebookClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NB_DIR = os.path.join(ROOT, "notebooks")
OUT_DIR = os.path.join(ROOT, "results", "executed_notebooks")


def main(names=None) -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    failed = []
    for name in names or sorted(n for n in os.listdir(NB_DIR) if n.endswith(".ipynb")):
        nb = nbformat.read(os.path.join(NB_DIR, name), as_version=4)
        try:
            NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": NB_DIR}}).execute()
            print("ok     ", name)
        except Exception as e:  # noqa: BLE001
            failed.append(name)
            print("FAILED ", name, "\n", str(e)[-3000:])
        nbformat.write(nb, os.path.join(OUT_DIR, name))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
