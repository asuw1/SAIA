"""WebSocket connection manager for SAIA V4."""

import json
import logging
from typing import Dict, Any
from uuid import UUID
from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasting."""

    def __init__(self):
        """Initialize the connection manager."""
        # Store active connections: {user_id: websocket}
        self.active_connections: Dict[UUID, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: UUID) -> None:
        """
        Accept a WebSocket connection and store it.

        Args:
            websocket: The WebSocket connection
            user_id: UUID of the connected user
        """
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket connected for user {user_id}")

    async def disconnect(self, user_id: UUID) -> None:
        """
        Remove a WebSocket connection.

        Args:
            user_id: UUID of the user to disconnect
        """
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].close()
            except Exception as e:
                logger.warning(f"Error closing websocket for {user_id}: {e}")

            del self.active_connections[user_id]
            logger.info(f"WebSocket disconnected for user {user_id}")

    async def send_to_user(self, user_id: UUID, message: dict) -> None:
        """
        Send a message to a specific user.

        Args:
            user_id: UUID of the recipient user
            message: Message dictionary to send
        """
        if user_id in self.active_connections:
            try:
                websocket = self.active_connections[user_id]
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Error sending message to {user_id}: {e}")
                # Remove failed connection
                await self.disconnect(user_id)

    async def broadcast(self, message: dict) -> None:
        """
        Broadcast a message to all connected users.

        Args:
            message: Message dictionary to broadcast
        """
        disconnected_users = []

        for user_id, websocket in list(self.active_connections.items()):
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Error broadcasting to {user_id}: {e}")
                disconnected_users.append(user_id)

        # Clean up failed connections
        for user_id in disconnected_users:
            await self.disconnect(user_id)

    async def broadcast_new_alert(
        self, alert_id: UUID, alert_number: int, severity: str
    ) -> None:
        """
        Broadcast a new alert notification to all connected clients.

        Args:
            alert_id: UUID of the new alert
            alert_number: Alert number for human reference
            severity: Severity level (Critical, High, Medium, Low)
        """
        message = {
            "type": "alert",
            "action": "new_alert",
            "data": {
                "alert_id": str(alert_id),
                "alert_number": alert_number,
                "severity": severity,
            },
        }

        await self.broadcast(message)


# Global connection manager instance
_connection_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """Get or create the global connection manager."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager
