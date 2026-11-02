import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest  # noqa: E402

import engine  # noqa: E402,F401  (puts backend/app/core on sys.path)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Research tests are offline: any HTTP request fails the test."""
    import requests

    def refuse(*a, **k):
        raise AssertionError(f"network access attempted in an offline test: {a[:1]}")
    monkeypatch.setattr(requests, "get", refuse)
    monkeypatch.setattr(requests, "post", refuse)
    monkeypatch.setattr(requests.Session, "request", refuse)


@pytest.fixture
def dev_claims():
    from engine.datasets import load_split
    return {c.claim_id: c for c in load_split("development")}


@pytest.fixture
def main_cfg():
    from engine.config import load_config
    return load_config("configs/main_comparison.json")
