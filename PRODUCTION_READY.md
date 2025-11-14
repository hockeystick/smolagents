# smolagents - Production-Ready Guide

## 🚀 What's New

This enhanced version of smolagents includes production-ready features:

### Core Improvements

✅ **Retry Mechanism** - Automatic retry with exponential backoff for API calls
✅ **Rate Limiting** - Prevent API overuse and manage costs
✅ **Caching** - LRU cache for tool outputs with TTL support
✅ **Configuration Management** - YAML/JSON config files + environment variables
✅ **Enhanced Error Handling** - Better error messages with context
✅ **Production Logging** - Structured logging with file and console output

### Deployment Features

✅ **Docker Support** - Multi-stage production Dockerfile
✅ **Docker Compose** - Full stack with Redis, Nginx, Prometheus, Grafana
✅ **API Server** - FastAPI-based REST API with health checks
✅ **Kubernetes Ready** - Example K8s manifests with HPA
✅ **CI/CD Pipeline** - GitHub Actions for testing and deployment
✅ **Monitoring** - Built-in metrics and health endpoints

---

## 📦 Quick Deploy (5 minutes)

### Option 1: Docker (Simplest)

```bash
# 1. Clone and enter directory
git clone https://github.com/huggingface/smolagents
cd smolagents

# 2. Setup configuration
make config-example
# Edit .env with your API keys

# 3. Deploy locally
make deploy-local

# 4. Test
curl http://localhost:8000/health
```

### Option 2: Docker Compose (Full Stack)

```bash
# 1. Setup
make config-example
# Edit .env

# 2. Start full stack (app + Redis + monitoring)
make up-full

# 3. Access services
# - API: http://localhost:8000
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000
```

### Option 3: Python (Development)

```bash
# 1. Install
pip install -e ".[all]"

# 2. Create config
cp .env.example .env
# Edit with your settings

# 3. Run
python -c "
from smolagents import CodeAgent, HfApiModel
from smolagents.config import load_config

config = load_config()
agent = CodeAgent(tools=[], model=HfApiModel())
print(agent.run('Calculate 2^10'))
"
```

---

## 🏗️ Architecture

```
smolagents/
├── src/smolagents/
│   ├── agents.py              # Core agent logic
│   ├── tools.py               # Tool system
│   ├── models.py              # LLM integrations
│   ├── config.py              # NEW: Configuration management
│   ├── retry.py               # NEW: Retry mechanism
│   ├── rate_limiter.py        # NEW: Rate limiting
│   ├── tool_cache.py          # NEW: Caching system
│   └── server.py              # NEW: FastAPI server
├── config/
│   └── smolagents.example.yaml # Example configuration
├── docker-compose.yml         # Orchestration
├── Dockerfile.production      # Production image
├── Makefile                   # Build & deploy tasks
└── .github/workflows/         # CI/CD
```

---

## 💡 Usage Examples

### With Configuration File

```python
from smolagents import CodeAgent, HfApiModel
from smolagents.config import load_config

# Load configuration from file
config = load_config('./smolagents.yaml')

# Configuration is automatically applied
agent = CodeAgent(tools=[], model=HfApiModel())
```

### With Retry Mechanism

```python
from smolagents.retry import retry_with_backoff

@retry_with_backoff(max_retries=3, initial_delay=1.0)
def call_api():
    # Your API call
    pass
```

### With Rate Limiting

```python
from smolagents.rate_limiter import RateLimiter

limiter = RateLimiter(max_calls=100, time_window=60)

with limiter.limit():
    # Rate-limited operation
    result = agent.run("Task")
```

### With Caching

```python
from smolagents import CodeAgent
from smolagents.tool_cache import CachedTool
from smolagents.default_tools import DuckDuckGoSearchTool

# Wrap tool with cache
search_tool = DuckDuckGoSearchTool()
cached_search = CachedTool(search_tool)

agent = CodeAgent(tools=[cached_search], model=model)

# First call: executes and caches
result1 = agent.run("Search for Python")

# Second call with same query: returns cached result
result2 = agent.run("Search for Python")
```

### API Server

```python
# Run server
python -m smolagents.server

# Or with uvicorn
uvicorn smolagents.server:app --host 0.0.0.0 --port 8000
```

```bash
# Make API requests
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "What is 2^10?",
    "model_type": "HfApiModel",
    "tools": [],
    "max_steps": 5
  }'
```

---

## ⚙️ Configuration

### Configuration Priority

1. Environment Variables (highest priority)
2. Configuration File (smolagents.yaml)
3. Defaults (lowest priority)

### Configuration File Example

```yaml
# smolagents.yaml
retry:
  enabled: true
  max_retries: 3
  initial_delay: 1.0

rate_limit:
  enabled: true
  max_calls: 100
  time_window: 60.0

cache:
  enabled: true
  max_size: 256
  ttl: 3600.0

agent:
  max_steps: 10
  add_base_tools: true

server:
  host: 0.0.0.0
  port: 8000
  workers: 4
```

### Environment Variables

```bash
# Agent settings
export SMOLAGENTS_MAX_STEPS=10
export SMOLAGENTS_LOG_LEVEL=INFO

# API keys
export HF_API_KEY=your_key
export OPENAI_API_KEY=your_key

# Performance
export SMOLAGENTS_CACHE_ENABLED=true
export SMOLAGENTS_RATE_LIMIT_ENABLED=true
```

---

## 🔧 Makefile Commands

```bash
# See all commands
make help

# Development
make install-dev      # Install with dev dependencies
make test             # Run tests
make quality          # Check code quality
make style            # Format code

# Configuration
make config-example   # Create example configs
make config-validate  # Validate configuration

# Docker
make docker-build     # Build Docker image
make docker-run       # Run container
make docker-stop      # Stop container

# Deployment
make deploy-local     # Deploy locally
make up               # Start with docker-compose
make up-full          # Start full stack
make down             # Stop services

# Monitoring
make health-check     # Check service health
make metrics          # Get metrics
make logs             # View logs
```

---

## 📊 Monitoring

### Health Check

```bash
curl http://localhost:8000/health

# Response
{
  "status": "healthy",
  "version": "1.10.0",
  "timestamp": 1234567890.123,
  "config": {...}
}
```

### Metrics

```bash
curl http://localhost:8000/metrics

# Response
{
  "agents_cached": 3,
  "cache_keys": ["..."],
  "requests_total": 150,
  "requests_failed": 5
}
```

### Logging

```python
# Logs are written to:
# - Console (stdout)
# - File: ./logs/smolagents.log
# - Audit log: ./logs/audit.log (if enabled)

# Configure in smolagents.yaml:
monitoring:
  log_level: DEBUG  # DEBUG, INFO, WARNING, ERROR
  log_file: ./logs/smolagents.log
```

---

## 🔒 Security

### E2B Sandboxing

```yaml
# In smolagents.yaml
security:
  use_e2b: true
```

```bash
export E2B_API_KEY=your_e2b_key
```

### Allowed Imports

```yaml
security:
  allowed_imports:
    - numpy
    - pandas
    - math
  block_dangerous_patterns: true
```

### Audit Logging

```yaml
security:
  audit_log_enabled: true
  audit_log_path: ./logs/audit.log
```

---

## 📈 Performance Tuning

### Increase Cache Size

```yaml
cache:
  max_size: 512     # More cached items
  ttl: 7200.0       # 2 hours
```

### Adjust Rate Limits

```yaml
rate_limit:
  max_calls: 200    # More calls allowed
  time_window: 60.0
```

### Worker Scaling

```yaml
server:
  workers: 4        # Number of worker processes
```

---

## 🚀 Deployment Patterns

### Pattern 1: Simple API

```bash
make docker-build
make docker-run
```

### Pattern 2: High Availability

```bash
# Use docker-compose with multiple replicas
docker-compose up --scale smolagents=3 -d
```

### Pattern 3: Kubernetes

```bash
kubectl apply -f k8s-deployment.yaml
kubectl get pods -n smolagents
```

### Pattern 4: Serverless

- Use AWS Lambda, Google Cloud Functions, or Azure Functions
- Package application with dependencies
- Configure API Gateway for routing

---

## 🛠️ Troubleshooting

### Check Logs

```bash
# Docker
docker logs smolagents

# Docker Compose
make logs

# File
tail -f logs/smolagents.log
```

### Validate Configuration

```bash
make config-validate
```

### Health Check

```bash
make health-check
```

### Clear Cache

```bash
make clear-cache
```

### Debug Mode

```bash
export SMOLAGENTS_LOG_LEVEL=DEBUG
```

---

## 📝 Migration from Previous Version

### From Original smolagents

No breaking changes! All existing code works as before.

New features are opt-in:

```python
# Old way (still works)
from smolagents import CodeAgent, HfApiModel
agent = CodeAgent(tools=[], model=HfApiModel())

# New way (with config)
from smolagents.config import load_config
config = load_config()  # Loads configuration
agent = CodeAgent(tools=[], model=HfApiModel())
```

### Recommended Updates

1. **Add configuration file**:
   ```bash
   cp config/smolagents.example.yaml smolagents.yaml
   ```

2. **Use environment variables**:
   ```bash
   cp .env.example .env
   # Edit with your keys
   ```

3. **Enable caching** (optional):
   ```python
   from smolagents.tool_cache import CachedTool
   cached_tool = CachedTool(your_tool)
   ```

---

## 📚 Additional Resources

- **Code Review**: See [CODE_REVIEW_AND_USAGE_GUIDE.md](CODE_REVIEW_AND_USAGE_GUIDE.md)
- **Deployment**: See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Documentation**: https://huggingface.co/docs/smolagents

---

## ✅ Production Checklist

Before deploying to production:

- [ ] API keys stored securely (environment variables or secrets manager)
- [ ] Configuration file reviewed and customized
- [ ] E2B sandboxing enabled (if applicable)
- [ ] Rate limiting configured
- [ ] Logging configured
- [ ] Health checks working
- [ ] Monitoring setup (Prometheus/Grafana)
- [ ] Resource limits set (CPU, memory)
- [ ] Backup strategy for logs
- [ ] CI/CD pipeline configured
- [ ] Load testing completed
- [ ] Security scan passed
- [ ] Documentation updated

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📜 License

Apache 2.0 - See [LICENSE](LICENSE)

---

**Version**: 1.10.0 (Production-Ready)
**Last Updated**: 2025-11-14
