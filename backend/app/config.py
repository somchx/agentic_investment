"""Runtime settings, read from the environment (.env in the backend/
directory, or the process environment directly -- same pattern the old
Flask app used for INVESMENT_SECRET_KEY / ANTHROPIC_API_KEY).
"""

import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://invesment:invesment@localhost:5432/invesment",
)

# A fresh random secret each process start is fine for local dev (existing
# sessions/tokens just stop validating on restart) -- set JWT_SECRET_KEY in
# the environment for a stable key across restarts.
import secrets  # noqa: E402

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))  # 7 days

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
