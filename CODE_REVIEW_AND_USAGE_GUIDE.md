# smolagents - Code Review & Usage Guide

## Executive Summary

**smolagents** is a well-architected, lightweight library for building AI agents that can execute code and use tools. The codebase demonstrates good software engineering practices with clear separation of concerns, comprehensive type hints, and strong security considerations.

**Overall Assessment**: 8.5/10
- **Strengths**: Clean architecture, security-first design, excellent documentation
- **Areas for Improvement**: Error handling, test coverage visibility, performance optimizations

---

## Table of Contents

1. [Code Review & Improvement Suggestions](#code-review--improvement-suggestions)
2. [Quick Start Guide](#quick-start-guide)
3. [Comprehensive Usage Instructions](#comprehensive-usage-instructions)
4. [Best Practices](#best-practices)
5. [Troubleshooting](#troubleshooting)

---

## Code Review & Improvement Suggestions

### 1. Architecture & Design (9/10)

#### Strengths
- **Clear separation of concerns**: Agents, tools, models, and executors are properly separated
- **Minimal abstraction**: ~1,000 lines for core logic (agents.py: 1333 lines) keeps it maintainable
- **Flexible model integration**: Supports multiple LLM providers through clean interfaces
- **Security-first design**: Sandboxed execution via E2B and local safe interpreter

#### Improvements

**Priority: HIGH - Add retry mechanism with exponential backoff**

Location: `src/smolagents/models.py`

```python
# Current: No retry logic for API calls
# Suggestion: Add retry decorator

from functools import wraps
import time

def retry_with_backoff(max_retries=3, initial_delay=1, backoff_factor=2):
    """Retry decorator with exponential backoff for API calls"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                        delay *= backoff_factor

            raise last_exception
        return wrapper
    return decorator

# Usage:
class HfApiModel:
    @retry_with_backoff(max_retries=3)
    def __call__(self, messages, ...):
        # API call logic
        pass
```

**Priority: MEDIUM - Improve type hints consistency**

Location: Multiple files

```python
# Current in agents.py:191-194
def __init__(
    self,
    tools: List[Tool],
    model: Callable[[List[Dict[str, str]]], ChatMessage],
    ...
)

# Suggestion: Use Protocol for better type safety
from typing import Protocol

class LLMModel(Protocol):
    """Protocol for LLM models"""
    def __call__(self, messages: List[Dict[str, str]]) -> ChatMessage: ...

def __init__(
    self,
    tools: List[Tool],
    model: LLMModel,
    ...
)
```

**Priority: LOW - Add configuration validation**

Location: `src/smolagents/agents.py:191-260`

```python
# Suggestion: Add configuration dataclass

from dataclasses import dataclass
from typing import Optional

@dataclass
class AgentConfig:
    """Configuration for agent initialization"""
    max_steps: int = 6
    verbosity_level: LogLevel = LogLevel.INFO
    add_base_tools: bool = False
    planning_interval: Optional[int] = None

    def __post_init__(self):
        if self.max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        if self.planning_interval and self.planning_interval < 1:
            raise ValueError("planning_interval must be >= 1")

# Usage:
agent = CodeAgent(
    tools=[...],
    model=model,
    config=AgentConfig(max_steps=10, verbosity_level=LogLevel.DEBUG)
)
```

---

### 2. Error Handling & Robustness (7.5/10)

#### Strengths
- Custom exception hierarchy (`AgentError`, `AgentParsingError`, etc.)
- Error messages are informative and logged properly
- Security patterns are blocked (DANGEROUS_PATTERNS in local_python_executor.py:117-135)

#### Improvements

**Priority: HIGH - Add context managers for resource cleanup**

Location: `src/smolagents/agents.py:406-458`

```python
# Current: No explicit cleanup of resources
# Suggestion: Add context manager support

from contextlib import contextmanager

class MultiStepAgent:
    @contextmanager
    def session(self, task: str, **kwargs):
        """Context manager for agent sessions"""
        try:
            self.logger.log_task(content=task, ...)
            yield self
        except Exception as e:
            self.logger.log(f"Session failed: {e}", level=LogLevel.ERROR)
            raise
        finally:
            # Cleanup resources
            self.monitor.finalize()
            if hasattr(self, '_temp_files'):
                self._cleanup_temp_files()

# Usage:
with agent.session("Solve this task") as session:
    result = session.run(task)
```

**Priority: MEDIUM - Improve error messages with suggestions**

Location: `src/smolagents/utils.py:130-149`

```python
# Current in parse_json_blob:
raise ValueError(f"The JSON blob you used is invalid...")

# Suggestion: Add helpful recovery suggestions
class JSONParsingError(AgentParsingError):
    """Enhanced JSON parsing error with suggestions"""
    def __init__(self, original_error, json_blob, logger):
        suggestions = []
        if "Expecting property name" in str(original_error):
            suggestions.append("Check for trailing commas in JSON objects")
        if "Expecting value" in str(original_error):
            suggestions.append("Ensure all values are properly quoted")

        message = f"JSON parsing failed: {original_error}\n"
        message += f"Problematic JSON: {json_blob[:200]}...\n"
        if suggestions:
            message += "Suggestions:\n" + "\n".join(f"  - {s}" for s in suggestions)

        super().__init__(message, logger)
```

**Priority: HIGH - Add input validation for tool execution**

Location: `src/smolagents/agents.py:355-400`

```python
# Suggestion: Validate inputs before execution

def execute_tool_call(self, tool_name: str, arguments: Union[Dict[str, str], str]) -> Any:
    """Execute tool with validated inputs"""
    available_tools = {**self.tools, **self.managed_agents}

    # Validate tool exists
    if tool_name not in available_tools:
        similar_tools = difflib.get_close_matches(tool_name, available_tools.keys(), n=3)
        error_msg = f"Unknown tool '{tool_name}'."
        if similar_tools:
            error_msg += f" Did you mean: {', '.join(similar_tools)}?"
        error_msg += f"\nAvailable tools: {list(available_tools.keys())}"
        raise AgentExecutionError(error_msg, self.logger)

    # Validate argument types
    tool = available_tools[tool_name]
    if isinstance(arguments, dict) and tool_name in self.tools:
        self._validate_tool_arguments(tool, arguments)

    # ... rest of execution logic

def _validate_tool_arguments(self, tool: Tool, arguments: Dict[str, Any]):
    """Validate tool arguments against expected inputs"""
    required_inputs = {k for k, v in tool.inputs.items()
                      if not v.get('nullable', False)}
    provided_inputs = set(arguments.keys())

    missing = required_inputs - provided_inputs
    if missing:
        raise AgentExecutionError(
            f"Missing required arguments for {tool.name}: {missing}",
            self.logger
        )

    extra = provided_inputs - set(tool.inputs.keys())
    if extra:
        self.logger.log(
            f"Warning: Ignoring unexpected arguments for {tool.name}: {extra}",
            level=LogLevel.WARNING
        )
```

---

### 3. Security (9/10)

#### Strengths
- **Excellent sandboxing**: E2B integration for isolated execution
- **Safe interpreter**: LocalPythonInterpreter blocks dangerous operations
- **Pattern blocking**: DANGEROUS_PATTERNS prevents risky imports
- **Input sanitization**: handle_agent_input_types/handle_agent_output_types

#### Improvements

**Priority: MEDIUM - Add rate limiting**

Location: New file `src/smolagents/rate_limiter.py`

```python
"""Rate limiting for tool execution and API calls"""
import time
from collections import deque
from threading import Lock
from typing import Optional

class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, max_calls: int, time_window: float):
        """
        Args:
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = deque()
        self.lock = Lock()

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire permission to make a call.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if permission granted, False if timeout
        """
        start_time = time.time()

        while True:
            with self.lock:
                now = time.time()
                # Remove old calls outside window
                while self.calls and self.calls[0] < now - self.time_window:
                    self.calls.popleft()

                if len(self.calls) < self.max_calls:
                    self.calls.append(now)
                    return True

            if timeout and (time.time() - start_time) >= timeout:
                return False

            time.sleep(0.1)

# Usage in agents.py:
class MultiStepAgent:
    def __init__(self, ..., rate_limit: Optional[RateLimiter] = None):
        self.rate_limiter = rate_limit or RateLimiter(max_calls=100, time_window=60)

    def execute_tool_call(self, tool_name: str, arguments):
        if not self.rate_limiter.acquire(timeout=30):
            raise AgentExecutionError("Rate limit exceeded", self.logger)
        # ... execute tool
```

**Priority: LOW - Add audit logging**

Location: `src/smolagents/monitoring.py`

```python
# Suggestion: Add security audit trail

import json
from datetime import datetime
from pathlib import Path

class SecurityAuditor:
    """Audit logger for security-sensitive operations"""

    def __init__(self, audit_log_path: Path):
        self.audit_log_path = audit_log_path
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_code_execution(self, code: str, user_id: Optional[str] = None):
        """Log code execution attempts"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "code_execution",
            "user_id": user_id,
            "code_hash": hashlib.sha256(code.encode()).hexdigest(),
            "code_preview": code[:200],
        }
        self._write_entry(entry)

    def _write_entry(self, entry: dict):
        with open(self.audit_log_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')
```

---

### 4. Performance & Optimization (7/10)

#### Improvements

**Priority: MEDIUM - Add caching for repeated operations**

Location: `src/smolagents/tools.py`

```python
# Suggestion: Cache tool outputs for identical inputs

from functools import lru_cache
import hashlib
import json

class CachedTool(Tool):
    """Tool wrapper with result caching"""

    def __init__(self, tool: Tool, cache_size: int = 128):
        super().__init__()
        self.tool = tool
        self.cache = {}
        self.cache_size = cache_size
        # Copy attributes from wrapped tool
        self.name = tool.name
        self.description = tool.description
        self.inputs = tool.inputs
        self.output_type = tool.output_type

    def _get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        cache_dict = {"args": args, "kwargs": kwargs}
        return hashlib.md5(
            json.dumps(cache_dict, sort_keys=True).encode()
        ).hexdigest()

    def forward(self, *args, **kwargs):
        cache_key = self._get_cache_key(*args, **kwargs)

        if cache_key in self.cache:
            logger.debug(f"Cache hit for {self.name}")
            return self.cache[cache_key]

        result = self.tool.forward(*args, **kwargs)

        # LRU eviction
        if len(self.cache) >= self.cache_size:
            self.cache.pop(next(iter(self.cache)))

        self.cache[cache_key] = result
        return result

# Usage:
search_tool = DuckDuckGoSearchTool()
cached_search = CachedTool(search_tool, cache_size=256)
agent = CodeAgent(tools=[cached_search], model=model)
```

**Priority: LOW - Optimize memory for long conversations**

Location: `src/smolagents/memory.py`

```python
# Suggestion: Add memory compression for long-running agents

class CompressedAgentMemory(AgentMemory):
    """Memory with automatic compression of old steps"""

    def __init__(self, system_prompt, max_uncompressed_steps: int = 10):
        super().__init__(system_prompt)
        self.max_uncompressed_steps = max_uncompressed_steps
        self.compressed_summary = ""

    def compress_old_steps(self):
        """Compress old steps into summary"""
        if len(self.steps) <= self.max_uncompressed_steps:
            return

        # Keep recent steps, compress older ones
        steps_to_compress = self.steps[:-self.max_uncompressed_steps]
        self.compressed_summary = self._summarize_steps(steps_to_compress)
        self.steps = self.steps[-self.max_uncompressed_steps:]

    def _summarize_steps(self, steps: List[ActionStep]) -> str:
        """Create summary of steps using LLM"""
        # Implementation: Use LLM to summarize old steps
        pass
```

---

### 5. Code Quality (8.5/10)

#### Strengths
- Consistent style (Ruff configuration in pyproject.toml)
- Good docstrings for public APIs
- Type hints throughout codebase
- Clear naming conventions

#### Improvements

**Priority: LOW - Add comprehensive docstring examples**

Location: `src/smolagents/tools.py:82-102`

```python
class Tool:
    """
    A base class for the functions used by the agent.

    Subclass this and implement the `forward` method as well as required class attributes.

    Attributes:
        name (str): A performative name for your tool (e.g., "text-classifier")
        description (str): Short description of what your tool does
        inputs (Dict[str, Dict[str, Union[str, type]]]): Expected input schema
        output_type (str): The type of output returned

    Example:
        >>> class CalculatorTool(Tool):
        ...     name = "calculator"
        ...     description = "Performs basic arithmetic operations"
        ...     inputs = {
        ...         "operation": {
        ...             "type": "string",
        ...             "description": "The operation: add, subtract, multiply, divide"
        ...         },
        ...         "a": {"type": "number", "description": "First operand"},
        ...         "b": {"type": "number", "description": "Second operand"}
        ...     }
        ...     output_type = "number"
        ...
        ...     def forward(self, operation: str, a: float, b: float) -> float:
        ...         operations = {
        ...             "add": lambda x, y: x + y,
        ...             "subtract": lambda x, y: x - y,
        ...             "multiply": lambda x, y: x * y,
        ...             "divide": lambda x, y: x / y if y != 0 else float('inf')
        ...         }
        ...         return operations[operation](a, b)

        >>> calc = CalculatorTool()
        >>> calc(operation="add", a=5, b=3)
        8.0

    See Also:
        - DuckDuckGoSearchTool for a complete example
        - Tool.from_hub() for loading tools from HuggingFace Hub
    """
```

**Priority: MEDIUM - Add debug utilities**

Location: New file `src/smolagents/debug_utils.py`

```python
"""Debug utilities for development"""
import json
from pathlib import Path
from typing import Any, Optional

class AgentDebugger:
    """Helper class for debugging agent runs"""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_conversation(self, agent: "MultiStepAgent", filename: str = "conversation.json"):
        """Save entire conversation history"""
        conversation = {
            "task": agent.task,
            "steps": [step.to_dict() for step in agent.memory.steps],
            "metrics": agent.monitor.get_metrics(),
        }

        output_path = self.output_dir / filename
        with open(output_path, 'w') as f:
            json.dump(conversation, f, indent=2, default=str)

        print(f"Conversation saved to {output_path}")

    def visualize_execution_flow(self, agent: "MultiStepAgent"):
        """Create a visual representation of execution flow"""
        # Could use graphviz or mermaid to create flowchart
        pass

# Usage:
debugger = AgentDebugger(output_dir="./debug_outputs")
agent = CodeAgent(tools=[...], model=model)
result = agent.run("Solve this task")
debugger.save_conversation(agent)
```

---

### 6. Testing & Validation (? /10)

Note: Test coverage not visible in current review, but based on project structure:

#### Recommendations

**Priority: HIGH - Add integration tests**

Location: `tests/integration/test_agent_workflows.py`

```python
"""Integration tests for complete agent workflows"""
import pytest
from smolagents import CodeAgent, DuckDuckGoSearchTool, HfApiModel

class TestAgentWorkflows:

    @pytest.fixture
    def agent(self):
        """Create agent for testing"""
        model = HfApiModel()
        return CodeAgent(
            tools=[DuckDuckGoSearchTool()],
            model=model,
            max_steps=5
        )

    def test_simple_calculation(self, agent):
        """Test agent can perform calculations"""
        result = agent.run("What is 15 * 37?")
        assert "555" in str(result)

    def test_web_search_and_synthesis(self, agent):
        """Test agent can search and synthesize information"""
        result = agent.run(
            "What is the capital of France and what is its population?"
        )
        assert "paris" in result.lower()
        # More specific assertions based on expected behavior

    def test_error_recovery(self, agent):
        """Test agent recovers from errors gracefully"""
        # Test with intentionally problematic task
        result = agent.run("Use a tool called 'nonexistent_tool'")
        # Should handle gracefully without crashing
        assert result is not None

    def test_max_steps_limit(self, agent):
        """Test agent respects max_steps limit"""
        agent.max_steps = 2
        with pytest.raises(AgentMaxStepsError):
            agent.run("Solve an intentionally complex task requiring many steps")
```

**Priority: MEDIUM - Add property-based testing**

```python
"""Property-based tests using hypothesis"""
from hypothesis import given, strategies as st
import pytest

class TestToolInputValidation:

    @given(
        tool_name=st.text(min_size=1, max_size=50),
        arguments=st.dictionaries(
            keys=st.text(min_size=1),
            values=st.one_of(st.text(), st.integers(), st.floats())
        )
    )
    def test_execute_tool_handles_arbitrary_inputs(self, agent, tool_name, arguments):
        """Test tool execution with random inputs doesn't crash"""
        try:
            agent.execute_tool_call(tool_name, arguments)
        except AgentExecutionError:
            # Expected for invalid tools/args
            pass
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")
```

---

### 7. Documentation (8/10)

#### Strengths
- Comprehensive README with examples
- Clear architecture diagrams (Mermaid)
- Good inline documentation

#### Improvements

**Priority: MEDIUM - Add architecture decision records (ADRs)**

Location: `docs/architecture/adr/`

```markdown
# ADR-001: Use Code-Based Actions over JSON Tool Calls

## Status
Accepted

## Context
Agents need to execute actions. Two main approaches:
1. LLM outputs JSON describing tool calls
2. LLM outputs Python code that calls tools

## Decision
Use code-based actions (CodeAgent) as the primary approach.

## Consequences

### Positive
- 30% fewer steps than JSON approach (research-backed)
- Higher performance on benchmarks
- More flexible (loops, conditionals, etc.)
- Familiar syntax for developers

### Negative
- Security concerns (requires sandboxing)
- More complex parsing
- Potential for arbitrary code execution

### Mitigation
- Implement E2B sandboxing
- Provide LocalPythonInterpreter with blocked patterns
- Maintain ToolCallingAgent as alternative
```

---

## Quick Start Guide

### Installation

```bash
# Basic installation
pip install smolagents

# With specific features
pip install smolagents[transformers]  # For local models
pip install smolagents[e2b]          # For sandboxed execution
pip install smolagents[all]          # Everything

# Development installation
git clone https://github.com/huggingface/smolagents
cd smolagents
pip install -e ".[dev]"
```

### Your First Agent (5 minutes)

```python
from smolagents import CodeAgent, DuckDuckGoSearchTool, HfApiModel

# 1. Initialize model
model = HfApiModel()

# 2. Create agent with tools
agent = CodeAgent(
    tools=[DuckDuckGoSearchTool()],
    model=model
)

# 3. Run a task
result = agent.run(
    "What is the current population of Tokyo?"
)

print(result)
```

### Using Different Models

```python
# OpenAI
from smolagents import LiteLLMModel
import os

model = LiteLLMModel(
    "gpt-4",
    api_key=os.environ["OPENAI_API_KEY"]
)

# Local transformers model
from smolagents import TransformersModel

model = TransformersModel(
    model_id="Qwen/Qwen2.5-Coder-32B-Instruct",
    device_map="auto"
)

# Anthropic Claude
model = LiteLLMModel(
    "anthropic/claude-3-5-sonnet-latest",
    api_key=os.environ["ANTHROPIC_API_KEY"]
)
```

### Creating Custom Tools

```python
from smolagents import Tool

class WeatherTool(Tool):
    name = "weather"
    description = "Gets current weather for a city"
    inputs = {
        "city": {
            "type": "string",
            "description": "City name"
        }
    }
    output_type = "string"

    def forward(self, city: str) -> str:
        # Your implementation
        return f"Weather in {city}: Sunny, 72°F"

# Use it
agent = CodeAgent(
    tools=[WeatherTool()],
    model=model
)
```

---

## Comprehensive Usage Instructions

### 1. Agent Types

#### CodeAgent (Recommended)

Writes actions as Python code for maximum flexibility.

```python
from smolagents import CodeAgent, HfApiModel

agent = CodeAgent(
    tools=[tool1, tool2],
    model=HfApiModel(),
    max_steps=10,                    # Maximum reasoning steps
    verbosity_level=LogLevel.INFO,   # Logging level
    add_base_tools=True,             # Include built-in tools
)

# The agent can use Python constructs
result = agent.run("""
Search for 'Python tutorials' and 'JavaScript tutorials',
then count which has more results.
""")
```

#### ToolCallingAgent

Uses traditional JSON-based tool calling.

```python
from smolagents import ToolCallingAgent

agent = ToolCallingAgent(
    tools=[tool1, tool2],
    model=model,
    max_steps=6
)
```

### 2. Security: Code Execution

#### Local Python Interpreter (Default)

Safer than exec(), blocks dangerous operations:

```python
agent = CodeAgent(
    tools=[...],
    model=model,
    # Uses LocalPythonInterpreter by default
)
```

#### E2B Sandboxed Execution (Most Secure)

```python
from smolagents import CodeAgent
from smolagents.e2b_executor import E2BExecutor
import os

# Set E2B API key
os.environ["E2B_API_KEY"] = "your-key"

executor = E2BExecutor()

agent = CodeAgent(
    tools=[...],
    model=model,
    # Pass executor to use E2B
)

# Configure agent to use E2B
agent.python_executor = executor
```

### 3. Tools

#### Built-in Tools

```python
from smolagents import (
    DuckDuckGoSearchTool,
    PythonInterpreterTool,
    FinalAnswerTool,  # Automatically added
)

agent = CodeAgent(
    tools=[
        DuckDuckGoSearchTool(),
        # Add your tools
    ],
    model=model,
    add_base_tools=True  # Adds default tools
)
```

#### Loading from Hub

```python
from smolagents import Tool

# Load community tools
tool = Tool.from_hub("username/tool-name")

agent = CodeAgent(tools=[tool], model=model)
```

#### Sharing Tools

```python
# Push your tool to Hub
my_tool = WeatherTool()
my_tool.push_to_hub("username/weather-tool")
```

#### Integration with LangChain

```python
from langchain.tools import DuckDuckGoSearchRun
from smolagents import Tool

# Convert LangChain tool
langchain_tool = DuckDuckGoSearchRun()
smolagent_tool = Tool.from_langchain(langchain_tool)

agent = CodeAgent(tools=[smolagent_tool], model=model)
```

### 4. Multi-Agent Systems

```python
from smolagents import CodeAgent, ManagedAgent

# Create specialized agents
search_agent = CodeAgent(
    tools=[DuckDuckGoSearchTool()],
    model=model,
    name="search_specialist",
    description="Expert at finding information online"
)

data_agent = CodeAgent(
    tools=[PythonInterpreterTool()],
    model=model,
    name="data_analyst",
    description="Expert at analyzing data"
)

# Manager agent coordinates them
manager = CodeAgent(
    tools=[],  # No direct tools
    model=model,
    managed_agents=[search_agent, data_agent]
)

result = manager.run("""
First, search for Tesla stock data.
Then analyze the trends.
""")
```

### 5. Memory & State

#### Conversation Continuity

```python
agent = CodeAgent(tools=[...], model=model)

# First task
agent.run("What is the capital of France?", reset=False)

# Continue conversation (keeps memory)
agent.run("What is its population?", reset=False)

# New conversation (reset memory)
agent.run("Different topic", reset=True)
```

#### Accessing Agent Memory

```python
# After running
agent.run("Some task")

# Access conversation history
for step in agent.memory.steps:
    print(f"Step {step.step_number}: {step}")

# Get metrics
metrics = agent.monitor.get_metrics()
print(f"Total steps: {metrics['total_steps']}")
print(f"Total tokens: {metrics['total_tokens']}")
```

#### Passing Additional State

```python
import pandas as pd

df = pd.DataFrame({'sales': [100, 200, 150]})

result = agent.run(
    "Calculate the average sales",
    additional_args={"sales_data": df}
)

# Agent can access 'sales_data' variable in code
```

### 6. Streaming Responses

```python
agent = CodeAgent(tools=[...], model=model)

# Stream mode returns generator
for step in agent.run("Complex task", stream=True):
    if isinstance(step, ActionStep):
        print(f"Step {step.step_number}")
        print(f"Action: {step.llm_output}")
        print(f"Result: {step.observations}")
    else:
        # Final answer
        print(f"Final: {step}")
```

### 7. CLI Usage

```bash
# Basic usage
smolagent "Analyze this dataset" \
  --model-type "HfApiModel" \
  --model-id "Qwen/Qwen2.5-Coder-32B-Instruct"

# With specific tools
smolagent "Search and summarize Python news" \
  --tools "web_search" \
  --imports "pandas numpy"

# Web browser agent
webagent "Go to example.com, find pricing, return it" \
  --model-type "LiteLLMModel" \
  --model-id "gpt-4o"
```

### 8. Gradio UI

```python
from smolagents import CodeAgent, launch_gradio_demo

agent = CodeAgent(tools=[...], model=model)

# Launch interactive UI
launch_gradio_demo(agent)
```

### 9. Monitoring & Observability

```python
from smolagents import CodeAgent
from smolagents.monitoring import LogLevel

agent = CodeAgent(
    tools=[...],
    model=model,
    verbosity_level=LogLevel.DEBUG  # VERBOSE, DEBUG, INFO, WARNING, ERROR
)

# Visualize agent structure
agent.visualize()

# Custom callbacks
def my_callback(step):
    print(f"Custom: Step {step.step_number} completed")

agent = CodeAgent(
    tools=[...],
    model=model,
    step_callbacks=[my_callback]
)
```

### 10. Advanced: Planning Agents

```python
agent = CodeAgent(
    tools=[...],
    model=model,
    planning_interval=3  # Re-plan every 3 steps
)

# Agent will create and update plans during execution
result = agent.run("Complex multi-step task")
```

---

## Best Practices

### 1. Tool Design

```python
# Good: Specific, single-purpose tool
class PriceFetcherTool(Tool):
    name = "price_fetcher"
    description = "Fetches current price for a product from API"
    # ...

# Avoid: Vague, multi-purpose tool
class GeneralAPItool(Tool):  # ❌ Too broad
    name = "api"
    description = "Does various API things"
```

### 2. Error Handling

```python
# Wrap agent calls in try-except
try:
    result = agent.run(task)
except AgentMaxStepsError:
    print("Task too complex, increase max_steps")
except AgentExecutionError as e:
    print(f"Execution failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### 3. Security

```python
# Always use sandboxed execution for untrusted code
from smolagents.e2b_executor import E2BExecutor

executor = E2BExecutor()
agent = CodeAgent(tools=[...], model=model)
agent.python_executor = executor

# Validate tool inputs
class MyTool(Tool):
    def forward(self, url: str):
        # Validate before using
        if not url.startswith(('http://', 'https://')):
            raise ValueError("Invalid URL")
        # ...
```

### 4. Performance

```python
# Cache repeated operations
from functools import lru_cache

class ExpensiveTool(Tool):
    @lru_cache(maxsize=128)
    def _expensive_operation(self, param):
        # Cached computation
        pass

    def forward(self, param: str):
        return self._expensive_operation(param)

# Limit max_steps for faster responses
agent = CodeAgent(tools=[...], model=model, max_steps=3)
```

### 5. Debugging

```python
# Enable verbose logging
from smolagents.monitoring import LogLevel

agent = CodeAgent(
    tools=[...],
    model=model,
    verbosity_level=LogLevel.DEBUG
)

# Save run for analysis
result = agent.run(task)

import json
with open('agent_run.json', 'w') as f:
    json.dump({
        'task': task,
        'result': str(result),
        'steps': [str(s) for s in agent.memory.steps],
        'metrics': agent.monitor.get_metrics()
    }, f, indent=2, default=str)
```

---

## Troubleshooting

### Common Issues

#### 1. "Unknown tool" Error

```python
# Problem: Tool not properly added
agent = CodeAgent(tools=[], model=model)
result = agent.run("Search for X")  # ❌ No search tool

# Solution: Add required tools
agent = CodeAgent(
    tools=[DuckDuckGoSearchTool()],
    model=model
)
```

#### 2. Max Steps Exceeded

```python
# Problem: Task requires more steps
agent = CodeAgent(tools=[...], model=model, max_steps=3)
agent.run("Very complex task")  # ❌ AgentMaxStepsError

# Solution: Increase max_steps or simplify task
agent.max_steps = 10  # Or break task into smaller parts
```

#### 3. API Rate Limits

```python
# Problem: Too many API calls
# Solution: Add delays or caching

import time

class RateLimitedTool(Tool):
    def forward(self, query: str):
        time.sleep(1)  # Rate limit
        return self._actual_query(query)
```

#### 4. Memory Issues with Long Conversations

```python
# Problem: Memory grows unbounded
agent.run(task1, reset=False)
agent.run(task2, reset=False)
# ... many more tasks

# Solution: Reset periodically
agent.run(task1, reset=True)  # Clear memory
```

#### 5. Import Errors in Code Execution

```python
# Problem: Agent tries to import unavailable package
# Solution: Provide available imports

agent = CodeAgent(
    tools=[...],
    model=model,
    additional_authorized_imports=["requests", "beautifulsoup4"]
)
```

---

## Summary of Improvement Priorities

### High Priority
1. **Add retry mechanism with exponential backoff** (models.py)
2. **Add context managers for resource cleanup** (agents.py)
3. **Improve error messages with suggestions** (utils.py)
4. **Add input validation for tool execution** (agents.py)
5. **Add comprehensive integration tests** (tests/)

### Medium Priority
6. **Improve type hints consistency** (multiple files)
7. **Add rate limiting** (new: rate_limiter.py)
8. **Add caching for repeated operations** (tools.py)
9. **Add comprehensive docstring examples** (tools.py)
10. **Add debug utilities** (new: debug_utils.py)
11. **Add architecture decision records** (docs/)

### Low Priority
12. **Add configuration validation** (agents.py)
13. **Add audit logging** (monitoring.py)
14. **Optimize memory for long conversations** (memory.py)

---

## Conclusion

The **smolagents** library is well-designed with a strong foundation. The suggested improvements focus on:

1. **Robustness**: Better error handling, retries, validation
2. **Developer Experience**: Better docs, debugging tools, type hints
3. **Production Readiness**: Caching, rate limiting, monitoring
4. **Security**: Audit logging, enhanced validation

These improvements will make the library even more suitable for production deployments while maintaining its "smol" philosophy of minimal abstractions.

---

**Generated:** 2025-11-14
**Reviewer:** Claude (AI Code Reviewer)
**Version:** smolagents 1.10.0.dev0
