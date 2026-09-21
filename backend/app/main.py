from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import auth, chat, companies, notifications, portfolio, positions, profiles, reasons, reports, screener
from app.config import CORS_ORIGINS
from app.rate_limit import limiter

app = FastAPI(title="Agentic AI for Evidence-Grounded Revalidation of Investment Assumptions")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(reports.router)
app.include_router(reasons.router)
app.include_router(screener.router)
app.include_router(positions.router)
app.include_router(portfolio.router)
app.include_router(profiles.router)
app.include_router(notifications.router)
app.include_router(chat.router)

# Continuous Monitoring: a free, deterministic background pass (never the
# paid LLM) that re-checks every held position on a schedule and creates a
# Notification when a reason's status changed since the last pass. Runs
# in-process (BackgroundScheduler) -- appropriate for this app's single-
# instance local deployment, same reasoning as the JWT secret / SQLite-era
# notes elsewhere in this codebase; a multi-instance deployment would need
# an external scheduler instead so the job doesn't run once per instance.
scheduler = BackgroundScheduler()


@app.on_event("startup")
def on_startup():
    import db
    db.init_db()

    from monitor import run_continuous_monitoring
    scheduler.add_job(run_continuous_monitoring, "interval", minutes=60, id="continuous_monitoring")
    scheduler.start()


@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown(wait=False)


@app.get("/api/health")
def health():
    return {"ok": True}
