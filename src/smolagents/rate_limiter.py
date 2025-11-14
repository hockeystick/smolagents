#!/usr/bin/env python
# coding=utf-8

# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Rate limiting for tool execution and API calls."""
import logging
import time
from collections import deque
from contextlib import contextmanager
from threading import Lock
from typing import Optional


logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    pass


class RateLimiter:
    """Token bucket rate limiter for controlling request rates."""

    def __init__(self, max_calls: int, time_window: float, name: str = "default"):
        """
        Initialize rate limiter.

        Args:
            max_calls: Maximum number of calls allowed within time_window
            time_window: Time window in seconds
            name: Name of this rate limiter for logging
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.name = name
        self.calls = deque()
        self.lock = Lock()

    def acquire(self, timeout: Optional[float] = None, block: bool = True) -> bool:
        """
        Acquire permission to make a call.

        Args:
            timeout: Maximum time to wait in seconds (None = wait forever)
            block: Whether to block until permission is granted

        Returns:
            True if permission granted, False if timeout or non-blocking and would block

        Raises:
            RateLimitExceeded: If blocking=False and rate limit exceeded
        """
        start_time = time.time()

        while True:
            with self.lock:
                now = time.time()

                # Remove calls outside the time window
                while self.calls and self.calls[0] < now - self.time_window:
                    self.calls.popleft()

                # Check if we can make the call
                if len(self.calls) < self.max_calls:
                    self.calls.append(now)
                    logger.debug(
                        f"Rate limiter '{self.name}': {len(self.calls)}/{self.max_calls} calls in window"
                    )
                    return True

            # If not blocking, raise exception
            if not block:
                raise RateLimitExceeded(
                    f"Rate limit exceeded for '{self.name}': {self.max_calls} calls per {self.time_window}s"
                )

            # Check timeout
            if timeout and (time.time() - start_time) >= timeout:
                logger.warning(f"Rate limiter '{self.name}': timeout after {timeout}s")
                return False

            # Wait before checking again
            time.sleep(0.1)

    @contextmanager
    def limit(self, timeout: Optional[float] = None):
        """
        Context manager for rate limiting.

        Args:
            timeout: Maximum time to wait in seconds

        Example:
            >>> limiter = RateLimiter(max_calls=10, time_window=60)
            >>> with limiter.limit():
            ...     make_api_call()
        """
        if not self.acquire(timeout=timeout):
            raise RateLimitExceeded(f"Could not acquire rate limit for '{self.name}' within {timeout}s")
        try:
            yield
        finally:
            pass

    def reset(self):
        """Reset the rate limiter, clearing all tracked calls."""
        with self.lock:
            self.calls.clear()
            logger.debug(f"Rate limiter '{self.name}': reset")

    def get_stats(self) -> dict:
        """
        Get current statistics.

        Returns:
            Dictionary with current call count and capacity
        """
        with self.lock:
            now = time.time()
            # Remove old calls
            while self.calls and self.calls[0] < now - self.time_window:
                self.calls.popleft()

            return {
                "current_calls": len(self.calls),
                "max_calls": self.max_calls,
                "time_window": self.time_window,
                "available": self.max_calls - len(self.calls),
            }


class MultiRateLimiter:
    """Manages multiple rate limiters with different time windows."""

    def __init__(self):
        """Initialize multi-rate limiter."""
        self.limiters = {}

    def add_limiter(self, name: str, max_calls: int, time_window: float):
        """
        Add a rate limiter.

        Args:
            name: Name of the limiter
            max_calls: Maximum calls in time window
            time_window: Time window in seconds
        """
        self.limiters[name] = RateLimiter(max_calls, time_window, name)

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire permission from all limiters.

        Args:
            timeout: Maximum time to wait

        Returns:
            True if all limiters grant permission
        """
        for limiter in self.limiters.values():
            if not limiter.acquire(timeout=timeout):
                return False
        return True

    @contextmanager
    def limit(self, timeout: Optional[float] = None):
        """Context manager for multi-rate limiting."""
        if not self.acquire(timeout=timeout):
            raise RateLimitExceeded(f"Could not acquire all rate limits within {timeout}s")
        try:
            yield
        finally:
            pass

    def reset_all(self):
        """Reset all rate limiters."""
        for limiter in self.limiters.values():
            limiter.reset()

    def get_all_stats(self) -> dict:
        """Get statistics for all limiters."""
        return {name: limiter.get_stats() for name, limiter in self.limiters.items()}
