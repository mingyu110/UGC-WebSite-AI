# UGC AI Demo - Backend Service Dockerfile
# For deployment to ECS Fargate

# Use ECR public registry to avoid Docker Hub rate limiting
FROM public.ecr.aws/docker/library/python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright CDP connection
# Note: We don't need browser binaries since we use AgentCore remote browser
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright (only needs websocket client, not browser binaries)
# AgentCore Browser runs in AWS cloud, we just connect via CDP
RUN playwright install-deps chromium || true

# Copy application code
COPY agent/ ./agent/
COPY mcp_servers/ ./mcp_servers/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "uvicorn", "agent.server:app", "--host", "0.0.0.0", "--port", "8000"]
