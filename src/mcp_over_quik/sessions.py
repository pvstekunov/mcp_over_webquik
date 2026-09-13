"""Per-MCP-session webQUIK client storage."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from .client import WebQuikClient

logger = logging.getLogger(__name__)


@dataclass
class SessionEntry:
    client: WebQuikClient
    created_at: float = field(default_factory=time.time)
    last_seen_at: float = field(default_factory=time.time)


class SessionStore:
    def __init__(self, *, idle_timeout_sec: float = 8 * 3600) -> None:
        self._entries: dict[str, SessionEntry] = {}
        self._lock = asyncio.Lock()
        self._idle_timeout_sec = idle_timeout_sec

    async def touch(self, session_key: str) -> None:
        entry = self._entries.get(session_key)
        if entry is not None:
            entry.last_seen_at = time.time()

    async def get(self, session_key: str) -> WebQuikClient | None:
        entry = self._entries.get(session_key)
        if entry is None:
            return None
        entry.last_seen_at = time.time()
        return entry.client

    async def require(self, session_key: str) -> WebQuikClient:
        client = await self.get(session_key)
        if client is None:
            raise RuntimeError(
                "No active webQUIK session. Call login with your broker credentials first."
            )
        return client

    async def replace(self, session_key: str, host: str) -> WebQuikClient:
        async with self._lock:
            old = self._entries.pop(session_key, None)
        if old is not None:
            try:
                await old.client.disconnect()
            except Exception:
                logger.debug("Failed to disconnect previous session %s", session_key, exc_info=True)

        client = WebQuikClient(host=host)
        async with self._lock:
            self._entries[session_key] = SessionEntry(client=client)
        return client

    async def remove(self, session_key: str) -> bool:
        async with self._lock:
            entry = self._entries.pop(session_key, None)
        if entry is None:
            return False
        try:
            await entry.client.disconnect()
        except Exception:
            logger.debug("Failed to disconnect session %s", session_key, exc_info=True)
        return True

    def stats(self) -> dict[str, int | float]:
        now = time.time()
        return {
            "active_sessions": len(self._entries),
            "idle_timeout_sec": self._idle_timeout_sec,
            "oldest_idle_sec": min((now - e.last_seen_at for e in self._entries.values()), default=0),
        }
