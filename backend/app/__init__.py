"""Puts app/core/ (the copied-over, framework-free domain logic: sec_client,
xbrl_extract, reason_engine, tools, agent, personalization, portfolio_report,
and the Postgres-backed db.py) directly on sys.path, so those modules can
keep importing each other with the same flat `from tools import ...` /
`import db` style they already used in src/ -- unmodified, to avoid
re-risking logic that's already validated against real SEC data and real
money.
"""

import os
import sys

_CORE_DIR = os.path.join(os.path.dirname(__file__), "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)
