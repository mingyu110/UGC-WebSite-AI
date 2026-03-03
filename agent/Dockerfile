# Dockerfile for AgentCore Runtime deployment
# ARM64 architecture required by AgentCore Runtime

FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY . .

# AgentCore Runtime requires port 8080
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# Run the agent using BedrockAgentCoreApp
CMD ["python", "-m", "uvicorn", "agentcore_handler:app", "--host", "0.0.0.0", "--port", "8080"]
