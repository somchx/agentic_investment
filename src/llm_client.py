"""Shared thin HTTP client for the Anthropic Messages API, factored out for
baseline1.py/baseline2.py so they don't duplicate agent.py's request-building
logic. agent.py itself is left untouched (it already works and is tested;
no reason to risk it for a refactor).

Same reasoning as agent.py for calling the API directly with `requests`
instead of the `anthropic` SDK: the SDK's bundled HTTP client hit a
response-decompression bug in this environment.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"


def call_claude(messages: list[dict], tools: list[dict] | None = None, max_tokens: int = 1024) -> dict:
    """One Messages API call. Returns the raw response JSON (content blocks +
    usage). Raises RuntimeError if no API key is configured -- callers
    should not silently skip or fabricate a result when budget isn't set up.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "call_claude requires ANTHROPIC_API_KEY to be set (e.g. in a .env file)."
        )

    payload = {"model": ANTHROPIC_MODEL, "max_tokens": max_tokens, "messages": messages}
    if tools:
        payload["tools"] = tools

    resp = requests.post(
        ANTHROPIC_API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()
