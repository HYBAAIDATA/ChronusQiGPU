"""Resource management and monitoring for production."""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionMetrics:
    """Metrics for a session."""

    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    request_count: int = 0
    memory_usage_mb: float = 0.0
    nlp_operations: int = 0
    kb_queries: int = 0
    errors: int = 0
    averageResponseTime_ms: float = 0.0
    totalProcessingTime_ms: float = 0.0

    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if session is expired."""
        elapsed = (datetime.now() - self.last_accessed).total_seconds()
        return elapsed > ttl_seconds

    def update_access(self) -> None:
        """Update last access time."""
        self.last_accessed = datetime.now()

    def record_request(self, response_time_ms: float) -> None:
        """Record a request."""
        self.request_count += 1
        self.totalProcessingTime_ms += response_time_ms
        self.averageResponseTime_ms = self.totalProcessingTime_ms / self.request_count
        self.update_access()


class ResourceManager:
    """Manages resources and prevents exhaustion."""

    def __init__(
        self,
        max_sessions: int = 1000,
        session_ttl_seconds: int = 3600,
        cleanup_interval_seconds: int = 300,
    ):
        """Initialize resource manager."""
        self.max_sessions = max_sessions
        self.session_ttl_seconds = session_ttl_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds

        self.sessions: dict[str, SessionMetrics] = {}
        self.lock = threading.RLock()
        self.cleanup_task = None
        self.running = False

        logger.info(f"Resource manager initialized with max_sessions={max_sessions}")

    async def start(self) -> None:
        """Start the resource manager."""
        if self.running:
            return

        self.running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Resource manager started")

    async def stop(self) -> None:
        """Stop the resource manager."""
        self.running = False
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Resource manager stopped")

    def create_session(self, session_id: str) -> bool:
        """Create a new session if under limit."""
        with self.lock:
            if len(self.sessions) >= self.max_sessions:
                logger.warning(
                    f"Cannot create session {session_id}: max sessions reached"
                )
                return False

            self.sessions[session_id] = SessionMetrics(session_id=session_id)
            logger.info(
                f"Session {session_id} created. Total sessions: {len(self.sessions)}"
            )
            return True

    def destroy_session(self, session_id: str) -> bool:
        """Destroy a session."""
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(
                    f"Session {session_id} destroyed. Total sessions: {len(self.sessions)}"
                )
                return True
            return False

    def get_session_metrics(self, session_id: str) -> Optional[SessionMetrics]:
        """Get metrics for a session."""
        with self.lock:
            return self.sessions.get(session_id)

    def record_request(self, session_id: str, response_time_ms: float) -> None:
        """Record a request for a session."""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].record_request(response_time_ms)

    def record_nlp_operation(self, session_id: str) -> None:
        """Record an NLP operation."""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].nlp_operations += 1

    def record_kb_query(self, session_id: str) -> None:
        """Record a KB query."""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].kb_queries += 1

    def record_error(self, session_id: str) -> None:
        """Record an error."""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].errors += 1

    def get_all_metrics(self) -> dict[str, SessionMetrics]:
        """Get metrics for all sessions."""
        with self.lock:
            return dict(self.sessions)

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        with self.lock:
            if not self.sessions:
                return {
                    "total_sessions": 0,
                    "total_requests": 0,
                    "total_errors": 0,
                    "avg_response_time_ms": 0.0,
                }

            total_requests = sum(s.request_count for s in self.sessions.values())
            total_errors = sum(s.errors for s in self.sessions.values())
            avg_response_time = sum(
                s.averageResponseTime_ms for s in self.sessions.values()
            ) / len(self.sessions)

            return {
                "total_sessions": len(self.sessions),
                "total_requests": total_requests,
                "total_errors": total_errors,
                "avg_response_time_ms": avg_response_time,
                "max_sessions_capacity": self.max_sessions,
            }

    async def _cleanup_loop(self) -> None:
        """Cleanup loop for expired sessions."""
        while self.running:
            try:
                await asyncio.sleep(self.cleanup_interval_seconds)
                self._cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions."""
        with self.lock:
            expired = [
                session_id
                for session_id, metrics in self.sessions.items()
                if metrics.is_expired(self.session_ttl_seconds)
            ]

            for session_id in expired:
                del self.sessions[session_id]
                logger.info(f"Cleaned up expired session {session_id}")

            if expired:
                logger.info(f"Cleaned up {len(expired)} expired sessions")


class CircuitBreaker:
    """Circuit breaker for fault tolerance."""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: float = 30.0,
        success_threshold: int = 2,
    ):
        """Initialize circuit breaker."""
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.success_threshold = success_threshold

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half_open
        self.lock = threading.RLock()

    def record_success(self) -> None:
        """Record a successful operation."""
        with self.lock:
            self.failure_count = 0

            if self.state == "half_open":
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = "closed"
                    logger.info("Circuit breaker reset to closed state")

    def record_failure(self) -> None:
        """Record a failed operation."""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.warning(
                    f"Circuit breaker opened after {self.failure_count} failures"
                )

    def can_proceed(self) -> bool:
        """Check if we can proceed with operation."""
        with self.lock:
            if self.state == "closed":
                return True

            if self.state == "open":
                # Check if we should transition to half-open
                if (
                    self.last_failure_time
                    and time.time() - self.last_failure_time >= self.timeout_seconds
                ):
                    self.state = "half_open"
                    self.success_count = 0
                    logger.info("Circuit breaker transitioned to half-open state")
                    return True
                return False

            # half_open state - allow limited attempts
            return True
