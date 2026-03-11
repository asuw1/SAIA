from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
import models  # ensures all models are registered before table creation

from api.auth import router as auth_router
from api.ingest import router as ingest_router
from api.alerts import router as alerts_router
from api.rules import router as rules_router
from api.reports import router as reports_router
from api.ai import router as ai_router
from config import settings


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered compliance auditing platform for Saudi regulatory frameworks.",
)

# Allow the frontend (running on localhost during dev) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restrict to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Create tables on startup ───────────────────────────────────────────────────

@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)


# ── Register routers ──────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(ingest_router)
app.include_router(alerts_router)
app.include_router(rules_router)
app.include_router(reports_router)
app.include_router(ai_router)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": settings.APP_VERSION}
