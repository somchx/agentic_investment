"""ReasonCheck research engine: financial claim verification experiments.

This package runs claim-verification experiments without the web app, the
database or the portfolio workflow. It reuses the application's
deterministic core (backend/app/core: SEC client + cache, XBRL extraction,
rule-engine arithmetic, evidence ledger + citation verification, model /
pricing configuration) instead of copying it, so the numbers an experiment
checks are computed by the same code the demo app uses.

backend/app/core modules import each other as top-level modules
(`from sec_client import ...`), so that directory is put on sys.path here,
exactly as the backend's own tests do (PYTHONPATH=app/core).
"""

import os
import sys

RESEARCH_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.abspath(os.path.join(RESEARCH_ROOT, ".."))
BACKEND_CORE = os.path.join(REPO_ROOT, "backend", "app", "core")

if BACKEND_CORE not in sys.path:
    sys.path.insert(0, BACKEND_CORE)

ENGINE_VERSION = "rc-research-1.0"
