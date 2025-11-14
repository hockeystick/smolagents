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
"""Configuration management for smolagents."""
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv


logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    enabled: bool = True
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    enabled: bool = True
    max_calls: int = 100
    time_window: float = 60.0  # seconds


@dataclass
class CacheConfig:
    """Configuration for caching."""

    enabled: bool = True
    max_size: int = 128
    ttl: Optional[float] = 3600.0  # 1 hour in seconds


@dataclass
class SecurityConfig:
    """Configuration for security settings."""

    use_e2b: bool = False
    allowed_imports: list = field(default_factory=lambda: ["numpy", "pandas", "math", "datetime"])
    block_dangerous_patterns: bool = True
    audit_log_enabled: bool = True
    audit_log_path: str = "./logs/audit.log"


@dataclass
class MonitoringConfig:
    """Configuration for monitoring and logging."""

    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = "./logs/smolagents.log"
    metrics_enabled: bool = True
    telemetry_enabled: bool = False


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""

    max_steps: int = 6
    planning_interval: Optional[int] = None
    add_base_tools: bool = False
    provide_run_summary: bool = False


@dataclass
class ServerConfig:
    """Configuration for server deployment."""

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    timeout: int = 300
    health_check_path: str = "/health"


@dataclass
class SmolagentsConfig:
    """Main configuration for smolagents."""

    retry: RetryConfig = field(default_factory=RetryConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    server: ServerConfig = field(default_factory=ServerConfig)

    # API keys and secrets (loaded from environment)
    hf_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    e2b_api_key: Optional[str] = None

    def __post_init__(self):
        """Load environment variables and validate configuration."""
        self._load_env_vars()
        self._validate()

    def _load_env_vars(self):
        """Load configuration from environment variables."""
        # Load .env file if it exists
        load_dotenv()

        # Load API keys
        self.hf_api_key = os.getenv("HF_API_KEY") or os.getenv("HUGGING_FACE_HUB_TOKEN")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.e2b_api_key = os.getenv("E2B_API_KEY")

        # Override config from environment variables
        if log_level := os.getenv("SMOLAGENTS_LOG_LEVEL"):
            self.monitoring.log_level = log_level

        if max_steps := os.getenv("SMOLAGENTS_MAX_STEPS"):
            self.agent.max_steps = int(max_steps)

        if host := os.getenv("SMOLAGENTS_HOST"):
            self.server.host = host

        if port := os.getenv("SMOLAGENTS_PORT"):
            self.server.port = int(port)

    def _validate(self):
        """Validate configuration values."""
        if self.agent.max_steps < 1:
            raise ValueError("agent.max_steps must be >= 1")

        if self.retry.max_retries < 0:
            raise ValueError("retry.max_retries must be >= 0")

        if self.rate_limit.max_calls < 1:
            raise ValueError("rate_limit.max_calls must be >= 1")

        if self.cache.max_size < 1:
            raise ValueError("cache.max_size must be >= 1")

        if self.server.port < 1 or self.server.port > 65535:
            raise ValueError("server.port must be between 1 and 65535")

        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.monitoring.log_level.upper() not in valid_levels:
            raise ValueError(f"monitoring.log_level must be one of {valid_levels}")

    @classmethod
    def from_file(cls, path: str) -> "SmolagentsConfig":
        """
        Load configuration from a file.

        Args:
            path: Path to configuration file (JSON or YAML)

        Returns:
            Configuration instance
        """
        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(file_path) as f:
            if file_path.suffix in [".yaml", ".yml"]:
                data = yaml.safe_load(f)
            elif file_path.suffix == ".json":
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SmolagentsConfig":
        """
        Create configuration from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            Configuration instance
        """
        # Handle nested dataclasses
        if "retry" in data and isinstance(data["retry"], dict):
            data["retry"] = RetryConfig(**data["retry"])

        if "rate_limit" in data and isinstance(data["rate_limit"], dict):
            data["rate_limit"] = RateLimitConfig(**data["rate_limit"])

        if "cache" in data and isinstance(data["cache"], dict):
            data["cache"] = CacheConfig(**data["cache"])

        if "security" in data and isinstance(data["security"], dict):
            data["security"] = SecurityConfig(**data["security"])

        if "monitoring" in data and isinstance(data["monitoring"], dict):
            data["monitoring"] = MonitoringConfig(**data["monitoring"])

        if "agent" in data and isinstance(data["agent"], dict):
            data["agent"] = AgentConfig(**data["agent"])

        if "server" in data and isinstance(data["server"], dict):
            data["server"] = ServerConfig(**data["server"])

        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            Configuration as dictionary
        """
        result = asdict(self)

        # Remove sensitive information
        for key in ["hf_api_key", "openai_api_key", "anthropic_api_key", "e2b_api_key"]:
            if key in result and result[key]:
                result[key] = "***"

        return result

    def save(self, path: str):
        """
        Save configuration to file.

        Args:
            path: Output file path (JSON or YAML)
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data = self.to_dict()

        with open(file_path, "w") as f:
            if file_path.suffix in [".yaml", ".yml"]:
                yaml.dump(data, f, default_flow_style=False)
            elif file_path.suffix == ".json":
                json.dump(data, f, indent=2)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")

        logger.info(f"Configuration saved to {path}")

    def setup_logging(self):
        """Setup logging based on configuration."""
        log_level = getattr(logging, self.monitoring.log_level.upper())

        # Create formatter
        formatter = logging.Formatter(self.monitoring.log_format)

        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File handler
        if self.monitoring.log_file:
            log_path = Path(self.monitoring.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_path)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        logger.info(f"Logging configured: level={self.monitoring.log_level}, file={self.monitoring.log_file}")


# Global configuration instance
_config: Optional[SmolagentsConfig] = None


def get_config() -> SmolagentsConfig:
    """
    Get global configuration instance.

    Returns:
        Global configuration
    """
    global _config
    if _config is None:
        _config = SmolagentsConfig()
    return _config


def set_config(config: SmolagentsConfig):
    """
    Set global configuration instance.

    Args:
        config: Configuration to set as global
    """
    global _config
    _config = config


def load_config(path: Optional[str] = None) -> SmolagentsConfig:
    """
    Load and set global configuration.

    Args:
        path: Path to configuration file (uses default if None)

    Returns:
        Loaded configuration
    """
    if path:
        config = SmolagentsConfig.from_file(path)
    else:
        # Try to load from default locations
        default_paths = ["./smolagents.yaml", "./smolagents.yml", "./smolagents.json", "./config.yaml"]

        config = None
        for default_path in default_paths:
            if Path(default_path).exists():
                logger.info(f"Loading configuration from {default_path}")
                config = SmolagentsConfig.from_file(default_path)
                break

        if config is None:
            logger.info("No configuration file found, using defaults")
            config = SmolagentsConfig()

    set_config(config)
    config.setup_logging()
    return config
