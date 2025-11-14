# smolagents Deployment Guide

Complete guide for deploying smolagents in production environments.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Docker Deployment](#docker-deployment)
3. [Docker Compose Deployment](#docker-compose-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Configuration](#configuration)
6. [Security Best Practices](#security-best-practices)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- Python 3.10+
- Docker (optional, for containerized deployment)
- Docker Compose (optional, for orchestrated deployment)

### Local Development

```bash
# 1. Clone repository
git clone https://github.com/huggingface/smolagents
cd smolagents

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -e ".[all]"

# 4. Create environment file
cp .env.example .env
# Edit .env and add your API keys

# 5. Run basic example
python -c "
from smolagents import CodeAgent, HfApiModel
agent = CodeAgent(tools=[], model=HfApiModel())
print(agent.run('What is 2^10?'))
"
```

---

## Docker Deployment

### Build Production Image

```bash
# Build with all dependencies
docker build -f Dockerfile.production -t smolagents:latest .

# Build with specific extras only
docker build \
  --build-arg INSTALL_EXTRAS="transformers,e2b" \
  -f Dockerfile.production \
  -t smolagents:lightweight .
```

### Run Container

```bash
# Run with environment variables
docker run -d \
  --name smolagents \
  -p 8000:8000 \
  -e HF_API_KEY=your_key \
  -e SMOLAGENTS_LOG_LEVEL=INFO \
  -v $(pwd)/logs:/logs \
  -v $(pwd)/data:/data \
  smolagents:latest

# Check logs
docker logs -f smolagents

# Check health
curl http://localhost:8000/health
```

### Production Deployment Options

#### Option 1: API Server

```bash
docker run -d \
  --name smolagents-api \
  --restart unless-stopped \
  -p 8000:8000 \
  -e HF_API_KEY=${HF_API_KEY} \
  -e SMOLAGENTS_MAX_STEPS=10 \
  -e SMOLAGENTS_LOG_LEVEL=INFO \
  -v smolagents-data:/data \
  -v smolagents-logs:/logs \
  --memory="4g" \
  --cpus="2.0" \
  smolagents:latest \
  python -m smolagents.server
```

#### Option 2: CLI Mode

```bash
docker run -it --rm \
  -e HF_API_KEY=${HF_API_KEY} \
  -v $(pwd)/data:/data \
  smolagents:latest \
  smolagent "Your task here" \
    --model-type HfApiModel \
    --model-id "Qwen/Qwen2.5-Coder-32B-Instruct"
```

---

## Docker Compose Deployment

### Basic Deployment

```bash
# 1. Create environment file
cp .env.example .env
# Edit .env with your settings

# 2. Start services
docker-compose up -d

# 3. Check status
docker-compose ps

# 4. View logs
docker-compose logs -f smolagents

# 5. Stop services
docker-compose down
```

### With Redis Caching

```bash
# Start with Redis profile
docker-compose --profile with-redis up -d

# Verify Redis connection
docker-compose exec redis redis-cli ping
```

### With Nginx Reverse Proxy

```bash
# 1. Create Nginx configuration
mkdir -p config
cat > config/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream smolagents {
        server smolagents:8000;
    }

    server {
        listen 80;
        server_name localhost;

        location / {
            proxy_pass http://smolagents;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /health {
            proxy_pass http://smolagents/health;
            access_log off;
        }
    }
}
EOF

# 2. Start with Nginx
docker-compose --profile with-nginx up -d
```

### With Monitoring (Prometheus + Grafana)

```bash
# 1. Create Prometheus config
mkdir -p config
cat > config/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'smolagents'
    static_configs:
      - targets: ['smolagents:8000']
EOF

# 2. Start monitoring stack
docker-compose --profile monitoring up -d

# 3. Access dashboards
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
```

### Full Production Stack

```bash
# Start all services
docker-compose \
  --profile with-redis \
  --profile with-nginx \
  --profile monitoring \
  up -d

# Verify all services are running
docker-compose ps

# Check health
curl http://localhost/health
```

---

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (1.20+)
- kubectl configured
- Helm (optional)

### Create Namespace

```bash
kubectl create namespace smolagents
```

### Create Secrets

```bash
# Create secret for API keys
kubectl create secret generic smolagents-secrets \
  --from-literal=HF_API_KEY=your_key \
  --from-literal=OPENAI_API_KEY=your_key \
  --from-literal=ANTHROPIC_API_KEY=your_key \
  --from-literal=E2B_API_KEY=your_key \
  -n smolagents
```

### Deployment Manifest

Create `k8s-deployment.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: smolagents-config
  namespace: smolagents
data:
  SMOLAGENTS_LOG_LEVEL: "INFO"
  SMOLAGENTS_MAX_STEPS: "10"
  SMOLAGENTS_PORT: "8000"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: smolagents
  namespace: smolagents
spec:
  replicas: 3
  selector:
    matchLabels:
      app: smolagents
  template:
    metadata:
      labels:
        app: smolagents
    spec:
      containers:
      - name: smolagents
        image: smolagents:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: HF_API_KEY
          valueFrom:
            secretKeyRef:
              name: smolagents-secrets
              key: HF_API_KEY
        envFrom:
        - configMapRef:
            name: smolagents-config
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        volumeMounts:
        - name: data
          mountPath: /data
        - name: logs
          mountPath: /logs
      volumes:
      - name: data
        emptyDir: {}
      - name: logs
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: smolagents-service
  namespace: smolagents
spec:
  selector:
    app: smolagents
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: smolagents-hpa
  namespace: smolagents
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: smolagents
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Deploy to Kubernetes

```bash
# Apply deployment
kubectl apply -f k8s-deployment.yaml

# Check deployment status
kubectl get deployments -n smolagents
kubectl get pods -n smolagents
kubectl get svc -n smolagents

# Check logs
kubectl logs -f deployment/smolagents -n smolagents

# Get service URL
kubectl get svc smolagents-service -n smolagents

# Test health endpoint
kubectl port-forward svc/smolagents-service 8000:80 -n smolagents
curl http://localhost:8000/health
```

---

## Configuration

### Configuration File

Create `smolagents.yaml`:

```yaml
retry:
  enabled: true
  max_retries: 3
  initial_delay: 1.0
  max_delay: 60.0
  backoff_factor: 2.0

rate_limit:
  enabled: true
  max_calls: 100
  time_window: 60.0

cache:
  enabled: true
  max_size: 256
  ttl: 3600.0

security:
  use_e2b: false
  allowed_imports:
    - numpy
    - pandas
    - math
    - datetime
  block_dangerous_patterns: true
  audit_log_enabled: true
  audit_log_path: ./logs/audit.log

monitoring:
  log_level: INFO
  log_file: ./logs/smolagents.log
  metrics_enabled: true

agent:
  max_steps: 10
  add_base_tools: true

server:
  host: 0.0.0.0
  port: 8000
  workers: 4
  timeout: 300
```

### Environment Variables

Priority: Environment Variables > Config File > Defaults

```bash
# Core settings
export SMOLAGENTS_LOG_LEVEL=DEBUG
export SMOLAGENTS_MAX_STEPS=10

# API keys
export HF_API_KEY=your_key
export OPENAI_API_KEY=your_key

# Performance
export SMOLAGENTS_CACHE_ENABLED=true
export SMOLAGENTS_RATE_LIMIT_ENABLED=true

# Server
export SMOLAGENTS_HOST=0.0.0.0
export SMOLAGENTS_PORT=8000
```

---

## Security Best Practices

### 1. Use E2B for Sandboxed Execution

```yaml
# In smolagents.yaml
security:
  use_e2b: true
```

```bash
# Set E2B API key
export E2B_API_KEY=your_e2b_api_key
```

### 2. Restrict Imports

```yaml
security:
  allowed_imports:
    - numpy
    - pandas
    - math
    # Only allow necessary modules
```

### 3. Enable Audit Logging

```yaml
security:
  audit_log_enabled: true
  audit_log_path: /secure/path/audit.log
```

### 4. Use Secrets Management

**Docker Compose:**
```bash
# Use Docker secrets
docker secret create hf_api_key your_key_file
```

**Kubernetes:**
```bash
# Use Kubernetes secrets
kubectl create secret generic api-keys \
  --from-literal=hf_api=your_key \
  -n smolagents
```

### 5. Network Security

- Use TLS/SSL for all external connections
- Implement API authentication
- Restrict network access with firewall rules

### 6. Resource Limits

```yaml
# Docker Compose
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 4G
```

```yaml
# Kubernetes
resources:
  limits:
    memory: "4Gi"
    cpu: "2000m"
```

---

## Monitoring

### Health Checks

```bash
# HTTP health check
curl http://localhost:8000/health

# Response
{
  "status": "healthy",
  "version": "1.10.0",
  "timestamp": 1234567890.123,
  "config": {...}
}
```

### Metrics Endpoint

```bash
curl http://localhost:8000/metrics

# Response
{
  "agents_cached": 3,
  "cache_keys": [...],
  "requests_total": 150,
  "requests_failed": 5
}
```

### Logs

```bash
# Docker
docker logs -f smolagents

# Docker Compose
docker-compose logs -f smolagents

# Kubernetes
kubectl logs -f deployment/smolagents -n smolagents

# File-based logging
tail -f logs/smolagents.log
```

### Prometheus Metrics (Optional)

Add to your application:

```python
from prometheus_client import Counter, Histogram

request_counter = Counter('smolagents_requests_total', 'Total requests')
request_duration = Histogram('smolagents_request_duration_seconds', 'Request duration')
```

---

## Troubleshooting

### Common Issues

#### 1. Container Won't Start

```bash
# Check logs
docker logs smolagents

# Common causes:
# - Missing API keys
# - Invalid configuration
# - Port already in use
```

**Solution:**
```bash
# Verify environment
docker run --rm smolagents:latest env | grep SMOLAGENTS

# Check port availability
lsof -i :8000
```

#### 2. Out of Memory

```bash
# Check memory usage
docker stats smolagents
```

**Solution:**
```bash
# Increase memory limit
docker run -m 4g smolagents:latest

# Or in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G
```

#### 3. Rate Limit Errors

**Solution:**
```yaml
# Increase rate limits in config
rate_limit:
  max_calls: 200
  time_window: 60.0
```

#### 4. Agent Timeout

**Solution:**
```bash
# Increase timeout
export SMOLAGENTS_TIMEOUT=600

# Increase max steps
export SMOLAGENTS_MAX_STEPS=20
```

#### 5. Cache Issues

```bash
# Clear cache
curl -X POST http://localhost:8000/clear_cache

# Disable cache temporarily
export SMOLAGENTS_CACHE_ENABLED=false
```

### Debug Mode

```bash
# Enable debug logging
export SMOLAGENTS_LOG_LEVEL=DEBUG

# Run with verbose output
docker-compose up smolagents  # without -d
```

### Performance Tuning

#### 1. Optimize Cache Settings

```yaml
cache:
  max_size: 512  # Increase cache size
  ttl: 7200.0    # 2 hours
```

#### 2. Adjust Worker Count

```yaml
server:
  workers: 4  # Number of CPU cores
```

#### 3. Database Connection Pooling (if using DB)

```python
# Example for PostgreSQL
pool_size = 20
max_overflow = 10
```

---

## Production Checklist

- [ ] API keys stored securely (environment variables or secrets manager)
- [ ] E2B sandboxing enabled for production
- [ ] TLS/SSL certificates configured
- [ ] Rate limiting enabled
- [ ] Resource limits set
- [ ] Health checks configured
- [ ] Monitoring and alerting setup
- [ ] Audit logging enabled
- [ ] Backup strategy for logs and data
- [ ] Auto-scaling configured (K8s HPA or similar)
- [ ] Load balancer configured
- [ ] Error tracking (Sentry, etc.)
- [ ] Log aggregation (ELK, Loki, etc.)
- [ ] Documentation for team
- [ ] Runbook for incidents

---

## Support

- **Documentation**: https://huggingface.co/docs/smolagents
- **Issues**: https://github.com/huggingface/smolagents/issues
- **Discord**: HuggingFace community

---

**Version**: 1.10.0
**Last Updated**: 2025-11-14
