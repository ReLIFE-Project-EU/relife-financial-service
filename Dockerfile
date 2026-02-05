# Multi-stage build: First stage builds the wheel package
FROM python:3.11-slim AS builder

# Set working directory for build stage
WORKDIR /app

# Install system dependencies needed for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy project configuration and source code
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# Create virtual environment and install build dependencies
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install build

# Build wheel package for distribution
RUN python -m build --wheel .

# Second stage: Runtime image with minimal dependencies
FROM python:3.11-slim AS runtime

# Set working directory for runtime
WORKDIR /app

# Install minimal runtime dependencies (curl for health checks, libgomp1 for LightGBM)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy built wheel from builder stage and install it
COPY --from=builder /app/dist/*.whl /app/
RUN pip install --no-cache-dir /app/*.whl

# Configure API server environment variables
ENV API_HOST=0.0.0.0
ENV API_PORT=9090

# Expose the API port
EXPOSE 9090

# Start the service API
CMD ["run-service"]