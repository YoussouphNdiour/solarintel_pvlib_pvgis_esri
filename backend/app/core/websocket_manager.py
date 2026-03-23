"""WebSocket connection manager for real-time monitoring data push.

Manages a registry of active WebSocket connections per project_id.
When new monitoring data arrives (via webhook), broadcasts to all
connected clients watching that project.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Thread-safe registry of active WebSocket connections keyed by project_id.

    Attributes:
        _connections: Mapping of project_id string to the set of connected
            ``WebSocket`` instances watching that project.
    """

    def __init__(self) -> None:
        """Initialise with an empty connection registry."""
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, project_id: str, ws: WebSocket) -> None:
        """Accept a new WebSocket connection and register it.

        Args:
            project_id: Project UUID string that the client wants to watch.
            ws: The incoming ``WebSocket`` connection to accept.
        """
        await ws.accept()
        self._connections[project_id].add(ws)
        logger.debug(
            "WS connected: project=%s total=%d",
            project_id,
            self.active_connections(project_id),
        )

    def disconnect(self, project_id: str, ws: WebSocket) -> None:
        """Remove a WebSocket from the registry.

        Cleans up the project key when no connections remain.

        Args:
            project_id: Project UUID string the connection was watching.
            ws: The ``WebSocket`` instance to remove.
        """
        self._connections[project_id].discard(ws)
        if not self._connections[project_id]:
            del self._connections[project_id]
        logger.debug("WS disconnected: project=%s", project_id)

    async def broadcast(self, project_id: str, data: dict) -> None:  # type: ignore[type-arg]
        """Send JSON data to all clients watching project_id.

        Dead connections (those that raise on send) are silently removed.

        Args:
            project_id: Project UUID string to broadcast to.
            data: JSON-serialisable dict to send to all connected clients.
        """
        dead: set[WebSocket] = set()
        for ws in list(self._connections.get(project_id, [])):
            try:
                await ws.send_json(data)
            except Exception as exc:
                logger.debug("WS send failed (marking dead): %s", exc)
                dead.add(ws)

        for ws in dead:
            self.disconnect(project_id, ws)

    def active_connections(self, project_id: str) -> int:
        """Return the count of active connections for a project.

        Args:
            project_id: Project UUID string to query.

        Returns:
            Integer count of currently connected WebSocket clients.
        """
        return len(self._connections.get(project_id, set()))


# Module-level singleton — import and reuse across the application.
ws_manager: ConnectionManager = ConnectionManager()
