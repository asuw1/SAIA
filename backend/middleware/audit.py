"""Audit logging middleware for SAIA V4."""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from uuid import UUID
from datetime import datetime, timezone
import asyncpg

from ..config import settings

logger = logging.getLogger(__name__)

# Paths to skip logging
SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that logs all API requests to the audit_log table."""

    def __init__(self, app):
        """Initialize the audit middleware."""
        super().__init__(app)
        self.pool = None

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Log request to audit_log table and forward to next middleware.

        Captures: user_id, action, resource, details, ip_address
        """
        # Skip logging for certain paths
        if request.url.path in SKIP_PATHS or request.url.path.startswith("/openapi"):
            return await call_next(request)

        # Extract user_id from Authorization header if present
        user_id = None
        auth_header = request.headers.get("Authorization")
        if auth_header:
            try:
                from .auth import verify_token

                parts = auth_header.split()
                if len(parts) == 2 and parts[0].lower() == "bearer":
                    token = parts[1]
                    payload = verify_token(token)
                    user_id = payload.user_id
            except Exception:
                # If token verification fails, continue without user_id
                pass

        # Get client IP address
        ip_address = request.client.host if request.client else "unknown"

        # Build audit log data
        action = f"{request.method} {request.url.path}"
        resource = request.url.path
        details = {}

        # Capture query parameters
        if request.query_params:
            details["query_params"] = dict(request.query_params)

        # Continue with request
        response = await call_next(request)

        # Log to database asynchronously
        try:
            await self._log_audit(
                user_id=user_id,
                action=action,
                resource=resource,
                details=details,
                ip_address=ip_address,
            )
        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")

        return response

    async def _log_audit(
        self,
        user_id: UUID | None,
        action: str,
        resource: str,
        details: dict,
        ip_address: str,
    ) -> None:
        """
        Insert audit log entry into database.

        Uses asyncpg for direct connection pool access.
        """
        try:
            # Get connection from pool
            conn = await asyncpg.connect(
                host=settings.db_host,
                port=settings.db_port,
                user=settings.db_user,
                password=settings.db_password,
                database=settings.db_name,
            )

            try:
                now = datetime.now(timezone.utc)

                query = """
                    INSERT INTO audit_log (user_id, action, resource, details, ip_address, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """

                import json

                details_json = json.dumps(details) if details else None

                await conn.execute(
                    query,
                    user_id,
                    action,
                    resource,
                    details_json,
                    ip_address,
                    now,
                )

            finally:
                await conn.close()

        except Exception as e:
            logger.warning(f"Failed to log audit entry: {e}")
