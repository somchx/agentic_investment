#!/bin/sh
# sha256 of the code that decides a Gold 150 prediction (docs/a3v2_2/08_preregistration_gold150.md, section 10):
# research pipeline + evaluator + the backend core modules the research engine imports at load time
# (the live API client and its top-level imports). Run from research/.
set -e
cd "$(dirname "$0")/.."
{ find a3v2 engine experiments graphs -name '*.py' -not -path '*/__pycache__/*'
  printf '%s\n' scripts/a3v2_gold_evaluate.py scripts/run_experiment.py
  for m in agent_config evidence_ledger sec_client xbrl_extract models investigation_engine investigation_tools; do
    echo "../backend/app/core/$m.py"
  done; } | LC_ALL=C sort | xargs shasum -a 256 | tee "${1:-/dev/null}" | shasum -a 256 | cut -d' ' -f1
