"""API route handlers for SAIA V4."""

from .auth import router as auth_router
from .logs import router as logs_router
from .alerts import router as alerts_router
from .rules import router as rules_router
from .cases import router as cases_router
from .chat import router as chat_router
from .dashboard import router as dashboard_router
from .reports import router as reports_router

__all__ = [
    "auth_router",
    "logs_router",
    "alerts_router",
    "rules_router",
    "cases_router",
    "chat_router",
    "dashboard_router",
    "reports_router",
]
