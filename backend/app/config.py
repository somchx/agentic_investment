"""Runtime settings, read from the environment (.env in the backend/
directory, or the process environment directly -- same pattern the old
Flask app used for INVESMENT_SECRET_KEY / ANTHROPIC_API_KEY).
"""

import os

from dotenv import load_dotenv

load_dotenv(os.environ.get("APP_ENV_FILE"))


def sqlalchemy_url(url: str) -> str:
    if url.startswith(("postgres://", "postgresql://")):
        return "postgresql+psycopg2://" + url.split("://", 1)[1]
    return url

DATABASE_URL = sqlalchemy_url(os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://invesment:invesment@localhost:5432/invesment",
))
DATABASE_URL_UNPOOLED = sqlalchemy_url(
    os.environ.get("DATABASE_URL_UNPOOLED") or DATABASE_URL
)

# A random fallback here used to silently generate a fresh secret on every
# process start when JWT_SECRET_KEY wasn't set -- convenient for a quick
# local run, but a real footgun anywhere sessions need to survive a
# restart: every existing token would silently stop validating (everyone
# logged out, no error, no log line explaining why) the moment the process
# restarted -- e.g. after a deploy, a crash, or `docker compose restart`.
# Fail fast and explicitly instead (Code Audit Session 5, item 3): a
# missing secret is a deployment misconfiguration, not something to paper
# over with a value nobody chose or recorded.
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is not set. Set it in the environment (e.g. backend/.env) before "
        "starting the server -- a random per-process fallback would silently invalidate "
        "every existing session on the next restart instead of failing here. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))  # 7 days

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
