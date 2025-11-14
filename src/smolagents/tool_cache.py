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
# distributed under the License.
"""Caching mechanism for tool outputs."""
import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Optional


logger = logging.getLogger(__name__)


class ToolCache:
    """LRU cache for tool outputs with TTL support."""

    def __init__(self, max_size: int = 128, ttl: Optional[float] = None):
        """
        Initialize tool cache.

        Args:
            max_size: Maximum number of cached items
            ttl: Time-to-live in seconds (None = no expiration)
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache = OrderedDict()
        self.stats = {"hits": 0, "misses": 0, "evictions": 0}

    def _generate_key(self, tool_name: str, *args, **kwargs) -> str:
        """
        Generate cache key from tool name and arguments.

        Args:
            tool_name: Name of the tool
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Cache key as hex string
        """
        # Create deterministic representation
        key_data = {"tool": tool_name, "args": args, "kwargs": sorted(kwargs.items())}

        try:
            key_str = json.dumps(key_data, sort_keys=True, default=str)
        except (TypeError, ValueError):
            # Fallback for non-serializable objects
            key_str = f"{tool_name}_{str(args)}_{str(sorted(kwargs.items()))}"

        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(self, tool_name: str, *args, **kwargs) -> Optional[Any]:
        """
        Get cached result if available and not expired.

        Args:
            tool_name: Name of the tool
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Cached result or None
        """
        key = self._generate_key(tool_name, *args, **kwargs)

        if key in self.cache:
            cached_time, cached_value = self.cache[key]

            # Check TTL
            if self.ttl and (time.time() - cached_time) > self.ttl:
                logger.debug(f"Cache expired for {tool_name}")
                del self.cache[key]
                self.stats["misses"] += 1
                return None

            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self.stats["hits"] += 1
            logger.debug(f"Cache hit for {tool_name} (hit rate: {self.get_hit_rate():.1%})")
            return cached_value

        self.stats["misses"] += 1
        return None

    def set(self, tool_name: str, result: Any, *args, **kwargs):
        """
        Cache a tool result.

        Args:
            tool_name: Name of the tool
            result: Result to cache
            args: Positional arguments
            kwargs: Keyword arguments
        """
        key = self._generate_key(tool_name, *args, **kwargs)

        # Remove oldest item if at capacity
        if len(self.cache) >= self.max_size and key not in self.cache:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            self.stats["evictions"] += 1
            logger.debug(f"Cache eviction (size: {len(self.cache)}/{self.max_size})")

        self.cache[key] = (time.time(), result)
        logger.debug(f"Cached result for {tool_name} (size: {len(self.cache)}/{self.max_size})")

    def clear(self):
        """Clear all cached items."""
        self.cache.clear()
        logger.debug("Cache cleared")

    def get_hit_rate(self) -> float:
        """
        Calculate cache hit rate.

        Returns:
            Hit rate as a float between 0 and 1
        """
        total = self.stats["hits"] + self.stats["misses"]
        return self.stats["hits"] / total if total > 0 else 0.0

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "evictions": self.stats["evictions"],
            "hit_rate": self.get_hit_rate(),
        }


class CachedTool:
    """Wrapper to add caching to any tool."""

    def __init__(self, tool: "Tool", cache: Optional[ToolCache] = None):
        """
        Initialize cached tool wrapper.

        Args:
            tool: The tool to wrap
            cache: Cache instance (creates default if None)
        """
        self.tool = tool
        self.cache = cache or ToolCache()

        # Copy attributes from wrapped tool
        self.name = tool.name
        self.description = tool.description
        self.inputs = tool.inputs
        self.output_type = tool.output_type
        self.is_initialized = False

    def forward(self, *args, **kwargs):
        """
        Execute tool with caching.

        Args:
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Tool result (cached or fresh)
        """
        # Check cache first
        cached_result = self.cache.get(self.name, *args, **kwargs)
        if cached_result is not None:
            return cached_result

        # Execute tool
        result = self.tool.forward(*args, **kwargs)

        # Cache result
        self.cache.set(self.name, result, *args, **kwargs)

        return result

    def __call__(self, *args, **kwargs):
        """Make the cached tool callable like the original tool."""
        if not self.is_initialized:
            self.setup()

        # Handle arguments passed as dictionary
        if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], dict):
            potential_kwargs = args[0]
            if all(key in self.inputs for key in potential_kwargs):
                args = ()
                kwargs = potential_kwargs

        return self.forward(*args, **kwargs)

    def setup(self):
        """Setup the tool (delegates to wrapped tool)."""
        if hasattr(self.tool, "setup"):
            self.tool.setup()
        self.is_initialized = True

    def clear_cache(self):
        """Clear this tool's cache."""
        self.cache.clear()

    def get_cache_stats(self) -> dict:
        """Get cache statistics for this tool."""
        return self.cache.get_stats()
