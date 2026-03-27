"""
Circuit breaker utility for handling failures and cooldowns.
"""
import time
import logging

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """Simple circuit breaker for AI service calls."""
    def __init__(self, threshold, cooldown):
        self._failures = 0
        self._open_until = 0.0
        self._threshold = threshold
        self._cooldown = cooldown

    # Circuit breaker is open means the upstream service is currently unavailable, 
    # so we should skip calls to it.
    def is_open(self):
        if self._open_until > time.monotonic():
            logger.warning("Circuit breaker OPEN — skipping AI call (%ds remaining)", round(self._open_until - time.monotonic()))
            return True
        return False

    # On success, reset failure count and close the circuit if it was open.
    def record_success(self):
        self._failures = 0
        self._open_until = 0.0

    # On failure, increment failure count and open the circuit if threshold is reached.
    def record_failure(self):
        self._failures += 1
        if self._failures >= self._threshold:
            self._open_until = time.monotonic() + self._cooldown
            logger.error("Circuit breaker OPENED after %d failures", self._failures)
