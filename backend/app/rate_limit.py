"""Rate limiting for endpoints that spend real LLM API budget.

Keyed per-user (decoded straight from the JWT in the Authorization header)
rather than per-IP, so the limit tracks the actual person hitting the paid
endpoint repeatedly rather than everyone behind the same NAT/office IP.
Falls back to per-IP only for a request with no valid token -- those still
fail auth (401) inside the endpoint itself, this is just a key to bucket
them under before that happens.

This project is a single-investor-per-account prototype, not a public API
that needs to survive abuse -- the limits below exist to stop an accidental
double-click or a runaway frontend retry loop from silently burning API
budget, not to defend against a malicious client.
"""

import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import JWT_ALGORITHM, JWT_SECRET_KEY


def _key_by_user_or_ip(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[len("Bearer ") :]
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return f"user:{payload['sub']}"
        except jwt.PyJWTError:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_key_by_user_or_ip)
