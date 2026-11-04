"""
PRAVISION — Single-Use Short-Lived WebSocket Ticket Manager
Provides cryptographically secure, high-entropy, single-use authentication tickets
for WebSocket sessions. Tickets are bound to the specific user, role, and targeted
investigation ID, expire after 60 seconds, and are immediately invalidated upon consumption.
"""

import time
import secrets
import threading
from typing import Optional, Dict, Any


class WebSocketTicketManager:
    def __init__(self, ttl_seconds: int = 60):
        self._tickets: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def issue_ticket(
        self,
        user_id: str,
        username: str,
        role: str,
        investigation_id: str
    ) -> str:
        """Issues a single-use ticket bound to user and investigation."""
        ticket = f"wst_{secrets.token_urlsafe(32)}"
        now = time.time()
        with self._lock:
            self._purge_expired(now)
            self._tickets[ticket] = {
                "user_id": user_id,
                "username": username,
                "role": role,
                "investigation_id": investigation_id,
                "issued_at": now,
                "expires_at": now + self._ttl,
                "used": False
            }
        return ticket

    def consume_ticket(
        self,
        ticket: str,
        expected_investigation_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Validates, consumes, and atomically invalidates a ticket.
        Returns ticket metadata if valid; returns None if ticket is invalid,
        expired, mismatched, or already used.
        """
        if not ticket:
            return None

        now = time.time()
        with self._lock:
            ticket_data = self._tickets.get(ticket)
            if not ticket_data:
                return None

            # 1. Check expiration
            if now > ticket_data["expires_at"]:
                self._tickets.pop(ticket, None)
                return None

            # 2. Check already consumed
            if ticket_data["used"]:
                self._tickets.pop(ticket, None)
                return None

            # 3. Check investigation binding
            if ticket_data["investigation_id"] != expected_investigation_id:
                return None

            # 4. Invalidate and remove ticket atomically
            ticket_data["used"] = True
            self._tickets.pop(ticket, None)
            return ticket_data

    def _purge_expired(self, now: float):
        expired = [t for t, data in self._tickets.items() if now > data["expires_at"]]
        for t in expired:
            self._tickets.pop(t, None)


ws_ticket_manager = WebSocketTicketManager(ttl_seconds=60)

