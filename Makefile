.PHONY: quality style test docs utils install install-dev \
        docker-build docker-run docker-push docker-clean \
        deploy-local deploy-staging deploy-production \
        config-example health-check logs clean

check_dirs := examples src tests utils

# =============================================================================
# Development
# =============================================================================

# Install package
install:
	pip install -e .

# Install with all dependencies for development
install-dev:
	pip install -e ".[dev]"

# Install for production
install-prod:
	pip install -e ".[all]"

# Check code quality of the source code
quality:
	ruff check $(check_dirs)
	ruff format --check $(check_dirs)
	python utils/check_tests_in_ci.py

# Format source code automatically
style:
	ruff check $(check_dirs) --fix
	ruff format $(check_dirs)

# Run smolagents tests
test:
	pytest ./tests/

# Run tests with coverage
test-cov:
	pytest ./tests/ --cov=smolagents --cov-report=html --cov-report=term

# =============================================================================
# Configuration
# =============================================================================

# Create example configuration files
config-example:
	@echo "Creating example configuration files..."
	@cp -n .env.example .env || echo ".env already exists"
	@cp -n config/smolagents.example.yaml smolagents.yaml || echo "smolagents.yaml already exists"
	@echo "✓ Configuration files created. Please edit them with your settings."

# Validate configuration
config-validate:
	@python -c "from smolagents.config import load_config; config = load_config(); print('✓ Configuration valid')"

# =============================================================================
# Docker
# =============================================================================

# Build production Docker image
docker-build:
	docker build -f Dockerfile.production -t smolagents:latest .

# Build with specific extras
docker-build-lightweight:
	docker build --build-arg INSTALL_EXTRAS="transformers,e2b" -f Dockerfile.production -t smolagents:lightweight .

# Run Docker container locally
docker-run:
	docker run -d --name smolagents \
		-p 8000:8000 \
		--env-file .env \
		-v $$(pwd)/logs:/logs \
		-v $$(pwd)/data:/data \
		smolagents:latest

# Push Docker image to registry
docker-push:
	docker tag smolagents:latest $(DOCKER_REGISTRY)/smolagents:latest
	docker push $(DOCKER_REGISTRY)/smolagents:latest

# Stop and remove Docker container
docker-stop:
	docker stop smolagents || true
	docker rm smolagents || true

# Clean Docker resources
docker-clean: docker-stop
	docker rmi smolagents:latest || true
	docker system prune -f

# =============================================================================
# Docker Compose
# =============================================================================

# Start all services
up:
	docker-compose up -d

# Start with Redis
up-with-redis:
	docker-compose --profile with-redis up -d

# Start with monitoring
up-with-monitoring:
	docker-compose --profile monitoring up -d

# Start full stack
up-full:
	docker-compose --profile with-redis --profile with-nginx --profile monitoring up -d

# Stop all services
down:
	docker-compose down

# View logs
logs:
	docker-compose logs -f smolagents

# Restart services
restart:
	docker-compose restart

# =============================================================================
# Deployment
# =============================================================================

# Deploy locally for testing
deploy-local: config-example docker-build docker-run
	@echo "✓ Deployed locally. Access at http://localhost:8000"
	@echo "  Health check: curl http://localhost:8000/health"

# Deploy to staging
deploy-staging:
	@echo "Deploying to staging..."
	@# Add your staging deployment commands here
	@# kubectl apply -f k8s/staging/ -n smolagents-staging

# Deploy to production
deploy-production:
	@echo "Deploying to production..."
	@# Add your production deployment commands here
	@# kubectl apply -f k8s/production/ -n smolagents-production

# =============================================================================
# Monitoring & Health
# =============================================================================

# Check health
health-check:
	@curl -f http://localhost:8000/health || echo "Service not healthy"

# Get metrics
metrics:
	@curl -s http://localhost:8000/metrics | python -m json.tool

# Clear cache
clear-cache:
	@curl -X POST http://localhost:8000/clear_cache

# =============================================================================
# Maintenance
# =============================================================================

# Clean up generated files
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Full clean including Docker
clean-all: clean docker-clean
	rm -rf logs/*
	rm -rf data/*

# =============================================================================
# Release
# =============================================================================

# Create a new release (use: make release VERSION=1.2.3)
release:
	@if [ -z "$(VERSION)" ]; then echo "Please specify VERSION (e.g., make release VERSION=1.2.3)"; exit 1; fi
	@echo "Creating release $(VERSION)..."
	@git tag -a v$(VERSION) -m "Release version $(VERSION)"
	@git push origin v$(VERSION)
	@echo "✓ Release v$(VERSION) created and pushed"

# =============================================================================
# Help
# =============================================================================

help:
	@echo "Smolagents Makefile Commands"
	@echo ""
	@echo "Development:"
	@echo "  make install          - Install package"
	@echo "  make install-dev      - Install with dev dependencies"
	@echo "  make quality          - Check code quality"
	@echo "  make style            - Format code"
	@echo "  make test             - Run tests"
	@echo "  make test-cov         - Run tests with coverage"
	@echo ""
	@echo "Configuration:"
	@echo "  make config-example   - Create example config files"
	@echo "  make config-validate  - Validate configuration"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build     - Build Docker image"
	@echo "  make docker-run       - Run Docker container"
	@echo "  make docker-stop      - Stop Docker container"
	@echo "  make docker-clean     - Clean Docker resources"
	@echo ""
	@echo "Docker Compose:"
	@echo "  make up               - Start services"
	@echo "  make up-with-redis    - Start with Redis"
	@echo "  make up-full          - Start full stack"
	@echo "  make down             - Stop services"
	@echo "  make logs             - View logs"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy-local     - Deploy locally"
	@echo "  make deploy-staging   - Deploy to staging"
	@echo "  make deploy-production - Deploy to production"
	@echo ""
	@echo "Monitoring:"
	@echo "  make health-check     - Check service health"
	@echo "  make metrics          - Get metrics"
	@echo "  make clear-cache      - Clear cache"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean            - Clean generated files"
	@echo "  make clean-all        - Full clean including Docker"
	@echo "  make release VERSION=x.y.z - Create new release"