"""SAIA V4 FastAPI Application Entry Point."""

import asyncio
import logging

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pathlib import Path

from .config import settings
from .middleware.audit import AuditMiddleware
from .routers import (
    auth_router,
    logs_router,
    alerts_router,
    rules_router,
    cases_router,
    chat_router,
    dashboard_router,
    reports_router,
)
from .services.websocket import get_connection_manager

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="SAIA V4 - Secure Artificial Intelligence Auditor",
)

# ─── Rate limiting ────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


# ─── Middleware ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)


# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(logs_router)
app.include_router(alerts_router)
app.include_router(rules_router)
app.include_router(cases_router)
app.include_router(chat_router)
app.include_router(dashboard_router)
app.include_router(reports_router)


# ─── WebSocket endpoint ───────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Real-time WebSocket endpoint for alert notifications.

    Clients authenticate by passing their JWT as a query param:
        ws://host/ws?token=<jwt>

    On connection the server registers the user; on disconnect it cleans up.
    Broadcasts: new_alert events from narrative_service / alert_aggregator.
    """
    from .middleware.auth import verify_token

    manager = get_connection_manager()
    token = websocket.query_params.get("token")
    user_id = None

    if token:
        try:
            payload = verify_token(token)
            user_id = payload.user_id
        except Exception:
            await websocket.close(code=4001)
            return
    else:
        await websocket.close(code=4001)
        return

    await manager.connect(websocket, user_id)
    try:
        while True:
            # Keep connection alive; server pushes messages, client just pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(user_id)
    except Exception as e:
        logger.warning(f"WebSocket error for {user_id}: {e}")
        await manager.disconnect(user_id)


# ─── Static files (frontend) ──────────────────────────────────────────────────
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


# ─── Exception handlers ───────────────────────────────────────────────────────
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded"},
    )


# ─── Lifecycle events ─────────────────────────────────────────────────────────
_worker_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup_event() -> None:
    """
    Application startup:
    1. Pre-load rule engine cache from DB
    2. Start LLM queue background worker (every 120 s)
    """
    global _worker_task

    # 1 — Pre-warm rule engine cache (best-effort; DB may not be ready in tests)
    try:
        from .services.rule_engine import RuleEngine
        import asyncpg

        pool = await asyncpg.create_pool(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            min_size=1,
            max_size=5,
        )
        engine = RuleEngine(pool)
        await engine.load_rules()
        await pool.close()
        logger.info("Rule engine cache loaded")
    except Exception as e:
        logger.warning(f"Rule engine cache warm-up skipped: {e}")

    # 2 — Start LLM queue worker as a background task
    try:
        from .workers.llm_queue_worker import run_worker

        _worker_task = asyncio.create_task(run_worker(interval_seconds=120))
        logger.info("LLM queue worker started")
    except Exception as e:
        logger.warning(f"LLM queue worker failed to start: {e}")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cancel background worker on shutdown."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    logger.info("SAIA V4 shut down cleanly")


# ─── Health / root ────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": settings.app_version,
        "app": settings.app_name,
    }


@app.get("/api/v1/health", tags=["Health"])
async def api_health():
    """API health check endpoint (versioned)."""
    return {
        "status": "ok",
        "version": settings.app_version,
        "mock_mode": settings.llm_mock_mode,
    }
