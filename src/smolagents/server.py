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
"""Production-ready server for deploying smolagents as an API service."""
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from .config import get_config, load_config


logger = logging.getLogger(__name__)


# Only import FastAPI if needed (for optional deployment)
try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, StreamingResponse
    from pydantic import BaseModel, Field
    import uvicorn

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger.warning("FastAPI not available. Install with: pip install 'smolagents[server]'")


# Request/Response models
if FASTAPI_AVAILABLE:

    class AgentRunRequest(BaseModel):
        """Request model for agent run."""

        task: str = Field(..., description="Task for the agent to perform")
        model_id: Optional[str] = Field(None, description="Model ID to use")
        model_type: str = Field("HfApiModel", description="Type of model (HfApiModel, LiteLLMModel, etc.)")
        tools: List[str] = Field(default_factory=list, description="List of tool names to use")
        max_steps: Optional[int] = Field(None, description="Maximum number of steps")
        stream: bool = Field(False, description="Whether to stream responses")
        reset: bool = Field(True, description="Whether to reset conversation")
        additional_args: Optional[Dict] = Field(None, description="Additional arguments")

    class AgentRunResponse(BaseModel):
        """Response model for agent run."""

        result: str
        steps: int
        success: bool
        metrics: Optional[Dict] = None
        error: Optional[str] = None

    class HealthResponse(BaseModel):
        """Health check response."""

        status: str
        version: str
        timestamp: float
        config: Dict


# Global agent instance
_agent_cache: Dict[str, any] = {}


def get_or_create_agent(model_type: str, model_id: Optional[str], tools: List[str], max_steps: Optional[int]):
    """Get or create an agent instance (cached)."""
    from .agents import CodeAgent
    from .default_tools import TOOL_MAPPING

    config = get_config()

    # Create cache key
    cache_key = f"{model_type}:{model_id}:{','.join(sorted(tools))}:{max_steps or config.agent.max_steps}"

    if cache_key in _agent_cache:
        logger.debug(f"Using cached agent: {cache_key}")
        return _agent_cache[cache_key]

    # Import model dynamically
    if model_type == "HfApiModel":
        from .models import HfApiModel

        model = HfApiModel(model_id=model_id) if model_id else HfApiModel()
    elif model_type == "LiteLLMModel":
        from .models import LiteLLMModel

        if not model_id:
            raise ValueError("model_id required for LiteLLMModel")
        model = LiteLLMModel(model_id)
    elif model_type == "TransformersModel":
        from .models import TransformersModel

        if not model_id:
            raise ValueError("model_id required for TransformersModel")
        model = TransformersModel(model_id)
    else:
        raise ValueError(f"Unknown model_type: {model_type}")

    # Initialize tools
    tool_instances = []
    for tool_name in tools:
        if tool_name in TOOL_MAPPING:
            tool_instances.append(TOOL_MAPPING[tool_name]())
        else:
            logger.warning(f"Unknown tool: {tool_name}")

    # Create agent
    agent = CodeAgent(
        tools=tool_instances,
        model=model,
        max_steps=max_steps or config.agent.max_steps,
        add_base_tools=config.agent.add_base_tools,
    )

    # Cache agent
    _agent_cache[cache_key] = agent
    logger.info(f"Created new agent: {cache_key}")

    return agent


if FASTAPI_AVAILABLE:

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Lifespan context manager for startup/shutdown."""
        # Startup
        logger.info("Starting smolagents server...")
        config = load_config()
        logger.info(f"Configuration loaded: {config.to_dict()}")

        yield

        # Shutdown
        logger.info("Shutting down smolagents server...")
        _agent_cache.clear()

    # Create FastAPI app
    app = FastAPI(
        title="smolagents API",
        description="Production-ready API for smolagents",
        version="1.10.0",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware for request logging
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log all requests."""
        start_time = time.time()

        response = await call_next(request)

        duration = time.time() - start_time
        logger.info(
            f"{request.method} {request.url.path} - Status: {response.status_code} - Duration: {duration:.3f}s"
        )

        return response

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        config = get_config()
        return HealthResponse(
            status="healthy",
            version="1.10.0",
            timestamp=time.time(),
            config=config.to_dict(),
        )

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "smolagents API",
            "version": "1.10.0",
            "endpoints": {
                "health": "/health",
                "run": "/run",
                "docs": "/docs",
            },
        }

    @app.post("/run", response_model=AgentRunResponse)
    async def run_agent(request: AgentRunRequest):
        """Run an agent task."""
        try:
            config = get_config()

            # Apply rate limiting if enabled
            if config.rate_limit.enabled:
                # Rate limiting logic would go here
                pass

            # Get or create agent
            agent = get_or_create_agent(
                model_type=request.model_type,
                model_id=request.model_id,
                tools=request.tools,
                max_steps=request.max_steps,
            )

            # Run agent
            start_time = time.time()

            if request.stream:
                # TODO: Implement streaming response
                raise HTTPException(status_code=501, detail="Streaming not yet implemented")

            result = agent.run(
                task=request.task,
                reset=request.reset,
                additional_args=request.additional_args,
            )

            duration = time.time() - start_time

            # Get metrics
            metrics = {
                "duration": duration,
                "steps": agent.step_number,
            }

            if hasattr(agent, "monitor"):
                metrics.update(agent.monitor.get_metrics())

            return AgentRunResponse(
                result=str(result),
                steps=agent.step_number,
                success=True,
                metrics=metrics,
            )

        except Exception as e:
            logger.error(f"Error running agent: {e}", exc_info=True)
            return AgentRunResponse(result="", steps=0, success=False, error=str(e))

    @app.get("/metrics")
    async def get_metrics():
        """Get server metrics."""
        return {
            "agents_cached": len(_agent_cache),
            "cache_keys": list(_agent_cache.keys()),
        }

    @app.post("/clear_cache")
    async def clear_cache():
        """Clear agent cache."""
        _agent_cache.clear()
        return {"message": "Cache cleared", "agents_cleared": len(_agent_cache)}


def main():
    """Run the server."""
    if not FASTAPI_AVAILABLE:
        print("FastAPI not available. Install with: pip install fastapi uvicorn")
        return

    config = load_config()

    uvicorn.run(
        "smolagents.server:app",
        host=config.server.host,
        port=config.server.port,
        workers=config.server.workers,
        timeout_keep_alive=config.server.timeout,
        log_level=config.monitoring.log_level.lower(),
    )


if __name__ == "__main__":
    main()
